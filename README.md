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
| 04 | [Technical decisions](docs/technical-decisions.md) | Decisions TD-01..18, PC spec, network, known problems, bench tests |

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
