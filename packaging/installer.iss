; Inno Setup script (TD-15). Built by packaging/build_windows.ps1:
;   iscc /DAppVersion=0.1.0 packaging\installer.iss
; Program in C:\Program Files\VisionSystem, data in C:\ProgramData\VisionSystem (never removed by an update or
; by uninstalling). The program starts as a Windows service (WinSW) or, as the fallback of TD-14 for a USB
; camera that does not open from a service, as a task when a user logs on.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F2B8E4A-3C1D-4E7A-9B0F-5A2D7C9E1B34}
AppName=Vision Station
AppVersion={#AppVersion}
AppPublisher=Vision Station
DefaultDirName={autopf}\VisionSystem
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputDir=..\dist
OutputBaseFilename=VisionStation-{#AppVersion}-setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Vision Station {#AppVersion}
CloseApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "service"; Description: "Como serviço do Windows (recomendado: inicia sem ninguém entrar)"; GroupDescription: "Como o programa inicia:"; Flags: exclusive
Name: "logon"; Description: "Ao entrar no Windows (use se a câmera USB não abrir pelo serviço)"; GroupDescription: "Como o programa inicia:"; Flags: exclusive unchecked
Name: "kiosk"; Description: "Abrir a tela do operador em tela cheia (Edge) ao entrar no Windows"; GroupDescription: "Tela do operador:"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\VisionSystem"; Permissions: users-modify

[Files]
Source: "..\dist\vision-station\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "start-vision-station.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "winsw\VisionStation.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "winsw\VisionStation.xml"; DestDir: "{app}"; Flags: ignoreversion

[INI]
Filename: "{app}\Vision Station.url"; Section: "InternetShortcut"; Key: "URL"; String: "http://127.0.0.1:8765"

[Icons]
Name: "{autoprograms}\Vision Station"; Filename: "{app}\Vision Station.url"
Name: "{commonstartup}\Vision Station (tela)"; Filename: "{code:EdgePath}"; Parameters: "--kiosk http://127.0.0.1:8765 --edge-kiosk-type=fullscreen --no-first-run"; Tasks: kiosk

[Run]
Filename: "{app}\VisionStation.exe"; Parameters: "install"; Flags: runhidden waituntilterminated; Tasks: service
Filename: "{app}\VisionStation.exe"; Parameters: "start"; Flags: runhidden waituntilterminated; Tasks: service
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /F /TN ""Vision Station"" /SC ONLOGON /RL LIMITED /TR ""\""{app}\start-vision-station.cmd\"""""; Flags: runhidden waituntilterminated; Tasks: logon
Filename: "{app}\vision-station.exe"; Parameters: "--set-password maintainer --data ""{commonappdata}\VisionSystem"""; Description: "Definir agora a senha do Mantenedor"; Flags: postinstall waituntilterminated skipifsilent unchecked

[UninstallRun]
Filename: "{app}\VisionStation.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\VisionStation.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""Vision Station"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveTask"

[Code]
function EdgePath(Param: String): String;
begin
  Result := ExpandConstant('{commonpf32}\Microsoft\Edge\Application\msedge.exe');
  if not FileExists(Result) then
    Result := ExpandConstant('{commonpf64}\Microsoft\Edge\Application\msedge.exe');
end;

{ An update stops the running program first, so its files can be replaced; the data stays. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  if FileExists(ExpandConstant('{app}\VisionStation.exe')) then
  begin
    Exec(ExpandConstant('{app}\VisionStation.exe'), 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Exec(ExpandConstant('{app}\VisionStation.exe'), 'uninstall', '', SW_HIDE, ewWaitUntilTerminated, Code);
  end;
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/Delete /F /TN "Vision Station"', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM vision-station.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;
