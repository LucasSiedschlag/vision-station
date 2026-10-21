"""The commissioning wizard's state (VIA-0068, FR-ADM-8, document 05 §7.11).

Every step is derived from what exists, never stored: a password that is set, frames that arrive, a folder that is
there, a job that was saved. So a restart of the program (a camera change needs one) loses nothing and two open
screens agree. While the Maintainer has no password the wizard opens without a login, so the first step can create it.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from vision_station.api import schemas as m
from vision_station.api.auth import at_least
from vision_station.core.i18n import render, tr


def add_setup_routes(api: APIRouter, deps: Any, role: Callable[..., str], Problem: type) -> None:
    """`role` is the app's dependency that gives the role behind the request's token, `Problem` its error."""

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
