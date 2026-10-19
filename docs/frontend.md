# Vision Station — Frontend

| | |
|---|---|
| Document | 05 — Frontend (web interface) |
| Version | 0.3 — the trigger moves to step 1, *Imagem e disparo*, and step 5 becomes *Qualidade* (§4.3, TD-32). 0.3 — 0.2 (the interface of a vision system: configuration sequence, vision controls with live feedback, three settings levels, image overlays) on **shadcn/ui + Tailwind + React Aria** (TD-29, revised) and **in Portuguese and English** (TD-30) |
| Date | 2026-10-18 |
| Author | Lucas (developer and maintainer) |
| Status | Design for review. Replaces 0.1 (14/10/2026) and 0.2 (same day as 0.3; 0.2 planned a migration to Mantine, reverted by the owner after weighing the trade-offs). Sections 1–16 keep the numbers of 0.1, which code comments and tasks cite; sections 17–19 are new. What is built today is in §15. |

Related documents: 02 — Requirements (FR-UI-*, FR-PLT-*, FR-ADM-*, FR-JOB-14) · 03 — Architecture (§10 API, §14 fixtures, §15 tools, §16 machine interface) · 04 — Technical Decisions (TD-11, TD-20, **TD-29**) · `docs/design-system.md` (practical guide) · `docs/design/DESIGN-IS-2026-10-14/` (audit of the prototype).

**What changed in 0.2, in one paragraph.** Version 0.1 built a correct, accessible admin application. It did not yet feel like the software of a vision system. The editor asked for numbers nobody knows by heart (an HSV range, a minimum score). It showed every parameter of a tool in one long form. The image was a third of the screen. The order of the steps did not follow the order of the work: the reference image came after the tools that need it. Version 0.2 reorganizes the interface around **the order in which a station is set up** (§4.3). That order is the same in the market leaders (Cognex EasyBuilder: connect → set up image → locate part → inspect part → I/O → communication → save → run; Keyence IV: image optimization → master registration → tool settings → output assignment) and in our own pipeline (architecture §7.1). Version 0.2 also makes the image the centre of every configuration screen (§10). It replaces typed numbers with **graphical controls that show the effect on the next capture** (§19). It shows settings at **three levels** (§17). It lets the user turn the **image overlays** on and off (§18). The component base **stays shadcn/ui + Tailwind**, extended with **React Aria** for the colour, range and number controls and with shadcn's `Sidebar`, `Resizable`, `Command` and `Chart` (§3, TD-29). The interface becomes **bilingual, Portuguese and English** (§11, TD-30).

---

## 1. Purpose and scope

The web interface is **how the system is operated**:
- the **operator** watches results;
- the **supervisor** manages jobs, results and backups, and fine-tunes tolerances;
- the **maintainer** commissions the station, sets up cameras, fixtures and tools, and configures the system.

It should feel like the software of a commercial vision system, but for any fixed station (TD-19).

**In scope:**
- every screen listed in §7;
- the configuration sequence (§4.3);
- the image workspace and region editor (§10);
- the vision controls (§19);
- the settings levels (§17);
- the overlays (§18);
- access control in the interface (§8);
- the API the interface needs (§9);
- the two interface languages (§11).

**Out of scope:**
- a mobile app;
- remote access over the plant network (allowed later by configuration, NFR-SEC-3);
- languages other than Portuguese (pt-BR) and English;
- a dashboard product. Statistics stay limited to what tuning and supervision need (§7.13).

---

## 2. Users and contexts

| Role | Where and how | What matters |
|---|---|---|
| **Operator** (no login) | Fixed monitor at the station (21–24", 1080p, possibly touch). Looks from about 2 m with busy hands | The verdict, readable at once; on FAIL, *where* on the part; nothing to learn (NFR-USA-1/2); no way to break the system by accident |
| **Supervisor** | Same PC or another on the plant network, mouse and keyboard | Select the job, review failures, correct wrong results, keep the backup (NFR-USA-3), and **fine-tune a tool's tolerance** when the product drifts, without touching regions, camera or tools (FR-JOB-14, §7.12) |
| **Maintainer** | At the PC, with the camera and parts in reach | Commission the station (§7.11), build and tune jobs while watching the image, see what the system measured and why, configure the machine interface |

Contexts that shape the design:
- **Shop-floor light:** dark theme by default, strong contrast.
- **Gloves and touch:** large targets in kiosk mode.
- **A PC with no internet:** everything is served locally, fonts included.
- **Unattended running:** the screen shows the truth about the system, never a stale or hopeful state.
- **A CPU-only PC** (tier M or R, NFR-PERF-5): live feedback in the editor is rate-limited by what the PC measured (§19.1).

**Screen sizes:**
- Operator screen: 1920×1080 kiosk.
- Configuration screens: designed for 1920×1080; they must stay fully usable at **1366×768** (§10.1).

---

## 3. Stack and project layout

### 3.1 Decisions

The foundation of 0.1 stays: it is tested, accessible and owned by us (23 base components, tokens with tested contrast, design-rule and accessibility tests, the `/design` gallery). 0.3 **adds** what the vision interface needs. Why not a full library such as Mantine: the vision controls (gauge, HSV range, histograms, image workspace) are our own code with any library, and replacing the foundation would redo a tested layer on top of the screens that are being redesigned anyway (TD-29).

| Area | Choice | Why | Instead of |
|---|---|---|---|
| Language | **TypeScript** (strict) | Types across 20+ screens and the API client; refactors stay safe for one developer | JavaScript |
| UI library | **React 19** | Owner's decision; largest ecosystem | — |
| Build | **Vite** | Fast dev server with proxy, hashed bundle, route-level splitting | — |
| Base components | **shadcn/ui** pattern, kept: components copied into the repo, built on **Radix** primitives, variants with `class-variance-authority` | We own the code; already built and tested (0.1) | Mantine (0.2, reverted: full re-foundation), MUI, Ant Design |
| **Colour, range and number controls** | **React Aria Components** (Adobe, Apache-2.0), through shadcn's React Aria variants where they exist and our own wrappers otherwise: `Slider` (one or more thumbs), `NumberField` (units, locale formatting), `ColorArea`, `ColorSlider`, `ColorField` (HSB channels), `DropZone` — **TD-29** | Best-in-class accessibility for exactly the controls the vision interface leans on; HSB colour channels and multi-thumb sliders are the base of `HsvRangePicker` and `ToolToleranceGauge`; numbers and dates formatted per locale (TD-30) | Radix Slider alone (no colour primitives, no number field) |
| Styling | **Tailwind CSS** with design tokens as CSS variables, kept | One styling system; tokens already enforced by tests (§6) | CSS modules |
| Layout and navigation | shadcn **`Sidebar`** (shell), **`Resizable`** (workbench panels, on `react-resizable-panels`), **`Command`** (Ctrl+K palette, on `cmdk`), **`Drawer`**, **`Accordion`** | From the same catalog, same tokens | Hand-built shell and panels |
| Forms | **React Hook Form** + **Zod** for our own forms, kept; **SchemaForm v2** for tool and locator parameters (§19.2) | The schema-driven form keeps "a new tool needs no screen code" (FR-PLT-2) | — |
| Toasts, dialogs | **sonner** and our `ConfirmDialog` on Radix Dialog, kept | Already built and tested | — |
| Charts (low frequency) | shadcn **`Chart`** (on Recharts, MIT) | Results trends, reason-code Pareto, margin trends (§7.13); styled with our tokens | — |
| Charts (live, ≥ 5 Hz) | **Own canvas components** (histogram, profile, gauge) | 256-bin histograms and line profiles redrawn per capture; canvas is cheaper than SVG charts at this rate | A charting library per frame |
| Reordering | **`@dnd-kit/core`** + **`@dnd-kit/sortable`** (MIT; the stable 6.x line, not the pre-1.0 `@dnd-kit/react`) | Drag to reorder tools and anchors, with keyboard support | Up/down buttons only |
| **Interface languages** | **Lingui** (`@lingui/core`, `@lingui/react`, `@lingui/cli`, `@lingui/vite-plugin`; MIT) with **PO catalogs** for `pt-BR` and `en` — **TD-30** | Messages extracted from the code, compiled at build (small runtime, missing translations fail the build), ICU plurals; PO is the same format the Python side uses for its texts (gettext/Babel), so one translation workflow serves both | `texts.ts` (pt-BR only, 0.1); i18next (runtime JSON, larger, no compile-time check) |
| Icons | **lucide-react** (ISC), kept | Already used everywhere | — |
| Fonts | **IBM Plex Sans** and **IBM Plex Mono**, self-hosted (OFL), kept | Legible at distance; tabular figures for every measured value; Latin coverage for both languages | — |
| Routing, server state, live state | **React Router**, **TanStack Query**, **Zustand**, kept | — | — |
| API client | **openapi-typescript** + **openapi-fetch**, generated, kept | The server defines the contract | — |
| Image workspace | `<canvas>` for the frame + **SVG overlay** for shapes, kept and extended (§10) | Handles, hit-testing and keyboard focus are easier on SVG | Konva, Fabric |
| Tests | **Vitest**, **Testing Library**, **MSW**, **Playwright**, **axe-core** (dev only), kept | §13 | — |

Licences (TD-18): React, Radix, Tailwind, shadcn/ui code, Recharts, react-resizable-panels, cmdk, dnd-kit, Lingui, TanStack, Zustand, sonner, Zod, React Hook Form, Vite are MIT; React Aria Components is Apache-2.0; lucide is ISC; IBM Plex is OFL. axe-core (MPL-2.0) is used only in tests. The bundle's licence list is generated in CI and fails on a disallowed licence.

### 3.2 Project layout

```
frontend/
  lingui.config.ts                  # locales pt-BR (source) and en; PO catalogs
  src/
    main.tsx
    app/            router.tsx  providers.tsx (I18nProvider of Lingui + React Aria, query, theme)  shell/  guards.tsx
    locales/        pt-BR/messages.po  en/messages.po   (compiled at build)
    api/            client.ts  schema.d.ts (generated)  queries/  live.ts  editor-session.ts (§9.5)
    features/
      operator/  jobs/  editor/  tune/  setup/  results/  stats/  machine/  dataset/  settings/  access/  audit/  about/  auth/
    components/
      ui/           shadcn components (Radix, and React Aria variants for slider, number, colour)
      vision/       ImageWorkspace  OverlayLayers  Filmstrip  ToolToleranceGauge  HsvRangePicker  Eyedropper  MaskPreview
                    Histogram  ProfilePlot  AngleRangeDial  PoseMarker  TemplateCropper  FocusMeter  ExposureControl
                    ToolList  StepRail  LevelSwitch  VerdictPanel  ResultChips
      form/         SchemaForm (v2), widget registry (§19.2)
    lib/            format.ts (locale-aware)  units.ts  keyboard.ts  geometry.ts  levels.ts  overlay.ts
    styles/         tokens.css (all colour values, including overlay tokens)  globals.css
  e2e/
```

**Rules:**
- A feature folder owns its screens, queries and private components.
- `components/ui` knows nothing of the domain.
- `components/vision` holds the vision controls (§19). They are shared by the editor, the fine-tune screen, the camera screen and the operator screen, and know the domain.
- No user-facing string outside the message catalogs: text is written with Lingui's `t` / `<Trans>` in the source language (pt-BR) and translated in `en/messages.po`.
- No colour value outside `styles/tokens.css`.

---

## 4. Information architecture and app shell

### 4.1 Sitemap by role

```
/                      Estação (operator, kiosk)                         everyone
/setup                 Comissionamento (first start wizard, §7.11)       maintainer
/jobs                  Jobs                                              supervisor+
/jobs/:id              Job detail, versions                              supervisor+
/jobs/:id/edit         Editor de job (the sequence of §4.3)              maintainer
/jobs/:id/tune         Ajuste fino de tolerâncias (§7.12)                supervisor+
/results               Resultados                                        supervisor+
/results/:id           Resultado (side panel or page)                    supervisor+
/stats                 Estatísticas e margens (§7.13)                    supervisor+
/machine               Máquina: interface com o CLP ao vivo (§7.14)      maintainer
/dataset               Dataset e coleta                                  maintainer
/settings/*            Configurações: estação, câmera, armazenamento,    maintainer
                       rede, máquina, desempenho
/access                Acessos                                           supervisor+
/audit                 Auditoria                                         supervisor+
/about                 Sobre                                             supervisor+
/login                 Entrar (also a dialog from anywhere)              —
/design                Galeria de componentes (development only)         —
```

### 4.2 Shell

- **Operator mode** (`/` without login): full-bleed, no navigation, a small lock button at the top right. This is what Edge shows in kiosk mode at start-up.
- **Admin mode** (after login): the shadcn `Sidebar` layout with:
  - **Navigation rail** (`Sidebar`, icons + labels, collapsible to icons), grouped by the four areas of work, separated by space and a divider rather than by labels:
    - **Operação:** Estação.
    - **Configuração:** Jobs, Máquina.
    - **Análise:** Resultados, Estatísticas.
    - **Sistema:** Configurações, Dataset, Acessos, Auditoria, Sobre.
    - Máquina and Estatísticas join the menu when their screens exist (phases B and D); a link is never shown to a screen that is not there.
  - **Top bar:**
    - the active job and version;
    - the **station mode badge**: *Em produção* (green outline) or *Em manutenção* (amber, while an editor or the machine monitor holds the station paused);
    - the user menu (role, settings level, **language**, theme, logout). Language is changed once or a few times per project, so it never sits in the top bar; the operator screen language is *Configurações › Estação*.
  - **Editor top bar** (§7.3) adds, next to the job name, the **trigger control** (`Disparo: Pela imagem ● peça parada há 0,6 s ▾`): the job's trigger mode and what the trigger would do now on the live image (*aguardando peça*, *aguardando sinal · DI1*, *pronto*, *a cada 500 ms*, *sem câmera*). Its menu picks among the four modes, each with a one-line explanation, and links to step 1 for the presence area, still time, delay, debounce and interval. It is a job setting (draft), shown in the top bar because it decides how every inspection starts.
  - The operator screen is one click away ("Estação").
- **Status strip** (footer), always visible in admin mode and on the operator screen. It has four named indicators, each a dot **and** a word; clicking one opens its detail:
  - **Sistema:** the browser reaches the core.
  - **Câmera:** connected, frames per second, last-frame age.
  - **Máquina:** connected, heartbeat age. Shown only when a connector is enabled.
  - **Registro:** results are being written.
- **Global behaviour:**
  - An offline banner when the live socket is down. The screen never shows a stale verdict (§7.1).
  - Session expiry opens a login dialog over the current page and keeps the page.
  - A `403` shows a plain "sem permissão" page.
  - An idle timeout returns to the operator screen and **resumes the station if an editor had paused it**, with a note in the audit log.

### 4.3 The order of work (new in 0.2)

A station is set up in a fixed order, because each step needs the one before it:

```
 Instalação (uma vez)                      Job (por produto)                                      Produção
┌───────────────────────┐   ┌───────────────────────────────────────────────────────────────┐   ┌──────────────┐
│ Comissionamento §7.11 │   │ 1 Imagem e disparo → 2 Amostras → 3 Âncora → 4 Ferramentas →  │   │ Estação §7.1 │
│ câmera, desempenho,   │──▶│ 5 Qualidade → 6 Resultado e saídas → 7 Validar →              │──▶│ Ajuste fino  │
│ senhas, máquina       │   │ 8 Salvar e ativar                                  §7.3       │   │ §7.12        │
└───────────────────────┘   └───────────────────────────────────────────────────────────────┘   └──────────────┘
```

**Answer to "what comes first?":**
- **The camera is chosen once per installation**, in the commissioning wizard (and later in *Configurações › Câmera*). It is system configuration (architecture §4.5), not part of a job.
- **A job begins with the image of this product and how it is taken**: exposure, focus and white balance on the camera already chosen, and the trigger. Cognex keeps both in `AcquireImage` and Keyence in the first screen of the program (document 09 §20); the trigger decides how every picture is taken, so it is set with the image (TD-32).
- Then the job **captures the images it will learn from**: the reference image and samples marked *Boa* and *Ruim*.
- Only then come the fixture and the tools, because both are taught and checked on those images.

The 0.1 editor captured the reference at step 6, after the tools that need it. 0.2 moves it to step 2.

| # | Step | What the user does | Needs | Done when | Mirrors |
|---|---|---|---|---|---|
| 1 | **Imagem e disparo** | Exposure, gain, white balance, focus, zoom, orientation on the live image; histogram and focus meter guide each setting. Then the **trigger**: its type and the parameters of that type (presence area and stillness; delay and debounce; interval). The source of an external signal is not here: it is in *Configurações › Máquina* | A connected camera | Settings applied and read back without errors; trigger values set (defaults are valid) | Cognex *Set Up Image* (`AcquireImage`), Keyence *Image optimization* (*Trigger Options*) |
| 2 | **Amostras** | Capture the **imagem de referência** (a good part, nominal position) and **amostras**: more good parts (*Boa*) and known defects (*Ruim*), placed as in production | Step 1 | Reference image captured | Keyence *Master registration*; our reference set (FR-JOB-9) |
| 3 | **Âncora** | Choose how the part is found (or *sem âncora*: the part is always in the same place); teach it on the reference; set the allowed angle and shift; see it found on every sample | Step 2 | Found on every *Boa* sample, or skipped | Cognex *Locate Part* (fixture), architecture §14 |
| 4 | **Ferramentas** | Add tools, draw their regions on the anchor, set what they measure and their tolerances with gauges that show every sample | Step 2 (and 3 if anchored) | At least one tool; every *Boa* passes and every *Ruim* fails at least one tool | Cognex *Inspect Part*, Keyence *Tool settings* |
| 5 | **Qualidade** | Image quality gates (brightness, sharpness, colour reference), proposed from the samples | Step 2 | Values set (defaults are valid) | — (neither product has quality gates) |
| 6 | **Resultado e saídas** | Which tools decide; the operator texts; the values published to the machine (FR-INT-11) | Step 4 | Defaults are valid | Keyence *Output assignment*, Cognex *Inputs/Outputs* |
| 7 | **Validar** | Run the job on all samples; see the time budget on this PC (FR-ADM-5); compare with the version in production (A/B replay, FR-JOB-12) | Step 4 | All samples as expected, budget met (or accepted with a note) | Our verification (architecture §7.3) |
| 8 | **Salvar e ativar** | Write the note, save version n+1, optionally activate it with verification | Step 7 | Saved | Cognex *Save Job* / *Run Job* |

**Rules of the sequence** (FR-UI-11):
- **Guided, not locked.** The step rail shows every step with its state:
  - *a fazer* (empty circle);
  - *feito* (check);
  - *precisa de atenção* (amber, with the reason on hover);
  - *bloqueado* (lock, with what it needs: "Capture a imagem de referência primeiro").
  A blocked step can be opened to read but not edited. Everything else can be visited in any order. *Próximo passo* at the bottom of each step leads forward.
- **Changes ripple visibly.** If step 1 changes the exposure after tools were tuned, steps 4 and 7 turn *precisa de atenção* ("A imagem mudou depois que as ferramentas foram ajustadas; rode Validar"). Nothing is silently invalidated.
- **Testar is always there** (top bar). It runs the whole draft on the current image or on all samples.
- **Editing an existing job** opens at step 4 (Ferramentas). That is where most edits happen, and the rail stays one click away.
- **As built (VIA-0064).**
  - **The rail.** Eight steps (`features/editor/sequence.ts`). Each has a state drawn as an icon and a word, and its reason as text under the step, never only on hover: *a fazer*, *feito*, *precisa de atenção*, *bloqueado*. A blocked step opens read-only (its inspector is a disabled `fieldset`). The state comes from the draft and from what the server refused, except for the steps whose defaults are valid (Imagem e disparo, Qualidade, Resultado e saídas), which are done once opened.
  - **Blocked.** Âncora, Ferramentas: no reference image yet *and* no tool (a job that already has tools is editable without one, so an old job can be fixed offline). Resultado e saídas and Validar: no tool.
  - **Attention.** The server refused something in the step (the path of the field decides which, the most specific prefix wins). Validar: the last run had samples off, or the job changed after it. Ferramentas: the camera settings, the reference or the samples changed after the last Validar.
  - **Salvar** is never blocked: the top bar's *Salvar…* always works. If the job was not validated, the step says "Ainda não validado".
  - **Validar** runs `POST /api/jobs/verify`: the draft on every sample of its reference set, the same run (`run_reference_set`) that activation does, so a green Validar is not refused at activation for its samples. Nothing is saved or recorded. It returns, per sample, what was expected, what the job said, the reason and the time. The camera and view part of the verification (settings applied, the live frame against the reference) needs the camera and is done when the job is activated. The batch test with per-tool values (`/api/editor/batch`), the A/B replay and the time budget on this PC come with UI-4 and phase C.
  - **Amostras** is the reference image and the samples; *Boa* is expected `PASS`, *Ruim* is `FAIL`, *Com erro* is `ERROR`.
  - **Imagem e disparo** (VIA-0082, TD-32) holds the camera settings and, below them under *Disparo*, the trigger mode with its timing; the presence area is drawn on the image in this step. A server error on `job.trigger` marks this step. **Qualidade** (step 5) holds the quality gates alone. The trigger control in the top bar sets the same value (`setTriggerMode`), so the two always agree. *Contínuo* has **Intervalo mínimo** (`trigger.interval_ms`, FR-TRG-7, default 500 ms, 0 to 10 000): the station waits that long between two inspections, and still never inspects a frame taken while the scene moves. The live "parado há 0,6 s" readout of the control comes with the editor session (UI-4).
  - **Resultado e saídas** has one switch per tool (*Decide o resultado*, `affects_result`) and the operator's waiting text. The outputs to the machine come with phase B.
  - **Mudanças:** the save dialog and *Salvar* list what changed in words (`summary.ts`: camera, reference, samples, anchor, regions, each changed tool parameter by its title, trigger, texts), against the version the draft started from. A draft kept by an older build, or a new job, has no version to compare with.
  - An existing job opens at *Ferramentas*; a new one at *Imagem*. *Próximo passo* at the bottom of each step leads forward.
- **The same order** appears on the job detail page as a read-only summary ("Imagem · Amostras 12 boas / 4 ruins · Âncora forma ±15° · 5 ferramentas · Disparo pela máquina · Validado em 16/10").

### 4.4 Breadboard of the editor flow

`mode: candidate-shape`. It becomes `selected-design` when this document is accepted. Question resolved: does the reordered sequence reach a saved, validated job with the image always in view, and is every visible consequence fed by a real source?

**Places**

| ID | Place | Description |
|---|---|---|
| P1 | Jobs list | Entry: *Novo job* or *Editar* |
| P2 | Editor workbench | Step rail, image workspace, inspector, result bar (§10.1). Steps are local states of P2: the image stays, the inspector changes |
| P2.1 | Inspector: Imagem e disparo | Camera controls, histogram, focus meter; trigger type and its parameters, presence area |
| P2.2 | Inspector: Amostras | Capture reference, capture and label samples, filmstrip |
| P2.3 | Inspector: Âncora | Locator choice, teaching, angle/shift ranges, results per sample |
| P2.4 | Inspector: Ferramentas | Tool list + selected tool's sections and gauges |
| P2.5 | Inspector: Qualidade | Quality gates |
| P2.6 | Inspector: Resultado e saídas | Deciding tools, texts, machine values |
| P2.7 | Inspector: Validar | Run on samples, budget, A/B against production |
| P3 | Save dialog | Note, save, optionally activate (blocking) |
| P4 | Activation report | Verification result (blocking) |
| P5 | Core (system) | Editor session, pipeline, camera, job store |

**UI affordances**

| ID | Place | Affordance | Control | Wires Out | Returns To |
|---|---|---|---|---|---|
| U1 | P1 | *Novo job* | click | → N1 | → P2 (step 1) |
| U2 | P2 | Step rail item | click | → (local step state S1) | P2.x |
| U3 | P2.1 | Exposure / focus / WB controls | drag | → N2 | U4, U5 |
| U4 | P2.1 | Histogram with clipping % | display | — | — |
| U5 | P2.1 | Focus meter with peak hold | display | — | — |
| U6 | P2.2 | *Capturar referência* | click | → N3 | U7 |
| U7 | P2.2 | Filmstrip (reference, Boa, Ruim) | display / click | → S2 select | image workspace U12 |
| U8 | P2.2 | *Capturar como Boa / Ruim* | click | → N3 | U7 |
| U9 | P2.3 | Locator picker + teach on reference | click / drag | → N4 | U10, pose on U12 |
| U10 | P2.3 | Found / not found per sample | display | — | — |
| U11 | P2.4 | Tool list (add, reorder, enable) | click / drag | → S1 draft | U12, U13 |
| U12 | P2 | Image workspace with overlay layers | view / draw | → S1 (regions) | — |
| U13 | P2.4 | Tolerance gauge (live needle, sample dots, draggable limits) | drag | → S1 → N2 | U13, U12, U16 |
| U14 | P2.4 | Color eyedropper / HSV range | drag on image | → N5 | U13, mask on U12 |
| U15 | P2.4 | *Ajustar pelas amostras* | click | → N6 | U13 (proposed limits) |
| U16 | P2 | Result bar (verdict, per-tool chips, time vs budget) | display | — | — |
| U17 | P2.7 | *Validar tudo* / *Comparar com produção* | click | → N6, N7 | report in P2.7, step states |
| U18 | P2 | *Salvar* | click | → P3 | — |
| U19 | P3 | *Salvar* / *Salvar e ativar* | click | → N8 | → P4 or P1 |

**Non-UI affordances**

| ID | Place | Affordance | Wires Out | Returns To |
|---|---|---|---|---|
| N1 | P5 | Create draft (from template or from version n) | → S1 | P2 |
| N2 | P5 | **Editor session**: on each new frame (rate-limited, §19.1) run the draft through the pipeline; send measured values, poses, overlays | → S3 | U4, U5, U12, U13, U16 |
| N3 | P5 | Capture frame into the draft (reference or sample with label) | → S2 | U7 |
| N4 | P5 | Teach locator on reference; locate on every sample | → S1 | U10, U12 |
| N5 | P5 | Propose color range from sampled pixels (percentiles) | → S1 | U14, U13 |
| N6 | P5 | Batch test: run draft on all samples, per-tool values | → S3; propose limits | U13 dots, U15, U17 |
| N7 | P5 | A/B replay against the active version's recorded frames | — | P2.7 report |
| N8 | P5 | Save version (+ verify + activate) | → job store | P4, P1 |

**Stores**

| ID | Store | Description |
|---|---|---|
| S1 | Draft | Job draft in the browser (autosaved) and in the editor session |
| S2 | Sample library | The draft's reference image and samples (become `reference/` and `tests/` of the version) |
| S3 | Measurements | Last live result and last batch results, per tool and sample |

**Trace (primary scenario):** U1 → N1 → P2.1 (U3 → N2 → U4/U5) → P2.2 (U6/U8 → N3 → S2 → U7) → P2.3 (U9 → N4 → U10) → P2.4 (U11, U12, U14 → N5 → U13; U15 → N6 → U13) → P2.7 (U17 → N6/N7) → U18 → P3 → U19 → N8 → P4.

**Reverse trace of U13** (the gauge):
- live needle ← N2 ← frames;
- sample dots ← N6 ← S2;
- limits ← S1 ← U13/U15.

All sources exist. **Gap:** N2 and N6 need new API endpoints (§9.5).

---

## 5. Design principles

The audit of the prototype is in `docs/design/DESIGN-IS-2026-10-14/`. The redesign follows Rams' principles and the habits of **high-performance HMI** (ISA-101 style): the screen is calm and neutral; **colour carries meaning and only meaning**.

The principles of 0.1 stay:
1. Useful.
2. Understandable.
3. As little design as possible.
4. Honest.
5. Thorough.
6. Aesthetic.
7. Long-lasting.

Version 0.2 adds five principles of **vision software**:

8. **The image is the workspace.** Every configuration step shows the image, as large as the screen allows. Settings live beside it, never instead of it. Whatever a setting changes is visible on the image.
9. **Every number has a picture.** A threshold is never only a number field. It is a gauge that shows where the current measurement is, where the samples are, and where the limit sits (§19.3). A colour range is a band on a colour bar plus a mask on the image (§19.4). The number box stays, for precision.
10. **Measure before you tune.** The user sees the measured value before choosing a limit. Limits can be proposed from labelled samples (*Ajustar pelas amostras*, FR-UI-14), as vision sensors do with OK/NG registration. The user always confirms.
11. **Essential first.** Each tool shows the few settings that decide most jobs. More appear when the user asks for them (§17). Hiding a setting never hides that it was changed.
12. **The same layout everywhere.** Every tool's inspector has the same sections in the same order (§19.2). The image workspace, filmstrip and result bar look and behave the same in the editor, the fine-tune screen and the camera screen.

---

## 6. Design system

The values and the mechanism of 0.1 are kept: CSS variables in `styles/tokens.css`, written once per token with `light-dark()`, exposed to Tailwind by `globals.css`, audited for contrast and enforced by tests. 0.3 adds the overlay tokens (§6.1) and the vision controls (§19).

### 6.1 Colour tokens

The neutral, accent and status values of 0.1 are unchanged:
- **Neutrals:** `--bg-0..3`, `--border`, `--border-strong`, `--border-control`, `--fg`, `--fg-muted`.
- **Accent:** `--accent`, `--accent-text`.
- **Status:** `--ok*`, `--fail*`, `--warn*`, `--busy*`.

Each has a dark and a light value. Contrast ratios are as listed in 0.1.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg-0` | `#0E1116` | `#F4F6F9` | page |
| `--bg-1` | `#151A21` | `#FFFFFF` | panels |
| `--bg-2` | `#1B222B` | `#EEF1F5` | inputs, stripes |
| `--bg-3` | `#242D38` | `#E3E8EE` | hover, selected |
| `--border` / `--border-strong` / `--border-control` | `#2D3743` / `#3D4957` / `#738091` | `#CBD3DD` / `#9AA6B4` / `#6B7787` | hairlines / emphasis / control edges (≥ 3:1) |
| `--fg` / `--fg-muted` | `#E8EDF3` / `#A3AFBD` | `#14181D` / `#4B5766` | text |
| `--accent` / `--accent-text` | `#2F6FEB` / `#7DB0FF` | `#1F5FD6` / `#1F5FD6` | primary action, focus, **selection on the image** |
| `--ok` / `--ok-text` / `--ok-surface` | `#188257` / `#4CC38A` / `#0F2E22` | `#14754A` / `#0F6A41` / `#DDF3E8` | PASS |
| `--fail` / `--fail-text` / `--fail-surface` | `#C93338` / `#FF7C80` / `#3A1316` | `#B42328` / `#A81E23` / `#FBE0E1` | FAIL |
| `--warn` / `--warn-text` / `--warn-surface` | `#F2B01E` / `#F7C948` / `#3B2E0A` | `#F2B01E` / `#7A5200` / `#FCEFC7` | ERROR, attention |
| `--busy-surface` / `--busy-text` | `#10284A` / `#7DB0FF` | `#DCE9FF` / `#1F5FD6` | inspecting, preparing |

**Tailwind mapping** (unchanged from 0.1): `bg-surface-0..3`, `border-line`, `border-line-strong`, `border-line-control`, `text-fg`, `text-fg-muted`, `bg-accent`, `text-accent-text`, `bg-ok` / `text-ok-text` / `bg-ok-surface` (and the same for `fail`, `warn`, `busy`). `tokens.test.ts` checks text pairs at 4.5:1 and control edges at 3:1 in both themes; `design-rules.test.ts` fails the build on a colour value outside `tokens.css`, an arbitrary pixel value in a class name, or a default palette class. React Aria components are styled with the same Tailwind names (their `data-*` state attributes map to Tailwind variants).

**Overlay tokens** (new in 0.2; CSS variables `--ov-*` in `tokens.css`, read once by `lib/overlay.ts` for the canvas and SVG layers). Overlays are drawn **on camera images**, not on our surfaces, so they need their own set:
- bright enough to be seen on any product;
- always drawn over a **1 px dark halo** (`rgba(0,0,0,0.6)`) so they also read on white parts;
- never used for interface surfaces.

| Token | Value | Line | Tag | Use |
|---|---|---|---|---|
| `ov-pass` | `#2ED3B7` | 2 px solid | ✓ + tool name | a tool passed |
| `ov-fail` | `#FF4F5E` | 3 px solid | ✕ + tool name + reason | a tool failed |
| `ov-error` | `#FFC233` | 2 px dotted | ! + reason | could not inspect (fixture not found, region outside) |
| `ov-select` | `#5B8CFF` | 2 px solid + handles | name | the region or fixture being edited |
| `ov-neutral` | `#FFFFFF` at 70 % | 1 px | name (on hover) | regions not being edited, presence area |
| `ov-mask` | `#FF3DD8` at 45 % fill, hatched | — | — | colour or threshold mask preview (§19.4) |
| `ov-pose` | `#5B8CFF` | 2 px axes + angle arc | angle in ° | the fixture's position and angle |

These five hues were run through the dataviz validator on the dark surface:
- **Normal-vision separation:** passes (worst pair 26.2).
- **Colour-blind separation:** pass ↔ fail reaches ΔE ≥ 8 only after the green was moved to teal (`#2ED3B7`); the earlier `#36D27E` gave 6.7 for deuteranopia.
- **Lightness band:** "fails" the chart rule on purpose. Overlays must be bright on dark images; the halo provides the contrast.

Because one pair (`ov-mask` ↔ `ov-select`) sits at 7.9, **colour is never the only code on the image**: pass, fail and error also differ by line weight, dash and tag icon. This keeps NFR-USA-2.

### 6.2 Typography

IBM Plex Sans for text, IBM Plex Mono for every measured number, id and time (tabular figures). The eight sizes and three weights of 0.1 are kept (`text-xs` 12 … `text-3xl` 48, and `text-display` for the verdict, clamp 48–96 px). Measured values in gauges and the result bar use Mono 14 (compact) or 20 (kiosk).

### 6.3 Space, shape, depth, motion

These are unchanged from 0.1:
- **Spacing:** the 4 px grid (4, 8, 12, 16, 24, 32, 48, 64).
- **Radius:** 6 px for controls, 10 px for cards, pill for badges (`rounded-control`, `rounded-card`, `rounded-pill`). The image workspace has **no radius**: an image is a measurement, not a card.
- **Depth:** separation by surface step and hairline. One shadow, for floating panels only.
- **Motion:** 120–180 ms for state changes; nothing animates while idle. **Live images and gauge needles are never animated**: the needle jumps to each new measurement, because a smoothed needle would show a value that was never measured.
- **Density:**
  - `kiosk`: 56 px targets, 16–20 px text; operator route.
  - `compact`: 36 px targets, 14 px text; admin routes.
  - Implemented as in 0.1, with a `data-density` attribute and the density-aware classes (`h-control`, `fs-control`).

### 6.4 Components

The 0.1 base components stay (`components/ui`: Button, Badge, StatusIndicator, Dialog, ConfirmDialog, Sheet, Select, Switch, SegmentedControl, Tabs, Table, Tooltip, Popover, DropdownMenu, Stepper, FileDrop, Skeleton, Spinner, EmptyState, ErrorState, toasts), each with every state in `/design`.

Added in 0.3:

| Component | Source | Use |
|---|---|---|
| `Sidebar` | shadcn catalog | Admin shell navigation (§4.2) |
| `Resizable` | shadcn catalog (`react-resizable-panels`) | Workbench panels (§10.1) |
| `Command` | shadcn catalog (`cmdk`) | Ctrl+K: go to a job, a step, a tool, a setting |
| `Accordion`, `Drawer` | shadcn catalog | Inspector sections; filmstrip and inspector at 1366×768 |
| `Chart` | shadcn catalog (Recharts) | Statistics (§7.13) |
| `Slider` (multi-thumb), `NumberField` | React Aria (shadcn's React Aria variant, or our wrapper) | Every limit and range: replaces the 0.1 `SliderField` and `NumberInput`, adds locale formatting (`0,80` in pt-BR, `0.80` in en) |
| `ColorArea`, `ColorSlider`, `ColorField` | React Aria | Base of `HsvRangePicker` and the reference-colour control (§19.4) |
| `LanguageSwitch` | own | pt-BR / en, in the user menu and on the login dialog (§11) |

**Vision components:** §19.

### 6.5 Patterns

The patterns of 0.1 are kept:
- Confirm only what matters.
- Errors say what happened and what to do.
- Empty states invite the first action.
- Units are always shown.
- Local time format.

New in 0.2:
- **The draft is the unit of work.** Every change in the editor and the fine-tune screen goes to the draft, autosaved in the browser. *Desfazer/Refazer* (Ctrl+Z/Y) work across steps. Nothing reaches production before *Salvar*, and nothing reaches the station before *Ativar*.
- **Proposals are never applied silently.** *Ajustar pelas amostras*, the colour eyedropper and *usar o valor atual* show the proposed values as a ghost on the gauge with *Aplicar* and *Descartar*.
- **Every place that shows a result shows why.** The result bar, the operator screen, the results page and the gauges link a tool's verdict to its region on the image and to the measured value.

---

## 7. Screens

For each screen: purpose, layout, data, actions, states. "Query" means TanStack Query; "live" means the Zustand live store.

### 7.1 Operator (`/`, everyone)

**Purpose:** the verdict, and on FAIL *where*, with nothing that distracts (FR-UI-1..5, NFR-USA-1/2).

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Tampa azul — etiqueta de lote  v8                       [◧ Marcações]        🔒 Entrar │
├──────────────────────────────────────────────────────────────┬───────────────────────────┤
│                                                              │            ✕              │
│                                                              │        REPROVADO          │
│                    IMAGEM (preenche a área)                  │   Tampa ausente (12% azul)│
│          contorno vermelho na região "tampa", ✕ tampa        │                           │
│          contorno verde nas outras, âncora tracejada         │   tampa      ✕   12%      │
│                                                              │   lote       ✓   L004211  │
│                                                              │   largura    ✓   29,1 mm  │
│                                                              │   14:32:07 · 310 ms       │
├──────────────────────────────────────────────────────────────┤───────────────────────────┤
│ ▢▢▢▢▢▢▢▢▢▢  últimas 10 (miniaturas com ✓ / ✕ / !)            │ Hoje 42 · 39 ✓ · 2 ✕ · 1 !│
│                                                              │ [Inspecionar] [Incorreto?]│
├──────────────────────────────────────────────────────────────┴───────────────────────────┤
│ ● Sistema  ● Câmera 30 fps  ● Máquina  ● Registro                          Aguardando peça│
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Changes from 0.1:**
- **The image fills its area.** No letterboxed empty frame; *fit* by default, *fill* as a station setting.
- **Per-tool lines** under the reason show each tool's verdict and measured value. Only the tools that affect the result are shown; at most 6 lines, with "+ 3 outras" beyond that.
- **Last results as thumbnails** instead of icons. Touching one freezes that result's image and overlay on the left for 10 s (or until *Voltar ao vivo*), so the operator can show a failure to someone.
- **Marcações toggle** (FR-UI-9, §18): shows or hides the overlays on the image. The station setting decides whether the operator may use it.
- **Verdict states** are as in 0.1:
  - *Aguardando*, *Inspecionando…*, *APROVADO*, *REPROVADO*, *ERRO*;
  - *Câmera desconectada*, *Falha na verificação*, *Em manutenção*, *Preparando…*;
  - *Conectando… / Sem conexão*, which never show a stale verdict as current.

  Plus **Teste de desafio pendente** (UC-14) and **Máquina sem sinal** (E601).

**Data:** live (status, frames, events), `GET /api/state` on connect, `POST /api/trigger`, `POST /api/results/{id}/incorrect`, `GET /api/results/{id}/thumb`.

**As built (VIA-0063).**
- **Tool lines:** `toolRows` lists the tools with `affects_result`, the failing ones first, at most 6 and then "+ N outras". The value is the measure of the criterion that decided the tool (the failing one, else the first with a measure), written by its unit: `fraction` as a percentage, `count` as an integer, `score` with two decimals. A yes/no rule has a line with no value.
- **Last results:** the status lists them with their `record_id`; each is a button with its picture (`/api/results/{id}/thumb?width=160`, open to everyone, a recorded picture never changes so the server keeps the last 64) and the outcome's icon over it. A result without a record has no picture and cannot be opened. Touching one shows its picture (width 1280) and its markings on the image for 10 s, under a bar with the time and *Voltar ao vivo*. A new result, a lost connection or the time ends it: an old picture is never taken for the present. The tool lines stay those of the verdict on screen.
- **Markings:** the contract carries each tool's `region` (fractions of the frame, set by the pipeline; `null` on records from before 0.3). The client draws them as vectors over the image, so turning them on and off asks for nothing: *Regiões* only (outline in the verdict colour with a dark edge; a failed region is thicker and crossed, an informative tool's is dashed). The other layers of §18 come with the editor's image workspace (UI-1). The station setting is `station.markings` (`always`, `on_fail` by default, `never`) and `station.operator_markings` (whether the button is shown), in *Configurações › Estação* and in the status; the button is a master switch the operator keeps until the page is closed. The full contract of a result looked at again is the one the live socket delivered (the last ten of this browser session); after a reload the picture and the verdict come back but not the markings or lines of results from before it.

**Accessibility:**
- The verdict is an `aria-live="assertive"` region and is announced as text.
- All targets are 56 px.
- Every verdict has an icon and a word.

### 7.2 Jobs (`/jobs`, `/jobs/:id`, supervisor+)

These are as built in 0.1 (list, versions, activate with verification, import, export, backup), with three additions:
- **Detail summary in the order of work (§4.3)**, with each step's state and a link straight to that step in the editor.
- **Per version:**
  - *Ajuste fino* (supervisor+, §7.12);
  - *Editar* (maintainer);
  - *Comparar com…*, showing the diff as **a list of changes in plain words**, not YAML. For example: "Ferramenta *tampa*: fração mínima 0,80 → 0,75". The YAML diff is available at the Especialista level.
- **Job number** for the machine (from system configuration, FR-INT-8), shown on the row and editable by the maintainer in *Configurações › Máquina*.

### 7.3 Job editor (`/jobs/:id/edit`, maintainer)

**Purpose:** build and tune a job while looking at the real image, in the order of §4.3 (UC-03, UC-13, FR-JOB-2/4/5, FR-PLT-*). This is the largest screen. Layout in §10.1; each step below says what its inspector holds and what it adds to the image.

**Common to every step:**
- the image workspace with its layer menu (§18);
- the filmstrip (reference, *Boa* and *Ruim* samples, *Ao vivo*);
- the **result bar**: last test verdict, per-tool chips, total time against the job's budget on this PC (FR-ADM-5).

The station is paused (*Em manutenção*) while the editor holds a camera session, and resumes when the editor is closed or idle.

**1 · Imagem e disparo**

| Level | Controls |
|---|---|
| Essencial | Exposure (`ExposureControl`: log slider in µs, with "Auto uma vez" that measures and then locks the value), focus (slider + `FocusMeter` with peak hold), white balance (eyedropper on a grey or white area: "Clique numa área cinza ou branca") |
| Avançado | Gain, resolution, frame rate, power-line frequency, zoom (motorized lens) |
| Especialista | Raw driver settings (read-only list with values), low-light compensation, pixel format |

**Image aids:**
- A live **histogram** with the percentage of clipped pixels at each end. It turns amber above 1 %: "2,4 % da imagem saturada".
- Optional **focus peaking** layer: edges tinted in `ov-select`.

*Aplicar na câmera* runs the existing apply + read-back and shows the per-setting report inline.

**Trigger** (the second half of the step, one `acquisition.trigger` block, TD-32):
- **Type:** a segmented control with a one-line explanation each (*Pela imagem*, *Pela máquina*, *Botão*, *Contínuo*); the same choice as the trigger control in the editor top bar. *Pela máquina* covers every external source (24 V input, S7, Modbus, OPC UA, local API): the source and the edge of the input are chosen once in *Configurações › Máquina*, not per job.
- **The parameters of the chosen type** (TD-31, TD-32):
  - *Pela máquina*: **Atraso após o sinal** (0–1000 ms, default 0, FR-TRG-6), with the frame it would take shown against the live image; **Filtro do sinal** (debounce, 0–65 ms, default 0, FR-TRG-8);
  - *Contínuo*: **Intervalo mínimo** (default 500 ms, FR-TRG-7);
  - *Pela imagem*: the presence area drawn on the image, the stillness time, and a live **"presença / movimento / parado há 0,6 s"** readout, so the maintainer sees the trigger decide.
- **Orientation** (FR-ACQ-10) is with the image controls; the parameters of *Auto uma vez* (target brightness, maximum exposure, measuring region, FR-ACQ-11) are in the exposure control at the Avançado level.
- **As built (VIA-0083).** *Auto uma vez* is a button under the exposure: `POST /api/camera/auto-exposure` pauses the station, searches the exposure (a bisection on its logarithm, one measure per step, about 20 s on the C920 because each step writes the camera and waits for it to settle), leaves the camera on the result and answers with the value, the share of saturated pixels it gives and every measure. The editor writes the value as a fixed exposure and keeps the parameters. If the target cannot be reached (the C920's steps jump from 0 % to about 20 % saturated, a longest exposure still short of it, a shortest one already over it) it says so and keeps the nearest step. The region is drawn on the image like the presence area. The *Essencial* level shows only the button.

**2 · Amostras**
- *Capturar referência*: freezes the current frame as the reference image. The reference is shown first in the filmstrip, with a star.
- *Capturar como Boa* / *Capturar como Ruim* (with an optional note: "sem fita", "aba aberta"). *Importar imagens* adds files.
- Each sample shows a thumbnail, its label and, after a test, ✓ or ✕ for whether the job agrees with the label.
- **Guidance:** "Recomendado: 10 boas e 1 ruim de cada defeito". Shown as a target count, never as a gate: activation is never blocked by missing samples. *Ajustar pelas amostras* needs at least 3 *Boa* and 1 *Ruim* (§16).
- The samples become the version's reference set (`tests/`, FR-JOB-9). The same images feed the gauges and the automatic tuning, so **what the job was tuned on is what it is verified on**.

**3 · Âncora**

The locator picker shows a card per type, each with a one-line use and a small diagram:
- *Sem âncora*: the part is always in the same place.
- *Contorno* (`shape`): finds the outline; tolerates rotation.
- *Modelo* (`template`): finds a picture; tolerates shift only.
- *Mancha de cor ou contraste* (`blob`).
- *Duas bordas* (`edges`).

Then:
- **Teach on the reference:** draw the model area (`TemplateCropper`) or the two calipers.
- **Search area:** drawn on the image.
- **Allowed range** (Essencial):
  - angle with `AngleRangeDial` (default ±15°);
  - shift as the search area;
  - scale range at Avançado.
- **Result on every sample:** a grid of thumbnails with the found pose drawn (`PoseMarker`) and the score. Not found is shown in amber with the reason.
- **Fixture chains** (FR-INS-12) at Avançado: *Adicionar âncora dentro desta*.

**4 · Ferramentas**

The inspector is split vertically (§10.1):
- **Tool list** on top (`ToolList`):
  - add with a catalog dialog: a card per type with what it measures, an icon and "Melhor para…";
  - drag to reorder;
  - enable / disable;
  - a live ✓ / ✕ chip per tool;
  - a warning icon when the tool does not separate the samples.
- **Selected tool** below, always in the same sections (§19.2):
  1. **Região:** draw on the image, relative to an anchor or the frame. The region list includes the anchors.
  2. **O que medir:** the tool's essential measurement settings, with their graphical control. For example, colour → `HsvRangePicker` with eyedropper; pattern → `TemplateCropper`; edge → caliper on the image + `ProfilePlot`; blob → threshold on a `Histogram`.
  3. **Critérios:** one `ToolToleranceGauge` per criterion (§19.3), with *Ajustar pelas amostras*.
  4. **Resultado:** decides the result or is informative only (FR-INS-13); the failure text with the available `{campos}` as clickable chips and a preview with the current values.
  5. **Avançado / Especialista:** collapsed sections with the remaining parameters (§17). A badge shows how many are changed from their defaults.

  Selecting a tool in the list or clicking its region on the image are the same action: both select the tool, and the image scrolls and zooms to its region if it is off-screen.

- **Separation indicator** per tool and for the job:
  - "Todas as boas passam · 3 de 4 ruins reprovam (falta *aba aberta*)", computed from the batch test;
  - shown again in step 7.

**5 · Qualidade**
- **Quality gates** (they come after the samples because they are proposed from them):
  - brightness range on the histogram;
  - sharpness ratio against the reference;
  - colour-reference patch (FR-INS-16);
  - each proposed from the samples: "valores das amostras ± 20 %".

**6 · Resultado e saídas**
- **Deciding tools:** a summary table, editable here or in each tool.
- **Operator texts:** waiting text and reason texts, each in pt-BR and en side by side (FR-JOB-15, §11.1).
- **Machine values:** pick up to 8 tool values (FR-INT-11), each with its unit. A preview of the interface map shows which `UserValue` each value lands in.
- The **job number** is shown read-only, with a link to *Configurações › Máquina*.

**7 · Validar**
- *Validar tudo* runs the draft on every sample. It shows a matrix of samples × tools (✓ / ✕ / value) and the outcome against the label. Mismatches come first.
- **Budget:** the time per stage against this PC's tier and the job's budget (FR-ADM-5).
- *Comparar com produção* runs the A/B replay (FR-JOB-12): "Esta versão teria reprovado 3 das últimas 500 peças aprovadas", with those images.
- *Verificação da câmera* (architecture §7.3, part 1) is shown here too, so nothing in the activation is a surprise.

**8 · Salvar e ativar**
- A summary of changes in plain words (as in §7.2) and the note (required).
- *Salvar* or *Salvar e ativar*. Activation runs the verification and shows the report (P4). The maintainer's override with a written reason is kept.

**Testar** (top bar, always available) runs the draft on the current frame, or on all samples with Shift. **Testar a cada captura** (toggle in the image toolbar; called *Captura contínua* before 17/10, renamed so it is not confused with the *Contínuo* trigger mode) runs it on every new frame through the editor session (§9.5), at the rate the PC allows (§19.1).

### 7.4 Results (`/results`, supervisor+)

As built in 0.1 (filters in the URL, CSV, side panel with original/marked image, mark incorrect). In 0.2:
- the side panel uses the same image workspace (zoom, layers, §18);
- it lists per-tool values with their tolerance gauges, frozen at that result;
- a filter by **reason code** (FR-INS-14).

### 7.5 Dataset and collection (`/dataset`, maintainer)

As built in 0.1, plus the image grid preview with labels (lazy, virtualized).

### 7.6 Settings (`/settings/*`, maintainer)

The page is split into sub-pages, each with the same layout as the editor's inspector (sections, levels):

| Sub-page | Content |
|---|---|
| **Estação** | Name, **station language (pt-BR / en)**, shift starts, idle timeout, audible alert, **Marcações on the operator screen** (§18: sempre / só em reprovação / nunca; the operator may toggle: sim/não), operator image fit/fill |
| **Câmera** | Driver and device (picked from a list with names and a live thumbnail), *Testar câmera*, connection details |
| **Armazenamento** | Backup folder and schedule, recording limits, data folder |
| **Rede** | Listening address and port, with the security warning |
| **Máquina** | Enabled adapters (S7, Modbus TCP server, remote I/O, OPC UA), addresses, interface map version, cycle, heartbeat, acknowledge mode, buffer depth, **job numbers** and **products** (tables), allowed client IPs |
| **Desempenho** | Last benchmark report (tier M/R, per-stage times), *Rodar teste de desempenho*, editor live-feedback rate (§19.1) |

Fields that need a restart are marked one by one. Saving shows what changed and asks to confirm.

### 7.7 Access (`/access`, supervisor+)

Unchanged.

### 7.8 Audit (`/audit`, supervisor+)

As in 0.1, with three new event kinds:
- *ajuste fino* (§7.12);
- *troca de job pela máquina*;
- *saída forçada* (§7.14).

### 7.9 About (`/about`, supervisor+)

As in 0.1, plus the benchmark summary and the tier.

### 7.10 Login and errors

Unchanged.

### 7.11 Commissioning (`/setup`, maintainer) — new

**Purpose:** take a fresh installation to its first job in the right order (FR-ADM-8).

**When it opens:** automatically after the first login when the system has no camera or no job. Later it is reachable from *Configurações*.

A full-page stepper (the 0.1 `Stepper`), each step with a clear *done* condition:

| # | Step | Done when |
|---|---|---|
| 1 | **Câmera:** pick the device from the list (thumbnail for each), test, see the live image | Frames arriving |
| 2 | **Desempenho:** run the benchmark (about a minute); shows the tier and what it means ("Este PC roda trabalhos clássicos; modelos grandes podem ficar lentos") | Report stored |
| 3 | **Senhas:** set the supervisor and maintainer passwords | Both set |
| 4 | **Máquina** (optional): choose the adapter or *Sem máquina*, enter addresses, test the connection with a heartbeat | Connected or skipped |
| 5 | **Backup:** choose the folder, *Testar pasta* | Tested |
| 6 | **Primeiro job:** opens the editor at step 1 | — |

### 7.12 Fine-tune (`/jobs/:id/tune`, supervisor+) — new

**Purpose:** let the supervisor adjust **tolerances only** when the product or the light drifts, without the maintainer (FR-JOB-14).

```
┌ Ajuste fino — Tampa azul v8 ─────────────────────────────────── [Descartar] [Salvar como v9…] ┐
│  IMAGEM (ao vivo ou amostra), marcações                  │ tampa      ✓  fração azul           │
│                                                          │   ├──────[████████▌····]──┤  0,92   │
│                                                          │   mín 0,80   ● boas  ✕ ruins        │
│                                                          │ largura    ✓  29,1 mm               │
│                                                          │   ├──[···████████···]──┤  28,0–30,5 │
├──────────────────────────────────────────────────────────┤ lote       ✓  (sem tolerância)      │
│ filmstrip: amostras ✓ / ✕                                │                                      │
└──────────────────────────────────────────────────────────┴──────────────────────────────────────┘
```

- **Shows:** every tool that affects the result, with only its **Essencial-level criteria** as gauges. The live needle and sample dots are shown, plus *Ajustar pelas amostras*. The supervisor can capture new samples (*Boa*, *Ruim*) for the gauges.
- **Does not show:**
  - regions;
  - the camera;
  - locators;
  - adding, removing or reordering tools;
  - measurement settings (such as the colour range itself);
  - Avançado and Especialista.

  The server enforces the same: a fine-tune save is refused if anything other than the allowed tolerance parameters changed.
- **Save:** a note is required. Saving creates version n+1, marked *ajuste fino*, then runs verification. The supervisor may activate it if verification passes; an override stays maintainer-only. The audit log records every changed value.

### 7.13 Statistics (`/stats`, supervisor+) — new

**Purpose:** see drift before it becomes rejects (FR-LOG-7).

Per job version, three views:
- **Pareto of reason codes** (bar chart, shadcn `Chart`).
- **Per-tool margin trend:** line chart with the warning limit as a reference line, built from the score monitor.
- **Value distribution against the limits:** histogram, PASS vs FAIL, with the tolerance band.
- **Disparos recusados:** count per shift and day (FR-INT-14), next to the inspection count; a rise points at a machine that triggers too early or too fast.
- **Aprovadas com pouca margem:** the low-margin PASS images kept by FR-LOG-9, one click from each margin warning.

Time range filter in one row above the charts. Every chart has a table view.

Each margin warning links to *Ajuste fino* (supervisor) or the editor (maintainer) for that tool.

### 7.14 Machine monitor (`/machine`, maintainer) — new

**Purpose:** commission and debug the machine interface (FR-ADM-7).

- A live table of the interface map (architecture §16.2): inputs and outputs with value, last change time and a sparkline of the last 30 s for bits. Heartbeat ages and last errors.
- **Forçar saídas:** only while the station is *Em manutenção*. Each forced value is shown in amber with *forçado*. Leaving the page releases every force. Everything is logged.
- *Simular gatilho*: sends a machine trigger to test the handshake end to end. The result is marked simulated and not signalled.
- **Remote I/O outputs** (architecture §16.7): each line with its function, polarity and live state; the **reject queue** with the pending entries (sequence, outcome, inspections or ms left).
- In *Configurações › Máquina* each remote I/O line gets a function, a polarity (*normal* / *invertida*) and, for *rejeito*, the results, the delay (*em peças* or *em ms*) and the pulse.

---

## 8. Access control in the interface

| Capability | Operator | Supervisor | Maintainer |
|---|---|---|---|
| See state, live image, results of the day; toggle overlays (if the station allows) | ✔ | ✔ | ✔ |
| Manual trigger, mark a result wrong | ✔ | ✔ | ✔ |
| Jobs: list, activate (verified), export, import, backup | | ✔ | ✔ |
| **Fine-tune tolerances (new version, verified, audited)** | | ✔ | ✔ |
| Results history, statistics, images, CSV | | ✔ | ✔ |
| Audit, About | | ✔ | ✔ |
| Activate despite failed verification (with reason) | | | ✔ |
| Commissioning, editor, camera, tools, anchors | | | ✔ |
| Machine monitor, forced outputs | | | ✔ |
| Dataset and collection mode | | | ✔ |
| Settings, access, pause/resume/retry | | | ✔ |

- **Settings levels are not permissions** (§17). A level changes what is shown, never what is allowed.
- The router hides entries and blocks routes by role. **The server enforces the same table on every endpoint**, including the parameter allow-list of a fine-tune save.
- Token handling, session length, lock-out and idle timeout are as in 0.1.

---

## 9. API contract the interface needs

### 9.1 Conventions

Unchanged from 0.1:
- the `/api` prefix and fallback to `index.html`;
- the contract generated from Pydantic models and checked in CI;
- the error shape `{detail, code, fields}`;
- pagination and ISO time.

New in 0.3:
- **Language:** every request carries `Accept-Language` (`pt-BR` or `en`); texts the server returns (messages, error-code texts, tool labels, reports) come in that language. Codes, never texts, are what clients act on.

### 9.2 Existing endpoints

As listed in 0.1 §9.2–9.3 (all implemented in VIA-0025/0026).

### 9.3 Tool metadata for the vision controls (new)

`GET /api/tools` already returns each tool's and locator's JSON Schema. Version 0.2 adds metadata to each property, written in the tool's Pydantic model (`json_schema_extra`), so the screen still needs no per-tool code (FR-PLT-2):

| Key | Meaning | Example |
|---|---|---|
| `x-group` | Inspector section | `measure`, `criteria`, `result` |
| `x-level` | 1 Essencial, 2 Avançado, 3 Especialista | `min_fraction: 1`, `line_min: 2`, `work_width: 3` |
| `x-widget` | Graphical control from the registry (§19.2) | `hsv-range`, `template`, `caliper`, `angle-range`, `code-formats`, `regex`, `region` |
| `x-unit` | What the number is, and how it is shown | `fraction`, `count`, `score`, `px`, `ΔE` |
| `x-tunable` | May be changed in fine-tune (§7.12) | `true` for limits only |

**As built (VIA-0062).** The tags are written next to the labels, in `core/schema_labels.py` (`meta(level, group, widget=, unit=, tunable=)`, given to `labels(meta={...})`), so a parameter has one place. `x-group` is `measure` (how the part is measured) or `criteria` (the limits it is judged by). `x-unit` uses the result contract's units (`fraction`, `count`, `score`, TD-22), plus `px` and `ΔE`: a `fraction` is a number from 0 to 1 that the screen writes as a percentage (`30%` is stored as 0.3; typing `35` gives 0.35), `px` and `ΔE` are a suffix, `count` and `score` are plain numbers. Stored values never change with the display. `x-tunable` is on the limits of a *tool* only: a locator's thresholds decide where the object is, not whether it is good. `hue` carries `x-widget: hsv-range` for the whole range (its saturation and value limits belong to the same picker). A test (`tests/test_schema_meta.py`) fails when a parameter of any tool or locator, including a nested color range, has no level or group.

Plus, per tool type, a **`criteria`** list that tells the gauge what to draw:
- the measured value's name;
- its range and unit;
- the parameter(s) that hold its limit(s);
- the direction (`at_least`, `at_most`, `between`).

Example (as `GET /api/tools` returns it, in each tool's `criteria`; a locator's is empty):

```json
{"value": "fraction", "label": "Fração com a cor", "unit": "fraction", "range": [0, 1],
 "limits": {"min": "min_fraction", "max": "max_fraction"}, "direction": "between", "level": 1}
```

`value` is a key of the result's values (`tests/test_schema_meta.py` checks it against what the tool reports). `range` is `[0, null]` for a count, which has no natural top: the gauge takes it from the data. A yes/no rule (a class that fails, a class that is missing) has no gauge and is not listed.

### 9.4 New endpoints

| Endpoint | Purpose | Role |
|---|---|---|
| `POST /api/editor/batch` | Run a draft on its samples; per sample and tool: passed, score, measured values (feeds gauge dots, separation, Validar) | maintainer, supervisor (fine-tune) |
| `POST /api/editor/suggest/color` | Sampled pixels (a drawn area or clicked points, with *incluir/excluir*) → proposed HSV range (percentiles), and how much of the region it covers | maintainer |
| `POST /api/editor/suggest/limits` | Per criterion: the values on *Boa* and *Ruim* samples → proposed limit in the middle of the widest gap, with the resulting margin, or "as amostras se sobrepõem" | maintainer, supervisor |
| `POST /api/editor/locate` | Teach and run a locator on the reference and all samples → pose and score per sample | maintainer |
| `GET /api/editor/debug/{layer}.png` | Debug image of the last live or sample result: colour mask, binarized blob image, edge map, anomaly map, for one tool | maintainer |
| `POST /api/jobs/{id}/versions/{v}/tune` | Fine-tune save: refuses any change outside `x-tunable` parameters | supervisor+ |
| `GET /api/machine/map`, `POST /api/machine/force`, `POST /api/machine/simulate-trigger` | Machine monitor (§7.14) | maintainer |
| `POST /api/bench`, `GET /api/bench/last` | Benchmark (FR-ADM-5) | maintainer |
| `GET /api/results/{id}/thumb` | Thumbnail for the operator's last results | everyone |

### 9.5 Editor session (new, WebSocket `/api/editor/live`)

The live feedback of §19.1. The client opens the session with the draft, then sends **patches** (only what changed: a limit, a region). On each new camera frame, at no more than the session rate, the server:
1. runs the draft through the same pipeline as the station;
2. sends a JSON message with the verdict, per-tool values, scores and margins, fixture poses, stage timings and the frame id;
3. sends a binary JPEG with the frame (the overlay is drawn by the client from the JSON, so toggling layers needs no new request).

The station stays paused while a session is open. Closing the session (or 10 min without messages) resumes it.

**As built (VIA-0065).**
- **Greeting.** A browser cannot put a token in the headers of a WebSocket, so the first message is `{type: hello, token, fps?}`. A token that is not a Maintainer's gets `{type: error, code: login_required}`; a second session gets `session_busy`; neither leaves the socket as a surprise. The origin is checked like `/api/live`.
- **Draft.** `{type: draft, job, profile}` at each change, after a pause of 120 ms in the client; the files (`base`, `add_files`, `remove_files`, megabytes of samples) go **once per connection**, and again only when the set of files changes. The server keeps the files between messages, so dragging a limit does not send or decode them again. Messages are whole `job` and `profile`, not patches of fields: the cost is in the files, not in them.
- **Answers.** `draft_ok`; `draft_error` with `message` and `fields` (the same paths as a refused save); `camera` with `connected`; `result` (the `DraftTestOut` fields: `result`, `regions`, `anchor`, `tools`, `timings`, `width`, `height`, plus `frame_id`) followed by one binary message, the JPEG of that frame; `run_error` when the draft cannot run on a picture; `idle` when 10 minutes pass with no message. A refused draft, a lost camera and a busy session are messages, never a closed socket.
- **Rate.** At most `editor_fps` runs per second (`ApiDeps`, default 4), never queued: the next run takes the newest frame when the last one is over. The client may ask for fewer (`fps`, `{type: rate}`).
- **Pause.** The session pauses the station on opening **only if it was running**, and resumes it on closing only then, so a pause that *Aplicar*, *Auto uma vez* or the person had made stays. A pause is taken only from some states (an inspection in progress ends first), so it is asked again until it holds, for up to 3 s. A station that is not running (Fault, CameraLost, Starting) is left alone and so is its end: closing the editor never clears a fault, *Tentar de novo* is the person's. `ready` says whether the pause is the session's (`paused_by_session`) and in which `station` state it found the station. It resumes in `finally`: on a disconnect, an error or an idle end. While the pause is the session's, the banner of the editor says so and offers no *Retomar*.
- **Editor.** The page opens the session when it opens and shows `Ao vivo ● 3,8/s` (the measured rate), or the reason it is not live. When the image shown is the camera's, the pictures come from the session instead of `/api/snapshot.jpg`, and its regions and the needles of the gauges are the live measurement; on the reference or a sample the last *Testar* is what there is. The result bar and the filmstrip (UI-1) are not part of this task.

### 9.6 Live socket (`/api/live`)

As in 0.1, plus `machine` status messages (connected, heartbeat age) for the status strip.

The state message carries `machine` only while a machine connector is enabled (absent or `null` otherwise): `{ "connected": bool, "heartbeat_age_s": number | null, "last_error": string | null }`. `connected` is the adapter link; `heartbeat_age_s` is the age of the last HeartbeatIn toggle (architecture §16), `null` while none has been seen. The strip shows *conectada* only with `connected` true **and** a heartbeat seen; `connected` without a heartbeat is *aguardando sinal de vida* (unknown); anything else is *sem sinal* (fail, with `last_error`, e.g. E601). The core does not send it yet (R3).

---

## 10. Image workspace and region editor

### 10.1 The workbench layout (editor, fine-tune, camera)

At **1920×1080**:

```
┌ Job · v8 · [Disparo: Pela imagem ● parada 0,6 s ▾] ─ [Nível ▾] ─ [▶ Testar] [Salvar…] ─ (LS ▾) ┐
│ ① Imagem/disp ✓│ ● Ao vivo                       [◧ Marcações · 5/5 ▾]│ Ferramentas            │
│ ② Amostras   ✓ │                                                      │ ┌────────────────────┐ │
│ ③ Âncora     ✓ │                  IMAGEM                              │ │ ⠿ tampa    ✓ cor   │ │
│ ④ Ferramentas ●│          zoom / pan, camadas, réguas                 │ │ ⠿ lote     ✓ código│ │
│ ⑤ Qualidade    │                                                      │ │ ⠿ largura  ✕ borda │ │
│ ⑥ Resultado    │                                                      │ └────────────────────┘ │
│ ⑦ Validar    ! │                                                      │ largura · borda        │
│ ⑧ Salvar       │                                                      │ ▸ Região               │
│                │                                                      │ ▾ O que medir          │
│                │                                                      │ ▾ Critérios  [régua]   │
│                │                                                      │ ▸ Resultado            │
│ [Próximo ▸]    ├──────────────────────────────────────────────────────┤ ▸ Avançado (2)         │
│                │ ★ ref │ ✓ ✓ ✓ ✓ ✓ │ ✕ ✕ │ ● Ao vivo   [+ Boa] [+ Ruim]│                        │
├────────────────┴──────────────────────────────────────────────────────┴────────────────────────┤
│ ✕ REPROVADO · Largura fora do limite (31,2 mm) · ✕ largura ✓ tampa ✓ lote · 182 ms · ● 4/s     │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Panel sizes:**
- step rail 200 px;
- image at least 50 % of the width;
- inspector 400–520 px, resizable and remembered per user;
- filmstrip 96 px high, collapsible;
- result bar 40 px.

**At 1366×768:**
- the step rail collapses to numbered icons with tooltips;
- the filmstrip collapses to a button that opens it as a drawer;
- the inspector keeps 360 px.

The image never drops below 60 % of the height.

**Keyboard:**
- F6 cycles the panels;
- `[` / `]` previous / next step;
- `Ctrl+K` opens the command palette;
- Space + drag pans;
- `Ctrl+0` fits the image;
- `1` shows the image at 100 %.

### 10.2 Image workspace

- **Rendering:** frame on `<canvas>` (ImageBitmap); shapes, poses, measurements and labels on an **SVG overlay**; masks and debug images as a second canvas layer with opacity.
- **Zoom and pan:**
  - wheel zoom up to 16× around the pointer;
  - pan with Space+drag or two fingers;
  - a mini-map appears above 2×;
  - pixel grid above 8×.
- **Readouts** under the pointer:
  - x, y in pixels and in the anchor's coordinates;
  - RGB and HSV of the pixel;
  - mm when the job is calibrated.
- **Layers** (§18): a menu with a switch per layer and a master switch.
- **Frozen vs live:**
  - a badge says what is shown: *Ao vivo*, *Referência*, *Amostra 4 (Ruim: sem fita)*, or *Resultado 14:32:07*;
  - live frames never replace a frozen image without the user asking.

### 10.3 Shapes and editing

These are as in 0.1:
- normalized geometry;
- draw, move, eight handles;
- keyboard nudge;
- undo/redo;
- snapping (Alt disables);
- focusable SVG groups with accessible names.

New in 0.2:
- **Rotated regions on anchored jobs.** Regions are drawn in the anchor's axes. When the anchor is found turned, the regions turn with it on screen, exactly as the pipeline cuts them (architecture §14.3).
- **Shape per widget:**
  - rectangle (regions, presence area, search area);
  - line or arc with width (calipers for `edge` and `edges`);
  - crop (templates).
- **Region selection follows the tool**, in both directions: selecting a tool selects its region on the image, and clicking a region selects its tool.

---

## 11. Languages and copy

### 11.1 Two languages (TD-30)

The interface is available in **Portuguese (pt-BR)** and **English (en)**. Portuguese is the source language: every message is written in pt-BR in the code and translated in the English catalog.

| What | Language rule |
|---|---|
| **Operator screen** | The **station language** (`system.yaml`, *Configurações › Estação*). The operator has no login, so the station decides |
| **Admin screens** | The user's choice (user menu, login dialog), remembered per browser; default: the station language |
| **Interface texts** | Lingui catalogs `pt-BR` and `en`; a missing English translation fails the build |
| **Texts from the server** (state messages, error-code texts of architecture §10.3, tool and locator labels and descriptions, verification reports) | Catalogs on the server (PO files, gettext/Babel), chosen by the request's `Accept-Language`; codes stay the contract, texts are rendered in the viewer's language |
| **Texts written in a job** (`reason_fail`, `ui.waiting`, sample notes) | **Both languages in the job** (job format 2, FR-JOB-15): the editor shows a pt-BR and an en field side by side; an empty translation falls back to the other language, marked in *Validar*. Format-1 jobs: the existing text is pt-BR |
| **Numbers, dates, units** | Formatted by locale (`Intl`, React Aria): `1.234,5` and `16/10/2026` in pt-BR, `1,234.5` and `10/16/2026` in en. Number fields accept the locale's decimal separator |
| **Records, CSV, audit** | Store codes and values, and the reason in the station language of the time (decision of Lucas, 2026-10-18). Listing results shows a standard text (one of the server catalog) in the language of the viewer; a text with details (a camera's own error, a file name) and a job's own `reason_fail` keep the form in which they were recorded. CSV exports carry the reason as recorded: the viewer's language (and saying which) is **not done yet** |
| **Guides** (`docs/guias/`) | Portuguese first; English versions when a project needs them |

How it is built (UI-C2, VIA-0060): `app/locale.tsx` is the one source of the language. It loads the catalog of the language on screen (each catalog is a chunk of its own), activates Lingui and React Aria, sets `<html lang>`, and mounts the pages again when the language changes (the query cache is invalidated, so the texts that came from the server are asked for again in the new language; the live socket is opened again at once with the new `?lang=`). The station language is `station.language` in `system.yaml` and `language` in the state message; a page opens in the last station language seen, so the kiosk does not flash Portuguese. A person's choice (user menu, login dialog) is kept in this browser and applies while logged in; logging out returns to the station's.

### 11.2 Voice

Short, plain, active, numbers and units instead of adjectives, no blame, no exclamation marks, in both languages. The English text is written for an operator, not translated word by word ("Tampa ausente" → "Cap missing", not "Absent cap").

### 11.3 Glossary

One concept, one word, in each language. The glossary of 0.1 is kept; additions in 0.2–0.3:

| pt-BR | en | Not | Meaning |
|---|---|---|---|
| Âncora | Anchor | fixture, referencial | What a locator finds; regions follow it (architecture §14). Several anchors are allowed |
| Amostras · Boa / Ruim | Samples · Good / Bad | OK/NG, golden, master set | The images a job learns from and is checked on (the reference set) |
| Imagem de referência | Reference image | golden, master | The one good image taken first |
| Critério · Tolerância · Limite | Criterion · Tolerance · Limit | threshold, setpoint | What a tool checks · the allowed band · each end of the band |
| Margem | Margin | slack, headroom | How far a passing value is from its limit |
| Ajustar pelas amostras | Set from samples | auto tune, teach | Propose limits from Good/Bad samples |
| Marcações | Overlays | graphics | What is drawn on the image |
| Nível: Essencial / Avançado / Especialista | Level: Essential / Advanced / Expert | básico / pro | Settings levels (§17) |
| Ajuste fino | Fine-tune | recalibração | The supervisor's tolerance-only edit |
| Em produção / Em manutenção | In production / In maintenance | online / offline | Whether the station is inspecting |
| Comissionamento | Commissioning | setup, instalação | The first-start wizard |
| Aprovado / Reprovado / Erro | Pass / Fail / Error | OK / NOK | The three outcomes |

The 0.1 editor showed tool descriptions from the server in English only ("Code tool: reads 1D bar codes…"). From 0.3, every label and description shown to users comes from the server's catalogs in the viewer's language. A test fails if a tool or locator property lacks a label in either language.

---

## 12. Accessibility, kiosk and touch

Unchanged from 0.1: WCAG 2.2 AA, focus visible, targets ≥ 24 px (admin) and 56 px (kiosk), keyboard for everything including the image workspace, reduced motion, colour schemes, landmarks, live regions; kiosk behaviour; touch without hover-only functions; status always with icon and word.

New in 0.2:
- **Gauges and sliders:**
  - each is a React Aria slider underneath, with `aria-valuetext` in words (in the interface language) ("Limite mínimo 80 %; valor atual 92 %; 12 de 12 boas acima");
  - arrows step by the parameter's step, Shift by ten steps.
- **Colour controls** never rely on colour perception alone:
  - the HSV picker shows numbers on every handle;
  - the mask preview has a hatched fill, not only a tint.
- **Overlays:** the fail outline is thicker and tagged ✕ (§6.1). With the overlays off, the per-tool list on the operator screen still says which tool failed.

---

## 13. Testing and quality gates

The levels of 0.1 are kept: unit, component, contract, end to end, accessibility, tokens, budget, lint. Changes in 0.2:

| Level | What changes |
|---|---|
| Unit | Gauge geometry (value ↔ position, limits, proposals), HSV range math including red wrap-around, level filtering (hidden-but-changed count), schema metadata mapping to sections and widgets |
| Component | Each vision component (§19) in the `/design` gallery with fixtures: live value inside/outside, overlapping samples, no samples, wrap-around hue, rotated anchor; SchemaForm v2 against every registered tool's schema |
| Contract | Every tool and locator schema has `x-group`, `x-level` and labels in pt-BR and en; every `criteria` entry names existing parameters |
| Languages | Lingui extraction in CI: no message without an English translation; the operator e2e runs in both station languages; numbers typed with `,` and `.` per locale |
| End to end | The full sequence on the simulated station: new job → image → samples (3 Boa, 1 Ruim) → anchor → colour tool with eyedropper → *Ajustar pelas amostras* → Validar → save and activate; fine-tune as supervisor (and refusal of a non-tolerance change); overlay toggle on the operator screen; 1366×768 run of the editor |
| Tokens | As in 0.1; the overlay tokens are added to the contrast and design-rule tests |
| Budget | Operator route ≤ 160 KB gzip JS (0.1 limit 150 KB + 10 KB for the i18n runtime and one compiled catalog; the other language is loaded on demand); editor, statistics and charts are lazy routes |

**Definition of done for a screen** (as in 0.1, plus):
- every vision control on it works with the live session and with frozen samples;
- it is checked at 1920×1080 and 1366×768.

---

## 14. Build, serving and CI

Unchanged from 0.1, plus:
- `lingui extract` runs in CI and fails if a message is missing in `en`; `@lingui/vite-plugin` compiles the catalogs at build.
- The server's PO catalog ships in the Python package (read with Babel, no compile step) and is checked the same way by `tests/test_server_texts.py`.

---

## 15. Current state and migration plan

### 15.1 What exists (built in 0.1)

Operator screen, jobs, editor (7 steps, regions, SchemaForm, test), results, dataset, settings, access, audit, about, login, `/design` gallery. All of it is on shadcn/ui + Radix + Tailwind, with tests (Vitest, Playwright, axe) and the token and design-rule tests (tasks VIA-0022, VIA-0027, VIA-0028, VIA-0031..0034).

### 15.2 Additions to the foundation (TD-29, TD-30)

No migration: the 0.1 foundation stays and grows. Each step keeps every test green.

| Step | Content | Exit |
|---|---|---|
| UI-C0 | Add React Aria Components; `Slider` (multi-thumb) and `NumberField` replace `SliderField` and `NumberInput`; `ColorArea` / `ColorSlider` / `ColorField` wrappers; all in `/design` with every state | Component and axe tests green |
| UI-C1 | Add shadcn `Sidebar`, `Resizable`, `Command`, `Accordion`, `Drawer`, `Chart`; `@dnd-kit/core` + `sortable`; shell moves to `Sidebar` with the four areas and the Máquina indicator | Shell e2e and roles green |
| UI-C2 | i18n: Lingui set up, `texts.ts` moved into `pt-BR` messages, `en` catalog written, `LanguageSwitch`, station language on the operator screen, locale-aware formatting | Both catalogs complete; operator e2e green in both languages |
| UI-C3 | Server i18n: PO catalog for state messages, error-code texts, tool and locator labels, verification reports, error answers; `Accept-Language` and `?lang=` on the socket; job format 2 texts in both languages (with R1) | Contract test: every text in both languages. **Done (VIA-0061)** except the job texts, which wait for R1 |

### 15.3 The new interface (alongside the additions)

| Step | Content | Depends on (architecture §18) |
|---|---|---|
| UI-1 | Workbench layout (§10.1), image workspace v2 (zoom, layers, frozen/live), filmstrip, result bar | UI-C1 |
| UI-2 | The sequence: step rail with states, steps reordered (§4.3), samples step, *Validar* | UI-1. **Done (VIA-0064)** on the current layout; the image workspace v2 (UI-1) and the filmstrip are not part of it |
| UI-3 | Schema metadata (`x-group`, `x-level`, `x-widget`, `criteria`) on the server; SchemaForm v2; levels (§17) | — (server: small). **Done (VIA-0062)**: the widget components themselves come with the steps that need them (UI-4, UI-5) |
| UI-4 | Editor session (`/api/editor/live`) and batch test; `ToolToleranceGauge`; *Ajustar pelas amostras* | R2 (result contract) for per-tool values. **Done (VIA-0065)** except the result bar, the filmstrip and the frozen-image states of §19.1 beyond *Sem amostras* and *Câmera perdida*, which belong to UI-1 |
| UI-5 | Colour controls (`HsvRangePicker`, eyedropper, mask preview), camera controls (histogram, focus meter, exposure) | UI-4 |
| UI-6 | Anchor step with pose, angle range and per-sample results | R1 (pose-based fixtures) |
| UI-7 | Fine-tune screen (§7.12) and the server's allow-list | UI-4 |
| UI-8 | Commissioning wizard, machine monitor, statistics | R3, R6 |
| UI-9 | Controls for the new tools as they arrive (`ProfilePlot` for edge, threshold histogram for blob, `TemplateCropper` for pattern v2) | R5 |

### 15.4 Mapping of 0.1 sections to 0.2

Sections 1–16 keep their numbers. §11 was "Language and copy" (pt-BR only) and is now "Languages and copy". Within §7, the subsections 7.1–7.10 keep their meaning. §4.3 (order of work), §4.4 (breadboard), §7.11–7.14, §9.3–9.5 and §17–19 are new. §10 was "Region editor" and is now "Image workspace and region editor"; its 0.1 content is §10.3.

---

## 16. Open questions

From 0.1, still open:
1. **Shift counters:** when do they reset?
2. **Audible alert:** is it wanted?
3. **Branding:** client logo or colours?
4. **Station monitor:** size and touch.
5. **Idle timeout** length.
6. **Network access:** will the interface be used from other PCs?
7. **Operator correction:** without a PIN?

Answered in 0.2 and 0.3:
- Who edits jobs: the maintainer, plus the supervisor for tolerances only (§7.12).
- Minimum screen: 1366×768.

- Overlays on the operator screen (owner, 17/10): *sempre* by default, and the operator may toggle them; the station setting can change both (§18).
- Live feedback rate in the editor (owner, 17/10): up to 2 runs per second on tier M and 5 on tier R, changeable in *Configurações › Desempenho* (§19.1).
- Samples (owner, 17/10): recommended, never required for activation. *Ajustar pelas amostras* needs at least 3 *Boa* and 1 *Ruim*; the target shown is 10 *Boa* and 1 *Ruim* per known defect; *Validar* shows the gap (§7.3, §19.1).
- Fine-tune and activation (owner, 17/10): the supervisor may activate a fine-tuned version once verification passes, with the audit record; an override after a failed verification stays maintainer-only (§7.12).

---

## 17. Settings levels (new in 0.2)

Three levels, chosen in the top bar (`LevelSwitch`, FR-UI-10):

| Level | Shows | For |
|---|---|---|
| **Essencial** | What decides most jobs: the region, the main measurement, the tolerances. Typically 3–6 fields per tool | Building a normal job; fine-tune |
| **Avançado** | Adds secondary measurement settings (morphology, line coverage, scale range, anchor chains, quality gate details) | Difficult parts, tuning robustness |
| **Especialista** | Adds performance and internal settings (work widths, decoder options, raw camera settings), the job's YAML view and diff | Diagnosis, the developer |

**Rules:**
- **A level is a view, not a permission.** The maintainer can switch freely. The level is remembered per user and per screen family (editor, settings). The supervisor's fine-tune screen is always Essencial.
- **Every parameter has a level** in its schema (`x-level`, §9.3). A parameter without one is treated as Especialista, so a forgotten tag hides a field rather than cluttering the screen.
- **Hidden is never invisible.** When a section hides parameters that differ from their defaults:
  - the section shows a badge ("2 ajustes avançados alterados");
  - the badge opens just those fields, even at the current level.

  Testing with a hidden parameter changed is allowed; the result bar shows the same badge.
- **As built (VIA-0062).** `SchemaForm` takes the level (`level`, 1–3; every parameter when it is not given). At the top it draws two sections, *O que medir* and *Critérios*, with the Essencial parameters; the Avançado and Especialista ones follow in collapsed sections, each only once the level reaches it. The badge counts the hidden parameters whose value differs from the schema default (a value present where the schema has no default counts), and opens just those. A nested object (the color range inside the blob locator) is drawn whole. The level is chosen in the editor's top bar (`LevelSwitch`), kept in this browser per role and per family (`editor`, `settings`), and starts at Essencial. The badge on the result bar and the fine-tune screen's fixed Essencial come with the screens that have them (UI-2, UI-7).
- **Levels never change values.** Switching level changes no value, never resets anything, and never adds a version.
- **The same levels** apply to the camera step, the anchor step, the quality gates and the settings sub-pages.

---

## 18. Image overlays — *Marcações* (new in 0.2)

FR-UI-9. Overlays are drawn by the client from the result contract (architecture §10.3), never burned into the image. They can therefore be turned on and off without a new request.

**Layers:**

| Layer | Shows | Editor default | Operator default |
|---|---|---|---|
| Regiões | Each tool's region, in its tool's verdict style (§6.1); not-yet-tested regions in `ov-neutral` | on | on |
| Âncoras | Found anchors: outline, axes and angle (`PoseMarker`); search areas at Avançado | on | on (outline only) |
| Medições | What each tool measured: matches, edges and widths, blobs, codes with their text, defect areas | on | on FAIL only |
| Rótulos | Tool names and values next to their regions | on | off |
| Máscara | The selected tool's mask or debug image (§19.4) | off (on while a colour or threshold control has focus) | never |
| Área de presença | The trigger area and its live state | step 1 only | off |
| Grade e réguas | Pixel grid (zoom ≥ 8×), rulers in px or mm | off | never |

**Controls:**
- In the editor, one **split button** above the image (`◧ Marcações · 4/5` and `▾`): the button toggles the master switch, the arrow opens the **layer menu** with *Todas as marcações* and one check per layer (with what it shows, in a few words). The shortcut `M` toggles the master switch. The layers are never a row of buttons on the image bar (prototype review of 17/10).
- On the operator screen there is one **Marcações** button that toggles the master switch.
- *Configurações › Estação* sets:
  - the default: *sempre* / *só em reprovação* / *nunca*;
  - whether the operator may toggle.

**Rule:** turning overlays off **never hides the verdict or the reason**. With overlays off, the operator screen still lists the failing tools by name (§7.1).

---

## 19. Vision controls (new in 0.2)

The components that make the interface a vision system. All live in `components/vision/`, are built on React Aria (Slider, NumberField, ColorArea, ColorSlider) and the shadcn primitives (Popover, SegmentedControl, Accordion) plus canvas or SVG, and have every state in the `/design` gallery.

### 19.1 Live feedback (FR-UI-12)

Every control that changes a measurement shows its effect on the **next capture**:
- a gauge's needle;
- the mask;
- the overlay;
- the result bar.

Feedback comes from the editor session (§9.5). The **rate** is set by the benchmark tier, and changeable in *Configurações › Desempenho*:
- tier R: up to 5 runs per second;
- tier M: up to 2.

A small indicator in the result bar ("Captura ● 4/s") shows the real rate. A slow run is never queued behind a newer one: the newest settings win.

On a frozen image (reference or a sample), the run happens once per change, on that image.

**States of the workspace.** The editor screens are designed for these states as well as the normal one (prototype review of 17/10):

| State | Image | Gauge and tool list | Result bar | Way out |
|---|---|---|---|---|
| **Carregando** | skeleton over the image, "Carregando a imagem e medindo as amostras…" | no needle, no dots; chips *…* | *Medindo…* (busy) | — |
| **Sem amostras** | normal | reference dot only; "only the reference was measured…" in place of the margin; *Ajustar pelas amostras* disabled; filmstrip shows *Nenhuma amostra ainda* with the minimum to propose limits (3 *Boa*, 1 *Ruim*; recommended 10 *Boa* and 1 *Ruim* per defect, never required, §16); step ② *Amostras* marked ! | normal | *+ Boa* / *+ Ruim* |
| **Âncora não encontrada** (E201/E202 on the live image) | no regions; the anchor's search area in `ov-error`, dashed, with the score and its minimum; a banner over the image names the error | value *não medido*, no needle; chips *–* (did not run); sample dots stay | *! ERRO · E201 · …* and "As ferramentas não rodaram" | *Abrir passo Âncora*; samples and reference still open normally; step ③ marked ! |
| **Câmera perdida** (E401) | last frame dimmed, with its age, under a dialog-like card | as above | *! ERRO · E401 · Câmera desconectada* | *Reconectar*; *Ajustar na referência* (tuning goes on with the reference and samples) |

In every one of them the controls stay usable on the reference and the samples: only the live image is lost.

### 19.2 SchemaForm v2 and the widget registry

The inspector for any tool or locator is drawn from its schema (§9.3), in these sections:

| Section | Holds | From |
|---|---|---|
| Região | Region picker and drawing | the tool's `roi` |
| O que medir | Measurement parameters, each with its widget | `x-group: measure` |
| Critérios | One gauge per `criteria` entry; limits as handles | `criteria` + `x-group: criteria` |
| Resultado | Affects result, failure text with field chips and preview | `affects_result`, `reason_fail` |
| Avançado / Especialista | Remaining parameters by level, collapsed | `x-level` 2 / 3 |

**Widget registry:** `x-widget` → component.

| `x-widget` | Component |
|---|---|
| `hsv-range` | `HsvRangePicker` + eyedropper + mask preview |
| `reference-color` | swatch + eyedropper + ΔE readout |
| `template` | `TemplateCropper` (crop on the reference, preview, rotation range for shape models) |
| `caliper` | caliper drawn on the image + `ProfilePlot` |
| `gray-threshold` | `Histogram` with a draggable threshold, Otsu proposal, binarized preview |
| `angle-range` | `AngleRangeDial` |
| `code-formats` | chip multi-select with format icons |
| `regex` | input with live test against the codes read now |
| `region` | region picker |
| (none) | the plain input for the type (React Aria `NumberField` with unit, `Switch`, `Select`, `SegmentedControl` for small enums) |

An unknown construct still renders as a validated JSON field and is never dropped (as in 0.1).

### 19.3 `ToolToleranceGauge` — the signature control

One gauge per criterion. It is the same in every tool, the fine-tune screen and the results panel. This is the one place where the interface spends its visual boldness.

```
  Fração da região com a cor                                       92 %  ✓
  Boas    ┆           │                        ● ●●● ●● ●
          ┆           │                             ▼ atual
          ┆ 0 ────────┼━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100 %
  Ruins   ┆  ✕ ✕   ✕  │
                      80 (mín)  [◀ arrastar]   [ 80 %]
  Margem: a pior boa (95 %) está 15 pontos percentuais acima do limite; a ruim mais alta, 52 abaixo.
  12 de 12 boas acima · 3 de 3 ruins abaixo                    [Ajustar pelas amostras]
```

- **Scale:** the measured value's full range from `criteria.range`, in its unit. Logarithmic where the unit asks for it (µs).
- **Band:** the allowed band is shaded in the neutral `--bg-3`. The area outside the band is not coloured red: colour stays for status.
- **Handles:** the limits are draggable thumbs of a React Aria `Slider` (one or two thumbs), with a `NumberField` beside each for exact values. `between` criteria have two handles.
- **Needle:** the **current value** (live or the frozen image) as a ▼ marker on the band, in the tool's verdict colour. It jumps, it does not animate (§6.3). With no current measurement (loading, anchor not found, camera lost) there is no needle and the value reads *não medido*.
- **One place for the value:** the current value is written **only** in the gauge header (Mono, with ✓/✕). The tool list and the result bar show the verdict only (✓ ✕ – …); the image shows it only when the *Medições* layer is on. A failing value reaches the result bar through the failure text, not a chip.
- **Sample dots, on two rows:** *Boa* samples as filled dots on the row **above** the band, *Ruim* samples as ✕ on the row **below**, each row labelled (*Boas* / *Ruins*), at their measured values from the batch test. The reference is a dot in the accent colour. A dot on the wrong side of the limit is ringed in the fail colour; the sample shown in the image is ringed in the selection colour. Each dot is a button: clicking it shows that sample in the image (hover shows its name and value). The limit line crosses both rows.
- **Margin line:** in words **and in the criterion's unit** — for a percentage, *pontos percentuais* ("a pior boa (95 %) está 15 pontos percentuais acima do limite; a ruim mais alta, 52 abaixo"), for a length, mm. Never a bare fraction such as "margem 0,15". A second line counts the samples on the right side.
- **No samples:** with no *Boa* or *Ruim* yet, the gauge shows the reference only and says that the limit cannot be checked or proposed; *Ajustar pelas amostras* is disabled with that reason (`aria-disabled`, tooltip).
- **Proposal:** *Ajustar pelas amostras* (FR-UI-14) puts a ghost handle at the proposed limit (the middle of the widest gap, or an agreed margin from the worst *Boa* if no *Ruim* exist), with *Aplicar* / *Descartar*. If the samples overlap, it says so ("As amostras se sobrepõem; a medição não separa boas de ruins") and proposes nothing.
- **Accessible name:** see §12.

**As built (VIA-0065).**
- **Where.** One gauge per criterion of the tool type (`GET /api/tools` › `criteria`) whose level the settings level shows, in the *Critérios* section of the tool, above the criteria parameters that are not limits. The parameters a gauge holds (`criteria.limits`) are not drawn a second time by the form; one that is hidden by the level and was changed still counts in the badge of §17 and is reachable through it.
- **The limit.** A React Aria `Slider` with one thumb per limit set, and a `NumberField` (a fraction as a percentage) beside each. A limit that can be empty (`min_fraction`) has a switch *Usar o limite mínimo/máximo*; one that cannot (`min_count`) does not.
- **The dots** come from the batch test (`POST /api/editor/batch`), measured again, after a pause of half a second, whenever something that affects a result changes; until then the numbers are marked as being measured again. The reference is a dot but never a *Boa* sample. A dot is a button: it shows its sample on the image, with *Voltar à imagem*. The ring of a dot on the wrong side is `ring-fail`.
- **The counts and the rings** (how many good samples are inside, how many bad ones outside, the ring of a dot on the wrong side) include **every** sample. A bad sample that another tool catches and this one passes is left out of the *proposal* (the limit is not blamed for it) but still shown here, so after *Aplicar* such a dot can stay ringed inside the band: it is the other tool's to fail.
- **The batch** is measured again only when something that changes **what** is measured changes: the limits of the criteria are not part of what it depends on, so dragging a limit never sends the samples again or makes the gauge say it is measuring.
- **The needle** is the value of the last measurement of the tool: the live session when the picture is the camera's, the last *Testar* otherwise; none, and *não medido*, when there is neither.
- **The margin** is written in the unit of the measure (*pontos percentuais* for a fraction), and a second line counts the samples on the right side.
- **The proposal** (`POST /api/editor/suggest/limits`, `tools/limits.py`): the middle of the gap between the worst good value and the nearest bad one (a count is whole and on the right side of the gap); with no bad samples, the worst good value less a **margin of 20 %** of it (document 02 §7); never fewer than **3** good samples; samples that overlap, or a limit the parameter does not accept, get no proposal and the gauge says why. It shows as a dashed ghost with *Aplicar* and *Descartar*; nothing changes before *Aplicar*. A bad sample that another tool fails and this one passes is not counted against this tool: that defect is somebody else's to catch.
- **Accessible name.** The group is named by the criterion, each thumb by its limit, and the thumb is described by "Limite mínimo 80%; valor atual 92%; 12 de 12 boas dentro".

### 19.4 Colour: `HsvRangePicker`, eyedropper, mask preview

**Why:** nobody knows an HSV range by heart. The 0.1 editor already proposed a hue range from a region; 0.2 makes colour a direct-manipulation task.

```
  Cor                                                 [◉ Conta-gotas]  [＋ incluir] [－ excluir]
  Matiz    ▕▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▕   (barra de cores reais)
                       ▲━━━━━━━━━━▲          103–128       histograma de matiz da região ▁▃▇▅▂
  Saturação ▕░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▕  ▲━━━━━━━━━━━━━━━━▲ 120–255
  Brilho    ▕░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▕     ▲━━━━━━━━━━━━━━▲ 70–255
  Folga     ─────●──────  +6        [Máscara na imagem ◧]
```

- **Eyedropper:** click or drag on the image to sample pixels; *incluir* adds them, *excluir* removes a colour (for example the label next to a blue cap). The server proposes the range (percentiles 2–98 %) and the picker shows it as a ghost to apply (§6.5).
- **Hue bar** shows real colours at the current saturation and value. Its range wraps around for reds: the band continues from 170 to 10.
- **Saturation and value bars** are gradients at the selected hue.
- **Hue histogram of the region** under the hue bar, so the user sees where the region's colours actually are.
- **Folga:** one slider that widens or narrows all three ranges together. This is the control most people need after the eyedropper.
- **Mask preview:** the pixels inside the range are hatched in `ov-mask` on the image while the control has focus (or always, by the layer switch). Live, at the session rate.
- **Reference colour mode** (distance ΔE to a picked colour): swatch, eyedropper, a single *distância máxima* slider and the same mask.
- **Numbers:** visible on every handle. At Essencial and Avançado, hue in **degrees** (0–360°, handles in 2° steps), saturation and value in **%**, *Folga* in degrees. The OpenCV scales (H 0–179, S and V 0–255) appear **only at Especialista**, beside the degrees, and in the job parameters. The stored job keeps the OpenCV values; only the display changes (levels never change values, §17). The pixel readout under the image follows the same rule.

### 19.5 Other controls

| Component | What it does | Used by |
|---|---|---|
| `Histogram` | 256-bin luminance or channel histogram on canvas; clipping percentages; optional draggable threshold (single or range) with Otsu proposal | camera, brightness tool, blob threshold, quality gates |
| `ExposureControl` | Log slider in µs with stops, NumberInput, *Auto uma vez* (measure, then lock), clipping warning from the histogram | camera step |
| `FocusMeter` | Sharpness value as a bar with **peak hold** ("melhor: 412"); the bar turns green within 5 % of the peak; optional focus-peaking layer | camera step |
| `ProfilePlot` | Intensity profile along a caliper and its derivative; edge threshold as a draggable line; found edges marked and numbered on both the plot and the image | `edge` tool, `edges` locator |
| `AngleRangeDial` | Half-circle dial with two handles for the allowed angle range; the found angle as a needle | anchor step |
| `PoseMarker` | Found anchor: outline, origin cross, axis arrows, angle arc and value | image overlay |
| `TemplateCropper` | Crop on the reference, preview at 1:1, "pontos de contorno" count for shape models, warning when the crop is flat or too small | pattern, template and shape locators |
| `Filmstrip` | Reference, samples (Boa/Ruim with ✓/✕ agreement), live; keyboard navigation; virtualized | editor, fine-tune |
| `ResultChips` | Per-tool ✓ / ✕ / – (did not run) / … (measuring) chips, **without values** (the value lives in the tool's gauge, §19.3); clicking selects the tool | editor result bar, fine-tune. The operator screen has no gauge, so it shows per-tool **lines with the value** in `VerdictPanel` (§7.1) instead |
| `StepRail` | The sequence with step states and reasons (§4.3) | editor |
| `LevelSwitch` | Essencial / Avançado / Especialista with the hidden-changes count | top bar |
| `VerdictPanel` | The operator verdict (as in 0.1) plus per-tool lines | operator screen |

---

## Sources

- Cognex In-Sight EasyBuilder: [Application Steps](https://docs.cognex.com/is_621/web/EN/ise/Content/EasyBuilder/AppSteps.htm).
- Keyence IV series user manual (Setup Navigator: image optimization, master registration, tool settings, output assignment; tool auto tuning with OK/NG images): [manualsdir](https://www.manualsdir.com/manuals/658109/keyence-iv-series.html).
- shadcn/ui: [Slider on React Aria](https://ui.shadcn.com/docs/components/aria/slider) · [Slider on Radix](https://ui.shadcn.com/docs/components/radix/slider).
- React Aria Components: [ColorPicker, ColorSlider, ColorArea](https://react-aria.adobe.com/ColorPicker) · [Slider](https://react-aria.adobe.com/Slider) (npm `react-aria-components` 1.22.1, Apache-2.0).
- Lingui (npm `@lingui/core` 6.10.0, MIT) · dnd-kit (npm `@dnd-kit/core` 6.3.1, MIT).
- Research and architecture behind the sequence: project documents 05 and 06; architecture §7.1, §14, §15, §16.
