; CatZap v1.0 — Installer
#define MyAppName "CatZap"
#define MyAppVersion "1.0"
#define MyAppPublisher "CatZap"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=CatZap_Setup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
UninstallDisplayIcon={app}\CatZap.exe
DisableWelcomePage=no
DisableDirPage=no
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=cat_icon.ico
UninstallDisplayName=CatZap v1.0
WizardStyle=modern

[Languages]
Name: "br"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na &Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
Source: "dist\CatZap.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "cat_zap_extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "cat_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CatZap Server"; Filename: "{app}\CatZap.exe"; WorkingDir: "{app}"
Name: "{group}\Desinstalar CatZap"; Filename: "{uninstallexe}"
Name: "{userstartup}\CatZap Server"; Filename: "{app}\CatZap.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\CatZap - WhatsApp"; Filename: "{code:GetBrowserPath}"; Parameters: "--load-extension=""{app}\extension"" https://web.whatsapp.com"; WorkingDir: "{app}"; Tasks: desktopicon; Check: IsAnyBrowserInstalled

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Instalando VC++ Redistributable..."; Flags: waituntilterminated; Check: VcRedistNeeded
Filename: "{app}\CatZap.exe"; Description: "Iniciar CatZap agora"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im CatZap.exe"; Flags: runhidden
Filename: "{app}\CatZap.exe"; Parameters: "--uninstall"; Flags: runhidden

[Code]
var
  BrowserPath: string;

function GetBrowserPath(Param: string): string;
begin
  Result := BrowserPath;
end;

function IsAnyBrowserInstalled: Boolean;
begin
  Result := BrowserPath <> '';
end;

function VcRedistNeeded: Boolean;
var
  Version: string;
begin
  Result := not (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\VC\Runtimes\x64', 'Version', Version) or
                 RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\VC\Runtimes\x64', 'Version', Version));
end;

function InitializeSetup: Boolean;
begin
  BrowserPath := '';
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe', '', BrowserPath) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe', '', BrowserPath) then
    ; // Chrome found
  if (BrowserPath = '') and (
     RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe', '', BrowserPath) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe', '', BrowserPath)) then
    ; // Edge found (only if Chrome wasn't found)
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  MarkerDir: string;
begin
  if CurStep = ssPostInstall then
  begin
    MarkerDir := ExpandConstant('{userappdata}\CatZap');
    if not DirExists(MarkerDir) then
      CreateDir(MarkerDir);
    SaveStringToFile(MarkerDir + '\.installed', '1', False);
  end;
end;
