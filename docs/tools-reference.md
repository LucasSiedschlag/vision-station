# Tools reference

Document 10 (D13, V10 of `docs/architecture.md` §15.3). One section per tool type: what it measures, when to use it, its limits, examples of `reason_fail` and the fields they can use. A test (`tests/validation/test_v7_v10_contract.py`) fails for a tool with no `## `name`` section, and another (`tests/validation/test_v5_v6_results.py`) keeps the fields below equal to the ones the tool gives.

How to read a section:

- **Region.** Every tool looks at the region the user draws, cut upright from the frame or from a fixture (architecture §14). Sizes in pixels are pixels of the frame; sizes in millimetres need a calibration of the job (FR-INS-15, architecture §14.4).
- **Fields.** The names a `reason_fail` text can use, written `{name}`; fractions are 0 to 1 (format them with `:.0%`).
- **Reason codes.** `<tool>.<criterion>`, the same list as architecture §10.3; a failing tool names the criteria that failed.
- **Groups.** Tools can be put in a *group* in which one passing tool is enough (OR; TD-33, job-format §3). The criteria, reason codes and fields below are the tool's own and do not change in a group; a failed group says its own text instead of its members', and a member that cannot run is still an ERROR. The limits proposed from the samples (*Ajustar pelas amostras*) for a member count as good only the *Boa* pictures that member passed itself: a picture another member carried says nothing about it.
- **Marks.** What the tool draws over the picture (the *Medições* layer, VIA-0124), or why it draws nothing.

Index: [`brightness`](#brightness), [`blob`](#blob), [`edge`](#edge), [`pattern`](#pattern), [`compare`](#compare), [`color`](#color), [`code`](#code), [`detect`](#detect). The locators (`fixed`, `template`, `blob`, `edges`, `shape`) are described in `docs/architecture.md` §14.

## `brightness`

**Measures.** The gray level of the region, 0 (black) to 255 (white): the mean, the standard deviation, the minimum and the maximum, and the share of pixels above and below a level.

**Use it to** confirm that a lamp is on or off, that a label or window is lit as it should be, that a surface is even (low standard deviation) or has no glare (a small share above a high level) or no black hole (a small share below a low one). For a *colour* use `color`; for *where* something is, `blob` or `pattern`.

**Criteria** (give at least one; all that are given must hold):

| Parameter | Reason code | Fails when |
|---|---|---|
| `min_mean` | `brightness.min_mean` | the mean is below it |
| `max_mean` | `brightness.max_mean` | the mean is above it |
| `max_std` | `brightness.max_std` | the standard deviation is above it (a stain or a gradient) |
| `max_above` with `level` | `brightness.max_above` | more than this fraction of the pixels is brighter than `level` (the prohibit form: no glare) |
| `max_below` with `level` | `brightness.max_below` | more than this fraction is darker than `level` (no black hole) |

**Fields.** `{mean}`, `{std}`, `{min}`, `{max}` (gray levels), `{above}`, `{below}` (fractions beyond `level`), the limits `{min_mean}`, `{max_mean}`, `{max_std}`, `{max_above}`, `{max_below}` and `{level}`.

**Limits.** It sees the gray level, so two colours with the same gray are the same to it. A change of the lighting changes the result: the job's exposure is fixed for this (FR-ACQ). An empty region is an error (E302), never a pass.

**Marks.** None: it measures the whole region, whose outline is its drawing.

**Examples of `reason_fail`.**

- `Região escura demais: brilho {mean:.0f} (mínimo {min_mean:.0f})`
- `Reflexo: {above:.0%} da região passa do nível {level} (máximo {max_above:.0%})`
- `Superfície irregular: variação {std:.0f} (máximo {max_std:.0f})`

**Benchmark.** 30 ms (tier M) and 12 ms (tier R) at 1 MP, proposed until B-1.

## `blob`

**Measures.** The connected parts (blobs) of the region that stand out: the ones of a colour, or darker or lighter than the rest (`mode`, the same as in the `blob` locator, so a colour means the same in both). Only the blobs whose area is inside the filter count (`filter_min`, default 20 px², drops specks; `filter_max`; `filter_min_mm2` and `filter_max_mm2` in a calibrated job). It reports the **count**, the **total area** and the **largest area**, in pixels and, in a calibrated job, in square millimetres.

**Use it to** count what must be there (screws, holes, drops of glue), to know how much of the region something covers, or to find a part that is too large (a stain, a burr). For *how much of a colour* in total, `color` is simpler; for the *position* of one object, the `blob` locator.

**Criteria** (give at least one):

| Parameter | Reason code | Fails when |
|---|---|---|
| `min_count` | `blob.min_count` | fewer blobs count than this |
| `max_count` | `blob.max_count` | more count than this |
| `min_area`, `max_area` (px²) | `blob.min_area`, `blob.max_area` | the total area of the blobs that count is outside |
| `max_largest` (px²) | `blob.max_largest` | the largest blob is larger than this (the prohibit form) |
| `min_area_mm2`, `max_area_mm2`, `max_largest_mm2` | `blob.min_area_mm2`, `blob.max_area_mm2`, `blob.max_largest_mm2` | the same, in mm² |

**Fields.** `{count}`, `{area}`, `{largest}` (px²), `{area_mm2}` and `{largest_mm2}` (calibrated job only), the limits `{min_count}`, `{max_count}`, `{min_area}`, `{max_area}`, `{max_largest}`, `{min_area_mm2}`, `{max_area_mm2}`, `{max_largest_mm2}` and the filter `{filter_min}`, `{filter_max}`, `{filter_min_mm2}`, `{filter_max_mm2}`.

**Limits.** Touching blobs are one blob (8-connected). With the automatic threshold (`threshold` empty) a region whose gray levels span less than 30 has nothing that stands out, so it has no blob; give `threshold` to measure a flat region. The area is that of the mask: `clean_px` (default 0) closes small holes and removes specks but, being a cross-shaped ellipse, it takes the corners of a square. A size in millimetres needs a calibration of the job (FR-INS-15); a job that uses it without one is refused. An empty region is an error (E302).

**Marks.** The outline of each blob that counts, the largest first (at most 64): `found`, or `defect` when a limit from above (`max_*`) failed.

**Examples of `reason_fail`.**

- `Faltam parafusos: {count} de {min_count}`
- `Rebarba: mancha de {largest_mm2:.1f} mm² (máximo {max_largest_mm2:.1f})`
- `Cola demais: {area:.0f} px² (máximo {max_area:.0f})`

**Benchmark.** 60 ms (tier M) and 25 ms (tier R) at 1 MP, proposed until B-1.

## `edge`

**Measures.** Where the gray level steps along a line, to a fraction of a pixel. The region is a strip; the tool averages it across the direction of the scan (`direction`: `x` scans left to right and finds vertical edges, `y` scans top to bottom) into a profile, smooths it (`sigma`, default 1 px) and takes the peaks of its gradient with a Gaussian fit (calipers, `algorithms/calipers.py`). `min_contrast` is the height of the step in gray levels (default 20); `polarity` is `rising` (dark to light in the direction of the scan), `falling`, or `any`. Distances are from the start of the strip, in pixels and, in a calibrated job, in millimetres.

**Modes.**

- `presence`: how many edges there are.
- `position`: the distance from the start of the strip to the first edge.
- `width`: from the first edge to the next one of the opposite polarity: a bar, a gap, the diameter of a part seen from the side.
- `pitch`: between consecutive edges of the polarity of the first one (the teeth of a comb, a thread). The minimum limit is checked on the **smallest gap** and the maximum on the **largest**, so a tooth missing fails even though the mean is inside.
- `diameter`: the diameter of a round feature (a hole, a pin, a cap). `rays` lines (default 36) leave the centre of the region, the strongest edge of the `polarity` on each one between `ring_min` and `ring_max` of the reach of the region (the distance from the centre to the nearest side; default 0.1 to 1) is taken, and a circle is fitted through them; a false edge far from the circle is dropped. `rising` here is dark to light going **outwards** (a dark hole in a light plate is rising, a light disc on a dark background falling). The feature does not have to be at the centre, only around it. It is **not found** when fewer than 70 % of the rays find an edge on the circle or when the edges are not round (their RMS distance to the circle, `{roundness}`, over a tenth of its radius). `direction` does not matter.

**Use it to** gauge a width or a gap, the diameter of a hole or a pin, check that a part is where it should be along a line, or count the teeth of a row.

**Criteria.**

| Parameter | Reason code | Fails when |
|---|---|---|
| (the mode needs edges) | `edge.found` | there is no first edge, no pair, or fewer than two for a pitch: a distance is never made up, so a part with no feature **fails** and is not passed by a limit that only says "at most" |
| `min_count`, `max_count` | `edge.min_count`, `edge.max_count` | fewer or more edges than this (any mode) |
| `min_distance`, `max_distance` (px) | `edge.min_distance`, `edge.max_distance` | the measure of the mode is outside |
| `min_distance_mm`, `max_distance_mm` | `edge.min_distance_mm`, `edge.max_distance_mm` | the same, in mm (calibrated job) |

**Fields.** `{count}`, `{distance}` and `{distance_mm}` (empty when it could not be measured), `{distance_min}`, `{distance_max}`, `{distance_min_mm}`, `{distance_max_mm}` (the smallest and the largest gap of a pitch), `{roundness}` (diameter: how far the edges are from a perfect circle, px RMS), `{contrast}` (the smallest contrast of the edges used), the limits `{min_count}`, `{max_count}`, `{min_distance}`, `{max_distance}`, `{min_distance_mm}`, `{max_distance_mm}`.

**Limits.** Positions are exact for a sharp step to about 0.05 px and for a blurred one (sigma up to 2) to 0.2 px; the contrast is the height of the step to 6 % for `sigma` of 1 or more (it is only approximate below one pixel). Edges within 3 sigma of either end of the strip are not seen. The strip is cut upright from the fixture, so it follows a turned part; with non-square pixels and a turned fixture the millimetres use the scale of the axis of the strip (the mean of both for a diameter) and are only approximate. An empty region is an error (E302).

**Marks.** A line across the strip at each edge used (`found`, or `defect` when a limit from above failed) and, for a width or pitch, the distance written between the first two; for a diameter the fitted circle, its centre and the diameter written.

**Examples of `reason_fail`.**

- `Largura {distance:.1f} px (entre {min_distance:.0f} e {max_distance:.0f})`
- `Falta um dente: maior intervalo {distance_max:.1f} px`
- `Furo fora da medida: {distance_mm:.2f} mm`
- `Pino torto: diâmetro {distance:.1f} px, desvio {roundness:.1f} px`

**Benchmark.** 30 ms (tier M) and 12 ms (tier R) at 1 MP, proposed until B-1.

## `pattern`

Two versions are saved in jobs: **v1**, which correlates gray levels (a pattern in the same pose and size as taught), and **v2**, which matches by the direction of the edges and finds the pattern turned and scaled. A job refers to a version and keeps running it; new jobs use v2. The criteria, the reason codes and the fields are the same.

**Measures.** How many times a taught pattern (a logo, a mark, a screw head, a feature) is in the region, and, along an axis, how much of the length it covers. The template is a PNG of the job, cut from the reference image. v1 scores by normalised correlation (`min_score`, default 0.7; the region is reduced to `max_side` for speed) and finds the pattern as taught only. v2 scores by the agreement of the directions of the edges (`algorithms/shapematch.py`): it finds the pattern turned (`angles`, default ±20°) and larger or smaller (`scales`, default 0.9 to 1.1), whatever the brightness; a part of it hidden lowers the score by the share hidden; `polarity` `ignore` accepts light and dark swapped; `max_instances` (default 50) is how many it looks for.

**Use it to** confirm a mark or a logo is printed, count the features of a part, or check that a pattern repeats along a seam. Use v2 when the part may arrive turned or at a different distance. For one object that anchors the regions, use the `shape` or `template` locator.

**Criteria.**

| Parameter | Reason code | Fails when |
|---|---|---|
| `min_count` (default 1) | `pattern.min_count` | fewer occurrences than this |
| `max_count` | `pattern.max_count` | more than this (with 0: the pattern must not be there) |
| `axis` with `min_coverage` | `pattern.min_coverage` | the matches cover less of the length of the strip than this (v2: the stretch their turned box spans) |
| `axis` with `max_gap` | `pattern.max_gap` | the longest stretch with no match, ends included, is longer than this |

**Fields.** `{count}`, `{best}` (best score), `{coverage}`, `{missing}` (1 - coverage), `{gap}`, the limits `{min_count}`, `{max_count}`, `{min_coverage}`, `{max_gap}`; fractions format with `:.0%`.

**Limits.** The whole pattern must be inside the region; a template larger than the region is a refusal (E302), as is a flat template. Two matches closer than half the pattern count once. A pattern with few edges (a plain blob) cannot be matched by v2 (the template is refused as flat); v1 can. v2 follows the pattern to about 0.3 px and 0.3°; its time grows with the range of angles and scales (a full turn is a few times a ±20° search).

**Marks.** The box of each occurrence, the best first (at most 64): `found`, or `defect` when there are more than `max_count`; v1 draws an upright box, v2 the box turned and scaled as the pattern was found.

**Examples of `reason_fail`.**

- `Logotipo ausente ou ilegível (melhor semelhança {best:.0%})`
- `Faltam marcas na emenda: {count} de {min_count}`
- `Trecho sem marca de {gap:.0%} da emenda (máximo {max_gap:.0%})`

**In a group (OR).** When a tape may show a logo or a text block, and how many of each varies, give one `pattern` per mark with `min_count` 1 and no `max_count`, put both in a group and write the text of the group (`Fita sem logo nem texto`). The tape passes with either mark, any number of times, and fails only with neither. A tape with no marks, a box with no tape and a background with no box are not a PASS (`tests/test_or_bench.py`).

**Benchmark.** v1 and v2: 120 ms (tier M) and 50 ms (tier R) at 1 MP, proposed until B-1.

## `compare`

**Measures.** Where the part differs from what good parts look like. The tool is taught with pictures of good parts (**15 or more are advised**, 3 are the least): the mean and the standard deviation of every pixel of the region, kept in a file of the job (`models/<name>.var`). Each part is then moved to the model (registration by phase correlation, up to `max_shift_px`, default 6), its light divided by one gain per channel, and a pixel is a **defect** when it differs from the mean by more than `max(abs_threshold, k * sigma + edge_px * the change to its neighbours)` (defaults 15 gray levels, 3 deviations, 1 px). The defects are the connected parts of those pixels, cleaned (`clean_px`, default 0) and with the ones smaller than `filter_min` (default 10 px²) dropped. It reports the **count**, the **total area** and the **largest area**, in pixels of the region and, in a calibrated job, in square millimetres.

**Use it to** find what you cannot name beforehand: a scratch, a stain, a missing or extra piece, a print that is off, on a part that is always the same. For a defect you can describe, `blob`, `color` or `brightness` is simpler and needs no teaching.

**Teaching.** `scripts/teach_compare.py JOB.vjob TOOL_ID FOLDER --out m.var` takes frames of good parts, locates the fixtures of the job and cuts the region of the tool upright as an inspection does, lists every picture it could not use with the reason, and writes the model, the file `models/<name>.var` that the `model` parameter of the tool names. **There is no screen to add that file to a job yet**: the upload of the editor takes the model of a `detect` tool only. Teaching from the station, which writes the model into the job, is VIA-0126. With fewer than about 15 pictures the floors (`abs_threshold` and the allowance at edges) hold the tolerance, not what the good parts showed. The file holds the mean and deviation as 16-bit floats and the SHA-256 of them; a damaged file is refused, it never gives a wrong answer.

**Criteria** (give at least one):

| Parameter | Reason code | Fails when |
|---|---|---|
| `max_count` | `compare.max_count` | more defects than this |
| `max_area` (px²) | `compare.max_area` | the total area of the defects that count is above this (0: not one pixel) |
| `max_largest` (px²) | `compare.max_largest` | the largest defect is above this |
| `max_area_mm2`, `max_largest_mm2` | `compare.max_area_mm2`, `compare.max_largest_mm2` | the same, in mm² (calibrated job) |

**Fields.** `{count}`, `{area}`, `{largest}` (pixels of the region), `{area_mm2}` and `{largest_mm2}` (calibrated job only), `{gain}` (the gain of the light, 1 is as taught), the limits `{max_count}`, `{max_area}`, `{max_largest}`, `{max_area_mm2}`, `{max_largest_mm2}` and the filter `{filter_min}`.

**Limits.**

- Registration corrects a **shift**, not a rotation or a change of size: the fixture does that, so the part needs a locator (`shape`, `edges`, `blob` v2) when it can arrive turned. A region cut from a fixture of another scale is resized to the taught size, up to a quarter; beyond that the tool is refused (the pipeline already makes a pose out of the range of the fixture an error).
- The light is corrected by a **gain** between 0.8 and 1.25, with no offset. A part 15 % darker is the same part; one 40 % darker is not, and what the gain cannot take is shown as defects. Weaker light needs a new teaching.
- A pixel on an edge of the part is allowed to be a pixel off; a defect that only changes pixels on an edge, by less than that, is not seen.
- The comparison is made on 8 bits and on the picture reduced to 256 pixels for registration and the gain; a model of a megapixel in colour is about 6 MB in the job (the gray one a third).
- An empty region, a region of another size than the model, a model that is missing or damaged, is an error (E302), never a pass.

**Marks.** The outline of each defect that counts, the largest first (at most 64): `defect` when a limit failed, `found` when the defects are within the limits.

**Examples of `reason_fail`.**

- `Mancha na peça: {count} defeito(s), {area:.0f} px²`
- `Defeito de {largest_mm2:.1f} mm² (máximo {max_largest_mm2:.1f})`
- `Luz fora do ensinado (ganho {gain:.2f})`

**Benchmark.** 60 ms (tier M) and 25 ms (tier R) at 1 MP, proposed until B-1; measured next to `color` it costs 1.3 to 1.8 times as much (about 13 ms at 1 MP in colour on a PC of tier R).

## `color`

**Measures.** How much of the region has a colour, and, along an axis, how much of its length. The colour is a range in HSV (`hue`, with `lo > hi` wrapping through red, and limits of saturation `s_min`, `s_max` and value `v_min`, `v_max`; a hue range needs a saturation floor, since grays and whites have hue 0, which is red) or a reference colour and a distance (`mode: reference`, ΔE in CIELAB). It reports `fraction`, the share of the pixels in the colour, and with `axis` (`x` or `y`, the region being a strip) a column or row counts as covered when at least `line_min` (default 30 %) of it has the colour, giving `coverage` of the length and `gap`, the longest stretch uncovered, ends included.

**Use it to** confirm a coloured part is there (a cap, a tape), that a colour is *not* there (no red where there should be none), or that a band runs the whole length of a seam. For a count or the size of coloured parts, `blob` with a colour range; for a gray level, `brightness`.

**Criteria** (give at least one):

| Parameter | Reason code | Fails when |
|---|---|---|
| `min_fraction` | `color.min_fraction` | the share of the region in the colour is below it |
| `max_fraction` | `color.max_fraction` | it is above it (the prohibit form) |
| `axis` with `min_coverage` | `color.min_coverage` | the covered share of the length is below it |
| `axis` with `max_gap` | `color.max_gap` | the longest uncovered stretch is longer than it |

**Fields.** `{fraction}`, `{coverage}`, `{missing}` (1 - coverage), `{gap}`, the limits `{min_fraction}`, `{max_fraction}`, `{min_coverage}`, `{max_gap}`; fractions format with `:.0%`.

**Limits.** The colour depends on the light: the job's exposure and white balance are fixed for this, and the supervisor's fine-tune moves the limits, never the range. Two colours with the same hue and different value need the value limits. An empty region gives a fraction of 0.

**Marks.** The outline of each part of the region in the colour, the largest first (at most 16), simplified to at most 64 points: `found`, or `defect` when `max_fraction` failed. A region that fails by not having the colour has no outline to draw.

**Examples of `reason_fail`.**

- `Tampa ausente ({fraction:.0%} azul, mínimo {min_fraction:.0%})`
- `Fita interrompida: trecho sem a cor de {gap:.0%} (máximo {max_gap:.0%})`
- `Cor indevida na região ({fraction:.0%})`

**Benchmark.** 60 ms (tier M) and 25 ms (tier R) at 1 MP, proposed until B-1; about 10 ms at 1 MP on a PC of tier R.

## `code`

**Measures.** The 1D bar codes and 2D codes (QR, Data Matrix, Code 128, EAN...) the region holds, read by zxing-cpp (Apache 2.0). It reports `found` (codes read), `matching` (the ones accepted: any, or those with the exact text `expect` or fully matching the regular expression `pattern`), their `texts`, and the position of each.

**Use it to** read a lot code and compare it with the expected one, or to confirm a label is on the part. Grading the print quality (ISO 15415/15416) is out of scope.

**Criteria.**

| Parameter | Reason code | Fails when |
|---|---|---|
| `min_count` (default 1) | `code.min_count` | fewer codes are accepted than this |
| `max_count` | `code.max_count` | more are accepted than this (a label stuck twice) |

**Fields.** `{found}`, `{matching}`, `{min_count}`, `{expected}` (the `expect` text or the `pattern`), `{texts}` (the texts read, joined by ", ").

**Limits.** `formats` (empty: every format) narrows what is tried and speeds it up; `try_rotate`, `try_downscale` and `try_invert` (light code on a dark background) widen it at a cost in time. A code partly outside the region is not read. An empty region reads nothing.

**Marks.** The outline of each code read and its text, `found` when accepted and `defect` when read but not accepted (a wrong lot). A region where nothing is read has nothing to draw.

**Examples of `reason_fail`.**

- `Código não lido`
- `Lote errado: lido "{texts}", esperado "{expected}"`
- `Etiqueta duplicada: {matching} códigos`

**Benchmark.** 250 ms (tier M) and 100 ms (tier R) at 1 MP, proposed until B-1.

## `detect`

**Measures.** What a model trained outside the station says about the region (ONNX Runtime on the CPU; the model and its card are files of the job, `models/<name>.onnx` and `models/<name>.card.yaml`, whose SHA-256 is checked; training stays out of the install, see `docs/models.md`). The card says the task:

- **classifier**: the top class and its confidence. Fails when the class is in `fail_classes`, or not in `pass_classes` (when given), or the confidence is below `min_confidence` (unsure is a failure).
- **detector**: boxes with a class and a confidence. Fails when any box has a class in `fail_classes`, when a class of `require_classes` has no box, or when the boxes of `count_class` are fewer than `min_count` or more than `max_count`.
- **anomaly**: a score. Fails when it is above `threshold` (the tool's, else the card's).

**Use it to** judge what cannot be said with a measure: a defect class, the right variant of a part, or a part that does not look normal. Without a trained model, `compare` finds differences from good parts with no training stack.

**Criteria and reason codes.** `detect.class`, `detect.min_confidence` (classifier); `detect.fail_class`, `detect.require_classes`, `detect.min_count`, `detect.max_count` (detector); `detect.max_score` (anomaly).

**Fields.** `{label}`, `{confidence}` (classifier), `{classes}` (the classes found, joined by ", "), `{count}` (of the counted class), `{score}`, `{threshold}` (anomaly).

**Limits.** A model that is not the one of its card (the hash differs), a card with problems, an output that is not a number or is empty, or a number of classes different from the card's, is an error (E302), never a pass. The time is the model's, stated in its card; there is no benchmark workload for it (VIA-0112). Only the exports the runtime reads are accepted (`docs/models.md`).

**Marks.** A detector: the box of each detection with its label and confidence, `defect` for a class in `fail_classes`. A classifier: the label and confidence at the corner of the region, `defect` when it fails. An anomaly above the limit: the whole region.

**Examples of `reason_fail`.**

- `Peça com risco ({confidence:.0%})`
- `Falta a tampa (classes vistas: {classes})`
- `Anomalia {score:.2f} acima de {threshold}`

**Benchmark.** Not timed: the latency is the model's (VIA-0112).
