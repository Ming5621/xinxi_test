; Inno Setup 安装程序脚本
; 需先运行 build_windows.bat，再安装 Inno Setup 6 后执行本脚本

#define MyAppName "微机教室考试系统"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ExamSystem"
#define MyAppExeName "ExamSystem.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=微机教室考试系统_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Files]
Source: "..\dist\ExamSystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{userappdata}\微机教室考试系统"

[Code]
function InitializeSetup(): Boolean;
begin
  if not FileExists(ExpandConstant('{src}\..\dist\ExamSystem\ExamSystem.exe')) then
  begin
    MsgBox('请先运行 build_windows.bat 生成程序文件！', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;
