# Vision Station

Packaging vision system. At the packing station, each box is placed on a scale in a fixed position. A fixed camera checks that the box leaves **closed and taped** and shows **PASS / FAIL / ERROR** with the reason (in Portuguese) on the operator screen.

> **Status:** design phase. The first delivery (30/10/2026) runs with the Logitech C920; the Hikvision camera comes later. This repository currently contains the design documents only; there is no code yet.

## What it will do

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
