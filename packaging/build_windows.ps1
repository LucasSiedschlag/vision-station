<#
Builds the installed program and the installer on Windows (TD-15).

    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1            # program + installer
    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -NoInstaller

Needs uv, Node 24 and git; the installer needs Inno Setup 6 (iscc.exe; winget install JRSoftware.InnoSetup).
Output: dist\vision-station\ (the program) and dist\VisionStation-<version>-setup.exe.
#>
param([switch]$NoInstaller)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Run($exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "$exe $($arguments -join ' ') failed ($LASTEXITCODE)" }
}

Write-Host '== Python and the C920 controls'
Run uv @('sync', '--extra', 'uvc', '--group', 'build')

Write-Host '== Interface'
Push-Location frontend
Run npm @('ci')
Run npm @('run', 'build')
Pop-Location

Write-Host '== Version stamp and licences'
$version = (& uv run python -c "import vision_station; print(vision_station.__version__)").Trim()
$commit = (& git rev-parse --short HEAD).Trim()
$info = @{ version = $version; commit = $commit; built_at = (Get-Date -Format 'yyyy-MM-dd') } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $root 'packaging\build_info.json'), $info)  # UTF-8 without BOM
Run uv @('run', 'python', 'scripts/third_party_licenses.py', '--out', 'THIRD_PARTY_LICENSES.md')

Write-Host '== Program (PyInstaller)'
if (Test-Path dist\vision-station) { Remove-Item -Recurse -Force dist\vision-station }
Run uv @('run', '--group', 'build', 'pyinstaller', 'packaging/vision_station.spec', '--noconfirm', '--distpath', 'dist', '--workpath', 'build/pyinstaller')
Run dist\vision-station\vision-station.exe @('--version')

Write-Host '== Service wrapper (WinSW, MIT)'
$winsw = Join-Path $root 'packaging\winsw\VisionStation.exe'
if (-not (Test-Path $winsw)) {
    Invoke-WebRequest -Uri 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe' -OutFile $winsw
}

if ($NoInstaller) { Write-Host 'Done (no installer).'; exit 0 }

Write-Host '== Installer (Inno Setup)'
$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($candidate in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $candidate) { $iscc = $candidate; break }
    }
}
if (-not $iscc) { throw 'Inno Setup 6 not found (winget install JRSoftware.InnoSetup), or use -NoInstaller' }
Run $iscc @("/DAppVersion=$version", 'packaging\installer.iss')
Write-Host "Done: dist\VisionStation-$version-setup.exe"
