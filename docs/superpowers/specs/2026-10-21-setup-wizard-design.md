# Commissioning wizard (`/setup`) — design

Task: VIA-0068 (held 2 h at the start, 14.5 h from 2026-10-21). Documents: `frontend.md` §7.11, FR-ADM-8, FR-UI-11, `guias/instalacao.md` §3.
Approved by the owner on 2026-10-21.

## Decisions

- **The wizard state is derived, not stored.** The server computes each step from what exists (password set, frames arriving, folder present, a job saved). Nothing is kept that can disagree with reality, a restart of the program (needed after a camera change) loses nothing, and two open tabs agree.
- **Initial Maintainer password in `/setup`, without a login.** While the Maintainer has no password, `/api/setup/*` opens without a login, and only if the API listens on loopback; the first step creates the password. It works once (a second call is 409), is audited, and after it everything asks for a login as usual.
- **Seven steps, in this order:** `maintainer_password`, `camera`, `performance` (unavailable until VIA-0074), `supervisor_password`, `machine` (unavailable until phase B), `backup`, `first_job`. §7.11 had six; the password step is split so the first one can be the bootstrap.
- `needs_setup` is true while the Maintainer password is missing, the camera sends no frames, or no job exists.
- Existing endpoints are reused: `/system/test-camera`, `PUT /system`, `/system/test-folder`, `PUT /users/{role}/password`, the jobs list.

## Checklist

Every box is checked only when its tests pass and `uv run pytest` and `npm test` are green.

- [x] **S1 (2 h) Server: `GET /api/setup/status`** with the derived state of the seven steps and `needs_setup`; open without a login only while the Maintainer has no password, then Maintainer only.
  - [x] one state per step (`done`, `todo`, `unavailable` with its reason)
  - [x] texts in Portuguese and English (catalog)
  - [x] OpenAPI models and `npm run gen:api`
- [ ] **S2 (2 h) Server: `PUT /api/setup/maintainer-password`**
  - [ ] refused when the password already exists (409)
  - [ ] refused when the API is not on loopback (403)
  - [ ] short password refused (400, same rule as `set_password`)
  - [ ] audit event; no session is created (the screen logs in afterwards)
  - [ ] the failed attempts of both cases leave nothing changed
- [ ] **S3 (2.5 h) Interface: route `/setup`**, the `Stepper`, access guard, banner on the operator screen while the Maintainer has no password, automatic opening after the Maintainer logs in when `needs_setup`, entry in *Configurações*.
- [ ] **S4 (2 h) Camera step:** pick driver and device, *Testar câmera*, live image, the restart notice, and continue after the restart.
- [ ] **S5 (1.5 h) Passwords and backup steps:** Supervisor password; folder, *Testar pasta*, frequency.
- [ ] **S6 (1 h) First job step and the unavailable steps:** link to the editor, *Desempenho* and *Máquina* greyed with their reason.
- [ ] **S7 (2 h) Tests:** server, Vitest, Playwright from a clean install to the first job, in Portuguese and English, axe.
- [ ] **S8 (1.5 h) Texts and documents:** both catalogs, `frontend.md` §7.11 *As built*, `guias/instalacao.md` §3, `CLAUDE.md` if the code map changes.

## Edge cases to cover

Camera change that needs a restart · weak password · folder without write permission · API not on loopback · two tabs · status asked after the wizard is complete (Maintainer only) · the camera lost in the middle of the wizard.
