# Vision Station — Frontend

| | |
|---|---|
| Document | 05 — Frontend (web interface) |
| Version | 0.1 (draft) |
| Date | 2026-10-14 |
| Author | Lucas (developer and maintainer) |
| Status | In use. Replaced the Preact + htm prototype, which was deleted in VIA-0033 (TD-20 revised). |

Related documents: 02 — Requirements (FR-UI-*, FR-PLT-*, FR-ADM-*) · 03 — Architecture (§10 API) · 04 — Technical Decisions (TD-11, TD-19, TD-20) · `docs/design/DESIGN-IS-2026-10-14/` (audit of the prototype).


---

## 1. Purpose and scope

The web interface is **how the system is operated**: the operator watches results; the supervisor manages jobs, results and backups; the maintainer sets up cameras, tools and regions, and configures the system. Like the software of a commercial vision system, but for any station (TD-19), not only the packaging one.

In scope: every screen listed in section 7, access control in the interface (section 8), the editor with regions drawn on the live image (section 10), and the contract with the API (section 9).

Out of scope: a mobile app, remote access over the plant network (allowed later by configuration, NFR-SEC-3), languages other than Portuguese (the code is prepared, section 11), charts and dashboards beyond the shift counters.

The Preact + htm prototype of task VIA-0013 was deleted when the React operator screen reached parity (task VIA-0033).

---

## 2. Users and contexts

| Role | Where and how | What matters |
|---|---|---|
| **Operator** (no login) | Fixed monitor at the station (assumed 21–24" 1080p, possibly touch), looks from about 2 m, hands busy with boxes | The verdict, readable at once; nothing to learn (NFR-USA-1/2); no way to break the system by accident |
| **Supervisor** | Same PC or another on the plant network, mouse and keyboard | Select the job, review failures, correct wrong results, keep the backup (NFR-USA-3) without the maintainer |
| **Maintainer** | At the PC, with the camera in reach | Tune camera settings while watching, draw regions, test a job on the current image, change settings; full visibility of what the system did and why |

Contexts that shape the design: shop-floor light (dark theme default, strong contrast), gloves and touch (large targets in kiosk mode), a PC with no internet (everything served locally, fonts included), unattended running (the screen must show the truth about the system, never a stale or hopeful state).

---

## 3. Stack and project layout

### 3.1 Decisions

| Area | Choice | Why | Instead of |
|---|---|---|---|
| Language | **TypeScript** (strict; version 5.9 because `openapi-typescript` and `typescript-eslint` do not yet accept a newer one) | Types across 20+ screens and the API client; refactors stay safe for one developer | JavaScript |
| UI library | **React** (current stable, pinned by lockfile) | The decision of the owner; the largest ecosystem for forms, tables, canvas and accessibility primitives | Preact + htm (prototype) |
| Build | **Vite** | Fast dev server with proxy, one hashed bundle with route-level splitting, no custom tooling | Webpack, no build |
| Styling | **Tailwind CSS** with design tokens as CSS variables | One visible system (audit principle #3); utilities keep components consistent; no runtime | CSS-in-JS, hand-written CSS |
| Components | **shadcn/ui** pattern: components copied into the repo, built on **Radix UI** primitives, `class-variance-authority` for variants | Accessible dialogs, menus, selects, tabs, tooltips out of the box; we own the code, nothing hides behind a theme API; MIT | Material UI, Ant Design, Mantine (large, visually generic, harder to bend to an HMI look) |
| Icons | **lucide-react** (ISC) | One consistent set, tree-shaken | Mixed icon sets |
| Fonts | **IBM Plex Sans** and **IBM Plex Mono**, self-hosted via `@fontsource` (OFL) | Legible at distance, tabular figures, no CDN | System fonts, Google Fonts |
| Routing | **React Router** (data router, browser history) | Nested layouts per role, route guards, lazy routes; server falls back to `index.html` | Hash routes |
| Server state | **TanStack Query** | Caching, invalidation after mutations, retries, loading and error states for every REST call | Hand-written fetch state |
| Live state | **Zustand** store fed by the WebSocket | High-frequency status and frames without re-rendering the tree; ~1 KB | Context for live data |
| API client | **openapi-typescript** types and **openapi-fetch**, generated from the FastAPI OpenAPI document | The server defines the contract; a CI check fails if the generated file is stale | Hand-written types |
| Forms | **React Hook Form** + **Zod** for our own forms; a small **`SchemaForm`** renderer for tool parameters (section 7.3) | Tool parameters come as JSON Schema from Pydantic; a renderer for the subset we use (about 300 lines, tested) matches our design better than a generic form library | RJSF |
| Tables | **TanStack Table** | Sorting, column control, pagination for results and audit | Hand-built tables |
| Toasts | **sonner** | Accessible live-region toasts | Custom |
| Region editor | HTML `<canvas>` for the image + **SVG overlay** for shapes, pointer events, own reducer for undo/redo (section 10) | Handles, keyboard control and hit-testing are easier on SVG than on canvas | Konva, Fabric |
| Tests | **Vitest**, **Testing Library**, **MSW**, **Playwright**, **axe-core** (dev only) | Section 13 | — |
| Lint/format | ESLint 9 (+ `typescript-eslint`, `jsx-a11y`, `react-hooks`; version 9 because `jsx-a11y` does not yet accept 10) and Prettier | Catches accessibility and hook mistakes at commit time | — |
| Language of the interface | **Portuguese (pt-BR) only**; every string in one module, `src/texts.ts`, no translation library | The software is not multilingual (owner, 2026-10-14) | i18n framework |

Licences (TD-18): React, Radix, Tailwind, shadcn/ui code, TanStack, Zustand, sonner, Zod, React Hook Form, Vite: MIT. lucide-react: ISC. IBM Plex: SIL OFL. axe-core is MPL-2.0 and is used only in tests, never shipped. A `THIRD_PARTY_LICENSES` list for the bundle is generated in CI and fails on a disallowed licence.

### 3.2 Project layout

```
frontend/                       # source (needs Node only to build)
  package.json  package-lock.json  vite.config.ts  tsconfig.json  eslint.config.js
  index.html
  src/
    main.tsx
    app/            router.tsx  providers.tsx  shell/ (AppShell, NavRail, TopBar, StatusStrip)  guards.tsx
    api/            client.ts  schema.d.ts (generated)  queries/ (jobs, results, system, users, audit, camera, tools)
                    live.ts (WebSocket client + Zustand store)  errors.ts
    features/       operator/ jobs/ editor/ camera/ results/ dataset/ settings/ access/ audit/ about/ auth/
    components/
      ui/           shadcn-based primitives (Button, Dialog, Select, Tabs, Table, Badge, Tooltip, ...)
      domain/       VerdictPanel  LiveCanvas  StatusIndicator  RoiEditor  SchemaForm  ReportList  ImageCompare
    lib/            format.ts  units.ts  keyboard.ts  geometry.ts
    texts.ts                        # every user-facing string, in pt-BR (the software is not multilingual)
    styles/         tokens.css  globals.css
    test/           setup.ts  msw/  fixtures/
  e2e/              *.spec.ts       # Playwright, against scripts/e2e_station.py
```

Rules: a feature folder owns its screens, queries and components; `components/domain` holds pieces shared by two or more features; nothing in `components/ui` knows the domain. No user-facing string outside `texts.ts`.

---

## 4. Information architecture and app shell

### 4.1 Sitemap by role

```
/                      Operator (kiosk)                       everyone
/jobs                  Jobs                                   supervisor+
/jobs/:id              Job detail, versions                   supervisor+
/jobs/:id/edit         Job editor  (steps below)              maintainer
/camera                Camera setup (live)                    maintainer
/results               Results                                supervisor+
/results/:id           Result detail (also as side panel)     supervisor+
/dataset               Dataset and collection                 maintainer
/settings              System settings                        maintainer
/access                Access (passwords, sessions)           maintainer
/audit                 Audit log                              supervisor+
/about                 Versions, licences, support bundle     supervisor+
/login                 Login (also a dialog from anywhere)    —
/design                Component gallery (development only)   —
```

### 4.2 Shell

- **Operator mode** (route `/` with no login): full-bleed, no navigation, a small lock button at the top right. This is what Edge shows in kiosk mode at start-up.
- **Admin mode** (after login): a left navigation rail (icons + labels, collapsible) with only the entries the role may open; a top bar with the job and version in use, a **status strip** and the user menu (role, logout). The operator screen stays one click away ("Estação").
- **Status strip**, always visible in admin mode and as the footer of the operator screen: three named indicators — **Sistema** (the browser reaches the core), **Câmera** (connected, with last-frame age), **Registro** (results are being written; red if the recorder fails). Each shows a dot **and** a word; clicking opens the detail. This replaces the single "Conectado" badge of the prototype (audit principle #6).
- **Global behaviour:** an offline banner when the live socket is down (the screen never shows a stale verdict, section 7.1); on session expiry a login dialog opens over the current page and the page is kept; on `403` a plain "sem permissão" page; an idle timeout (setting, default 10 min) logs the supervisor or maintainer out and returns to the operator screen.

---

## 5. Design principles

The audit of the prototype (18/30) is in `docs/design/DESIGN-IS-2026-10-14/`. The redesign follows Rams' principles in this order of priority and the habits of **high-performance HMI** (ISA-101 style): the screen is calm and neutral; **colour carries meaning and only meaning**.

1. **Useful (#2).** The operator reads the verdict in under a second from 2 m. The supervisor and maintainer reach any task in at most three clicks.
2. **Understandable (#4).** Every control has a plain Portuguese name; one concept, one word (glossary, section 11). No jargon on the operator screen.
3. **As little design as possible (#10).** No decoration; no gradients or shadows on the dark theme except overlays; elements are removed until removing one breaks the task.
4. **Honest (#6).** Indicators claim only what they measure; a state the system does not know is shown as unknown, never as OK.
5. **Thorough (#8).** Every screen has designed loading, empty, error, success, disabled, focus and offline states; they are part of the definition of done.
6. **Aesthetic (#3).** One visible system of tokens (section 6). No orphan values.
7. **Unobtrusive, long-lasting, innovative-with-restraint (#5, #7, #1).** Neutral graphite surfaces, a single accent, system-quality typography. Nothing that dates itself.

---

## 6. Design system

All values are CSS variables in `styles/tokens.css`; Tailwind is configured to expose only these. Dark is the default; light follows `prefers-color-scheme` and a user setting. Contrast figures below are WCAG ratios computed from these values.

### 6.1 Colour tokens

Neutrals (8 steps) carry the layout; **four status hues** carry meaning; one accent marks the primary action and focus.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg-0` | `#0E1116` | `#F4F6F9` | page |
| `--bg-1` | `#151A21` | `#FFFFFF` | panels, cards |
| `--bg-2` | `#1B222B` | `#EEF1F5` | inputs, table stripes, secondary buttons |
| `--bg-3` | `#242D38` | `#E3E8EE` | hover, selected row |
| `--border` | `#2D3743` | `#CBD3DD` | hairlines |
| `--border-strong` | `#3D4957` | `#9AA6B4` | emphasised separators |
| `--border-control` | `#738091` | `#6B7787` | edges of form controls: at least 3:1 on every surface (WCAG 1.4.11), which `--border-strong` is not |
| `--fg` | `#E8EDF3` | `#14181D` | text (16.1:1 on bg-0 dark, 16.5:1 light) |
| `--fg-muted` | `#A3AFBD` | `#4B5766` | secondary text (7.8:1 on bg-1 dark, 7.4:1 light) |
| `--accent` | `#2F6FEB` | `#1F5FD6` | primary button, links, focus ring (white text 4.6:1 / 5.7:1) |
| `--accent-text` | `#7DB0FF` | `#1F5FD6` | accent as text on surfaces (7.9:1 dark) |
| `--ok` | `#188257` | `#14754A` | PASS solid (white text 4.8:1 / 5.7:1) |
| `--ok-text` / `--ok-surface` | `#4CC38A` / `#0F2E22` | `#0F6A41` / `#DDF3E8` | PASS text and soft surface (6.6:1 / 5.7:1) |
| `--fail` | `#C93338` | `#B42328` | FAIL solid (white text 5.2:1 / 6.5:1) |
| `--fail-text` / `--fail-surface` | `#FF7C80` / `#3A1316` | `#A81E23` / `#FBE0E1` | (6.6:1 / 5.9:1) |
| `--warn` | `#F2B01E` | `#F2B01E` | ERROR/attention solid (dark text `#14181D`, 9.3:1) |
| `--warn-text` / `--warn-surface` | `#F7C948` / `#3B2E0A` | `#7A5200` / `#FCEFC7` | (8.5:1 / 6.0:1) |
| `--busy-surface` / `--busy-text` | `#10284A` / `#7DB0FF` | `#DCE9FF` / `#1F5FD6` | inspecting, preparing (6.7:1 / 4.7:1) |

Implementation (task VIA-0032): `src/styles/tokens.css` is the only place with values, written once per token with `light-dark(<light>, <dark>)` so the theme follows `prefers-color-scheme` or `<html data-theme="dark|light">`; `globals.css` maps them to Tailwind names (`bg-surface-0..3`, `border-line`, `border-line-control`, `text-fg`, `text-fg-muted`, `bg-accent`, `text-ok-text`, `bg-ok-surface`, `text-on-fail`…) and switches the default Tailwind palette, sizes and radii **off**. `tokens.test.ts` reads the file and checks every text pair at 4.5:1 and the control edges at 3:1 in both themes; `design-rules.test.ts` fails the build on a colour value outside `tokens.css`, an arbitrary pixel value in a class name, or a default palette class.

Rules: neutral surfaces never carry colour; a status colour is **always** paired with an icon and a word (never colour alone, NFR-USA-2); no more than one solid status surface visible at a time on the operator screen.

### 6.2 Typography

IBM Plex Sans for text, IBM Plex Mono for numbers, ids and times (tabular figures). Eight sizes only:

| Token | Size / line | Use |
|---|---|---|
| `text-xs` | 12 / 16 | table meta, captions |
| `text-sm` | 14 / 20 | table and form text, admin default |
| `text-base` | 16 / 24 | body, operator secondary |
| `text-lg` | 20 / 28 | card titles, buttons in kiosk mode |
| `text-xl` | 24 / 32 | page titles |
| `text-2xl` | 32 / 40 | counters |
| `text-3xl` | 48 / 56 | reason text on the operator screen |
| `text-display` | clamp(48px, 5.5vw, 96px) | the verdict word (APROVADO, REPROVADO, ERRO); other headlines use `text-3xl` |

Weights 400, 500, 600. Verdict word 700. No other sizes or weights.

### 6.3 Space, shape, depth, motion

- **Spacing:** 4 px grid: 4, 8, 12, 16, 24, 32, 48, 64. Nothing else.
- **Radius:** 6 px (controls), 10 px (cards, dialogs), pill (badges). No other radii.
- **Depth:** on dark, separation by surface step and hairline, no shadows; dialogs and popovers use `--bg-1` with a border and one shadow token.
- **Motion:** 120–180 ms ease-out for state changes; nothing animates while idle; a spinner only while a request or inspection is running; `prefers-reduced-motion` removes transitions. Live frames are never animated.
- **Density:** `kiosk` (min target 56 px, base text 16–20) and `compact` (min target 36 px, base 14). The operator route is always `kiosk`; admin routes `compact`, switchable.

### 6.4 Components

Built on shadcn/ui; each has loading, disabled, error and focus states in the gallery at `/design`.

| Component | Notes |
|---|---|
| Button | variants `primary`, `secondary`, `ghost`, `danger`; sizes `md`, `lg` (kiosk); icon + label; busy state keeps width |
| Badge / StatusIndicator | dot or icon + word; tones `ok`, `fail`, `warn`, `busy`, `neutral`, `unknown` |
| Dialog, Sheet (side panel), AlertDialog | focus trap, focus return, Escape; AlertDialog for impactful actions with a named confirmation ("Ativar versão 7 de Caixa M?") |
| Form controls | Input, NumberInput (unit, min/max, step), Select, Switch, Slider (with number box), SegmentedControl, Textarea, FileDrop |
| Table | TanStack Table: sortable, sticky header, row selection, empty and loading skeleton, pagination |
| Tabs, Stepper, Breadcrumb | Stepper for the job editor |
| Toast | success, error (with action), info; stays 5 s, errors until dismissed |
| Tooltip, Popover, DropdownMenu | keyboard accessible |
| EmptyState, ErrorState, Skeleton | every list and panel uses them |
| ReportList | list of checks with pass/fail icon and message (verification and tests) |
| VerdictPanel | the operator verdict (section 7.1) |
| LiveCanvas | draws JPEG frames from the live store; fit/fill; optional overlay layer |
| ImageCompare | side by side or slider: reference vs live, raw vs overlay |
| RoiEditor | section 10 |
| SchemaForm | section 7.3 |

### 6.5 Patterns

- **Confirm only what matters:** activate a job, override a failed verification, delete, restore a backup, change a password. Everything else saves directly with an undo toast where possible.
- **Errors:** a failed request shows what happened in Portuguese and what to do, with a retry; the technical detail is in a collapsible "detalhes".
- **Empty states** say what the screen is for and offer the first action ("Nenhum job ainda. Importe um arquivo ou crie um job.").
- **Units** always shown (µs, ms, mm, %); numbers right-aligned in tables, monospaced.
- **Time:** local time `dd/mm/aaaa hh:mm:ss`; relative time ("há 3 min") with the exact time on hover.

---

## 7. Screens

For each: purpose, layout, data, actions, states. "Query" = TanStack Query; "live" = the Zustand live store.

### 7.1 Operator (`/`, everyone)

Purpose: the verdict and nothing that distracts from it (FR-UI-1..5, NFR-USA-1/2).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Caixa M — fita vermelha  v7                                      🔒 Entrar  │
├────────────────────────────────────────────┬─────────────────────────────────┤
│                                            │                                 │
│                                            │            ✔                    │
│              LIVE IMAGE                    │        APROVADO                 │
│        (fit; overlay of what the           │      Fita presente em 98%       │
│         last inspection looked at)         │      da emenda                  │
│                                            │                                 │
│                                            │  14:32:07 · 310 ms              │
│                                            │                                 │
│                                            ├─────────────────────────────────┤
│                                            │ Últimos: ✔ ✔ ✘ ✔ ✔ ✔ ✔ ✘ ✔ ✔    │
│                                            │ Hoje  42 total · 39 · 2 · 1     │
│                                            │ [Inspecionar agora] [Incorreto?]│
├────────────────────────────────────────────┴─────────────────────────────────┤
│ ● Sistema   ● Câmera 30 fps   ● Registro                      Aguardando caixa│
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Verdict panel** fills the height of the right column. Fill = the status surface (ok / fail / warn / busy / neutral), a large icon, the word at `text-display`, the reason at `text-3xl`, time and duration small. States: `Aguardando <objeto>` (neutral), `Inspecionando…` (busy), `APROVADO`, `REPROVADO`, `ERRO` (warn), `Câmera desconectada`, `Falha na verificação — chamar manutenção`, `Em manutenção`, `Preparando…`, and **`Conectando…` / `Sem conexão`** (neutral, with the last known state greyed out and clearly marked old; never a stale verdict presented as current).
- **Live image:** the newest frame, fit to the area; after a result, the overlay of that inspection (regions, found anchor, failing area) until the next object. No frame for 3 s → "Sem imagem da câmera".
- **Secondary actions** (secondary and ghost weight, below the verdict): **Inspecionar agora** (enabled only when the station is Ready or WaitingStill) and **Resultado incorreto?** (opens a dialog: "O sistema disse REPROVADO. Qual era o resultado certo? [Estava OK] [Estava NÃO OK]").
- **Last results strip** (last 10, icon + position, hover for time and reason) and **Hoje** counters (total, aprovadas, reprovadas, erros; shift start is a setting).
- **Footer:** status strip (section 4.2) and the waiting text of the job.
- **Optional** (setting, off by default): audible alert on FAIL (FR-UI-7).
- Data: `live` (status, frames, events), `GET /api/state` on connect, `POST /api/trigger`, `POST /api/results/{id}/incorrect`.
- Accessibility: the verdict is an `aria-live="assertive"` region; the result is also announced as text; all targets 56 px; keyboard works but nothing is bound to a single key.

### 7.2 Jobs (`/jobs`, `/jobs/:id`, supervisor+)

Purpose: choose the active job, move jobs between PCs, keep backups (UC-02, UC-04, UC-05, NFR-USA-3).

```
Jobs                                   [Importar arquivo]  [Fazer backup]  [Backups…]
┌───────────────────────────────────────────────────────────────────────────────┐
│ Nome               Ativo   Versões  Última alteração     Autor      Ações      │
│ Caixa M — fita…    ● v7    7        02/10/2026 15:40     lucas      ⋯          │
│ Etiqueta de lote           3        10/10/2026 09:12     lucas      ⋯          │
└───────────────────────────────────────────────────────────────────────────────┘
```
- **List:** name, the active version as a badge, number of versions, last change, author, row menu (Abrir, Exportar, Duplicar (maintainer), Editar (maintainer)).
- **Detail (side panel or page):** versions as a timeline (number, date, author, notes, parent), the active one marked; per version: **Ativar** (opens the verification dialog), **Exportar .vjob**, **Comparar com…** (diff of job.yaml, read-only), **Abrir no editor** (creates a draft from this version).
- **Activate flow:** AlertDialog "Ativar versão 7 de Caixa M?" → runs the verification, shows a **ReportList** (settings, view against reference, reference set) with pass/fail → if all pass **Ativar**; if some fail: the report and, for the maintainer only, **Ativar mesmo assim** which requires a written reason (recorded in the audit log).
- **Import:** FileDrop for `.vjob` or `.vbak`; shows what the file contains and what it will add ("3 versões de 2 jobs; 1 já existe") before confirming; result list per job (added, already present, renumbered). Importing never activates.
- **Backup:** "Fazer backup" writes to the configured folder and shows name and size; "Backups…" lists the folder with download; restore = import of a `.vbak`.
- States: loading skeleton rows; empty ("Nenhum job ainda…"); import error with the server's reason; offline.
- Data: `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/versions/{v}/activate`, `GET …/export`, `POST /api/jobs/import`, `POST /api/backup`, `GET /api/backup`.

### 7.3 Job editor (`/jobs/:id/edit`, maintainer) and Camera setup (`/camera`)

Purpose: create and tune a job while looking at the real image (UC-03, FR-JOB-2/4/5, FR-PLT-*). The largest screen.

```
┌ Caixa M — fita vermelha · rascunho de v7 ───────── [Descartar] [Testar] [Salvar…] ┐
│ ① Câmera        │                                          │ Inspetor (do passo)  │
│ ② Gatilho       │                                          │                      │
│ ③ Qualidade     │            IMAGE + REGIONS               │  Exposição  [8000] µs│
│ ④ Âncora/regiões│       (live, or a captured still)        │  Ganho      [ 0 ]    │
│ ⑤ Ferramentas   │                                          │  …                   │
│ ⑥ Referência    │                                          │  [Aplicar na câmera] │
│ ⑦ Revisar       │                                          │                      │
└─────────────────┴──────────────────────────────────────────┴──────────────────────┘
```

- **Draft model:** the editor works on a draft held in memory and autosaved to the browser; the server never sees a half-edited job. **Salvar…** asks for a note and creates version n+1 (parent n); **Descartar** drops the draft. Leaving with unsaved changes asks first. Validation errors from the server (Pydantic) are shown on the field.
- **Steps:**
  1. **Câmera** — the camera profile (resolution, format, exposure, gain, white balance, focus, zoom, power-line, low-light), live image, brightness and sharpness readouts, histogram. **Aplicar na câmera** pauses the station, applies, reads back and shows the per-setting result (applied / not supported / rejected) with the reason. Also available alone at `/camera` for tuning without a job.
  2. **Gatilho** — mode (`image_presence`, `manual`, `external`, `continuous`), the presence area drawn on the image, stillness time, thresholds; a live "presença / movimento / parado há 0,6 s" readout so the maintainer sees the trigger decide.
  3. **Qualidade** — brightness range, minimum sharpness ratio, minimum similarity, anchor tolerance; the live image's current values are shown next to each limit with a "usar o valor atual ±20%" helper.
  4. **Âncora e regiões** — the locator (type and parameters) and the regions, drawn on the image (section 10), named, relative to the anchor or the frame.
  5. **Ferramentas** — ordered list (drag to reorder); **Adicionar ferramenta** lists the registered types with a one-line description; selecting one shows its form, drawn from the tool's JSON Schema (below), the region it looks at, and the failure text (`reason_fail`, with the available `{fields}` listed). Each tool has **Testar**: runs on the current image and shows the result, score and what it looked at as an overlay.
  6. **Referência** — capture the reference image from the live view; the system measures brightness, sharpness and anchor; manage the **reference set**: capture frames or upload images, label each with the expected outcome (and optional expected scores and reason text), set the tolerance, **Executar tudo** to see every case pass or fail in a ReportList.
  7. **Revisar** — a summary of what changed from the parent version, the verification report on the draft, and the save button.
- **Testar** (top bar) runs the whole job on the current image through the same pipeline the station uses and shows PASS/FAIL/ERROR, the reason and per-tool scores.
- **SchemaForm** renders the subset of JSON Schema that our Pydantic models produce: `string` (with `enum` as select, `format` hints), `number`/`integer` (with min/max and `x-unit` shown as a suffix), `boolean` (switch), arrays of primitives (list editor), nested objects (group), nullable (`anyOf null`) as "usar valor opcional" toggle, defaults and descriptions as hints. Server-side field names in errors map onto fields. Unknown constructs render as a JSON text area with validation, never silently dropped. New tool types therefore need no screen code (FR-PLT-2).
- Data: `GET /api/jobs/{id}/versions/{v}`, `POST /api/jobs/validate`, `POST /api/jobs/{id}/versions`, `GET /api/tools`, `POST /api/camera/apply`, `GET /api/camera/state`, `POST /api/jobs/test`, `GET /api/snapshot.jpg`, the live socket.
- States: no camera (steps needing the image show "Sem imagem da câmera" and stay editable as text), station busy (the editor pauses it and shows a banner; leaving the editor resumes it), a failed apply shows the report instead of an error page.

### 7.4 Results (`/results`, supervisor+)

Purpose: understand failures and correct wrong results (UC-07, FR-LOG-4).

- **Filter bar:** period chips (Hoje, 7 dias, 30 dias, Personalizado), job, result (Todos, Aprovadas, Reprovadas, Erros), "só incorretos"; the filters live in the URL so a view can be shared.
- **Table:** time, job and version, result (badge), reason, duration, a thumbnail on hover. Server-side pagination (100 per page). **Exportar CSV** exports exactly the filtered set.
- **Detail side panel:** the image with a **Original / Marcado** toggle, zoom; per-tool scores and timings; the job version used; **Marcar como incorreto** (PASS↔FAIL) with the effect explained ("a imagem vai para o treinamento"); **Baixar imagem**. If the image was not kept, the panel says so and disables the actions that need it.
- States: loading skeleton, empty ("Nenhum resultado neste período"), error with retry.
- Data: `GET /api/results`, `GET /api/results/{id}`, `GET /api/results/{id}/image`, `POST /api/results/{id}/incorrect`, `GET /api/results.csv`.

### 7.5 Dataset and collection (`/dataset`, maintainer)

Purpose: gather and export training images (FR-MDL-1/2, TD-10, UC-08).

- Per job: **Modo de coleta** switch (every inspection frame is also saved), counters (collected, corrected, per label), and a clear note that images stay on this PC.
- **Exportar dataset:** choose the job, see the count, export; the result shows the **dataset id**, the folder and a download; exporting the same content twice reuses the id.
- A grid preview of the latest collected images with their labels (lazy-loaded).

### 7.6 Settings (`/settings`, maintainer)

Purpose: the installation's configuration (system configuration, architecture §4.5).

- **Câmera:** driver (UVC, Hikvision later, file), device (picked from a list, shown by name and path), a **Testar conexão** button.
- **Armazenamento:** backup folder with a **Testar** (write and read a file), automatic backup schedule and number to keep (FR-JOB-10), recording limits (keep everything / PASS sampling / retention days / minimum free disk), data folder shown read-only.
- **Estação:** name, shift start times (counters), language (Portuguese), audible alert on FAIL, idle timeout.
- **Rede:** port and listening address; opening the API to the network shows a warning and requires a password to exist for the supervisor (NFR-SEC-3).
- Fields that need a restart are marked, and a **Reiniciar o sistema** banner appears after saving them. Saving shows what changed and asks to confirm.
- Data: `GET/PUT /api/system`, `POST /api/system/test-camera`, `POST /api/system/test-folder`.

### 7.7 Access (`/access`, maintainer)

- Table of the two protected roles (Supervisor, Mantenedor): whether a password is set, last change; **Definir/trocar senha** dialog (twice, minimum 8 characters, strength hint, never shown again); **Encerrar todas as sessões**.
- A supervisor can change only their own password; the maintainer both.
- Data: `GET /api/users`, `PUT /api/users/{role}/password`, `POST /api/users/sessions/revoke`.

### 7.8 Audit (`/audit`, supervisor+)

- Table of events (when, what — activate, activate with override, import, backup, password change, settings change — job and version, role, reason); filters by kind and job; detail drawer with the raw record; **Exportar CSV**.
- Data: `GET /api/audit`.

### 7.9 About (`/about`, supervisor+)

- Application version, job file format version, tool types and versions, camera driver in use, licences of the shipped components (FR-ADM-3, NFR-LIC-2), and **Gerar pacote de suporte** (zip of logs, system config without secrets, last results; NFR-MAI-2).

### 7.10 Login and errors

- **Login dialog:** role select (Supervisor, Mantenedor), password, clear messages for wrong password and for the 30 s lock (with a countdown). Reachable from the lock button and from any expired session.
- **Pages:** `403` "Sem permissão", `404`, an **error boundary** per route with retry, and **offline** handled by the shell banner.

---

## 8. Access control in the interface

| Capability | Operator | Supervisor | Maintainer |
|---|---|---|---|
| See state, live image, results of the day | ✔ | ✔ | ✔ |
| Manual trigger, mark a result wrong | ✔ | ✔ | ✔ |
| Jobs: list, activate (verified), export, import, backup | | ✔ | ✔ |
| Results history, images, CSV | | ✔ | ✔ |
| Audit, About | | ✔ | ✔ |
| Activate despite failed verification (with reason) | | | ✔ |
| Editor, camera setup, tools | | | ✔ |
| Dataset and collection mode | | | ✔ |
| Settings, access, pause/resume/retry | | | ✔ |

- The router hides entries and blocks routes by role; **the server enforces the same table on every endpoint** (the interface is convenience, not security).
- Token kept in memory and `sessionStorage` (cleared on tab close), sent as `Authorization: Bearer`; the 8 h session, the lock after 5 wrong passwords and the idle timeout come from the API and settings.
- Requests from other origins are refused by the server; the interface calls only same-origin `/api`.
- Sensitive actions (override, password change, settings change, restore) are recorded in the audit log by the server.

---

## 9. API contract the interface needs

### 9.1 Conventions

- **Prefix:** every API path moves under `/api` (the prototype used the root, which collides with the interface's own routes). The WebSocket is `/api/live`. Everything else is the interface: `/assets/*` (hashed, `immutable`), `index.html` (`no-cache`), and **a fallback to `index.html` for any other GET** so deep links and reloads work. Unknown `/api/*` paths return JSON `404`.
- **Contract:** every endpoint declares Pydantic request and response models, so the OpenAPI document is complete; `npm run gen:api` regenerates `src/api/schema.d.ts`; CI fails if the committed file differs.
- **Errors:** `{ "detail": "<Portuguese message>", "code": "<machine code>", "fields": {"path.to.field": "message"} }`; `422` for validation, `401` no login, `403` wrong role, `409` state conflict (station not ready, verification failed), `429` login lock with `Retry-After`.
- **Pagination:** `limit`, `offset`; responses carry `total`.
- **Time:** ISO 8601 with offset.

### 9.2 Existing endpoints (move under `/api`)

`GET state`, `GET result/last`, `GET snapshot.jpg`, `POST trigger`, `POST results/{id}/incorrect`, `WS live`, `POST login`, `POST logout`, `GET whoami`, `GET jobs`, `POST jobs/{id}/versions/{v}/activate`, `GET jobs/{id}/versions/{v}/export`, `POST jobs/import`, `POST backup`, `GET backup/{name}`, `GET results`, `GET results.csv`, `GET results/{id}`, `GET results/{id}/image`, `POST collection/{job_id}`, `POST station/{command}`.

### 9.3 New endpoints (task VIA-0025 and VIA-0026)

| Endpoint | Purpose | Role |
|---|---|---|
| `GET /api/tools` | tool types with versions, description and **JSON Schema** of the parameters | maintainer |
| `GET /api/jobs/{id}` | versions with date, author, notes, parent, active flag | supervisor |
| `GET /api/jobs/{id}/versions/{v}` | the full job (job.yaml as JSON, camera profile, list of extra files, reference meta, expected set) | maintainer |
| `POST /api/jobs/validate` | validates a draft; returns field errors | maintainer |
| `POST /api/jobs` / `POST /api/jobs/{id}/versions` | create a job / save version n+1 with a note | maintainer |
| `POST /api/jobs/{id}/duplicate` | new job from a version | maintainer |
| `POST /api/jobs/test` | run a draft on the current frame (or a given image); returns outcome, reason, per-tool scores, overlay | maintainer |
| `GET /api/jobs/{id}/versions/{v}/diff?against=` | read-only diff of the definitions | supervisor |
| `GET/POST /api/camera/state`, `POST /api/camera/apply` | live camera settings and apply with the per-setting report (station paused during the call) | maintainer |
| `POST /api/reference/capture`, `POST /api/reference/cases` | reference image and reference-set cases from the live frame or an upload | maintainer |
| `GET /api/backup` | list backups in the folder | supervisor |
| `GET/PUT /api/system`, `POST /api/system/test-camera`, `POST /api/system/test-folder` | system configuration (`system.yaml`) | maintainer |
| `GET /api/users`, `PUT /api/users/{role}/password`, `POST /api/users/sessions/revoke` | access management | maintainer |
| `GET /api/audit` | audit events with filters and CSV | supervisor |
| `POST /api/dataset/export`, `GET /api/dataset` | dataset counts and export | maintainer |
| `GET /api/about` | versions, tool types, driver, licences; `POST /api/support-bundle` | supervisor |

### 9.4 Live socket (`/api/live`)

Text messages (JSON): `status` (full state, camera, counters, job — at connect and every 2 s), `state`, `result` (with `record_id`), and new `camera_settings` events during tuning. Binary messages: JPEG frames, at most 10 per second, 960 px wide by default (a query parameter asks for another width in the editor). The client reconnects with backoff and drops frames older than the newest.

---

## 10. Region editor

Used by the editor steps 2, 4 and 5 and by the camera screen.

- **Geometry:** all shapes are stored **normalised** (0–1) relative to the frame or the anchor; the editor converts to pixels for display. Rectangles first (all tools in TD-19 use rectangles); polygons later behind the same interface.
- **Rendering:** the image on a `<canvas>` (ImageBitmap), shapes on an **SVG overlay**; layers for regions, the trigger area, the located anchor, and the last tool results, each toggled from a small layer menu.
- **Interaction (pointer events, mouse and touch):** draw by dragging; move by dragging; eight resize handles; keep inside the image; snap to the image edges and to other regions (hold Alt to disable); wheel zoom up to 16× around the pointer, pan with Space+drag or two fingers; double-click a region to rename.
- **Keyboard:** Tab cycles regions; arrows nudge 1 px (Shift: 10 px); Delete removes; Ctrl+Z / Ctrl+Y undo and redo (a reducer with a history stack); Enter edits the name; Escape cancels a drag.
- **Readouts:** the size and position in pixels and in fractions; with the pointer over the image, the **RGB and HSV** of the pixel (needed by the `color` tool), and a **colour picker mode** that samples a region and proposes a hue range for the tool's parameters.
- **Anchor-relative regions** are drawn relative to the located anchor: while editing, the anchor is located on the current image, and a banner says when it cannot be found (regions then show relative to the frame, marked "sem âncora").
- **Accessibility:** every region is a focusable SVG group with a name and an `aria-label` giving size and position; all operations are reachable by keyboard.
- **Tests:** geometry helpers (clamp, snap, resize) unit-tested; interactions tested with Playwright on the editor.

---

## 11. Language and copy

- **Portuguese (pt-BR) only.** The software is not multilingual: all strings live in `src/texts.ts` as plain typed constants (functions for the ones that take values), with no translation library. Reasons the jobs define (`reason_fail`) arrive already written in Portuguese.
- **Voice:** short, plain, active; numbers and units instead of adjectives; no jargon for the operator; no exclamation marks; no blame ("Câmera desconectada. Reconectando automaticamente.").
- **Glossary (one concept, one word):**

| Use | Not |
|---|---|
| Job | receita, programa, configuração |
| Versão | revisão |
| Ferramenta | check, teste, filtro |
| Região | ROI, área (in the UI; "área de presença" only for the trigger) |
| Âncora | referência (that is the image), objeto localizado |
| Resultado: Aprovado / Reprovado / Erro | OK / NOK, sucesso / falha |
| Estação | máquina, sistema (for the station as a whole; "Sistema" only in the status strip) |
| Mantenedor / Supervisor / Operador | admin, usuário |
| Imagem de referência / Conjunto de referência | golden, baseline |

- **Dates and numbers** in pt-BR formats (`1.234,5`, `dd/mm/aaaa`).
- Every string is reviewed against the **honesty check**: it states only what the system measured.

---

## 12. Accessibility, kiosk and touch

- **Target:** WCAG 2.2 AA on every screen: contrast (tokens in 6.1 are checked), focus visible (2 px accent ring + 2 px offset), target size ≥ 24 px (admin) and 56 px (kiosk), keyboard operation for everything including the editor, `prefers-reduced-motion`, `prefers-color-scheme`, `lang="pt-BR"`, one `h1` per page, landmarks, a skip link, focus trap and return in dialogs, live regions for results and toasts.
- **Kiosk (Edge `--kiosk`):** the operator route fills the screen, hides the cursor after 5 s of inactivity (touch and mouse bring it back), disables text selection and the context menu on that route only, and never shows scrollbars. Zoom and shortcuts are blocked by kiosk mode itself. An idle login falls back to the operator screen.
- **Touch:** no hover-only function; drags in the editor work with touch; dialogs scroll inside themselves.
- **Colour independence:** every status has an icon and a word.
- **Reading distance:** operator text sizes in 7.1 are chosen for 2 m on a 24" 1080p monitor (verdict word up to 96 px, reason 48 px).

---

## 13. Testing and quality gates

| Level | Tool | What |
|---|---|---|
| Unit | Vitest | view-model functions (state → what the screen shows; ported from `viewmodel.js` and its tests), geometry, formatting, schema-form mapping |
| Component | Testing Library + MSW | each screen against a mocked API in loading, empty, error, success and forbidden states; dialogs (focus trap and return); the verdict panel for every station state |
| Contract | CI script | regenerate `schema.d.ts` from the running API and fail if it differs; every endpoint the client uses exists in the OpenAPI document |
| End to end | Playwright against `scripts/e2e_station.py` (the demo with controls: `POST /__e2e/box/on`, `/__e2e/outcome/FAIL`…) | operator cycle (box in, verdict, box out), login and role menus, activate a job (verified and refused), import and export, results filter and mark incorrect, editor: draw a region, test a tool, save a version, camera apply report |
| Accessibility | `@axe-core/playwright` | zero serious or critical violations on every route in both themes |
| Tokens and components in the browser | Playwright on `/design`, in four theme situations (dark and light by the system, and each forced over the other) | computed styles equal the tokens (background, density 36/56 px, bundled fonts, reduced motion); screenshot baselines are not used because text rendering differs between Windows, macOS and Linux, so they would fail on every other machine |
| Budget | `size-limit` | initial JS for the operator route ≤ 150 KB gzip, total initial ≤ 300 KB gzip; editor loaded lazily |
| Lint/type | ESLint (`jsx-a11y`, hooks), `tsc --noEmit` | zero warnings |

Run locally: `cd frontend && npm run build && npm run e2e` (starts the simulated station by itself; `npm run e2e:ui` for the debugger, `npm run e2e:report` after a failure). The first run needs `npx playwright install chromium`. Every page load is also checked to be free of console errors and of requests that leave this machine, which is how the invalid `ws://[::1]` source in the content policy was found.

**Definition of done for a screen:** all states designed and tested (loading, empty, error, success, disabled, focus, offline, forbidden); keyboard-only run-through; axe clean in both themes; strings in `pt-BR.ts`; seen in a real browser at 1920×1080 and at 1280×720; budget respected.

---

## 14. Build, serving and CI

- **Node** is needed to build, not to run: `frontend/` builds with `npm run build` into `frontend/dist/`; the API serves that folder (`VISION_STATION_WEB` points it elsewhere), and the installer copies it next to the program (task VIA-0017). Nothing of the interface lives inside the Python package. The built files are **not** committed; CI builds them and the installer includes them.
- **Dev:** `npm run dev` (Vite, hot reload, port 5173) with a proxy of `/api` and the WebSocket to `127.0.0.1:8765`; run `uv run python scripts/e2e_station.py --port 8765` (the simulated station) next to it.
- **Commands** (in `frontend/`): `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run gen:api` (regenerates `src/api/openapi.json` and `schema.d.ts` from the API; commit both), `npm run build`, `npm run size`.
- **Without a build:** the server answers `/` with a clear page ("A interface não foi compilada. Rode `npm run build` em `frontend/`.") and keeps the API working.
- **Serving:** `/assets/*` with `Cache-Control: public, max-age=31536000, immutable`; `index.html` with `no-cache`; fallback for client routes. CSP becomes stricter than the prototype's: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` (for the style attributes Radix sets), `img-src 'self' blob: data:`, `connect-src 'self'` plus the same-host WebSocket, `frame-ancestors 'none'`. No inline script, so the import-map hash of the prototype goes away.
- **CI** (GitHub Actions, Windows and Linux): `npm ci`, lint, typecheck, unit and component tests, API contract check, build, size budget, then the Python tests against the built files, then Playwright (Linux).
- **Prototype removal:** done in VIA-0033 (the Preact files and `tests/web/` are gone); `src/vision_station/web/` is gone too, the interface lives only in `frontend/`.

---

## 15. Work plan and task map


| Task | Content | Sections | Estimate | Deadline |
|---|---|---|---|---|
| VIA-0030 | This document and the audit | all | 3 h | 14/10 (done) |
| VIA-0031 | React + Vite + TypeScript project, Tailwind, lint and tests set up, API under `/api` with response models and generated types, serving the build with fallback, CI with Node | 3, 9.1, 14 | 10 h | 17/10 |
| VIA-0032 | Design system: tokens, light and dark themes, local fonts, base components, `/design` gallery | 5, 6 | 8 h | 20/10 |
| VIA-0033 | App shell (routes, roles, login, navigation, status strip, error pages) and the redesigned operator screen; remove the prototype | 4, 7.1, 7.10, 8 | 12 h | 22/10 |
| VIA-0034 | Interface tests: Vitest, Testing Library, MSW, Playwright against the demo, axe, size budget | 13 | 6 h | 24/10 |

Existing tasks now carried out in React, estimates raised for the scope: VIA-0026 API for management (10 → 12 h, response models), VIA-0027 Jobs screen (8 → 10 h, section 7.2), VIA-0028 Results, dataset, settings, access, audit, about (10 → 14 h, sections 7.4–7.9), VIA-0022 Job editor with regions (20 → 24 h, sections 7.3 and 10).

Order: backend pieces (VIA-0008 pipeline, VIA-0025 configuration, VIA-0026 API) run in parallel with VIA-0031 and VIA-0032; screens follow in the order operator → jobs → results and the rest → editor, each closed only when its definition of done (section 13) is met.

---

## 16. Open questions

1. **Shift:** when do the counters start and reset (fixed times? a "novo turno" button)? Today: since midnight.
2. **Audible alert on FAIL** (FR-UI-7 is a Could): wanted at the station? Which sound and volume?
3. **Branding:** client logo or colours on the screen? Today: product name only.
4. **Station monitor:** size, resolution and touch? The kiosk sizes assume 21–24" 1080p.
5. **Who edits jobs:** only the maintainer (FR-JOB-4) or also the supervisor for thresholds? Today: maintainer only.
6. **Idle timeout** length for supervisor and maintainer sessions (proposed 10 min).
7. **Network access:** will the supervisor use the interface from another PC (then the listening address and a password are mandatory, section 7.6)?
8. **Operator correction:** may the operator mark results wrong without login (FR-MDL-2 says supervisor or operator), or should it need a PIN?
