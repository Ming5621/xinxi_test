; Inno Setup 安装程序脚本
; 需先运行 build_windows.bat，再安装 Inno Setup 6 后执行本脚本
; 本文件必须保存为带 BOM 的 UTF-8，否则在中文 Windows 上目录名会乱码，卸载会删错位置。

#define MyAppName "微机教室考试系统"
#define MyAppVersion "1.2.19"
#define MyAppPublisher "柴延明"
#define MyAppExeName "ExamSystem.exe"
#define MyDataDir "微机教室考试系统"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=版权所有 © 柴延明 · 保留所有权利
VersionInfoCopyright=版权所有 © 柴延明 · 保留所有权利
InfoBeforeFile=copyright.txt
DisableWelcomePage=no
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
Source: "upgrade_data.ps1"; Flags: dontcopy
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
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}_is1';
var
  UpgradePage: TInputOptionWizardPage;
  OldUninstallCommand, OldVersion, OldInstallDir, BackupRoot: String;
  HasOldData, UpgradePrepared, ClearConfirmed, BackupReady: Boolean;

function RunDataTool(const Mode: String): String;
var
  Params, Report: String;
  Detail: AnsiString;
  ResultCode: Integer;
begin
  Result := '';
  if not FileExists(ExpandConstant('{tmp}\upgrade_data.ps1')) then
    ExtractTemporaryFile('upgrade_data.ps1');
  Report := ExpandConstant('{tmp}\upgrade-result.txt');
  DeleteFile(Report);
  Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{tmp}\upgrade_data.ps1') + '" -Mode ' + Mode +
    ' -ResultFile "' + Report + '"';
  if BackupRoot <> '' then Params := Params + ' -BackupRoot "' + BackupRoot + '"';
  if OldInstallDir <> '' then Params := Params + ' -InstallDir "' + RemoveBackslashUnlessRoot(OldInstallDir) + '"';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := '无法运行数据保护程序：' + SysErrorMessage(ResultCode)
  else if ResultCode <> 0 then
  begin
    LoadStringFromFile(Report, Detail);
    Result := '数据处理失败，安装已停止。' + #13#10 + String(Detail);
  end;
end;

procedure ReadOldInstall(const Root: Integer);
begin
  if OldUninstallCommand <> '' then exit;
  if RegQueryStringValue(Root, UninstallKey, 'UninstallString', OldUninstallCommand) then
  begin
    RegQueryStringValue(Root, UninstallKey, 'DisplayVersion', OldVersion);
    RegQueryStringValue(Root, UninstallKey, 'InstallLocation', OldInstallDir);
  end;
end;

procedure InitializeWizard();
var
  ErrorText, Choice: String;
  CountText: AnsiString;
begin
  ReadOldInstall(HKLM64);
  ReadOldInstall(HKLM32);
  ReadOldInstall(HKCU64);
  ReadOldInstall(HKCU32);
  ErrorText := RunDataTool('detect');
  if ErrorText <> '' then RaiseException(ErrorText);
  LoadStringFromFile(ExpandConstant('{tmp}\upgrade-result.txt'), CountText);
  HasOldData := StrToIntDef(String(CountText), 0) > 0;
  if OldVersion = '' then OldVersion := '未找到版本号';
  UpgradePage := CreateInputOptionPage(wpInfoBefore, '旧版本与数据处理',
    '请选择是否保留旧数据库的全部内容',
    '检测到的旧版本：' + OldVersion + #13#10 +
    '保留范围包括所有账号、班级、题目、考试、答卷、成绩、打字文章及记录。' + #13#10 +
    '处理范围为本机各 Windows 用户的系统数据目录。', True, False);
  UpgradePage.Add('保留全部数据并升级（推荐）');
  UpgradePage.Add('清空全部旧数据，重新安装');
  Choice := ExpandConstant('{param:DATA|keep}');
  if (Choice <> 'keep') and (Choice <> 'reset') then
    RaiseException('DATA 参数必须为 keep 或 reset。');
  UpgradePage.SelectedValueIndex := 0;
  if Choice = 'reset' then UpgradePage.SelectedValueIndex := 1;

end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = UpgradePage.ID) and (OldUninstallCommand = '') and not HasOldData;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = UpgradePage.ID then
  begin
    ClearConfirmed := False;
    if UpgradePage.SelectedValueIndex = 1 then
    begin
      Result := MsgBox('确认清空本机所有用户的旧数据库？' + #13#10 +
        '所有账号、班级、试题、答卷、成绩及打字记录将被删除，不能撤销。',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
      ClearConfirmed := Result;
    end;
  end;
end;

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
var
  PreserveData, UninstallOK: Boolean;
  ResultCode: Integer;
  RestoreError: String;
begin
  Result := '';
  if UpgradePrepared then exit;
  PreserveData := UpgradePage.SelectedValueIndex = 0;
  if not PreserveData and not WizardSilent and not ClearConfirmed and
     ((OldUninstallCommand <> '') or HasOldData) then
  begin
    Result := '请返回并确认是否清空旧数据。';
    exit;
  end;
  StopInstalledApp();
  if PreserveData and not BackupReady then
  begin
    BackupRoot := ExpandConstant('{commonappdata}\ExamSystemUpgradeBackups\') +
      GetDateTimeString('yyyymmdd-hhnnss-zzz', '-', ':');
    Log('Upgrade data backup: ' + BackupRoot);
    Result := RunDataTool('snapshot');
    if Result <> '' then exit;
    BackupReady := True;
  end
  else if PreserveData and BackupReady then
  begin
    { Retry a failed upgrade using the original snapshot, never a partial restore. }
    Result := RunDataTool('restore');
    if Result <> '' then
    begin
      Result := Result + #13#10 + '备份保留在：' + BackupRoot;
      exit;
    end;
  end;
  if OldUninstallCommand <> '' then
  begin
    { Old versions ignore PRESERVEDATA and delete data: verified snapshot protects them. }
    UninstallOK := Exec('>', OldUninstallCommand +
      ' /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /PRESERVEDATA=1', '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if UninstallOK and (ResultCode = 0) then OldUninstallCommand := '';
    if PreserveData then
    begin
      RestoreError := RunDataTool('restore');
      if RestoreError <> '' then
      begin
        Result := RestoreError + #13#10 + '备份保留在：' + BackupRoot;
        exit;
      end;
    end;
    if not UninstallOK or (ResultCode <> 0) then
    begin
      Result := '旧版本卸载失败，安装已停止。错误码：' + IntToStr(ResultCode);
      exit;
    end;
    OldUninstallCommand := '';
  end;
  if not PreserveData then
  begin
    Result := RunDataTool('clear');
    if Result <> '' then exit;
  end;
  UpgradePrepared := True;
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
    { Silent uninstall keeps data unless deletion was explicitly requested. }
    RemoveData := ExpandConstant('{param:DELETEDATA|0}') = '1';
    if ExpandConstant('{param:PRESERVEDATA|0}') = '1' then exit;
    if not UninstallSilent and not RemoveData then
      RemoveData := MsgBox(
        '是否同时删除本机的考试数据？' + #13#10 + #13#10 +
        '包括全部账号、班级、题目、考试、成绩、打字记录和日志。' + #13#10 +
        '选择“是”后，本机会恢复为空白数据。需要保留时，请先在软件里导出数据包。',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;
    if RemoveData then
      DeleteAllUserData();
  end;
end;
