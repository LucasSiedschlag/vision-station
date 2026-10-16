# Vision Station — Models (the `detect` tool)

| | |
|---|---|
| Document | 07 — Models |
| Date | 2026-10-15 |
| Decisions | TD-08 (model family and licence), TD-09 (runtime), TD-10 (training), architecture §9 |

A `detect` tool runs a trained model on its region. Training happens **offline**, on the maintainer's machine, from the images the station collected; only the exported ONNX file and its card go into the job. Nothing of the training stack (PyTorch, CVAT, Anomalib…) is installed at the station.

## 1. From images to a model

1. **Collect** (screen **Dataset**): turn on collection mode for the job for long enough to cover the variation (shifts, light, products). Mark wrong results on **Resultados**: they become labeled images.
2. **Export** the dataset (screen **Dataset** → Exportar): images, `labels.csv` and `manifest.json` with SHA-256, in `<data>/exports/<dataset_id>/`.
3. **Label and train** offline, with a permissive model only (TD-08):
   - detection: **RF-DETR Nano/Small/Medium/Large** (Apache 2.0; never XL/2XL) or **YOLOX** (Apache 2.0);
   - classification: any Apache/MIT/BSD backbone with licensed weights;
   - anomaly (good images only): **Anomalib** PatchCore or PaDiM.
   **Never Ultralytics YOLO** (AGPL-3.0), including models trained with it.
4. **Export to ONNX** (opset 17 or newer), input `[1, 3, H, W]`, float32.
5. **Write the card** (below) and compute the SHA-256 of the `.onnx`.
6. **Add both to the job** in the editor (step Ferramentas → the detect tool → drop the `.onnx` and the `.card.yaml`), set the classes that fail, **Testar**, add reference-set cases, save, and activate (the verification runs the reference set).

Replacing a model is a new job version (UC-08).

## 2. The model card (`models/<name>.card.yaml`)

```yaml
format: 1
task: detector                 # classifier | detector | anomaly
sha256: 4f6c…                  # of models/<name>.onnx; the tool refuses a file that does not match (FR-MDL-3)
classes: [risco, amassado]     # classifier and detector, in the model's output order
input:
  size: [384, 384]             # height, width
  channels: RGB                # RGB or BGR
  scale: 255                   # pixels are divided by this
  mean: [0.485, 0.456, 0.406]  # then (x - mean) / std per channel
  std: [0.229, 0.224, 0.225]
  keep_aspect: false           # true: letterbox instead of stretching
output:
  boxes: dets                  # detector: name of the boxes output [1, N, 4] (cx, cy, w, h as fractions)
  scores: labels               # detector: name of the class logits output [1, N, C]
  sigmoid: true                # detector: scores are logits
  softmax: false               # classifier: the output is logits
threshold: null                # anomaly: score above this is anomalous (the tool can override)
name: Riscos na tampa v3
trained_at: '2026-11-03'
dataset_id: ds-20261102-a1b2
licence_code: Apache-2.0 (RF-DETR)
licence_weights: Apache-2.0 (RF-DETR COCO weights)
metrics: {mAP50: 0.94, recall_fail: 0.99, test_images: 412}
```

The licences of the code and of the starting weights are written in the card (TD-08, TD-18).

## 3. What each task returns

| Task | Model output | The tool fails when |
|---|---|---|
| `classifier` | `[1, C]` probabilities (or logits with `softmax: true`) | the top class is in `fail_classes`, or not in `pass_classes` (if given), or its probability is below `min_confidence` |
| `detector` | DETR style: boxes `[1, N, 4]` + logits `[1, N, C]` (RF-DETR export) | a box of a `fail_classes` class above `min_confidence`; a `require_classes` class with no box; `count_class` outside `min_count`/`max_count` |
| `anomaly` | a score `[1]`/scalar or an anomaly map `[1, 1, H, W]` (its maximum) | the score is above `threshold` |

Fields for the failure text: `{label}`, `{confidence}`, `{classes}`, `{count}`, `{score}`, `{threshold}`.

Not yet supported: YOLOX raw outputs (grid decoding), segmentation, OpenVINO IR files (the OpenVINO execution provider of TD-09 comes with the production PC).

## 4. Runtime

ONNX Runtime (MIT) on the CPU. Sessions are kept in memory by the model's SHA-256 (up to four models). The first inspection after a job loads pays the model's load time; measure it on the target PC (NFR-PERF-1) and write it in the card's metrics.
