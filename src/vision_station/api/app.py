"""The local API (architecture §10.1, docs/frontend.md §9): the screens talk to the core only through it.

Everything the program offers lives under `/api`: HTTP for commands and queries, one WebSocket (`/api/live`)
for the reduced live view and for state and result events. Every other path belongs to the web interface.
Operator endpoints need no login; the rest need a Supervisor or Maintainer token (`POST /api/login`, then
`Authorization: Bearer <token>`). It listens on 127.0.0.1 by default, accepts only local Host headers, and
refuses browser requests from other origins.
"""

import asyncio
import base64
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, Depends, FastAPI, Header, Query as QueryParam, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from vision_station import __version__
from vision_station.api import schemas as m
from vision_station.api.auth import AuthError, AuthService, LockedOut, at_least
from vision_station.api.hub import EventHub
from vision_station.records import InspectionRecord, Query, ResultRecorder, ResultsError, ResultStore
from vision_station.station import Acquisition, StationController, StationEvent
from vision_station.store import FormatError, JobRef, JobStore, StoreError
from vision_station.store.archive import FORMAT, kind_of
from vision_station.tools import tool_types
from vision_station.verification import VerificationFailed, activate, verify_stored_job
from vision_station.verification.verify import Inspector

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_UPLOAD = 256 * 1024 * 1024
_BACKUP_NAME = re.compile(r"backup_[0-9_-]+\.vbak")
_DEFAULT_CODES = {400: "bad_request", 401: "login_required", 403: "forbidden", 404: "not_found", 409: "conflict", 413: "too_large", 422: "validation_error", 429: "locked", 503: "unavailable"}


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
    web_dist: Path = WEB_DIR / "dist"  # the built interface (cd frontend && npm run build)
    shift_start: Callable[[], datetime] = _start_of_today  # counters for "the current shift": since this moment
    frame_fps: float = 10.0  # the live view is reduced to at most this (NFR-PERF-4)
    frame_width: int = 960
    jpeg_quality: int = 70
    heartbeat_s: float = 2.0
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "[::1]")
    hub: EventHub = field(default_factory=EventHub)


class Problem(StarletteHTTPException):
    """An error the interface can show: a Portuguese message plus a machine code and optional details."""

    def __init__(self, status_code: int, detail: str, code: str | None = None, headers: dict[str, str] | None = None, **extra: Any):
        super().__init__(status_code, detail, headers=headers)
        self.code = code or _DEFAULT_CODES.get(status_code, "error")
        self.extra = extra


def make_event_handler(deps: ApiDeps) -> Callable[[StationEvent], None]:
    """The `on_event` for the controller: record the result, then tell the screens."""

    def handle(event: StationEvent) -> None:
        if deps.recorder is not None:
            deps.recorder(event)
        deps.hub.publish(event_message(deps, event))

    return handle


def _result(result: Any, at: str | None = None) -> m.ResultOut | None:
    if result is None:
        return None
    return m.ResultOut(outcome=str(result.outcome), reason=result.reason, scores=dict(result.scores), duration_ms=round(result.duration_s * 1000), at=at)


def _recorded_at(deps: ApiDeps) -> str | None:
    """When the last result was recorded, if a recorder is writing them."""
    if deps.recorder is None or deps.recorder.last_record_id is None:
        return None
    record = deps.results.get(deps.recorder.last_record_id)
    return record.at if record else None


def event_message(deps: ApiDeps, event: StationEvent) -> dict[str, Any]:
    if event.kind == "result":
        message = m.ResultMessage(
            **_result(event.result, _recorded_at(deps) or datetime.now().astimezone().isoformat(timespec="milliseconds")).model_dump(),
            job=m.JobRefOut(id=event.job_id, name=event.job_name, version=event.job_version),
            record_id=deps.recorder.last_record_id if deps.recorder else None,
        )
    else:
        message = m.StateMessage(state=str(event.state), previous=str(event.previous) if event.previous else None, message=event.message)
    return message.model_dump(mode="json")


def status_model(deps: ApiDeps) -> m.StateOut:
    status = deps.controller.status()
    acq = deps.acquisition
    age = acq.age_s()
    return m.StateOut(
        state=str(status.state),
        message=status.message,
        detail=status.detail,
        warnings=list(status.warnings),
        job=m.JobRefOut(id=status.job_id, name=status.job_name, version=status.job_version),
        last_result=_result(status.last_result, _recorded_at(deps)),
        last_record_id=deps.recorder.last_record_id if deps.recorder else None,
        camera=m.CameraOut(connected=acq.connected, last_frame_age_s=None if age is None else round(age, 2), last_error=acq.last_error),
        counters=m.Counters(**deps.results.counts(deps.shift_start())),
        recent=[m.RecentResult(outcome=r.outcome, reason=r.reason, at=r.at) for r in reversed(deps.results.find(limit=10))],
        recording_failures=deps.recorder.failures if deps.recorder else 0,
        version=__version__,
    )


def status_json(deps: ApiDeps) -> dict[str, Any]:
    return status_model(deps).model_dump(mode="json")


def _record(r: InspectionRecord) -> m.RecordOut:
    return m.RecordOut(**{k: getattr(r, k) for k in m.RecordOut.model_fields})


def encode_jpeg(image: Any, width: int, quality: int) -> bytes:
    h, w = image.shape[:2]
    if w > width:
        image = cv2.resize(image, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("cannot encode the frame")
    return data.tobytes()


def content_security_policy() -> str:
    """Scripts and styles only from this server; the built page has no inline script."""
    return (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; connect-src 'self' ws://localhost:* ws://127.0.0.1:*; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )


NO_BUILD_PAGE = (
    '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Vision Station</title>'
    "<body style=\"font-family:system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem\">"
    "<h1>A interface não foi compilada</h1>"
    "<p>Rode <code>npm ci &amp;&amp; npm run build</code> na pasta <code>frontend/</code> e recarregue esta página. "
    "A API continua funcionando em <code>/api</code>.</p></body></html>"
)


def create_app(deps: ApiDeps) -> FastAPI:
    app = FastAPI(
        title="Vision Station",
        version=__version__,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        generate_unique_id_function=lambda route: route.name,  # operation ids the generated client can use as names
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(deps.allowed_hosts))
    api = APIRouter(
        prefix="/api",
        responses={401: {"model": m.Problem, "description": "needs a login"}, 403: {"model": m.Problem, "description": "needs another role"}},
    )

    # --- errors: always {detail, code, ...} ----------------------------------------------------

    @app.exception_handler(StarletteHTTPException)
    async def http_problem(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = getattr(exc, "code", None) or _DEFAULT_CODES.get(exc.status_code, "error")
        body = {"detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail), "code": code, **getattr(exc, "extra", {})}
        return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = {".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]): e["msg"] for e in exc.errors()}
        return JSONResponse({"detail": "Dados inválidos", "code": "validation_error", "fields": fields}, status_code=422)

    # --- same-machine rules ----------------------------------------------------------------------

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
            return JSONResponse({"detail": "Origem não permitida", "code": "origin_not_allowed"}, status_code=403)
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
                if current == "operator":
                    raise Problem(401, "É preciso entrar como " + ("Mantenedor" if minimum == "maintainer" else "Supervisor"), "login_required")
                raise Problem(403, "Este perfil não tem permissão para isso", "forbidden")
            return current

        return check

    def jobref(job_id: str, version: int) -> JobRef:
        ref = JobRef(job_id, version)
        if version not in deps.jobs.versions(job_id):
            raise Problem(404, "Essa versão do job não existe", "job_not_found")
        return ref

    # --- operator: no login ------------------------------------------------------------------------

    @api.get("/state", response_model=m.StateOut)
    def state() -> m.StateOut:
        return status_model(deps)

    @api.get("/result/last", response_model=m.LastResultOut, responses={404: {"model": m.Problem}})
    def last_result() -> m.LastResultOut:
        result = _result(deps.controller.last_result, _recorded_at(deps))
        if result is None:
            raise Problem(404, "Ainda não há resultado", "no_result")
        return m.LastResultOut(**result.model_dump(), record_id=deps.recorder.last_record_id if deps.recorder else None)

    @api.get("/snapshot.jpg", responses={200: {"content": {"image/jpeg": {}}}, 503: {"model": m.Problem}})
    def snapshot() -> Response:
        frame = deps.acquisition.latest()
        if frame is None:
            raise Problem(503, "Sem imagem da câmera", "no_frame")
        return Response(encode_jpeg(frame.image, deps.frame_width, deps.jpeg_quality), media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @api.post("/trigger", status_code=202, response_model=m.Accepted, responses={409: {"model": m.Problem}})
    def trigger() -> m.Accepted:
        """Manual (FR-TRG-3) and external (FR-TRG-2) trigger."""
        if deps.controller.state.value not in ("Ready", "WaitingStill"):
            raise Problem(409, "A estação não está pronta", "station_not_ready")
        deps.controller.request_trigger()
        return m.Accepted(accepted=True)

    @api.post("/results/{record_id}/incorrect", response_model=m.RecordOut, responses={404: {"model": m.Problem}, 400: {"model": m.Problem}})
    def mark_incorrect(record_id: str, body: m.IncorrectBody) -> m.RecordOut:
        """The operator or supervisor says a result was wrong; the image becomes labeled training data (FR-MDL-2)."""
        try:
            return _record(deps.results.mark_incorrect(record_id, body.correct, body.by))
        except ResultsError as exc:
            missing = "no such result" in str(exc)
            raise Problem(404 if missing else 400, "Esse resultado não existe" if missing else "A imagem desse resultado não foi guardada", "result_not_found" if missing else "no_image") from exc

    @api.websocket("/live")
    async def live(ws: WebSocket) -> None:
        """Text messages (JSON, see LiveMessage): the status at connect and every few seconds, then state and result
        events. Binary messages: JPEG frames, at most `frame_fps` per second."""
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

    # --- login -----------------------------------------------------------------------------------------

    @api.post("/login", response_model=m.LoginOut, responses={429: {"model": m.Problem}})
    def login(body: m.LoginBody) -> m.LoginOut:
        try:
            token, seconds = deps.auth.login(body.role, body.password)
        except LockedOut as exc:
            raise Problem(429, f"Muitas tentativas. Tente de novo em {int(exc.seconds) + 1} s", "locked", headers={"Retry-After": str(int(exc.seconds) + 1)}) from exc
        except AuthError as exc:
            raise Problem(401, "Perfil ou senha incorretos", "wrong_credentials") from exc
        return m.LoginOut(token=token, role=body.role, expires_in_s=seconds)

    @api.post("/logout", response_model=m.Ok)
    def logout(authorization: str | None = Header(default=None)) -> m.Ok:
        deps.auth.logout(token_of(authorization))
        return m.Ok(ok=True)

    @api.get("/whoami", response_model=m.WhoAmI)
    def whoami(current: str = Depends(role)) -> m.WhoAmI:
        return m.WhoAmI(role=current)

    # --- supervisor: jobs ----------------------------------------------------------------------------

    @api.get("/jobs", response_model=m.JobsOut)
    def list_jobs(_: str = Depends(need("supervisor"))) -> m.JobsOut:
        active = deps.jobs.get_active()
        out = []
        for job_id in deps.jobs.job_ids():
            latest = deps.jobs.latest(job_id)
            info = deps.jobs.load(JobRef(job_id, latest)).job.job  # type: ignore[arg-type]
            out.append(m.JobListItem(id=job_id, name=info.name, versions=deps.jobs.versions(job_id), latest=latest))  # type: ignore[arg-type]
        return m.JobsOut(jobs=out, active=m.ActiveRef(id=active.job_id, version=active.version) if active else None)

    @api.post("/jobs/{job_id}/versions/{version}/activate", response_model=m.ActivateOut, responses={409: {"model": m.Problem}, 404: {"model": m.Problem}})
    def activate_job(job_id: str, version: int, body: m.ActivateBody | None = None, current: str = Depends(need("supervisor"))) -> m.ActivateOut:
        """Verify the job's decision logic on its reference set, record it as active and switch the station to it.
        The camera part of the verification runs on the station itself (a failure shows as a fault on the screen)."""
        ref = jobref(job_id, version)
        reason = (body.override_reason if body else None) or None
        if reason and not at_least(current, "maintainer"):
            raise Problem(403, "Só o Mantenedor pode liberar um job que não passou na verificação", "forbidden")
        report = verify_stored_job(deps.jobs, ref, deps.inspect)
        try:
            activate(deps.jobs, ref, report, reason)
        except VerificationFailed as exc:
            raise Problem(409, "O job não passou na verificação", "verification_failed", problems=[c.message for c in report.failures()], verified=False) from exc
        deps.controller.switch_job(deps.jobs.load(ref))
        return m.ActivateOut(activated=True, verified=report.ok, warnings=list(report.warnings), override=bool(reason) and not report.ok)

    @api.get("/jobs/{job_id}/versions/{version}/export", responses={200: {"content": {"application/octet-stream": {}}}, 404: {"model": m.Problem}})
    def export_job(job_id: str, version: int, _: str = Depends(need("supervisor"))) -> Response:
        ref = jobref(job_id, version)
        return Response(deps.jobs.export_vjob(ref), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{job_id}_v{version}.vjob"'})

    @api.post("/jobs/import", response_model=m.ImportOut, responses={400: {"model": m.Problem}, 413: {"model": m.Problem}})
    async def import_file(request: Request, _: str = Depends(need("supervisor"))) -> m.ImportOut:
        """A `.vjob` or a `.vbak`, as the raw request body. Stores new versions; activating is a separate, verified step."""
        data = await request.body()
        if len(data) > MAX_UPLOAD:
            raise Problem(413, "Arquivo grande demais", "too_large")

        def item(r: Any) -> m.ImportItem:
            return m.ImportItem(id=r.ref.job_id, version=r.ref.version, status=r.status, original_version=r.original.version)

        def work() -> m.ImportOut:
            kind = kind_of(data)
            if kind == "job":
                return m.ImportOut(kind="job", imported=[item(deps.jobs.import_vjob(data))])
            if kind == "backup":
                report = deps.jobs.restore_backup(data)
                return m.ImportOut(
                    kind="backup",
                    imported=[item(r) for r in report.imported],
                    active_was=m.ActiveRef(id=report.active.job_id, version=report.active.version) if report.active else None,
                    has_system_config=report.system_yaml is not None,
                )
            raise FormatError(f"unknown file kind '{kind}'")

        try:
            return await asyncio.get_running_loop().run_in_executor(None, work)
        except StoreError as exc:
            raise Problem(400, f"Arquivo recusado: {exc}", "file_refused") from exc

    @api.post("/backup", response_model=m.BackupOut, responses={409: {"model": m.Problem}})
    def make_backup(_: str = Depends(need("supervisor"))) -> m.BackupOut:
        if deps.backup_dir is None:
            raise Problem(409, "Nenhuma pasta de backup foi configurada", "no_backup_folder")
        path = deps.jobs.make_backup(deps.backup_dir)
        return m.BackupOut(name=path.name, size=path.stat().st_size)

    @api.get("/backup/{name}", responses={200: {"content": {"application/octet-stream": {}}}, 404: {"model": m.Problem}})
    def download_backup(name: str, _: str = Depends(need("supervisor"))) -> FileResponse:
        if deps.backup_dir is None or not _BACKUP_NAME.fullmatch(name) or not (deps.backup_dir / name).is_file():
            raise Problem(404, "Esse backup não existe", "backup_not_found")
        return FileResponse(deps.backup_dir / name, media_type="application/octet-stream", filename=name)

    # --- supervisor: results ---------------------------------------------------------------------------

    def query_of(since: datetime | None, until: datetime | None, job_id: str | None, outcome: str | None, incorrect_only: bool) -> Query:
        if outcome and outcome not in ("PASS", "FAIL", "ERROR"):
            raise Problem(422, "O resultado deve ser PASS, FAIL ou ERROR", "validation_error", fields={"outcome": "PASS, FAIL ou ERROR"})
        return Query(since=since, until=until, job_id=job_id, outcome=outcome, incorrect_only=incorrect_only)

    @api.get("/results", response_model=m.ResultsOut)
    def results(
        since: datetime | None = None,
        until: datetime | None = None,
        job_id: str | None = None,
        outcome: str | None = None,
        incorrect_only: bool = False,
        limit: int = QueryParam(100, ge=1, le=1000),
        offset: int = QueryParam(0, ge=0),
        _: str = Depends(need("supervisor")),
    ) -> m.ResultsOut:
        q = query_of(since, until, job_id, outcome, incorrect_only)
        return m.ResultsOut(total=deps.results.count(q), results=[_record(r) for r in deps.results.find(q, limit, offset)])

    @api.get("/results.csv", responses={200: {"content": {"text/csv": {}}}})
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

    @api.get("/results/{record_id}", response_model=m.RecordOut, responses={404: {"model": m.Problem}})
    def one_result(record_id: str, _: str = Depends(need("supervisor"))) -> m.RecordOut:
        record = deps.results.get(record_id)
        if record is None:
            raise Problem(404, "Esse resultado não existe", "result_not_found")
        return _record(record)

    @api.get("/results/{record_id}/image", responses={200: {"content": {"image/jpeg": {}}}, 404: {"model": m.Problem}})
    def result_image(record_id: str, overlay: bool = False, _: str = Depends(need("supervisor"))) -> FileResponse:
        record = deps.results.get(record_id)
        rel = (record.overlay_path if overlay else record.image_path) if record else None
        if rel is None or not (deps.results.root / rel).is_file():
            raise Problem(404, "Nenhuma imagem foi guardada para esse resultado", "no_image")
        return FileResponse(deps.results.root / rel, media_type="image/jpeg")

    @api.get("/about", response_model=m.AboutOut)
    def about(_: str = Depends(need("supervisor"))) -> m.AboutOut:
        return m.AboutOut(version=__version__, job_format=FORMAT, tools=[m.ToolInfo(name=n, version=v) for n, v in tool_types()])

    # --- maintainer ----------------------------------------------------------------------------------------

    @api.post("/collection/{job_id}", response_model=m.CollectionOut)
    def collection(job_id: str, body: m.CollectionBody, _: str = Depends(need("maintainer"))) -> m.CollectionOut:
        deps.results.set_collection(job_id, body.enabled)
        return m.CollectionOut(job_id=job_id, enabled=body.enabled, dataset_images=deps.results.dataset_count(job_id))

    @api.post("/station/{command}", response_model=m.Sent, responses={404: {"model": m.Problem}})
    def station_command(command: str, _: str = Depends(need("maintainer"))) -> m.Sent:
        actions = {"pause": deps.controller.pause, "resume": deps.controller.resume, "retry": deps.controller.retry, "reset-background": deps.controller.reset_background}
        if command not in actions:
            raise Problem(404, "Comando desconhecido", "unknown_command")
        actions[command]()
        return m.Sent(sent=command)

    @api.get("/{rest:path}", include_in_schema=False)
    def unknown_api(rest: str) -> Response:
        raise Problem(404, "Esse caminho da API não existe", "not_found")

    app.include_router(api)

    # --- OpenAPI: add the live socket's messages, which are not REST paths ---------------------------------

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        live = TypeAdapter(m.LiveMessage).json_schema(ref_template="#/components/schemas/{model}")
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components.update(live.pop("$defs", {}))
        components["LiveMessage"] = live
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    # --- the screens -------------------------------------------------------------------------------------------

    dist = deps.web_dist
    built = (dist / "index.html").is_file()
    csp = content_security_policy()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        response.headers.setdefault("Content-Security-Policy", csp)
        if path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # hashed file names
        elif not path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache"  # the page updates with the program, never from a stale copy
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    if built:
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Response:
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)  # favicon and the like
            return FileResponse(dist / "index.html", media_type="text/html")  # any client route: reload and deep links work

    else:  # the API keeps working; the page says how to build the interface

        @app.get("/{path:path}", include_in_schema=False)
        def no_build(path: str) -> HTMLResponse:
            return HTMLResponse(NO_BUILD_PAGE, status_code=503)

    return app
