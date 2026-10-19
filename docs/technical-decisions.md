# Vision Station — Technical Decisions

| | |
|---|---|
| Document | 04 — Technical Decisions |
| Version | 0.11 — TD-32: the job's acquisition block and the two layers, job and station (document 09 v0.3); TD-31 and TD-19 item 4 amended. 0.10 — TD-31: trigger timing and remote I/O outputs, decided from the market reference (document 09). 0.9 — TD-29 revised: shadcn/ui + Tailwind kept, React Aria added (the Mantine plan of 0.8 reverted); TD-30: interface in Portuguese and English. 0.7 — TD-21..TD-28: pose-based fixtures, result contract, machine interface, OPC UA, algorithms, OCR, teaching from good parts, CPU-only PC tiers; TD-18 amended |
| Date | 2026-10-18 |
| Author | Lucas (developer and maintainer) |
| Status | Draft for internal review |

Related documents: 01 — Project Scope · 02 — Requirements and Use Cases · 03 — Architecture ("job" model) · 05 — Frontend.

> Some decisions below were first taken for the first project that uses the platform (a packing station). Where they keep examples from it (box, tape), they are examples; the decision applies to any fixed station (TD-19).

Each decision follows the same format: **context → options → decision → consequences → revisit when**. IDs `TD-nn` are used in code comments and tickets. Requirement IDs refer to document 02, section numbers "§" to document 03.

---

## 1. Summary

| ID | Topic | Decision |
|---|---|---|
| TD-01 | Operating system | **Windows 11** (Pro, or IoT Enterprise LTSC if the supplier offers it). Linux stays possible, but we don't ask for it. |
| TD-02 | Language | **Python 3.12** for the whole core |
| TD-03 | Image library | **OpenCV** (`opencv-python-headless`) + NumPy |
| TD-04 | C920 capture and control (prototype) | OpenCV with **DirectShow** backend, forced **MJPG**; controls through **duvc-ctl**; settings reapplied and read back on every open |
| TD-05 | Hikvision capture and control (production) | **RTSP over TCP** via OpenCV/FFmpeg, or **ISAPI snapshot** on trigger; settings via **ISAPI** (HTTP Digest, XML). No Hikvision SDK. |
| TD-06 | Cameras | C920 for the prototype only; **Hikvision DS-2CD3666G2T-IZS** (6 MP, motorized 2.7–13.5 mm) for production |
| TD-07 | Inspection approach | **Classical checks first**, model only where they aren't enough |
| TD-08 | Model family and licence | **No Ultralytics** (AGPL-3.0). **RF-DETR Nano–Large** (Apache 2.0) for detection, **YOLOX** (Apache 2.0) as the fast-CPU alternative, **Anomalib** (Apache 2.0) for anomaly detection. Final pick by benchmark on the target PC. |
| TD-09 | Inference runtime | **ONNX Runtime** (CPU); **OpenVINO** execution provider if the PC has an Intel CPU. No PyTorch in production. |
| TD-10 | Training and labeling | Offline, outside the product. Labeling with **CVAT** or **Label Studio**; metrics with **Supervision** |
| TD-11 | Operator screen | **Local web UI** served by the core, shown in **Microsoft Edge kiosk mode** |
| TD-12 | Core API | **FastAPI + Uvicorn**, HTTP + WebSocket, localhost only by default |
| TD-13 | Storage and formats | **SQLite** + files; job files **YAML** validated by **Pydantic**; ZIP + **SHA-256** |
| TD-14 | Running unattended | Core as a **Windows service** (WinSW); fallback to a start-up task in the operator session if the C920 can't be opened from a service |
| TD-15 | Packaging and updates | **PyInstaller** (one-folder) + **Inno Setup** installer; data in `C:\ProgramData\VisionSystem` |
| TD-16 | Secrets | **Windows Credential Manager** via `keyring`, under the service account |
| TD-17 | Testing | **pytest**, file camera driver, reference-set tests on every build (CI on Windows) |
| TD-18 | Licence compliance | Only permissive licences in the shipped product; licence list generated at build |
| TD-19 | General platform | **Vision Station is a general vision system for fixed stations** (still object, fixed camera). Inspection steps are **tools** (color, code, pattern, detect), configured per job. Customer projects use it and live outside this repository. |
| TD-20 | Web interface | The system is **controlled from a web interface served by the API**. **React + TypeScript + Vite**, Tailwind and shadcn/ui (Radix), TanStack Query, generated API types; design system with tokens. Details in document 05 (`docs/frontend.md`). |
| TD-21 | Pose-based fixtures | Locators return a **pose** (x, y, angle, scale); regions are cut **upright** for the tools; fixture chains; job **format 2** with a migrator. |
| TD-22 | Result contract | One structured result everywhere, with a stable **error-code catalog** and **reason codes**. |
| TD-23 | Machine interface | One fail-safe **handshake** (interface map v1); adapters: **S7 client** (python-snap7, MIT), **Modbus TCP server** and **remote 24 V I/O** (pymodbus, BSD-3). No PROFINET device stack. |
| TD-24 | OPC UA | **OPC 40100-1** server (Simple Inline target) on **asyncua** (LGPL-3.0, shipped unmodified and replaceable), after S7 and Modbus. |
| TD-25 | Vision algorithms | Own shape matching, calipers and variation model in `algorithms/`; **Fullseye** (Apache 2.0) code may be ported with attribution, never a dependency. |
| TD-26 | OCR | Tier-2 `ocr` tool on **RapidOCR** (Apache 2.0, ONNX), to be evaluated; Tesseract as fallback. |
| TD-27 | Teaching from good parts | `compare` (variation model) and `anomaly` (ONNX backbone + memory bank) taught on the station, NumPy only, no PyTorch. |
| TD-28 | PC tiers | **Tier M** (Intel N100 class) and **tier R** (Core i5 12th+), both without a dedicated GPU; built-in **benchmark** classifies the PC; iGPU optional. |
| TD-29 | UI components | **shadcn/ui + Radix + Tailwind kept**; **React Aria Components** for colour, range and number controls; shadcn `Sidebar`, `Resizable`, `Command`, `Chart`; `@dnd-kit`. Extends TD-20. |
| TD-30 | Interface languages | **Portuguese (pt-BR) and English**; **Lingui** with PO catalogs in the interface, gettext/Babel PO catalogs on the server; job texts in both languages (format 2). Supersedes the pt-BR-only rule of TD-20/document 05 0.1. |
| TD-31 | Trigger timing and remote I/O outputs | Trigger delay 0–1 000 ms per job; continuous interval 500 ms; refused triggers counted and assignable to an output; Error output stays normal; delayed reject in inspections or ms with a queue; low-margin PASS images kept; output polarity per line. From document 09 (market reference). Amended by TD-32: the fields live in the trigger type's sub-block, and jobs are written in full instead of relying on defaults. |
| TD-32 | Acquisition block and the two layers | **One `acquisition` block in the job** (trigger type with its own timing, image settings, calibration), **written in full**; debounce in the job, input-line edge in the station; trigger moves to step 1 of the editor; rule: job = follows the product and the view, station = follows the installation. From document 09 v0.3. |

---

## 2. Decision records

### TD-01 — Operating system

**Context.**
- The client buys the PC, and their staff only knows Windows.
- Linux could be requested, but it isn't guaranteed (document 01, section 10).
- The C920 is much easier to control on Linux (V4L2), but the C920 is only for the prototype.
- The production camera (Hikvision) is controlled over the network, so the OS doesn't matter for it.

**Options.**

| Option | For | Against |
|---|---|---|
| Windows 11 Pro | What the client knows and will buy; their IT can support it | Updates can reboot the PC; harder to control USB cameras; service/USB camera limits |
| Windows 11 IoT Enterprise LTSC | Same as Pro, plus long support with no feature updates, built for fixed-purpose machines | Sold only through OEMs/distributors, so the PC supplier must offer it |
| Linux (Ubuntu LTS) | Best camera control (V4L2), simpler services, no forced reboots | Client staff can't support it; needs the client's approval; risk of push-back |

**Decision.**
- **Windows 11, 64-bit.** Prefer **IoT Enterprise LTSC** if the supplier offers it; otherwise **Pro**. Not Home: Home doesn't allow enough control of updates.
- Don't ask for Linux. Section 5 describes what changes if the client offers it.

**Consequences.**
- **Update policy (Pro):** set active hours to cover all shifts, defer feature updates, and agree a reboot window with the client's IT. The system must survive a reboot anyway (NFR-REL-2, UC-10).
- **Camera privacy:** the Windows setting "Let desktop apps access your camera" must be on. The installer checks it and shows a clear message if it's off.
- The C920 prototype carries the Windows-specific risks: TD-04 and TD-14.
- The core stays OS-independent (§1 principle 7), so moving to Linux later means changing three things: the camera driver, the service wrapper and the installer.

**Revisit when:** the client offers Linux, or Windows updates cause downtime in production.

---

### TD-02 — Language

**Context.**
- One developer.
- The vision and ML tooling is Python-first: OpenCV, ONNX Runtime, OpenVINO, Anomalib, RF-DETR, Supervision.
- Everything that is heavy on the CPU runs inside native libraries. Python only connects the steps.

**Options:** Python · C# (.NET) with OpenCvSharp · C++.

**Decision.** **Python 3.12** for the core, the training tools and the tests.

**Consequences.**
- **Why 3.12:** it is the newest version supported by every library we need. In particular, duvc-ctl lists Python 3.8–3.12.
- **Packaging:** Windows needs a frozen build (TD-15).
- **Typing:** type hints plus Pydantic models at every boundary (job files, API), to make up for Python's dynamic typing.
- **Timing:** if any stage turns out too slow for NFR-PERF-1, optimize that stage. The language stays.

**Revisit when:** a measured latency budget can't be met.

---

### TD-03 — Image library

**Decision.** **OpenCV** through the `opencv-python-headless` wheel, plus NumPy.

**Why headless:**
- The screen is a web page (TD-11), so OpenCV's own windows are never needed.
- The headless wheel is smaller.
- It still includes **FFmpeg** (needed for RTSP) and the DirectShow and Media Foundation capture backends on Windows.

**Consequences.**
- **Licences:** OpenCV is Apache 2.0. The bundled FFmpeg is LGPL and dynamically linked, which is acceptable; list it in the licence file (TD-18).
- **Version pinning:** pin the OpenCV version. Capture behavior changes between versions, so updating it means re-running the camera tests.

---

### TD-04 — C920 capture and control (prototype)

**Context.** These problems are known and documented:
1. The C920 firmware ignores manual exposure or focus while the matching **auto** mode is on.
2. Settings can return to auto after a restart or replug.
3. In its default **YUYV** format the C920 is limited to low frame rates at higher resolutions. **MJPG** fixes this.
4. "Low light compensation" quietly lowers the frame rate.
5. On Windows, OpenCV's behavior depends on the backend:
   - DirectShow can get stuck at a low frame rate unless MJPG is forced;
   - Media Foundation gets slower to open with each `set()` call;
   - mixing the two backends breaks capture;
   - auto-exposure values mean different things on each backend.
6. OpenCV buffers frames, so a read can return an old frame.
7. Every apply reopens the capture (the format is asked for while opening), and the C920 then sends 2 or 3 **overexposed frames** (mean brightness about 200–240 against 100) before the manual exposure holds, even when the same profile is written again (bench PC, 2026-10-16).
8. Unplugged, the C920 does not make OpenCV's `read()` fail: DirectShow keeps delivering perfectly uniform black frames (about 2 per second), and after it is plugged back that capture stays dead (bench PC, 2026-10-16).

**Options for control on Windows:**
- OpenCV `CAP_PROP_*`: partial, behavior differs by backend.
- The camera's settings dialog (`CAP_PROP_SETTINGS`): manual only, can't be scripted or restored.
- Logitech software: not scriptable.
- **duvc-ctl:** MIT-licensed, Windows-only. It controls exposure, focus, white balance, gain, zoom and the other standard UVC properties, in both Auto and Manual modes, through DirectShow, with no vendor SDK.

**Decision.**
- **Frames:** OpenCV with the **`CAP_DSHOW`** backend only. Ask for `MJPG`, the resolution and the format **while opening** (`cv2.VideoCapture(index, cv2.CAP_DSHOW, [CAP_PROP_FOURCC, ..., CAP_PROP_FRAME_WIDTH, ..., CAP_PROP_FRAME_HEIGHT, ...])`). Setting the FOURCC after opening did not stick on the bench PC (the C920 stayed on YUY2, about 5 fps at 1080p; 2026-10-13). The driver reads the format back and falls back to setting FOURCC before the size, then the size before FOURCC. Read in a dedicated thread that keeps only the latest frame (§3.2).
- **Settings:** set through **duvc-ctl** in two passes:
  1. switch every auto mode to manual;
  2. wait about 200 ms, then write the values;
  3. read everything back.
- **When to apply:** on every open, every reconnect, and every job activation (FR-ACQ-4/5).
- **Settling after an apply:** the acquisition drops every frame for `camera.settle_ms` of `system.yaml` (default 500 ms) after the settings are written, and the frame from before the apply is not used either. Only then is the profile counted as applied, so the controller never takes an overexposed frame as the empty scene of the image trigger or inspects it. Without this, a job switch could learn a bright background: the real scene then looked like an object forever, the station inspected on its own and never re-armed (VIA-0045).
- **Fixed defaults in every C920 profile:** low-light compensation off; power-line frequency 60 Hz (Brazil mains); autofocus off, with a fixed focus value.
- **Unplugged camera:** the acquisition counts a camera that sends only perfectly uniform frames for `camera.dead_after_s` (default 2 s) as lost, for any driver; the UVC driver also checks every 2 s that the device is still in duvc-ctl's device list. Either way the acquisition closes the capture and reconnects through the normal path (CameraLost, retries, settings applied again, settling) (VIA-0050).
- **Device identity:** store the camera's device path in `system.yaml`. Don't use the OpenCV index, which can change when USB devices are added or removed.
- **On Linux (if TD-01 changes):** V4L2 backend plus `v4l2-ctl`, under the same driver interface. Control names differ between kernels (`focus_auto` vs `focus_automatic_continuous`), so read the available controls at start-up instead of hardcoding them.

**Consequences.**
- The C920 driver is the most fragile part of the prototype. That's acceptable, because it is replaced in production.
- **Risk:** if duvc-ctl and OpenCV conflict when opening the same device, settings fall back to OpenCV `set()` calls with read-back, and anything that can't be set is reported as "not supported".
- **Early test:** this is item 1 of the prototype tests (section 7).

**Revisit when:** the C920 is retired, or Linux is approved.

---

### TD-05 — Hikvision capture and control (production)

**Context.**
- Hikvision cameras expose **ISAPI**, an HTTP API with XML bodies and Digest authentication. Channel 101 is the main stream and 102 the sub-stream.
- Image settings live under `/ISAPI/Image/channels/1/…`: exposure, shutter, gain, colour, WDR, and others.
- Focus is under `/ISAPI/System/Video/inputs/channels/1/focus`.
- Single images come from `/ISAPI/Streaming/channels/101/picture`.
- The available settings vary by model. Every model publishes its own list at `/ISAPI/System/capabilities`.

**Known problems:**
- OpenCV's FFmpeg backend shows decode errors and smeared frames on Hikvision RTSP over UDP.
- RTSP latency grows if processing is slower than the stream.
- The snapshot can be lower quality than the stream, and high-resolution snapshots are less stable on some units.
- Newer firmware ships with ISAPI disabled.

**Decision.**
- **Settings: ISAPI** through `requests` with `HTTPDigestAuth`. No Hikvision SDK: it isn't needed, and it would tie the core to Windows DLLs.
- **What goes in the job's `camera/raw/`:** a full GET of `/ISAPI/Image/channels/1` (plus focus and zoom positions where the model exposes them). Restore = PUT, then GET and compare (§5.3).
- **Frames:** the choice is made per job, after testing on the real unit (§13 open point 2).
  - **RTSP main stream (101) over TCP.** Set `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` before opening. Read in a latest-frame thread.
  - **ISAPI snapshot on trigger.** Simplest, no buffering. Use it if image quality is good enough.
- **Camera encoder settings:** H.264 (not H.265 or H.264+/H.265+), constant bitrate, short I-frame interval (equal to the frame rate), main stream at the resolution the job needs.
- **Commissioning checklist:** enable ISAPI under Network → Advanced → Integration Protocol; static IP; time synced to the PC; turn off the camera's own motion and smart detection features (not used).
- **Fallback library:** PyAV, also FFmpeg-based. Use it only if OpenCV's RTSP reader proves unreliable over a long test.
- **Camera alarm I/O (the selected model has 2 inputs and 2 outputs):**
  - **Input:** can receive the scale's "weight stable" dry contact (FR-TRG-2). The core listens to the camera's ISAPI event stream (`/ISAPI/Event/notification/alertStream`) for the input event. This needs no extra I/O hardware on the PC.
  - **Output:** can be switched over ISAPI (`/ISAPI/System/IO/outputs/<n>/trigger`) to drive a tower light or buzzer on FAIL (FR-INT-2). Use an interposing relay for anything beyond a small 24 V signal lamp.
  - **To confirm on the delivered unit:** both endpoints, and the delay from contact closure to event. If the delay is too long, the image-based trigger stays the default.

**Consequences.**
- **Find the exact XML from the real camera:** change the setting in the camera's web page and capture the request in the browser's developer tools. Then replay it from the code.
- **Read the capabilities before writing code:** fetch `/ISAPI/System/capabilities` from the purchased unit first, and build the driver from what the model actually supports.

**Revisit when:** a different camera brand is chosen. The driver interface (§5.1) stays the same.

---

### TD-06 — Cameras

**Context.**
- Clean environment, fixed station, a budget below industrial cameras, and local availability in Brazil.
- Hikvision was chosen because Dahua is hard to find locally.
- The simulator (Bancada Virtual de Visão) is used to choose height, lens and lighting.

**Decision.**

| Phase | Camera | Why |
|---|---|---|
| Prototype | **Logitech C920** (USB) | Already bought, cheap. Enough to build the software, collect first images and test the checks |
| Production | **Hikvision DS-2CD3666G2T-IZS**, 6 MP bullet, motorized varifocal **2.7–13.5 mm** | Focus and zoom can be set and restored remotely; settings can be saved and restored over ISAPI; alarm I/O on board; available in Brazil; wired Ethernet |

#### Selected model: DS-2CD3666G2T-IZS — what matters for this project

| Spec (datasheet) | Value | What it means here |
|---|---|---|
| Sensor / max resolution | 1/2.4" CMOS, **3200 × 1800** | Enough detail for small print, logos and codes over a large field |
| Frame rate | 20 fps at 3200 × 1800; 30 fps at 1920 × 1080 (60 Hz) | More than enough for a still object |
| Lens | Motorized varifocal 2.7–13.5 mm | Zoom and focus set remotely and stored in the job |
| Horizontal FOV | **106° (2.7 mm) → 35.6° (13.5 mm)** | See the coverage table below |
| Vertical FOV | 55.9° → 20° | — |
| Focus modes | Auto, semi-auto, manual | **Manual** in production, so focus never moves on its own |
| Shutter | 1/3 s to 1/100 000 s | Manual shutter under the station lighting |
| WDR / BLC / HLC / 3D DNR / defog | 140 dB WDR and the usual enhancements | All **off** or fixed in the job, so colour and contrast stay repeatable |
| IR | 850 nm, up to 60 m, IR-cut filter; day/night modes Day / Night / Auto / Schedule | **Must be forced to Day, IR off** (see below) |
| Compression | Main stream H.265 / H.264 / H.264+ / H.265+ | Use plain **H.264** (TD-05) |
| Streams | 4 independent streams (sub and fourth stream offer MJPEG) | Main for inspection; a sub-stream can feed the live view |
| **Alarm I/O** | **2 inputs, 2 outputs** (max 24 VDC/24 VAC, 1 A) | Can take a machine or sensor contact (e.g. a scale's "weight stable") as a trigger, and drive a tower light or buzzer on FAIL |
| Audio | 1 line in, 1 line out | Not used |
| Power | 12 VDC (max 13 W) or **PoE IEEE 802.3at, Class 4** (max 15 W) | The injector or switch must be **802.3at (PoE+)**; an 802.3af injector is not enough |
| Protocols | ONVIF (S, G, T), **ISAPI**, SDK, ISUP, RTSP | ISAPI available as planned |
| Protection / temperature | IP67, IK10; −30 °C to 65 °C | No enclosure needed indoors |

**Coverage by mounting height** (lens straight down, at the two ends of the zoom; width × height of the area seen, and horizontal pixel density at 3200 px):

| Height above the object's top | At 13.5 mm (tele) | px/mm | At 2.7 mm (wide) | px/mm |
|---|---|---|---|---|
| 0.8 m | 0.51 × 0.28 m | 6.2 | 2.12 × 0.85 m | 1.5 |
| 1.0 m | 0.64 × 0.35 m | 5.0 | 2.65 × 1.06 m | 1.2 |
| 1.2 m | 0.77 × 0.42 m | 4.2 | 3.18 × 1.27 m | 1.0 |
| 1.5 m | 0.96 × 0.53 m | 3.3 | 3.98 × 1.59 m | 0.8 |

- **Choose the height** so the largest object of the station, plus the placement tolerance (NFR-ACC-4), fills about 70–80 % of the frame at a focal length in the **middle or tele half of the zoom**.
- **Avoid the 2.7 mm end.** At 106° there is strong barrel distortion and the sides of the object are seen at a steep angle.
- **Same zoom for all variants:** one zoom setting serves every variant unless the sizes are very different. Each job stores its own zoom and focus anyway.
- **Confirm in the simulator:** the actual object dimensions go into the simulator to confirm the height before the bracket is made.

**Settings that are fixed in every job for this camera:**
- **Day/night mode = Day, IR LEDs off.** If left on Auto, the camera switches to black-and-white with IR in low light. That breaks every color tool, and IR reflects strongly on glossy surfaces (film, tape, metal). Forced Day mode keeps the IR-cut filter in and the image in colour.
- Focus mode **Manual**, with focus and zoom positions stored in the job.
- Exposure **manual** (fixed shutter and gain); white balance **manual / locked**.
- WDR, BLC, HLC, defog **off**; 3D DNR low or off; sharpening fixed.
- **AcuSense** (human/vehicle detection), motion detection and other smart events **off**: not used, and they add load on the camera.
- Main stream **H.264**, constant bitrate. H.264+/H.265+ off.

**On-arrival checks:** these are prototype test 5 (section 7). Confirm on the delivered unit:
- `/ISAPI/System/capabilities` lists zoom/focus control and manual exposure/white balance;
- a job's settings can be written, read back and restored after a reboot;
- the alarm input and output can be read and switched over ISAPI.

**Industrial cameras (GigE Vision, e.g. Basler, Hikrobot)** are the fallback if the IP camera can't deliver a stable image. They add cost and lead time, but give hardware triggers and full control. Only the driver would change.

**Lighting:**
- Diffuse lighting fixed to the station, sized in the simulator.
- Its job is to make daylight from the windows a small part of the total light (NFR-ENV-1).
- This matters more than the choice of camera.

---

### TD-07 — Inspection approach

**Decision.** Each job is built from tools (TD-19), chosen in this order of preference:

1. **Classical tools** with OpenCV:
   - locators: fixed position, template, outline or color blob;
   - `color`: color coverage in a region (e.g. a colored tape or cap is there);
   - `pattern`: template / feature matching, and repeats along a line (e.g. a printed logo along a seam);
   - `code`: bar codes and 2D codes.
2. **Anomaly detection** trained on good objects only: for defects that are rare or varied, when there are few failure images.
3. **Object detection model:** for things that need to be learned, such as an open flap, a folded edge, or a mark under glare.

**Why this order:**
- Classical checks need no training data.
- They are fast on a CPU.
- They are easy to explain to the operator (FR-INS-7).
- Their thresholds are plain numbers inside the job, so restoring them is exact.

Models are added only where the classical tools can't separate good objects from bad ones (UC-03, exception 6a).

---

### TD-08 — Model family and licence

**Context.**
- **Ultralytics YOLO (v8/11)** is AGPL-3.0. Using its code or models, including models **trained** with it, requires either releasing the whole project under AGPL-3.0 or buying an Ultralytics Enterprise licence. Ultralytics states that all models trained with its framework fall under AGPL-3.0 by default.
- The client's software is closed (NFR-LIC-1).

**Options:**

| Model | Licence | Strengths | Weaknesses |
|---|---|---|---|
| Ultralytics YOLO11 | AGPL-3.0 / paid Enterprise | Easiest tooling, large community | Licence; cost of Enterprise licence |
| **RF-DETR** Nano / Small / Medium / Large | **Apache 2.0** (code and COCO weights) | High accuracy; designed for fine-tuning on small custom datasets; exports to ONNX | Transformer, heavier on CPU than small YOLOs; **XL and 2XL sizes are under Roboflow's Platform Model Licence, not Apache — do not use them** |
| **YOLOX** Nano → X | **Apache 2.0** | Light, fast on CPU; ready ONNX and OpenVINO exports; same input/output across sizes | Older (2021), less active; lower accuracy than recent models |
| **Anomalib** (PatchCore, PaDiM, EfficientAD…) | **Apache 2.0** library | Trains on good images only; anomaly maps show *where*; exports to OpenVINO | Gives "unusual", not "which defect"; check each model's pretrained backbone licence |

**Decision.**
- **Ultralytics: excluded,** unless the client chooses to buy an Enterprise licence. That choice is recorded here if it happens.
- **Detection, first candidate: RF-DETR Nano or Small.** Second candidate: **YOLOX-S or Tiny**, if RF-DETR is too slow on the target CPU.
- **Anomaly detection: Anomalib**, starting with PatchCore or PaDiM.
- **The final pick per check comes from a benchmark on the target PC.** Measure accuracy on the held-out station test set (NFR-ACC-3) and latency on the CPU (NFR-PERF-1). Record the result in the model card (§9).

**Consequences.**
- **Weights licences:** every model card records the licence of its code **and** of its starting weights (TD-18). Pretrained backbones and datasets can carry their own terms; check them before shipping.
- **Training tools stay separate:** they are never part of the installed product (TD-10). Only the exported ONNX file ships.

**Revisit when:** a new permissively licensed model clearly beats these on our test set, or the client buys an Ultralytics licence.

---

### TD-09 — Inference runtime

**Decision.**
- **ONNX Runtime** (MIT) on the CPU is the default.
- If the PC has an **Intel** CPU, use the **OpenVINO** execution provider of ONNX Runtime, or the OpenVINO runtime itself (Apache 2.0) for Anomalib exports, for a large speed-up on the same CPU.
- **No PyTorch in the production install.**

**Consequences.**
- **OpenVINO is not a switch.** Its execution provider ships in the `onnxruntime-openvino` package, which replaces `onnxruntime` (the two must not be installed together), and `models._session` asks for `CPUExecutionProvider` only. When the production PC arrives: swap the package in `pyproject.toml` (and the PyInstaller spec's `collect_dynamic_libs`), ask for `OpenVINOExecutionProvider` with the CPU one as fallback, check its licence for the list of TD-18, and benchmark against plain CPU (prototype test 4) (VIA-0054).
- Every model is exported to ONNX (or OpenVINO IR) during training.
- The job stores the exported file and its checksum (FR-MDL-3).
- The production install stays small, and the training stack's dependencies never reach the client's PC.
- **CPU preference:** an Intel CPU is preferred for the PC (section 3).

---

### TD-10 — Training and labeling

**Decision.**
- **Where:** training runs **offline**, on the maintainer's workstation or a rented GPU. It is never part of the installed product (§9).
- **Labeling:**
  - **CVAT** (MIT), self-hosted, as the default.
  - **Label Studio** (Apache 2.0) as the alternative.
  - Prefer running the labeling tool locally over cloud labeling services, so client images stay under control.
- **Datasets:** stored as plain folders. Each export from the station's `dataset/` gets an id and a SHA-256 manifest. Model cards point to that id.
- **Evaluation:** **Supervision** (MIT) for metrics and visualizing detections. A fixed held-out test set per job, never used for training (NFR-ACC-3).

**Consequences.**
- **Image privacy:** client images never leave controlled storage without the client's agreement. Write this into the service contract.

---

### TD-11 — Operator screen

> **Superseded in part by TD-20 (2026-10-14):** the interface is a React + Vite application described in `docs/frontend.md`; the choices of a local web UI served by the core and of Edge kiosk mode stand.

**Context.** The screen only talks to the core through the API (§3.1, §10.1). It must be:
- full-screen;
- impossible for the operator to close by accident;
- readable from 2 m (NFR-USA-2);
- in Portuguese.

**Options:**

| Option | For | Against |
|---|---|---|
| **Local web UI + Edge kiosk** | Edge is already on every Windows PC; kiosk mode gives a locked full-screen; the same page works for remote support from another PC; works unchanged on Linux | Live video goes through the API (fine at ≤ 10 fps) |
| PySide6 / Qt desktop app | Native feel, direct video drawing | LGPL obligations; another large dependency; harder remote viewing |
| Tkinter | Ships with Python | Dated look, weak for an operator-facing screen |

**Decision.**
- **Local web UI**, served by the core: plain HTML, CSS and JavaScript, with no build step and no front-end framework.
- Opened at login with `msedge --kiosk http://localhost:<port>/ --edge-kiosk-type=fullscreen`.
- **Admin screens:** job editor, results and backup are pages of the same web app behind login (FR-ADM-1).

**Consequences.**
- **Drawing ROIs:** the job editor needs a simple canvas tool for drawing ROIs on the reference image. Planned as the largest single UI task.
- **Remote support:** possible by opening the same URL from another PC, if the client allows the API on the network (NFR-SEC-3).

---

### TD-12 — Core API

**Decision.** **FastAPI** (MIT) on **Uvicorn** (BSD).
- HTTP for commands and queries.
- One WebSocket for live view, state and result events.
- Pydantic models define every request and response.
- The API listens on `127.0.0.1` by default.

---

### TD-13 — Storage and formats

**Decision.**

| Data | Format | Library |
|---|---|---|
| Job definition | YAML (`job.yaml`, `profile.yaml`) | PyYAML, loaded into Pydantic models with a schema per `format` version |
| Hikvision raw settings | XML, stored as returned by the camera | stored as-is; parsed only to compare |
| Job / backup files | ZIP + `manifest.json` with SHA-256 | Python `zipfile`, `hashlib` |
| Results, audit log | SQLite, WAL mode | Python `sqlite3` |
| Images | PNG for reference/test images (lossless); JPEG for result images (smaller) | OpenCV |

**Why YAML:** a Maintainer can read and diff a job by hand. Pydantic validation catches typos and wrong types on load, so the format's leniency doesn't let bad jobs through.

---

### TD-14 — Running unattended

**Context.**
- The core must start with Windows, run without a logged-in user, and restart on crash (NFR-REL-2/6).
- Windows runs services in a separate session (session 0). Opening a USB webcam from a service, rather than from a user's desktop session, is not guaranteed to work. The IP camera has no such issue.

**Decision.**
- **Production (Hikvision):**
  - the core runs as a **Windows service**, wrapped with **WinSW** (MIT);
  - startup Automatic (Delayed), with automatic restart on failure;
  - logs to `logs/`.
- **Prototype (C920):** first test the same service setup with the C920.
- **Fallback, if the service can't open the C920:** run the core as a **Task Scheduler task at user logon**, with "restart on failure", plus a small watchdog that restarts it if `/state` stops answering.
- **Operator session:** Windows auto-logon to a dedicated limited user, which opens Edge in kiosk mode (TD-11).

**Consequences.**
- **Two setups:** the installer supports both start-up modes, chosen in `system.yaml`.
- **Auto-logon credentials** follow the client's IT policy.

---

### TD-15 — Packaging and updates

**Decision.**
- **Build:** **PyInstaller**, one-folder mode. Its licence (GPL with a bootloader exception) allows closed commercial distribution.
- **Installer:** **Inno Setup**. It installs the program, the service wrapper and the kiosk shortcut.
- **Locations:**
  - program files in `C:\Program Files\VisionSystem\`;
  - all data in `C:\ProgramData\VisionSystem\` (§4.4, §11).
- **Updates:** a new installer version. It stops the service, replaces the program files, leaves data untouched and starts the service again. Jobs in older formats are upgraded on read (§4.2).
- **Version stamping:** each build carries its version, the git commit and the licence list (TD-18).

---

### TD-16 — Secrets

**Decision.**
- Camera and user passwords are stored in **Windows Credential Manager** through `keyring` (MIT), under the account the core runs as.
- `system.yaml` holds only the name of the credential.
- Job and backup files never contain secrets (§4.2).

**Clarification (2026-10-14).** Supervisor and Maintainer passwords are checked, never read back, so they are kept only as scrypt hashes in `system/users.json` (`vision_station.api.auth`), with a lock of 30 s after 5 wrong attempts. Credential Manager is used for the camera password, which the core has to send to the camera.

**Consequence.** After a restore on a new PC, the Maintainer re-enters the camera password. This is part of UC-06, step 2.

---

### TD-17 — Testing

**Decision.**
- **Unit and integration tests** with **pytest**.
- **File camera driver** (§5.3) replays stored images, so the whole pipeline runs without hardware.
- **Reference-set tests:** every job in a test fixture folder must give its expected results (§7.3, part 2). This is the automated proof of NFR-REL-5.
- **Round-trip tests:** export → import → compare, for jobs and backups.
- **Continuous integration** on a Windows runner (GitHub Actions `windows-latest`). The same tests also run on Linux to keep the core OS-independent (NFR-POR-2).
- **Hardware tests:** run by hand, from a checklist, on the bench and on site (section 7).

---

### TD-18 — Licence compliance

**Decision.**
- Only MIT, BSD, Apache 2.0, PSF, public domain or similarly permissive licences in the shipped product.
- LGPL is acceptable only when dynamically linked and unmodified (the FFmpeg inside OpenCV), or, for a Python package, when it ships unmodified outside the bundled archive so the user can replace it (asyncua, TD-24).
- **No AGPL or GPL code ships.** The PyInstaller bootloader exception is the one GPL-licensed exception, and it explicitly allows this use.
- The build generates `THIRD_PARTY_LICENSES.txt` (e.g. with `pip-licenses`) and fails if a disallowed licence appears.

**Main components and licences:**

| Component | Licence |
|---|---|
| Python | PSF |
| OpenCV (+ bundled FFmpeg) | Apache 2.0 (+ LGPL) |
| NumPy | BSD |
| ONNX Runtime | MIT |
| OpenVINO | Apache 2.0 |
| duvc-ctl | MIT |
| python-snap7 (S7 adapter, TD-23) | MIT |
| pymodbus (Modbus adapters, TD-23) | BSD-3-Clause |
| Babel (server text catalogs, TD-30) | BSD-3-Clause |
| asyncua (OPC UA adapter, TD-24) | LGPL-3.0, shipped unmodified and replaceable |
| requests | Apache 2.0 |
| FastAPI / Uvicorn / Pydantic | MIT / BSD / MIT |
| PyYAML | MIT |
| keyring | MIT |
| SQLite | Public domain |
| WinSW | MIT |
| React, Radix UI, Tailwind CSS, shadcn/ui, TanStack, Zustand, Zod, Vite (web interface, built into the bundle) | MIT |
| lucide-react / IBM Plex fonts (web interface) | ISC / SIL OFL |
| PyInstaller | GPL with bootloader exception |
| Inno Setup | Inno Setup licence (free, commercial use allowed) |
| RF-DETR Nano–Large / YOLOX / Anomalib | Apache 2.0 |
| Supervision, CVAT / Label Studio (training side only, not shipped) | MIT, MIT / Apache 2.0 |

---

### TD-19 — General platform for fixed stations

**Context.**
- The first idea was a system for one job: check that a box is closed and taped (documents 01–03).
- The decision (2026-10-13) is that `vision-station` is a base for any typical industrial **station**: a fixed camera that identifies **objects**, **colors** or **codes**. The packaging application is built on it, not the other way round.
- The commercial tools the client's staff already know (Cognex In-Sight, Keyence) work like this: a *job* holds a camera setup and a list of *tools*, each tool looking at a region the user draws. The In-Sight Explorer reference lists the tool families Blob, Color, ID (bar codes and 2D codes), Pattern Match, Edge, Flaw Detection, Histogram and OCV/OCR ([Cognex](https://docs.cognex.com/is_611/web/EN/ise/Content/Reference/VisionTools.htm)).
- A search for an open-source equivalent (no-code, jobs and tools, camera I/O) found none; the usual base is OpenCV plus own code. So the editor and the job model are ours to build, which is the main cost of this decision.

**Options.**

| Option | For | Against |
|---|---|---|
| A. Keep the specific design (box + tape checks) | Smallest scope; fastest to 30/10 | Every new application needs core changes; box and tape words leak into code, screens and files |
| **B. General contract now, tools added by priority** | The job format, the tool contract and the vocabulary are right from the start; the first application only needs the tools it uses; each new tool is a new module, not a redesign | A little extra work now (renames, contract, docs); tools beyond the first application's need wait |
| C. Full no-code editor and all tool families from the start | Closest to a commercial system | Largest scope by far; cannot be done by one developer by 30/10; most tools would be untested against a real use |

**Decision: option B.**

1. **Vocabulary.** A *check* is now a **tool**. A job has an ordered list of tools; each tool has a `type`, a `version`, a region (`roi`), `params`, a `reason_fail` text and returns pass/fail plus a score. The decision rule stays `all_pass`.
2. **Regions.** `box` becomes **`anchor`**: the thing the **locator** finds in the image (a box, a part, a label). ROIs are relative to the `anchor` or to the `frame`. A job without a locator uses only the `frame`. The format is not released yet (`format: 1`), so this changes without a migrator.
3. **First tool families** (in this order of delivery):

| Tool `type` | What it does | Training | Library (licence) | Used by |
|---|---|---|---|---|
| `color` | Fraction of the region inside a color range (hue, saturation, value), or distance to a reference color. User draws the validation area. | none | OpenCV (Apache 2.0) | a colored part, cap, tape or mark is present |
| `code` | Reads 1D bar codes and QR / Data Matrix codes in the region, optionally compares with an expected text or pattern. | none | **zxing-cpp** (Apache 2.0, Windows wheel for Python 3.12). OpenCV's own `barcode_BarcodeDetector` and `QRCodeDetector` are built into the wheel and stay as a fallback. | any station that reads a label |
| `pattern` | Finds a template (logo) or counts repeats along a line. | none | OpenCV (Apache 2.0) | a logo or feature is present; a printed tape along a seam |
| `detect` | Runs a trained object detector or anomaly model on the region. | **yes**, offline | ONNX Runtime (MIT), model per TD-08 | defects that need learning; "which objects are present" |

   All four are part of the platform for the first delivery (amendment below); `detect` needs the offline training path (TD-08).
4. **Trigger modes.** (Amended by TD-32: the choice is `acquisition.trigger.type`, with the parameters of each type next to it.) A job picks one: `image_presence` (object present and still, as today), `manual`, `external`, or `continuous` (no trigger; still frames inspected one after another, e.g. a code reader). `continuous` is named now and built when a project needs it. Objects that move during capture are out of scope.
5. **Screen text comes from the job and the language file**, not from code: "Aguardando caixa" becomes the job's `ui.waiting` text, with a neutral default.
6. **Repository layout.**
   - `src/vision_station/`: the platform (cameras, jobs, tools, station, API, screen). No customer words.
   - Customer projects live **outside** this repository (amendment of 2026-10-15 below).
7. **Cameras.** Unchanged: the camera is a plugin (TD-04, TD-05). The C920 is the camera for the first application; the Hikvision driver comes later and serves every application.
8. **Documents.** Documents 01–05 describe the platform (rewritten on 2026-10-15). A project's scope, requirements and acceptance numbers are written in the project.

**What the C920 means for the general tools.** The search for similar projects found the C920 used with OpenCV in real prototypes (for instance a firmware test rig for electricity meters, University of Ljubljana) and sold with C/CS-mount rework kits by Kurokesu; forum reports also warn about inconsistent frame rates and prefer fixed focus for vision work. On the bench PC the driver measured 30.7 fps in MJPG at 1920×1080 with every setting read back. For the tools it means:
- **Codes (measured on the bench PC, 2026-10-13/14, C920 at 1920×1080, focus fixed, sheet printed at 100%):**
  - **Even light, 33 ms exposure, gain 0** (about 3.3 and 3.9 px/mm in two shots): QR and Data Matrix modules of 1.02 mm (about 3.4 to 4 px) were read, 0.68 mm (about 2.2 to 2.7 px) were not. Code 128 with 0.51 mm bars (about 1.7 to 2 px per bar) was read, 0.34 mm (about 1.1 px) was not.
  - **Phone torch, 7.8 ms** (about 4.8 px/mm): QR at 0.68 mm (3.3 px) was read; Data Matrix needed 1.02 mm; Code 128 at 0.51 mm was *not* read in that shot. The hot spot and glare of a single torch hurt more than the pixel count helped, so light quality changed the limit by about 1 px.
  - **Bench with its own lights, 7.8 ms, gain 0 (2026-10-16, about 3.9 px/mm):** QR and Data Matrix from 0.68 mm (about 2.7 px) were read in every frame (141 of 141); Code 128 only now and then. The fixed focus mattered: at that distance the sharpness peaked at focus 35–40 and fell fast above 45, so the focus value is set per job, at the working distance.
  - **Rule used for design (with margin): at least 4 px per module for QR and Data Matrix, and at least 2 px per bar for Code 128.** The smallest module is `4 / (px per mm)`: a field of 600 mm across (3.2 px/mm) allows modules of about 1.3 mm; 900 mm across (2.1 px/mm) allows about 1.9 mm.
  - **Light, not the camera, was the main limit.** With ambient light only and 7.8 ms, gain 0, the sheet came out at brightness 20 of 255 and nothing was read. Raising the exposure to 33 ms (about 1/30 s, fine for a still scene) gave an evenly lit sheet and the results above. Raising the gain made the image almost saturated. Brightening dark frames by software recovered only one or two codes (8-bit noise). So: dedicated, diffuse light, fixed exposure and gain 0.
- **Objects and colors:** fine for a fixed scene with fixed light. Light matters more than the camera (TD-06). A webcam has a rolling shutter: moving objects blur, so the object must be still when captured.
- **Limits:** no hardware trigger, a fixed wide lens (distortion at the edges), USB cable length limits. For stations with these needs the Hikvision camera or a GigE industrial camera is the next step.

**Consequences and trade-offs.**
- **Cost now:** about 3 h to rename and document, plus the contract work in the tool tasks; roughly +30 h to the plan for the platform pieces (code tool, a region editor, the detect tool), most of them after the first delivery.
- **Risk to 30/10:** the editor (drawing regions on a live image) is the biggest new item. For the first delivery, regions can be edited in the job file and drawn in a small tool; the full screen comes after.
- **Benefit:** the second application does not touch the core. The jobs, backup, verification, results and API are all application-independent from the start.
- **Danger:** a platform with no second application can become over-built. Rule: a tool is written only when an application uses it, except `code`, which is cheap and testable without hardware.
- **Licences:** all four tool families use Apache 2.0 or MIT components (TD-18). `pyzbar` is not used because it needs the LGPL ZBar library.

**Revisit when:** a second application is defined, or the Hikvision camera replaces the C920, or the editor proves too large for one developer.

**Amendment (2026-10-15): the platform stands alone.**
- Vision Station is a vision system for **industrial fixed stations and machines** where the object is **stopped** for the reading. It is not built from any one product: a packing station that checks boxes and tape is a **project that uses it**, configured with jobs (locator, `color`, `pattern`), and is done last, when its samples arrive.
- `applications/` is removed from this repository. Each customer project (jobs, reference images, acceptance data, customer notes) lives in its own place and installs Vision Station. The platform repository holds only the platform, its tests and neutral examples.
- Documents 01–03 are rewritten as platform documents; the earlier packaging versions are kept with the project's records.
- The tools and locators are built and tested with synthetic and bench images, not with one customer's samples. The first delivery has the four tool families, locators beyond `fixed`, and job editing on the screen (FR-PLT-7 becomes Must).

---

### TD-20 — The web interface controls the system

> **Extended by TD-29 and TD-30 (2026-10-16):** React Aria and more shadcn components are added (TD-29); the interface becomes bilingual (TD-30). The rest of this decision stands.

**Context.**
- TD-11 chose a local web UI in Edge kiosk mode, "plain HTML, CSS and JavaScript with no build step and no framework". At that point the UI was an operator screen plus a few admin pages.
- The decision (2026-10-14) is that the interface is *how the system is operated*, like the software of a commercial vision system: parameters, settings, access, live view, job import and export, region drawing, results and training data. That is more than twenty screens with shared state, forms, tables and a canvas editor.
- A first prototype with Preact + htm (vendored, no build) was written the same day (VIA-0013). The Rams audit of it scored 18/30 (`docs/design/DESIGN-IS-2026-10-14/`), and the owner decided on **React with a build tool and a proper design system**.
- The station may have no internet, and the PC is Windows with Edge.

**Options.**

| Option | For | Against |
|---|---|---|
| A. Plain JS (TD-11 as written) | Nothing to build | Hand-written DOM updates for every screen |
| B. Preact + htm, vendored, no build (the prototype) | 16 KB, no Node | Small ecosystem for tables, forms, accessibility primitives; templates are strings; no types; the design system would be hand-built |
| **C. React + TypeScript + Vite** | Largest ecosystem (Radix, TanStack, testing tools); strict types across screens and API; hashed, split bundle; the owner's choice | A Node build step (CI and installer), more dependencies to keep |
| D. Desktop UI (Qt/PySide6) | Native widgets | LGPL obligations, harder remote support, the web interface is already the plan |

**Decision: option C.** The details are in document 05 (`docs/frontend.md`); the points that shape the rest of the system are:

1. **Stack.** React, TypeScript (strict), Vite, Tailwind CSS with design tokens, shadcn/ui components on Radix primitives, lucide icons, IBM Plex fonts self-hosted, React Router, TanStack Query (REST), Zustand (live state), React Hook Form + Zod, TanStack Table. All permissive licences (TD-18); axe-core (MPL-2.0) only in tests.
2. **API contract.** All API paths move under `/api` (`/api/live` for the WebSocket); every endpoint has Pydantic request and response models; TypeScript types and the client are **generated** from the OpenAPI document and CI fails if they are stale.
3. **Serving.** `npm run build` writes to `frontend/dist/`; the API serves it with a fallback to `index.html`, hashed assets cached as immutable, a strict Content-Security-Policy. The build is not committed; CI builds it and the installer includes it. Node is needed to build, never to run.
4. **Roles decide what is shown, the server decides what is allowed** (FR-UI-6): the same permission table in the router and on every endpoint.
5. **Forms come from the tools.** The API lists every tool type with the JSON Schema of its parameters and the editor draws the form from it, so a new tool needs no screen code (FR-PLT-2).
6. **Design system.** One token set (8 neutrals, 4 status hues, 8 type sizes, 4 px grid, 2 radii plus pill), dark default and light, contrast checked; colour means status only and always comes with an icon and a word (NFR-USA-2).
7. **Quality gates.** Component and end-to-end tests (Playwright against a simulated station), axe with zero serious violations, a size budget in CI, and a definition of done that includes every state and a look in a real browser.

**Consequences.**
- The prototype was deleted when the new operator screen reached parity (VIA-0033), and nothing of the interface lives in the Python package. TD-11's "no framework" and the Preact + htm choice are superseded.
- A Node toolchain enters CI and the build of the installer. The lockfile pins every dependency; updating means re-running the tests.
- The server needs the work in VIA-0031 and VIA-0026 (prefix, response models, new endpoints) before the screens beyond the operator screen can be built.
- The region editor (drawing on a canvas, with undo, zoom and keyboard control) is still the largest single UI task.

**Revisit when:** the bundle budget cannot be met, or the team grows and a component library with a stronger ecosystem is worth the weight.

---

### TD-21 — Pose-based fixtures and job format 2

**Context.**
- Locators return an axis-aligned rectangle (`Anchor.rect`). The `template` locator tolerates a shift, not a rotation or a change of size; `blob` returns the upright rectangle around the region.
- NFR-ACC-4 already asks for ±10° of placement tolerance, so jobs cannot meet it today.
- Every commercial system reviewed (Cognex fixtures, Keyence position adjustment, QuaSolo coordinate-system tool) inspects in the part's own coordinate system.

**Options.**

| Option | For | Against |
|---|---|---|
| Keep rectangles; ask projects to use jigs | No work | NFR-ACC-4 unmet; every rotated part is a FAIL or an ERROR |
| Rotation-aware tools (each tool handles angle) | No geometry layer | Every tool gets more complex; easy to get one wrong |
| **Pose-based fixtures + upright region cut** | Tools unchanged; one place handles geometry; fixture chains possible | Job format change (2) and a migrator; interpolation on rotated cuts |

**Decision.**
- A locator returns a fixture with a pose `(x, y, angle, scale)` and a taught size. ROIs are fractions of a fixture's size in its own axes. The geometry component cuts each region **upright** with `cv2.warpAffine`, so tools keep their contract (architecture §14).
- Fixtures are an ordered list; each may search inside a previous one. Each states its allowed angle, scale and position range; outside it is ERROR E202.
- Job format 2; format 1 migrates (anchor = fixture `anchor`, angle 0, scale 1) with identical results on the reference set.

**Consequences.**
- New locators: `blob` v2 (angle from `minAreaRect`), `shape` (TD-25), `edges` (two-edge corner).
- Tool details with coordinates are mapped back to frame pixels for the overlay by the geometry component.
- The editor must draw rotated fixtures and let the user set the allowed ranges.

**Revisit when:** a project needs perspective (tilted part surfaces); then the pose becomes a homography.

---

### TD-22 — Result contract and error-code catalog

**Context.** Results carry an outcome, a Portuguese reason and scores. A PLC cannot act on Portuguese text, records cannot be counted by cause, and OPC 40100 needs a typed result content.

**Decision.**
- One result structure (architecture §10.3) for the pipeline, the records, the API, the machine interface and OPC UA: sequence, job version and content hash, trigger source and part id, outcome, **error code** from a stable catalog (E1xx image, E2xx location, E3xx region/tool, E4xx camera, E5xx system, E6xx machine), **reason codes** `<tool type>.<criterion>`, per-tool values with units, fixture poses, stage timings, `simulated`.
- Codes are never reused or renumbered; texts may be reworded.
- The API keeps today's fields and adds the new ones.

**Consequences.** Every internal "stop" in the pipeline carries a code; a test checks that each code in the catalog is reachable and documented.

---

### TD-23 — Machine interface: one handshake, thin adapters (S7, Modbus TCP, remote I/O)

**Context.**
- Typical customers use, in order: Siemens S7 (S7-1200/1500), Modbus TCP, OPC UA, plain 24 V I/O.
- PLC programmers expect the smart-camera handshake (trigger enable/ready/ack, acquisition done, results valid, acknowledge, error and clear error, job number).
- Requirement: never a false PASS at the PLC.

**Options for Siemens.**

| Option | For | Against |
|---|---|---|
| **S7 protocol, PC as client of an interface DB** (python-snap7, MIT) | What Siemens integrators expect (a DB); no PLC code beyond the DB and a small FB | PUT/GET must be enabled and the DB must not be optimized; PUT/GET is unauthenticated plaintext |
| **Modbus TCP, PC as server, PLC as client** (pymodbus, BSD-3) | Works with any brand; no PUT/GET; PLC-side code with the standard Modbus client instruction | No authentication in Modbus; register mapping is less readable |
| PROFINET device stack on the PC | Native to Siemens | Needs a licensed or GPL stack; the PC becomes an I/O device; much more work |
| OPC UA (S7-1500 as client, or MES) | Secure, typed | Not every S7-1200 can be a client; heavier for a cyclic handshake |

**Decision.**
- One **handshake engine** with a versioned **interface map v1** (architecture §16.2). Adapters only move fields: **S7 client** (python-snap7) and **Modbus TCP server** (pymodbus) first; **remote I/O** as a Modbus TCP client of a 24 V I/O module (pymodbus); OPC UA later (TD-24).
- Adapters run in their own threads at a fixed cycle (proposed 10 ms) and drive the controller only through its existing commands.
- Fail-safe rules (architecture §16.3–16.5): edges start actions; fields before valid; Pass/Fail/Error only while ResultValid; heartbeats both ways; simulated results never signalled.
- Job numbers and products are system configuration, not job content.
- No PROFINET/EtherNet/IP device stack. No USB I/O boxes.

**Consequences.**
- New dependencies: python-snap7 (MIT; since 3.x pure Python per its PyPI page) and pymodbus (BSD-3). Both are permissive (TD-18).
- Installation guide: how to enable PUT/GET and a non-optimized interface DB, with the security note and the Modbus alternative (NFR-SEC-6).
- Deliverable D12: interface map document, TIA Portal interface DB and function block (handshake + heartbeat check) for S7-1200/1500.
- Test suite: a simulated PLC for both adapters; fail-safe tests (kill the core, drop the link, stop the heartbeat); 72-hour soak (NFR-REL-9).

**Revisit when:** a customer requires PROFINET or EtherNet/IP natively, or OPC UA replaces the cyclic handshake at a site.

---

### TD-24 — OPC UA server (OPC 40100-1) on asyncua, shipped replaceable

**Context.**
- OPC 40100-1 is the standard way to expose a vision system to MES and modern PLCs (project doc 05). Target profile: *Simple Inline Vision System*.
- asyncua is the only maintained Python OPC UA server. It is **LGPL-3.0**; its server supports encryption and certificates, and its user model distinguishes admin and user roles (a custom `UserManager` can be supplied). Importing the MachineVision NodeSet has a known open issue around `ResultType`.
- TD-18 allows LGPL only dynamically linked and unmodified.

**Decision.**
- OPC UA adapter on asyncua, after S7 and Modbus (phase E).
- Shipped **unmodified and replaceable**: the asyncua package is kept outside the PyInstaller archive, as plain files the user can replace, with its licence and a source offer (NFR-LIC-3). TD-18 is amended accordingly.
- SignAndEncrypt by default; state-changing methods check the session's user and role in our handlers.
- First task: load the official MachineVision NodeSet; if the import fails, build the needed types in code.

**Consequences.** The licence list gains one LGPL entry with the replacement instructions. A third-party 40100 client (e.g. the OPC Foundation .NET samples, `Opc.Ua.Vision*`) is used to test the server.

**Revisit when:** a permissively licensed Python OPC UA server appears, or a customer requires certification.

---

### TD-25 — Algorithms for shape matching, calipers and the variation model

**Context.**
- The minimum tool set needs rotation- and scale-tolerant shape matching (`pattern` v2, `shape` locator), 1D calipers with subpixel edges (`edge`, `edges` locator) and a per-pixel variation model (`compare`).
- OpenCV has the building blocks (Sobel, pyramids, `matchTemplate`, `warpAffine`) but no ready shape matcher of this kind.
- Fullseye (Apache 2.0) contains NumPy implementations of all three (`shapematch.py`, `measuring1d.py`, `inspection.py`) but is ~770 k lines across ~1 700 flat modules, one author, beta (0.6.0, Oct 2026), with a scope far beyond ours.

**Decision.**
- Implement the three algorithms in `algorithms/`, small and tested, following the published methods (gradient-direction shape matching on a pyramid; 1D projection with Gaussian-derivative edges and subpixel interpolation; mean ± k·σ per pixel after alignment).
- Fullseye code may be **ported** where it helps, keeping the Apache-2.0 attribution (THIRD_PARTY_LICENSES, NOTICE). **Fullseye is not a dependency.**
- For shape matching, benchmark the NumPy implementation against an OpenCV multi-angle NCC pyramid on tier M; keep the faster one that passes V4.

**Consequences.** Three algorithm modules with their own golden and invariance tests (V2–V4) and benchmarks (V8).

**Revisit when:** a permissive library offers a maintained, faster shape matcher.

---

### TD-26 — OCR

**Decision.** Tier-2 `ocr` tool (read, or verify an expected text or pattern) on **RapidOCR** (Apache 2.0, PaddleOCR models in ONNX), to be evaluated on lot and date prints at the station before it is committed. Tesseract (Apache 2.0) is the fallback. No cloud OCR.

**Revisit when:** the evaluation shows poor results on dot-matrix or inkjet prints; then consider a small model trained offline for the font (document 07).

---

### TD-27 — Teaching from good parts on the station

**Context.** Integrators expect to teach "what good looks like" at the station (Keyence Learning, Cognex Flaw Detection, QuaSolo "looks-right"). TD-09 forbids PyTorch in production.

**Decision.**
- **`compare`** (tier 1): variation model — per-pixel mean and tolerance from N aligned good regions; defect = pixels outside mean ± k·σ, filtered by area. Pure NumPy/OpenCV.
- **`anomaly`** (tier 2): patch features from a small backbone in ONNX (candidates: ResNet-18 from torchvision, BSD; DINOv2 ViT-S/14, Apache 2.0 — not the XRay/Cell DINO variants, which are non-commercial), a coreset memory bank stored in the job's `taught/`, nearest-neighbour distance as the anomaly map. Teaching is NumPy on the CPU; fixed random seed.
- Heavier anomaly models stay offline with Anomalib (Apache 2.0) and are exported (document 07).

**Consequences.** The backbone file and its licence are part of the program (not of each job) and listed in THIRD_PARTY_LICENSES; the job records which backbone version taught it and refuses to run with another.

**Revisit when:** benchmark B-1 shows tier M cannot teach within NFR-PERF-5.

---

### TD-28 — CPU-only PC tiers and the built-in benchmark

**Context.** Stations will not have a dedicated GPU. Some customers want low-cost fanless mini-PCs; others accept a desktop-class CPU.

**Decision.**
- Two tiers, both without a dedicated GPU: **M** (Intel N100/N97/N150 class, 16 GB) and **R** (Core i5 12th gen or newer / Core Ultra 5, 16–32 GB). Section 3 replaces the single specification.
- A built-in **benchmark** (FR-ADM-5) runs at first start and on demand: a fixed workload plus the jobs' reference sets; it records times per stage and tool, classifies the PC and sets thread caps.
- The Intel integrated GPU may be used through OpenVINO only when the benchmark shows a gain, and never as a requirement (NFR-PERF-3).
- Targets per tier are in document 02 (NFR-PERF-5) and stay *proposed* until **bench test B-1** (section 7) on one real unit of each tier.

**Consequences.** Model cards state latency per tier (FR-MDL-6); the editor compares each job with its budget on the PC it runs on.

**Revisit when:** B-1 results are in.

---

### TD-29 — Interface components: keep shadcn/ui + Tailwind, add React Aria

**Context.**
- TD-20 chose React + TypeScript + Vite with shadcn/ui on Radix and Tailwind. The result (document 05 v0.1) is accessible and tested: 23 base components (~1 600 lines), tokens with tested contrast, design-rule and accessibility tests, a gallery. It did not yet feel like vision software (document 05 v0.2).
- The redesign needs rich controls: multi-thumb sliders, number fields with units and locale formatting, colour channels in HSB, resizable panels, a command palette, charts. On top of them it builds its own vision controls (tolerance gauge, HSV range picker, histograms, profiles, image workspace) — **with any library**.
- The screens of the editor and the operator are redesigned whichever library is used.
- Document 04 v0.8 recorded a migration to Mantine. The owner reviewed the trade-offs the same day and reverted it.

**Options.**

| Option | For | Against |
|---|---|---|
| Migrate to **Mantine 9** | Complete library with RangeSlider, NumberInput, Stepper, AppShell, Spotlight, charts out of the box; we stop owning base components | Re-founds a tested layer (components, tokens pipeline, design-rule tests) on top of the screen redesign; Tailwind removed or run beside a second styling system; Mantine's ColorPicker has no HSV ranges, so the vision controls stay custom anyway |
| **Keep shadcn + Tailwind, add React Aria and catalog components** | Keeps the tested foundation; React Aria brings the exact primitives the vision controls need (multi-thumb `Slider`, `NumberField`, `ColorArea`/`ColorSlider`/`ColorField` in HSB) with strong accessibility and locale formatting; shadcn now publishes React Aria variants of its components | We keep owning the base components; two primitive families (Radix and React Aria) side by side |
| Ark UI / Park UI, Blueprint, MUI, Ant Design | Complete sets | A third foundation (Ark), a dated look (Blueprint), or a strong identity hard to bend to an HMI (MUI, Ant) |

**Decision.**
- **Keep shadcn/ui + Radix + Tailwind** and the token and design-rule tests.
- Add **React Aria Components** (Apache-2.0) for colour, range and number controls, through shadcn's React Aria variants where they exist and thin wrappers otherwise. Radix stays for everything else (dialogs, menus, popovers, tabs, select).
- Add from the shadcn catalog: `Sidebar`, `Resizable` (react-resizable-panels), `Command` (cmdk), `Accordion`, `Drawer`, `Chart` (Recharts). `Drawer` is built on the Radix dialog, like `Sheet` but from the bottom, and not on `vaul`, which is no longer maintained (UI-C1, 2026-10-17).
- Add `@dnd-kit/core` + `@dnd-kit/sortable` (stable 6.x) for reordering.
- No migration plan: additions in steps UI-C0..C3 (document 05 §15.2).

**Consequences.**
- One styling system (Tailwind + tokens), as today.
- React Aria components are styled through their `data-*` state attributes with the same Tailwind names; a rule in the design-rules test keeps them on tokens.
- Operator-route JS budget: 150 → 160 KB gzip, for the i18n runtime (TD-30), re-measured after UI-C2.
- **Measured after UI-C2 (2026-10-17):** the operator route loads its entry chunk, the chunks `index.html` preloads and the catalog of its language: **187 KB + 9 KB gzip**. Before UI-C2 the same count was 177 KB, already above 150: the size check (`npm run size`, `dist/assets/index-*.js`) counts only the entry chunk, which now holds 67 KB after the catalogs became chunks of their own. The check still passes but covers about a third of what the screen loads. Open decision (Lucas): raise the budget, trim the preloaded chunks, or measure the entry plus its preloads. All JS: 459 of 500 KB.

**Revisit when:** keeping the base components costs more time than the screens, or a single library covers the colour and range primitives with the same accessibility.

---

### TD-30 — Interface in Portuguese and English

**Context.** Document 05 v0.1 made the interface pt-BR only (owner, 2026-10-14), with every string in `texts.ts`. On 2026-10-16 the owner asked for Portuguese **and** English. Texts come from three places: the interface, the server (state messages, error-code texts, tool labels, reports) and the jobs (`reason_fail`, `ui.waiting`).

**Options.**

| Option | For | Against |
|---|---|---|
| **Lingui** (MIT) | Messages written in the code in the source language and extracted; catalogs compiled at build (small runtime; a missing translation fails the build); ICU plurals; **PO files**, the same format as Python's gettext/Babel, so one workflow serves interface and server | Build step (Vite plugin, CLI) |
| i18next / react-i18next (MIT) | Most used; runtime JSON | No compile-time check; larger runtime; JSON on the client and PO on the server would be two formats |
| Keep `texts.ts` with two objects | No dependency | No extraction, no plurals, no translator tooling |

**Decision.**
- **Lingui** in the interface, source language **pt-BR**, second language **en**; PO catalogs in `frontend/src/locales/`.
- **Server texts** in a PO catalog read with **Babel**, chosen by `Accept-Language` (`?lang=` on the WebSocket, the station language when a request names none); codes stay the contract (TD-22).
- **Operator screen** follows the **station language** (`system.yaml`); admin users choose theirs.
- **Job texts** in both languages from job format 2 (`reason_fail: {pt-BR: …, en: …}`); a missing translation falls back to the other language and is flagged in *Validar*; format-1 texts are read as pt-BR (FR-JOB-15).
- Numbers and dates formatted by locale (`Intl`; React Aria `NumberField`).

**Consequences.**
- `texts.ts` is migrated into the pt-BR catalog (UI-C2); the server side is done in UI-C3 (VIA-0061).
- CI fails on a message without an English translation, on both sides.
- Records keep codes and values, plus the reason in the station language of the time (decision of Lucas, 2026-10-18: what is recorded in operation stays in the language it was recorded in). When results are listed, a standard text (one of the catalog's, found in either language) is shown in the language of the viewer; a text with details keeps its recorded form. CSV exports in the viewer's language are not done.

**How the server does it (UI-C3).**
- The code writes the text in Portuguese, as the interface does: `tr("Região '{name}' fora da imagem", name=name)`. That is a `Msg`, a `str` that already reads in Portuguese and also carries its msgid and parameters. The core, the records and the comparison with a job's reference set (`reason_contains`, FR-JOB-9) work in that one language whatever the station speaks.
- Only the API renders, per request or per WebSocket, in the language of that person (the controller's one event is built again for each language). The hub carries one message and each socket asks for its language.
- The English texts are `src/vision_station/core/locales/en/LC_MESSAGES/messages.po`, whose msgids are the Portuguese texts. There is no compile step: the file ships as package data and the PyInstaller spec collects it. `uv run python -m vision_station.core.i18n_extract --update` finds the texts in the code (`tr`, `render`, the message of `Problem`, the labels of the forms) and adds the new ones, empty; a test fails on an empty or leftover entry, on an f-string where a `tr` belongs, and on a translation that loses a `{field}`.
- The parameter forms of tools and locators are served with titles, descriptions and choice labels translated on a copy of the schema; validation is untouched.
- **Known limit until job format 2 (R1, VIA-0070):** a job's own texts (`reason_fail`, `ui.waiting`) are read as Portuguese, so on an English station the reason of a FAIL stays in the job's language. Technical tails (a camera's own error, a file name, a pydantic field message) are not translated.

**Revisit when:** a third language is needed (add a catalog; nothing else changes).

### TD-31 — Trigger timing and remote I/O outputs, from the market reference

**Context.** Document 09 (2026-10-17) compared Vision Station with Cognex In-Sight and Keyence IV/IV3, feature by feature. Six gaps touched the trigger and the outputs a machine sees. The owner decided them on 2026-10-17, plus the output polarity.

**Decisions.**

| # | Topic | Market | Decision |
|---|---|---|---|
| 1 | Trigger delay, mode *Pela máquina* | Cognex 0–10 000 ms; Keyence 0–1 000 ms, default 0 | **0–1 000 ms, default 0, per job** (`trigger.delay_ms`). It depends on the part and the mechanics, as in both vendors (FR-TRG-6). The wider Cognex range mostly admits configuration mistakes |
| 2 | Interval, mode *Contínuo* | Cognex default 500 ms; Keyence *Internal* default 50 ms | **Minimum interval 500 ms by default, per job** (`trigger.interval_ms`; 0 = as fast as possible). Leaves CPU on tier M and keeps the record readable; the still-scene rule of FR-TRG-5 stays (FR-TRG-7) |
| 3 | Refused triggers | Cognex *ERR: Missed Acquisition*, *Acquisition Error*; Keyence *Trigger Error* output and count | Keep the `TriggerRefused` pulse (§16.2). **Add a counter** per job, shift and day in the statistics, and make it **assignable to a remote I/O output** (FR-INT-14). No alert in this version |
| 4 | Error output polarity | Keyence: Error is N.C. by default | **Error stays normal** (energized on error), as are all outputs. The owner prefers the behaviour every integrator reads at a glance. Consequence: a cut wire or an unpowered I/O module is not seen on that line; it is caught by the PLC heartbeat (NFR-REL-8) or, on lines without a PLC, by wiring the *Online* output as a "healthy" lamp or relay. The integrator can invert any output (decision 7) |
| 5 | Delayed reject | Cognex *Acquisition Delay (N)* 0–1 000 and *Time After Trigger* 0–10 000 ms; pulse 1–1 000 ms | **Both forms**: after **N inspections** (fixed-pitch conveyor) or **T ms** after the trigger (constant speed). Pulse 10–1 000 ms, default 100. Rejects on **FAIL and ERROR** by default, each switchable, because an unjudged object must not pass. Pending rejects in a queue. On stop, job change or restart the queue is cleared, the loss logged, and Error raised until acknowledged: a lost reject must never look like a pass (FR-INT-15). Station configuration, not job: it depends on where the rejector sits |
| 6 | Images of low-margin passes | Keyence image history *NG and OK near threshold* | **Keep every PASS whose margin on a deciding tool is below twice the margin warning limit** (default 0.05 → below 0.10), besides the 1-in-20 sample. These are the border cases fine-tune needs. Under disk pressure they go after the sampled PASS images (FR-LOG-9) |
| 7 | Output polarity | Keyence N.O./N.C. per output | **Normal or inverted per remote I/O output**, all normal by default (FR-INT-16). Lets an integrator build a fail-safe line without code |

**Consequences.**
- Job format 2 gains `trigger.delay_ms` and `trigger.interval_ms` (defaults keep old jobs unchanged). *Amended by TD-32:* in `acquisition.trigger`, inside the sub-block of their type, and written in full in every job; "defaults keep old jobs unchanged" is replaced by the migrator writing the old behaviour.
- `system.yaml › machine.remote_io.outputs` becomes a list of `{line, function, polarity}`; the `reject` function carries `on`, `delay` (`{inspections: N}` or `{ms: T}`) and `pulse_ms` (architecture §16.7).
- The handshake engine owns the reject queue; R3 adds tests for the queue, for clearing on stop and for the Error raised on a lost reject.
- Statistics (document 05 §7.13) show refused triggers; the machine monitor (§7.14) shows the reject queue.

**Revisit when:** a project needs an encoder-based tracking delay (pulses rather than inspections), or a site asks for the Error output fail-safe by default.

### TD-32 — The job's acquisition block, and the two layers: job and station

**Context.** The owner accepted document 09 v0.3 as the model on 2026-10-18 (§19–§22). Cognex and Keyence agree on two points. First, the **trigger type, its timing and the image settings are one unit that travels with the job or program**: Cognex's `AcquireImage` sits permanently in cell A0 of the job; Keyence's *Image Optimization* is the first screen of the program setup. Second, **wiring, network, identity and the way jobs are selected stay on the sensor** (`proc.set`; *Sensor Advanced*). Our job spread acquisition over three places (`trigger` and `quality` in `job.yaml`, the camera profile in its own file), the editor set the trigger late (step 5), and TD-31 said that new trigger fields have "defaults that keep old jobs unchanged", which a default of 500 ms for the continuous interval does not do.

**Decisions.**

| # | Topic | References | Decision |
|---|---|---|---|
| 1 | Which layer owns a setting | Cognex job × `proc.set`; Keyence program × *Sensor Advanced*; OPC 40100 recipe × configuration | **A setting is in the job if it follows the product and the view; in the station (`system.yaml`) if it follows the installation.** The test is whether the same job restored on another PC with the same camera must still carry it. The table of architecture §4.6 lists every case |
| 2 | One acquisition block | `AcquireImage`; *Image Optimization* | **Job format 2 has one `acquisition:` block** with the trigger, the image settings (the camera profile, orientation, the parameters of the automatic exposure) and the calibration. The driver-specific dump stays in `camera/raw/` |
| 3 | The trigger type carries its timing | Cognex *Delay* (delay or interval by type); Keyence *Internal* interval, *External* delay | `acquisition.trigger.type` is `image_presence`, `external`, `manual` or `continuous`, and **each type has its own parameters**: `external: {delay_ms, debounce_ms}`, `continuous: {interval_ms}`, `image_presence: {roi, still_ms, rearm, diff_threshold, min_area, motion_area}`. Two named fields, not Cognex's one overloaded `Delay`: a person and a PLC programmer read them without knowing the type rule |
| 4 | Trigger debounce | Cognex: in `AcquireImage` (0 – 65 536 µs, default 1). Keyence: the electrical side of IN1 is a sensor setting | **Debounce is in the job** (`external.debounce_ms`, 0 – 65 ms, default 0), as in `AcquireImage` (0 – 65 536 µs, default 1 µs). Milliseconds, because our line is read through a Modbus module, not a hardware input. The **edge** (rising or falling) and the role of each input line are **station** settings, as in Keyence *I/O Settings* |
| 5 | Written in full | Cognex writes every `AcquireImage` parameter in every job | **The writer always writes every parameter of the acquisition block, and format 2 refuses a block with one missing.** Software updates can then never change the behaviour of a saved version by changing a default (design principle 3). The editor offers the defaults of the project values (document 02 §7); the migrator writes the behaviour the old code had |
| 6 | Image parameters adopted | `AcquireImage`: Orientation, Auto Exposure (Mode, Max Exposure, Target Brightness, Auto Expose Region) | **Adopted:** `orientation` (`normal`, `mirror`, `flip`, `rotate180`, applied at acquisition so every coordinate is in the oriented frame) and, for the editor's *Auto uma vez*, `target_brightness`, `max_exposure_us` and the measuring `region`, kept in the profile so the measurement can be repeated. The job still runs with the **fixed value** it measured. **Not adopted:** continuous auto exposure (the picture would depend on the lighting of the moment, against principles 1 and 2); image area by rows (we process regions, so a smaller band saves nothing); light control (no integrated light; external lighting is a project matter); gain offset, HDR (driver capabilities, kept in `camera/raw/` when a driver offers them); buffer mode, network trigger, timestamp (not applicable) |
| 7 | Quality limits | No equivalent in either product | **Stay a separate job section** (`quality`), checked at verification and on every inspection. They are proposed from the samples, so they come after the samples in the order of work |
| 8 | Station input lines | Cognex *Discrete I/O Settings*; Keyence *I/O Settings* (IN1 edge, IN2–IN6 roles) | `machine.remote_io.inputs` is a list of `{line, function, edge}` (functions `trigger`, `clear_error`; edge `rising` default or `falling`), replacing the single `trigger_input` (architecture §16.7, FR-INT-17) |
| 9 | Order of work | Trigger is part of the first step in both products | **The trigger moves to step 1**, which becomes *Imagem e disparo*. Step 5 is *Qualidade*. The trigger control in the top bar stays and edits the same value (document 05 §4.3) |

**Consequences.**
- Job format 2 (R1, VIA-0070) carries the `acquisition` block. The migrator maps format 1: `trigger.mode` → `acquisition.trigger.type`; the presence settings → `image_presence`; `camera_profile` → `acquisition.image`; a continuous trigger without an interval → `interval_ms: 0` (it ran without one); `delay_ms` → 0; `debounce_ms` → 0.
- **Format 1 is transitional.** Code written before this decision (the continuous `interval_ms` in `trigger`, with a default of 500 ms) is aligned when format 2 is written; until then format 1 is not extended, with one exception: the profile gains an optional `orientation` (VIA-0083), applied by the program to every frame and written to `profile.yaml` only when it is not `normal`, so a job that does not use it still opens in an older version; and `exposure.auto_once` (VIA-0083, the parameters of *Auto uma vez*), written only when set.
- TD-31 stands for what it decided (delay and interval **per job**, 500 ms as the project value) and is amended in two points: where the fields live (the type's sub-block) and the rule of writing in full instead of "defaults keep old jobs unchanged".
- Documents changed with this decision: 01 (§3, §4.1, §4.4), 02 (FR-PLT-3, FR-TRG-6/7/8, FR-ACQ-10/11, FR-INT-6/17, FR-JOB-16, FR-UI-11), 03 (§1, §4.1, §4.2, §4.5, §4.6, §16.3, §16.7), 05 (§4.3, §7.3, §4.4), 08, 09.
- The editor changes its steps (document 05 §4.3): the trigger leaves step 5.

**Revisit when:** a GenICam camera with a hardware trigger input is used (phase F: debounce then belongs to the camera, and the question of layer 1 returns for it), or a second installation of the same job shows that debounce depends on the wiring.

---

## 3. PC specification (for the client to buy)

Two tiers, both **without a dedicated GPU** (TD-28, NFR-PERF-5). The project chooses the tier; the built-in benchmark confirms it on the delivered unit.

| Item | Tier M (minimum) | Tier R (recommended) | Why |
|---|---|---|---|
| CPU | Intel N100 / N97 / N150 class (4 cores, AVX2) | Intel Core i5 12th gen or newer, or Core Ultra 5 | Intel for OpenVINO (TD-09); tier M for classical jobs and one small model, tier R for several models and teaching at full size |
| GPU | Integrated only | Integrated only | No dedicated GPU (NFR-PERF-3); the iGPU is an optional accelerator chosen by the benchmark |
| RAM | 16 GB | 16–32 GB | Models + image buffers + browser |
| Storage | 256 GB SSD | 512 GB – 1 TB NVMe SSD | Result images with the retention of FR-LOG-3 (NFR-ENV-2) |
| Network | 2 × Gigabit Ethernet | 2 × Gigabit Ethernet | One port **only for the camera**, one for the machine/plant network (NFR-SEC-2, NFR-SEC-4) |
| USB | 2 × USB 3 | 2 × USB 3 | C920 during the prototype, backup drive |
| OS | Windows 11 IoT Enterprise LTSC or Pro, 64-bit | Windows 11 IoT Enterprise LTSC or Pro, 64-bit | TD-01 |
| Form factor | Fanless industrial mini-PC | Desktop, or fanless industrial PC if the area is dusty | Reliability |
| Monitor | 21" | 24" | Readable from 2 m (NFR-USA-2) |
| Power | **UPS** (small, line-interactive) | **UPS** | Avoids corrupting data on power loss; gives a clean shutdown |
| Camera power | **PoE+ (IEEE 802.3at) injector** or switch on the camera port | same | DS-2CD3666G2T-IZS is PoE Class 4 (max 15 W); an 802.3af injector is not enough |
| Remote I/O (if the project uses 24 V signals) | Modbus TCP digital I/O module on the machine network | same | FR-INT-6; no USB I/O |

The tier is confirmed by running the benchmark (FR-ADM-5, test B-1 in section 7) on the candidate machine, or on one with the same CPU, before purchase.

---

## 4. Network

- **Separate camera network:** the camera is on its own network port of the PC, with static IPs (e.g. PC `192.168.10.1`, camera `192.168.10.2`). It is not reachable from the plant network (NFR-SEC-2).
- **Camera accounts:** change the camera's default password. Create a dedicated user for the core with only the rights it needs.
- **Time sync:** the camera syncs time from the PC (NTP), so timestamps match.
- **Plant-network services:** backups to a network share (FR-JOB-10) and remote support (NFR-SEC-3) go through the plant-network port, following the client's IT rules.

---

## 5. If the client offers Linux

| Area | Windows (chosen) | Linux (alternative) |
|---|---|---|
| C920 frames | OpenCV `CAP_DSHOW` + MJPG | OpenCV `CAP_V4L2` + MJPG |
| C920 controls | duvc-ctl | `v4l2-ctl` / direct V4L2 ioctls; `udev` rule to reapply on plug |
| Service | WinSW | systemd unit with `Restart=always` |
| Kiosk | Edge `--kiosk` | Chromium/Firefox kiosk on a minimal desktop |
| Secrets | Windows Credential Manager | Secret Service / file readable only by the service user |
| Installer | Inno Setup | `.deb` package or install script |
| Hikvision driver, core, jobs, models, UI | **unchanged** | **unchanged** |

Job files are the same on both, so a backup made on Windows restores on Linux and the other way round (NFR-POR-3).

---

## 6. Known problems and how each is handled

| # | Problem | Where it bites | Handled by |
|---|---|---|---|
| 1 | C920 ignores manual values while auto is on | Prototype | Two-pass apply + read-back (TD-04) |
| 2 | C920 settings revert after restart/replug | Prototype | Reapply on every open/reconnect (TD-04, §7.4) |
| 3 | C920 low fps in YUYV | Prototype | Force MJPG before resolution (TD-04) |
| 4 | C920 low-light compensation drops fps | Prototype | Off in every profile (TD-04) |
| 5 | OpenCV backend differences on Windows | Prototype | DirectShow only, never mixed (TD-04) |
| 6 | Stale buffered frames | Both | Latest-frame thread + "frame after t0" (§7.1) |
| 7 | Hikvision RTSP decode errors over UDP | Production | `rtsp_transport;tcp` (TD-05) |
| 8 | RTSP latency grows under load | Production | Latest-frame thread; or snapshot on trigger (TD-05) |
| 9 | ISAPI disabled by default on new firmware | Production | Commissioning checklist (TD-05) |
| 10 | Feature set varies by Hikvision model | Production | Read `/ISAPI/System/capabilities` first (TD-05, TD-06) |
| 11 | AGPL licence of Ultralytics | Model | Excluded; Apache 2.0 models (TD-08) |
| 12 | RF-DETR XL/2XL not Apache 2.0 | Model | Only Nano–Large used (TD-08) |
| 13 | Windows Update reboots | Production | LTSC or update policy + auto-recovery (TD-01, UC-10) |
| 14 | USB camera from a Windows service | Prototype | Test first; logon-task fallback (TD-14) |
| 15 | Daylight from windows | Both | Fixed station lighting + manual exposure/WB in the job (TD-06) |
| 16 | Camera switches to B/W + IR in low light | Production | Day/night forced to Day, IR off, in every job (TD-06) |
| 17 | Wrong PoE class (802.3af) | Production | 802.3at injector/switch specified (section 3) |
| 18 | Barrel distortion at the wide end of the zoom | Production | Use the middle/tele half of the zoom; choose height accordingly (TD-06) |
| 19 | C920 sends overexposed frames after each apply | Prototype | Frames dropped for `camera.settle_ms` after every apply (TD-04) |
| 20 | Unplugged C920 sends black frames with no error | Prototype | Uniform frames for `camera.dead_after_s` = lost; UVC device-list check (TD-04) |
| 21 | A turned part is not found, or regions land beside the feature | Both | Pose-based fixtures with allowed ranges (TD-21) |
| 22 | S7 PUT/GET is unauthenticated and needs non-optimized DBs | Machine | Segmented machine network; Modbus server alternative (TD-23, NFR-SEC-6) |
| 23 | asyncua may fail to import the MachineVision NodeSet (`ResultType`) | OPC UA | Test first; build the types in code if needed (TD-24) |
| 24 | A model that is fast on tier R is too slow on tier M | Model | Latency per tier in the model card; benchmark; INT8 (TD-28, FR-MDL-6) |

---

## 7. Prototype tests that settle open decisions

Run these first, on the bench, in this order. Each one closes a decision above.

| # | Test | Settles |
|---|---|---|
| 1 | Open the C920 with DirectShow + MJPG at 1920×1080. Set manual exposure, WB and focus with duvc-ctl. Read back. Restart the PC. Repeat 20 times. | TD-04 |
| 2 | Same as test 1, with the core running as a Windows service | TD-14 |
| 3 | Run classical checks on the first images collected at the station, across a full day of light | TD-07, NFR-ENV-1 |
| 4 | Benchmark RF-DETR Nano/Small vs YOLOX-S/Tiny, ONNX Runtime CPU vs OpenVINO, on a PC with the target CPU | TD-08, TD-09, section 3 |
| 5 | On the DS-2CD3666G2T-IZS: read capabilities; set and read back image settings, day/night mode, focus and zoom over ISAPI, then reboot and check they persist and restore; compare RTSP-TCP and snapshot quality and delay at 3200 × 1800 and 1920 × 1080; read alarm input events and switch an output, measuring the delay; run 8 hours without stopping | TD-05, TD-06, §13 open point 2 |
| 6 | Export a backup on one PC, install fresh on another, restore, run verification | NFR-REL-4/5 |
| B-1 | Benchmark on one tier-M and one tier-R unit: fixed workload, a classical job, a job with one model (FP32 and INT8, CPU and iGPU), `compare` and `anomaly` teaching | TD-28, NFR-PERF-5 |
| B-2 | Handshake against a real S7-1200 (S7 adapter) and a Modbus client (PLC or simulator): UC-11 and UC-12 for 8 h, then the fail-safe tests (kill the core, pull the cable, stop the heartbeat) | TD-23, NFR-REL-7/8 |
| B-3 | Load the official MachineVision NodeSet in asyncua; run a 40100 client against the server | TD-24 |

---

## 8. Sources

- TD-21..TD-28: project research documents 05 and 06 · [Cognex industrial communication signals](https://docs.cognex.com/is3d_132/web/EN/Help_IS3D/Content/Topics/IndustrialCommunications/comms-signals-vidi.htm) · [Keyence IV3 specifications](https://www.keyence.com/products/vision/vision-sensor/iv3/specs/) · [python-snap7](https://pypi.org/project/python-snap7/) · [pymodbus](https://pypi.org/project/pymodbus/) · [asyncua](https://pypi.org/project/asyncua/) · [asyncua #651](https://github.com/FreeOpcUa/opcua-asyncio/issues/651) · [S7-1200/1500 settings for PC clients (EMQX)](https://docs.emqx.com/en/neuronex/latest/configuration/south-devices/siemens-s7/plc/siemens-s7-1200-1500.html) · [Fullseye](https://github.com/furuse-kazufumi/fullseye) · [RapidOCR](https://pypi.org/project/rapidocr/) · [Anomalib](https://pypi.org/project/anomalib/) · [DINOv2 licence](https://github.com/facebookresearch/dinov2)
- C920 firmware and focus/exposure behavior: [crowsnest issue #96](https://www.github.com/mainsail-crew/crowsnest/issues/96) · [OctoPrint community thread](https://community.octoprint.org/t/anyway-to-disable-the-autofocus-for-cameras/801/21) · [udev rule gist](https://gist.github.com/fornellas/b9a00066faf67a34beea529ff2156e46)
- C920 frame rate (YUYV, MJPG, low-light compensation): [OpenCV forum](https://forum.opencv.org/t/opencv-camera-low-fps/567) · [BeagleBoard forum](https://forum.beagleboard.org/t/problems-with-webcams/13172?page=5)
- OpenCV backends on Windows: [MSMF slow init](https://forum.opencv.org/t/the-msmf-backend-is-slow-to-acquire-the-initial-frame/24121) · [auto-exposure semantics](https://forum.opencv.org/t/set-camera-paramter-without-reset-of-it/15021) · [Arducam UVC + OpenCV](https://docs.arducam.com/UVC-Camera/Appilcation-Note/Access%20UVC%20Cameras%20using%20OpenCV%2C%20Python%2C%20and%20GStreamer/)
- UVC control on Windows: [duvc-ctl](https://pypi.org/p/duvc-ctl) · [pygrabber](https://pypi.org/project/pygrabber)
- Linux camera controls: [cameractrls](https://github.com/soyersoyer/cameractrls)
- Hikvision ISAPI: [Hikvision ISAPI best practices](https://github.com/uchkunr/hikvision-best-practices) · [ipcamtalk ISAPI thread](https://ipcamtalk.com/goto/post?id=442454) · [saving/restoring image XML](https://www.ipcamtalk.com/goto/post?id=341542) · [ISAPI disabled by default](https://www.ipcamtalk.com/goto/post?id=262148) · [snapshot quality](https://ipcamtalk.com/threads/aquire-best-quality-current-snapshot-via-script.6326/post-64532)
- RTSP with OpenCV: [decode errors with Hikvision](https://answers.opencv.org/question/59697) · [capture options](https://forum.opencv.org/t/cv-capturing-rtsp-error/24030) · [latency and threading](https://github.com/qengineering/multithread-camera-opencv)
- Model licences: [Ultralytics licence](https://www.ultralytics.com/request-license) · [RF-DETR on PyPI](https://pypi.org/project/rfdetr/) · [RF-DETR XL/2XL licence](https://discuss.roboflow.com/t/plan-required-for-new-rfdetrlarge-sizes/11827) · [YOLOX ONNX](https://huggingface.co/Heliosoph/yolox-onnx) · [Anomalib + OpenVINO (Intel)](https://www.intel.com/content/www/us/en/developer/articles/training/defect-detection-with-anomalib.html) · [Supervision](https://supervision.roboflow.com/latest/faq/)
- Job/recipe vocabulary: [OPC UA Machine Vision](https://reference.opcfoundation.org/MachineVision/docs/13.2.2/)
- Selected camera: [DS-2CD3666G2T-IZS(Y) datasheet (Hikvision, 2024)](https://pro-av.hikvision.com/content/dam/hikvision/en/support/regional-materials/mea/DS-2CD3666G2T-IZSYH_Datasheet_MEA_2024Q1.pdf)
- General platform (TD-19): [Cognex In-Sight vision tools](https://docs.cognex.com/is_611/web/EN/ise/Content/Reference/VisionTools.htm) · [zxing-cpp on PyPI](https://pypi.org/project/zxing-cpp) · [OpenCV barcode module](https://docs.opencv.org/4.x/d7/d2a/group__objdetect__barcode.html) · [C920 + OpenCV test rig, Univ. of Ljubljana](https://repozitorij.uni-lj.si/IzpisGradiva.php?id=103811) · [Kurokesu C920 rework kit](https://www.kurokesu.com/shop/KITC920) · [OpenCV forum on camera choice](https://forum.opencv.org/t/which-cameras-are-compatible-with-opencv/7017)
