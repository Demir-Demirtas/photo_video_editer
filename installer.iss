; Foto Düzenleyici kurulum dosyası (Inno Setup 6). build.bat bunu otomatik derler.
; Çıktı: dist\FotoDuzenleyici_Kurulum.exe  (Python gerekmez, yönetici izni istemez)
#define AppName "Foto Düzenleyici"
#define AppVersion "3.0"
#define AppExe "FotoDuzenleyici.exe"

[Setup]
AppId={{6F3B1C52-8E4D-4E0B-9C1A-FD0E2B7A31C4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Foto Düzenleyici
DefaultDirName={autopf}\FotoDuzenleyici
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=FotoDuzenleyici_Kurulum
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes

[Languages]
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\FotoDuzenleyici\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "BENIOKU.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Kaldırırken kullanıcının ayarları (%APPDATA%\FotoDuzenleyici: dil, cihaz adı eşleştirmeleri) bilerek silinmez.
