#define AppVersion "0.2.7"
#ifndef PayloadDir
  #define PayloadDir "..\AudioPlayer"
#endif
#ifndef InstallerOutput
  #define InstallerOutput "..\installers"
#endif
[Setup]
AppId={{08F8A8C8-71B2-4350-BFC9-FEB50F8BEF5D}
AppName=AudioPlayer
AppVersion={#AppVersion}
AppPublisher=Frommer-droid
AppPublisherURL=https://github.com/Frommer-droid/AudioPlayer
DefaultDirName={code:GetDefaultDir}
UsePreviousAppDir=no
ChangesAssociations=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LanguageDetectionMethod=none
ShowLanguageDialog=no
DefaultGroupName=AudioPlayer
OutputDir={#InstallerOutput}
OutputBaseFilename=AudioPlayer_v{#AppVersion}_Setup
SetupIconFile=..\app\ui\assets\audioplayer.ico
UninstallDisplayIcon={app}\AudioPlayer.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"
[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\AudioPlayer"; Filename: "{app}\AudioPlayer.exe"
Name: "{autodesktop}\AudioPlayer"; Filename: "{app}\AudioPlayer.exe"; Tasks: desktopicon
[Registry]
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe\shell\open"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\AudioPlayer.exe"" ""%1"""
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe\shell\play"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe\shell\play\command"; ValueType: string; ValueName: ""; ValueData: """{app}\AudioPlayer.exe"" ""%1"""
Root: HKLM; Subkey: "Software\Classes\CLSID\{{45DDC492-B10B-4868-B1F1-F315E79543E8}"; ValueType: string; ValueName: "PlayerExecutable"; ValueData: "{app}\AudioPlayer.exe"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\CLSID\{{45DDC492-B10B-4868-B1F1-F315E79543E8}\InProcServer32"; ValueType: string; ValueName: ""; ValueData: "{app}\AudioPlayerShell-{#AppVersion}.dll"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{45DDC492-B10B-4868-B1F1-F315E79543E8}\InProcServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe\shell\open\command"; ValueType: string; ValueName: "DelegateExecute"; ValueData: "{{45DDC492-B10B-4868-B1F1-F315E79543E8}"
Root: HKLM; Subkey: "Software\Classes\Applications\AudioPlayer.exe\shell\play\command"; ValueType: string; ValueName: "DelegateExecute"; ValueData: "{{45DDC492-B10B-4868-B1F1-F315E79543E8}"
[Run]
Filename: "{app}\AudioPlayer.exe"; Description: "Запустить приложение"; Flags: nowait postinstall skipifsilent
[Code]
function GetDefaultDir(Param: String): String;
begin
  if DirExists('D:\') then
    Result := 'D:\Apps\AudioPlayer'
  else
    Result := 'C:\Apps\AudioPlayer';
end;
