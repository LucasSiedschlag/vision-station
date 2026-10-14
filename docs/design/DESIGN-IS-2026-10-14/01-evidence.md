# 01 — Evidence

Facts only; scoring is in 02. Method notes: sizes by `gzip` of the served files; contrast computed from the stylesheet's colours (WCAG 2.x relative luminance); states and layout from the screen running in Chrome.

## Structural
- Interactive elements on the operator screen: header `Entrar`/`Sair` (1), `Inspecionar agora` (1), `Resultado incorreto?` (1, conditional) + 3 in its dialog; login dialog: 1 select, 1 input, 2 buttons. Source: `app.js:50-54`, `views/operator.js:93-97`, `views/login.js`.
- Repeated pattern: the PASS/FAIL/ERROR → APROVADO/REPROVADO/ERRO mapping is written twice (`viewmodel.js:18-20` and `views/operator.js:71`).
- Nesting depth of the operator tree: 5 (app → main → operator → aside → verdict).
- Landmarks: `header`, `main`, `aside`, `section`, conditional `nav` (4–5). No skip link.

## Visual (inferred from `static/styles.css`, confirmed in browser)
- Colours: **27** distinct hex values. Tokens exist (`:root`), but 4 colours are hard-coded (`#000`, `#fff`).
- Type sizes: **12** distinct values (`.8rem`, `.85`, `.9`, `.95`, `1.05`, `1.1`, `1.25`, `1.35`, `1.4`, `1.8rem`, `16px`, one `clamp`) — no scale.
- Spacing values include 10, 14 and 18 px next to 4/8/12/16/24: not on a 4 px grid (`styles.css`).
- Radii: 5 values (8, 10, 12, 14, 999 px).
- Layout: the side panel has a large empty gap between the trigger button and the counters (screenshot, 2026-10-14); the verdict panel has a fixed `min-height: 210px` regardless of content.
- Lowest contrast of primary text: `white on #3d8bfd` (primary button) **3.33:1**, `white on #1f9d55` **3.49:1**, `white on #e5484d` **3.91:1**, `#e5484d` text on panel **4.33:1**. Body text 16.7:1; muted 6.7–7.4:1. Large-text buttons (20 px) pass 3:1; the 16 px semibold `Entrar` button (`btn-primary`) fails 4.5:1.
- States: empty (`Sem imagem da câmera`, counters at 0) present; loading **missing** (before the first message the screen says `Sem conexão`, `viewmodel.js:13`); error: toasts only, no error boundary, no message for a failed live socket reason; success: toast present; focus: visible outline present; disabled: present.

## Copy and honesty
- `Conectado` badge (`app.js:50`) reports the browser↔system link, not the camera or the station: a reader would take it for "the camera is connected".
- `Aviso` badge before every warning (`operator.js:100`) says nothing the text does not.
- No superlatives, no dark patterns. Plain Portuguese; the verdict words carry the meaning together with colour.
- Mixed vocabulary: `Aguardando objeto` (default) vs `Aguardando caixa` (job text) — intended (TD-19), but not explained on screen.

## Weight and friction
- Transferred: **22.3 KB gzip** in total (56 KB raw), **13 requests** + 1 WebSocket (unbundled ES modules load in a waterfall). TTI not measured; local server, so effectively instant.
- Idle animations: **0** (one CSS transition, gated by `prefers-reduced-motion: no-preference`).
- Modals/badges/notifications on load: 0.
- Dark by default; `prefers-color-scheme: light` honoured.

## Accessibility
- Native `button`/`select`/`input`: all primary actions reachable by keyboard. Dialogs close on Escape; no focus trap, no focus return on close.
- The verdict panel has `role="status" aria-live="assertive"`. Canvas has an `aria-label`.
- No `lang` mismatch (`pt-BR`). No skip link.

## Known gaps
- No automated axe run; no measurement on a touch device; no real operator test.
