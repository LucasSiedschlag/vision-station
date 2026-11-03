# Installation guide: Vision Station

For the Maintainer. It takes about 30 minutes on a new PC, not counting mounting the camera and the light.

The installer wizard is in Portuguese. Its option labels are quoted below in the original, with the meaning in English.

## 1. What you need

- **PC:** Windows 11 Pro 64-bit, Intel Core i5 12th generation or better, 16 GB of memory, 512 GB SSD, 21" or larger monitor, UPS. Full specification in document 04, §3.
- **Camera:** the C920 on a USB 3 port, or the IP camera on the network (Hikvision driver, after the first delivery).
- **The installer:** `VisionStation-<version>-setup.exe` (built as explained in the [guide to building the installer](building-the-installer.md), or downloaded from the CI, artifact *installer*).
- **Microsoft Edge:** comes with Windows 11; it is the operator screen.

## 2. Install

1. Log in to Windows as an administrator and run `VisionStation-<version>-setup.exe`.
2. **How the program starts:**
   - **As a Windows service** (recommended; installer label "Como serviço do Windows"): starts by itself when the PC turns on, with nobody logged in, and restarts if it crashes.
   - **At Windows logon** (label "Ao entrar no Windows"): use it if the USB camera does not open from the service (see *Common problems*). The program starts when the station user logs in.
3. **Operator screen:** tick the full-screen option (label "Abrir a tela do operador em tela cheia") so that Edge opens the station in kiosk mode whenever someone logs in to Windows.
4. At the end, tick the option to set the Maintainer password now (label "Definir agora a senha do Mantenedor"): a window opens and asks for the password twice (at least 8 characters).

Where everything is:

| What | Where |
|---|---|
| Program | `C:\Program Files\VisionSystem\` |
| Data (jobs, results, images, configuration, logs) | `C:\ProgramData\VisionSystem\` |
| Installation configuration | `C:\ProgramData\VisionSystem\system\system.yaml` |
| Program log | `C:\ProgramData\VisionSystem\logs\` |

## 3. First setup

1. On the station PC, open **http://127.0.0.1:8765** (Start menu → *Vision Station*). The first time, the operator screen shows "This installation has not been set up yet." and the **Set up now** button; it opens the **installation wizard** (`/setup`). Afterwards it is under **Settings → Installation wizard**.
2. **Maintainer password:** create the password (at least 8 characters). This is the only step without a login, and it only works on the station PC itself, once. Write the password down: it cannot be recovered without access to the PC.
3. **Camera:** the wizard lists the USB cameras that are connected. Each one shows as *Validated* or *Not validated* (a model that has not been bench-tested yet). Choose the camera, **Test camera** and **Use this camera**. The camera only changes after the program restarts: in Windows, *Services* → *Vision Station* → *Restart* (or restart the PC). The step is done when the image arrives.
4. **Supervisor password:** set the Supervisor password.
5. **Backup:** the folder comes filled in with the program's data folder. To protect the backups from a disk failure, click **Choose folder…** and pick a USB drive or a network folder. Set the frequency and click **Save the backup folder**; if the program cannot write to the folder, it says why.
6. **First job:** the button opens the editor at the first step. You can also import the station's job (`.vjob`, or the `.vbak` backup of the previous installation) under **Jobs**. Then **Activate**: the system requires a readable reference image and checks the job against the reference set before using it. If either reference is missing, activation is refused and the screen shows the reason.

The *PC performance* and *Machine* steps appear switched off, with the reason: they arrive in later phases and do not stop the station from working. When the password, the camera and the job are ready, the wizard shows **Go to the station**.

If another program on the station (for example the packing station's) is going to use Vision Station through its own screen, put that page's address under **Settings → Network → Pages of other programs** (document 06).

## 4. Update

Run the installer of the new version. It stops the program, replaces the files and starts it again. **The data stays**: jobs, results, configuration and passwords. Jobs in old formats are converted when they are read.

Before updating, make a backup (**Jobs → Back up now**).

## 5. Uninstall

*Windows Settings → Apps → Vision Station → Uninstall.* The service and the task are removed. **The data folder is not deleted**; delete `C:\ProgramData\VisionSystem\` by hand only if you are sure.

## 6. Common problems

| What you see | What to do |
|---|---|
| The screen does not open (page not found) | The program is not running. *Services* → *Vision Station* → *Start*. Check the log in `logs\` |
| "Camera disconnected" all the time with the C920 | Close any program that uses the camera (the Logitech app, Teams, a browser). If it continues and the program runs as a service, reinstall choosing **At Windows logon** (a USB camera sometimes does not open outside the user's session) |
| "A interface não foi compilada" ("The interface was not built"; this page is in Portuguese) | The installer was built without the interface: build it again ([guide to building the installer](building-the-installer.md)) |
| "No active job" | Activate a job under **Jobs** |
| "Verification failed — call maintenance" | The camera or the image changed since the job was made (camera moved, focus, light). The detail appears on screen. Fix the camera and, as Maintainer, tap **Try again** on the station screen; if the scene changed for good, adjust the job in the editor and activate the new version |
| The program does not start and the log mentions `system.yaml` | The file was edited with an error; the log says where. Fix it or delete the file (it goes back to the defaults) |
| Forgot the password | On the PC, in an administrator prompt: `"C:\Program Files\VisionSystem\vision-station.exe" --set-password maintainer --data C:\ProgramData\VisionSystem` |

For support, gather the `C:\ProgramData\VisionSystem\logs\` folder and `system.yaml` (it has no passwords).
