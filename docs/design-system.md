# Vision Station — Design system guide

How to use the system in `frontend/`. The values and the reasons are in `docs/frontend.md` §5 and §6; this is the practical side. The living reference is the gallery: run the interface and open **`/design`** (every token and component, light and dark, compact and kiosk density).

## The five rules

1. **Tokens only.** Colours, sizes, radii and widths come from `src/styles/tokens.css` through the Tailwind names. A hex value, `rgb()`, an arbitrary `w-[…px]` or a default palette class (`bg-red-500`) fails `npm test` (`src/styles/design-rules.test.ts`).
2. **Colour means status, and never alone.** Green, red, amber and blue are for PASS, FAIL, ERROR/attention and busy. Each is shown with an icon and a word (`StatusIndicator`, `Badge`). Neutrals carry the layout.
3. **Every state is designed.** A screen is not done without loading (`Skeleton`), empty (`EmptyState`), error (`ErrorState` with a retry), disabled, focus, offline and forbidden. See the definition of done in `docs/frontend.md` §13.
4. **Plain Portuguese, one word per concept.** All text lives in `src/texts.ts` (the software is pt-BR only). Glossary in `docs/frontend.md` §11.
5. **Confirm what matters, nothing else.** `ConfirmDialog` for activate, override, delete, restore, password change; it names the action and focuses *Cancelar*. Everything else saves directly.

## Tailwind names

| Use | Class |
|---|---|
| Page / panel / input / hover | `bg-surface-0` / `bg-surface-1` / `bg-surface-2` / `bg-surface-3` |
| Hairline / emphasised line / edge of a control | `border-line` / `border-line-strong` / `border-line-control` |
| Text / secondary text | `text-fg` / `text-fg-muted` |
| Primary action, focus | `bg-accent text-on-accent`, `text-accent-text` |
| PASS | `bg-ok text-on-ok`, `text-ok-text`, `bg-ok-surface` |
| FAIL | `bg-fail text-on-fail`, `text-fail-text`, `bg-fail-surface` |
| ERROR / attention | `bg-warn text-on-warn`, `text-warn-text`, `bg-warn-surface` |
| Busy | `text-busy-text`, `bg-busy-surface` |
| Text sizes | `text-xs` 12, `text-sm` 14, `text-base` 16, `text-lg` 20, `text-xl` 24, `text-2xl` 32, `text-3xl` 48, `text-display` (the verdict) |
| Shape | `rounded-control` 6, `rounded-card` 10, `rounded-pill` |
| Spacing | the 4 px grid: `p-1` … `p-16`, `gap-2`, `gap-4` … (4, 8, 12, 16, 24, 32, 48, 64) |
| Density-aware | `h-control`, `min-h-control`, `min-w-control`, `fs-control` (36 px / 14 px compact, 56 px / 18 px kiosk) |
| Overlay widths | `w-dialog`, `w-confirm`, `w-sheet`, `w-toast` |
| Numbers | `font-mono tabular-nums` |

Density is set by `data-density="kiosk"` on an element (the operator route); everything inside follows it. Themes: `useTheme()` from `src/lib/theme.ts`; `<html data-theme>` forces dark or light, no attribute follows the system.

## Components (`src/components/ui/`)

| Need | Component |
|---|---|
| Action | `Button` (`primary`, `secondary`, `ghost`, `danger`; `loading`) |
| Status | `StatusIndicator` (icon + word, `unknown` is never shown as OK), `Badge` |
| Form | `Field` (label, hint, error, ids wired) around `Input`, `NumberInput` (unit, range, comma decimals, arrows), `Textarea`, `Select`, `Switch`, `SliderField`, `SegmentedControl`, `FileDrop` |
| Overlays | `Dialog`, `ConfirmDialog`, `Sheet`, `DropdownMenu`, `Tooltip`, toasts with `toast` from `sonner` (`<Toaster />` is in the providers) |
| Structure | `Card`, `Tabs`, `Table` parts, `Stepper` |
| Feedback | `Skeleton`, `Spinner`, `EmptyState`, `ErrorState` |

Pattern for a new component: build it on a Radix primitive when it has behaviour (focus, keyboard), style it only with the names above, give it every state, add it to `/design`, and test it with Testing Library (roles and names, keyboard, focus). Domain pieces (the verdict panel, live image, region editor, schema form) go in `src/components/domain/` and use these.

## Accessibility checklist for a component or screen

- Reachable and operable with the keyboard alone; visible focus (the 2 px ring comes from the base styles).
- A role and an accessible name for every control; labels through `Field`; errors in `role="alert"`.
- Dialogs: title, focus trapped and returned to the opener, Escape closes.
- Contrast: use the token pairs (they are tested); never put `text-fg-muted` on a status surface.
- Motion only while something runs; `prefers-reduced-motion` is honoured by the base styles.
- Touch targets: `min-h-control` (56 px in kiosk).
