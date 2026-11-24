; Inno Setup 安装程序脚本
; 需先运行 build_windows.bat，再安装 Inno Setup 6 后执行本脚本
; 本文件必须保存为带 BOM 的 UTF-8，否则在中文 Windows 上目录名会乱码，卸载会删错位置。

#define MyAppName "微机教室考试系统"
#define MyAppVersion "1.2.15"
#define MyAppPublisher "柴延明"
#define MyAppExeName "ExamSystem.exe"
#define MyDataDir "微机教室考试系统"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=ExamSystem-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=force
RestartApplications=no
AppMutex=ExamSystemMutex

[Languages]
#ifdef UseChineseMessages
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
#else
Name: "english"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Files]
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\ExamSystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
Type: files; Name: "{app}\icon.ico"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure StopInstalledApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure RemoveFirewallRule(const RuleName: String);
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall delete rule name="' + RuleName + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode
  );
end;

procedure RemoveFirewallRules();
var
  Port: Integer;
begin
  RemoveFirewallRule('{#MyDataDir}程序');
  for Port := 18765 to 18774 do
    RemoveFirewallRule('{#MyDataDir}-' + IntToStr(Port));
  RemoveFirewallRule('{#MyDataDir}-8765');
  RemoveFirewallRule('{#MyDataDir}-8766');
  RemoveFirewallRule('{#MyDataDir}-9765');
  RemoveFirewallRule('{#MyDataDir}-9766');
  RemoveFirewallRule('{#MyDataDir}-9788');
end;

procedure DeleteDataDir(const Dir: String);
begin
  if DirExists(Dir) then
    DelTree(Dir, True, True, True);
end;

procedure DeleteAllUserData();
var
  UsersDir, Target: String;
  FindRec: TFindRec;
begin
  DeleteDataDir(ExpandConstant('{userappdata}\{#MyDataDir}'));
  DeleteDataDir(ExpandConstant('{commonappdata}\{#MyDataDir}'));
  UsersDir := ExpandConstant('{sd}\Users');
  if FindFirst(UsersDir + '\*', FindRec) then
  try
    repeat
      if ((FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and
         (FindRec.Name <> '.') and (FindRec.Name <> '..') then
      begin
        Target := UsersDir + '\' + FindRec.Name + '\AppData\Roaming\{#MyDataDir}';
        DeleteDataDir(Target);
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopInstalledApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopInstalledApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RemoveData: Boolean;
begin
  if CurUninstallStep = usUninstall then
  begin
    StopInstalledApp();
    RemoveFirewallRules();
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    RemoveData := UninstallSilent;
    if not RemoveData then
      RemoveData := MsgBox(
        '是否同时删除本机的考试数据？' + #13#10 + #13#10 +
        '包括教师和学生账号、考试、成绩和日志。残留的数据或仍在运行的程序会导致再次安装失败。' + #13#10 +
        '选择“是”后，本机会恢复为空白数据。需要保留时，请先在软件里导出数据包。',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;
    if RemoveData then
      DeleteAllUserData();
  end;
end;
