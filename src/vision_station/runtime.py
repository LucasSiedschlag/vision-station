"""The program: reads the system configuration, wires camera, station, pipeline, records and API, and runs.

    vision-station --data C:\\ProgramData\\VisionSystem      (or python -m vision_station)

One process (TD-02): the acquisition thread, the station controller thread, a maintenance thread
(housekeeping and automatic backups) and the API server. On start the active job is loaded and verified
like any activation; with no active job the screen says so and the station waits for one.
"""

import argparse
import logging
import logging.handlers
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vision_station.api import ApiDeps, AuthService, create_app, make_event_handler
from vision_station.build_info import describe
from vision_station.cameras import Camera, create_camera
from vision_station.core.i18n import tr
from vision_station.pipeline import draw_overlay, inspect_job
from vision_station.records import ResultRecorder, ResultStore
from vision_station.station import Acquisition, StationController
from vision_station.store import JobStore
from vision_station.system import ConfigError, Maintenance, SystemConfig, SystemService, default_data_root, load_config, shift_start
from vision_station.verification import JobVerifier

log = logging.getLogger("vision_station")

LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")


@dataclass
class Runtime:
    root: Path
    system: SystemService
    jobs: JobStore
    results: ResultStore
    auth: AuthService
    acquisition: Acquisition
    controller: StationController
    deps: ApiDeps
    maintenance: Maintenance
    _threads: list[threading.Thread] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)

    def load_active_job(self) -> None:
        ref = self.jobs.get_active()
        if ref is None:
            log.info("no active job")
            return
        try:
            bundle = self.jobs.load(ref)
        except Exception as exc:  # a damaged store must not stop the program: the screen says what happened
            log.exception("cannot load the active job %s v%s", ref.job_id, ref.version)
            self.controller.fault(tr("O job ativo não pôde ser carregado: {exc}", exc=exc))
            return
        self.controller.start(bundle)

    def start(self, maintenance_period_s: float = 60.0) -> None:
        self.load_active_job()
        self.acquisition.start()
        self._spawn("station", self.controller.run)
        self._spawn("maintenance", lambda: self._maintenance_loop(maintenance_period_s))

    def _maintenance_loop(self, period_s: float) -> None:
        while not self._stop.wait(period_s):
            self.maintenance.tick()

    def _spawn(self, name: str, target) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()
        self.controller.stop()
        self.acquisition.stop()
        for thread in self._threads:
            thread.join(timeout=5)
        self.results.close()


def build_runtime(root: Path | str, config: SystemConfig | None = None, camera: Camera | None = None, web_dist: Path | None = None) -> Runtime:
    """Everything wired, nothing started. `camera` replaces the configured one (tests, the simulated station)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = config if config is not None else load_config(root)
    jobs = JobStore(root)
    results = ResultStore(root, config.recording.to_recording_config())
    auth = AuthService(root / "system" / "users.json")
    acquisition = Acquisition(
        camera if camera is not None else create_camera(config.camera.driver),
        config.camera.connection,
        settle_s=config.camera.settle_ms / 1000,
        dead_after_s=config.camera.dead_after_s,
    )
    controller = StationController(
        acquisition, inspect_job, verifier=JobVerifier(inspect_job), hold_s=config.station.result_min_s,
        first_sequence=results.next_sequence(), save_sequence=results.save_sequence,  # a restart continues the numbers a PLC follows (TD-22)
    )
    system = SystemService(root, config)
    extra = dict(web_dist=web_dist) if web_dist is not None else {}
    deps = ApiDeps(
        controller=controller,
        acquisition=acquisition,
        jobs=jobs,
        results=results,
        auth=auth,
        inspect=inspect_job,
        recorder=ResultRecorder(results, overlay=draw_overlay, language=lambda: system.config.station.language),
        backup_dir=system.backup_dir(),
        shift_start=lambda: shift_start(system.config, datetime.now().astimezone()),
        allowed_hosts=LOCAL_HOSTS + tuple(config.network.allowed_hosts),
        system=system,
        overlay=draw_overlay,
        cors_origins=tuple(config.network.allowed_origins),
        **extra,
    )

    def apply(new: SystemConfig) -> None:  # what applies without a restart
        results.config = new.recording.to_recording_config()
        deps.backup_dir = system.backup_dir()
        controller.set_hold(new.station.result_min_s)

    system.on_apply = apply
    controller._on_event = make_event_handler(deps)
    maintenance = Maintenance(system, jobs, results)
    deps.maintenance = maintenance
    return Runtime(root, system, jobs, results, auth, acquisition, controller, deps, maintenance)


def _setup_logging(root: Path, verbose: bool) -> None:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(logs / "vision-station.log", when="midnight", backupCount=30, encoding="utf-8")  # NFR-MAI-2
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=[handler, logging.StreamHandler()])


def _set_password(root: Path, role: str) -> int:
    import getpass

    from vision_station.api import AuthError

    password = getpass.getpass(f"Nova senha do perfil {role}: ")
    if password != getpass.getpass("Repita: "):
        print("As duas senhas são diferentes.")
        return 1
    try:
        AuthService(root / "system" / "users.json").set_password(role, password)
    except AuthError as exc:
        print(f"Senha não aceita: {exc}")
        return 1
    print(f"Senha do perfil {role} definida em {root / 'system' / 'users.json'}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vision-station", description="Vision Station: the inspection station and its web interface.")
    parser.add_argument("--data", type=Path, default=None, help=f"data folder (default: {default_data_root()})")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_argument("--set-password", choices=["supervisor", "maintainer"], metavar="ROLE", help="set the password of supervisor or maintainer and exit")
    args = parser.parse_args(argv)
    if args.version:
        print(f"vision-station {describe().replace(' · ', ' / ')}")  # plain ASCII: any console code page
        return 0
    root = args.data or default_data_root()
    if args.set_password:
        return _set_password(root, args.set_password)
    _setup_logging(root, args.verbose)
    try:
        runtime = build_runtime(root)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2
    network = runtime.system.config.network
    if not network.local_only and not (runtime.auth.has_password("supervisor") or runtime.auth.has_password("maintainer")):
        log.error("the API is set to listen on %s, but no Supervisor or Maintainer password exists; set one first (vision-station --set-password maintainer)", network.host)
        return 2
    import uvicorn

    log.info("starting: data %s, camera %s, listening on %s:%s", root, runtime.system.config.camera.driver, network.host, network.port)
    runtime.start()
    try:
        uvicorn.run(create_app(runtime.deps), host=network.host, port=network.port, log_level="info")
    finally:
        runtime.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
