# 03 — Verdict

**REDESIGN.** The total is 18/30, below the threshold of 20 for a refine; the weak points (aesthetic system, thoroughness) are structural, not touch-ups, and the stack is being replaced anyway.

Highest-leverage moves:

1. **#3 Aesthetic — one visible system.** Replace 27 colours, 12 type sizes, off-grid spacing and 5 radii with a token set: 8 neutral steps + 4 status hues, 8 type sizes, a 4 px spacing grid, 2 radii plus pill. Evidence: `styles.css` (01 Visual).
2. **#8 Thorough — every state designed.** Add loading ("Conectando…"), error boundary with retry, empty and offline states, focus trap and focus return in dialogs, skip link; test them. Evidence: `viewmodel.js:13`, dialogs (01 Accessibility).
3. **#2 Useful — the verdict is the figure.** Make the verdict fill the panel's height, move the manual trigger and "wrong result?" to secondary weight, and remove the empty gap. Evidence: `operator.js:93-97`, screenshot.
4. **#6 Honest — say what is measured.** Replace `Conectado` with separate, named indicators (Sistema, Câmera, Registro); drop the generic `Aviso` badge. Evidence: `app.js:50`, `operator.js:100`.
5. **#4 / contrast — AA everywhere.** Make solid buttons and status text pass 4.5:1 (white on `#3d8bfd`, `#1f9d55`, `#e5484d` fail). Evidence: 01 Visual contrast list.
