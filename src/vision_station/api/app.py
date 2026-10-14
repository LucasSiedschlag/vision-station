"""The local API (architecture §10.1): the operator and admin screens talk to the core only through it.

HTTP for commands and queries, one WebSocket (`/live`) for the reduced live view and for state and
result events. Operator endpoints need no login; the rest need a Supervisor or Maintainer token
(`POST /login`, then `Authorization: Bearer <token>`). It listens on 127.0.0.1 by default, accepts only
local Host headers, and refuses browser requests from other origins.
"""

import asyncio
import base64
import dataclasses
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
from fastapi import Depends, FastAPI, Header, HTTPException, Query as QueryParam, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from vision_station import __version__
from vision_station.api.auth import AuthError, AuthService, LockedOut, at_least
from vision_station.api.hub import EventHub
from vision_station.records import InspectionRecord, Query, ResultRecorder, ResultsError, ResultStore
from vision_station.station import Acquisition, StationController, StationEvent
from vision_station.store import FormatError, JobRef, JobStore, StoreError
from vision_station.store.archive import kind_of
from vision_station.verification import VerificationFailed, activate, verify_stored_job
from vision_station.verification.verify import Inspector

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_UPLOAD = 256 * 1024 * 1024
_BACKUP_NAME = re.compile(r"backup_[0-9_-]+\.vbak")


def _start_of_today() -> datetime:
    return datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass
class ApiDeps:
    controller: StationController
    acquisition: Acquisition
    jobs: JobStore
    results: ResultStore
    auth: AuthService
    inspect: Inspector
    recorder: ResultRecorder | None = None
    backup_dir: Path | None = None
    shift_start: Callable[[], datetime] = _start_of_today  # counters for "the current shift": since this moment
    frame_fps: float = 10.0  # the live view is reduced to at most this (NFR-PERF-4)
    frame_width: int = 960
    jpeg_quality: int = 70
    heartbeat_s: float = 2.0
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "[::1]")
    hub: EventHub = field(default_factory=EventHub)


def make_event_handler(deps: ApiDeps) -> Callable[[StationEvent], None]:
    """The `on_event` for the controller: record the result, then tell the screens."""

    def handle(event: StationEvent) -> None:
        if deps.recorder is not None:
            deps.recorder(event)
        deps.hub.publish(event_message(deps, event))

    return handle


def _result_json(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    return {"outcome": str(result.outcome), "reason": result.reason, "scores": dict(result.scores), "duration_ms": round(result.duration_s * 1000)}


def event_message(deps: ApiDeps, event: StationEvent) -> dict[str, Any]:
    if event.kind == "result":
        return {
            "type": "result",
            **_result_json(event.result),
            "job": {"id": event.job_id, "name": event.job_name, "version": event.job_version},
            "record_id": deps.recorder.last_record_id if deps.recorder else None,
        }
    return {"type": "state", "state": str(event.state), "previous": str(event.previous) if event.previous else None, "message": event.message}


def status_json(deps: ApiDeps) -> dict[str, Any]:
    status = deps.controller.status()
    acq = deps.acquisition
    age = acq.age_s()
    return {
        "state": str(status.state),
        "message": status.message,
        "detail": status.detail,
        "warnings": list(status.warnings),
        "job": {"id": status.job_id, "name": status.job_name, "version": status.job_version},
        "last_result": _result_json(status.last_result),
        "last_record_id": deps.recorder.last_record_id if deps.recorder else None,
        "camera": {"connected": acq.connected, "last_frame_age_s": None if age is None else round(age, 2), "last_error": acq.last_error},
        "counters": deps.results.counts(deps.shift_start()),
        "recording_failures": deps.recorder.failures if deps.recorder else 0,
        "version": __version__,
    }


def _record_json(r: InspectionRecord) -> dict[str, Any]:
    return dataclasses.asdict(r)


def encode_jpeg(image: Any, width: int, quality: int) -> bytes:
    h, w = image.shape[:2]
    if w > width:
        image = cv2.resize(image, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("cannot encode the frame")
    return data.tobytes()


class LoginBody(BaseModel):
    role: str
    password: str


class ActivateBody(BaseModel):
    override_reason: str | None = None


class IncorrectBody(BaseModel):
    correct: str
    by: str = ""


class CollectionBody(BaseModel):
    enabled: bool


def content_security_policy(index_html: str) -> str:
    """Scripts only from this server, plus the one inline import map of index.html (by its hash)."""
    m = re.search(r'<script type="importmap">(.*?)</script>', index_html, re.S)
    inline = f" 'sha256-{base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode()}'" if m else ""
    return (
        f"default-src 'self'; script-src 'self'{inline}; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; connect-src 'self' ws://localhost:* ws://127.0.0.1:* ws://[::1]:*; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )


def create_app(deps: ApiDeps) -> FastAPI:
    app = FastAPI(title="Vision Station", version=__version__)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(deps.allowed_hosts))

    def origin_allowed(origin: str | None) -> bool:
        """No Origin header (not a browser page) or one of this machine's own addresses."""
        if not origin:
            return True
        host = re.sub(r"^https?://", "", origin).split("/")[0]
        host = host.rsplit(":", 1)[0] if not host.endswith("]") else host
        return host.strip("[]") in {h.strip("[]") for h in deps.allowed_hosts}

    @app.middleware("http")
    async def refuse_other_origins(request: Request, call_next):
        # a web page on another site must not drive the station through the browser
        if not origin_allowed(request.headers.get("origin")):
            return JSONResponse({"detail": "origin not allowed"}, status_code=403)
        return await call_next(request)

    def token_of(authorization: str | None) -> str | None:
        if authorization and authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return None

    def role(authorization: str | None = Header(default=None)) -> str:
        return deps.auth.role_of(token_of(authorization))

    def need(minimum: str):
        def check(current: str = Depends(role)) -> str:
            if not at_least(current, minimum):
                raise HTTPException(401 if current == "operator" else 403, f"needs a {minimum} login")
            return current

        return check

    def jobref(job_id: str, version: int) -> JobRef:
        ref = JobRef(job_id, version)
        if version not in deps.jobs.versions(job_id):
            raise HTTPException(404, "no such job version")
        return ref

    # --- operator: no login ----------------------------------------------------------

    @app.get("/state")
    def state() -> dict[str, Any]:
        return status_json(deps)

    @app.get("/result/last")
    def last_result() -> dict[str, Any]:
        result = deps.controller.last_result
        if result is None:
            raise HTTPException(404, "no result yet")
        return {**_result_json(result), "record_id": deps.recorder.last_record_id if deps.recorder else None}

    @app.get("/snapshot.jpg")
    def snapshot() -> Response:
        frame = deps.acquisition.latest()
        if frame is None:
            raise HTTPException(503, "no image from the camera")
        return Response(encode_jpeg(frame.image, deps.frame_width, deps.jpeg_quality), media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/trigger", status_code=202)
    def trigger() -> dict[str, Any]:
        """Manual (FR-TRG-3) and external (FR-TRG-2) trigger."""
        if deps.controller.state.value not in ("Ready", "WaitingStill"):
            raise HTTPException(409, f"the station is not ready ({deps.controller.state.value})")
        deps.controller.request_trigger()
        return {"accepted": True}

    @app.post("/results/{record_id}/incorrect")
    def mark_incorrect(record_id: str, body: IncorrectBody) -> dict[str, Any]:
        """The operator or supervisor says a result was wrong; the image becomes labeled training data (FR-MDL-2)."""
        try:
            return _record_json(deps.results.mark_incorrect(record_id, body.correct, body.by))
        except ResultsError as exc:
            raise HTTPException(404 if "no such result" in str(exc) else 400, str(exc)) from exc

    @app.websocket("/live")
    async def live(ws: WebSocket) -> None:
        """Text messages: the state at connect and every few seconds, then state and result events.
        Binary messages: JPEG frames, at most `frame_fps` per second."""
        if not origin_allowed(ws.headers.get("origin")):  # the same rule for the WebSocket handshake
            await ws.close(code=1008)
            return
        await ws.accept()
        loop = asyncio.get_running_loop()
        queue = deps.hub.subscribe()
        try:
            await ws.send_json({"type": "status", **status_json(deps)})
            interval = 1.0 / deps.frame_fps
            next_frame = loop.time()
            next_beat = loop.time() + deps.heartbeat_s
            last_stamp = None
            while True:
                wait = max(0.0, min(next_frame, next_beat) - loop.time())
                try:
                    await ws.send_json(await asyncio.wait_for(queue.get(), wait))
                    continue
                except asyncio.TimeoutError:
                    pass
                now = loop.time()
                if now >= next_beat:
                    next_beat = now + deps.heartbeat_s
                    await ws.send_json({"type": "status", **await loop.run_in_executor(None, status_json, deps)})
                if now >= next_frame:
                    next_frame = now + interval
                    frame = deps.acquisition.latest()
                    if frame is not None and frame.timestamp != last_stamp:
                        last_stamp = frame.timestamp
                        await ws.send_bytes(await loop.run_in_executor(None, encode_jpeg, frame.image, deps.frame_width, deps.jpeg_quality))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            deps.hub.unsubscribe(queue)

    # --- login -----------------------------------------------------------------------

    @app.post("/login")
    def login(body: LoginBody) -> dict[str, Any]:
        try:
            token, seconds = deps.auth.login(body.role, body.password)
        except LockedOut as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": str(int(exc.seconds) + 1)}) from exc
        except AuthError as exc:
            raise HTTPException(401, "wrong role or password") from exc
        return {"token": token, "role": body.role, "expires_in_s": seconds}

    @app.post("/logout")
    def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
        deps.auth.logout(token_of(authorization))
        return {"ok": True}

    @app.get("/whoami")
    def whoami(current: str = Depends(role)) -> dict[str, str]:
        return {"role": current}

    # --- supervisor: jobs ------------------------------------------------------------

    @app.get("/jobs")
    def list_jobs(_: str = Depends(need("supervisor"))) -> dict[str, Any]:
        active = deps.jobs.get_active()
        out = []
        for job_id in deps.jobs.job_ids():
            latest = deps.jobs.latest(job_id)
            info = deps.jobs.load(JobRef(job_id, latest)).job.job  # type: ignore[arg-type]
            out.append({"id": job_id, "name": info.name, "versions": deps.jobs.versions(job_id), "latest": latest})
        return {"jobs": out, "active": {"id": active.job_id, "version": active.version} if active else None}

    @app.post("/jobs/{job_id}/versions/{version}/activate")
    def activate_job(job_id: str, version: int, body: ActivateBody | None = None, current: str = Depends(need("supervisor"))) -> dict[str, Any]:
        """Verify the job's decision logic on its reference set, record it as active and switch the station to it.
        The camera part of the verification runs on the station itself (a failure shows as a fault on the screen)."""
        ref = jobref(job_id, version)
        reason = (body.override_reason if body else None) or None
        if reason and not at_least(current, "maintainer"):
            raise HTTPException(403, "only a maintainer can override a failed verification")
        report = verify_stored_job(deps.jobs, ref, deps.inspect)
        try:
            activate(deps.jobs, ref, report, reason)
        except VerificationFailed as exc:
            raise HTTPException(409, {"verified": False, "problems": [c.message for c in report.failures()], "message": str(exc)}) from exc
        deps.controller.switch_job(deps.jobs.load(ref))
        return {"activated": True, "verified": report.ok, "warnings": list(report.warnings), "override": bool(reason) and not report.ok}

    @app.get("/jobs/{job_id}/versions/{version}/export")
    def export_job(job_id: str, version: int, _: str = Depends(need("supervisor"))) -> Response:
        ref = jobref(job_id, version)
        return Response(deps.jobs.export_vjob(ref), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{job_id}_v{version}.vjob"'})

    @app.post("/jobs/import")
    async def import_file(request: Request, _: str = Depends(need("supervisor"))) -> dict[str, Any]:
        """A `.vjob` or a `.vbak`, as the raw request body. Stores new versions; activating is a separate, verified step."""
        data = await request.body()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "file too large")

        def work() -> dict[str, Any]:
            kind = kind_of(data)
            if kind == "job":
                r = deps.jobs.import_vjob(data)
                return {"kind": "job", "imported": [_import_json(r)]}
            if kind == "backup":
                report = deps.jobs.restore_backup(data)
                return {"kind": "backup", "imported": [_import_json(r) for r in report.imported], "active_was": {"id": report.active.job_id, "version": report.active.version} if report.active else None, "has_system_config": report.system_yaml is not None}
            raise FormatError(f"unknown file kind '{kind}'")

        try:
            return await asyncio.get_running_loop().run_in_executor(None, work)
        except StoreError as exc:
            raise HTTPException(400, str(exc)) from exc

    def _import_json(r: Any) -> dict[str, Any]:
        return {"id": r.ref.job_id, "version": r.ref.version, "status": r.status, "original_version": r.original.version}

    @app.post("/backup")
    def make_backup(_: str = Depends(need("supervisor"))) -> dict[str, Any]:
        if deps.backup_dir is None:
            raise HTTPException(409, "no backup folder is configured")
        path = deps.jobs.make_backup(deps.backup_dir)
        return {"name": path.name, "size": path.stat().st_size}

    @app.get("/backup/{name}")
    def download_backup(name: str, _: str = Depends(need("supervisor"))) -> FileResponse:
        if deps.backup_dir is None or not _BACKUP_NAME.fullmatch(name) or not (deps.backup_dir / name).is_file():
            raise HTTPException(404, "no such backup")
        return FileResponse(deps.backup_dir / name, media_type="application/octet-stream", filename=name)

    # --- supervisor: results ---------------------------------------------------------

    def query_of(since: datetime | None, until: datetime | None, job_id: str | None, outcome: str | None, incorrect_only: bool) -> Query:
        if outcome and outcome not in ("PASS", "FAIL", "ERROR"):
            raise HTTPException(422, "outcome must be PASS, FAIL or ERROR")
        return Query(since=since, until=until, job_id=job_id, outcome=outcome, incorrect_only=incorrect_only)

    @app.get("/results")
    def results(
        since: datetime | None = None,
        until: datetime | None = None,
        job_id: str | None = None,
        outcome: str | None = None,
        incorrect_only: bool = False,
        limit: int = QueryParam(100, ge=1, le=1000),
        offset: int = QueryParam(0, ge=0),
        _: str = Depends(need("supervisor")),
    ) -> dict[str, Any]:
        q = query_of(since, until, job_id, outcome, incorrect_only)
        return {"total": deps.results.count(q), "results": [_record_json(r) for r in deps.results.find(q, limit, offset)]}

    @app.get("/results.csv")
    def results_csv(
        since: datetime | None = None,
        until: datetime | None = None,
        job_id: str | None = None,
        outcome: str | None = None,
        incorrect_only: bool = False,
        _: str = Depends(need("supervisor")),
    ) -> Response:
        buffer = io.StringIO()
        deps.results.export_csv(buffer, query_of(since, until, job_id, outcome, incorrect_only))
        return Response("﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="resultados.csv"'})

    @app.get("/results/{record_id}")
    def one_result(record_id: str, _: str = Depends(need("supervisor"))) -> dict[str, Any]:
        record = deps.results.get(record_id)
        if record is None:
            raise HTTPException(404, "no such result")
        return _record_json(record)

    @app.get("/results/{record_id}/image")
    def result_image(record_id: str, overlay: bool = False, _: str = Depends(need("supervisor"))) -> FileResponse:
        record = deps.results.get(record_id)
        rel = (record.overlay_path if overlay else record.image_path) if record else None
        if rel is None or not (deps.results.root / rel).is_file():
            raise HTTPException(404, "no image kept for this result")
        return FileResponse(deps.results.root / rel, media_type="image/jpeg")

    # --- maintainer ------------------------------------------------------------------

    @app.post("/collection/{job_id}")
    def collection(job_id: str, body: CollectionBody, _: str = Depends(need("maintainer"))) -> dict[str, Any]:
        deps.results.set_collection(job_id, body.enabled)
        return {"job_id": job_id, "enabled": body.enabled, "dataset_images": deps.results.dataset_count(job_id)}

    @app.post("/station/{command}")
    def station_command(command: str, _: str = Depends(need("maintainer"))) -> dict[str, str]:
        actions = {"pause": deps.controller.pause, "resume": deps.controller.resume, "retry": deps.controller.retry, "reset-background": deps.controller.reset_background}
        if command not in actions:
            raise HTTPException(404, "unknown command")
        actions[command]()
        return {"sent": command}

    # --- the screens: a single page served from here, no build step ----------------------

    index_path = WEB_DIR / "index.html"
    csp = content_security_policy(index_path.read_text(encoding="utf-8"))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"  # the screens update with the program, never from a stale copy
        return response

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(index_path, media_type="text/html")

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    return app
