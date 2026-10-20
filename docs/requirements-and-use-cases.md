# Vision Station — Requirements and Use Cases

| | |
|---|---|
| Document | 02 — Functional Requirements, Non-Functional Requirements and Use Cases |
| Version | 0.8 — no migrator while nothing is deployed (FR-JOB-13 suspended, FR-JOB-16 is format 3). 0.7 — the job's acquisition block and the two layers, job and station (document 09 v0.3, TD-32): FR-TRG-8, FR-ACQ-10/11, FR-INT-17, FR-JOB-16 new; FR-PLT-3, FR-TRG-6/7, FR-INT-6, FR-UI-11 changed. 0.6 — trigger timing and remote I/O outputs from the market reference (document 09, TD-31): FR-TRG-6/7, FR-INT-14..16, FR-LOG-9 new; FR-INT-6 changed. 0.5 — interface in Portuguese and English (FR-UI-5, FR-INS-7 changed; FR-JOB-15 new; TD-30). 0.4 — interface requirements of document 05 v0.2 (FR-UI-9..14, FR-JOB-14, FR-ADM-8). 0.3 — robust core, machine connectors, minimum tool set, CPU-only PC tiers |
| Date | 2026-10-18 |
| Author | Lucas (developer and maintainer) |
| Status | Platform requirements (TD-19). New and changed items are marked **(new 0.3)** / **(changed 0.3)**. |

> **Platform requirements (TD-19).** These are the requirements of Vision Station, a vision system for **fixed stations** where the object is **still** while it is inspected. Customer projects that use the platform write their own requirements (what to inspect, accuracy, time to result) and meet them with jobs; they are not listed here. Examples in this document (a label, a part on a jig, a closed package) only illustrate.

Related documents: 01 — Project Scope · 03 — Architecture ("job" model) · 04 — Technical Decisions · 06 — Integration.

**What changed in 0.3.** Research on commercial and open vision systems (project documents 05 and 06) and a review of the code led to requirements for: object placement with **rotation** (pose-based fixtures), **stable error and reason codes**, a **fail-safe machine interface** (Siemens S7, Modbus TCP, OPC UA, 24 V I/O), a **minimum tool set** and a definition of a **validated tool**, **on-station teaching** from good parts, operations aids (challenge test, margin warnings, A/B replay), and **two CPU-only PC tiers** with measured performance. Existing IDs are unchanged; new IDs continue each area's numbering.

---

## 1. Conventions

- **IDs:** `FR-<area>-<n>` for functional requirements, `NFR-<area>-<n>` for non-functional requirements, `UC-<n>` for use cases.
- **Priority (MoSCoW):**
  - **M** = Must: required for acceptance.
  - **S** = Should: expected, but can move to a later phase.
  - **C** = Could: only if time allows.
  - **W** = Won't (this version): recorded so it isn't forgotten.
- **Phase:** a letter in parentheses after the priority, e.g. **M (B)**, is the phase of document 03 §19 that delivers the requirement (A robust core · B machine · C minimum tool set · D operations · E standards and models · F industrial cameras). No letter: delivered by the first delivery (phase 1 of document 01) or already implemented. A Must with a phase letter is required for the acceptance of that phase.
- **Project value:** a number that each project that uses the platform sets for itself (time to result, accuracy). The platform makes it configuration and measures it; section 7 lists them.
- **Proposed:** a default value suggested by the developer. Performance values marked proposed become binding only after the benchmark B-1 on real units (document 04, TD-28).
- **Glossary:**
  - **Job:** the full set of settings for inspecting one product or variant at one station: camera settings, trigger, fixtures, regions, tools, thresholds, models and reference images.
  - **Job file:** a single file containing one job, used for backup and restore.
  - **Backup file:** a single file containing all jobs plus the system settings.
  - **Trigger:** the event that starts one inspection.
  - **ROI:** region of interest, the part of the image a tool looks at.
  - **Tool:** a versioned inspection step of one type (`color`, `pattern`, `code`, `detect`, …) that looks at one ROI and returns pass/fail, a score and named values.
  - **Locator / fixture / pose:** a locator finds something in the image (the object, a label on it) and gives a **fixture**: its position, angle and scale (**pose**). ROIs are drawn relative to a fixture, so they follow the object when it is placed shifted or turned. The format-1 word **anchor** is a fixture without angle.
  - **Fixed station:** a fixed camera and an object that is still during the capture (on a jig, bench, scale or a stopped machine).
  - **Machine interface:** the set of signals (trigger, ready, result valid, pass/fail/error, codes…) exchanged with a PLC or I/O module, the same for every protocol.
  - **Interface map:** the versioned list and layout of those signals (document 03 §16.2).
  - **Tier M / tier R:** the minimum and recommended PC classes, both without a dedicated GPU (NFR-PERF-5).
  - **Challenge test:** presenting known good and known bad master parts to prove the station still detects a defect.
  - **Margin:** how far a tool's measure is from its threshold, relative to the threshold.
  - **Simulated result:** a result from stored images (file camera, editor test, replay, benchmark), never a real inspection.

## 2. Actors

| Actor | Description |
|---|---|
| Operator | Presents the object at the station and reads the result. No technical training. |
| Supervisor | Selects the active job, reviews failures, keeps the backup file, runs the challenge test. |
| Maintainer | Creates and tunes jobs, installs updates, trains models, configures machine connectors. |
| Machine (PLC) | Optional. Triggers inspections, selects jobs and reads results through the machine interface (Siemens S7, Modbus TCP, OPC UA). **(changed 0.3)** |
| Remote I/O module | Optional. 24 V digital inputs and outputs on Modbus TCP: trigger input, lamps, rejector. **(new 0.3)** |
| Other program | Optional. A program on the same PC that uses Vision Station through the local API (document 06). |
| Camera | A camera plugin: C920 (USB) now, Hikvision IP camera later, GenICam cameras if a project needs them. |

---

## 3. Functional requirements

### 3.1 Acquisition (ACQ)

| ID | Requirement | Priority |
|---|---|---|
| FR-ACQ-1 | The system shall acquire images from a USB UVC camera (first: Logitech C920). | M |
| FR-ACQ-2 | The system shall acquire images from a Hikvision IP camera, by RTSP stream and/or HTTP snapshot. | S (after the first delivery) |
| FR-ACQ-3 | The camera type and its connection data shall be selected by configuration, without changing code. | M |
| FR-ACQ-4 | On startup and on every job load, the system shall apply the job's camera settings (exposure, gain, white balance, focus, resolution, format), then read each one back and report any that did not apply. | M |
| FR-ACQ-5 | The system shall detect when the camera disconnects or the stream stops, show the problem to the operator, and reconnect automatically. After reconnecting, it shall reapply the camera settings. | M |
| FR-ACQ-6 | Each inspection shall use a frame captured after the trigger, never one buffered from before it. | M |
| FR-ACQ-7 | The system shall measure image sharpness and brightness on each inspection frame and compare them with the job's reference image. | S |
| FR-ACQ-8 | For the motorized lens, the system shall store the zoom and focus position in the job and restore it. | S |
| FR-ACQ-9 | **(new 0.3)** The system shall support GenICam cameras (GigE Vision / USB3 Vision) through a GenTL producer, with hardware trigger and an exposure-end event, behind the same camera interface. | C (F) |
| FR-ACQ-10 | **(new 0.7)** A job shall set the image **orientation** — normal, mirrored, flipped or rotated 180° — applied at acquisition, so that every region and result is in the oriented frame (Cognex `AcquireImage` *Orientation*). | S |
| FR-ACQ-11 | **(new 0.7, built in VIA-0083)** The editor's *Auto uma vez* shall measure the exposure once, with the station paused: it searches the exposure until a **target percentage of the pixels** of a **measuring region** are saturated (default 10 %, the whole picture), never going over a **maximum exposure**, and leaves the camera on the result. These three parameters are the job's (`exposure.auto_once`). A camera with coarse steps (the C920 has factor-of-two steps) takes the nearest step, so the result is the step closest to the target, and the editor says so. The job then runs with the **fixed value** it measured; automatic exposure that follows each image is not offered (principles 1 and 2). | C |

### 3.2 Trigger (TRG)

| ID | Requirement | Priority |
|---|---|---|
| FR-TRG-1 | The system shall start an inspection automatically when an object is present and still in the trigger area, detected from the image (presence + no motion for a configurable time). | M |
| FR-TRG-2 | **(changed 0.3)** The system shall accept an external trigger (a machine ready signal, a sensor, a scale's "weight stable") through the machine interface (FR-INT-3) or a remote I/O input (FR-INT-6). | S (B) |
| FR-TRG-3 | The operator shall be able to trigger an inspection manually from the screen. | M |
| FR-TRG-4 | The system shall inspect each object exactly once until it leaves the area. It shall not re-trigger while the same object stays in place. | M |
| FR-TRG-5 | In `continuous` mode the system shall inspect still frames one after another with no trigger (for example a code reader at a station), and still never inspect a frame taken while the scene moves. | C |
| FR-TRG-6 | **(new 0.6, changed 0.7)** In the `external` trigger type a job may set (`acquisition.trigger.external.delay_ms`) a **trigger delay** of 0–1000 ms (default 0) between the accepted trigger and the frame used for the inspection, for machines whose signal comes before the object has settled. The delay is per job (TD-31). | S (B) |
| FR-TRG-7 | **(new 0.6, changed 0.7)** In the `continuous` trigger type a job shall set (`acquisition.trigger.continuous.interval_ms`) a **minimum interval** between inspections (default 500 ms; 0 = as fast as the PC allows). FR-TRG-5 still applies: a frame taken while the scene moves is never inspected. | C |
| FR-TRG-8 | **(new 0.7)** In the `external` trigger type a job shall set a **debounce**, 0–65 ms (default 0): the least time the trigger input stays active before it counts, as in Cognex *Trigger Debounce*. It is a job setting (`acquisition.trigger.external.debounce_ms`); the edge of the input is station configuration (FR-INT-17). | S (B) |

### 3.3 Inspection (INS)

| ID | Requirement | Priority |
|---|---|---|
| FR-INS-1 | **(changed 0.3)** Each inspection shall run the active job's pipeline: image quality gate → fixtures (locators, in order) → regions → every tool in order → decision. | M |
| FR-INS-2 | The `color` tool shall measure the fraction of a region inside a color range, or the distance to a reference color, against a threshold, inside a validation area the user draws. | M |
| FR-INS-3 | The `pattern` tool shall find a taught template in a region, and count its repeats along a line, against a minimum count or coverage. | M |
| FR-INS-4 | Tools shall only look at the job's ROIs, so things outside them (people, other objects) do not affect the result. | M |
| FR-INS-5 | A job shall be able to combine classical tools and trained models. Each tool returns pass/fail plus a score. | M |
| FR-INS-6 | **(changed 0.3)** The final result shall be **PASS**, **FAIL** or **ERROR**. ERROR means the system could not inspect: object not found, object outside the allowed position or angle, image too dark, too bright, flat or out of focus, region outside the image, a tool that broke, camera lost. ERROR shall never be shown or signalled as PASS. | M |
| FR-INS-7 | **(changed 0.5)** Every FAIL and ERROR shall carry a human-readable reason in the language of the screen showing it (pt-BR or en, FR-UI-5). FAIL reasons come from the job (each tool's `reason_fail`), and list every tool that failed. | M |
| FR-INS-8 | **(changed 0.3)** The system shall locate the object in the image and place the ROIs relative to it, tolerating the placement variation the job allows (NFR-ACC-4). | S |
| FR-INS-9 | Variants of a product (sizes, colors) shall be handled as separate jobs or as one job whose tools cover them, without platform changes. | M |
| FR-INS-10 | The `code` tool shall read 1D bar codes, QR and Data Matrix in a region and optionally compare the text with an expected value or pattern. | M |
| FR-INS-11 | **(new 0.3)** A locator shall return a **pose** (position, angle, scale). ROIs relative to a fixture shall follow its rotation and scale, and tools shall receive the region as an upright image. Each fixture shall state its allowed angle and scale range; a pose outside it is ERROR, not FAIL. | M (A) |
| FR-INS-12 | **(new 0.3)** A job shall be able to use several fixtures, each searched in the frame or inside a previous fixture (e.g. a label inside a part). | S (A) |
| FR-INS-13 | **(new 0.3)** Each tool shall be marked as affecting the result or as informative. Informative tools are run and recorded but never decide the outcome. | S |
| FR-INS-14 | **(new 0.3)** Every ERROR shall carry a stable numeric code from a documented catalog, and every failing tool a stable reason code (`<tool type>.<criterion>`), in addition to the Portuguese text. Codes keep their meaning across software versions. | M |
| FR-INS-15 | **(new 0.3)** A job may hold a calibration (millimetres per pixel). Measurement tools shall then report and judge in millimetres. A job with millimetre thresholds and no calibration shall be refused on load. | S (C) |
| FR-INS-16 | **(new 0.3)** A job may name a color-reference patch (e.g. a white target fixed in the field of view) with a drift limit. A drift beyond the limit shall give ERROR, so a lighting change is never judged as a product defect. | S (C) |

### 3.4 Jobs (JOB)

| ID | Requirement | Priority |
|---|---|---|
| FR-JOB-1 | The system shall keep any number of jobs. Exactly one job is active at a time. | M |
| FR-JOB-2 | A job shall contain everything needed to reproduce the inspection: camera settings, ROIs, tools and thresholds, model file, reference images, metadata (name, version, author, date, description). | M |
| FR-JOB-3 | The Supervisor shall be able to select the active job from a list. | M |
| FR-JOB-4 | The Maintainer shall be able to create a job, duplicate it, edit it and delete it. | M |
| FR-JOB-5 | Saving changes to a job shall create a new job version. Previous versions shall be kept and can be restored. | S |
| FR-JOB-6 | A job shall be exportable as a **single file**. | M |
| FR-JOB-7 | All jobs plus the system settings shall be exportable as a **single backup file**. | M |
| FR-JOB-8 | Import shall check the file's integrity (checksums, format version) and refuse a damaged or incompatible file with a clear message. | M |
| FR-JOB-9 | After import or restore, the system shall run a **verification**: apply camera settings, read them back, capture a frame, compare it with the reference image, and run the tools on the stored reference images. The job only becomes active if verification passes, or if the Maintainer explicitly overrides it. | M |
| FR-JOB-10 | The system shall make an automatic backup on a schedule (proposed: daily) and every time a job changes, to a configurable folder (e.g. a network share or USB drive). It shall keep the last N backups (proposed: 30). | S |
| FR-JOB-11 | A job created for one camera type shall be importable on the other camera type. Camera settings that do not apply shall be flagged for review rather than silently ignored. | C |
| FR-JOB-12 | **(new 0.3)** Before a new version of an active job is activated, the Maintainer shall be able to replay it on recorded frames of the previous version and see which outcomes and scores would change. Replayed results are simulated and not recorded as inspections. | S (D) |
| FR-JOB-13 | **(new 0.3, suspended 0.8)** Jobs in format 1 shall be migrated to format 2 on import or first load, as a new copy, giving the same results on their reference sets. *Suspended on 2026-10-20: nothing is deployed, so a format is forced and an older file is refused with a clear message; it comes back when a station is installed.* | M (A) |
| FR-JOB-14 | **(new 0.4)** The Supervisor shall be able to change a job's tolerance limits only (parameters marked tunable), creating a new version that is verified before activation and recorded in the audit log. The server shall refuse any other change made through this path (document 05 §7.12). | S |
| FR-JOB-15 | **(new 0.5)** Texts written in a job (failure reasons, waiting text, sample notes) shall hold both languages (job format 2). A missing translation falls back to the other language and is flagged when the job is validated; format-1 texts are read as Portuguese. | M (A) |
| FR-JOB-16 | **(new 0.7)** The acquisition block of a job (trigger type with its parameters, image settings, calibration) shall be written in full in every saved version, and a job whose block lacks a parameter shall be refused. A change of a default in the software shall never change the behaviour of a saved version; the block is job format 3 and is forced, with no migrator while nothing is deployed (TD-32). | M |

### 3.5 Operator screen (UI)

| ID | Requirement | Priority |
|---|---|---|
| FR-UI-1 | The screen shall show the live image, the active job and the last result in large, colour-coded form (green PASS, red FAIL, yellow ERROR). | M |
| FR-UI-2 | On FAIL, the screen shall show the reason and highlight on the image where the problem is. | M |
| FR-UI-3 | The screen shall show the system state: camera connected, job verified, waiting (with the job's own text), inspecting. | M |
| FR-UI-4 | The screen shall show counters for the current shift: total, pass, fail, error. | S |
| FR-UI-5 | **(changed 0.5)** The interface shall be available in Portuguese (pt-BR) and English (en). The operator screen uses the station language (system configuration); each logged-in user may choose theirs. Numbers and dates follow the language's format (TD-30, document 05 §11). | M |
| FR-UI-6 | Job editing, export, import and settings shall be hidden from the Operator and need a Supervisor or Maintainer login. | M |
| FR-UI-7 | The system shall give an audible alert on FAIL. | C |
| FR-UI-8 | **(new 0.3)** The screen shall show the machine-interface status when one is enabled: connected, heartbeat, the last trigger source, and the job number. | S (B) |
| FR-UI-9 | **(new 0.4)** The image overlays (regions, anchors, measurements, labels, masks) shall be switchable on and off, as a whole and per layer, on the operator screen and in the editor. A station setting sets the operator default and whether the operator may switch them. Turning them off never hides the verdict or the reason (document 05 §18). | M |
| FR-UI-10 | **(new 0.4)** Configuration screens shall show settings at three levels — Essencial, Avançado, Especialista. A level changes what is shown, never what is allowed or any value; a section that hides changed values shall say so (document 05 §17). | M |
| FR-UI-11 | **(new 0.4, changed 0.7)** Configuration shall follow the order of work: commissioning (camera, performance, passwords, machine, backup) once per installation; per job: image and trigger → samples → anchor → tools → quality → result and outputs → validate → save (TD-32). Each step shows its state and what it needs; steps can be visited in any order (document 05 §4.3). | M |
| FR-UI-12 | **(new 0.4)** While a job is edited, every change shall be applied to the next captured frame (or to the frozen image) and its effect shown — measured values, gauges, masks, overlays, verdict and time — at a rate the PC allows (document 05 §19.1). | M |
| FR-UI-13 | **(new 0.4)** Every tolerance shall be adjustable on a gauge that shows the current measurement, the samples' values and the allowed band, with a number field for precision; colours shall be chosen by sampling the image, with the range shown on colour bars and as a mask on the image (document 05 §19.3–19.4). | M |
| FR-UI-14 | **(new 0.4)** The system shall propose tolerance limits from samples labelled good and bad, show the resulting margin or that the samples overlap, and apply them only when the user confirms. | S |

### 3.6 Results and records (LOG)

| ID | Requirement | Priority |
|---|---|---|
| FR-LOG-1 | Every inspection shall be recorded with: timestamp, job name and version, result, reason, per-tool scores, and the inspection image. | M |
| FR-LOG-2 | Images shall be kept for all FAIL and ERROR results. A configurable sample of PASS images shall also be kept (proposed: 1 in 20). | M |
| FR-LOG-3 | Records older than the configured retention period shall be deleted automatically. When the disk drops below a free-space threshold, the oldest PASS images shall be deleted first. | M |
| FR-LOG-4 | The Supervisor shall be able to browse and filter results by date, job and result, and export them to CSV. | S |
| FR-LOG-5 | **(changed 0.3)** The system shall keep an audit log of job changes, imports, exports, overrides and logins, and of job changes requested by the machine. | S |
| FR-LOG-6 | **(changed 0.3)** Records shall be linkable to an order or batch number, when a project provides one (the machine's part id, or the API's reference). | C |
| FR-LOG-7 | **(new 0.3)** The system shall track, per job version and tool, the margin of PASS results over a rolling window and warn the Supervisor when it falls below a configured limit. | S (D) |
| FR-LOG-8 | **(new 0.3)** Records shall store the result contract (document 03 §10.3): sequence, trigger source, error code, reason codes, per-tool values with units, fixture poses, stage timings and the simulated flag. | M |
| FR-LOG-9 | **(new 0.6)** In addition to the sample of FR-LOG-2, the image of every PASS whose margin on any deciding tool is below **twice the margin warning limit** of FR-LOG-7 (default: below 0.10) shall be kept. Under disk pressure these images are deleted after the sampled PASS images and before FAIL and ERROR images. | S (D) |

### 3.7 Integration (INT)

| ID | Requirement | Priority |
|---|---|---|
| FR-INT-1 | The system shall let another program on the same PC request an inspection, follow it by id and get its result and pictures, the system state and the live view, through a documented local interface (HTTP/JSON and WebSocket; document 06). | M |
| FR-INT-2 | **(changed 0.3)** The system shall signal the result to an external device (PLC, digital output, tower light, rejector) through the machine connectors FR-INT-3..7. Project-specific integrations stay outside the platform. | S (B) |
| FR-INT-3 | **(new 0.3)** The system shall offer one machine interface — trigger, ready, acknowledge, acquisition done, result valid, pass/fail/error, error code, reason code, sequence, job number, heartbeats, user values — defined once as a versioned interface map and carried unchanged by every connector. | M (B) |
| FR-INT-4 | **(new 0.3)** The system shall connect to Siemens S7-1200 and S7-1500 PLCs as a client of an interface data block. | M (B) |
| FR-INT-5 | **(new 0.3)** The system shall act as a Modbus TCP server holding the interface map, for any PLC or HMI acting as client. | M (B) |
| FR-INT-6 | **(changed 0.7)** The system shall drive 24 V digital I/O through a Modbus TCP remote I/O module: inputs with a function and an edge (FR-INT-17) — the trigger and a clear-error input — and assignable outputs — ready, pass, fail, error, busy, online, job change done / failed, trigger refused (FR-INT-14) and reject (FR-INT-15) — plus a tower light. | S (B) |
| FR-INT-7 | **(new 0.3)** The system shall expose an OPC UA server following OPC 40100-1, targeting the *Simple Inline Vision System* profile: state machine, jobs as recipes, products, `StartSingleJob`, results by event with a typed result content. | S (E) |
| FR-INT-8 | **(new 0.3)** The machine shall be able to select the active job by number (and, on OPC UA, by product). Numbers and products are mapped to jobs in the system configuration, not in the jobs. The new job becomes active only after verification; a failure is signalled, and the station stays out of Ready. | M (B) |
| FR-INT-9 | **(new 0.3)** Results shall be held valid until the machine acknowledges them (acknowledge mode) or until the next trigger (no-acknowledge mode). In acknowledge mode, unacknowledged results shall be buffered up to a configured depth and an overrun flagged. | M (B) |
| FR-INT-10 | **(new 0.3)** The system shall signal "acquisition done" as soon as the inspection frame is taken, before the result, so the machine can move the object. | M (B) |
| FR-INT-11 | **(new 0.3)** A job may publish up to 8 numeric tool values (with units) to the machine interface, chosen in the job. | S (B) |
| FR-INT-12 | **(new 0.3)** Simulated results (file camera, editor test, replay, benchmark) shall be flagged and shall never be signalled to a machine as a result. | M (B) |
| FR-INT-13 | **(new 0.3)** The platform shall ship, for Siemens, a ready interface data block and a function block that implements the PLC side of the handshake and the heartbeat check (deliverable D12). | S (B) |
| FR-INT-14 | **(new 0.6)** Every refused trigger (`TriggerRefused`, document 03 §16.2) shall be counted per job, shift and day in the statistics, and shall be assignable as a pulse on a remote I/O output. | S (B) |
| FR-INT-15 | **(new 0.6)** A remote I/O output may act as a **delayed reject**: it fires for FAIL and ERROR results (each configurable; both by default) either **N inspections** after the one that failed or **T ms** after its trigger, as a pulse of 10–1000 ms (default 100 ms). Pending rejects are held in a queue; on stop, job change or restart the queue is cleared, the loss is logged, and the machine sees Error until it is acknowledged (TD-31). | S (B) |
| FR-INT-16 | **(new 0.6)** Each remote I/O output shall have a polarity, **normal** (energized when the signal is true) or **inverted**, set in the system configuration. Every output, including Error, is normal by default (TD-31). | S (B) |
| FR-INT-17 | **(new 0.7)** Each remote I/O input shall have a function (`trigger`, `clear_error`) and an edge, **rising** or **falling**, set in the system configuration (document 09 §19, Keyence *I/O Settings*). Debounce is a job setting (FR-TRG-8). | S (B) |

### 3.8 Data collection and model (MDL)

| ID | Requirement | Priority |
|---|---|---|
| FR-MDL-1 | The system shall have a collection mode that saves every inspection frame, with the job name and the result, for later labeling. | M |
| FR-MDL-2 | The Supervisor or Operator shall be able to mark a result as wrong ("this was actually OK / NOT OK") so the image is added to the training set with the correct label. | S |
| FR-MDL-3 | A job shall reference its model by file and checksum. Replacing the model shall create a new job version. | M |
| FR-MDL-4 | Before a new model is accepted, the system shall run it on the job's reference images and the labeled test set, and show the comparison with the current model. | S |
| FR-MDL-5 | **(new 0.3)** The Maintainer shall be able to teach a "different from good" tool at the station from good parts only, without a training stack installed: the `compare` tool (variation model) and the `anomaly` tool (patch features of an ONNX backbone and a memory bank). The taught data is stored in the job. | S (C: compare · E: anomaly) |
| FR-MDL-6 | **(new 0.3)** A model card shall state the licence of the code and the starting weights, and the measured latency on tier M and tier R. The job editor shall warn when a model breaks the job's time budget on this PC. | S (E) |

### 3.9 Administration (ADM)

| ID | Requirement | Priority |
|---|---|---|
| FR-ADM-1 | There shall be three access levels: Operator (no login), Supervisor and Maintainer, each with a password. | M |
| FR-ADM-2 | The application shall start automatically when Windows starts and open the operator screen. | M |
| FR-ADM-3 | The system shall show the application version, job versions and model versions on an "About" screen. | M |
| FR-ADM-4 | Updates shall be installable by the Maintainer, by copying a file or remotely, without losing jobs or records. | M |
| FR-ADM-5 | **(new 0.3)** The system shall include a benchmark that runs a fixed workload and the jobs' reference sets, records the time per stage and per tool, classifies the PC (tier M or R), and sets thread limits. It runs on first start and on demand; the "About" screen shows the last report. | M (C) |
| FR-ADM-6 | **(new 0.3)** A job may define a challenge set (known good and known bad master parts with expected results). The system configuration may require a challenge run at the start of each shift and after each job change; until it passes, the station does not reach Ready (ERROR E505). Each run is recorded. | S (D) |
| FR-ADM-7 | **(new 0.3)** The Maintainer shall be able to see the machine interface live (inputs, outputs, heartbeat ages, last errors) and to force outputs for commissioning, only while the station is Paused, with every forced value logged. | S (B) |
| FR-ADM-8 | **(new 0.4)** A fresh installation shall open a commissioning wizard (camera, benchmark, passwords, machine, backup folder, first job) that the Maintainer can also reopen later (document 05 §7.11). | S |

### 3.10 Platform (PLT)

| ID | Requirement | Priority |
|---|---|---|
| FR-PLT-1 | **(changed 0.3)** The system shall offer inspection tools by type, each with its own parameters and a user-drawn region. Today: `color`, `pattern`, `code`, `detect`. Minimum set (tier 1, FR-PLT-9) adds `brightness`, `blob`, `edge`, `pattern` v2 and `compare`. | M (`color`, `pattern`, `code`), S (`detect`) |
| FR-PLT-2 | A new tool type shall be added without changing the job manager, the station controller, the API or the screen. | M |
| FR-PLT-3 | **(changed 0.7)** A job shall choose its trigger type in its acquisition block (`acquisition.trigger.type`): `image_presence`, `manual`, `external` or `continuous`. The parameters of each type are written next to it (FR-TRG-1, -5, -6, -7, -8). Which line or protocol delivers an `external` trigger is not in the job: it is station configuration (FR-INT-6, FR-INT-17). | M (`continuous` built when a project needs it) |
| FR-PLT-4 | A job shall work without a locator, with regions relative to the frame. | M |
| FR-PLT-5 | The texts the operator screen shows for a job shall come from the job and the language file, not from code. | M |
| FR-PLT-6 | Customer jobs, reference images, acceptance data and notes shall live in each customer project, outside this repository; the platform code and its examples contain no customer words. | M |
| FR-PLT-7 | The user shall be able to create a job, draw and test tool regions on the live image, and save it, from the screen. | M |
| FR-PLT-8 | **(changed 0.3)** Locators shall be plugins like tools: `fixed`, `template`, `blob` exist; `blob` v2 (with angle), `shape` (rotation and scale) and `edges` (two-edge corner) complete the set. | M (`fixed`, `template`, `blob`), M (A/C) for the rest |
| FR-PLT-9 | **(new 0.3)** The minimum tool set (tier 1) shall be: `brightness` (level and prohibit), `color`, `blob` (area and count), `edge` (presence, position, width, pitch, diameter on an arc), `pattern` v2 (shape-based, rotation and scale), `code`, `compare` (variation model), `detect`. Tier 2: `ocr` (read or verify text), `anomaly` (taught on station). | M (C) tier 1, S (E) tier 2 |
| FR-PLT-10 | **(new 0.3)** Every tool shall return named numeric values with units and reason codes, and draw on the overlay what it measured (matches, edges, blobs, defect areas). | M (C) |
| FR-PLT-11 | **(new 0.3)** A tool or locator type version shall be released only when it passes the validation checklist of document 03 §15.3 (V1–V10), automated in the test suite. | M (C) |
| FR-PLT-12 | **(new 0.3)** Inspection logic shall ship only inside the program, versioned per tool type. A job shall contain data (parameters, images, taught data, models), never executable code; a job file with any other kind of file is refused. | M (A) |

---

## 4. Non-functional requirements

### 4.1 Performance (PERF)

| ID | Requirement | Priority |
|---|---|---|
| NFR-PERF-1 | Time from the object being still to the result on screen: project value (proposed: ≤ 1.5 s with the classical tools on the specified PC). The pipeline reports its own timings. | M |
| NFR-PERF-2 | Throughput: one inspection per presented object with no missed objects, up to a project value (proposed: 20 per minute). | M |
| NFR-PERF-3 | **(changed 0.3)** All inspection, teaching and inference shall run on the CPU. No dedicated GPU is required or supported as a requirement. An Intel integrated GPU may be used through OpenVINO only as an optional accelerator chosen by the benchmark; no job may depend on it. | M |
| NFR-PERF-4 | **(changed 0.3)** The live image on the operator screen shall update at ≥ 10 fps on tier R and ≥ 5 fps on tier M. | S |
| NFR-PERF-5 | **(new 0.3)** The platform shall meet the per-tier targets of the table below, measured by the benchmark (FR-ADM-5). Values are proposed until benchmark B-1 on real units confirms them (TD-28). | M (C) |
| NFR-PERF-6 | **(new 0.3)** Machine interface: from the machine's trigger edge to TriggerAck ≤ 50 ms; from the decided result to ResultValid ≤ 30 ms; adapter cycle ≤ 10 ms (proposed, both tiers). | M (B) |
| NFR-PERF-7 | **(new 0.3)** While waiting for an object with the image trigger, the core shall use ≤ 35 % of the CPU on tier M and ≤ 15 % on tier R, leaving room for the screen and the operating system. | S (C) |

**PC tiers and targets (NFR-PERF-5).** Neither tier has a dedicated GPU.

| | Tier M (minimum) | Tier R (recommended) |
|---|---|---|
| CPU class | Intel N100 / N97 / N150 (4 cores, AVX2) | Intel Core i5 12th gen or newer, or Core Ultra 5 |
| RAM / storage | 16 GB / 256 GB SSD | 16–32 GB / 512 GB – 1 TB NVMe |
| Classical job (≤ 8 tier-1 tools, 1920 × 1080 frame, regions ≤ 1 MP): pipeline time | ≤ 400 ms | ≤ 150 ms |
| Job with one model at its card's input size: pipeline time | ≤ 900 ms (INT8 where possible) | ≤ 350 ms |
| `compare` teaching from 20 good parts | ≤ 30 s | ≤ 10 s |
| `anomaly` teaching from 50 good parts | ≤ 5 min | ≤ 1 min |
| Core memory with 3 models loaded | ≤ 2.5 GB | ≤ 2.5 GB |
| Start-up to Ready (after Windows has started) | ≤ 2 min | ≤ 2 min |

### 4.2 Accuracy (ACC)

| ID | Requirement | Priority |
|---|---|---|
| NFR-ACC-1 | Detection rate (a real defect flagged FAIL): project value (proposed: 99 %). The platform measures it on the job's reference set and on labeled results. | M |
| NFR-ACC-2 | False-reject rate (a good object flagged FAIL): project value (proposed: 1 %). | M |
| NFR-ACC-3 | Accuracy shall be measured on a test set collected at the station, not used for training, covering every variant of the job and the light of a full day. | M |
| NFR-ACC-4 | The result shall not change when the object is placed within the job's placement tolerance (proposed: ±30 mm and ±10°) of its nominal position, when the job has a locator. | S → **M (A)** with FR-INS-11 |
| NFR-ACC-5 | **(new 0.3)** For validated tools, the outcome on the reference set shall not change under a global brightness change of ±15 % or Gaussian noise of σ = 2 gray levels (validation check V4). | M (C) |
| NFR-ACC-6 | **(new 0.3)** Acceptance of a job for production shall follow the method of VDI/VDE/VDMA 2632-3: a sample catalog (good parts and parts with each defect) plus production data, with the detection and false-reject rates and the sample sizes recorded. | S (D) |

### 4.3 Reliability and recovery (REL)

| ID | Requirement | Priority |
|---|---|---|
| NFR-REL-1 | The system shall run unattended for a full shift (proposed: 10 h) and across days without needing a restart. | M |
| NFR-REL-2 | After a power loss or PC restart, the system shall return to inspecting with the last active job, without operator action, within 2 min. | M |
| NFR-REL-3 | After a camera disconnect, inspection shall resume automatically within 30 s of the camera returning. | M |
| NFR-REL-4 | A complete reinstallation on a new PC from a backup file, by the Maintainer, shall take ≤ 1 hour, including verification. | M |
| NFR-REL-5 | Restoring a backup on a new installation shall give the same results on the jobs' reference images as the original installation. | M |
| NFR-REL-6 | A crash of the inspection process shall be detected and the process restarted automatically, with the crash logged. | S |
| NFR-REL-7 | **(new 0.3)** Machine outputs shall fail safe: at start, on loss of the core, of the connection, of the camera, and between results, no result signal shall be on; Pass, Fail and Error are meaningful only while ResultValid is on, and are written before it. | M (B) |
| NFR-REL-8 | **(new 0.3)** Heartbeats shall run both ways (proposed period 500 ms, timeout 1.5 s). On loss of the machine's heartbeat the station shall stop accepting machine triggers and raise ERROR E601. | M (B) |
| NFR-REL-9 | **(new 0.3)** A 72-hour soak test with a trigger every 3 s (file camera and simulated PLC) shall show no missed or duplicated result, no growth of the core's memory above 50 MB after the first hour, and no growth in pipeline time. | M (B) |

### 4.4 Usability (USA)

| ID | Requirement | Priority |
|---|---|---|
| NFR-USA-1 | An operator shall understand the result and the reason after a training of at most 15 minutes. | M |
| NFR-USA-2 | The result shall be readable from the operator's working position (proposed: ≥ 2 m), using colour **and** text, not colour alone. | M |
| NFR-USA-3 | The Supervisor shall be able to export a backup and restore a job by following the written procedure, without the Maintainer present. | M |
| NFR-USA-4 | **(new 0.3)** A PLC programmer shall be able to integrate a station with the interface map document and the sample block alone, without reading Vision Station's code (proposed check: one integration done by someone other than the developer). | S (B) |

### 4.5 Portability and platform (POR)

| ID | Requirement | Priority |
|---|---|---|
| NFR-POR-1 | The system shall run on Windows 11 (64-bit). | M |
| NFR-POR-2 | The inspection core shall not depend on Windows-only libraries, so it can also run on Linux. | S |
| NFR-POR-3 | The job file format shall not depend on the operating system: paths relative, text files in UTF-8. | M |
| NFR-POR-4 | Adding a new camera model shall need only a new camera driver module, with no change to inspection or job code. | M |
| NFR-POR-5 | **(new 0.3)** The same job shall give the same outcomes and scores (to 1e-6) on tier M and tier R; only time may differ. No tool may use tier-specific logic. | M (C) |

### 4.6 Maintainability (MAI)

| ID | Requirement | Priority |
|---|---|---|
| NFR-MAI-1 | The job file format shall be documented (deliverable D8) and versioned. Newer software shall read older job files. | M |
| NFR-MAI-2 | Application logs shall be kept with rotation (proposed: 30 days) and be easy to collect for remote support. | M |
| NFR-MAI-3 | The code shall have automated tests for job export/import and for the tools, run against stored reference images. | S |
| NFR-MAI-4 | The design shall stay simple enough for one developer to maintain. | M |
| NFR-MAI-5 | **(new 0.3)** The tool validation checklist (V1–V10) shall run automatically in the test suite for every tool and locator type; a failing check blocks the release. | M (C) |
| NFR-MAI-6 | **(new 0.3)** The interface map shall be versioned. Within a major version, changes shall only add fields at the end; existing fields keep their position and meaning. | M (B) |
| NFR-MAI-7 | **(new 0.3)** Code shall be organized so that vision algorithms are pure functions without file, camera or job access (document 03 §3.3), testable and benchmarkable on their own. | S |

### 4.7 Security (SEC)

| ID | Requirement | Priority |
|---|---|---|
| NFR-SEC-1 | Camera passwords and user passwords shall not be stored in plain text. Job files shall not contain camera passwords. | M |
| NFR-SEC-2 | The IP camera shall be on a network segment or port dedicated to the inspection PC, where possible. | S |
| NFR-SEC-3 | Remote access for support, if any, shall follow the site's IT policy. | M |
| NFR-SEC-4 | **(new 0.3)** Machine connectors shall bind only to the configured machine-network interface. The Modbus TCP server shall accept only listed client addresses. | M (B) |
| NFR-SEC-5 | **(new 0.3)** The OPC UA server shall offer SignAndEncrypt by default. Reading may be anonymous if configured; methods that change state (prepare a recipe, start a job, transfer files) shall need an authenticated user with the right role. | M (E) |
| NFR-SEC-6 | **(new 0.3)** The S7 connector needs PUT/GET enabled on the PLC, which is unauthenticated. The installation guide shall state this, require a segmented machine network, and offer the Modbus route for sites that refuse PUT/GET. | M (B) |

### 4.8 Legal and licensing (LIC)

| ID | Requirement | Priority |
|---|---|---|
| NFR-LIC-1 | Every shipped component, including model weights and training code that produced them, shall have a license that allows closed commercial use (e.g. MIT, BSD, Apache 2.0), or a commercial license shall be bought. | M |
| NFR-LIC-2 | A list of third-party components and their licenses shall be delivered with the software. | M |
| NFR-LIC-3 | **(new 0.3)** An LGPL component (the OPC UA library) may ship only unmodified and replaceable by the user (outside the program's bundled archive), with its licence text and a source offer (TD-24). Code ported from Apache-2.0 projects (e.g. Fullseye) shall keep the attribution required by their NOTICE. | M (E) |

### 4.9 Environment and storage (ENV)

| ID | Requirement | Priority |
|---|---|---|
| NFR-ENV-1 | The system shall keep working under the light variation of a full day at the station (ceiling lamps and windows), or flag ERROR when the image leaves the job's limits. | M |
| NFR-ENV-2 | Disk usage for records shall stay within a configured limit (proposed: 100 GB), enforced by FR-LOG-3. | M |

---

## 5. Use cases

### UC-01 — Inspect an object (main flow)

| | |
|---|---|
| Actor | Operator (primary), Camera, Machine (optional) |
| Goal | Know whether the object at the station is right before it moves on |
| Preconditions | System running, active job verified, camera connected |
| Trigger | The object is presented and stays still, or an external or manual trigger |

**Main flow**
1. The Operator (or the machine) presents the object at the station.
2. The system detects an object present and still, or receives the external or manual trigger.
3. The system captures a fresh frame and signals acquisition done.
4. The system checks image quality (brightness, color reference if any, sharpness) against the job's limits and reference.
5. The system finds the job's fixtures (position, angle, scale) and places the ROIs.
6. The system runs every tool of the job, in order.
7. The system shows PASS, FAIL or ERROR with the reason, and draws what each tool measured (green passed, red failed).
8. The system records the result (and the image, per FR-LOG-2) and, if a machine interface is enabled, signals it.
9. The object is removed. The system shows the job's waiting text and waits for the next one.

**Alternative / exception flows**
- 4a. Image too dark, too bright, flat, out of focus, or color reference drifted → ERROR with the specific reason and code. Go to 8.
- 5a. A fixture is not found → ERROR E201, "Objeto não encontrado na posição esperada". Go to 8.
- 5b. A fixture is found outside its allowed position, angle or scale → ERROR E202. Go to 8.
- 6a. A region falls outside the image, or a tool breaks → ERROR. Go to 8.
- 7a. FAIL → the object is fixed and presented again. The system treats it as a new inspection.
- 2a. The object is removed before the result → no result recorded; logged as "inspeção interrompida".
- Any step: camera lost → UC-09.

**Postconditions:** a record exists for the inspection. Counters are updated.

Covers: FR-ACQ-6/7, FR-TRG-1..4, FR-INS-*, FR-UI-1..4, FR-LOG-1/2/8.

---

### UC-02 — Select the active job

| | |
|---|---|
| Actor | Supervisor |
| Goal | Switch the station to another product or variant |
| Preconditions | Supervisor logged in; target job exists |

**Main flow**
1. The Supervisor opens the job list and picks a job.
2. The system loads the job, applies the camera settings and reads them back.
3. The system captures a frame and compares it with the job's reference image.
4. The system shows "Job verificado" and starts inspecting with the new job (after a challenge test, if the system requires one, UC-14).

**Exceptions**
- 2a. A camera setting did not apply → the system shows which one and does not start. The Supervisor can retry or call the Maintainer.
- 3a. The frame differs too much from the reference (camera moved, lighting changed, focus off) → warning with the side-by-side images. The job does not start unless the Maintainer overrides.

Covers: FR-JOB-1/3, FR-ACQ-4/8, FR-JOB-9.

---

### UC-03 — Create or tune a job ("teach")

| | |
|---|---|
| Actor | Maintainer |
| Goal | Set up the inspection for a new product or variant |
| Preconditions | Maintainer logged in; sample objects available (good and defective) |

**Main flow**
1. The Maintainer creates a new job, or duplicates an existing one.
2. The Maintainer sets the camera settings while watching the live image (exposure, white balance, focus, zoom).
3. The Maintainer presents a good object and captures the **reference image**.
4. The Maintainer adds fixtures (a locator, its search area, its allowed angle and scale) or none, and draws the ROIs on the reference.
5. The Maintainer adds tools from the catalog (FR-PLT-9), one per ROI, sets their parameters and writes each failure reason in Portuguese and English. Tools that learn from good parts are taught here (UC-13).
6. The Maintainer tests the job live with good and defective objects, placed shifted and turned within the tolerance, and adjusts the parameters. The editor shows the time per stage against the job's budget on this PC.
7. The Maintainer saves the reference set: the images used in step 6, with their expected results; and, optionally, the challenge set.
8. The Maintainer saves the job. A new version is created and an automatic backup is made. For an active job, the A/B replay (FR-JOB-12) is offered before activation.

**Exceptions**
- 6a. Good and bad objects can't be separated by thresholds → the Maintainer tries a `compare` or `anomaly` tool (UC-13) or marks the job as needing a model and starts UC-08.
- 6b. The job breaks its time budget on this PC → the editor shows which stage; the Maintainer reduces regions or work sizes, or the project moves to tier R.

Covers: FR-JOB-2/4/5/10/12, FR-INS-2..5/10..13, FR-PLT-7/9, FR-ACQ-8, FR-ADM-5.

---

### UC-04 — Export a job or a full backup

| | |
|---|---|
| Actor | Supervisor or Maintainer; System (scheduled) |
| Goal | Have a copy of the configuration outside the PC |
| Preconditions | Logged in, for manual export |

**Main flow**
1. The user chooses "Exportar job" (one job) or "Backup completo" (all jobs + system settings).
2. The user chooses the destination (USB drive, network folder).
3. The system writes the file with checksums and a manifest.
4. The system reads the file back and verifies it.
5. The system shows "Backup concluído" with the file name and size.

**Alternative flow**
- 1a. Scheduled: the system runs steps 3–4 automatically to the configured folder and keeps the last N backups. A failure is shown on the operator screen as a warning.

Covers: FR-JOB-6/7/10, NFR-USA-3.

---

### UC-05 — Import / restore a job or backup

| | |
|---|---|
| Actor | Supervisor or Maintainer |
| Goal | Recover the configuration after loss, or move it to another PC |
| Preconditions | Logged in; backup or job file available |

**Main flow**
1. The user chooses "Importar" and selects the file.
2. The system checks integrity and format version (FR-JOB-8); a job of an older format is refused with a clear message (FR-JOB-13 is suspended).
3. The system lists what the file contains and what it will replace. The user confirms.
4. The system stores the jobs. Existing versions are kept, not overwritten.
5. For the job to be activated, the system runs verification (FR-JOB-9): apply settings, read back, capture, compare with reference, run tools on reference images.
6. The system shows the verification report. If it passed, the job becomes active.

**Exceptions**
- 2a. Damaged or incompatible file → refused, with the reason. Nothing is changed.
- 2b. The file contains files the job's tools do not name (e.g. scripts) → refused (FR-PLT-12).
- 5a. Verification fails (e.g. camera mounted differently on a new installation) → the job is stored but not activated. The Maintainer adjusts (UC-03) or overrides with a recorded reason.
- 3a. The file came from the other camera type → settings that don't apply are listed for review (FR-JOB-11).

Covers: FR-JOB-8/9/11/13, FR-PLT-12, NFR-REL-4/5.

---

### UC-06 — Replace the PC or the camera

| | |
|---|---|
| Actor | Maintainer |
| Goal | Return to production after a hardware failure |
| Preconditions | Latest backup file available |

**Main flow**
1. The Maintainer installs the application on the new PC, or connects the new camera. On first start the benchmark classifies the PC (FR-ADM-5).
2. The Maintainer sets the system settings that aren't part of the jobs (camera address and password, backup folder); machine settings come back with the backup.
3. The Maintainer restores the backup (UC-05).
4. For each job in use, the system runs verification. The Maintainer adjusts focus or position if the camera mount changed.
5. The Maintainer runs the challenge set, or a few known good and bad objects, to confirm.

**Postcondition:** production resumes within NFR-REL-4.

---

### UC-07 — Review failures and correct results

| | |
|---|---|
| Actor | Supervisor |
| Goal | Understand failures and feed corrections back into training |

**Main flow**
1. The Supervisor opens the results screen and filters by date, job, result and reason code.
2. The Supervisor opens a result and sees the image with what each tool measured and the scores.
3. If the result was wrong, the Supervisor marks it "Resultado incorreto" and picks the correct one.
4. The system adds the image to the training set with the correct label (FR-MDL-2).
5. Optionally, the Supervisor exports the filtered results to CSV.

**Alternative flow**
- 1a. The system shows a margin warning (FR-LOG-7) for a tool → the Supervisor opens the results of that tool sorted by margin and calls the Maintainer.

Covers: FR-LOG-4/7, FR-MDL-2.

---

### UC-08 — Collect images and update the model

| | |
|---|---|
| Actor | Maintainer |
| Goal | Train or improve the model used by a job |

**Main flow**
1. The Maintainer turns on collection mode for the job (FR-MDL-1) for a period that covers different times of day.
2. The Maintainer exports the collected and corrected images.
3. Outside the system, the Maintainer labels the images, trains and exports the model, and measures its latency on tier M and tier R for the card (FR-MDL-6).
4. The Maintainer loads the new model into the job.
5. The system runs the new model on the reference images and the test set, and shows the comparison with the current model (FR-MDL-4).
6. If the new model is better, the Maintainer accepts it. A new job version is created and backed up.

**Exceptions**
- 5a. The new model is worse on any reference image → the Maintainer must confirm explicitly. The old version remains restorable.
- 5b. The model breaks the job's time budget on this PC → warning (FR-MDL-6).

---

### UC-09 — Camera lost and recovered

| | |
|---|---|
| Actor | System; Operator (informed); Machine (informed) |
| Trigger | No frames from the camera for more than a short timeout |

**Main flow**
1. The system detects the loss and shows "Câmera desconectada" in yellow. No PASS is shown or signalled while the camera is lost; the machine sees TriggerReady off and Error with E401.
2. The system retries the connection periodically.
3. When the camera returns, the system reapplies the job's camera settings and reads them back.
4. The system compares a frame with the reference image.
5. The system returns to the job's waiting text (`ui.waiting`, e.g. "Aguardando peça") and to TriggerReady.

**Exceptions**
- 4a. The frame doesn't match the reference → as UC-02 3a.

Covers: FR-ACQ-5, NFR-REL-3, NFR-REL-7.

---

### UC-10 — Start-up after power loss

| | |
|---|---|
| Actor | System |
| Trigger | The PC powers on |

**Main flow**
1. Windows starts. The application starts automatically (FR-ADM-2).
2. The system loads the last active job and runs the camera steps of UC-02 (apply, read back, compare).
3. The machine connectors start with every result signal off, then report Online and the job number (NFR-REL-7).
4. The system shows the operator screen with the job's waiting text (after a challenge test, if required at start-up).

**Exceptions**
- 2a. The camera isn't ready yet (the IP camera boots slower than the PC) → keep retrying as in UC-09.

Covers: NFR-REL-2, NFR-REL-7.

---

### UC-11 — Machine-driven inspection **(new 0.3)**

| | |
|---|---|
| Actor | Machine (PLC) (primary), System |
| Goal | The machine decides when to inspect and acts on the result (pass the part, reject it, stop) |
| Preconditions | A machine connector is enabled; the active job has the `external` trigger type; heartbeats running |
| Trigger | The machine has a part in position and still |

**Main flow**
1. The PLC sets TriggerEnable and waits for TriggerReady.
2. The PLC writes PartId (optional) and raises Trigger.
3. The system answers TriggerAck, takes a fresh frame and raises AcquisitionDone. The PLC may move the part.
4. The system runs the pipeline and writes the result fields (sequence, Pass/Fail/Error, error code, reason code, tool mask, user values), then raises ResultValid.
5. The PLC reads the result, acts on it, and raises ResultAck.
6. The system lowers ResultValid and clears the result bits (or presents the next buffered result).
7. The PLC lowers Trigger; the system lowers TriggerAck and AcquisitionDone.

**Exceptions**
- 2a. Trigger while TriggerReady is off → TriggerRefused pulses; nothing is queued.
- 4a. ERROR → Error bit with its code; the PLC treats it as reject or stop, per its program.
- 5a. The PLC does not acknowledge and more results arrive → buffered up to the depth; then BufferOverrun.
- Any step: the PLC's heartbeat stops → E601, triggers refused; the core stops → the PLC sees the heartbeat stop and must fault the station.

Covers: FR-INT-3..5/9..12, FR-TRG-2, NFR-PERF-6, NFR-REL-7/8.

---

### UC-12 — Change job from the machine **(new 0.3)**

| | |
|---|---|
| Actor | Machine (PLC) |
| Goal | Switch the station to the product the machine is about to run |
| Preconditions | Job numbers mapped in the system configuration |

**Main flow**
1. The PLC writes JobNumberRequest and raises JobChangeRequest.
2. The system finds the job for the number and switches to it as in UC-02 (apply, read back, compare, reference set if configured).
3. The system sets CurrentJobNumber, raises JobChangeDone and returns to TriggerReady (after a challenge test if required).
4. The PLC lowers JobChangeRequest; the system lowers JobChangeDone.
5. The audit log records the change with the source "machine".

**Exceptions**
- 2a. Unknown number → JobChangeFailed with E503; the station stays out of Ready.
- 2b. Verification fails → JobChangeFailed with E504; the station stays out of Ready until a valid job is active.

Covers: FR-INT-8, FR-LOG-5, FR-JOB-9.

---

### UC-13 — Teach a "different from good" tool from good parts **(new 0.3)**

| | |
|---|---|
| Actor | Maintainer |
| Goal | Detect unexpected defects (scratch, smear, missing feature) without training a model offline |
| Preconditions | The job has a fixture that aligns the part; good parts available |

**Main flow**
1. The Maintainer adds a `compare` (or `anomaly`) tool on a region and starts teaching.
2. The Maintainer presents good parts one by one (proposed: 20 for `compare`, 50 for `anomaly`), placed as in production.
3. The system aligns each region with the fixture and builds the taught data (per-pixel statistics, or a memory bank of patch features). It shows progress and how much each new part still changed the model.
4. The Maintainer presents known bad parts; the system shows the defect map and score; the Maintainer sets the threshold.
5. The taught data is saved in the job with the new version.

**Exceptions**
- 3a. A part is not aligned (fixture not found or out of range) → that part is skipped and reported.
- 4a. Good and bad parts overlap → the Maintainer adds more good parts, narrows the region, or falls back to UC-08.

Covers: FR-MDL-5, FR-PLT-9.

---

### UC-14 — Start-of-shift challenge test **(new 0.3)**

| | |
|---|---|
| Actor | Supervisor or Operator |
| Goal | Prove at the start of the shift, or after a job change, that the station still catches a known defect |
| Preconditions | The active job has a challenge set; the system configuration requires a challenge run |

**Main flow**
1. The station shows "Teste de desafio pendente" and is not Ready (machine: ERROR E505).
2. The user presents each master part named in the challenge set, in the order shown.
3. The system inspects each one and compares the outcome with the expected one.
4. When all match, the system records the run and goes to Ready.

**Exceptions**
- 3a. A master gives the wrong outcome → the run fails, the station stays out of Ready, the Maintainer is called; the run is recorded.

Covers: FR-ADM-6, NFR-ACC-6.

---

### UC-15 — Fine-tune a tolerance **(new 0.4)**

| | |
|---|---|
| Actor | Supervisor |
| Goal | Keep a job accepting good parts when the product or the light drifts a little, without the Maintainer |
| Preconditions | Supervisor logged in; the active job has tools with tunable limits |
| Trigger | False rejects rise, or a margin warning (FR-LOG-7) |

**Main flow**
1. The Supervisor opens *Ajuste fino* for the active job.
2. The system shows each deciding tool with its tolerance gauges: the live value, the samples' values and the limits.
3. The Supervisor captures a few new good (and, if available, bad) parts as samples.
4. The Supervisor drags a limit, or accepts the limit proposed from the samples, and watches the live result.
5. The Supervisor saves with a note. A new version is created and verified.
6. If verification passes, the Supervisor activates it. The audit log records every changed limit.

**Exceptions**
- 4a. The samples overlap (no limit separates good from bad) → the system says so; the Supervisor calls the Maintainer.
- 5a. Anything other than a tunable limit changed (e.g. through a stale draft) → the server refuses the save.
- 6a. Verification fails → the version is stored, not active; only the Maintainer may override.

Covers: FR-JOB-14, FR-UI-13/14, FR-LOG-5.

---

## 6. Traceability summary

| Use case | Main requirements |
|---|---|
| UC-01 Inspect an object | FR-ACQ-6/7, FR-TRG-*, FR-INS-*, FR-UI-1..4, FR-LOG-1/2/8, NFR-PERF-1/2/5, NFR-ACC-* |
| UC-02 Select job | FR-JOB-1/3/9, FR-ACQ-4/8 |
| UC-03 Create/tune job | FR-JOB-2/4/5/10/12, FR-INS-2..5/10..13, FR-PLT-7/9, FR-ADM-5, FR-UI-10..14 |
| UC-04 Export / backup | FR-JOB-6/7/10, NFR-USA-3 |
| UC-05 Import / restore | FR-JOB-8/9/11/13, FR-PLT-12, NFR-REL-4/5 |
| UC-06 Replace PC or camera | UC-05, FR-ADM-5, NFR-REL-4, NFR-POR-4/5 |
| UC-07 Review failures | FR-LOG-4/7/9, FR-MDL-2 |
| UC-08 Update model | FR-MDL-*, FR-JOB-5 |
| UC-09 Camera lost | FR-ACQ-5, NFR-REL-3/7 |
| UC-10 Start-up | FR-ADM-2, NFR-REL-2/7 |
| UC-11 Machine-driven inspection | FR-INT-3..6/9..12/14..17, FR-TRG-2/6/8, NFR-PERF-6, NFR-REL-7..9, NFR-SEC-4/6 |
| UC-12 Job change from the machine | FR-INT-8, FR-LOG-5 |
| UC-13 Teach from good parts | FR-MDL-5, FR-PLT-9, NFR-PERF-5 |
| UC-14 Challenge test | FR-ADM-6, NFR-ACC-6 |
| UC-15 Fine-tune a tolerance | FR-JOB-14, FR-UI-13/14, FR-LOG-5 |

## 7. Project values

Each project that uses the platform sets these for its jobs and its own acceptance. The platform keeps them as configuration (in the job or the system settings), never as constants in code.

| Item | Where | Proposed default |
|---|---|---|
| Time to result after the object is still | NFR-PERF-1 | 1.5 s |
| Objects per minute | NFR-PERF-2 | 20 |
| Detection rate | NFR-ACC-1 | 99 % |
| False-reject rate | NFR-ACC-2 | 1 % |
| Placement tolerance | NFR-ACC-4 | ±30 mm, ±10° |
| Retention of records and images | FR-LOG-3 | keep everything; PASS sampling, days and disk limit configurable |
| External trigger source | FR-TRG-2 | none (image trigger) |
| Trigger delay (external) | FR-TRG-6 | 0 ms |
| Minimum interval (continuous) | FR-TRG-7 | 500 ms |
| Trigger debounce (external) | FR-TRG-8 | 0 ms |
| Trigger input edge | FR-INT-17 | rising |
| Image orientation | FR-ACQ-10 | normal |
| Good samples needed to propose a limit | FR-UI-14 | 3 |
| Margin of a proposed limit, with no bad samples | FR-UI-14 | 20 % of the worst good value |
| Reject output: results, delay, pulse | FR-INT-15 | FAIL and ERROR; delay per station; 100 ms pulse |
| Output polarity | FR-INT-16 | all normal |
| Machine connector | FR-INT-3..7 | none; S7, Modbus TCP server, remote I/O or OPC UA per project |
| Acknowledge mode and result-buffer depth | FR-INT-9 | acknowledge, 8 |
| Heartbeat period / timeout | NFR-REL-8 | 500 ms / 1.5 s |
| Job numbers and products | FR-INT-8 | none |
| User values to the machine | FR-INT-11 | none |
| What happens on FAIL beyond the screen | FR-INT-2 | screen only |
| Order/batch number source | FR-LOG-6 | none |
| Backup destination | FR-JOB-10 | network share + USB drive |
| Recovery time after power loss | NFR-REL-2 | 2 min |
| PC tier | NFR-PERF-5 | R; M only for classical jobs that the benchmark confirms |
| Margin warning limit and window | FR-LOG-7 | 0.05 over the last 200 PASS |
| Low-margin PASS images kept | FR-LOG-9 | margin below 2 × the warning limit (0.10) |
| Challenge test policy | FR-ADM-6 | not required; when required: start of shift and after job change |
| Color-reference drift limit | FR-INS-16 | ΔE 6 |
