# Vision Station — Job file format (`.vjob`) and backup file (`.vbak`)

| | |
|---|---|
| Document | 08 — Job file format (deliverable D8) |
| Format | 1 |
| Date | 2026-10-15 |
| Code | `src/vision_station/jobs/`, `src/vision_station/store/` |

A job holds everything that affects an inspection result (architecture §4). It is saved as an immutable version in the job store and exchanged as one `.vjob` file. A `.vbak` holds every job plus the system configuration. Both are ZIP archives with a `manifest.json`.

## 1. Container (both kinds)

- ZIP, deflate. Entries sorted, timestamps fixed (1980-01-01), so the same content gives the same bytes.
- Paths are relative, use `/`, UTF-8, no `..`, no absolute paths, no drive letters.
- `manifest.json` (UTF-8 JSON, sorted keys):

```json
{
  "format": 1,
  "kind": "job",
  "job_id": "3f1c9a2e-5b7d-4c1e-9a0f-2d6b8e4f7a10",
  "version": 7,
  "created_at": "2026-10-15T14:32:00-03:00",
  "app_version": "0.1.0",
  "files": {
    "job.yaml": {"sha256": "…", "size": 1234},
    "camera/profile.yaml": {"sha256": "…", "size": 210}
  }
}
```

- **Integrity:** every entry except the manifest must be listed with its SHA-256 and size, and nothing else may be in the archive. One byte different refuses the whole file; nothing is stored (FR-JOB-8).
- **Format version:** a file with a newer `format` is refused with a clear message. Older formats are upgraded on import by migrators (`store/archive.py`, `MIGRATORS`), never in place (NFR-MAI-1).
- **Limits:** 256 MB per file, 1 GB per archive.
- **No secrets:** YAML files are scanned by key; `password`, `secret`, `token`, `credential`, `apikey` are refused (NFR-SEC-1).

## 2. `.vjob` contents

```
job.yaml                        required: the job definition (section 3)
camera/profile.yaml             required: the camera profile (section 4); path given by job.yaml
camera/raw/*                    optional: driver-specific dumps, used only by the same driver
reference/reference.png         the view of a good object (verification, sharpness gate)
reference/reference.meta.yaml   brightness, sharpness and anchor measured on it
tests/expected.yaml             the reference set (section 5)
tests/images/*.png              its images
locator/template.png            the template locator's image, when used
patterns/*.png                  pattern tool templates
models/*.onnx, *.card.yaml      detect tool models and their cards (docs/models.md)
```

A file a tool or locator names in its parameters must be in the job: a job without it is refused on load.

## 3. `job.yaml`

```yaml
format: 1
job:
  id: 3f1c9a2e-5b7d-4c1e-9a0f-2d6b8e4f7a10   # UUID, the same for every version
  name: Tampa azul — etiqueta de lote
  version: 7                                 # 1, 2, 3…; saved versions never change
  parent_version: 6                          # the version it was edited from (none for 1)
  author: maintainer
  created_at: 2026-10-15T14:32:00-03:00
  description: ''
  notes: luz nova                            # what changed in this version
camera_profile: camera/profile.yaml
trigger:
  mode: image_presence                       # image_presence | manual | external | continuous
  presence_roi: [0.1, 0.1, 0.9, 0.9]          # fractions of the frame (image_presence)
  still_ms: 500                              # stillness before the picture (image_presence)
  rearm: object_absent
  diff_threshold: 25                         # gray levels that count as a change (1–255)
  min_area: 0.05                             # fraction of the area that must differ to count as present
  motion_area: 0.01                          # fraction that must change between frames to count as moving
  delay_ms: 0                                # external: wait 0–1000 ms after the trigger before the frame (FR-TRG-6)
  interval_ms: 500                           # continuous: minimum time between inspections; 0 = as fast as possible (FR-TRG-7)
quality:
  brightness: {min: 15, max: 245}             # outside: ERROR
  sharpness_min_ratio: 0.5                   # vs. the reference image; below: ERROR
  similarity_min: 0.6                        # live view vs. reference, at activation
  anchor_tolerance: 0.05                     # allowed anchor shift at activation
geometry:
  locator: {type: template, version: 1, params: {template: locator/template.png, min_score: 0.6}}
  rois:
    cap:   {relative_to: anchor, rect: [0.30, 0.00, 0.70, 0.20]}
    label: {relative_to: frame,  rect: [0.10, 0.45, 0.90, 0.80]}
tools:
  - id: tampa                                # unique in the job; the key of its score
    type: color                              # code | color | pattern | detect
    version: 1
    roi: cap                                 # a name of geometry.rois, or frame, or anchor
    params: {hue: [100, 130], s_min: 100, min_fraction: 0.4}
    reason_fail: Tampa ausente ({fraction:.0%} azul)
decision: all_pass
ui:
  waiting: Aguardando peça                   # the operator screen's waiting text
```

Rules (checked on load, `jobs/job.py`):

- Rectangles are `[x0, y0, x1, y1]`, fractions 0–1, `x0 < x1`, `y0 < y1`. A region relative to the anchor is a fraction of the anchor's rectangle.
- `frame` and `anchor` are built-in region names; `anchor` and anchor-relative regions need a locator.
- At least one tool; tool ids unique; every tool's region exists.
- Each tool and locator `type` + `version` must be one this software runs, and its `params` must validate. The parameters of each type, with titles and limits, are served as JSON Schema by `GET /api/tools`; their meaning is in the module of each type (`tools/*.py`, `locators/*.py`). A version that is no longer supported refuses the job instead of running different logic.
- `reason_fail` is Portuguese for the operator in format 1; from format 2 it holds both languages, `{pt-BR: …, en: …}` (TD-30, FR-JOB-15); `{field}` placeholders take the tool's values (listed in each tool's module). A wrong placeholder leaves the text as written.
- `affects_result` (optional, default `true`; FR-INS-13): `false` makes the tool **informative**: it runs, its values and verdict are recorded and shown, but it never decides the result. It does not make the result FAIL, its failure is not in the reason or the reason codes, and an informative tool that cannot run is noted on its own entry instead of turning the result into ERROR. A job needs at least one tool that decides. The field is written only when `false`, so a job that does not use it stays readable by programs older than 0.2.

## 4. `camera/profile.yaml`

```yaml
resolution: [1920, 1080]
pixel_format: mjpeg                 # UVC only: mjpeg | yuyv
exposure: {mode: manual, value_us: 33000}
gain: {mode: manual, value: 0}
white_balance: {mode: manual, kelvin: 4500}
focus: {mode: manual, value: 30}
zoom: {value: 4.0}                  # motorized lens only
power_line_hz: 60                   # 50 | 60
low_light_compensation: false
```

`mode: auto` takes no value; `mode: manual` needs one. The settings are written to the camera on every open, reconnect and activation, then read back; what did not apply is reported (FR-ACQ-4).

## 5. `tests/expected.yaml` (the reference set)

```yaml
tolerance: 0.05                      # allowed difference of each expected score
cases:
  - image: tests/images/ok1.png
    outcome: PASS                    # PASS | FAIL | ERROR
    scores: {tampa: 1.0}             # optional
  - image: tests/images/sem_tampa.png
    outcome: FAIL
    reason_contains: Tampa ausente   # optional
```

A job is activated only if every case gives the expected outcome (and scores within the tolerance, and the reason text), or if the Maintainer overrides with a written reason, which is audited (FR-JOB-9). JSON is valid YAML: the editor writes this file as JSON.

## 6. `.vbak`

```
manifest.json        kind: backup, created_at, app_version, include (all | latest), jobs: [{job_id, version, path, sha256}]
system.yaml          the system configuration, without secrets (architecture §4.5)
active.yaml          which job and version was active
jobs/<job-id>/v<n>.vjob
```

Restoring checks the whole file first, stores the versions it does not have (an identical version is skipped; a version whose number is already used here with different content is stored as the next version, never overwritten), and activates nothing: the restored active version is shown to be verified and activated. Results and recorded images are not in backups.
