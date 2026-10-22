# Tools reference

Document 10 (D13, V10 of `docs/architecture.md` §15.3). One section per tool type: what it measures, when to use it, its limits, examples of `reason_fail` and the fields they can use. A test (`tests/validation/test_v7_v10_contract.py`) fails for a tool with no `## `name`` section, and another (`tests/validation/test_v5_v6_results.py`) keeps the fields below equal to the ones the tool gives.

How to read a section:

- **Region.** Every tool looks at the region the user draws, cut upright from the frame or from a fixture (architecture §14). Sizes in pixels are pixels of the frame; sizes in millimetres need a calibration of the job (FR-INS-15, architecture §14.4).
- **Fields.** The names a `reason_fail` text can use, written `{name}`; fractions are 0 to 1 (format them with `:.0%`).
- **Reason codes.** `<tool>.<criterion>`, the same list as architecture §10.3; a failing tool names the criteria that failed.
- **Marks.** What the tool draws over the picture (the *Medições* layer, VIA-0124), or why it draws nothing.

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
