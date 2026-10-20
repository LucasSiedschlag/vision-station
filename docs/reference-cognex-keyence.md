# Vision Station — Reference: Cognex In-Sight and Keyence IV

| | |
|---|---|
| Document | 09 — Market reference (Cognex In-Sight EasyBuilder, Keyence IV / IV3) |
| Version | 0.4 — accepted as the model (2026-10-18): §18 items 38–44 decided in TD-32, the open points of §22 settled. 0.3 — who owns what, job versus sensor (§19); Cognex *AcquireImage* as the model of the acquisition block (§20); the station layer (§21); our configuration flow checked against both (§22); sources moved to §23. 0.2 — §18 items 4, 5, 6, 21, 22, 23, 29 decided (TD-31). 0.1 — first version |
| Date | 2026-10-18 |
| Author | Lucas (developer and maintainer) |
| Status | Reference. Facts come from the vendors' public documentation (links in §23). Where a page does not say something, this document says "not documented" instead of guessing. The comparison with Vision Station and the proposals are in §18; nothing here changes a requirement by itself. §19–§22 describe the shape the references share and where we differ. The owner accepted them as the model on 2026-10-18; the decisions that follow are TD-32 (§18 items 38–44). |

Related documents: 02 — Requirements · 03 — Architecture (§14 fixtures, §15 tools, §16 machine interface) · 05 — Frontend (§4.3 order of work, §7.3 editor, §19 vision controls) · project documents 05 (OPC UA for Machine Vision) and 06 (generic vision systems).

---

## 1. Why this document

Cognex and Keyence have sold configurable vision systems for decades, and their products set what an integrator expects: which steps a setup has, which trigger modes exist, which signals a PLC finds, what an output line can do. When Vision Station makes a design choice that the market has already settled, it should follow the market unless there is a reason not to, and that reason should be written down.

This document collects, in one place, **what the two reference products do**, feature by feature, with the exact setting names, ranges and defaults from their documentation. Each section ends with a short note on Vision Station. §18 consolidates those notes into a table of what we adopt, what we already have and what we propose.

**Products covered:**

| Vendor | Product | Kind | Documentation used |
|---|---|---|---|
| Cognex | **In-Sight** smart cameras, configured in **EasyBuilder** (In-Sight Explorer) | Smart camera: sensor, lens, light and processor in one body; a PC tool configures it | In-Sight Explorer help, versions 5.7 to 6.2 (`docs.cognex.com/is_573` … `is_621`); In-Sight 2D / Vision Suite pages for industrial communications |
| Cognex | **In-Sight 2800** | Smart camera with *edge learning* (classification trained on the device) | Cognex blog and product pages |
| Keyence | **IV series** | Vision sensor: camera head + amplifier, set up on a monitor with the *Setup Navigator* | IV Series User's Manual (Monitor) |
| Keyence | **IV3 series** | Successor of IV: AI-based detection and imaging, smart cameras and amplifier heads | IV3 functional specifications page |

The two products sit at different points:
- **Cognex In-Sight** is a smart camera with a large tool set and a spreadsheet underneath. EasyBuilder is its guided front-end.
- **Keyence IV/IV3** is a vision *sensor*: fewer tools, a fixed four-step setup, and a strong focus on "register a good part, register bad parts, let the sensor set the thresholds".

Vision Station is a PC-based system for fixed stations. It sits between the two: Keyence's simplicity of setup, Cognex's breadth of tools and integration.

---

## 2. The setup flow

### 2.1 Cognex EasyBuilder: nine application steps

| # | Step | What it configures |
|---|---|---|
| 1 | **Get Connected** | Connect to a sensor or the emulator; open a job or start a new one |
| 2 | **Set Up Image** | Acquire or load an image; acquisition settings (trigger, exposure, light, focus); calibration to real units |
| 3 | **Locate Part** | A *Location Tool* configured as a **fixture**: the reference point that other tools follow |
| 4 | **Inspect Part** | *Inspection Tools* that examine, qualify or quantify the part |
| 5 | **Inputs/Outputs** | Discrete I/O lines: names, signal types, edges, forcing for tests |
| 6 | **Communication** | OPC, EasyView for the VisionView panel, network and serial protocols, FTP |
| 7 | **Filmstrip** | Which images are stored for review, on the sensor or the PC |
| 8 | **Save Job** | File management while the sensor is **Offline** (or Online, if *Allow Online Job Save* is enabled for the user) |
| 9 | **Run Job** | Run, review results, adjust and troubleshoot |

### 2.2 Keyence IV: the Setup Navigator, four steps

| # | Step | What it configures |
|---|---|---|
| 1 | **Image Optimization** | Trigger options, automatic brightness adjustment, focus |
| 2 | **Master Registration** | The master image: the good part at the reference position |
| 3 | **Tool Settings** | Detection tools and the position adjustment tool |
| 4 | **Output Assignment** | What each output line means |

After the navigator, thresholds are refined in **Test mode** (*Limit Adjustment*) or automatically by **Tool Auto Tuning** from OK and NG images (§7.2).

### 2.3 Vision Station

Document 05 §4.3 already follows both orders: 1 Imagem → 2 Amostras → 3 Âncora → 4 Ferramentas → 5 Disparo e qualidade → 6 Resultado e saídas → 7 Validar → 8 Salvar e ativar. It differs in two ways:
- **Samples come second**, as in Keyence (master registration before tools), and are a set of good *and* bad parts, as in Keyence's auto tuning. Cognex has no explicit sample step: images come from the live camera or the filmstrip.
- **Trigger is step 5**, not step 1. Cognex sets the trigger in *Set Up Image* and Keyence in *Image Optimization*. Because the trigger decides how every inspection starts, the editor now also shows it in its top bar (document 05 §4.2).

---

## 3. Image acquisition: Trigger Controls

### 3.1 Cognex: trigger types

Set in *Set Up Image › Edit Acquisition Settings › Trigger*.

| Type | Acquires an image when… |
|---|---|
| **Camera** (default on the Trigger Controls page) | A rising edge arrives at the sensor's **dedicated acquisition trigger input**. Faster than *External*. |
| **Continuous** | Always: free-running, as fast as possible, or at the *Interval* |
| **External** | A serial command, or an edge on a general-purpose input line configured as *Acquisition Trigger* (§9.1) |
| **Manual** | The user presses **F5** (or the *TRG* button) |
| **Industrial Ethernet** (also *Network*) | The PLC sets the *Trigger* bit over EtherNet/IP, PROFINET, POWERLINK, SLMP Scanner or CC-Link IE Field Basic (§10.2) |
| **Timestamp** | A PLC sends a timestamp trigger over EtherNet/IP (only some In-Sight 5000, 7000 Gen2 and 9000 models) |

**Where it lives (§19, §20):** the trigger type is a parameter of `AcquireImage`, the function that sits permanently in cell A0 of the job, so it is saved with the job. Which physical line or protocol delivers an *External* trigger is a sensor setting (*Discrete I/O Settings*, §9.1).

**Timing settings:**

| Setting | Range | Default | Applies to |
|---|---|---|---|
| **Trigger Delay** | 0 – 10 000 ms | 0 | *Camera* and *Network*: wait between the trigger and the start of acquisition. Also delays the *Acquisition Start* and *Strobe* outputs |
| **Trigger Interval** | 0 – 10 000 ms | 500 ms (one page of the In-Sight 2000 help gives 0) | *Continuous*: time between acquisitions. The real interval is longer when the job takes longer than the interval |

**Limits that matter:**
- *External* triggering is not supported on the In-Sight 2000 series.
- The output *ERR: Missed Acquisition* works only with *Camera* (§9.2).

### 3.2 Keyence IV: trigger options

Set in *Image Optimization › Trigger Options*.

| Setting | Applies when | Range | Default | Meaning |
|---|---|---|---|---|
| **Trigger** | always | *Internal* / *External* | **Internal** | When imaging starts |
| **Trigger interval** | *Internal* | 1 – 10 000 ms | 50 ms | The sensor images continuously at this interval |
| **Trigger Delay** | *External* | 0 – 1 000 ms | 0 ms | Wait between the trigger input and imaging, for when the trigger signal comes before the part is in place |

**External** means a photoelectric sensor or a PLC on input **IN1** (§9.3). While setting up, the operator can image with a temporary internal trigger. There is a separate **Trigger Error** output (§9.4), and the RUN screen counts triggers and trigger errors (§14).

**Where it lives (§19):** *Trigger Options* is the first screen of the Setup Navigator, the per-program setup (§2.2). The electrical side of the trigger, IN1 and its rising or falling edge, is a sensor setting under *Sensor Advanced › Environmental › I/O Settings*.

### 3.3 Signals around the trigger

Both vendors tell the machine more than "here is the result":

| Signal | Cognex | Keyence |
|---|---|---|
| Acquisition started | *Acquisition Start* output (always pulsed) | — |
| Acquisition finished (the part may move) | *Acquisition End* output; *Exposure Complete* status bit on Industrial Ethernet | — (BUSY covers it) |
| Cannot accept a trigger now | *Trigger Ready* low (Industrial Ethernet); *System Busy* output | **BUSY** output: imaging, judging, switching programs, registering an external master |
| A trigger was lost | *ERR: Missed Acquisition* (trigger before the previous acquisition ended, or no free buffer); *Acquisition Error* bit | **Trigger Error** output; trigger error count |

### 3.4 Vision Station

Vision Station has **four modes** (job `trigger.mode`, FR-PLT-3): *Pela imagem* (`image_presence`), *Pela máquina* (`external`), *Botão* (`manual`), *Contínuo* (`continuous`).

| Market | Vision Station |
|---|---|
| Cognex *Camera* | Not applicable to UVC cameras (no trigger input). With a GenICam camera (FR-ACQ-9, phase F) the hardware trigger is a camera setting, still in mode *Pela máquina* |
| Cognex *External*, *Industrial Ethernet*; Keyence *External* | **Pela máquina**. The source (24 V input through remote I/O, S7, Modbus TCP, OPC UA, local API) is chosen once in *Configurações › Máquina*, not per job |
| Cognex *Manual* | **Botão** |
| Cognex *Continuous*; Keyence *Internal* | **Contínuo**, with one difference: we never inspect a frame taken while the scene moves (FR-TRG-5) |
| Cognex *Timestamp* | Not applicable |
| — (no equivalent) | **Pela imagem**: presence and stillness detected in the image. Neither vendor documents this as a trigger type |

**Gaps** (proposals in §18): a **trigger delay** for *Pela máquina* and an **interval** for *Contínuo*; both vendors have both. The missed-trigger signal already exists: `TriggerRefused` pulses when a trigger arrives while not ready (architecture §16.2), the equivalent of Cognex *Acquisition Error* and Keyence *Trigger Error*. What is missing is **counting** it in the statistics, as Keyence does.

---

## 4. Image acquisition: image settings

### 4.1 Cognex (In-Sight 2000 EasyBuilder Lite page; other models have more)

| Group | Setting | Range / default | Meaning |
|---|---|---|---|
| Lighting | **Auto Exposure** | off by default | Recalculates exposure after each acquisition |
| | **Manual Exposure** | on by default | Fixed exposure |
| | **Target Image Brightness** | 0 – 100, default 50 | For auto exposure: the allowed percentage of saturated pixels in the exposure region |
| | **Exposure (msec)** | 0.000 – 1000.000, default 0.250 | |
| | **Exposure Region** | *Set Region*, *Reset to Default Region* | Area used to compute exposure |
| | **Optimal Exposure** | button | Computes the exposure **once**, then keeps it |
| | **Light Intensity** | 0 – 100, default 70 | Integrated LED intensity, saved with the job |
| | **Light Control Mode** | *On (Exposure)* (default) / *Off* | Light only during exposure, or ambient light only |
| Focus (autofocus models) | **Autofocus Region**, **Autofocus** button | | Focus on a chosen area |
| | **Autofocus On Job Load** | off by default | Off: the focus distance is saved with the job. On: autofocus at each job load |
| | **Focus Distance (%)** | 0 – 100 | 0 = closest plane, 100 = infinity |
| White balance (colour models) | **White Balance Region**, **Set White Balance** | | On a flat white target; requires manual exposure; saved with the job |
| Image | **Image Area Height** (*Start Row* / *End Row*) | full height by default | Acquire only a band of rows, to save time |
| | **Image Magnification Mode** | model-dependent | Half the field of view, double the resolution |
| | **Calibration Type** | *Field of View* (known width → mm, cm, in) / *Import* (N-point calibration file) | Results in real units |

Gain is not described on that page.

### 4.2 Keyence

- **Auto Brightness Adjustment** sets light intensity and shutter speed from the target's shape and surface (colour, shine, material). The IV3 adds **AI-Based Imaging**, which sets illumination intensity, flash method and exposure time automatically.
- **Focus Adjustment**, with auto focus. On IV3 sensor heads, focus can be adjusted automatically at installation; it is disabled during operation, and a separate focus position can be stored per program.
- IV3 capture functions: **digital zoom** (2×, 4×), **HDR**, **High gain**, **Colour filter**, **White balance**, **Brightness correction**; pulse or continuous lighting. Exposure 12 µs – 9 ms (heads) or 10 ms (smart cameras).
- **Scaling function** (units) is listed among tool functions.

### 4.3 Vision Station

Step 1 *Imagem* covers exposure, gain, white balance, focus and zoom, with a histogram and a focus meter (document 05 §19.5), and FR-ACQ-4 reads every setting back. Things worth taking:
- **"Auto once, then lock"** (Cognex *Optimal Exposure*). Document 05 already has *Auto uma vez* in `ExposureControl`; keep it.
- **Exposure region** for the auto computation. Not in our docs yet.
- **Focus saved with the job vs autofocus at job load** (Cognex) and **focus per program** (Keyence). We store zoom and focus per job (FR-ACQ-8); same idea.
- **Calibration** to mm (FR-INS-15) matches Cognex *Field of View*.

---

## 5. Reference image (master)

### 5.1 Keyence: Master Registration

- Place a good part at the reference position, tap *Register Live Image as Master*, image it (external trigger, or a temporary internal trigger), confirm.
- Other sources: the **sensor's image history**, or a **USB** image.
- **Brightness correction** is part of the step.
- IV3: **Multi-master image registration**, and an **External master image registration** input (re-register the master from the line).
- Registering a new master resets some outline settings, which then have to be set again.

### 5.2 Cognex

There is no separate master step. Each location or inspection tool trains its own model on the current image (for example *Train* on the PatMax tools).

### 5.3 Vision Station

Step 2 *Amostras* holds the reference image plus labelled good and bad samples (document 05 §4.3). Keyence's model is the closest. Two ideas we do not have:
- **Register from history:** turning a recorded production image into the reference or into a sample. Our results browser keeps images (FR-LOG-2); a "use as sample" action would close the loop.
- **External master registration:** a machine input that re-teaches the master. We deliberately do not do this. A new reference is a new job version that must pass verification (architecture §7.3).

---

## 6. Locating the part

### 6.1 Cognex: fixtures

- *Locate Part* creates a **fixture**: a reference point (X, Y, angle, scale) that other tools follow.
- The user picks a **feature type** that appears in every image (**pattern, edge, circle or blob**) and a matching Location Tool.
- **Several fixtures** per job, and fixtures can be **linked** to each other.
- A fixture is unnecessary when the part is always in the same place.
- Many **inspection** tools can also output a fixture: Edge, PatMax Pattern, Pattern Presence/Absence, the ID tools, Angle and Distance, the circle measurement tools and several Geometry tools.
- Each tool chooses its **Input Fixture** (§7.1).

**PatMax / PatMax RedLine settings** (Presence/Absence tool; the Location tools share the parameters):

| Setting | Range / default | Meaning |
|---|---|---|
| **Accept Threshold** | 0 – 100 / 50 | Minimum similarity to the model. Higher is faster but stricter |
| **Contrast Threshold** | RedLine 0 – 100 / 0; PatMax 0 – 255 / 10 | Minimum contrast of a found pattern |
| **Angle Tolerance** | ±0 – 180° / 15° | Rotation accepted. Wider is slower |
| **Scale Tolerance** | 0 – 50 % / 0 | Size variation accepted, ± |
| **Find Mode** | *PatMax* / *PatQuick* | Accurate or fast (not on RedLine) |
| **Strict Scoring** | off | Missing or occluded features lower the score |
| **Ignore Polarity** | off | Light-on-dark and dark-on-light both match |
| **Invert** | off | Reverses pass/fail |
| **Timeout** | 0 – 30 000 ms / 5 000 ms | Search time limit; exceeded → Fail |
| *Result* | *Present* / *Not Present* | Not Present when nothing is found **or more than one instance is found** |

The location tools publish **Fixture.X, .Y, .Angle, .Scale, .Score**, plus Pass/Fail/Error counts.

### 6.2 Keyence: Position Adjustment

- Measures how far the target is off-centre from the master and **moves the detection tools' search areas** accordingly.
- **One** position adjustment tool per program; it applies to every detection tool.
- IV3 adds **High-speed position adjustment** (1-axis or 2-axis edge) and **Multi-position adjustment**.
- **If position adjustment fails:** its result is **NG**, the **total status is NG**, and the detection tools are **not judged**. A dedicated output (*Pos. Adj.*) reports it.

### 6.3 Vision Station

Architecture §14 follows Cognex: pose-based fixtures, chains of fixtures (FR-INS-12), upright region cuts, allowed angle and scale ranges.

**One deliberate difference:** when the part is not found, both vendors give a **Fail/NG**. Vision Station gives **ERROR E201/E202**: "the object is not where the job can judge it". This keeps our rule *never a false PASS* and also *never a false FAIL*. A missing part is not a defective part, and the machine may handle the two differently (reject versus stop and call someone). The PLC can still treat ERROR like NG if the project wants that. Keep it.

**Worth taking from Cognex:**
- **Contrast threshold** as a separate criterion from the score.
- **"More than one found → Not Present"**: a presence tool that sees two parts should not pass.
- **Timeout per search**, ending in a defined result. Ours maps a timeout to E302/E303.

---

## 7. Judgment: tools, limits and the job result

### 7.1 Cognex

**Per-tool general settings** (most Inspect tools):

| Setting | Meaning |
|---|---|
| **Enabled** | The tool runs or not; can be linked to another value (conditional tool) |
| **Input Image** | The acquired image, or another tool's output image (filters) |
| **Input Fixture** | Which fixture the region follows |
| **Input Region** | The region analysed; can be another tool's region |
| **Include In Job Pass** | Whether the tool's result counts towards **Job Pass** |
| **Show Graphics** | The tool's overlay on or off |
| **Description** | Free text |

- Each tool has its own pass criteria (for example *Accept Threshold* and *Invert* above).
- **Job Pass** combines the tools that are included.
- The **Logic** and **Math** tools build other combinations.
- Tools keep **Pass_Count, Fail_Count, Error_Count**.

### 7.2 Keyence

- Each detection tool judges a **matching rate** (degree of similarity) or a measured value against a **threshold**. OK if the value is above the threshold, NG if below.
- **Limit Adjustment** (manual) works in Test mode. Image a good and a bad part, read their matching rates, set the threshold between them. The manual's example: good above 90, bad below 40 → threshold **65, the midpoint**. Slider or typed value. A histogram of earlier values guides the choice.
- **Tool Auto Tuning** sets each tool's threshold automatically from **several OK and NG images**. The images come from three sources:
  - Test-mode captures;
  - the sensor's image history;
  - USB files.

  Earlier registrations can be reused. The manual does not document the method or a minimum number of images.
- **Total Status** is computed with one of these rules:
  - **All Tools OK** (default);
  - **Any Tool OK**;
  - **Logic 1 – 4** (user logic).
- IV3: **Threshold changing in RUN** (adjust without leaving operation); **Additional learning** for the Learning tool.

### 7.3 Vision Station

| Market | Vision Station |
|---|---|
| Cognex *Include In Job Pass* | `affects_result` (FR-INS-13), informative tools |
| Cognex *Show Graphics* per tool | Overlay layers (document 05 §18) apply to all tools. A per-tool switch is not planned |
| Cognex *Enabled* linked to a value | Not planned (jobs carry data, never code; CLAUDE.md rule 10) |
| Keyence *Limit Adjustment* with the midpoint | **The same rule**: *Ajustar pelas amostras* proposes the middle of the widest gap (FR-UI-14). Keyence confirms the choice |
| Keyence *Tool Auto Tuning* from OK/NG images | The same idea, on the gauge with every sample visible (document 05 §19.3), and confirmed with *Aplicar* |
| Keyence *Threshold changing in RUN* | Supervisor fine-tune (FR-JOB-14), as a new verified version, never a silent change |
| Keyence *Any Tool OK*, *Logic 1–4* | Not planned. The job result is "every deciding tool passes"; anything else is a project integration |
| Cognex *Invert* | Criteria already express "must be absent" (for example `max` instead of `min`). No generic invert |

---

## 8. Learning-based tools

| | Cognex In-Sight 2800 (*edge learning*) | Keyence IV / IV3 |
|---|---|---|
| What | A classifier trained **on the camera** | **Learning** tool; IV3 **AI-Based Detection** |
| Classes | Start with **OK** and **NG**; more can be added (for example *no part*) | OK and NG |
| Images | Captured live and labelled with one button per class, or imported from a folder. The example uses about 19 images (9 OK, 8 NG, 2 no part) | IV3: register **at least one OK and one NG** and the AI sets up the detection |
| Readiness | A **model health** figure. The suggestion is to deploy when it is above 80 % and stable | Not documented |
| Extras | Several regions, each with its own classes | **Additional learning**; image history saves *OK near threshold* for review (§13) |

**Vision Station:** `detect` runs offline-trained ONNX models; **`anomaly`** is taught on the station from good parts (tier 2, TD-27). The In-Sight 2800 and IV3 show that integrators now expect **training on the station from a handful of labelled images, with a readiness indicator**. Our `anomaly` tool should show such an indicator (separation of good and bad samples on its gauge already does part of the job).

---

## 9. Discrete I/O

### 9.1 Cognex input signal types

| Type | Meaning |
|---|---|
| **Acquisition Trigger** | Triggers acquisition (*Trigger* = *External*). One line only |
| **Online/Offline** | Forces Online (1) or Offline (0). One line only |
| **Job ID Number** | One bit of a job number (jobs carry a numeric prefix **0 – 127**); the lowest line is the least significant bit |
| **Job Load Switch** | When on, reads the Job ID lines and loads that job. **The system must be Offline** |
| **Job Change (Pulsed)** | In-Sight 2000 only: a pulse train (start 20 ms, count pulses 10 ms, gaps 10 ms, stop 20 ms) whose count is the job number (0 – 31) |
| **Reset Counters** | Zeros the counters (Online only) |
| **Event Trigger** | Runs an event in the spreadsheet |
| **User Data** | General-purpose; can enable or disable tools |
| **Serial Receive** | Serial on input 1 (some models) |

Edges: *Rising*, *Falling*, *Both* (*Both* for *Event Trigger* only).

### 9.2 Cognex output signal types

| Type | Meaning |
|---|---|
| **Job Result** (default) | Driven by a tool's result, pulsed or steady |
| **High** / **Low** | Forced level |
| **Acquisition Start** / **Acquisition End** | Pulses at the start / end of acquisition |
| **Job Completed** | Pulses after each job update |
| **System Busy** | High while running a job or responding to the user |
| **Job Load OK** / **Job Load Fail** | Pulses after a job load |
| **ERR: Missed Acquisition** | Trigger before the previous acquisition ended, or no free buffer (*Camera* trigger only) |
| **ERR: Tracking Overrun** / **ERR: Tracking Queue Full** | A delayed output fired late, or collided with another on the same line |
| **Online/Offline** | High when Online |
| **Strobe**, **Light Control** | Strobe or light timing |
| **Lifeline** (CIO-MICRO) | High while the I/O module is connected |
| **Job Pass/Fail** (7000 Gen2, 9000) | Drives the pass/fail LED ring |

**Output Details:**

| Control | Range / default | Meaning |
|---|---|---|
| **Pulse** | on / off | Pulse or steady state |
| **Pulse Length** | min 1 – 10 ms (model), max 1 000 ms, default 10 ms | |
| **Acquisition Delay (N)** | 0 – 1 000 | Fire the output **N acquisitions (or encoder/tracking pulses) later**. Used for a rejector downstream of the camera. Forces pulse mode |
| **Time After Trigger** | 0 – 10 000 ms | Fire the output a fixed time after the trigger. Exclusive with *Acquisition Delay* |
| **Strobe/Light Control Trigger**, **Strobe Start Position** | | Edge and timing of a strobe |

**Other options:**
- **De-Energize Outputs While Offline**.
- **Force** an input or output for testing. For outputs, *Force* changes only the logical value: to test wiring, set the line to *High* or *Low* while Online.

### 9.3 Keyence inputs

- **IN1 is the external trigger** on both the amplifier and the smart camera.
- The other inputs are assignable:
  - **Program switching**;
  - **Clear error**;
  - **External master image registration**;
  - **SD card save cancel**.
- Amplifier: 8 inputs, voltage or non-voltage type. Smart camera: 6 ports, 3 of them configurable as input or output.

### 9.4 Keyence outputs (Output Assignment)

| Function | ON when |
|---|---|
| **Total Status** | The total result is OK (*All Tools OK*, *Any Tool OK*, *Logic 1 – 4*) |
| **Tot. Status NG** | The total result is NG |
| **RUN** | Running with no system error |
| **BUSY** | Cannot accept a trigger (imaging, judging, switching programs, registering an external master) |
| **Error** | System error, memory readout error, external master registration error, trigger error |
| **Pos. Adj.** | Position adjustment finished normally |
| **Tool 01 – 16** / **Logic 1 – 4** | That tool / logic result is OK |
| *(IV3)* | also **Variety discrimination result**, **Master judgment result**, **SD card error** |

**Defaults on the IV:**

| Output | Default function | Contact |
|---|---|---|
| OUT1 | Total Status | N.O. |
| OUT2 | BUSY | N.O. |
| OUT3 | **Error** | **N.C.** |
| OUT4 | OFF | — |
| Trigger Error | OFF | — |

Every output can be N.O. or N.C. Error is normally closed by default, so a cut wire or a dead sensor reads as "error".

### 9.5 Vision Station

FR-INT-6 drives 24 V I/O through a Modbus TCP remote I/O module: one trigger input, outputs for ready, pass, fail and error (and a rejector or tower light). The machine interface (architecture §16) is fail-safe: outputs drop on loss of heartbeat or shutdown. FR-ADM-7 forces outputs during commissioning, only while the station is in maintenance.

**Worth taking** (proposals in §18):
- **Error as normally closed by default** (Keyence). It is the same fail-safe idea as ours, applied to the wiring. Our remote I/O map should default *Error* (or a *Healthy* output) to "energized when healthy".
- **Delayed reject output** (Cognex *Acquisition Delay N* / *Time After Trigger*). A rejector placed downstream fires N parts or T ms later. Today this is "a project integration" (FR-INT-2). It is common enough to deserve a setting.
- **Pulse length** per output (Cognex 1 – 1 000 ms).
- **Job Load OK / Fail**, **Busy** and **Online** on discrete I/O. They exist on the PLC interface (`JobChangeDone/Failed`, `Busy`, `Online`, architecture §16.2), not yet as assignable remote I/O outputs.
- **Clear error** as an input (Keyence), for lines without a PLC.

---

## 10. Industrial communication

### 10.1 Cognex protocols (Communication step)

- **Up to two protocols per job**: one primary, one secondary.
- **Primary:**
  - **EtherNet/IP**, **PROFINET**, **Modbus TCP Server**;
  - **CC-Link** (IE Field Basic on firmware 5.x), **SLMP**, **SLMP Scanner**, **POWERLINK** (firmware 4.x, some models);
  - **Ethernet Native** (also *Robot* and *String* variants);
  - serial: **Serial Native** and **Serial Text**, plus robot variants (*Kuka*, *Motoman*).
- **Secondary:** **TCP/IP**, **UDP**.
- Also in the step:
  - **OPC Server** (inspection results for open data access; not on the In-Sight 2000);
  - **FTP** (export images, write or append data files);
  - **SD Card**;
  - **EasyView** for the VisionView panel.

### 10.2 Cognex industrial communications signals

The full table is in project document 06 §4.1. In short:
- **PLC → vision:**
  - *Trigger Enable*, *Trigger*;
  - *Set Offline*, *Clear Error*;
  - *Buffer Results Enable*, *Inspection Results Acknowledge*;
  - *Execute Command* + *Command ID*;
  - *User Data*.
- **Vision → PLC:**
  - *System Ready*, *Online*;
  - *Trigger Ready*, *Trigger Acknowledge*, *Acquisition ID*, *Acquisition Error*;
  - **Exposure Complete**;
  - *Inspection Completed* (toggles), **Results Valid**, *Job Passed*, *Inspection Results*;
  - *Results Buffer Overrun* (**up to 16 buffered result sets**);
  - *Error* + *Error ID*;
  - *Command Executing / Completed / Failed* + *Command Result Code*;
  - **Current Job ID** (0 – 65 535).

**Trigger sequence:**
1. Set *Trigger Enable*.
2. Wait for *Trigger Ready*.
3. Set *Trigger*. The camera answers with *Acquisition ID* and *Trigger Acknowledge*.
4. Wait for *Exposure Complete*: the part may move.
5. Wait for *Inspection Completed* and *Results Valid*.
6. Read the results.
7. Acknowledge, then clear *Trigger*.

**Job load from the PLC (EtherNet/IP):**
- *Load Job by ID*: Command ID **0x000 – 0x3E7** (jobs 0 – 999).
- *Load Job by Name*: Command ID **0x4000**, with the name (no extension, null-terminated) in *User Data*.
- Sequence:
  1. Set **Set Paused** (if a job is running).
  2. Write the Command ID.
  3. Set *Execute Command*.
  4. Wait for *Command Completed* or *Command Failed*.
  5. Clear *Execute Command* and *Set Paused*.

### 10.3 Keyence

- **Built-in:** EtherNet/IP, PROFINET (Conformance Class B, LLDP, SNMP), **TCP/IP non-procedure** (text commands).
- **Through DL communication units:** EtherCAT, CC-Link, DeviceNet, RS-232C, PROFIBUS.
- **Network:** FTP and SFTP client for images and data.

### 10.4 Vision Station

Architecture §16 (machine interface map v1) took Cognex's handshake almost signal for signal:
- TriggerEnable / Ready / Ack;
- AcquisitionDone = *Exposure Complete*;
- ResultValid / ResultAck with a buffer (FR-INT-9, default 8 against Cognex's 16);
- error code, job number, heartbeats.

The transports are S7 (client of a DB), Modbus TCP server, remote I/O and OPC UA 40100 (FR-INT-4..7).

| Cognex / Keyence | Vision Station |
|---|---|
| EtherNet/IP, PROFINET | Not planned. Siemens is reached through S7 PUT/GET (FR-INT-4). a PROFINET or EtherNet/IP device stack on the PC is out of scope (TD-23 alternatives; architecture §16) |
| Modbus TCP Server | Same (FR-INT-5) |
| OPC Server | OPC UA 40100 (FR-INT-7) |
| TCP/IP text commands, Ethernet Native | Local HTTP/WebSocket API (FR-INT-1) |
| FTP image export | Not planned; results and images stay local with backup (FR-JOB-10) |
| *Set Paused* before a job load | The new job becomes active only after verification; a failure is signalled and the station stays out of Ready (FR-INT-8) |
| *Load Job by Name* | By number (and by product on OPC UA) |
| *Command Result Code* | Error code E503 for an unknown job number |

**Worth taking:**
- **Job load by name** as well as by number. On OPC UA we have products; on S7/Modbus only numbers.
- `JobChangeDone` / `JobChangeFailed` already match Cognex *Job Load OK / Fail*; `Busy` matches *System Busy* and Keyence *BUSY*.

---

## 11. Jobs and programs

| | Cognex | Keyence |
|---|---|---|
| Unit | **Job** (`.job` / `.jobx`) | **Program** |
| How many | As many as storage allows; numeric prefix 0 – 127 for I/O loading, 0 – 999 over EtherNet/IP | **32** (128 with an SD card) |
| Switching | I/O (*Job ID Number* bits + *Job Load Switch*, Offline), pulse train (2000 series), Industrial Ethernet command, user | Program switching inputs, panel, Ethernet; IV3: **High-speed program switching**, **Auto program switching** |
| Saving | **Offline** only, unless *Allow Online Job Save*; saving at the maximum trigger rate may cause missed triggers | Settings backed up to USB or PC; IV3 **Auto setting backup/restore** |
| Versions | Not documented | Not documented |

What a job or program holds, and what stays on the sensor, is in §19.

**Vision Station:** jobs are **immutable versions** with notes, verification before activation and A/B replay (FR-JOB-12). Neither vendor documents versions. This is a real difference in our favour and should stay central.

---

## 12. Online / offline, test and run

- **Cognex:**
  - A sensor is **Online** (inspecting, outputs live) or **Offline** (editing).
  - Online/Offline can be switched by the user (if allowed), by an input line, or by *Set Offline* from the PLC.
  - *De-Energize Outputs While Offline* drops outputs while editing.
- **Keyence:**
  - The sensor is in **RUN** or in setup. **Test mode** runs judgments without leaving setup (used by *Limit Adjustment* and auto tuning).
  - IV3 utilities:
    - **Test run**;
    - **Failure hold** (keep the failing image on screen);
    - **I/O monitor**;
    - **Failing sensor list** (on multi-sensor setups);
    - **Simulator** on PC.

**Vision Station:**
- *Em produção* / *Em manutenção* is the same idea as Online / Offline. The editor holds the station paused, and the idle timeout resumes it.
- The editor's **Testar** and **Testar a cada captura** play the role of Test mode.
- **Failure hold** (Keyence) and *Freeze on Fail* (Cognex filmstrip, §13) keep a failing image in view. Our operator screen shows the latest verdict; neither a hold time on FAIL nor a frozen view in the editor is specified yet (§18 #30).

---

## 13. Image history and filmstrip

### 13.1 Cognex filmstrip (on the sensor)

| Setting | Options / limits |
|---|---|
| **Queue** | *Disabled* (default), *Passed Results*, *Fail Results*, *Pass and Fail Results*, **Separate Pass and Fail Results** |
| **Queue Size** | Up to **20** results, depending on resolution and RAM |
| **Pass Size** / **Fail Size** | With separate queues; minimum 1 each |
| **Queue Type** | *First Only* or *Most Recent* (default) |
| **Clear When Placed in Online Mode** | On by default |
| **Display Mode** | *Normal*, **Freeze on Fail**, **Pause on Fail** |
| **Pause Delay** | 1 – 120 s, default 5 s (*Pause on Fail*) |
| **LED Style** | Shapes (green circle / red rectangle), *OK* / *NG* labels, or ✓ / ✕ |
| **Save to PC** | Saves the selected or frozen results to a folder |

The documentation warns that the filmstrip **may increase job execution time**. Images can also be **exported by FTP or to an SD card** (Communication step).

### 13.2 Keyence image history (IV3)

- Up to **100 images** in internal memory.
- **Save conditions:** *NG only*, **NG and OK near threshold** (Learning tool only), or *All*.
- **Transfer** to SD card, FTP or SFTP, as bmp, jpeg, iv3p or txt, with configurable file names and the same three conditions.
- Images from history can become the **master** (§5.1) or **OK/NG tuning images** (§7.2).

### 13.3 Vision Station

FR-LOG-1/2 keep every FAIL and ERROR image and a sample of PASS images, on disk and with retention, which is far beyond 20 or 100 images. Things worth taking:
- **"OK near threshold"** as a save condition (Keyence). A PASS image whose margin is small is exactly what the margin warning (FR-LOG-7) and the fine-tune screen need. Proposal: keep **every PASS with low margin** in addition to the 1-in-20 sample.
- **Freeze / pause on fail** in the editor's live view (Cognex).
- **Separate pass and fail limits** match our retention policy (PASS images deleted first).

---

## 14. Monitoring and statistics

| | Cognex | Keyence IV3 (RUN information) |
|---|---|---|
| Counts | Pass, Fail, Error counts per tool; *Reset Counters* input | Trigger count, OK and NG counts, **trigger errors** (and strobe errors) |
| Values | Tool outputs to OPC, EasyView, spreadsheet *Statistics* and *Trend* tools | **Histogram of similarity** with max / min / average |
| Time | Not documented on these pages | **Processing time**: latest, max, min, average |
| I/O | — | **Output monitor**: ON/OFF of each output; **I/O monitor** |

**Vision Station:** document 05 §7.13 (statistics, margin trend) and §7.14 (machine monitor) cover this. Two items to check against the doc:
- **Trigger errors** as a counted statistic.
- **Processing time max / min / average** visible in operation, not only in the benchmark (FR-ADM-5).

---

## 15. Users and security

| Cognex level | What it can do |
|---|---|
| **Full** (default *admin*) | Everything: load, modify and save any job |
| **Protected** (default *operator*) | Live video; Online/Offline if allowed; open/save if FTP rights allow. **Edit tool parameters but not add or delete tools** |
| **Locked** (default *monitor*) | Monitor only |

Per user:
- **FTP-R** (load jobs) and **FTP-W** (save jobs);
- **Online/Offline**;
- **Online Job Save**.

The user list lives on each camera. Names and passwords are limited to 15 characters.

Keyence IV3: **Security settings** with a **two-factor password**. Details are not documented on the specification page.

**Vision Station:** Operator / Supervisor / Maintainer (FR-ADM-1) match Locked / Protected / Full closely. Cognex's *Protected* is exactly our Supervisor fine-tune: **change parameters, not the structure** (FR-JOB-14, which is narrower: tolerances only). The per-user **"may switch Online/Offline"** flag is worth considering for the Supervisor.

---

## 16. Operator interfaces

- **Cognex:**
  - **VisionView** operator panel, configured with **EasyView** (chosen values and controls exposed to the operator);
  - a **Web HMI** on newer firmware with a filmstrip;
  - *Custom View* for Protected and Locked users.
- **Keyence:** a dedicated monitor or the **IV3-CP50** control panel (Ethernet, M12); PC software IV3-H1 with a simulator.

**Vision Station:** the operator screen runs in Edge kiosk mode on the station PC. It shows the verdict, the reason in the station language and the overlays (document 05 §7.1). Cognex's *EasyView* idea, choosing which values the operator sees, is close to the job's operator texts and published values (step 6).

---

## 17. Tool catalogues

### 17.1 Cognex EasyBuilder Inspect Part tools

| Category | Tools |
|---|---|
| **Presence/Absence** | Brightness, Contrast, PatMax RedLine Pattern, PatMax Pattern, Pattern, Pixel Count, Color Pixel Count, Blob, Color Blob, Edge, Circle, Sharpness |
| **Measurement** | Distance, Angle, Blob Area, Blob Areas (1-10), Color Blob Area, Color Blob Areas (1-10), Circle Diameter, Circle Concentricity, Measure Radius, Min/Max Points |
| **Counting** | Blobs, Color Blobs, Edges, Edge Pairs, PatMax RedLine Patterns, PatMax Patterns, Patterns |
| **Identification** | Read 1D Code(s), Read 2D Code(s), Read Postal Code, Read ID Codes, Read Text, Read Text (OCRMax), PatMax RedLine Patterns (1-10), PatMax Patterns (1-10), Patterns (1-10), Color, Color Model |
| **Geometry** | Point-to-Point (Line, Mid-Point, Dimension), Perpendicular Line, Line Intersection, Bisect Angle, Line / Circle From N Points, Circle-Line Intersection, User-Defined Point / Line, Circle Fit, Line Fit |
| **Math & Logic** | Math, Logic, Trend, Statistics, Group, Sequence, Compute Point, Variables, Robot Guidance |
| **Plot** | Plot Arc, Circle, Cross, Line, Point, Region, String |
| **Image Filter** | Filter, Neighbor, Scene Correction, Point, Color to Greyscale, Color to Binary, Transform, Compare |
| **Defect Detection** | Surface Flaw, Edge, Edge Pair, Edge Width, Bead Finder, Bead Tracker |
| **Calibration** | Robot, N Point, Sequence N Point |

### 17.2 Keyence IV3 detection tools

- **Tools:** Learning, Outline, Color area, Area, Edge pixels, Color average, Brightness average, Width, Diameter, Edge presence, Pitch, OCR, Color prohibit, Brightness prohibit, Blob count, plus Position adjustment and High-speed position adjustment.
- **Tool functions:** Additional learning, Mask outline, Masking, Colour extraction/exclusion, Colour or monochrome histogram, Scaling.
- **Capacity:** up to **64 detection tools** per unit (65 with position adjustment).
- **Modes:** Standard, and **Sorting mode** (variety discrimination, up to 8 tools).

### 17.3 Vision Station

Architecture §15.1 maps both lists to our tiers:
- **Tier 1:** brightness, color, blob, edge, pattern v2, code, compare, detect.
- **Tier 2:** ocr, anomaly.
- **Tier 3:** measure.

Two Keyence ideas not in that table:
- **Prohibit tools** (colour prohibit, brightness prohibit): "this colour / brightness must **not** appear". Our `color` and `brightness` express it with a `max` criterion; the editor should offer it as a named preset ("Cor proibida").
- **Masking** inside a tool region (exclude a label inside a cap area). Our regions are rectangles; a mask is not in the job format yet.

Cognex's **Sharpness** presence tool is our sharpness quality gate (E104), job-wide instead of per tool.

---

## 18. What Vision Station adopts, has, and could add

Status: **Has** = already in our documents; **Adopt** = proposed here, needs a decision and a requirement; **No** = deliberately different.

| # | Feature | Cognex | Keyence | Vision Station | Status |
|---|---|---|---|---|---|
| 1 | Guided setup in fixed steps | 9 application steps | 4-step navigator | 8 steps (doc 05 §4.3) | Has |
| 2 | Trigger: machine, button, continuous | External / Industrial Ethernet, Manual, Continuous | External, Internal | *Pela máquina*, *Botão*, *Contínuo* | Has |
| 3 | Trigger by image presence and stillness | — | — | *Pela imagem* | Has (ours only) |
| 4 | **Trigger delay** after the external signal | 0 – 10 000 ms | 0 – 1 000 ms | — | **Decided**: 0–1 000 ms, default 0, per job (FR-TRG-6, TD-31) |
| 5 | **Interval** for continuous | 0 – 10 000 ms | 1 – 10 000 ms | — | **Decided**: minimum interval 500 ms per job (FR-TRG-7, TD-31) |
| 6 | **Missed-trigger** signal and count | ERR: Missed Acquisition, Acquisition Error | Trigger Error output and count | `TriggerRefused` pulse (§16.2) | **Decided**: counter + assignable output (FR-INT-14, TD-31) |
| 7 | Exposure / acquisition done before the result | Exposure Complete | (BUSY) | AcquisitionDone (FR-INT-10) | Has |
| 8 | Result buffer with acknowledge | 16 sets | — | 8 (FR-INT-9) | Has |
| 9 | Auto exposure once, then lock | Optimal Exposure | Auto brightness | *Auto uma vez* | Has |
| 10 | Exposure region for auto exposure | Exposure Region | — | — | Adopt (small) |
| 11 | Reference from recorded images | — | Master from image history / USB | — | **Adopt**: "usar como amostra / referência" in results |
| 12 | Fixtures, several, linked | Yes | One position adjustment per program | Chains (FR-INS-12) | Has |
| 13 | Part not found | Fail | NG, tools not judged | **ERROR E201/E202** | No (deliberate) |
| 14 | More than one instance → not present | Yes (P/A) | — | — | Adopt in `pattern` v2 presence mode |
| 15 | Include tool in job result | Include In Job Pass | Total Status conditions | `affects_result` | Has |
| 16 | Any-tool-OK / user logic | Logic tool | Any Tool OK, Logic 1 – 4 | — | No (project integration) |
| 17 | Threshold at the midpoint of good and bad | — | Limit Adjustment example | *Ajustar pelas amostras* | Has |
| 18 | Auto tuning from OK/NG images | — | Tool Auto Tuning | Same, on the gauge | Has |
| 19 | Change thresholds during operation | Protected user edits parameters | Threshold changing in RUN | Supervisor fine-tune, new verified version | Has (stricter) |
| 20 | On-station learning with readiness figure | Edge learning, model health | AI-Based Detection | `anomaly` (tier 2) | **Adopt**: readiness indicator |
| 21 | **Error output normally closed** | — | OUT3 Error N.C. by default | Fail-safe interface | **Decided: No** — Error stays normal; polarity per output instead (FR-INT-16, TD-31) |
| 22 | **Delayed reject output** | Acquisition Delay N, Time After Trigger | — | Project integration | **Decided**: N inspections or T ms, queue, FAIL and ERROR (FR-INT-15, TD-31) |
| 23 | Output pulse length | 1 – 1 000 ms | — | — | **Decided**: 10–1 000 ms, default 100 (FR-INT-15) |
| 24 | Job load OK / failed signal | Job Load OK/Fail outputs; Command Failed | — | `JobChangeDone` / `JobChangeFailed`, E503 | Has |
| 25 | Job load by name | 0x4000 | — | By number (by product on OPC UA) | Consider |
| 26 | Clear error input | Clear Error bit | Clear error input | `ClearError` on the PLC interface | Adopt on discrete I/O |
| 27 | Force I/O for testing | Force | I/O monitor | FR-ADM-7 | Has |
| 28 | De-energize outputs while editing | Option | — | Outputs fail safe in maintenance | Has |
| 29 | Save images "OK near threshold" | — | Yes | 1-in-20 PASS sample | **Decided**: PASS with margin below 2 × the warning limit (FR-LOG-9, TD-31) |
| 30 | Freeze / pause on fail | Filmstrip display modes | Failure hold | Operator screen holds the verdict | Adopt in the editor live view |
| 31 | Trigger errors and processing time in RUN | Counts | Counts, time max/min/avg | Statistics §7.13 | Check |
| 32 | Three user levels, middle level edits parameters only | Full / Protected / Locked | Two-factor password | Maintainer / Supervisor / Operator | Has |
| 33 | Job versions with verification | Not documented | Not documented | Immutable versions, verification, A/B | Has (ours only) |
| 34 | Prohibit tools | — | Colour / brightness prohibit | `max` criterion | Adopt as named presets |
| 35 | Mask inside a region | — | Masking function | — | Consider (job format) |
| 36 | FTP / SD image export | Yes | SD, FTP, SFTP | Local + backup | No |
| 37 | EtherNet/IP, PROFINET | Yes | Yes | S7, Modbus, OPC UA | No (for now) |
| 38 | **One acquisition block** in the job: trigger, image settings, calibration | `AcquireImage` | Image Optimization | `acquisition:` in job format 2 (architecture §4.1, document 08 §7) | **Decided** (TD-32 §2) |
| 39 | **The trigger type carries its own timing** | `Delay` (by type) | Internal interval, External delay | Sub-block per type: `external {delay_ms, debounce_ms}`, `continuous {interval_ms}`, `image_presence {…}` | **Decided** (TD-32 §3). Two named fields instead of one overloaded `Delay`: deliberate difference |
| 40 | **Trigger debounce** | `Trigger Debounce` in `AcquireImage` | IN1 edge on the sensor | `external.debounce_ms` in the job (FR-TRG-8); the edge in the station (FR-INT-17) | **Decided** (TD-32 §4) |
| 41 | **Jobs written in full** | Every `AcquireImage` parameter is in every job | — | Format 3 refuses an incomplete block (FR-JOB-16) | **Decided** (TD-32 §5) |
| 42 | **Orientation** | `Orientation` 0 – 3 | — | `orientation` in the profile (FR-ACQ-10) | **Decided** (TD-32 §6) |
| 43 | **Auto-exposure parameters** | Mode, Max Exposure, Target Brightness, Auto Expose Region | Auto brightness adjustment | For *Auto uma vez* only (FR-ACQ-11). Continuous auto exposure: **No** (principles 1 and 2) | **Decided** (TD-32 §6) |
| 44 | **Input line settings in the station** | Discrete I/O Settings | I/O Settings: IN1 edge, IN2–IN6 roles | `machine.remote_io.inputs` `{line, function, edge}` (FR-INT-17) | **Decided** (TD-32 §8) |

**Decided on 2026-10-17** (TD-31): items 4, 5, 6, 21, 22, 23 and 29, now requirements FR-TRG-6/7, FR-INT-14..16 and FR-LOG-9 (document 02 v0.6) and architecture §16.7. Item 21 went the other way from the proposal: the Error output stays normal (energized on error), and every output gets a polarity setting so an integrator can make it fail-safe.

---

## 19. Who owns what: the job or program, and the sensor

Both vendors keep two layers apart. One travels with the job or program and says **what to inspect and how to take the picture**. The other stays with the sensor and says **how this sensor is wired, named and reached**. The setup flow does not show the split (Cognex puts the I/O and Communication steps inside EasyBuilder's flow). The split is in where each setting is stored and in the menus.

How sure each statement is: **stated** is quoted from the vendor's page; **inferred** is read from the page's structure and is marked so.

### 19.1 Cognex

| Layer | What it holds | Evidence |
|---|---|---|
| **Job** (`.job` / `.jobx`) | The spreadsheet, with **`AcquireImage` in cell A0**: trigger type, delay or interval, debounce, exposure, gain, light, orientation, image area, white balance and focus regions (§20). The tools. Calibration. | *Stated*: "AcquireImage exists permanently in cell A0 and cannot be cut, copied, or cleared". Saving a job "only saves the tool settings and the information specific to that job". |
| **Sensor** (`proc.set`) | Network configuration and vision-system settings: user list, discrete I/O, date and time, host list, serial and FTP settings | *Stated*: the *Store Settings* command "stores the In-Sight sensor settings to the proc.set file", with the sensor Offline and Full Access. *Inferred* from the factory reset, which clears the user list, discrete I/O, date/time, host list, serial and FTP settings. The page that defines `proc.set` could not be read (error 429), so its exact contents are not quoted. |
| Both | *Communication* step: results formatting and "up to two protocols per job" (§10.1) sit in the job; addresses and the network sit on the sensor | *Inferred*; the pages do not label each part |

The *Discrete I/O Settings* dialog says its changes "are saved to flash memory", not into a job. The only mention of a job there is the naming rule of the job to load, a numeric prefix of 0 to 127.

### 19.2 Keyence IV

| Layer | What it holds | Evidence |
|---|---|---|
| **Program** (Setup Navigator: Image Optimization, Master Registration, Tool Settings, Output Assignment) | **Trigger Options** (internal or external, interval 1 – 10 000 ms, delay 1 – 1 000 ms), brightness and focus, the master image, the tools, **what each output line means** | *Stated*: *Trigger Options* is a button of the Image Optimization screen of the Settings Navigator, which the manual's chapter 4 calls "Setting the Judgment Condition". *Inferred*: that these are saved per program; the manual pages I could read never say "per program" for the trigger. |
| **Sensor** (*Sensor Setup Menu › Sensor Advanced*) | Four groups, below | *Stated*, with the menu text quoted |

*Sensor Advanced*:

| Group | Contents |
|---|---|
| **Environmental** | **I/O Settings**: "Sets the input/output settings for the sensor", with *Input Settings* (the trigger timing of IN1, rising or falling edge; the role of IN2 to IN6: OFF, Program bit0 to bit4, Clear Error, Ext. Master Save), *Output Settings* (OUT1 to OUT4 formats, latching, one-shot) and *Polarity and I/O Monitor*. **Device Name/Pass** (sensor name, password lock). **Network Settings**. **Adv. Network Settings** (FTP client, field network). |
| **Setup Adjustment** | Display only: tilt correction, rotate 180°, white balance of the monitor |
| **Program** | **Program Switch Method** (Monitor/PC, External IN, field network). **Auto Focus Adj Pos**: "whether or not to share the adjusting position for auto focus to all programs" |
| **System** | Sensor information, initialize the sensor, update the sensor software |

The *Auto Focus Adj Pos* option shows the default: image settings belong to each program, and sharing across programs is an explicit sensor choice.

### 19.3 OPC UA for Machine Vision (OPC 40100-1)

The same two layers appear in the standard that machine builders use to talk to vision systems. A *recipe* is where "properties, procedures and parameters that describe a machine vision job" are stored. *Configurations* are managed as separate objects (add, activate, transfer). The specification leaves the content of a recipe open, so it confirms the split but not what goes on each side.

### 19.4 What the two products agree on

| Kind of setting | Layer | Cognex | Keyence |
|---|---|---|---|
| **How and when the image is taken**: trigger type, delay, interval, exposure, gain, light, focus, orientation, image area | **Job / program** | `AcquireImage` | Image Optimization |
| **What is judged**: fixture, tools, limits | Job / program | Locate Part, Inspect Part | Master, Tool Settings |
| **What the result means on an output**: which tool or total drives which line | Job / program | tool option *Include In Job Pass* | Output Assignment (step 4) |
| **How a signal enters or leaves the sensor**: which line is the trigger, edge, role of each input, polarity, formats | **Sensor** | Discrete I/O Settings | I/O Settings (IN1 edge, IN2–IN6 roles, OUT formats, polarity) |
| **Network, protocols' addresses, users, name, password, date and time** | Sensor | Network, User Access and Date/Time dialogs | Device Name/Pass, Network Settings |
| **How a program or job is selected**: the method, the numbering | Sensor (method), job (its number in the file name for Cognex) | I/O *Job ID Number* bits, PLC command | *Program Switch Method*, IN2–IN6 as Program bits |
| **Firmware, factory reset, system information** | Sensor | Add Sensor to Network, firmware update | System group |

Two things are **not** uniform, and the note matters if we copy only one:
- **Trigger debounce.** Cognex keeps it in `AcquireImage` (job, 0 – 65 536 µs, default 1, *Camera* trigger only). Keyence keeps the electrical side of IN1, the edge, on the sensor.
- **Where the trigger source is wired.** In both, the job says *which kind* of trigger it uses (*External*, *Industrial Ethernet*, *Manual*, *Continuous*), and the sensor says *how the signal gets in*. A job never names a pin.

---

## 20. Cognex `AcquireImage`: the model of the job's acquisition block

`AcquireImage` is one function with every parameter of how the picture is taken. Keyence's *Image Optimization* step is the same idea as a screen. The table is the complete parameter list of In-Sight Explorer 6.3 (model-dependent ranges are summarised), with what Vision Station has today.

| Parameter | Values (default) | Meaning | Vision Station today |
|---|---|---|---|
| **Trigger** | 0 Camera (default), 1 Continuous, 2 External, 5 Timestamp, 6 Industrial Ethernet, 32 Manual, 99 Network | The source of the acquisition. Not to be changed from the spreadsheet while Online | `trigger.mode`: `image_presence`, `manual`, `external`, `continuous` (document 03 §5) |
| **Delay** | 0 – 10 000 ms. With *Camera* or *Network*: wait between the trigger and the acquisition. With *Continuous*: the interval between acquisitions (500 ms; never shorter than the processing time) | One parameter, two meanings by trigger type | `trigger.delay_ms` and `trigger.interval_ms` (FR-TRG-6/7); two fields |
| **Trigger Debounce** | 0 – 65 536 µs (1); *Camera* trigger only | Minimum time the trigger input stays active to count | none |
| **Manual** | 0 off, 1 on (1) | Whether F5 or the trigger button may acquire while Offline | the button is always available (FR-TRG-3) |
| **Exposure** | ms, model range (for example 0.016 – 1000) | Light integration time | camera profile `exposure` |
| **Auto Exposure › Mode** | 0 Disabled, 1 Continuous, 2 Single-shot | Single-shot sets the exposure on the first image and reuses it | The profile has `exposure.mode` `auto` or `manual` (a value only in manual); *Auto uma vez* measures once and writes the manual value. No target brightness, maximum or region |
| **Auto Exposure › Max Exposure**, **Target Brightness** | Target 0 – 100 (10): percentage of saturated pixels | Limits of the automatic computation | none |
| **Auto Expose Region** | x, y, height, width in fixture coordinates | Where brightness is measured | none (§18 item 10) |
| **Start Row**, **Number of Rows** | per resolution | Acquire only a band of rows, to save time | none |
| **Light Control** | mode (exposure-controlled, always on, off); intensity 0 – 100 | The integrated light | none (a UVC camera has no light control) |
| **Gain**, **Offset** | model range (Gain 0 – 255, 128 on many models) | Sensor gain and DC level | camera profile `gain`; no offset |
| **Orientation** | 0 normal, 1 mirrored, 2 flipped, 3 rotated 180° | Image orientation | none |
| **White Balance Region** | x, y, height, width | Where white balance is measured | profile `white_balance` (a value, no region) |
| **Focus Metric Region** | x, y, height, width, angle, curve | Where the focus score is measured | profile `focus`; the focus meter of document 05 §19.5 |
| **High Dynamic Range** | Disabled, HDR+, HDR; kernel size | Pixel-wise range extension, some models | none (Keyence IV3 also lists HDR and high gain) |
| **Network Trigger** | master on or off, master name, master data | A camera triggers others | not applicable |
| **Buffer Mode** | 0 overlapped (default), 1 single | Image buffers | not applicable (the acquisition thread keeps the latest frame) |
| Calibration (*Set Up Image*, outside `AcquireImage`) | *Field of View* or *Import* | Results in real units | `calibration` in job format 2 (FR-INS-15) |

### 20.1 The shape the references share

- **One block.** All acquisition parameters sit together: trigger type with its timing, and the image settings. A person sets "how a picture is taken" in one place, and a job file holds it as one unit.
- **The trigger type carries its own timing.** *Delay* is a single parameter whose meaning depends on the type; Keyence has the same pair under *Internal* (interval) and *External* (delay).
- **Regions in fixture coordinates.** Auto exposure, white balance and focus each take a region, so they follow the part.
- **The source of an external trigger is not in the block.** The block says *External*; the sensor's I/O settings say which line.

### 20.2 Where Vision Station differs

| | References | Vision Station |
|---|---|---|
| Where acquisition settings live | One block (`AcquireImage`; one Setup Navigator step) | Three places: `trigger` in `job.yaml`, `camera/profile.yaml` (exposure, gain, white balance, focus), `quality` limits in `job.yaml` |
| Step in the editor | The first step after connecting (*Set Up Image*, *Image Optimization*) | Step 1 *Imagem* for the camera, step 5 *Disparo e qualidade* for the trigger (§22) |
| Trigger types | Hardware, serial, network, continuous, manual | Adds `image_presence`, with its own area, stillness time and thresholds. It has no equivalent in either product, so it belongs in the trigger type, as a type with parameters |
| Auto exposure | Mode (disabled, continuous, single-shot), maximum, target, region, stored with the job | `auto` or `manual`, and the value written by *Auto uma vez*, with its target, maximum and region in `exposure.auto_once` (VIA-0083). Single-shot only; the continuous mode is deliberately not offered |
| Camera-specific settings | Per sensor model, in the same function | `camera/profile.yaml` per driver (`raw` for what is not modelled) |

---

## 21. The station layer, according to the references

What Cognex keeps in `proc.set` and Keyence in *Sensor Advanced* is the **sensor's own configuration**. For us the sensor is the PC with its camera, so the equivalent is `system.yaml` and the commissioning (document 03 §5; document 05 §7.11).

| Sensor setting (reference) | Cognex | Keyence | Vision Station | Note |
|---|---|---|---|---|
| Input lines: which is the trigger, **edge**, role of the others | Discrete I/O Settings | I/O Settings: IN1 edge; IN2–IN6 roles | `machine.remote_io`: which input is the trigger | We have no edge (rising or falling) and no debounce for it |
| Output lines: function, **polarity**, formats, pulse | Output Details | Output Settings, Polarity | `machine.remote_io.outputs` `{line, function, polarity}` (FR-INT-15/16) | Has |
| Network and addressing | Network Settings | Network Settings | `network` (listen address, allowed origins) | Has |
| Protocols of the field network | Communication step | Adv. Network Settings | `machine:` adapters | Has (phase B) |
| Device name, password lock | Host name, User Access | Device Name/Pass | `station.name`, accounts (FR-ADM-1) | Has |
| Date and time | Date/Time Settings | (sensor clock) | the operating system | Not ours |
| How a job is selected | I/O Job ID bits, PLC command | **Program Switch Method** | `machine.jobs` numbering; PLC, OPC UA or API | Has |
| Sharing an image setting across programs | — | *Auto Focus Adj Pos* | focus is stored per job (FR-ACQ-8) | Same default |
| Language, display | — | Setup Adjustment (tilt, rotation of the monitor) | `station.language` | Ours |
| Firmware, factory reset, information | Add Sensor to Network, firmware | System group | About, restore (document 05 §7.11), installer | Has |
| Image storage | Filmstrip | Image history | `recording:` | Has |

One more point the references settle: the **meaning** of an output is job content (Keyence *Output Assignment* is step 4 of the program; Cognex *Include In Job Pass* is a tool option), while **line, polarity and format** are sensor content. Our job format 2 `outputs` (which tool values go to the machine, FR-INT-11) and `affects_result` are on the job side; `machine.remote_io.outputs` is on the sensor side.

---

## 22. Is our configuration flow in line with the references?

Checked against document 05 §4.3, §7.3, §7.11 and document 03 §5.

| # | Question | Cognex / Keyence | Vision Station | Verdict |
|---|---|---|---|---|
| 1 | Is the sensor-level setup done once, apart from the job? | Cognex: *Get Connected* first, but I/O and Communication come inside the flow. Keyence: *Sensor Advanced* is separate from the Setup Navigator | Commissioning once per installation (camera, performance, passwords, machine, backup), then the job | **In line**, and closer to Keyence than to Cognex |
| 2 | Does the job start with the image? | *Set Up Image* (step 2 of 9); *Image Optimization* (step 1 of 4) | Step 1 *Imagem* | **In line** |
| 3 | Is the trigger part of that first step? | Yes: Cognex *Set Up Image › Edit Acquisition Settings › Trigger*; Keyence *Image Optimization › Trigger Options* | Step 5 *Disparo e qualidade*, with a trigger control in the top bar | **Differs.** The top bar shows it, but the setup sits late in the sequence and apart from the camera settings |
| 4 | Are all acquisition parameters set together? | One block | Camera in step 1, trigger in step 5, quality gates in step 5 | **Differs** (§20.2) |
| 5 | Reference image before tools? | Keyence yes (*Master Registration*); Cognex no separate step | Step 2 *Amostras* | **In line** with Keyence |
| 6 | Locating before inspecting? | *Locate Part* then *Inspect Part*; Keyence *Position Adjustment* is in Tool Settings | Step 3 *Âncora*, step 4 *Ferramentas* | **In line** |
| 7 | Output meaning set in the job flow? | Keyence step 4 *Output Assignment*; Cognex *Inputs/Outputs* step | Step 6 *Resultado e saídas* (which tools decide; texts; values to the machine) | **In line**; the wiring is in commissioning, as the references keep it on the sensor |
| 8 | Is the trigger *source* chosen outside the job? | Yes (Discrete I/O Settings; I/O Settings) | `Configurações › Máquina`, not per job | **In line** |
| 9 | Are the electrical details of the trigger input configurable? | Cognex debounce; Keyence IN1 edge | Which input only | **Differs**: no edge, no debounce |
| 10 | Is an unfinished or unverified job kept from running? | Cognex: edit Offline, then Run; Keyence: test mode | Immutable versions; Validar; activation verifies | **Beyond** the references (ours only) |
| 11 | Is a job selected from the machine by number? | Job ID bits; Program bits | `machine.jobs` | **In line** |
| 12 | Does a setting that belongs to the image travel with the job? | Light intensity, focus distance, white balance "saved with the job" (Cognex) | Camera profile is in the job; zoom and focus per job (FR-ACQ-8) | **In line** |

**Summary.** The split between layers is the same as the references': what the picture is and what is judged in the job; wiring, network, identity and selection method on the station. The differences are in the **job's acquisition block**: its parameters are spread over three files and two steps, the trigger is set late, the trigger type does not carry all its timing the way `AcquireImage` does, and a few `AcquireImage` and *Trigger Options* parameters are missing (§20: debounce, auto-exposure limits and region, orientation, image area). On the station side the references also configure the input line (edge, debounce) and we do not.

The owner accepted this document as the model on 2026-10-18, and TD-32 settled what follows from it: the acquisition block, the trigger in step 1, debounce in the job and the edge in the station, jobs written in full, the two-layer rule (architecture §4.6). The open points seen while checking are settled as follows:
- The text of TD-31 ("defaults keep old jobs unchanged") against the 500 ms default of the interval: the fields move into the trigger type's sub-block and every job is written in full, so no default can change a saved version (TD-32 §5). Code written before this (the interval in format 1) is transitional.
- Document 03 §5 and document 05 §4.3 now agree: the trigger is job content and is set in step 1.
- FR-TRG-6/7 "per job" stands, as in `AcquireImage`.

---

## 23. Sources

**Cognex (In-Sight Explorer / EasyBuilder help):**
- [Application Steps](https://docs.cognex.com/is_621/web/EN/ise/Content/EasyBuilder/AppSteps.htm)
- [Trigger Controls](https://docs.cognex.com/is_573/web/EN/ezb/Content/EasyBuilder/Image_TriggerSettings.htm)
- [Image Settings (EasyBuilder Lite)](https://docs.cognex.com/is_573/web/EN/ezb/Content/EasyBuilder/EasyBuilderLite/ImageSettings.htm)
- [Inputs: Triggering Image Acquisition](https://docs.cognex.com/is_610/web/en/ezb/content/EasyBuilder/Inputs_ImageAcquisition.htm)
- [Locate Part: fixtures](https://docs.cognex.com/is_590/web/EN/ezb/Content/EasyBuilder/Locate_Fixture.htm)
- [Location tool properties (PatMax)](https://docs.cognex.com/is_573/web/EN/ezb/Content/EasyBuilder/Locate_PatMax_UsingTool.htm)
- [PatMax Presence/Absence: Settings tab](https://docs.cognex.com/is_573/web/EN/ezb/Content/EasyBuilder/Inspect_PA_PatMax_Param_Settings.htm)
- [Choosing Inspect Part Tools](https://docs.cognex.com/is_610/web/EN/ezb/Content/EasyBuilder/Inspect_Tools.htm)
- [General Advanced Settings (Include In Job Pass)](https://docs.cognex.com/isvs_2520/web/EN/InSight_EZ/Content/Topics/EZB/ezb-ui-inspect-advanced-general.htm)
- [Vision Tools (spreadsheet)](https://docs.cognex.com/is_611/web/EN/ise/Content/Reference/VisionTools.htm)
- [Configuring Input and Output Lines](https://docs.cognex.com/is_590/web/en/ezb/content/EasyBuilder/InputsOutputs_ConfigureLines.htm)
- [Output Details Dialog Controls](https://docs.cognex.com/is_590/web/EN/ezb/Content/EasyBuilder/Outputs_OutputDetails.htm)
- [Communication Home](https://docs.cognex.com/is_573/web/EN/ezb/Content/EasyBuilder/Communication_Home.htm)
- [Industrial Communications Signals](https://docs.cognex.com/is3d_132/web/EN/Help_IS3D/Content/Topics/IndustrialCommunications/comms-signals-vidi.htm)
- [Load a Job Through an EtherNet/IP PLC](https://docs.cognex.com/is2d_2230/web/EN/InSight_EZ/Content/Topics/IndustrialCommunications/comms-eip-loadjobrecipe.htm)
- [Filmstrip: Sensor Settings](https://docs.cognex.com/is_573/web/EN/ezb/Content/EasyBuilder/Filmstrip_Sensor.htm)
- [User Access Settings Dialog](https://docs.cognex.com/is_573/web/EN/ezb/Content/Dialogs/UserListDialog.htm)

**Cognex, added in 0.3:**
- [AcquireImage](https://docs.cognex.com/is_631/web/EN/ise/Content/Reference/AcquireImage.htm)
- [Managing In-Sight Jobs](https://docs.cognex.com/is2d_2311/web/EN/InSight_Sheet/Content/Topics/EZB/getting-started-managing-jobs.htm)
- [Store Settings](https://docs.cognex.com/is_574/web/EN/ise/Content/Communications_Reference/StoreSettings.htm)
- [Configure Discrete I/O Lines](https://docs.cognex.com/is_610/web/EN/ise/Content/Dialogs/DiscreteIOConfigure.htm)
- [Network Settings Dialog](https://support.cognex.com/docs/is_613/web/EN/ise/Content/Dialogs/NetworkSettingsDialog.htm)
- [Add Sensor/Device to Network Dialog](https://support.cognex.com/docs/is_574/web/EN/ise/Content/Dialogs/AddSensorsDialog.htm) (what a reset clears)

**Cognex (In-Sight 2800):** [How to Train Edge Learning](https://www.cognex.com/blogs/machine-vision/how-to-train-edge-learning).

**Keyence:**
- [IV Series User's Manual (Monitor)](https://www.manualsdir.com/manuals/658109/keyence-iv-series.html):
  - Setup Navigator, p. 69;
  - trigger options, p. 76 (manual page 4-8);
  - master registration, p. 89;
  - position adjustment, p. 119;
  - output assignment, p. 128;
  - limit adjustment, p. 148;
  - Tool Auto Tuning, p. 149.
- IV Series User's Manual (Monitor), pages read in 0.3 on the manualsdir.com copy (its viewer pages, not the manual's own numbering): [trigger options](https://www.manualsdir.com/manuals/658109/keyence-iv-series.html?page=78) (the manual's p. 76), [Sensor Advanced menu](https://www.manualsdir.com/manuals/658109/keyence-iv-series.html?page=201), [I/O Settings](https://www.manualsdir.com/manuals/658109/keyence-iv-series.html?page=202). The official PDFs sit behind a download form and were not read.
- [IV3 Series functional specifications](https://www.keyence.com/products/vision/vision-sensor/iv3/specs/)
- [IV3 Series product page](https://www.keyence.com/products/vision/vision-sensor/iv3/)

**OPC Foundation:** [OPC 40100-1, UA for Machine Vision, Part 1](https://reference.opcfoundation.org/specs/OPC-40100-1).
