# 00 — Scope

**Date:** 2026-10-14 · **Method:** Dieter Rams' ten principles (skill `design-is`), evidence gathered by the orchestrator by reading the code and running the screen in Chrome (no sub-agents were launched).

**Audited surface.** The web interface as it exists today: `src/vision_station/web/` (operator screen, login dialog, shell, 8 JS modules + 3 vendored files, one stylesheet). Looked at in a real browser on the demo station (`scripts/demo_station.py`) on 2026-10-14.

**Primary user.** The packing-station *operator*: no technical training, glances at the screen from about 2 m while handling boxes. Secondary users: the *supervisor* (jobs, results, backups) and the *maintainer* (camera, jobs, tools, settings).

**Primary task.** Know at once whether the object on the station passed, failed or could not be inspected, and why.

**Constraints.** Windows 11 PC, Edge kiosk mode, touch possible, no internet at the station, one developer, Portuguese. Operator screen is only the first of many screens (jobs, editor, results, settings, access, audit).

**Decision already taken by the owner (2026-10-14).** The prototype's stack (Preact + htm) is replaced by React with Vite; the design must look professional and follow one system.

**Out of scope of this audit.** Screens that do not exist yet.
