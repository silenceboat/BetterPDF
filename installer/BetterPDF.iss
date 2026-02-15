#define MyAppName "BetterPDF"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "dist\\BetterPDF"
#endif
#ifndef WebView2Setup
  #define WebView2Setup "build_assets\\webview2\\MicrosoftEdgeWebView2Setup.exe"
#endif
#ifndef AppIcon
  #define AppIcon "BetterPDF.ico"
#endif

[Setup]
AppId={{8C8AE570-4E9E-4D08-BBF3-0EF0E9AF18F0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=BetterPDF
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=BetterPDF-{#MyAppVersion}-win-x64-setup
WizardStyle=modern
DisableProgramGroupPage=yes
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\BetterPDF.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#DistDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#WebView2Setup}"; DestDir: "{tmp}"; DestName: "MicrosoftEdgeWebView2Setup.exe"; Flags: ignoreversion deleteafterinstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\BetterPDF.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\BetterPDF.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: runhidden waituntilterminated; Check: not IsWebView2RuntimeInstalled
Filename: "{app}\BetterPDF.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function IsWebView2RuntimeInstalled: Boolean;
var
  Version: string;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKCU, 'SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKLM, 'SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
end;
