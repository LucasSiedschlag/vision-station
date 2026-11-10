# Plan: free-form regions (a region that is not a rectangle)

Status: **proposal**, not started (issue #24). The design questions were settled in a grilling round (see "Decisions" at the end). No TD/FR number yet: assign them when it is accepted (keep IDs stable, CLAUDE.md). Terms are those of `GLOSSARY.md`: region, shape, part, bounding box, mask.

## 1. Why

A region is one rectangle today (`Roi.rect`, `src/vision_station/jobs/job.py`). Two tapes that cross in an "X" cannot be told apart by colour with
rectangles that take in the crossing: the small square where they cross holds both tapes' printing, and on real frames a window that includes it saw
up to ~9,800 px² of the *other* tape's red, more than a real tape gives under two lights. What works is a region that **leaves the crossing out**:
the horizontal tape as its left and right arms, the vertical tape as its top and bottom arms. Today that is four rectangles (a taped-box job
with four colour windows); wanted is **two regions, each of two parts**, forming a broken "X".

More generally: any part that is not a box (an L-shaped bracket, a curved label) is measured with the background around it.

Rings are not a reason for this feature. A ring is counted with `circles` (count and mean radius) and measured with `edge` (`mode: diameter`); neither needs a shape. Only the colour or area of the ring itself, without its centre, needs a hole, which is a later option (§8).

## 2. What it is (and is not)

- A region may have a **shape**: a set of simple polygons (**parts**). The region is their **union**. A rectangle is the one-part, four-vertex case.
- Out of scope for v1: holes (subtracting a shape), curves, a mask taught from an image, tools that cannot honour a mask (see §4).
- The job stays *data* (FR-PLT-12): vertices are numbers in the job, not code.

## 3. Data model and how a region is cut

- `Roi` keeps `relative_to` and `rect`. `rect` is a field name kept so existing jobs do not change; in docs and interface text it is the **bounding box**. It stays required: it is the crop the pipeline already makes, and the whole region when there is no `shape`.
- New optional `shape: {parts: [[[x, y], ...], ...]}`, vertices as **fractions of the same reference as `rect`** (the frame, or a fixture's box).
  Written only when used, like `informative`. **No format bump** (TD-33 added `groups` inside format 3 the same way): a program without this feature
  refuses the job as an unknown field, never judges it with the wrong region (`_Strict`, extra forbidden).
- Validation in `Roi`: 1..8 parts, 3..64 vertices each, every part simple (no self-intersection), area > 0, inside `rect`, and `rect` equal to the
  bounding box of the parts (so the two cannot disagree).
- Cutting (`geometry/pose.py: cut`, `geometry/regions.py: cut_region`): unchanged crop of `rect`, plus a **mask** (`uint8`, 255 inside) built in the
  *cut's own pixel grid*: a vertex maps linearly from the reference's fractions to the cut's pixels, so it needs no extra warp, also for a region of a
  turned fixture (the cut is already upright). **Pixel rule:** the mapped vertices are rounded to integers and the part is filled with `cv2.fillPoly`
  (no anti-aliasing), boundary pixels included, so the mask is deterministic and the same on both OSes. `Cut` gains `mask: np.ndarray | None`.

## 4. How tools use the mask

A tool that is handed a mask must count **only** masked pixels. A tool that cannot is **refused for a shaped region when the job is saved or
loaded** (and so never reaches activation), never run on the bounding box: the box would measure the background, a false PASS (design rule 5). This is a
rule of the job, not of the run: there is no ERROR at inspection time and no fallback to the box anywhere. The editor greys out *Free form* for those tools.

| Tool | v1 | How |
|---|---|---|
| `blob` | yes | the colour/threshold mask ANDed with the region mask before the parts are counted; filters and areas are inside the shape |
| `color` | yes | fractions over masked pixels |
| `brightness` | yes | statistics over masked pixels |
| `circles`, `pattern`, `compare`, `edge`, `code`, `detect` | no (refused) | need work each: edges/strips with invalid pixels, a template that straddles the border, a variation model with holes. Later, one at a time |

`run(region, params, files)` becomes `run(region, params, files, mask=None)` for the tools that accept it (a `ToolType.supports_mask` flag; the
refusal is a new error code, texts in pt-BR/en, listed in architecture §10.3 and the error table). The reason for the rule is recorded in an ADR,
written when the refusal slice starts (§7), so it can cite the error code.

## 5. Marks, overlay, API

- Marks are already given in the cut's pixels and mapped with `Cut.to_frame`: the crop keeps that map, so **marks need no change**.
- The result's `regions[]` entry (and the overlay, `pipeline/overlay.py`) gains the outline: `parts` as polygons in frame pixels next to `rect`.
- API: the job schema (`api/schemas.py`) and the generated `frontend/src/api/schema.d.ts` gain `shape`; `npm run gen:api`.
- Operator screen: `LiveCanvas` draws the outline (dashed/thick rules for fail/informative stay).

## 6. Editor

`features/editor/RegionCanvas.tsx` (draw/move/resize a rectangle today) gains a *Shape* choice per region: **Rectangle | Free form**.
Free form: click to add vertices, close on the first vertex or Enter, drag a vertex, delete a vertex, *Add part* for the next polygon,
Esc cancels. Keyboard operable (React Aria, TD-29), pt-BR and en texts (Lingui, TD-30). Editing keeps `rect` equal to the bounding box.
Also touched: `draft.ts`, `summary.ts`, `fixtures.ts`, `steps.tsx`, `EditorPage.tsx`.

Out of v1: rotating or scaling a whole shape, copy/paste of a shape, snapping to a grid. Each is its own ticket if a job needs it.

## 7. Milestones

1. **M1, backend and display (no drawing yet).** Slices, in this order, each shown on its own; the refusal comes before any tool accepts a mask, so a
   shaped job can never run on the box:
   1. `shape` on `Roi` with validation, unit tests for the polygon check, and V3 (degenerate and self-intersecting shapes are refused).
   2. The cut builds the mask, with V2 golden: a polygon equal to the rectangle gives the **same mask** and the same result as the rectangle.
   3. A tool without `supports_mask` is refused for a shaped region at save and load (new error code, pt-BR/en texts); write the ADR for the rule.
   4. `color` honours the mask.
   5. `blob` and `brightness` honour it; V4: a masked blob keeps its outcome under light, noise and shift.
   6. Result outline, overlay and API schema.
   7. Docs (job-format §3, architecture §7.1/§14, tools-reference "Region" and the three tools, error table) and the scripted two-region "X" job.

   *Result:* the "X" job can be built by script (as the other jobs here) and shown by the operator screen. Editing it is still done in JSON.
2. **M2, editor drawing.** §6, with frontend tests and a browser e2e (draw an "X" of two shapes, test, save, activate).
3. **M3, more tools.** `circles` (mask the edge map), `pattern` (reject a template outside the mask), `compare`, `edge`, as asked.

## 8. Risks and open questions

- **A mask is not a locator.** The shape is fixed in the frame (or a fixture); a box that moves needs a fixture (TD-19/21), same as a rectangle.
- **Holes.** Not in v1; the region is a union. Later, as its own milestone: an optional `exclude` field of parts, evaluated after the union, for the
  colour or area of a ring without its centre. It needs its own rules (the hole lies inside the union and does not split a part). Adding it is compatible.
- **Where the shape is valid.** An empty mask after the crop (a shape wholly outside the frame) is the existing *region outside the picture* error.
- **Colour tools still need the exposure and white balance fixed** (the job's camera profile); a shape does not change that.
- **Cost.** Building the mask is one `fillPoly` per run; cache it per (job version, region size) if a profile shows it matters.

## 9. Interim

Nothing here is in production, so free-form regions block no delivery. The four-rectangle tape job (the editor's v4 with one corrected test
picture is version 5) is a working fallback; the two-region "X" job built after M1 is the target. Whichever passes the bench on real frames is the one
activated; there is no deadline attached.

## 10. Decisions

Settled in the grilling round, before TD/FR numbers exist:

1. No format bump: `shape` is an optional field in format 3; a program without it refuses the job.
2. v1 is union only, no holes; rings are checked with `circles` and `edge`; `exclude` is a later option.
3. A tool that cannot honour a mask is refused for a shaped region at save and load, with a new error code; never run on the box, never an ERROR at run time.
4. Vocabulary in `GLOSSARY.md`: region, shape, part, bounding box (`rect` keeps its field name), mask.
5. Pixel rule: integer-rounded vertices in the cut's grid, `fillPoly` with boundary pixels; V2 golden asserts equal masks.
6. M2 is limited to Rectangle | Free form with the listed interactions.
7. Nothing is in production; the four-rectangle job is the fallback and the "X" job the target, chosen on real frames.
8. M1 is sliced as in §7, with the refusal before any tool accepts a mask.
9. One ADR for the refusal rule, written when its slice starts.
