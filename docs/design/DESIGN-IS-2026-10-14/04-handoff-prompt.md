# 04 — Handoff

````
/make-plan Redesign the Vision Station web interface (operator screen first, then jobs, editor, results, settings, access, audit). Current design failed audit at 18/30 with the weakest principles #3 aesthetic (1) and #8 thorough (1), and #1 innovative (1).

Verdict paragraph (quoted from 03-verdict.md):
> REDESIGN. The total is 18/30, below the threshold of 20 for a refine; the weak points (aesthetic system, thoroughness) are structural, not touch-ups, and the stack is being replaced anyway.

Why redesign and not refine: the total is below 20 and the owner decided to replace the stack (Preact+htm prototype -> React + Vite + TypeScript), so no structure of the prototype needs to survive.

Preserve from current design:
- Domain behaviour and copy: verdict words APROVADO / REPROVADO / ERRO shown with colour and text together (viewmodel.js:18-20); state->headline mapping (viewmodel.js:16-37) as the reference for tests; `Aguardando <objeto>` text coming from the job (viewmodel.js:33, TD-19).
- The live protocol: one WebSocket with JSON status/state/result messages and JPEG frames at <=10 fps (api.js:63-85, api/app.py `/live`), re-expressed under `/api/live`.
- Role model: operator without login, supervisor and maintainer with token (api.js:18-60), enforced again by the server.
- Dark-first, light on request; operator screen readable from 2 m.

Discard:
- Ad-hoc stylesheet tokens (27 colours, 12 type sizes, off-grid spacing, 5 radii). Evidence: styles.css. Caused failure on principle #3.
- The `Conectado` badge and generic `Aviso` badge. Evidence: app.js:50, operator.js:100. Caused failure on principle #6.
- The fixed-height verdict panel and the empty side-panel gap. Evidence: styles.css `.verdict`, screenshot. Caused failure on principle #2.
- The unbundled Preact/htm module graph (13 requests) and the hand-written store. Evidence: 01 Weight.

Top moves from the audit (verbatim):
1. #3 Aesthetic: one visible system - token set with 8 neutral steps + 4 status hues, 8 type sizes, 4 px grid, 2 radii plus pill. Evidence: styles.css.
2. #8 Thorough: every state designed - loading, error boundary with retry, empty, offline, focus trap and return, skip link. Evidence: viewmodel.js:13, dialogs.
3. #2 Useful: the verdict is the figure - fills the panel, trigger and "wrong result?" at secondary weight. Evidence: operator.js:93-97.
4. #6 Honest: separate named indicators (Sistema, Camera, Registro) instead of `Conectado`. Evidence: app.js:50.
5. #4 contrast: AA everywhere (solid buttons and status text >= 4.5:1). Evidence: 01 Visual contrast list.

Redesign principles in priority order:
1. Useful (#2) - the operator reads the verdict from 2 m in under a second; the supervisor and maintainer reach any task in at most three clicks.
2. Understandable (#4) - every control named in plain Portuguese; no jargon; one concept, one word.
3. As little design as possible (#10) - colour means status and nothing else (ISA-101 style high-performance HMI); no decoration.

Deliverables for the plan:
- New information architecture (sitemap by role, not derived from the prototype)
- New primary flows, low-fi, labelled, side by side with the current ones
- States checklist (empty, loading, error, success, focus, disabled, offline) per screen
- Migration path (prototype stays until the new operator screen reaches parity, then is deleted) and cutover criteria
- Token decisions with contrast figures; component inventory; testing and budget rules

Anti-patterns to guard against:
- Porting the old structure under new styling
- Keeping both interfaces behind a flag indefinitely
- Following a visual trend instead of the principles above
- Treating the Preserve list as optional
````
