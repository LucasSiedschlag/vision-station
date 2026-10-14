# 02 — Scorecard

Tie-breaker applied: when unsure, the lower score. Worst instance scored, not the mean.

1. Good design is innovative — Score: **1/3**
   Evidence: generic dark card dashboard (01 Visual, screenshot). Justification: imitates common dashboards with minor variation; nothing wrong, nothing new.
2. Good design makes a product useful — Score: **2/3**
   Evidence: 01 Structural, `operator.js:93-97`. Justification: the verdict is the largest element and the task is supported, but the blue `Inspecionar agora` button is as loud as the verdict and sits above the counters, and the side panel leaves a large empty area.
3. Good design is aesthetic — Score: **1/3**
   Evidence: 01 Visual (27 colours, 12 type sizes, off-grid spacing, 5 radii, empty gap). Justification: tokens exist but no scale is followed; 3–5 inconsistencies.
4. Good design makes a product understandable — Score: **2/3**
   Evidence: 01 Copy (`Conectado`, `Aviso`). Justification: one label needs thought ("connected" to what?).
5. Good design is unobtrusive — Score: **2/3**
   Evidence: 01 Visual. Justification: chrome is quiet, but the coloured 6 px frame plus the verdict plus the toast compete at the moment of a result.
6. Good design is honest — Score: **2/3**
   Evidence: `app.js:50`. Justification: the `Conectado` badge claims more than it measures (one minor inflation).
7. Good design is long-lasting — Score: **2/3**
   Evidence: neutral palette, system fonts. Justification: one dated marker (rounded dark cards with coloured borders as in 2021–2023 dashboards).
8. Good design is thorough down to the last detail — Score: **1/3**
   Evidence: 01 Visual states (loading missing, no error boundary), 01 Accessibility (no focus trap/return, no skip link). Justification: two to three states or details missing.
9. Good design is environmentally friendly — Score: **3/3**
   Evidence: 01 Weight (22 KB gzip, no idle animation, dark default, motion gated). Justification: meets every anchor of a 3.
10. Good design is as little design as possible — Score: **2/3**
   Evidence: 01 Structural (duplicated mapping; clock, connection badge and version in the bar). Justification: two removable elements.

**Total: 18 / 30.** No principle scored 0.
