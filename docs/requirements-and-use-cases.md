# Vision Station — Requirements and Use Cases

| | |
|---|---|
| Document | 02 — Functional Requirements, Non-Functional Requirements and Use Cases |
| Version | 0.2 |
| Date | 2026-10-15 |
| Author | Lucas (developer and maintainer) |
| Status | Platform requirements (TD-19) |

> **Platform requirements (TD-19).** These are the requirements of Vision Station, a vision system for **fixed stations** where the object is **still** while it is inspected. Customer projects that use the platform write their own requirements (what to inspect, accuracy, time to result) and meet them with jobs; they are not listed here. Examples in this document (a label, a part on a jig, a closed package) only illustrate.

Related documents: 01 — Project Scope · 03 — Architecture ("job" model) · 04 — Technical Decisions.

---

## 1. Conventions

- **IDs:** `FR-<area>-<n>` for functional requirements, `NFR-<area>-<n>` for non-functional requirements, `UC-<n>` for use cases.
- **Priority (MoSCoW):**
  - **M** = Must: required for acceptance.
  - **S** = Should: expected, but can move to a later phase.
  - **C** = Could: only if time allows.
  - **W** = Won't (this version): recorded so it isn't forgotten.
- **Project value:** a number that each project that uses the platform sets for itself (time to result, accuracy). The platform makes it configuration and measures it; section 7 lists them.
- **Proposed:** a default value suggested by the developer.
- **Glossary:**
  - **Job:** the full set of settings for inspecting one product or variant at one station: camera settings, trigger, locator, regions, tools, thresholds, models and reference images.
  - **Job file:** a single file containing one job, used for backup and restore.
  - **Backup file:** a single file containing all jobs plus the system settings.
  - **Trigger:** the event that starts one inspection.
  - **ROI:** region of interest, the part of the image a tool looks at.
  - **Tool:** a versioned inspection step of one type (`color`, `pattern`, `code`, `detect`) that looks at one ROI and returns pass/fail and a score.
  - **Locator / anchor:** the locator finds the object (the anchor) in the image, so ROIs can follow it when it is placed a little differently.
  - **Fixed station:** a fixed camera and an object that is still during the capture (on a jig, bench, scale or a stopped machine).

## 2. Actors

| Actor | Description |
|---|---|
| Operator | Presents the object at the station and reads the result. No technical training. |
| Supervisor | Selects the active job, reviews failures, keeps the backup file. |
| Maintainer | Creates and tunes jobs, installs updates, trains models. |
| External system | Optional source of the trigger (a machine, a sensor, a scale with "weight stable") and optional receiver of the result (PLC, MES). |
| Camera | A camera plugin: C920 (USB) now, Hikvision IP camera later. |

---

## 3. Functional requirements

### 3.1 Acquisition (ACQ)

| ID | Requirement | Pri. |
|---|---|---|
| FR-ACQ-1 | The system shall acquire images from a USB UVC camera (first: Logitech C920). | M |
| FR-ACQ-2 | The system shall acquire images from a Hikvision IP camera, by RTSP stream and/or HTTP snapshot. | S (after the first delivery) |
| FR-ACQ-3 | The camera type and its connection data shall be selected by configuration, without changing code. | M |
| FR-ACQ-4 | On startup and on every job load, the system shall apply the job's camera settings (exposure, gain, white balance, focus, resolution, format), then read each one back and report any that did not apply. | M |
| FR-ACQ-5 | The system shall detect when the camera disconnects or the stream stops, show the problem to the operator, and reconnect automatically. After reconnecting, it shall reapply the camera settings. | M |
| FR-ACQ-6 | Each inspection shall use a frame captured after the trigger, never one buffered from before it. | M |
| FR-ACQ-7 | The system shall measure image sharpness and brightness on each inspection frame and compare them with the job's reference image. | S |
| FR-ACQ-8 | For the motorized lens, the system shall store the zoom and focus position in the job and restore it. | S |

### 3.2 Trigger (TRG)

| ID | Requirement | Pri. |
|---|---|---|
| FR-TRG-1 | The system shall start an inspection automatically when an object is present and still in the trigger area, detected from the image (presence + no motion for a configurable time). | M |
| FR-TRG-2 | The system shall accept an external trigger (a machine ready signal, a sensor, a scale's "weight stable"). Interfaces are camera or I/O plugins. | S |
| FR-TRG-3 | The operator shall be able to trigger an inspection manually from the screen. | M |
| FR-TRG-4 | The system shall inspect each object exactly once until it leaves the area. It shall not re-trigger while the same object stays in place. | M |
| FR-TRG-5 | In `continuous` mode the system shall inspect still frames one after another with no trigger (for example a code reader at a station), and still never inspect a frame taken while the scene moves. | C |

### 3.3 Inspection (INS)

| ID | Requirement | Pri. |
|---|---|---|
| FR-INS-1 | Each inspection shall run the active job's pipeline: image quality gate → locator (if any) → regions → every tool in order → decision. | M |
| FR-INS-2 | The `color` tool shall measure the fraction of a region inside a color range, or the distance to a reference color, against a threshold, inside a validation area the user draws. | M |
| FR-INS-3 | The `pattern` tool shall find a taught template in a region, and count its repeats along a line, against a minimum count or coverage. | M |
| FR-INS-4 | Tools shall only look at the job's ROIs, so things outside them (people, other objects) do not affect the result. | M |
| FR-INS-5 | A job shall be able to combine classical tools and trained models. Each tool returns pass/fail plus a score. | M |
| FR-INS-6 | The final result shall be **PASS**, **FAIL** or **ERROR**. ERROR means the system could not inspect: object not found, image too dark, too bright, flat or out of focus, region outside the image, a tool that broke, camera lost. ERROR shall never be shown as PASS. | M |
| FR-INS-7 | Every FAIL and ERROR shall carry a human-readable reason in Portuguese. FAIL reasons come from the job (each tool's `reason_fail`), and list every tool that failed. | M |
| FR-INS-8 | The system shall locate the anchor in the image and place the ROIs relative to it, tolerating the placement variation the job allows (NFR-ACC-4). | S |
| FR-INS-9 | Variants of a product (sizes, colors) shall be handled as separate jobs or as one job whose tools cover them, without platform changes. | M |
| FR-INS-10 | The `code` tool shall read 1D bar codes, QR and Data Matrix in a region and optionally compare the text with an expected value or pattern. | M |

### 3.4 Jobs (JOB)

| ID | Requirement | Pri. |
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

### 3.5 Operator screen (UI)

| ID | Requirement | Pri. |
|---|---|---|
| FR-UI-1 | The screen shall show the live image, the active job and the last result in large, colour-coded form (green PASS, red FAIL, yellow ERROR). | M |
| FR-UI-2 | On FAIL, the screen shall show the reason and highlight on the image where the problem is. | M |
| FR-UI-3 | The screen shall show the system state: camera connected, job verified, waiting (with the job's own text), inspecting. | M |
| FR-UI-4 | The screen shall show counters for the current shift: total, pass, fail, error. | S |
| FR-UI-5 | The operator screen shall be in Portuguese. | M |
| FR-UI-6 | Job editing, export, import and settings shall be hidden from the Operator and need a Supervisor or Maintainer login. | M |
| FR-UI-7 | The system shall give an audible alert on FAIL. | C |

### 3.6 Results and records (LOG)

| ID | Requirement | Pri. |
|---|---|---|
| FR-LOG-1 | Every inspection shall be recorded with: timestamp, job name and version, result, reason, per-tool scores, and the inspection image. | M |
| FR-LOG-2 | Images shall be kept for all FAIL and ERROR results. A configurable sample of PASS images shall also be kept (proposed: 1 in 20). | M |
| FR-LOG-3 | Records older than the configured retention period shall be deleted automatically. When the disk drops below a free-space threshold, the oldest PASS images shall be deleted first. | M |
| FR-LOG-4 | The Supervisor shall be able to browse and filter results by date, job and result, and export them to CSV. | S |
| FR-LOG-5 | The system shall keep an audit log of job changes, imports, exports, overrides and logins. | S |
| FR-LOG-6 | Records shall be linkable to an order or batch number, when a project provides one. | C |

### 3.7 Integration (INT)

| ID | Requirement | Pri. |
|---|---|---|
| FR-INT-1 | The system shall let another program on the same PC request an inspection, follow it by id and get its result and pictures, the system state and the live view, through a documented local interface (HTTP/JSON and WebSocket; document 06). | M |
| FR-INT-2 | The system shall signal the result to an external device (digital output, PLC, tower light) through an I/O plugin. Project integrations are outside the platform scope. | W |

### 3.8 Data collection and model (MDL)

| ID | Requirement | Pri. |
|---|---|---|
| FR-MDL-1 | The system shall have a collection mode that saves every inspection frame, with the job name and the result, for later labeling. | M |
| FR-MDL-2 | The Supervisor or Operator shall be able to mark a result as wrong ("this was actually OK / NOT OK") so the image is added to the training set with the correct label. | S |
| FR-MDL-3 | A job shall reference its model by file and checksum. Replacing the model shall create a new job version. | M |
| FR-MDL-4 | Before a new model is accepted, the system shall run it on the job's reference images and the labeled test set, and show the comparison with the current model. | S |

### 3.9 Administration (ADM)

| ID | Requirement | Pri. |
|---|---|---|
| FR-ADM-1 | There shall be three access levels: Operator (no login), Supervisor and Maintainer, each with a password. | M |
| FR-ADM-2 | The application shall start automatically when Windows starts and open the operator screen. | M |
| FR-ADM-3 | The system shall show the application version, job versions and model versions on an "About" screen. | M |
| FR-ADM-4 | Updates shall be installable by the Maintainer, by copying a file or remotely, without losing jobs or records. | M |

### 3.10 Platform (PLT)

What makes Vision Station a platform rather than one application (TD-19 in document 04).

| ID | Requirement | Pri. |
|---|---|---|
| FR-PLT-1 | The system shall offer inspection tools by type, each with its own parameters and a user-drawn region: `color` (color area or distance to a reference color), `pattern` (template or repeated logo), `code` (1D bar codes, QR and Data Matrix), `detect` (trained model). | M (`color`, `pattern`, `code`), S (`detect`) |
| FR-PLT-2 | A new tool type shall be added without changing the job manager, the station controller, the API or the screen. | M |
| FR-PLT-3 | A job shall choose its trigger mode: `image_presence`, `manual`, `external` or `continuous`. | M (`continuous` built when a project needs it) |
| FR-PLT-4 | A job shall work without a locator, with regions relative to the frame. | M |
| FR-PLT-5 | The texts the operator screen shows for a job shall come from the job and the language file, not from code. | M |
| FR-PLT-6 | Customer jobs, reference images, acceptance data and notes shall live in each customer project, outside this repository; the platform code and its examples contain no customer words. | M |
| FR-PLT-7 | The user shall be able to create a job, draw and test tool regions on the live image, and save it, from the screen. | M |
| FR-PLT-8 | Locators shall be plugins like tools (`fixed` first; template and color/outline locators next). | M |

---

## 4. Non-functional requirements

### 4.1 Performance (PERF)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-PERF-1 | Time from the object being still to the result on screen: project value (proposed: ≤ 1.5 s with the classical tools on the specified PC). The pipeline reports its own timings. | M |
| NFR-PERF-2 | Throughput: one inspection per presented object with no missed objects, up to a project value (proposed: 20 per minute). | M |
| NFR-PERF-3 | Inference shall run on the CPU of the specified PC. No GPU is required. | M |
| NFR-PERF-4 | The live image on the operator screen shall update at ≥ 10 fps. | S |

### 4.2 Accuracy (ACC)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-ACC-1 | Detection rate (a real defect flagged FAIL): project value (proposed: 99 %). The platform measures it on the job's reference set and on labeled results. | M |
| NFR-ACC-2 | False-reject rate (a good object flagged FAIL): project value (proposed: 1 %). | M |
| NFR-ACC-3 | Accuracy shall be measured on a test set collected at the station, not used for training, covering every variant of the job and the light of a full day. | M |
| NFR-ACC-4 | The result shall not change when the object is placed within the job's placement tolerance (proposed: ±30 mm and ±10°) of its nominal position, when the job has a locator. | S |

### 4.3 Reliability and recovery (REL)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-REL-1 | The system shall run unattended for a full shift (proposed: 10 h) and across days without needing a restart. | M |
| NFR-REL-2 | After a power loss or PC restart, the system shall return to inspecting with the last active job, without operator action, within 2 min. | M |
| NFR-REL-3 | After a camera disconnect, inspection shall resume automatically within 30 s of the camera returning. | M |
| NFR-REL-4 | A complete reinstallation on a new PC from a backup file, by the Maintainer, shall take ≤ 1 hour, including verification. | M |
| NFR-REL-5 | Restoring a backup on a new installation shall give the same results on the jobs' reference images as the original installation. | M |
| NFR-REL-6 | A crash of the inspection process shall be detected and the process restarted automatically, with the crash logged. | S |

### 4.4 Usability (USA)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-USA-1 | An operator shall understand the result and the reason after a training of at most 15 minutes. | M |
| NFR-USA-2 | The result shall be readable from the operator's working position (proposed: ≥ 2 m), using colour **and** text, not colour alone. | M |
| NFR-USA-3 | The Supervisor shall be able to export a backup and restore a job by following the written procedure, without the Maintainer present. | M |

### 4.5 Portability and platform (POR)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-POR-1 | The system shall run on Windows 11 (64-bit). | M |
| NFR-POR-2 | The inspection core shall not depend on Windows-only libraries, so it can also run on Linux. | S |
| NFR-POR-3 | The job file format shall not depend on the operating system: paths relative, text files in UTF-8. | M |
| NFR-POR-4 | Adding a new camera model shall need only a new camera driver module, with no change to inspection or job code. | M |

### 4.6 Maintainability (MAI)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-MAI-1 | The job file format shall be documented (deliverable D8) and versioned. Newer software shall read older job files. | M |
| NFR-MAI-2 | Application logs shall be kept with rotation (proposed: 30 days) and be easy to collect for remote support. | M |
| NFR-MAI-3 | The code shall have automated tests for job export/import and for the tools, run against stored reference images. | S |
| NFR-MAI-4 | The design shall stay simple enough for one developer to maintain. | M |

### 4.7 Security (SEC)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-SEC-1 | Camera passwords and user passwords shall not be stored in plain text. Job files shall not contain camera passwords. | M |
| NFR-SEC-2 | The IP camera shall be on a network segment or port dedicated to the inspection PC, where possible. | S |
| NFR-SEC-3 | Remote access for support, if any, shall follow the site's IT policy. | M |

### 4.8 Legal and licensing (LIC)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-LIC-1 | Every shipped component, including model weights and training code that produced them, shall have a license that allows closed commercial use (e.g. MIT, BSD, Apache 2.0), or a commercial license shall be bought. | M |
| NFR-LIC-2 | A list of third-party components and their licenses shall be delivered with the software. | M |

### 4.9 Environment and storage (ENV)

| ID | Requirement | Pri. |
|---|---|---|
| NFR-ENV-1 | The system shall keep working under the light variation of a full day at the station (ceiling lamps and windows), or flag ERROR when the image leaves the job's limits. | M |
| NFR-ENV-2 | Disk usage for records shall stay within a configured limit (proposed: 100 GB), enforced by FR-LOG-3. | M |

---

## 5. Use cases

### UC-01 — Inspect an object (main flow)

| | |
|---|---|
| Actor | Operator (primary), Camera, External system (optional) |
| Goal | Know whether the object at the station is right before it moves on |
| Preconditions | System running, active job verified, camera connected |
| Trigger | The object is presented and stays still, or an external or manual trigger |

**Main flow**
1. The Operator (or the machine) presents the object at the station.
2. The system detects an object present and still, or receives the external or manual trigger.
3. The system captures a fresh frame.
4. The system checks image quality (brightness, sharpness) against the job's limits and reference.
5. The system runs the job's locator, if any, and places the ROIs.
6. The system runs every tool of the job, in order.
7. The system shows PASS, FAIL or ERROR with the reason, and draws the regions (green passed, red failed).
8. The system records the result (and the image, per FR-LOG-2).
9. The object is removed. The system shows the job's waiting text and waits for the next one.

**Alternative / exception flows**
- 4a. Image too dark, too bright, flat or out of focus → ERROR with the specific reason ("Imagem escura demais, verificar a iluminação"). Go to 8.
- 5a. The locator does not find the object → ERROR, "Objeto não encontrado na posição esperada". Go to 8.
- 6a. A region falls outside the image, or a tool breaks → ERROR. Go to 8.
- 7a. FAIL → the object is fixed and presented again. The system treats it as a new inspection.
- 2a. The object is removed before the result → no result recorded; logged as "inspeção interrompida".
- Any step: camera lost → UC-09.

**Postconditions:** a record exists for the inspection. Counters are updated.

Covers: FR-ACQ-6/7, FR-TRG-1..4, FR-INS-*, FR-UI-1..4, FR-LOG-1/2.

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
4. The system shows "Job verificado" and starts inspecting with the new job.

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
4. The Maintainer chooses a locator (or none) and draws the ROIs on the reference.
5. The Maintainer adds tools (`color`, `pattern`, `code`, `detect`), one per ROI, sets their parameters and writes each failure reason in Portuguese.
6. The Maintainer tests the job live with good and defective objects and adjusts the parameters.
7. The Maintainer saves the reference set: the images used in step 6, with their expected results.
8. The Maintainer saves the job. A new version is created and an automatic backup is made.

**Exceptions**
- 6a. Good and bad objects can't be separated by thresholds → the Maintainer marks the job as needing a model and starts UC-08.

Covers: FR-JOB-2/4/5/10, FR-INS-2..5/10, FR-PLT-7, FR-ACQ-8.

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
2. The system checks integrity and format version (FR-JOB-8).
3. The system lists what the file contains and what it will replace. The user confirms.
4. The system stores the jobs. Existing versions are kept, not overwritten.
5. For the job to be activated, the system runs verification (FR-JOB-9): apply settings, read back, capture, compare with reference, run tools on reference images.
6. The system shows the verification report. If it passed, the job becomes active.

**Exceptions**
- 2a. Damaged or incompatible file → refused, with the reason. Nothing is changed.
- 5a. Verification fails (e.g. camera mounted differently on a new installation) → the job is stored but not activated. The Maintainer adjusts (UC-03) or overrides with a recorded reason.
- 3a. The file came from the other camera type → settings that don't apply are listed for review (FR-JOB-11).

Covers: FR-JOB-8/9/11, NFR-REL-4/5.

---

### UC-06 — Replace the PC or the camera

| | |
|---|---|
| Actor | Maintainer |
| Goal | Return to production after a hardware failure |
| Preconditions | Latest backup file available |

**Main flow**
1. The Maintainer installs the application on the new PC, or connects the new camera.
2. The Maintainer sets the system settings that aren't part of the jobs (camera address and password, backup folder).
3. The Maintainer restores the backup (UC-05).
4. For each job in use, the system runs verification. The Maintainer adjusts focus or position if the camera mount changed.
5. The Maintainer runs a few known good and bad objects to confirm.

**Postcondition:** production resumes within NFR-REL-4.

---

### UC-07 — Review failures and correct results

| | |
|---|---|
| Actor | Supervisor |
| Goal | Understand failures and feed corrections back into training |

**Main flow**
1. The Supervisor opens the results screen and filters by date, job and result.
2. The Supervisor opens a result and sees the image with the problem area and the scores.
3. If the result was wrong, the Supervisor marks it "Resultado incorreto" and picks the correct one.
4. The system adds the image to the training set with the correct label (FR-MDL-2).
5. Optionally, the Supervisor exports the filtered results to CSV.

Covers: FR-LOG-4, FR-MDL-2.

---

### UC-08 — Collect images and update the model

| | |
|---|---|
| Actor | Maintainer |
| Goal | Train or improve the model used by a job |

**Main flow**
1. The Maintainer turns on collection mode for the job (FR-MDL-1) for a period that covers different times of day.
2. The Maintainer exports the collected and corrected images.
3. Outside the system, the Maintainer labels the images, trains and exports the model.
4. The Maintainer loads the new model into the job.
5. The system runs the new model on the reference images and the test set, and shows the comparison with the current model (FR-MDL-4).
6. If the new model is better, the Maintainer accepts it. A new job version is created and backed up.

**Exceptions**
- 5a. The new model is worse on any reference image → the Maintainer must confirm explicitly. The old version remains restorable.

---

### UC-09 — Camera lost and recovered

| | |
|---|---|
| Actor | System; Operator (informed) |
| Trigger | No frames from the camera for more than a short timeout |

**Main flow**
1. The system detects the loss and shows "Câmera desconectada" in yellow. No PASS is shown while the camera is lost.
2. The system retries the connection periodically.
3. When the camera returns, the system reapplies the job's camera settings and reads them back.
4. The system compares a frame with the reference image.
5. The system returns to the job's waiting text (`ui.waiting`, e.g. "Aguardando peça").

**Exceptions**
- 4a. The frame doesn't match the reference → as UC-02 3a.

Covers: FR-ACQ-5, NFR-REL-3.

---

### UC-10 — Start-up after power loss

| | |
|---|---|
| Actor | System |
| Trigger | The PC powers on |

**Main flow**
1. Windows starts. The application starts automatically (FR-ADM-2).
2. The system loads the last active job and runs the camera steps of UC-02 (apply, read back, compare).
3. The system shows the operator screen with the job's waiting text.

**Exceptions**
- 2a. The camera isn't ready yet (the IP camera boots slower than the PC) → keep retrying as in UC-09.

Covers: NFR-REL-2.

---

## 6. Traceability summary

| Use case | Main requirements |
|---|---|
| UC-01 Inspect an object | FR-ACQ-6/7, FR-TRG-*, FR-INS-*, FR-UI-1..4, FR-LOG-1/2, NFR-PERF-1/2, NFR-ACC-* |
| UC-02 Select job | FR-JOB-1/3/9, FR-ACQ-4/8 |
| UC-03 Create/tune job | FR-JOB-2/4/5/10, FR-INS-2..5/10, FR-PLT-7 |
| UC-04 Export / backup | FR-JOB-6/7/10, NFR-USA-3 |
| UC-05 Import / restore | FR-JOB-8/9/11, NFR-REL-4/5 |
| UC-06 Replace PC or camera | UC-05, NFR-REL-4, NFR-POR-4 |
| UC-07 Review failures | FR-LOG-4, FR-MDL-2 |
| UC-08 Update model | FR-MDL-*, FR-JOB-5 |
| UC-09 Camera lost | FR-ACQ-5, NFR-REL-3 |
| UC-10 Start-up | FR-ADM-2, NFR-REL-2 |

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
| What happens on FAIL beyond the screen | FR-INT-2 | screen only |
| Order/batch number source | FR-LOG-6 | none |
| Backup destination | FR-JOB-10 | network share + USB drive |
| Recovery time after power loss | NFR-REL-2 | 2 min |
