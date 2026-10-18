# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**Vision Station**: a general vision system for **industrial fixed stations and machines**, where a fixed camera looks at an object that is **stopped** for the reading (objects in motion are out of scope). In the style of commercial vision systems, a *job* holds the camera setup and an ordered list of *tools* (`color`, `pattern`, `code`, `detect`), each looking at a region the user draws, relative to the frame or to an *anchor* found by a *locator* (TD-19). It answers PASS / FAIL / ERROR with a reason in Portuguese. It is **not built around any product**: customer projects are separate projects that install Vision Station and configure jobs; they live outside this repository and are done last.

Current state: platform core implemented (cameras, jobs, store, station, verification, records, API, pipeline, operator screen); tools beyond `code`, locators beyond `fixed`, management screens and the job editor are in progress. Delivery of 30/10/2026 uses the **Logitech C920 only**; the Hikvision driver comes later. Phases: 0 definition → 1 platform with the C920 → 2 model → 3 production camera (Hikvision DS-2CD3666G2T-IZS) → 4 first project on site.

## Documents (read before changing design)

| File | Content |
|---|---|
| `docs/project-scope.md` | 01: what a fixed station is, in/out of scope, deliverables D1–D11, phases, risks |
| `docs/requirements-and-use-cases.md` | 02: `FR-*` / `NFR-*` requirements (MoSCoW + phase letter), use cases `UC-01..14`, PC tiers M/R, project values |
| `docs/architecture.md` | 03: components, the **job** model, `.vjob` / `.vbak` formats, camera abstraction, state machine, flows; new in 0.4: pose-based fixtures (§14), tool catalog and validation checklist (§15), machine interface (§16), robustness patterns (§17), refactors R0–R9 (§18), phases A–F (§19) |
| `docs/technical-decisions.md` | 04: decisions `TD-01..30`, PC tiers M/R, network, known problems, bench tests |
| `docs/frontend.md` | 05 (v0.3): the web interface (shadcn + Tailwind + React Aria, TD-29; pt-BR + en, TD-30): the order of work (§4.3), screens by role, workbench and image workspace (§10), settings levels (§17), overlays (§18), vision controls (§19), API contract, migration plan (§15) |
| `docs/integration.md` | 06: how another program uses Vision Station through the local API (inspections with an id, result and pictures, live view, allowed origins) |
| `docs/models.md` | 07: the `detect` tool, training offline, ONNX export, the model card |
| `docs/job-format.md` | 08: `.vjob`/`.vbak` format (D8) |
| `docs/reference-cognex-keyence.md` | 09: market reference, Cognex In-Sight and Keyence IV/IV3 feature by feature; §18 says what we adopt (TD-31) |
| `docs/guias/` | Portuguese guides: installation, operator, backup and restore (D10), building the installer |

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
9. **Machine outputs fail safe** (architecture §16): Pass/Fail/Error only while ResultValid; everything off on start, on any loss and between results; simulated results are never signalled.
10. **Jobs carry data, never code** (FR-PLT-12): inspection logic ships only in the program, versioned per tool type.

## Commands

```bash
uv sync              # create .venv with Python 3.12 and install deps
uv run pytest        # run the tests
uv run vision-station --data bench_data   # the program (setup: scripts/setup_bench.py, scripts/set_password.py)
(cd frontend && npm ci && npm test && npm run build)   # the React interface; after changing the API: npm run gen:api
uv sync --extra uvc  # on Windows: add duvc-ctl for the C920 driver
packaging\gerar-instalador.cmd   # Windows: program (PyInstaller) + installer (Inno Setup); docs/guias/gerar-instalador.md
```

Code map (architecture §3.3): `core/` (`results.py` PASS/FAIL/ERROR, `jobfiles.py` job files a tool or locator needs, checked on load, `schema_labels.py` Portuguese labels and the `x-level`/`x-group`/`x-unit` tags of the parameter schemas, `i18n.py` the server's texts in Portuguese and English with the catalog in `locales/`, TD-30), `jobs/` (job and camera profile models), `cameras/` (interface, file and UVC drivers), `algorithms/` (pure functions: `color.py` color ranges, `metrics.py` brightness, sharpness and similarity, `measures.py` scores and strip gaps), `geometry/` (`regions.py`: a region relative to the frame or the anchor, in pixels), `tools/` (tool registry; `code`, `color`, `pattern`, `detect`), `locators/` (locator registry; `fixed`, `template`, `blob`), `models/` (`card.py` the model card, `runtime.py` ONNX sessions, SHA-256 checked, cached), `pipeline/` (`inspect_job`: brightness → locator → sharpness → regions → all tools → PASS/FAIL/ERROR; `quality.py` gates, `overlay.py` the drawn result), `store/` (`.vjob`/`.vbak` archives and the job store), `station/` (acquisition thread, image trigger, state machine), `verification/` (job verification and activation), `api/` (FastAPI: HTTP, WebSocket, login), `records/` (results in SQLite, images, collection mode, dataset export), `system/` (`system.yaml`, applying settings, scheduled backup and housekeeping, camera and folder checks), `runtime.py` (the `vision-station` entry point that wires everything).

Layout: `src/vision_station/` (platform, no customer words), `frontend/`, `tests/`, `scripts/`, `docs/`. No customer project lives here (no `applications/`). CI (`.github/workflows/tests.yml`) runs pytest on Windows and Linux.

## Chosen stack (TD-02..TD-18)

Python 3.12 · OpenCV headless + NumPy · duvc-ctl + DirectShow/MJPG (C920) · `requests` Digest + ISAPI (Hikvision, no SDK) · ONNX Runtime CPU (OpenVINO on Intel) · FastAPI + Uvicorn (localhost) · web UI in Edge kiosk (React + TypeScript + Vite, shadcn/ui on Radix + Tailwind, **React Aria** for colour/range/number controls (TD-29), **Lingui** pt-BR + en (TD-30); all of it in `frontend/`; the API serves `frontend/dist`) · SQLite · YAML + Pydantic · WinSW service · PyInstaller + Inno Setup · pytest.

**Licensing is a hard constraint (NFR-LIC-1, TD-08, TD-18):** no AGPL/GPL in the shipped product. **Never use Ultralytics/YOLOv8/11.** RF-DETR only Nano–Large (XL/2XL are not Apache). Training stack (CVAT, Supervision, Anomalib, PyTorch) stays offline and out of the install.

## Conventions

- Vocabulary (TD-19, TD-21): a **tool** (not check) inspects a region; a **locator** finds a **fixture** with a **pose** (x, y, angle, scale); ROIs are relative to a fixture or to the `frame`. In format-1 jobs the only fixture is called `anchor`. No product words in platform code; examples and tests use neutral samples (a part with a blue cap and a lot label).
- Interface text is **Portuguese and English** (TD-30): Lingui catalogs in `frontend/` (source pt-BR), PO catalogs on the server; the operator screen uses the station language. Jobs supply their own texts in both languages (format 2). Docs, code and identifiers are English.
- Reference requirement/decision IDs in code comments and commits (`TD-04`, `FR-ACQ-4`).
- Project values (time to result, accuracy, retention…) are configuration, never constants in code (document 02 §7).
