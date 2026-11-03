# Guide to building the installer: Vision Station

For whoever maintains the program. It produces the `VisionStation-<version>-setup.exe` that the [installation guide](installation.md) uses. The build is done **on Windows**: the C920 driver (duvc-ctl) only exists there.

## 1. What you need (once per PC)

| What | What for | How to install |
|---|---|---|
| Windows 10 or 11, 64-bit | the program and the installer are for Windows | — |
| git | download the code and stamp the commit into the version | `winget install Git.Git` |
| uv | Python 3.12 and the program's libraries | `winget install astral-sh.uv` |
| Node 24 | build the interface (React) | nvm-windows: `nvm install 24` and `nvm use 24` |
| Inno Setup 6 | assemble the installer | `winget install JRSoftware.InnoSetup` |
| Internet | the first time: libraries, interface packages and WinSW | — |

To check, open a new terminal (cmd or PowerShell):

```
git --version
uv --version
node -v          (must show v24.x)
npm -v
```

Inno Setup is not on the PATH: the script looks for `ISCC.exe` in `C:\Program Files (x86)\Inno Setup 6\` and in `%LOCALAPPDATA%\Programs\Inno Setup 6\`.

## 2. Build

1. Update the code, in the project folder: `git pull`.
2. Check the version in `pyproject.toml` (`version`) and in `src\vision_station\__init__.py` (`__version__`). Both must be equal; the installer name and the *About* page use that number. For a new delivery, raise both before the build.
3. Run the build:
   - **with a double click** on `packaging\gerar-instalador.cmd`; or
   - in a terminal, in the project folder: `packaging\gerar-instalador.cmd`.

   Only the program, without the installer (does not need Inno Setup): `packaging\gerar-instalador.cmd -NoInstaller`.

The shortcut calls `packaging\build_windows.ps1`, which does, in order:

1. installs Python and the libraries, with the C920 driver (`uv sync --extra uvc --group build`);
2. builds the interface (`npm ci` and `npm run build` in `frontend\`);
3. writes the version, the commit and the build date (they show in *About* and in `vision-station.exe --version`);
4. generates the license list `THIRD_PARTY_LICENSES.md` (it **stops** if a copyleft license appears, NFR-LIC-1);
5. assembles the program with PyInstaller and checks that it starts (`vision-station.exe --version`);
6. downloads WinSW, the program that runs Vision Station as a service, if it is not in the folder yet;
7. assembles the installer with Inno Setup.

Measured on the bench PC (2026-10-16), without the installer: about **3 minutes** in a new folder and about **2 minutes** on later runs. On a PC that has never downloaded the libraries, the first time takes longer.

## 3. What comes out

| File | What it is |
|---|---|
| `dist\VisionStation-<version>-setup.exe` | the installer: this is what goes to the station PC |
| `dist\vision-station\` | the assembled program (the installer carries this folder) |
| `THIRD_PARTY_LICENSES.md` | the licenses of everything that ships with it; deliver it together with the installer |
| `packaging\build_info.json` | version, commit and date of this build |

None of these files goes into git.

## 4. Check before delivering

1. `dist\vision-station\vision-station.exe --version` shows the right version and commit (the script already runs it; check the commit).
2. Install on a test PC following the [installation guide](installation.md) and open the *About* page: version, commit and build date.
3. With the camera connected, the station reaches *Waiting for a part* and a test inspection gives a result.

## 5. Without building on the PC: download from the CI

On every push to GitHub, the CI builds the installer on Windows with the same script, starts the program and checks that the API and the interface respond. To download: GitHub → *Actions* → workflow *tests* → the run for the commit → artifact **installer** (a `.zip` with the installer and the license list).

## 6. Problems

| What you see | What to do |
|---|---|
| `node` is not recognized, or *The path cannot be traversed because it contains an untrusted mount point* | nvm-windows created the `.nodejs` folder without being an administrator and Windows does not follow it. In a PowerShell **as administrator**, logged in as your own user: `$n = "$env:LOCALAPPDATA\Author Software\nvm"`, then `cmd /c rmdir "$n\.nodejs"` and `cmd /c mklink /J "$n\.nodejs" "$n\.shim"`. Open a new terminal. |
| *Inno Setup 6 not found* | Install it with `winget install JRSoftware.InnoSetup`, or build only the program with `-NoInstaller`. |
| *running scripts is disabled on this system* | Use `packaging\gerar-instalador.cmd`: it already runs the script with the needed permission. |
| *duvc-ctl* does not install | The build must be done on Windows (this package does not exist on macOS and Linux). |
| Failure to download WinSW | Without internet: copy `WinSW-x64.exe` version 2.12.0 to `packaging\winsw\VisionStation.exe` and run again. |
| Cannot delete `dist\vision-station` | The assembled program is open (or a terminal is inside the folder): close it and run again. |
| *WARNING: Hidden import "tzdata" not found* | You can ignore it: the program does not use time zones by name. |
| *copyleft* in the license list | A new library has a GPL/AGPL license and cannot ship in the product (TD-18): replace the library. |
