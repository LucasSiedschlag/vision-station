# Vision Station

A configurable vision system for **fixed industrial stations and machines**: a fixed camera looks at an object that is **stopped** for the reading (a part on a jig, a product on a bench or scale, a machine that pauses) and answers **PASS / FAIL / ERROR** with the reason in Portuguese. Objects in motion are out of scope.

Like commercial vision systems, a *job* holds the camera setup and an ordered list of *tools* (`color`, `pattern`, `code`, `detect`), each looking at a region the user draws, relative to the frame or to an *anchor* found by a *locator*. Decisions are in [TD-19](docs/technical-decisions.md).

Vision Station is not built around any product. Each customer project (for example a packing station that checks that boxes leave closed and taped) installs Vision Station and configures its own jobs; those projects live in their own place, not in this repository.

> **Status:** platform core working (cameras, jobs, backups, verification, pipeline, results, API, operator screen). Tools, locators, management screens and the job editor are being added for the first delivery (30/10/2026, Logitech C920). The Hikvision camera comes later.

## What it does

- Inspects a still object with the tools of the active job; any doubt (dark, blurred or flat picture, object not found, a tool that breaks, camera lost) is **ERROR**, never a false PASS.
- Keeps every setting in **jobs**: versioned, exportable to one file (`.vjob`), backed up together (`.vbak`), and restored on a replacement PC or camera with automatic verification that the behavior is the same.
- Treats the camera as a plugin: Logitech C920 (USB) now, Hikvision IP camera (motorized lens) later, without rewriting the inspection logic.
- Runs on a Windows 11 PC, CPU only, as a service with a local web screen for the operator, the supervisor and the maintainer.

## Documents

| # | Document | Content |
|---|---|---|
| 01 | [Project scope](docs/project-scope.md) | Purpose, scope, deliverables, phases, risks, open client questions |
| 02 | [Requirements and use cases](docs/requirements-and-use-cases.md) | Functional and non-functional requirements, use cases UC-01..10 |
| 03 | [Architecture](docs/architecture.md) | Components, the job model, `.vjob` / `.vbak` formats, camera abstraction, station state machine |
| 04 | [Technical decisions](docs/technical-decisions.md) | Decisions TD-01..20, PC spec, network, known problems, bench tests |
| 05 | [Frontend](docs/frontend.md) | The web interface: stack, design system, screens by role, API contract, editor, tests, build |
| 06 | [Integration](docs/integration.md) | How another program on the same PC uses Vision Station: request an inspection, get the result and pictures, live view |
| 07 | [Models](docs/models.md) | The `detect` tool: train offline, export to ONNX, the model card, what each task returns |
| 08 | [Job file format](docs/job-format.md) | `.vjob` and `.vbak`: container, manifest, `job.yaml`, camera profile, reference set (deliverable D8) |

## Stack

Python 3.12, OpenCV, ONNX Runtime (CPU, OpenVINO on Intel), FastAPI, SQLite, a local web UI in Edge kiosk mode, packaged as a Windows service with PyInstaller and Inno Setup. Only permissive licenses ship in the product (no Ultralytics/AGPL).

## Run everything (quick start)

**Needs:** [uv](https://docs.astral.sh/uv/) (installs Python 3.12 by itself) and **Node 24 LTS** (only to build the screens; `frontend/.nvmrc`). On Windows: `winget install astral-sh.uv` and `winget install OpenJS.NodeJS.LTS`.

**1. Install and build (once, and after each `git pull`)**

```bash
uv sync                      # Python and the dependencies; on Windows with the C920: uv sync --extra uvc
cd frontend && npm ci && npm run build && cd ..     # the web interface, into frontend/dist/
```

**2. Prepare a data folder (once)**

```bash
# with the C920 (Windows): reference.png is a picture of the bench with a readable code
uv run python scripts/setup_bench.py --name C920 --reference reference.png --exposure-us 33000
# without a camera (any OS): a folder with a few PNG/JPG pictures plays as the camera (the first is the reference)
uv run python scripts/setup_bench.py --folder path/to/pictures

uv run python scripts/set_password.py maintainer      # asks for the password (8+ characters)
uv run python scripts/set_password.py supervisor
```

`setup_bench.py` writes `bench_data/system/system.yaml` (the camera) and creates and activates a code-reading job, with the reference image and the reference set every job needs (FR-JOB-9); it refuses a reference picture the job cannot read. Use `--data <folder>` on both scripts for another folder.

**3. Run**

```bash
uv run vision-station --data bench_data
```

Open http://127.0.0.1:8765: the operator screen. **Entrar** opens the Supervisor and Maintainer screens: **Jobs** lists the jobs (activate with verification, import, export, backups), **Resultados**, **Auditoria** and **Acessos** are there for the Supervisor, **Dataset** and **Configurações** for the Maintainer, and as Maintainer **Novo job** / **Editar** opens the job editor (camera, trigger, quality, regions drawn on the image, tools, reference, test, save). The API's own page is http://127.0.0.1:8765/api/docs. Stop with Ctrl+C. Logs: `bench_data/logs/`.

**4. Check that all is well**

```bash
uv run pytest                                  # Python tests
cd frontend && npm test && npm run e2e         # interface tests (e2e once needs: npx playwright install chromium)
```

**Working on the screens without the bench:** `uv run python scripts/e2e_station.py --port 8765` (a simulated station with logins `supervisor` / `supervisor-pass` and `maintainer` / `maintainer-pass`) and, beside it, `cd frontend && npm run dev` (http://localhost:5173, reloads on save).

**Another program using the vision system** (a station's own software): see [docs/integration.md](docs/integration.md).

## Install on the station PC (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1    # needs uv, Node 24, git and Inno Setup 6
```

It builds the program (`dist\vision-station\`, PyInstaller) and the installer `dist\VisionStation-<version>-setup.exe` (Inno Setup; the CI builds the same one, artifact *installer*). The installer puts the program in `C:\Program Files\VisionSystem`, the data in `C:\ProgramData\VisionSystem`, starts it as a Windows service (WinSW) or at logon, and can open the operator screen in Edge kiosk mode. On the installed PC: `vision-station.exe --version`, `vision-station.exe --set-password maintainer`. Guides: [installation](docs/guides/installation.md), [operator](docs/guides/operator.md), [backup and restore](docs/guides/backup-and-restore.md), [building the installer](docs/guides/building-the-installer.md); job file format: [docs/job-format.md](docs/job-format.md); third-party licences: `THIRD_PARTY_LICENSES.md` (generated by `scripts/third_party_licenses.py`).

## Development

Needs [uv](https://docs.astral.sh/uv/). It installs Python 3.12 by itself.

```bash
uv sync
uv run pytest
```

On Windows, `uv sync --extra uvc` adds the C920 controls (duvc-ctl).

### C920 bench check (Windows)

```bash
uv sync --extra uvc
uv run python scripts/c920_check.py --list
uv run python scripts/c920_check.py --name C920 --repeat 20
```

Opens the camera, applies `examples/c920-profile.yaml`, reads every setting back and measures fps. Exit code 1 if any setting was rejected.

### Code tool (bar codes and QR)

```bash
uv run python scripts/make_test_codes.py   # test_codes.html: print at 100% to find the smallest readable code
uv run python scripts/read_codes.py --name C920 --seconds 10   # Windows, camera plugged in
```

In a job: `{id: lote, type: code, version: 1, roi: label, params: {formats: [QRCode], pattern: 'LOTE-\d+'}, reason_fail: "Código não lido"}`. Parameters are in `src/vision_station/tools/code.py`.

### Inspection pipeline

```python
from vision_station.pipeline import inspect_job, draw_overlay

result = inspect_job(bundle, frame)          # never raises; any doubt is ERROR
StationController(acq, inspect_job, on_event=ResultRecorder(store, overlay=draw_overlay))
```

Order: brightness range → locator (`geometry.locator`) → sharpness vs. the reference → regions in pixels (relative to `frame` or `anchor`) → every tool in order → `all_pass`. The locator runs before the sharpness check so an empty station says "Objeto não encontrado", not "fora de foco". The reason lists every tool that failed; `details` has the timings, the anchor and each region's rectangle.

Locators (`src/vision_station/locators/`):

| Type | Finds the anchor by | Main parameters |
|---|---|---|
| `fixed` | a rectangle written in the job (a jig holds the object) | `rect` |
| `template` | a taught picture inside the job, normalized correlation (light changes and shifts, not rotation or size) | `template` (path in the job), `search`, `min_score` |
| `blob` | the largest region of a color, or darker / lighter than the background | `mode` (`color`, `dark`, `light`), `color`, `threshold`, `min_area`, `max_area`, `search` |

Tools (`src/vision_station/tools/`): `code` (bar codes and 2D codes, above) and `color`: the fraction of the region in a color (HSV range, or a reference RGB with a ΔE distance), and optionally the coverage along `x` or `y` with the longest gap, e.g. `{id: faixa, type: color, version: 1, roi: seam, params: {hue: [170, 10], s_min: 100, v_min: 70, axis: x, min_coverage: 0.9, max_gap: 0.05}, reason_fail: "Faixa ausente em {missing:.0%} da emenda"}`. `pattern` finds a taught template (a logo, a mark) in the region and counts it (`min_count`, `max_count`), and optionally its coverage along `x` or `y` with the longest stretch without it, ends included: `{id: marca, type: pattern, version: 1, roi: seam, params: {template: patterns/logo.png, axis: x, max_gap: 0.1}, reason_fail: "Marca ausente em {gap:.0%} da faixa"}`. Like the `template` locator it tolerates light changes, not rotation or size. `detect` runs a trained ONNX model (classifier, DETR-style detector or anomaly) with its card, both inside the job ([docs/models.md](docs/models.md)). Files a tool or locator needs (a template) travel inside the job; a job without them is refused when loaded.

### Jobs, versions and backups

```python
from vision_station.store import JobStore, JobBundle, JobRef

store = JobStore("C:/ProgramData/VisionSystem")      # <root>/jobs/<job-id>/v<n>/, <root>/system/active.yaml
ref = store.save(JobBundle(job, profile, extra={"reference/reference.png": png}))
store.write_vjob(ref, "E:/")                          # .vjob, read back and checked before it counts
store.make_backup("E:/backups", keep=30)              # .vbak with every version, rotated
store.restore_backup(open("backup.vbak", "rb").read())  # checks the whole file first; stores nothing if damaged
```

Format and rules: `docs/architecture.md` §4. A saved version is never changed, a damaged or newer-format file is refused with a clear message, and no secrets are written.

### Station controller (C920 bench run)

```bash
uv run python scripts/run_station.py --name C920 --reference reference.png --exposure-us 33000
```

Starts the camera thread and the state machine with a stand-in inspection (reads a code in the picture). Supply a reference image with a readable code and start with that scene in view for verification (FR-JOB-9). Then empty the scene and press Enter to set the background. Put an object in the area, wait until it is still, and watch the states and the result; take it away to re-arm. Pictures go to `station_out/`.

### Verification and activation

```python
from vision_station.verification import JobVerifier, activate, make_reference_files, verify_live, verify_stored_job

extra = make_reference_files(image_of_a_good_object)           # reference/reference.png and .meta.yaml, for the job
verifier = JobVerifier(inspect)                                 # StationController(..., verifier=verifier)
report = verify_live(store, ref, acquisition, inspect)          # camera settings + live view vs reference + reference set
report = verify_stored_job(store, ref, inspect)                 # reference set only, no camera (proves a restore)
activate(store, ref, report)                                    # only if verified, or activate(..., override_reason="...")
```

The reference set is `tests/expected.yaml` (image, expected outcome, scores with a tolerance, reason text) and `tests/images/` inside the job. Every activation and override goes to `system/audit.log`.

### Results and training data

```python
from vision_station.records import ResultStore, ResultRecorder, RecordingConfig, Query

store = ResultStore("C:/ProgramData/VisionSystem")            # results/results.db, results/images/, dataset/
controller = StationController(acq, inspect, on_event=ResultRecorder(store))   # every result, with its frame
store.find(Query(outcome="FAIL"), limit=50)                    # browse; store.counts(since) for the shift totals
store.export_csv("resultados.csv", Query(job_id=job_id))       # ';' separated, opens in Excel
store.set_collection(job_id, True)                             # collection mode: every frame also goes to dataset/
store.mark_incorrect(record_id, "FAIL", by="supervisor")       # a wrong result becomes labeled training data
store.export_dataset("E:/datasets")                            # images + labels.csv + manifest.json with SHA-256
```

By default every image is kept. `RecordingConfig` sets PASS sampling, retention days and a free-disk limit, applied by `store.housekeeping()` (run it hourly); it never deletes `dataset/` or the job store.

### Web interface

The interface is the React app in `frontend/` (below). The operator screen needs no login; **Entrar** opens the Supervisor and Maintainer screens as they are built (TD-20). To work on it without the bench, run the simulated station of the tests, `uv run python scripts/e2e_station.py --port 8765` (logins `supervisor` / `supervisor-pass` and `maintainer` / `maintainer-pass`). Without a build, `/` says how to build it and the API keeps working.

### The React interface

Needs **Node 24 LTS** (`frontend/.nvmrc`; on Windows `winget install OpenJS.NodeJS.LTS` or `nvm use 24`). Node is only for building: the installed program serves `frontend/dist`.

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxies /api to 127.0.0.1:8765 (run `uv run python scripts/e2e_station.py --port 8765` beside it)
npm run build      # writes frontend/dist/, which the API serves (set VISION_STATION_WEB to serve another folder)
npm test           # unit and component tests;  npm run lint;  npm run typecheck
npx playwright install chromium   # once
npm run e2e        # end-to-end tests and accessibility (axe) against scripts/e2e_station.py; needs `npm run build` first
npm run gen:api    # regenerates the TypeScript types from the API after any change to src/vision_station/api/
```

Details, design system and screens: [docs/frontend.md](docs/frontend.md). All API paths are under `/api`; the typed client is generated from `GET /api/openapi.json`.

### Running the station

```bash
uv run vision-station --data C:/ProgramData/VisionSystem   # or python -m vision_station; default data folder per OS
```

One process: camera, station, inspection pipeline, records (with the overlay image), hourly housekeeping, automatic backups and the API with the web interface on `127.0.0.1:8765`. The active job is loaded and verified on start; with none, the screen says "Nenhum job ativo". Logs rotate daily in `<data>/logs/`.

The installation's settings are in `<data>/system/system.yaml` (architecture §4.5), edited on the screen (Configurações) or by hand; a missing file means the defaults:

```yaml
station: {name: Linha 2, shift_starts: ['06:00', '14:00', '22:00'], idle_logout_min: 10, fail_sound: false}
camera: {driver: uvc, connection: {device_name: C920}}            # file: {path: folder, loop: true, fps: 10}
recording: {pass_sample_every: 1, retention_days: null, min_free_gb: null}
backup: {folder: 'E:/backups', every_hours: 24, keep: 30, include: all}
network: {host: 127.0.0.1, port: 8765, allowed_hosts: []}       # another host opens it to the network
```

No password ever goes in it (a camera names an OS secret store entry in `keyring_entry`). Recording, backup and station settings apply at once; camera and network after a restart. Opening the API to the network needs a Supervisor or Maintainer password first.

On the bench, with the C920:

```bash
uv run python scripts/setup_bench.py --name C920 --reference reference.png --exposure-us 33000   # system.yaml + a code-reading job, active
uv run python scripts/set_password.py maintainer                       # once per role (supervisor, maintainer)
uv run vision-station --data bench_data
```

### API

Every path is under `/api`; the full list is in `/api/docs` and [docs/frontend.md](docs/frontend.md) §9. Operator, no login: `GET /state`, `GET /result/last`, `GET /snapshot.jpg`, `POST /trigger`, `WS /live` (status, state and result events as JSON, JPEG frames as binary, at most 10 per second), `POST /results/{id}/incorrect`. Supervisor (`POST /login`, then `Authorization: Bearer ...`): jobs (list, verify and activate, export, import `.vjob`/`.vbak`), backups, results (browse, filter, images, CSV). Maintainer: collection mode, pause/resume/retry, overriding a failed verification, the system configuration (`GET/PUT /system`, `POST /system/test-camera`, `POST /system/test-folder`), and the job editor's endpoints: tool and locator types with their parameter schemas (`GET /tools`), jobs as drafts (`POST /jobs/validate`, `POST /jobs`, `POST /jobs/{id}/versions`, `POST /jobs/{id}/duplicate`, `POST /jobs/test` on the live frame or an image, `GET /jobs/{id}/versions/{v}` and its files, `GET .../diff?against=`), camera tuning (`GET /camera/state`, `POST /camera/apply`, which pauses the station), reference image and reference-set cases (`POST /reference/capture`, `POST /reference/cases`), passwords and sessions (`/users`), audit (`GET /audit`, `/audit.csv`) and dataset (`GET /dataset`, `POST /dataset/export`). Other programs: `POST /inspections` and `GET /inspections/{id}` ([docs/integration.md](docs/integration.md)). It accepts only local Host headers and refuses browser requests from other origins.

## Related

- [`vision-sim`](../vision-sim): the *Bancada Virtual de Visão* simulator, used to choose camera, lens, height and lighting before buying hardware.

## Phases

0. Definition (documents 01–05)
1. Platform with the C920 (first delivery, 30/10/2026)
2. Model (`detect` tool and the offline training path)
3. Production camera (Hikvision)
4. First customer project on site (owned by that project)

## Trademarks

Cognex, In-Sight, Keyence, MVTec, MERLIC, Hikvision, Logitech, Siemens, Intel, OpenVINO, Microsoft and Windows, and any other product or company names mentioned in this repository, are trademarks or registered trademarks of their respective owners. They are used only to identify products for comparison and compatibility. Vision Station is an independent project and is not affiliated with, endorsed by, or sponsored by any of them.

## Author

Lucas Siedschlag.
