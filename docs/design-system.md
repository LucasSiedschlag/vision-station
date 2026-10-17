# Vision Station — Design system guide

How to use the design system in `frontend/`. The values and the reasons are in `docs/frontend.md` §5, §6 and §17–19 (document 05 v0.3). The component choices are TD-20, TD-29 and TD-30.

The living reference is the gallery: run the interface and open **`/design`**. It shows every token, component and vision control, in light and dark, compact and kiosk density, in pt-BR and en.

## The seven rules

1. **Tokens only.** Colours, sizes, radii and widths come from `src/styles/tokens.css` through the Tailwind names. Overlay colours are tokens too (`--ov-*`), read for canvas and SVG by `lib/overlay.ts`. `npm test` fails (`src/styles/design-rules.test.ts`) on:
   - a hex value or `rgb()`;
   - an arbitrary `w-[…px]`;
   - a default palette class (`bg-red-500`).
2. **Colour means status, and never alone.** Green, red, amber and blue are for PASS, FAIL, ERROR/attention and busy. Each is shown with an icon and a word (`StatusIndicator`, `Badge`). Neutrals carry the layout. On camera images, use the overlay tokens with their line style and tag (document 05 §6.1), never the interface status colours.
3. **Every state is designed.** A screen is not done without loading (`Skeleton`), empty (`EmptyState`), error (`ErrorState` with a retry), disabled, focus, offline and forbidden. Vision controls also need *live*, *frozen*, *no samples* and *samples overlap*; the image workspace also needs *anchor not found* and *camera lost* (document 05 §19.1).
4. **Two languages, one word per concept.** No user-facing string in the code without Lingui: write `t` / `<Trans>` in pt-BR, translate in `src/locales/en/messages.po`. The build fails on a missing translation. Numbers and dates go through the locale formatters (`lib/format.ts`, React Aria `NumberField`). Glossary in both languages: document 05 §11.3.
5. **Confirm what matters, nothing else.** `ConfirmDialog` for activate, override, delete, restore, password change and forced outputs. It names the action and focuses *Cancelar* / *Cancel*. Proposals (eyedropper, *Ajustar pelas amostras*) appear as a ghost with *Aplicar* / *Descartar*. Everything else saves directly.
6. **Every number has a picture.** A tolerance is a `ToolToleranceGauge`, a colour range an `HsvRangePicker`, a threshold a `Histogram` with a handle. The `NumberField` stays beside it for precision. A limit is never a bare number field.
7. **The image is never decorated.** No radius, shadow or card around the image workspace. Overlays always carry their 1 px dark halo.

## Tailwind names

| Use | Class |
|---|---|
| Page / panel / input / hover | `bg-surface-0` / `bg-surface-1` / `bg-surface-2` / `bg-surface-3` |
| Hairline / emphasised line / edge of a control | `border-line` / `border-line-strong` / `border-line-control` |
| Text / secondary text | `text-fg` / `text-fg-muted` |
| Primary action, focus, selection | `bg-accent text-on-accent`, `text-accent-text` |
| PASS | `bg-ok text-on-ok`, `text-ok-text`, `bg-ok-surface` |
| FAIL | `bg-fail text-on-fail`, `text-fail-text`, `bg-fail-surface` |
| ERROR / attention | `bg-warn text-on-warn`, `text-warn-text`, `bg-warn-surface` |
| Busy | `text-busy-text`, `bg-busy-surface` |
| Text sizes | `text-xs` 12, `text-sm` 14, `text-base` 16, `text-lg` 20, `text-xl` 24, `text-2xl` 32, `text-3xl` 48, `text-display` (the verdict) |
| Shape | `rounded-control` 6, `rounded-card` 10, `rounded-pill`; images: none |
| Spacing | the 4 px grid: `p-1` … `p-16`, `gap-2`, `gap-4` … (4, 8, 12, 16, 24, 32, 48, 64) |
| Density-aware | `h-control`, `min-h-control`, `min-w-control`, `fs-control` (36 px / 14 px compact, 56 px / 18 px kiosk) |
| Overlay widths | `w-dialog`, `w-confirm`, `w-sheet`, `w-toast` |
| Numbers and measured values | `font-mono tabular-nums` |
| React Aria states | `data-[dragging]:`, `data-[focus-visible]:`, `data-[disabled]:` variants on the same names |

**Density and theme:**
- Density is set by `data-density="kiosk"` on an element (the operator route); everything inside follows it.
- Theme: `useTheme()` from `src/lib/theme.ts`. `<html data-theme>` forces dark or light; no attribute follows the system.
- Language: the Lingui `I18nProvider` plus React Aria's `I18nProvider` with the same locale. The operator route takes the station language.

## Components

**`src/components/ui/`** (shadcn pattern; Radix unless noted):

| Need | Component |
|---|---|
| Action | `Button` (`primary`, `secondary`, `ghost`, `danger`; `loading`) |
| Status | `StatusIndicator` (icon + word; `unknown` is never shown as OK), `Badge` |
| Form | `Field` (label, hint, error, ids wired) around `Input`, **`NumberField`** (React Aria: unit, locale decimals, arrows within the range; a value out of range is flagged, never changed; a typed `.` or `,` is the decimal mark of the language, so `0.8` is never read as 8; no thousands separator), `Textarea`, `Select`, `Switch`, **`Slider`** (React Aria, one or more thumbs that never cross; `fields` adds a `NumberField` per thumb), `SegmentedControl`, `FileDrop` |
| Colour | **`ColorArea`, `ColorSlider`, `ColorField`** (React Aria, HSB channels): building blocks of `HsvRangePicker` |
| Overlays | `Dialog`, `ConfirmDialog`, `Sheet`, `Drawer` (a `Sheet` from the bottom), `DropdownMenu`, `Popover`, `Tooltip`, toasts with `toast` from `sonner` |
| Structure | `Sidebar` (shell), `Resizable` (panels), `Accordion` (inspector sections), `Card`, `Tabs`, `Table` parts, `Stepper` |
| Navigation | `Command` (Ctrl+K palette, inside our `Dialog`; only the screens of the role) |
| Charts | `Chart` (Recharts) for low-frequency charts, always with a table view |
| Feedback | `Skeleton`, `Spinner`, `EmptyState`, `ErrorState` |
| Language | `LanguageSwitch` |

**`src/components/vision/`** (document 05 §19): `ImageWorkspace`, `OverlayLayers`, `Filmstrip`, `ToolToleranceGauge`, `HsvRangePicker`, `Eyedropper`, `MaskPreview`, `Histogram`, `ProfilePlot`, `AngleRangeDial`, `PoseMarker`, `TemplateCropper`, `FocusMeter`, `ExposureControl`, `ToolList`, `StepRail`, `LevelSwitch`, `VerdictPanel`, `ResultChips`.

**Pattern for a new component:**
- Build it on a Radix primitive when it has behaviour (focus, keyboard); on **React Aria** when it is a slider, number or colour control.
- Style it only with the names above.
- Give it every state.
- Add it to `/design`.
- Test it with Testing Library (roles and names, keyboard, focus), in both languages if it shows text.

A new **tool parameter** needs no screen code: tag it in the Pydantic model with `x-group`, `x-level`, `x-unit`, labels in pt-BR and en, and an `x-widget` from the registry if it needs a graphical control (document 05 §19.2).

## Accessibility checklist for a component or screen

- Reachable and operable with the keyboard alone; visible focus (the 2 px ring comes from the base styles).
- A role and an accessible name for every control. Labels go through `Field`. Errors go in `role="alert"`. Sliders and gauges give `aria-valuetext` in words, in the interface language.
- Dialogs: title, focus trapped and returned to the opener, Escape closes.
- Contrast: use the token pairs (they are tested). Never put `text-fg-muted` on a status surface.
- Colour never alone:
  - status has icon + word;
  - overlays differ by line style and tag;
  - colour controls show numbers.
- Motion only while something runs; `prefers-reduced-motion` is honoured by the base styles. Live images and gauge needles jump; they never animate.
- Touch targets: `min-h-control` (56 px in kiosk).
- `lang` on `<html>` follows the active language.
