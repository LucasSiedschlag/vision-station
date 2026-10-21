"""The commissioning wizard's state (VIA-0068, FR-ADM-8, document 05 §7.11).

Every step is derived from what exists, never stored: a password that is set, frames that arrive, a folder that is
there, a job that was saved. So a restart of the program (a camera change needs one) loses nothing and two open
screens agree. While the Maintainer has no password the wizard opens without a login, so the first step can create it.
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from vision_station.api import schemas as m
from vision_station.api.auth import AuthError, at_least
from vision_station.core.i18n import render, tr


def add_setup_routes(api: APIRouter, deps: Any, role: Callable[..., str], need: Callable[[str], Callable], Problem: type) -> None:
    """`role` is the app's dependency that gives the role behind the request's token, `need(role)` the one that asks
    for a role, `Problem` its error."""

    first_password = threading.Lock()  # two requests at once must not both find the password missing

    def maintainer_password_missing() -> bool:
        return not deps.auth.has_password("maintainer")

    def may_ask(current: str = Depends(role)) -> str:
        if maintainer_password_missing() or at_least(current, "maintainer"):
            return current
        if current == "operator":
            raise Problem(401, tr("É preciso entrar como Mantenedor"), "login_required")
        raise Problem(403, "Este perfil não tem permissão para isso", "forbidden")

    def step(id: str, done: bool, todo: str = "", done_detail: str = "") -> m.SetupStepOut:
        return m.SetupStepOut(id=id, state="done" if done else "todo", detail=render(done_detail if done else todo) or None)  # type: ignore[arg-type]

    def camera_step() -> m.SetupStepOut:
        acq = deps.acquisition
        sending = acq.latest() is not None and not acq.stalled()
        if sending:
            return step("camera", True, done_detail=tr("A câmera está mandando imagem"))
        return step("camera", False, todo=acq.last_error or tr("A câmera não está mandando imagem"))

    def backup_step() -> m.SetupStepOut:
        svc = deps.system
        folder = svc.config.backup.folder if svc is not None else None
        if not folder:
            return step("backup", False, todo=tr("Nenhuma pasta escolhida: os backups ficam só na pasta de dados"))
        if not Path(folder).is_dir():
            return step("backup", False, todo=tr("A pasta {folder} não existe ou não está ligada", folder=folder))
        return step("backup", True, done_detail=tr("Pasta de backup: {folder}", folder=folder))

    def on_this_pc() -> bool:
        svc = deps.system
        return svc is not None and svc.started_with.network.local_only  # unknown counts as not local: fail safe

    @api.get("/setup/open", response_model=m.SetupOpenOut)
    def setup_open() -> m.SetupOpenOut:
        """Whether the first password can be created now: for the notice on the operator screen. Says nothing else."""
        return m.SetupOpenOut(open=maintainer_password_missing() and on_this_pc())

    @api.get("/setup/status", response_model=m.SetupStatusOut, responses={401: {"model": m.Problem}, 403: {"model": m.Problem}})
    def setup_status(_: str = Depends(may_ask)) -> m.SetupStatusOut:
        """The seven steps of the wizard and whether the installation still needs it. Open to everyone while the
        Maintainer has no password (the first step creates it); the Maintainer's afterwards."""
        missing = maintainer_password_missing()
        camera = camera_step()
        job = step("first_job", bool(deps.jobs.job_ids()), todo=tr("Nenhum job criado ainda"))
        steps = [
            step("maintainer_password", not missing, todo=tr("O Mantenedor ainda não tem senha")),
            camera,
            m.SetupStepOut(id="performance", state="unavailable", detail=render(tr("Disponível quando o teste de desempenho do PC for feito (fase C)"))),
            step("supervisor_password", deps.auth.has_password("supervisor"), todo=tr("O Supervisor ainda não tem senha")),
            m.SetupStepOut(id="machine", state="unavailable", detail=render(tr("Interface com a máquina ainda não disponível (fase B)"))),
            backup_step(),
            job,
        ]
        return m.SetupStatusOut(steps=steps, needs_setup=missing or camera.state != "done" or job.state != "done", maintainer_password_missing=missing)

    @api.put(
        "/setup/maintainer-password",
        response_model=m.UserOut,
        responses={400: {"model": m.Problem}, 403: {"model": m.Problem}, 409: {"model": m.Problem}},
    )
    def create_maintainer_password(body: m.SetupPasswordBody) -> m.UserOut:
        """The first password of the Maintainer, with no login: only while there is none, once, and only when the
        API listens on this PC (anyone who can reach it from the network would otherwise take over the station).
        No session is opened; the screen logs in afterwards. Everything after it asks for a login."""
        if not on_this_pc():
            raise Problem(403, tr("A senha inicial só pode ser criada no próprio PC da estação"), "not_local")
        with first_password:
            if not maintainer_password_missing():
                raise Problem(409, tr("O Mantenedor já tem senha; entre para continuar"), "conflict")
            try:
                deps.auth.set_password("maintainer", body.password)
            except AuthError as exc:
                raise Problem(400, tr("Senha não aceita: {why}", why=exc), "bad_password") from exc
            deps.jobs.audit("password_set", by="setup", role="maintainer")
        return next(m.UserOut(**u) for u in deps.auth.users() if u["role"] == "maintainer")

    @api.get("/setup/cameras", response_model=m.SetupCamerasOut, responses={401: {"model": m.Problem}, 403: {"model": m.Problem}})
    def setup_cameras(_: str = Depends(need("maintainer"))) -> m.SetupCamerasOut:
        """The USB cameras connected to this PC, each with what to put in the system configuration to open it and
        whether its model has been validated. `available` is false when this PC cannot list cameras at all."""
        found = deps.discover_cameras()
        return m.SetupCamerasOut(
            available=found.available,
            cameras=[
                m.SetupCameraOut(name=c.name, driver=c.driver, connection=c.connection, model=c.model, validated=c.model is not None)
                for c in found.cameras
            ],
        )
