# Plan: free-form regions (a region that is not a rectangle)

Status: **proposal**, not started (issue #24). No TD/FR number yet: assign them when it is accepted (keep IDs stable, CLAUDE.md).

## 1. Why

A region is one rectangle today (`Roi.rect`, `src/vision_station/jobs/job.py`). Two tapes that cross in an "X" cannot be told apart by colour with
rectangles that take in the crossing: the small square where they cross holds both tapes' printing, and on real frames a window that includes it saw
up to ~9,800 px² of the *other* tape's red, more than a real tape gives under two lights. What works is a region that **leaves the crossing out**:
the horizontal tape as its left and right arms, the vertical tape as its top and bottom arms. Today that is four rectangles (a taped-box job
with four colour windows); wanted is **two regions, each of two parts**, forming a broken "X".

More generally: any part that is not a box (an L-shaped bracket, a ring, a curved label) is measured with the background around it.

## 2. What it is (and is not)

- A region may be a **set of simple polygons** (parts). The region is their **union**. A rectangle is the one-part, four-vertex case.
- Out of scope for v1: holes (subtracting a shape), curves, a mask taught from an image, tools that cannot honour a mask (see §4).
- The job stays *data* (FR-PLT-12): vertices are numbers in the job, not code.

## 3. Data model and how a region is cut

- `Roi` keeps `relative_to` and `rect`. `rect` stays required: it is the **bounding box** of the region (the crop the pipeline already makes) and
  the whole region when there is no `shape`.
- New optional `shape: {parts: [[[x, y], ...], ...]}`, vertices as **fractions of the same reference as `rect`** (the frame, or a fixture's box).
  Written only when used, like `informative`; no format bump (TD-33 added `groups` inside format 3 the same way). A program without this feature
  refuses the job as an unknown field, never judges it with the wrong region (`_Strict`, extra forbidden).
- Validation in `Roi`: 1..8 parts, 3..64 vertices each, every part simple (no self-intersection), area > 0, inside `rect`, and `rect` equal to the
  bounding box of the parts (so the two cannot disagree).
- Cutting (`geometry/pose.py: cut`, `geometry/regions.py: cut_region`): unchanged crop of `rect`, plus a **mask** (`uint8`, 255 inside) built in the
  *cut's own pixel grid*: a vertex maps linearly from the reference's fractions to the cut's pixels, so it needs no extra warp, also for a region of a
  turned fixture (the cut is already upright). Rasterised with `cv2.fillPoly` (no anti-aliasing: deterministic, same on both OSes). `Cut` gains
  `mask: np.ndarray | None`.

## 4. How tools use the mask

A tool that is handed a mask must count **only** masked pixels; a tool that cannot is **refused for a shaped region** at load and at activation,
never run on the box (the box would measure the background: a false PASS, design rule 5).

| Tool | v1 | How |
|---|---|---|
| `blob` | yes | the colour/threshold mask ANDed with the region mask before the parts are counted; filters and areas are inside the shape |
| `color` | yes | fractions over masked pixels |
| `brightness` | yes | statistics over masked pixels |
| `circles`, `pattern`, `compare`, `edge`, `code`, `detect` | no (refused) | need work each: edges/strips with invalid pixels, a template that straddles the border, a variation model with holes. Later, one at a time |

`run(region, params, files)` becomes `run(region, params, files, mask=None)` for the tools that accept it (a `ToolType.supports_mask` flag; the
registry refuses a shaped region for a tool without it with a new error code, texts in pt-BR/en, listed in architecture §10.3 and the error table).

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

## 7. Milestones

1. **M1, backend and display (no drawing yet).** Model + validation, cut with mask, `blob`/`color`/`brightness` honour it, other tools refuse,
   result outline, overlay, API schema, docs (job-format §3, architecture §7.1/§14, tools-reference "Region" and the three tools, error table),
   validation bench (V2 golden: a polygon equal to the rectangle gives the same result as the rectangle; V3: degenerate and self-intersecting shapes
   are refused; V4: a masked blob keeps its outcome under light, noise and shift; unsupported tool refused). Unit tests for the polygon check.
   *Result:* the two-region "X" job can be built by script (as the other jobs here) and shown by the operator screen. Editing it is still done in JSON.
2. **M2, editor drawing.** §6, with frontend tests and a browser e2e (draw an "X" of two shapes, test, save, activate).
3. **M3, more tools.** `circles` (mask the edge map), `pattern` (reject a template outside the mask), `compare`, `edge`, as asked.

## 8. Risks and open questions

- **A mask is not a locator.** The shape is fixed in the frame (or a fixture); a box that moves needs a fixture (TD-19/21), same as a rectangle.
- **Holes.** Not in v1. If needed: `exclude` parts, evaluated after the union.
- **Where the shape is valid.** An empty mask after the crop (a shape wholly outside the frame) is the existing *region outside the picture* error.
- **Colour tools still need the exposure and white balance fixed** (the job's camera profile); a shape does not change that.
- **Cost.** Building the mask is one `fillPoly` per run; cache it per (job version, region size) if a profile shows it matters.
- **Which format number?** Plan says none (optional field, like TD-33); confirm with the maintainer before M1.

## 9. Interim

The four-rectangle tape job stays the delivered one. Version 5 of it (the editor's v4 with one corrected test picture) is the candidate to activate.
