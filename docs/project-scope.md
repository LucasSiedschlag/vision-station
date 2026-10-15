# Vision Station — Project Scope

| | |
|---|---|
| Document | 01 — Project Scope |
| Version | 0.2 |
| Date | 2026-10-15 |
| Author | Lucas (developer and maintainer) |
| Status | Platform scope (TD-19) |

Related documents: 02 — Requirements and Use Cases · 03 — Architecture ("job" model) · 04 — Technical Decisions · 05 — Frontend · Bancada Virtual de Visão (simulator).

> **Platform, not application.** Vision Station is a general vision system for **fixed stations**. It is not built around one product. Each customer project (for example a packing station that checks boxes and tape) is a separate project that **uses** Vision Station: it installs the software, configures jobs with the platform's tools, and keeps its own jobs, reference images, acceptance data and customer context in its own place, never in this repository.

---

## 1. Purpose

Define what Vision Station does and does not do, what it delivers and under which assumptions. It is the reference for every project that uses it.

## 2. What a fixed station is

- A **fixed camera** looks at an object that is **stopped** while it is inspected: a part on a jig, a product on a bench or scale, a label on a stopped package, a machine that pauses for the reading.
- The object does not move during the capture. Stations where the object moves past the camera (conveyors at speed, web inspection, tracking) are **not** in scope: they need hardware trigger, global shutter and encoder timing that this design does not plan for.
- The camera, its mount and the lighting stay in place between inspections, so a job's settings and reference image keep their meaning.

## 3. Objectives

1. Inspect an object at a fixed station and give a clear **PASS / FAIL / ERROR** with a reason in Portuguese, never a false PASS.
2. Be configured, not programmed: a **job** holds the camera settings and an ordered list of **tools** (`color`, `pattern`, `code`, `detect`), each looking at a region the user draws, relative to the frame or to an **anchor** found by a **locator**.
3. Keep every setting that affects a result in the job; export a job or a full backup to a **single file**; restore it on a replacement PC or camera and **verify automatically** that it behaves the same.
4. Treat the camera as a plugin: a USB webcam (Logitech C920) now, a Hikvision IP camera and others later, with no change to jobs or inspection code.
5. Run on an ordinary Windows 11 PC, CPU only, as a service with a local web screen.
6. Stay simple enough for one maintainer.

## 4. In scope

### 4.1 Platform software
- Acquisition from camera plugins (UVC for the C920 now; Hikvision ISAPI + RTSP/snapshot later; a file camera for tests), with settings applied and read back on every open, reconnect and activation.
- Triggers for a still object: image presence + stillness, manual, external signal, continuous.
- Inspection pipeline: image quality gate, locator, regions, tools, `all_pass` decision, reason text.
- Tools by type, each a versioned module: `color`, `pattern`, `code`, `detect` (trained model, ONNX).
- Jobs: create, edit (from the screen), version, export/import `.vjob`, full backup `.vbak`, verification before activation.
- Operator screen (live image, result, reason, overlay, counters), Supervisor and Maintainer screens (jobs, results, settings, users, audit), all in Portuguese.
- Results and images in a local store; collection mode and dataset export for training.
- Installer, Windows service, installation and operation guides.

### 4.2 Hardware guidance (not purchase)
- How to choose camera, lens, height and lighting, using the simulator (Bancada Virtual de Visão) and a bench test.
- Minimum PC specification.

### 4.3 Model tooling
- A documented, offline path to label images, train, validate and export a model that a `detect` tool runs.

## 5. Out of scope

- Objects in motion during capture (see §2).
- Several cameras or stations in one installation (a station = one camera; more stations = more installations).
- Product-specific logic in the platform: words such as "caixa" or "fita" never appear in platform code, only in a project's jobs and texts.
- Customer projects themselves: their jobs, reference images, acceptance tests and context live in each project, outside this repository.
- PLC/MES programming, reject devices, mechanics and electrical work (the platform exposes results; integration belongs to the project).
- Cloud services and remote dashboards.

## 6. Deliverables

| # | Deliverable | Form |
|---|---|---|
| D1 | Project scope (this document) | Markdown |
| D2 | Requirements and use cases | Markdown |
| D3 | Architecture ("job" model) | Markdown |
| D4 | Technical decisions | Markdown |
| D5 | Simulator (Bancada Virtual de Visão) | Web page, separate public project |
| D6 | Platform software with the C920 driver | Installable application |
| D7 | Hikvision driver | Module of the application |
| D8 | Job file format specification | Markdown |
| D9 | Model tooling (training and export guide) | Markdown + scripts |
| D10 | Installation guide, operator guide, backup/restore procedure | Markdown / PDF |
| D11 | Web interface specification | Markdown (document 05) |

## 7. Phases

| Phase | Goal | Exit criteria |
|---|---|---|
| 0 — Definition | Scope, requirements, architecture, decisions | Documents D1–D5 written |
| 1 — Platform with the C920 | Acquisition, triggers, pipeline, tools, jobs, verification, screens, records | A job made on the screen, exported, restored on another PC and verified; PASS/FAIL live on the bench |
| 2 — Model | `detect` tool and the offline training path | A model trained offline runs in a job and passes its reference set |
| 3 — Production camera | Hikvision driver | The same job runs on the Hikvision after re-verification |
| 4 — First project on site | A customer project configured with the platform | That project's acceptance (owned by the project) |

The first delivery (30/10/2026) is phase 1 complete, with the C920.

## 8. Roles

| Who | Role |
|---|---|
| Operator | Presents the object at the station and reads the result. No technical training. |
| Supervisor | Selects the active job, reviews results, keeps backups. |
| Maintainer | Creates and tunes jobs, installs updates, trains models. |
| Project | A customer project that uses Vision Station: owns its jobs, acceptance numbers and customer context. |

## 9. Assumptions

- Camera and mount are fixed; the object is presented in a repeatable area and is still when captured.
- Light can vary (windows, ceiling lamps); dedicated, diffuse light is recommended and each job fixes exposure and gain.
- The PC runs Windows 11 (64-bit); the core also runs on Linux for development and tests.
- IP cameras are on wired Ethernet.

## 10. Constraints

- **Licensing:** only permissive licenses ship (MIT, BSD, Apache 2.0); no AGPL/GPL (NFR-LIC-1, TD-08, TD-18).
- **Operating system:** the people at the stations know Windows.
- **Hardware in Brazil:** Hikvision is the IP camera because alternatives are hard to find locally.
- **Team:** one developer; one process, SQLite and files, no brokers, containers or cloud.

## 11. Acceptance of the platform

1. A tool type can be added without changing the job manager, the station controller, the API or the screen (FR-PLT-2).
2. Every image that cannot be inspected with confidence gives ERROR, never PASS (FR-INS-6), shown by tests with damaged, dark, blurred and empty images.
3. A job exported from one installation and imported on a fresh one gives the same results on its reference set (NFR-REL-5).
4. The station runs unattended for a shift and recovers by itself from a camera loss and a PC restart (NFR-REL-1..3).
5. An operator reads the result and the reason without training beyond 15 minutes (NFR-USA-1).

Each project adds its own numbers (detection rate, false rejects, time to result) to its own acceptance.

## 12. Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| Webcam settings (focus, exposure) reset or are ignored | Unstable images | Apply and read back on every open; C920 only until the IP camera; documented limits (TD-19) |
| Light changes during the day | Results vary by time of day | Fixed exposure and gain per job; quality gate; dedicated light recommended |
| Platform over-built without real use | Time lost | A tool is built when a project needs it; `code` is the exception (cheap, testable without hardware) |
| Region editor on the screen is a large item | Late delivery | Jobs are also editable as files; the editor grows by steps |
| Few real failure images for models | Weak `detect` | Classical tools first; anomaly models trained on good images only |
| IP camera stream drops or lags | Missed results | Wired network, reconnection, snapshot on trigger |
| Model licensing | Legal exposure | Permissive models only (TD-08) |
