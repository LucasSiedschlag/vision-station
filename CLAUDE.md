# CLAUDE.md


## What this is

**Vision Station**: a general inspection platform for a **fixed station** (a fixed camera that identifies objects, colors or codes), in the style of commercial vision systems: a *job* holds the camera setup and an ordered list of *tools* (`color`, `pattern`, `code`, `detect`), each looking at a region the user draws (TD-19). The first application, for Customer, checks that each box leaves the scale **closed and taped** (red tape, or transparent tape with a printed logo; sizes P, M, G, GG), giving PASS / FAIL / ERROR with a reason in Portuguese. The platform is the base; the application sits on top of it, never the other way round. Sole developer: Lucas.

Current state: **design done; code just started** (`src/vision_station/` is a skeleton). Delivery of 30/10/2026 (implemented and validated) uses the **Logitech C920 only**; the Hikvision driver, ISAPI work and the trained model are postponed. The repository holds only the four design documents in `docs/`. Phases: 0 definition → 1 prototype (Logitech C920) → 2 model → 3 production camera (Hikvision DS-2CD3666G2T-IZS) → 4 acceptance.

Sibling project: `../vision-sim` (Bancada Virtual de Visão, project VIS, public repo). A static ES-module web simulator used to choose camera, lens, height and lighting before buying hardware. It is not a dependency of this repo, but its camera catalog (`data/cameras.csv`) and models are the reference for hardware choices. **Nothing from the client may go into `vision-sim`**, it is public.

## Documents (read before changing design)

| File | Content |
|---|---|
| `docs/project-scope.md` | 01: purpose, in/out of scope, deliverables D1–D10, phases, risks, open client questions |
| `docs/requirements-and-use-cases.md` | 02: `FR-*` / `NFR-*` requirements (MoSCoW), use cases `UC-01..10`, values to agree with the client |
| `docs/architecture.md` | 03: components, the **job** model, `.vjob` / `.vbak` formats, camera abstraction, state machine, flows |
| `docs/technical-decisions.md` | 04: decisions `TD-01..18`, PC spec, network, known problems, bench tests |

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
uv sync --extra uvc  # on Windows: add duvc-ctl for the C920 driver
```

Layout: `src/vision_station/` (platform, no customer words), `applications/<name>/` (jobs, reference images and notes of one application; first: `Customer`), `tests/`, `docs/`. CI (`.github/workflows/tests.yml`) runs pytest on Windows and Linux.

## Chosen stack (TD-02..TD-18)

Python 3.12 · OpenCV headless + NumPy · duvc-ctl + DirectShow/MJPG (C920) · `requests` Digest + ISAPI (Hikvision, no SDK) · ONNX Runtime CPU (OpenVINO on Intel) · FastAPI + Uvicorn (localhost) · local web UI in Edge kiosk (plain HTML/CSS/JS, no build step) · SQLite · YAML + Pydantic · WinSW service · PyInstaller + Inno Setup · pytest.

**Licensing is a hard constraint (NFR-LIC-1, TD-08, TD-18):** no AGPL/GPL in the shipped product. **Never use Ultralytics/YOLOv8/11.** RF-DETR only Nano–Large (XL/2XL are not Apache). Training stack (CVAT, Supervision, Anomalib, PyTorch) stays offline and out of the install.

## Conventions

- Vocabulary (TD-19): a **tool** (not check) inspects a region; the **anchor** (not box) is what the locator finds; ROIs are relative to the `anchor` or the `frame`. Product words stay in `applications/` and in examples.
- Operator-facing text is **Portuguese** (e.g. "Fita ausente em 40% da emenda", "Aguardando caixa"). Docs, code and identifiers are English.
- Reference requirement/decision IDs in code comments and commits (`TD-04`, `FR-ACQ-4`).
- Values marked **TBD** in the docs are waiting for the client; do not invent them in code, make them configuration.

