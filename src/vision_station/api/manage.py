"""Management endpoints (docs/frontend.md §9.3, VIA-0026): what the Jobs, editor, camera, access, audit and
dataset screens need. Mounted by `create_app`; every route needs a Supervisor or Maintainer login.

Jobs are edited as drafts (`JobDraft`): the server sets identity, version, author and date, checks the
draft exactly as an import is checked, and saves a new immutable version (FR-JOB-5).
"""

import base64
import binascii
import csv
import difflib
import io
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

import cv2
import numpy as np
import yaml
from fastapi import APIRouter, Depends, Query as QueryParam, Response
from pydantic import ValidationError

from vision_station.api import schemas as m
from vision_station.api.auth import AuthError, LockedOut
from vision_station.cameras import Frame
from vision_station.algorithms.color_range import propose_range
from vision_station.core.i18n import render, render_schema, text_of, tr
from vision_station.jobs import CameraProfile, Job
from vision_station.jobs import tuning
from vision_station.jobs.job import BUILTIN_ROIS
from vision_station.locators import get_locator, locator_types
from vision_station.records import ResultsError
from vision_station.station.exposure import ExposureError, measure_exposure
from vision_station.tools.limits import MARGIN, propose_for_criterion
from vision_station.store import FormatError, JobBundle, JobRef, StoreError
from vision_station.store.archive import check_path, sha256
from vision_station.store.bundle import JOB_FILE, bundle_from_files
from vision_station.tools import get_tool, tool_types
from vision_station.verification import make_reference_files, run_cases, run_reference_set, verify_stored_job
from vision_station.verification.reference import EXPECTED_FILE, REFERENCE_IMAGE, REFERENCE_META, decode_image, parse_expected

MAX_IMAGE = 32 * 1024 * 1024


def _now() -> datetime:
    return datetime.now().astimezone()


def _type_info(name: str, version: int, entry: Any) -> m.TypeInfo:
    schema = entry.params.model_json_schema()
    # what the editor shows about the type: the `about` of its parameters (schema_labels, translated), not the docstring
    criteria = [
        m.CriterionSpecOut(
            value=c.value, label=render(c.label), unit=c.unit, range=list(c.range), direction=c.direction, level=c.level,
            limits={k: p for k, p in (("min", c.min_param), ("max", c.max_param)) if p},
        )
        for c in getattr(entry, "criteria", ())
    ]
    return m.TypeInfo(name=name, version=version, description=render(schema.get("description", "")), params_schema=render_schema(schema), criteria=criteria)


def _fields(exc: ValidationError, prefix: str) -> dict[str, str]:
    return {".".join([prefix, *(str(p) for p in e["loc"])]): e["msg"] for e in exc.errors()}


def _decode_image(data: str) -> np.ndarray:
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(tr("a imagem não está em base64")) from None
    if len(raw) > MAX_IMAGE:
        raise ValueError(tr("imagem grande demais"))
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(tr("o arquivo não é uma imagem"))
    return image


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def add_management_routes(api: APIRouter, deps: Any, need: Callable[[str], Callable], Problem: type, result_out: Callable) -> Callable[..., JobBundle]:
    """`need(role)` is the login dependency of the app, `Problem` its error, `result_out(result, at)` its
    result model builder; they are passed in so this module shares the app's rules. It returns `build`, which the
    editor's live session uses to turn each draft it receives into a job."""
    jobs = deps.jobs

    def ref_of(job_id: str, version: int) -> JobRef:
        if version not in jobs.versions(job_id):
            raise Problem(404, "Essa versão do job não existe", "job_not_found")
        return JobRef(job_id, version)

    def frame_or(image: str | None) -> np.ndarray:
        if image:
            try:
                return _decode_image(image)
            except ValueError as exc:
                raise Problem(400, tr("Imagem inválida: {why}", why=exc.args[0]), "bad_image") from exc
        frame = deps.acquisition.latest()
        if frame is None:
            raise Problem(409, "Sem imagem da câmera", "no_frame")
        return frame.image

    # --- drafts --------------------------------------------------------------------------------------

    def build(draft: m.JobDraft, *, job_id: str, version: int, parent: int | None, author: str, extra: dict[str, bytes] | None = None, tuned: bool = False) -> JobBundle:
        """The draft as a bundle with this identity, checked like an import. Raises Problem 422 with fields."""
        data = dict(draft.job)
        info = dict(data.get("job") or {})
        info.update(id=job_id, version=version, parent_version=parent, author=author, created_at=_now().isoformat(timespec="seconds"), notes=draft.notes, tuned=tuned)
        data["job"] = info
        data.setdefault("format", 1)
        data.setdefault("camera_profile", "camera/profile.yaml")
        fields: dict[str, str] = {}
        job = profile = None
        try:
            job = Job.model_validate(data)
        except ValidationError as exc:
            fields.update(_fields(exc, "job"))
        try:
            profile = CameraProfile.model_validate(draft.profile)
        except ValidationError as exc:
            fields.update(_fields(exc, "profile"))
        if fields:
            raise Problem(422, "O job tem campos inválidos", "invalid_draft", fields=fields)
        if extra is None:  # the files of the draft: the base version's, with what was added and removed
            extra = {}
            if draft.base is not None:
                extra = dict(jobs.load(ref_of(draft.base.id, draft.base.version)).extra)
            for path in draft.remove_files:
                extra.pop(path, None)
            for path, content in draft.add_files.items():
                try:
                    check_path(path)
                    extra[path] = base64.b64decode(content, validate=True)
                except (FormatError, binascii.Error, ValueError) as exc:
                    raise Problem(422, "Arquivo inválido no job", "invalid_draft", fields={f"add_files.{path}": str(exc)}) from exc
        bundle = JobBundle(job, profile, extra)  # type: ignore[arg-type]
        try:
            bundle_from_files(bundle.files())
            if EXPECTED_FILE in extra:  # the reference set must name only images the job carries
                missing = [c.image for c in parse_expected(extra[EXPECTED_FILE]).cases if c.image not in extra]
                if missing:
                    raise FormatError(f"the reference set names images that are not in the job: {missing}")
        except (FormatError, StoreError) as exc:
            raise Problem(422, tr("O job não pode rodar: {why}", why=exc), "invalid_draft") from exc
        return bundle

    def placeholder(draft: m.JobDraft, role: str) -> JobBundle:
        return build(draft, job_id=str(uuid.uuid4()), version=1, parent=None, author=role)

    def save(bundle: JobBundle) -> m.SavedVersion:
        try:
            ref = jobs.save(bundle)
        except StoreError as exc:
            raise Problem(409, tr("Não foi possível salvar: {why}", why=exc), "save_conflict") from exc
        return m.SavedVersion(id=ref.job_id, version=ref.version)

    # --- types ---------------------------------------------------------------------------------------

    @api.get("/tools", response_model=m.TypesOut)
    def list_types(_: str = Depends(need("supervisor"))) -> m.TypesOut:
        """Tool and locator types with the JSON Schema of their parameters, for the editor's forms."""
        return m.TypesOut(
            tools=[_type_info(n, v, get_tool(n, v)) for n, v in tool_types()],
            locators=[_type_info(n, v, get_locator(n, v)) for n, v in locator_types()],
            builtin_rois=sorted(BUILTIN_ROIS),
        )

    # --- jobs ----------------------------------------------------------------------------------------

    @api.get("/jobs/{job_id}", response_model=m.JobDetailOut, responses={404: {"model": m.Problem}})
    def job_detail(job_id: str, _: str = Depends(need("supervisor"))) -> m.JobDetailOut:
        versions = jobs.versions(job_id)
        if not versions:
            raise Problem(404, "Esse job não existe", "job_not_found")
        active = jobs.get_active()
        infos = []
        for v in reversed(versions):
            info = jobs.load(JobRef(job_id, v)).job.job
            infos.append(m.VersionInfo(version=v, created_at=info.created_at.isoformat(), author=info.author, notes=info.notes, parent_version=info.parent_version, tuned=info.tuned,
                                       active=bool(active and active.job_id == job_id and active.version == v)))
        latest = jobs.load(JobRef(job_id, versions[-1])).job.job
        return m.JobDetailOut(id=job_id, name=latest.name, description=latest.description, versions=infos)

    @api.get("/jobs/{job_id}/versions/{version}", response_model=m.JobVersionOut, responses={404: {"model": m.Problem}})
    def job_version(job_id: str, version: int, _: str = Depends(need("supervisor"))) -> m.JobVersionOut:
        bundle = jobs.load(ref_of(job_id, version))
        extra = bundle.extra
        return m.JobVersionOut(
            id=job_id,
            version=version,
            job=bundle.job.model_dump(mode="json"),
            profile=bundle.profile.model_dump(mode="json"),
            files=[m.JobFileOut(path=p, size=len(d), sha256=sha256(d)) for p, d in sorted(extra.items())],
            reference=yaml.safe_load(extra[REFERENCE_META]) if REFERENCE_META in extra else None,
            expected=yaml.safe_load(extra[EXPECTED_FILE]) if EXPECTED_FILE in extra else None,
        )

    @api.get("/jobs/{job_id}/versions/{version}/files/{path:path}", responses={200: {"content": {"application/octet-stream": {}}}, 404: {"model": m.Problem}})
    def job_file(job_id: str, version: int, path: str, width: int | None = QueryParam(None, ge=32, le=1920), _: str = Depends(need("supervisor"))) -> Response:
        """One file of a saved version (a reference image, a template), for the editor to show. `width` reduces an image
        (the thumbnails of the filmstrip do not carry full frames)."""
        data = jobs.load(ref_of(job_id, version)).extra.get(path)
        if data is None:
            raise Problem(404, "Esse arquivo não existe nesse job", "file_not_found")
        kind = "image/png" if path.lower().endswith(".png") else "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "application/octet-stream"
        if width is not None and kind != "application/octet-stream":
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if image is not None and image.shape[1] > width:
                image = cv2.resize(image, (width, max(1, round(image.shape[0] * width / image.shape[1]))), interpolation=cv2.INTER_AREA)
                ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    return Response(jpeg.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
        return Response(data, media_type=kind, headers={"Cache-Control": "no-store"})

    @api.post("/jobs/validate", response_model=m.DraftCheckOut)
    def validate_draft(draft: m.JobDraft, role: str = Depends(need("maintainer"))) -> m.DraftCheckOut:
        """Check a draft without saving it: field errors, or why it could not run."""
        try:
            placeholder(draft, role)
        except Problem as exc:  # type: ignore[misc]
            return m.DraftCheckOut(ok=False, message=render(exc.detail), fields=exc.extra.get("fields", {}))
        return m.DraftCheckOut(ok=True)

    @api.post("/jobs/verify", response_model=m.VerifyOut)
    def verify_draft(draft: m.JobDraft, role: str = Depends(need("maintainer"))) -> m.VerifyOut:
        """Run a draft on every sample of its reference set (Validar). It is the run activation does, so a draft that
        passes here is not refused there for its samples; nothing is saved or recorded."""
        try:
            bundle = placeholder(draft, role)
        except Problem as exc:  # type: ignore[misc]
            return m.VerifyOut(ok=False, message=render(exc.detail), fields=exc.extra.get("fields", {}))
        runs = run_reference_set(bundle, deps.inspect)
        if not runs:
            return m.VerifyOut(ok=False, message=tr("Não há amostras para validar: capture amostras Boas e Ruins"))
        cases = [
            m.CaseRunOut(image=r.image, expected=r.expected, outcome=r.outcome, ok=r.ok, message=render(r.message), reason=render(r.reason), duration_ms=r.duration_ms)  # type: ignore[arg-type]
            for r in runs
        ]
        times = [r.duration_ms for r in runs if r.duration_ms is not None]
        return m.VerifyOut(ok=all(r.ok for r in runs), cases=cases, max_ms=max(times) if times else None)

    def run_samples(draft: m.JobDraft, role: str) -> tuple[JobBundle, list[tuple[str, str, str | None, bool, Any, Any]]]:
        """The draft on its reference picture and on every sample, with the loop activation and Validar use. A row is
        (image, kind, expected, ok, result or None, message)."""
        bundle = placeholder(draft, role)
        rows: list[tuple[str, str, str | None, bool, Any, Any]] = []
        reference = bundle.extra.get(REFERENCE_IMAGE)
        picture = decode_image(reference) if reference else None
        if picture is not None:
            try:
                result = deps.inspect(bundle, Frame(image=picture, timestamp=0.0))
                rows.append((REFERENCE_IMAGE, "reference", None, str(result.outcome) == "PASS", result, ""))
            except Exception as exc:  # the reference that cannot be run is a row that says so, not a failed request
                rows.append((REFERENCE_IMAGE, "reference", None, False, None, tr("{image}: erro ao inspecionar ({kind}: {exc})", image=REFERENCE_IMAGE, kind=type(exc).__name__, exc=exc)))
        for done in run_cases(bundle, deps.inspect):
            kind = {"PASS": "good", "FAIL": "bad", "ERROR": "error"}[done.case.outcome]
            rows.append((done.case.image, kind, done.case.outcome, done.ok, done.result, done.message))
        return bundle, rows

    @api.post("/editor/batch", response_model=m.BatchOut)
    def editor_batch(draft: m.JobDraft, role: str = Depends(need("supervisor"))) -> m.BatchOut:
        """The draft on all its samples at once (frontend.md §9.4). It feeds the dots of the tolerance gauges and the
        separation line: nothing is saved or recorded, and the results are simulated."""
        try:
            bundle, rows = run_samples(draft, role)
        except Problem as exc:  # type: ignore[misc]
            return m.BatchOut(ok=False, message=render(exc.detail), fields=exc.extra.get("fields", {}))
        samples = [
            m.BatchSampleOut(
                image=image, kind=kind, expected=expected, ok=ok, message=render(message) if message else "",  # type: ignore[arg-type]
                result=None if result is None else result_out(replace(result, simulated=True), None),
            )
            for image, kind, expected, ok, result, message in rows
        ]
        deciding = [t.id for t in bundle.job.tools if t.affects_result]
        separation = []
        for tool_id in deciding:
            on = lambda kind: [s for s in samples if s.kind == kind and s.result is not None and any(t.id == tool_id for t in s.result.tools)]  # noqa: E731
            passed = lambda s: next(t.passed for t in s.result.tools if t.id == tool_id)  # type: ignore[union-attr]  # noqa: E731
            good, bad = on("good"), on("bad")
            separation.append(m.ToolSeparationOut(
                tool=tool_id, good_total=len(good), good_passed=sum(passed(s) for s in good), bad_total=len(bad), bad_failed=sum(not passed(s) for s in bad),
            ))
        counted = [s for s in samples if s.kind in ("good", "bad")]
        times = [s.result.duration_ms for s in samples if s.result is not None]
        return m.BatchOut(
            ok=True, samples=samples, tools=separation,
            good_total=sum(s.kind == "good" for s in counted), good_ok=sum(s.kind == "good" and s.ok for s in counted),
            bad_total=sum(s.kind == "bad" for s in counted), bad_ok=sum(s.kind == "bad" and s.ok for s in counted),
            max_ms=max(times) if times else None,
        )

    @api.post("/editor/suggest/limits", response_model=m.LimitsOut)
    def suggest_limits(body: m.SuggestLimitsBody, role: str = Depends(need("supervisor"))) -> m.LimitsOut:
        """The limits the *Boa* and *Ruim* samples suggest for each criterion of each tool (FR-UI-14). Nothing is
        changed: the editor shows each proposal and applies it only when the person says so."""
        try:
            bundle, rows = run_samples(body.draft, role)
        except Problem as exc:  # type: ignore[misc]
            return m.LimitsOut(ok=False, message=render(exc.detail), fields=exc.extra.get("fields", {}))
        proposals = []
        for tool in bundle.job.tools:
            if not tool.affects_result or (body.tool is not None and tool.id != body.tool):
                continue
            entry = get_tool(tool.type, tool.version)
            for spec in entry.criteria:
                for found in propose_for_criterion(tool, entry, spec, rows, getattr(deps, "limit_margin", MARGIN)):
                    proposals.append(m.LimitProposalOut(**{**found, "label": render(found["label"])}))
        return m.LimitsOut(ok=True, proposals=proposals)

    @api.post("/editor/suggest/colour", response_model=m.ColourProposalOut)
    def suggest_colour(body: m.SuggestColourBody, _: str = Depends(need("maintainer"))) -> m.ColourProposalOut:
        """A color range from the pixels the person sampled on the image; the editor shows it as a proposal (FR-UI-13)."""
        try:
            include = [_decode_image(x) for x in body.include]
            exclude = [_decode_image(x) for x in body.exclude]
        except ValueError as exc:
            return m.ColourProposalOut(ok=False, message=str(exc))
        found = propose_range(include, exclude)
        if found is None:
            return m.ColourProposalOut(ok=False, message=render("Poucos pixels para propor uma cor: arraste sobre uma área maior"))
        return m.ColourProposalOut(ok=True, **{k: getattr(found, k) for k in ("hue", "s_min", "s_max", "v_min", "v_max", "pixels", "kept", "leak")})

    @api.post("/jobs", status_code=201, response_model=m.SavedVersion, responses={409: {"model": m.Problem}, 422: {"model": m.Problem}})
    def create_job(draft: m.JobDraft, role: str = Depends(need("maintainer"))) -> m.SavedVersion:
        saved = save(build(draft, job_id=str(uuid.uuid4()), version=1, parent=None, author=role))
        jobs.audit("job_create", by=role, job_id=saved.id, version=1)
        return saved

    @api.post("/jobs/{job_id}/versions", status_code=201, response_model=m.SavedVersion, responses={409: {"model": m.Problem}, 422: {"model": m.Problem}})
    def save_version(job_id: str, draft: m.JobDraft, role: str = Depends(need("maintainer"))) -> m.SavedVersion:
        """Save the draft as version n+1. The draft may start from any version (`draft.base`, where its files come
        from), but the newest version it saw (`draft.latest`, else `draft.base`) must still be the latest: if
        someone saved meanwhile, 409 instead of silently building on a version the editor did not see (VIA-0047)."""
        latest = jobs.latest(job_id)
        if latest is None:
            raise Problem(404, "Esse job não existe", "job_not_found")
        seen = draft.latest if draft.latest is not None else draft.base.version if draft.base else None
        if draft.base is None or draft.base.id != job_id or seen != latest:
            raise Problem(409, tr("O job mudou: a última versão é a {latest}. Abra de novo antes de salvar.", latest=latest), "stale_draft", latest=latest)
        saved = save(build(draft, job_id=job_id, version=latest + 1, parent=latest, author=role))
        jobs.audit("job_save", by=role, job_id=job_id, version=saved.version, parent=latest, notes=draft.notes)
        return saved

    @api.post("/jobs/{job_id}/tune", status_code=201, response_model=m.TuneOut, responses={404: {"model": m.Problem}, 409: {"model": m.Problem}, 422: {"model": m.Problem}})
    def tune_job(job_id: str, draft: m.JobDraft, role: str = Depends(need("supervisor"))) -> m.TuneOut:
        """Save a fine-tune as version n+1 and verify it (FR-JOB-14, document 05 §7.12). The draft is whatever the screen
        built, and the server decides what may differ from the version it starts from: tolerance limits and new samples,
        nothing else. A note is required. The version is not activated: that is the person's next step."""
        latest = jobs.latest(job_id)
        if latest is None:
            raise Problem(404, "Esse job não existe", "job_not_found")
        seen = draft.latest if draft.latest is not None else draft.base.version if draft.base else None
        if draft.base is None or draft.base.id != job_id or seen != latest or draft.base.version != latest:
            raise Problem(409, tr("O job mudou: a última versão é a {latest}. Abra de novo antes de salvar.", latest=latest), "stale_draft", latest=latest)
        if not draft.notes.strip():
            raise Problem(422, "Diga o que foi ajustado e por quê", "note_required", fields={"notes": tr("Obrigatório no ajuste fino")})
        base = jobs.load(JobRef(job_id, latest))
        bundle = build(draft, job_id=job_id, version=latest + 1, parent=latest, author=role, tuned=True)
        try:
            changes = tuning.tolerance_changes(base.job, bundle.job, base.profile, bundle.profile)
            tuning.check_files({p: d for p, d in base.extra.items()}, bundle.extra)
            tuning.check_expected(base.extra.get(EXPECTED_FILE), bundle.extra.get(EXPECTED_FILE))
        except tuning.NotTunable as exc:
            raise Problem(422, "No ajuste fino só mudam os limites de tolerância e as amostras", "not_tunable", fields=exc.fields) from exc
        saved = save(bundle)
        report = verify_stored_job(jobs, ref_of(saved.id, saved.version), deps.inspect)
        lines = [f"{c.tool}: {c.param}, {c.old} → {c.new}" for c in changes]
        jobs.audit("job_tune", by=role, job_id=job_id, version=saved.version, parent=latest, notes=draft.notes, changes=[{"tool": c.tool, "param": c.param, "old": c.old, "new": c.new} for c in changes], verified=report.ok)
        return m.TuneOut(id=saved.id, version=saved.version, verified=report.ok, problems=[render(c.message) for c in report.failures()], changes=lines)

    @api.post("/jobs/{job_id}/duplicate", status_code=201, response_model=m.SavedVersion, responses={404: {"model": m.Problem}})
    def duplicate_job(job_id: str, body: m.DuplicateBody, role: str = Depends(need("maintainer"))) -> m.SavedVersion:
        """A new job (new id, version 1) from a saved version, with all its files."""
        source = jobs.load(ref_of(job_id, body.version))
        draft = m.JobDraft(job={**source.job.model_dump(mode="json"), "job": {**source.job.job.model_dump(mode="json"), "name": body.name}},
                           profile=source.profile.model_dump(mode="json"), base=m.ActiveRef(id=job_id, version=body.version),
                           notes=f"cópia de {source.job.job.name} v{body.version}")
        saved = save(build(draft, job_id=str(uuid.uuid4()), version=1, parent=None, author=role))
        jobs.audit("job_duplicate", by=role, job_id=saved.id, source_id=job_id, source_version=body.version)
        return saved

    @api.post("/jobs/test", response_model=m.DraftTestOut, responses={409: {"model": m.Problem}, 422: {"model": m.Problem}})
    def test_draft(body: m.DraftTestBody, role: str = Depends(need("maintainer"))) -> m.DraftTestOut:
        """Run a draft on the camera's newest frame (or a given image) without saving or activating it."""
        bundle = placeholder(body.draft, role)
        image = frame_or(body.image)
        # a draft on a picture is never a production result (FR-INT-12); it is not recorded and takes no sequence number
        result = replace(deps.inspect(bundle, Frame(image=image, timestamp=time.monotonic())), simulated=True)
        drawn = deps.overlay(image, result) if deps.overlay else image
        ok, jpeg = cv2.imencode(".jpg", drawn, [cv2.IMWRITE_JPEG_QUALITY, 85])
        details = dict(result.details)
        anchor = details.get("anchor")
        return m.DraftTestOut(
            result=result_out(result, None),
            regions=[m.RegionOut(**r) for r in details.get("regions", [])],
            anchor=anchor["rect"] if anchor else None,
            tools=details.get("tools", {}),
            timings=details.get("timings", {}),
            width=image.shape[1],
            height=image.shape[0],
            overlay=_b64(jpeg.tobytes()) if ok else "",
        )

    @api.get("/jobs/{job_id}/versions/{version}/diff", response_model=m.DiffOut, responses={404: {"model": m.Problem}})
    def diff_versions(job_id: str, version: int, against: int = QueryParam(..., ge=1), _: str = Depends(need("supervisor"))) -> m.DiffOut:
        def text(v: int) -> list[str]:
            files = jobs.load(ref_of(job_id, v)).files()
            bundle = jobs.load(JobRef(job_id, v))
            return (files[JOB_FILE].decode("utf-8") + "\n# camera profile\n" + files[bundle.job.camera_profile].decode("utf-8")).splitlines(keepends=True)

        diff = difflib.unified_diff(text(against), text(version), fromfile=f"v{against}", tofile=f"v{version}")
        return m.DiffOut(id=job_id, version=version, against=against, diff="".join(diff))

    # --- camera tuning ---------------------------------------------------------------------------------

    def camera_state() -> m.CameraStateOut:
        acq = deps.acquisition
        report = acq.last_apply
        settings = {k: m.SettingResult(status=str(getattr(s, "value", s)), detail=(report.detail.get(k, "") if report else "")) for k, s in (report.status.items() if report else [])}
        profile = acq.profile
        return m.CameraStateOut(
            connected=acq.connected,
            last_error=acq.last_error,
            profile=profile.model_dump(mode="json") if profile else None,
            applied=acq.applied,
            settings=settings,
            station_paused=deps.controller.state.value == "Paused",
        )

    @api.get("/camera/state", response_model=m.CameraStateOut)
    def get_camera(_: str = Depends(need("maintainer"))) -> m.CameraStateOut:
        return camera_state()

    @api.post("/camera/apply", response_model=m.CameraStateOut, responses={422: {"model": m.Problem}})
    def apply_camera(profile: dict[str, Any], role: str = Depends(need("maintainer")), wait_s: float = QueryParam(5.0, ge=0, le=15)) -> m.CameraStateOut:
        """Write these settings to the camera while watching the live view. The station is paused first; resuming
        it (`POST /api/station/resume`) writes the active job's settings back."""
        try:
            parsed = CameraProfile.model_validate(profile)
        except ValidationError as exc:
            raise Problem(422, "Ajustes de câmera inválidos", "invalid_profile", fields=_fields(exc, "profile")) from exc
        deps.controller.pause()
        deps.acquisition.configure(parsed)
        deadline = time.monotonic() + wait_s
        while not deps.acquisition.applied and time.monotonic() < deadline and deps.acquisition.connected:
            time.sleep(0.05)
        jobs.audit("camera_apply", by=role)
        return camera_state()

    @api.post("/camera/auto-exposure", response_model=m.AutoExposureOut, responses={409: {"model": m.Problem}, 422: {"model": m.Problem}})
    def auto_exposure(profile: dict[str, Any], role: str = Depends(need("maintainer"))) -> m.AutoExposureOut:
        """*Auto uma vez*: find the exposure once, with the settings of this draft profile, and leave the camera on it.
        The station is paused first, as in `/camera/apply`; the measuring parameters are the profile's
        `exposure.auto_once`. It takes several seconds: the camera is written and settles at every step."""
        try:
            parsed = CameraProfile.model_validate(profile)
        except ValidationError as exc:
            raise Problem(422, "Ajustes de câmera inválidos", "invalid_profile", fields=_fields(exc, "profile")) from exc
        if not deps.acquisition.connected:
            raise Problem(409, "A câmera não está conectada", "camera_not_connected")
        deps.controller.pause()
        try:
            found = measure_exposure(deps.acquisition, parsed)
        except ExposureError as exc:
            raise Problem(409, tr("Não foi possível medir a exposição: {why}", why=text_of(exc)), "auto_exposure_failed") from exc
        jobs.audit("camera_auto_exposure", by=role, value_us=found.value_us)
        return m.AutoExposureOut(
            value_us=found.value_us, saturated_percent=found.saturated_percent, target_percent=found.target_percent,
            reached=found.reached, limit=found.limit,  # type: ignore[arg-type]
            steps=[m.ExposureStepOut(exposure_us=s.exposure_us, saturated_percent=s.saturated_percent) for s in found.steps],
        )

    # --- reference image and reference set ---------------------------------------------------------------

    @api.post("/reference/capture", response_model=m.ReferenceOut, responses={409: {"model": m.Problem}})
    def capture_reference(body: m.ReferenceBody, _: str = Depends(need("maintainer"))) -> m.ReferenceOut:
        """The reference image and its measures from the live view (or an upload), to add to a draft."""
        image = frame_or(body.image)
        files = make_reference_files(image)
        meta = yaml.safe_load(files[REFERENCE_META])
        return m.ReferenceOut(files={p: _b64(d) for p, d in files.items()}, brightness=meta["brightness"], sharpness=meta["sharpness"], width=image.shape[1], height=image.shape[0])

    @api.post("/reference/cases", response_model=m.ReferenceCaseOut, responses={409: {"model": m.Problem}, 422: {"model": m.Problem}})
    def capture_case(body: m.ReferenceCaseBody, role: str = Depends(need("supervisor"))) -> m.ReferenceCaseOut:
        """A reference-set image, with what the draft says about it now (the editor records the expected result)."""
        image = frame_or(body.image)
        result = replace(deps.inspect(placeholder(body.draft, role), Frame(image=image, timestamp=time.monotonic())), simulated=True)
        ok, png = cv2.imencode(".png", image)
        return m.ReferenceCaseOut(path=f"tests/images/{body.name}.png", image=_b64(png.tobytes()) if ok else "", result=result_out(result, None))

    # --- backups -------------------------------------------------------------------------------------------

    @api.get("/backup", response_model=m.BackupsOut)
    def list_backups(_: str = Depends(need("supervisor"))) -> m.BackupsOut:
        folder = deps.backup_dir
        items: list[m.BackupItem] = []
        if folder is not None and folder.is_dir():
            for f in sorted(folder.glob("backup_*.vbak"), key=lambda p: p.stat().st_mtime, reverse=True):
                st = f.stat()
                items.append(m.BackupItem(name=f.name, size=st.st_size, created_at=datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")))
        return m.BackupsOut(folder=str(folder) if folder else None, backups=items)

    # --- access ----------------------------------------------------------------------------------------------

    @api.get("/users", response_model=m.UsersOut)
    def list_users(_: str = Depends(need("supervisor"))) -> m.UsersOut:
        return m.UsersOut(users=[m.UserOut(**u) for u in deps.auth.users()])

    @api.put("/users/{role}/password", response_model=m.UserOut, responses={400: {"model": m.Problem}, 403: {"model": m.Problem}, 404: {"model": m.Problem}})
    def set_password(role: str, body: m.PasswordBody, current: str = Depends(need("supervisor"))) -> m.UserOut:
        """The maintainer sets either password; a supervisor only their own, confirming the old one."""
        if role not in ("supervisor", "maintainer"):
            raise Problem(404, "Esse perfil não tem senha", "unknown_role")
        if current == "supervisor":
            if role != "supervisor":
                raise Problem(403, "O Supervisor só troca a própria senha", "forbidden")
            try:
                if not body.current_password or not deps.auth.check_password("supervisor", body.current_password):
                    raise Problem(400, "A senha atual não confere", "wrong_password")
            except LockedOut as exc:
                raise Problem(429, "Muitas tentativas; aguarde e tente de novo", "locked", headers={"Retry-After": str(int(exc.seconds) + 1)}) from exc
        try:
            deps.auth.set_password(role, body.password)
        except AuthError as exc:
            raise Problem(400, tr("Senha não aceita: {why}", why=exc), "bad_password") from exc
        jobs.audit("password_set", by=current, role=role)
        return next(m.UserOut(**u) for u in deps.auth.users() if u["role"] == role)

    @api.post("/users/sessions/revoke", response_model=m.RevokedOut)
    def revoke_sessions(current: str = Depends(need("maintainer"))) -> m.RevokedOut:
        """End every session, this one included."""
        n = deps.auth.revoke_all()
        jobs.audit("sessions_revoked", by=current, count=n)
        return m.RevokedOut(revoked=n)

    # --- audit -------------------------------------------------------------------------------------------------

    def audit_events(kind: str | None, job_id: str | None) -> list[m.AuditEvent]:
        events = []
        for e in reversed(jobs.read_audit()):
            if (kind and e.get("kind") != kind) or (job_id and e.get("job_id") != job_id):
                continue
            data = {k: v for k, v in e.items() if k not in ("at", "kind")}
            events.append(m.AuditEvent(at=e.get("at", ""), kind=e.get("kind", ""), data=data))
        return events

    @api.get("/audit", response_model=m.AuditOut)
    def audit(kind: str | None = None, job_id: str | None = None, limit: int = QueryParam(100, ge=1, le=1000), offset: int = QueryParam(0, ge=0), _: str = Depends(need("supervisor"))) -> m.AuditOut:
        events = audit_events(kind, job_id)
        return m.AuditOut(events=events[offset : offset + limit], total=len(events))

    @api.get("/audit.csv", responses={200: {"content": {"text/csv": {}}}})
    def audit_csv(kind: str | None = None, job_id: str | None = None, _: str = Depends(need("supervisor"))) -> Response:
        out = io.StringIO()
        writer = csv.writer(out, delimiter=";")
        writer.writerow(["quando", "evento", "detalhes"])
        for e in audit_events(kind, job_id):
            writer.writerow([e.at, e.kind, json.dumps(e.data, ensure_ascii=False, sort_keys=True)])
        return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="auditoria.csv"'})

    # --- dataset ---------------------------------------------------------------------------------------------

    @api.get("/dataset", response_model=m.DatasetOut)
    def dataset(_: str = Depends(need("maintainer"))) -> m.DatasetOut:
        out = []
        for job_id in jobs.job_ids():
            name = jobs.load(JobRef(job_id, jobs.latest(job_id))).job.job.name  # type: ignore[arg-type]
            out.append(m.DatasetJob(job_id=job_id, name=name, collecting=deps.results.collecting(job_id), images=deps.results.dataset_count(job_id)))
        return m.DatasetOut(jobs=out, total=deps.results.dataset_count())

    @api.get("/dataset/{job_id}/images", response_model=m.DatasetImagesOut)
    def dataset_images(job_id: str, limit: int = QueryParam(48, ge=1, le=200), offset: int = QueryParam(0, ge=0), _: str = Depends(need("maintainer"))) -> m.DatasetImagesOut:
        """The images a job has in the dataset, newest first, for the grid with their labels (document 05 §7.5)."""
        return m.DatasetImagesOut(total=deps.results.dataset_count(job_id), images=[m.DatasetImage(**row) for row in deps.results.dataset_items(job_id, limit, offset)])

    @api.get("/dataset/{job_id}/images/{image_id}.jpg", responses={200: {"content": {"image/jpeg": {}}}, 404: {"model": m.Problem}})
    def dataset_image(job_id: str, image_id: str, width: int = QueryParam(320, ge=64, le=1920), _: str = Depends(need("maintainer"))) -> Response:
        """One image of the dataset, reduced to `width` (a grid of thumbnails does not carry full frames)."""
        path = deps.results.dataset_file(job_id, image_id)
        if path is None:
            raise Problem(404, "Essa imagem não existe", "image_not_found")
        image = cv2.imread(str(path))
        if image is None:
            raise Problem(404, "Essa imagem não existe", "image_not_found")
        if image.shape[1] > width:
            image = cv2.resize(image, (width, max(1, round(image.shape[0] * width / image.shape[1]))), interpolation=cv2.INTER_AREA)
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return Response(jpeg.tobytes() if ok else b"", media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

    @api.post("/dataset/export", response_model=m.DatasetExportOut, responses={409: {"model": m.Problem}})
    def export_dataset(body: m.DatasetExportBody, role: str = Depends(need("maintainer"))) -> m.DatasetExportOut:
        """Images and labels for training, into <data>/exports/ (training happens offline, TD-08)."""
        try:
            export = deps.results.export_dataset(jobs.root / "exports", job_id=body.job_id)
        except ResultsError as exc:
            raise Problem(409, "Não há imagens coletadas para exportar", "dataset_empty") from exc
        jobs.audit("dataset_export", by=role, job_id=body.job_id, dataset_id=export.dataset_id, count=export.count)
        return m.DatasetExportOut(dataset_id=export.dataset_id, folder=str(export.path), count=export.count)

    return build
