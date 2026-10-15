# CLAUDE.md


## What this is

**Vision Station**: a general vision system for **industrial fixed stations and machines**, where a fixed camera looks at an object that is **stopped** for the reading (objects in motion are out of scope). In the style of commercial vision systems, a *job* holds the camera setup and an ordered list of *tools* (`color`, `pattern`, `code`, `detect`), each looking at a region the user draws, relative to the frame or to an *anchor* found by a *locator* (TD-19). It answers PASS / FAIL / ERROR with a reason in Portuguese. It is **not built around any product**: customer projects (e.g. Customer's packing station, box and tape) are separate projects that install Vision Station and configure jobs; they live outside this repository and are done last. Sole developer: Lucas.

Current state: platform core implemented (cameras, jobs, store, station, verification, records, API, pipeline, operator screen); tools beyond `code`, locators beyond `fixed`, management screens and the job editor are in progress. Delivery of 30/10/2026 uses the **Logitech C920 only**; the Hikvision driver comes later. Phases: 0 definition → 1 platform with the C920 → 2 model → 3 production camera (Hikvision DS-2CD3666G2T-IZS) → 4 first project on site.

Sibling project: `../vision-sim` (Bancada Virtual de Visão, project VIS, public repo). A static ES-module web simulator used to choose camera, lens, height and lighting before buying hardware. It is not a dependency of this repo, but its camera catalog (`data/cameras.csv`) and models are the reference for hardware choices. **Nothing from a customer may go into `vision-sim`**, it is public.

## Documents (read before changing design)

| File | Content |
|---|---|
| `docs/project-scope.md` | 01: what a fixed station is, in/out of scope, deliverables D1–D11, phases, risks |
| `docs/requirements-and-use-cases.md` | 02: `FR-*` / `NFR-*` requirements (MoSCoW), use cases `UC-01..10`, project values |
| `docs/architecture.md` | 03: components, the **job** model, `.vjob` / `.vbak` formats, camera abstraction, state machine, flows |
| `docs/technical-decisions.md` | 04: decisions `TD-01..20`, PC spec, network, known problems, bench tests |
| `docs/frontend.md` | 05: the web interface (React + Vite + TypeScript): design system, screens by role, API contract, editor, tests, build |

Docs cross-reference each other by ID (`FR-JOB-9`, `TD-04`, `§7.3`). Keep IDs stable; when a decision changes, update the TD record and every place that cites it.

## Design rules that must survive into code

1. **The job is the unit of configuration.** Everything affecting a result lives in the job (`.vjob` ZIP + `manifest.json` with SHA-256). Camera IP/password, backup paths and user accounts are *system configuration*, never in a job.
2. **Configuration lives on the PC, not the camera.** Apply settings on every open/reconnect/activation, then **read back** and report what did not apply.
3. **Saved job versions are immutable.** Edits create a new version; writes are atomic (temp folder/file, then rename).
4. **A job is active only after verification** (camera/view part with reference image + decision-logic part with the reference set).
5. **Never a false PASS.** PASS can only come out of the `Inspecting → ShowingResult` path; any doubt is ERROR.
6. **The camera is a plugin** behind one interface (`open/capabilities/apply/read_back/frames/snapshot/health`). Drivers: UVC (C920), Hikvision (ISAPI + RTSP/snapshot), File (tests). Inspection and job code never name a camera.
7. **Core is OS-independent**; OS-specific code only in camera drivers, service wrapper, installer.
8. **Simple for one maintainer**: one process, SQLite + files, no brokers, containers or cloud.

## Commands

```bash
uv sync              # create .venv with Python 3.12 and install deps
uv run pytest        # run the tests
(cd frontend && npm ci && npm test && npm run build)   # the React interface; after changing the API: npm run gen:api
uv sync --extra uvc  # on Windows: add duvc-ctl for the C920 driver
```

Code map: `jobs/` (job and camera profile models), `cameras/` (interface, file and UVC drivers), `tools/` (tool registry; `code`, `color`), `locators/` (locator registry; `fixed`, `template`, `blob`), `colors.py` (color ranges shared by tools and locators), `jobfiles.py` (job files a tool or locator needs, checked on load), `pipeline.py` (`inspect_job`: brightness → locator → sharpness → regions → all tools → PASS/FAIL/ERROR), `store/` (`.vjob`/`.vbak` archives and the job store), `station/` (acquisition thread, image trigger, state machine), `verification/` (job verification and activation), `api/` (FastAPI: HTTP, WebSocket, login), `records/` (results in SQLite, images, collection mode, dataset export), `results.py` (PASS/FAIL/ERROR).

Layout: `src/vision_station/` (platform, no customer words), `frontend/`, `tests/`, `scripts/`, `docs/`. No customer project lives here (no `applications/`). CI (`.github/workflows/tests.yml`) runs pytest on Windows and Linux.

## Chosen stack (TD-02..TD-18)

Python 3.12 · OpenCV headless + NumPy · duvc-ctl + DirectShow/MJPG (C920) · `requests` Digest + ISAPI (Hikvision, no SDK) · ONNX Runtime CPU (OpenVINO on Intel) · FastAPI + Uvicorn (localhost) · web UI in Edge kiosk (React + TypeScript + Vite, all of it in `frontend/`; the API serves `frontend/dist`) · SQLite · YAML + Pydantic · WinSW service · PyInstaller + Inno Setup · pytest.

**Licensing is a hard constraint (NFR-LIC-1, TD-08, TD-18):** no AGPL/GPL in the shipped product. **Never use Ultralytics/YOLOv8/11.** RF-DETR only Nano–Large (XL/2XL are not Apache). Training stack (CVAT, Supervision, Anomalib, PyTorch) stays offline and out of the install.

## Conventions

- Vocabulary (TD-19): a **tool** (not check) inspects a region; the **anchor** (not box) is what the locator finds; ROIs are relative to the `anchor` or the `frame`. No product words in platform code; examples and tests use neutral samples (a part with a blue cap and a lot label).
- Operator-facing text is **Portuguese** (e.g. "Tampa ausente ou de outra cor", "Aguardando peça"); the job supplies its own texts. Docs, code and identifiers are English.
- Reference requirement/decision IDs in code comments and commits (`TD-04`, `FR-ACQ-4`).
- Project values (time to result, accuracy, retention…) are configuration, never constants in code (document 02 §7).

