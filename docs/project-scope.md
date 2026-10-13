# Packaging Vision System — Project Scope

| | |
|---|---|
| Document | 01 — Project Scope |
| Version | 0.1 (draft) |
| Date | 2026-10-02 |
| Author | Lucas (developer and maintainer) |
| Status | For review with the client |

Related documents: 02 — Requirements and Use Cases · 03 — Architecture ("job" model) · 04 — Technical Decisions · Bancada Virtual de Visão (simulator).

---

## 1. Purpose

Define what the packaging vision system will and will not do, what will be delivered, in which phases, and under which assumptions. This document is the reference for agreeing on scope with the client before detailed requirements and architecture are fixed.

## 2. Background

- At the packing station, each box is placed on a scale at a fixed position. The client needs an automatic check that every box leaves the station **closed and taped**.
- Two tape types are in use: **colored tape** (red) and **transparent tape with a printed logo**.
- Boxes come in several sizes (currently **P, M, G, GG**), inspected with the same fixed camera.
- The client already operates a **commercial vision camera** that stores its configuration as **"jobs"**. They expect the same here: the configuration must be saved as a file and restorable if it is lost.
- An interactive simulator (Bancada Virtual de Visão) already exists to choose camera, lens, height and lighting before buying, and to explain those choices to the client.

## 3. Objectives

1. Inspect every box placed on the scale and give a clear **pass / fail** result with the reason (e.g. "tape missing on part of the seam").
2. Support the box sizes and tape types in use, with the camera fixed.
3. Keep all inspection settings in **jobs**: one job per product or box type, exportable to and importable from a **single backup file**.
4. Restore a job onto a replacement PC or camera and get the **same inspection behavior**, verified automatically.
5. Run on a **PC bought by the client** (expected Windows 11).
6. Prototype with a **Logitech C920** USB webcam, then move to the final **Hikvision IP camera with motorized lens** without rewriting the inspection logic.

## 4. In scope

### 4.1 Software
- Image acquisition from both camera types (USB webcam for the prototype, Hikvision IP camera for production).
- Inspection of box closure and tape:
  - classical checks (color area for colored tape, logo search along the seam for logo tape);
  - a trained detection or anomaly model where classical checks are not enough.
- Job management: create, edit, select, export, import, restore with verification.
- Operator screen showing the live image, the result and the reason for a failure.
- Logging of results and of the images that support them (retention period to be defined).

### 4.2 Hardware specification (not purchase)
- Camera, lens, mounting height and lighting, chosen with the simulator and validated on site.
- Minimum PC specification for the client to buy.

### 4.3 Model
- Image collection at the station, labeling, training, validation and export of the model used in production.

### 4.4 Documentation and handover
- Installation guide, operator guide, and job backup/restore procedure.

## 5. Out of scope

Unless added by a later agreement:

- Purchase and installation of the PC, network and electrical infrastructure.
- Mechanical work: conveyors, reject devices, camera brackets beyond specifying them.
- Programming of the client's PLC or other systems (the system will expose results; integration is a separate item).
- Inspection of anything other than closure and tape (labels, barcodes, box damage, contents, weight).
- More than one inspection station or camera.
- Cloud services and remote dashboards.

## 6. Deliverables

| # | Deliverable | Form |
|---|---|---|
| D1 | Project scope (this document) | Markdown |
| D2 | Requirements and use cases | Markdown |
| D3 | Architecture ("job" model) | Markdown |
| D4 | Technical decisions | Markdown |
| D5 | Simulator (Bancada Virtual de Visão) | Web page — already published |
| D6 | Prototype software with the C920 | Installable application |
| D7 | Production software with the Hikvision camera | Installable application |
| D8 | Job file format specification | Markdown |
| D9 | Trained model and the dataset used to train it | Files |
| D10 | Installation guide, operator guide, backup/restore procedure | Markdown / PDF |

## 7. Phases

Dates are to be defined with the client.

| Phase | Goal | Exit criteria |
|---|---|---|
| 0 — Definition | Scope, requirements, architecture, decisions; hardware chosen with the simulator | Documents D1–D4 approved |
| 1 — Prototype (C920) | Capture, classical checks, first job format, image collection on site | Pass/fail shown live on the bench; a job exported and restored on another PC |
| 2 — Model | Label images, train, validate against held-out images | Accuracy target (section 11) met on held-out images |
| 3 — Production camera | Hikvision driver, on-site installation, tuning | System running at the station with the final camera |
| 4 — Acceptance and handover | Acceptance tests, guides, training of the client's staff | Acceptance criteria met and signed off |

## 8. Stakeholders

| Who | Role |
|---|---|
| Client (management) | Approves scope, buys hardware, accepts the system |
| Operators | Place boxes on the scale and react to results |
| Client's responsible for jobs | Selects jobs, keeps the backup file (to be named) |
| Lucas | Sole developer and maintainer |

## 9. Assumptions

- The camera and the scale are fixed; boxes are placed in a repeatable area of the scale.
- The environment is relatively clean. Ambient light comes from ceiling lamps and windows, so it changes during the day (already modeled in the simulator).
- The client buys the PC and is expected to choose Windows 11; Linux is possible only if requested and approved.
- The IP camera is connected by wired Ethernet.
- The client provides access to the station to collect images, including real failures (open boxes, missing tape).

## 10. Constraints

- **Licensing:** no component that forces the client's software to be open-sourced (e.g. AGPL-licensed model frameworks) may be shipped unless a commercial license is bought.
- **Operating system:** the client's staff only knows Windows.
- **Hardware availability in Brazil:** Hikvision chosen for the IP camera because alternatives are hard to find locally.
- **Team:** one developer; the design must stay simple to maintain.

## 11. Acceptance criteria (high level)

Numbers marked TBD are to be agreed with the client in document 02.

1. Correctly flags boxes with missing or incomplete tape and open boxes, with a detection rate of **TBD %** and a false-reject rate of **TBD %**, measured on a test set collected at the station.
2. Produces a result within **TBD seconds** after the box settles on the scale.
3. Keeps working across a full working day of natural light variation.
4. A job exported from one installation, imported into a fresh installation, gives the same results on the job's reference images.
5. An operator without technical training can read the result and the reason for a failure.

## 12. Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| C920 settings (focus, exposure) reset or are ignored, especially on Windows | Unstable images during the prototype | Use the C920 only for the prototype; reapply and verify settings on every start |
| Transparent tape is hard to see; reflections from lamps | Missed defects | Logo search along the seam; diffuse lighting; validated in the simulator |
| Daylight from windows changes during the day | Results vary by time of day | Fixed exposure and white balance per job; tests across a full day |
| Red objects near the box (e.g. operator's red shirt) confused with red tape | False passes | Inspect only a region of interest on the seam |
| Few real failure images available | Weak model | Start with classical checks; consider anomaly detection trained on good boxes only |
| IP camera video stream drops or lags | Missed or delayed results | Wired network, reconnection logic, snapshot on trigger |
| Model licensing | Legal exposure for the client | Use permissively licensed models (see document 04) |

## 13. Open questions for the client

1. What must happen when a box fails: only a message on screen, an alarm, or a signal to another system (PLC, MES)?
2. How many boxes per minute pass through the station?
3. Does the scale provide a "weight stable" signal the system can use as the trigger?
4. How many products or box types need separate jobs, and who may create or change them?
5. How long must results and images be kept, and must they be linked to an order or batch number?
6. Does "closed" mean only "taped", or must the system also check that the flaps are fully closed?
7. Language of the operator screen (Portuguese assumed).
