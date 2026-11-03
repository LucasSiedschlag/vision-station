# Backup and restore guide: Vision Station

For the Supervisor (NFR-USA-3): it can be done without the Maintainer.

## What the backup holds

A `.vbak` file with:

- **all the jobs**, with all their versions (or only the latest of each, if configured);
- **which version was active**;
- **the installation configuration** (`system.yaml`): camera, backup, recording, network.

It does **not** hold: the inspection results and images (they are records, not configuration; export them with **Results → Export CSV**) and **the passwords** (for security; set them again after restoring).

## Automatic backup

Under **Settings → Backup** (Maintainer): the folder (network or USB drive), the frequency (default: every 24 h) and how many to keep (default: 30; the oldest are deleted). If the automatic backup fails, **Settings** shows the warning and **Audit** records *Backup failed*.

## Make a backup now

1. **Log in** as Supervisor.
2. **Jobs → Back up now.** The file name and size appear, e.g. `backup_2026-10-15_1432.vbak (2.4 MB)`.
3. To copy it elsewhere: **Jobs → Backups…** → **Download** next to the file.

Keep a copy outside the station PC (USB drive or network).

## Export a single job

**Jobs → ⋯ → Export .vjob** (the latest version), or on the job page, **Export .vjob** on the version you want. Use it to take a job to another station.

## Restore on a new PC (or after a failure)

1. Install Vision Station (installation guide) and set the Maintainer password.
2. Connect the camera **in the same position** as before.
3. **Log in → Jobs → Import file** and choose the `.vbak`.
   - The system checks the whole file first: if it is damaged, it refuses and changes nothing.
   - It shows what came in: versions *added*, *already there*, or *renumbered* (when a version with the same number and different content already existed here).
   - **Importing never activates anything by itself.**
4. Open the job that was active (the notice says which) and click **Activate** on the version.
   - The system requires a readable **reference image** and checks the job against the **reference set** (images with the expected result). Without either reference, activation is refused and the screen shows the reason. If everything matches, it is activated.
   - On activation, the station applies the camera settings and compares the live image with the reference image. If the camera is in another position or out of focus, the screen shows *Verification failed — call maintenance*: adjust the camera and ask the Maintainer to log in and tap **Try again** on the station screen.
5. The installation configuration that came in the backup is **not applied by itself**: check **Settings** (camera, backup folder) and save.
6. Set the passwords again under **Access**.
7. Run a few known good and bad parts to confirm.

## When the verification does not pass

On activation, the system shows what did not match (e.g. *case ok2.png: result FAIL, expected PASS*). Only the **Maintainer** can **Activate anyway**, by writing the reason; this goes in the **Audit**.
