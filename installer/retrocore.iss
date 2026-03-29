#define MyAppName "Retrocore"
#define MyAppVersion "0.1-alpha"
#define MyAppPublisher "Hivemind Studio"
#define MyAppURL "https://hivemindstudio.art"
#define MyAppExeName "retrocore.exe"
#define MyAppCmdName "retrocore.cmd"

[Setup]
AppId={{8F0CF512-7A63-46B2-9A62-9C743DDC9B18}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Retrocore
DefaultGroupName=Retrocore
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist-installer
OutputBaseFilename=retrocore-setup
SetupIconFile=..\branding\retrocore.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addtopath"; Description: "Add Retrocore command to the system PATH"; GroupDescription: "Optional tasks:"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Optional tasks:"; Flags: unchecked

[Files]
Source: "..\dist\retrocore\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "retrocore_launcher.cmd"; DestDir: "{app}"; DestName: "{#MyAppCmdName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Retrocore Manager"; Filename: "{app}\{#MyAppExeName}"; Parameters: "manager"; IconFilename: "{app}\branding\retrocore.ico"
Name: "{autodesktop}\Retrocore Manager"; Filename: "{app}\{#MyAppExeName}"; Parameters: "manager"; Tasks: desktopicon; IconFilename: "{app}\branding\retrocore.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "manager"; Description: "Launch Retrocore Manager"; Flags: nowait postinstall skipifsilent

[Code]
const
  EnvironmentKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

procedure AddDirToPath(Dir: string);
var
  PathValue: string;
begin
  if not RegQueryStringValue(HKLM, EnvironmentKey, 'Path', PathValue) then
    PathValue := '';

  if Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(PathValue) + ';') = 0 then
  begin
    if (PathValue <> '') and (Copy(PathValue, Length(PathValue), 1) <> ';') then
      PathValue := PathValue + ';';
    PathValue := PathValue + Dir;
    RegWriteStringValue(HKLM, EnvironmentKey, 'Path', PathValue);
  end;
end;

procedure RemoveDirFromPath(Dir: string);
var
  PathValue: string;
  UpperPath: string;
  SearchValue: string;
  Position: Integer;
begin
  if not RegQueryStringValue(HKLM, EnvironmentKey, 'Path', PathValue) then
    exit;

  UpperPath := ';' + Uppercase(PathValue) + ';';
  SearchValue := ';' + Uppercase(Dir) + ';';
  Position := Pos(SearchValue, UpperPath);
  if Position > 0 then
  begin
    Delete(PathValue, Position, Length(Dir) + 1);
    while Pos(';;', PathValue) > 0 do
      StringChangeEx(PathValue, ';;', ';', True);
    if (Length(PathValue) > 0) and (Copy(PathValue, 1, 1) = ';') then
      Delete(PathValue, 1, 1);
    if (Length(PathValue) > 0) and (Copy(PathValue, Length(PathValue), 1) = ';') then
      Delete(PathValue, Length(PathValue), 1);
    RegWriteStringValue(HKLM, EnvironmentKey, 'Path', PathValue);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    AddDirToPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveDirFromPath(ExpandConstant('{app}'));
end;
