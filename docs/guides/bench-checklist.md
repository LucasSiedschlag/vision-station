# Bench checklist: Phase 1 exit

For the Maintainer (VIA-0117, which fulfils VIA-0016). It is meant to **show** that Phase 1 is ready, not to assume it. Exit criterion (document 01 §7): *a job made on screen, exported, restored on another PC and verified; live PASS/FAIL on the bench*, with the C920.

Tick each item, note the date, the PC and what you saw. An item without a tick was not checked.

## What is already checked automatically

The scenario `frontend/e2e/exit-scenario.spec.ts` (`npm run e2e`) does, on a simulated station, the part that **does not need a second PC**: it creates a job in the editor (reference, tool, good sample, validation), saves, exports the `.vjob`, imports it into a clean installation, activates it (with the rule 4 verification) and sees **PASS** and **FAIL** on the operator screen, each object counted once.

It does **not** prove the vision or the camera: the result comes from a simulated inspection that the test controls. Everything that depends on the real PC, the C920 and time is below.

## 0. Before starting

- [ ] Station PC with the installer of the version to check (`docs/guides/installation.md`); note the version under **About**.
- [ ] A second PC (or an empty data folder on the same PC, on another port) for the restore.
- [ ] C920 connected, bench lighting on, the test part at hand.
- [ ] **Settings → PC performance** (run the performance test, or `vision-station --benchmark`): note the level (M or R) and whether the idle trigger stayed within the limit.

## 1. A job made on screen (FR-JOB, UC-01)

- [ ] **Jobs → New job**: camera applied, trigger chosen, **reference image** captured, at least one tool, **Good** sample and **Bad** sample captured.
- [ ] **Validate all**: all samples with the expected result.
- [ ] **Save**: version 1 appears under **Jobs**.
- [ ] **Activate**: the verification passes. *Without a reference image or a reference set, activation is refused* (rule 4): check that the refusal shows the reason.

## 2. Live PASS and FAIL on the bench (UC-02, UC-03)

- [ ] Good part in the area: **PASS**, counted **once** (not once per image).
- [ ] Remove the part: the screen goes back to waiting by itself.
- [ ] Part with a known defect: **FAIL** with the reason and the marks over the image.
- [ ] Cover the camera or turn off the light: **ERROR**, never a pass.
- [ ] Note the time per inspection (**Duration** column under **Results**): median and worst case.

## 3. Export and restore on another PC (UC-05, NFR-REL-4, NFR-REL-5)

- [ ] On the station PC: **Jobs → ⋯ → Export .vjob** and **Back up now** (`docs/guides/backup-and-restore.md`); copy the files out of the PC.
- [ ] On the other PC (new installation): import the `.vjob` and restore the `.vbak`; set the passwords again (the backup does not hold them).
- [ ] **Activate** the job there: the verification passes **without manual adjustment**, with the same reference image and the same reference set.
- [ ] The results on the images of the reference set are **the same** as on the original PC (NFR-REL-5).
- [ ] Time it: from the new installation to the job active and verified, **at most 1 hour** (NFR-REL-4). Time: ______

## 4. Camera unplugged and plugged back in (UC-09, NFR-REL-3)

- [ ] With the station inspecting, **pull the USB cable**: *Camera disconnected* appears, and no inspection is given as good.
- [ ] Plug it back in: the station inspects again **by itself within 30 s** (NFR-REL-3). Time: ______
- [ ] When opening the station with the camera already connected, the screen shows **Preparing…** (and not *camera lost*) until the camera opens.

## 5. Restart the PC with the service (UC-10, NFR-REL-2)

- [ ] With a job active, restart the PC (or cut the power) **without logging in to Windows**.
- [ ] The station inspects again with the **last active job**, with nobody touching it, **within 2 min** (NFR-REL-2). Time: ______
- [ ] The screen shows the right job and the day's counters continue.

## 6. A shift without stopping (NFR-REL-1)

- [ ] Leave the station inspecting for **a whole shift (proposed: 10 h)**, with real parts or repeating the same one.
- [ ] No restart, no write error, no frozen screen; the data folder did not fill the disk.
- [ ] The shift's results are under **Results**; the time per inspection at the end is similar to the start.
- [ ] No PASS counted for a part that was not there.

## When finished

Keep this filled-in list together with the performance test report (`system/benchmark.json`) and the result of `npm run e2e`. Each item that is **not** ticked becomes a task, with the reason.
