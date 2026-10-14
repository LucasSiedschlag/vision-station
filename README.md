# Vision Station

General inspection platform for a **fixed station**: a fixed camera identifies objects, colors or codes. Like commercial vision systems, a *job* holds the camera setup and a list of *tools* (`color`, `pattern`, `code`, `detect`), each looking at a region the user draws, and the screen shows **PASS / FAIL / ERROR** with the reason.

The first application (for Customer) is the packing station: each box is placed on a scale, and the camera checks that it leaves **closed and taped**. Platform decisions are in [TD-19](docs/technical-decisions.md).

> **Status:** design done, implementation starting. The first delivery (30/10/2026) runs with the Logitech C920; the Hikvision camera comes later.

## What it will do

Platform: tools by type, jobs exportable to one backup file and restorable with automatic verification, a camera plugin (C920 now, Hikvision later), operator screen and results log. First application (box and tape):

- Inspect every box (sizes P, M, G, GG) with red tape or transparent tape with a printed logo.
- Keep all inspection settings in **jobs**: one per product or box type, exportable to a single backup file and restorable on a replacement PC or camera, with automatic verification that behavior is the same.
- Prototype with a Logitech C920 USB webcam, then move to a Hikvision DS-2CD3666G2T-IZS IP camera (motorized lens) without rewriting the inspection logic.
- Run on a client-supplied Windows 11 PC, CPU only.
- Never show a false PASS: any doubt is ERROR.

## Documents

| # | Document | Content |
|---|---|---|
| 01 | [Project scope](docs/project-scope.md) | Purpose, scope, deliverables, phases, risks, open client questions |
| 02 | [Requirements and use cases](docs/requirements-and-use-cases.md) | Functional and non-functional requirements, use cases UC-01..10 |
| 03 | [Architecture](docs/architecture.md) | Components, the job model, `.vjob` / `.vbak` formats, camera abstraction, station state machine |
| 04 | [Technical decisions](docs/technical-decisions.md) | Decisions TD-01..20, PC spec, network, known problems, bench tests |
| 05 | [Frontend](docs/frontend.md) | The web interface: stack, design system, screens by role, API contract, editor, tests, build |

## Stack (planned)

Python 3.12, OpenCV, ONNX Runtime (CPU, OpenVINO on Intel), FastAPI, SQLite, a local web UI in Edge kiosk mode, packaged as a Windows service with PyInstaller and Inno Setup. Only permissive licenses ship in the product (no Ultralytics/AGPL).

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
uv run python scripts/run_station.py --name C920 --exposure-us 33000
```

Starts the camera thread and the state machine with a stand-in inspection (reads a code in the picture). Put an object in the area, wait until it is still, and watch the states and the result; take it away to re-arm. Pictures go to `station_out/`.

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

To try it without the bench, on any computer: `uv run python scripts/demo_station.py` and open `http://127.0.0.1:8765/` (simulated camera, logins `supervisor` / `supervisor-pass` and `maintainer` / `maintainer-pass`). With the C920, open `http://127.0.0.1:8765/` while `run_api.py` is running. The operator screen needs no login: live image, state, result and reason, shift counters, "Inspecionar agora" and "Resultado incorreto?". **Entrar** gives the Supervisor and Maintainer screens as they are built (TD-20). This is a **prototype** (Preact + htm) that stays until the React interface of document 05 reaches parity; its logic tests run with `node --test tests/web/*.test.mjs`.

### API

```bash
uv run python scripts/set_password.py supervisor          # once per role (supervisor, maintainer)
uv run python scripts/run_api.py --name C920 --exposure-us 33000   # station + API on 127.0.0.1:8765, docs at /docs
```

Operator, no login: `GET /state`, `GET /result/last`, `GET /snapshot.jpg`, `POST /trigger`, `WS /live` (status, state and result events as JSON, JPEG frames as binary, at most 10 per second), `POST /results/{id}/incorrect`. Supervisor (`POST /login`, then `Authorization: Bearer ...`): jobs (list, verify and activate, export, import `.vjob`/`.vbak`), backups, results (browse, filter, images, CSV). Maintainer: collection mode, pause/resume/retry, and overriding a failed verification. It accepts only local Host headers and refuses browser requests from other origins.

## Related

- [`vision-sim`](../vision-sim): the *Bancada Virtual de Visão* simulator, used to choose camera, lens, height and lighting before buying hardware.

## Phases

0. Definition (documents 01–04 approved)
1. Prototype with the C920
2. Model (labeling, training, validation)
3. Production camera (Hikvision) and on-site installation
4. Acceptance and handover

## Author

Lucas Siedschlag.
