#ifndef AppVersion
  #define AppVersion "3.2"
#endif
#ifndef BuildRoot
  #define BuildRoot AddBackslash(SourcePath) + "..\build\windows"
#endif
#ifndef VCX64Version
  #define VCX64Version "14.0.0.0"
#endif
#ifndef VCX86Version
  #define VCX86Version "14.0.0.0"
#endif

[Setup]
AppId={{463813C8-20DC-44B3-8DB9-1960A507B39C}
AppName=MEGAORNO
AppVersion={#AppVersion}
VersionInfoVersion=3.2.0.1
AppPublisher=MEGAORNO - Astillero Río Santiago
AppPublisherURL=https://github.com/BaltazarPatane/MEGAORNO
AppSupportURL=https://github.com/BaltazarPatane/MEGAORNO/issues
DefaultDirName={autopf}\MEGAORNO
DefaultGroupName=MEGAORNO
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
WizardStyle=modern
SetupIconFile=..\ui\icons\megaorno.ico
UninstallDisplayIcon={app}\ui\icons\megaorno.ico
InfoBeforeFile=LEEME_INSTALACION.txt
OutputDir={#BuildRoot}\dist
OutputBaseFilename=MEGAORNO-Setup-x64
Compression=lzma2/normal
SolidCompression=yes
LZMAUseSeparateProcess=yes
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
SetupLogging=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#BuildRoot}\prerequisites\dotnet48.exe"; Flags: dontcopy noencryption
Source: "{#BuildRoot}\prerequisites\vc_redist.x64.exe"; Flags: dontcopy noencryption
Source: "{#BuildRoot}\prerequisites\vc_redist.x86.exe"; Flags: dontcopy noencryption
Source: "{#BuildRoot}\payload\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{commondesktop}\MEGAORNO"; Filename: "{app}\MEGAORNO.exe"; WorkingDir: "{app}"; IconFilename: "{app}\ui\icons\megaorno.ico"; AppUserModelID: "ARS.MEGAORNO"
Name: "{autoprograms}\MEGAORNO"; Filename: "{app}\MEGAORNO.exe"; WorkingDir: "{app}"; IconFilename: "{app}\ui\icons\megaorno.ico"; AppUserModelID: "ARS.MEGAORNO"

[Run]
Filename: "{app}\MEGAORNO.exe"; Description: "Abrir MEGAORNO"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: CanLaunch

[Code]
var
  PrerequisiteRestart: Boolean;

function DotNet48Installed: Boolean;
var Release: Cardinal;
begin
  Result := (RegQueryDWordValue(HKLM32, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Release) and (Release >= 528040));
  if not Result then
    Result := (RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Release) and (Release >= 528040));
end;

function VersionPart(var Value: String): Integer;
var P: Integer; Part: String;
begin
  P := Pos('.', Value);
  if P = 0 then begin Part := Value; Value := ''; end
  else begin Part := Copy(Value, 1, P - 1); Delete(Value, 1, P); end;
  Result := StrToIntDef(Part, 0);
end;

function VersionAtLeast(Current, Required: String): Boolean;
var I, A, B: Integer;
begin
  if (Length(Current) > 0) and (Lowercase(Copy(Current, 1, 1)) = 'v') then Delete(Current, 1, 1);
  Result := True;
  for I := 1 to 4 do begin
    A := VersionPart(Current); B := VersionPart(Required);
    if A <> B then begin Result := A > B; Exit; end;
  end;
end;

function VCInstalled(Architecture, Required: String): Boolean;
var Key, Version: String; Installed: Cardinal;
begin
  Key := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\' + Architecture;
  Result := RegQueryDWordValue(HKLM64, Key, 'Installed', Installed) and (Installed = 1) and
    RegQueryStringValue(HKLM64, Key, 'Version', Version) and VersionAtLeast(Version, Required);
  if not Result then
    Result := RegQueryDWordValue(HKLM32, Key, 'Installed', Installed) and (Installed = 1) and
      RegQueryStringValue(HKLM32, Key, 'Version', Version) and VersionAtLeast(Version, Required);
end;

function InstallPrerequisite(FileName, Title, LogName: String; AllowNewer: Boolean): String;
var ExitCode: Integer; LogPath, Parameters: String;
begin
  Result := '';
  LogPath := ExpandConstant('{commonappdata}\MEGAORNO\Instalacion');
  if not ForceDirectories(LogPath) then begin Result := 'No se puede crear la carpeta de diagnóstico ' + LogPath; Exit; end;
  LogPath := AddBackslash(LogPath) + LogName;
  ExtractTemporaryFile(FileName);
  WizardForm.StatusLabel.Caption := 'Preparando ' + Title + '...';
  if FileName = 'dotnet48.exe' then Parameters := '/q /norestart /log "' + LogPath + '"'
  else Parameters := '/install /quiet /norestart /log "' + LogPath + '"';
  if not Exec(ExpandConstant('{tmp}\') + FileName, Parameters, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
    Result := 'No se pudo iniciar ' + Title + ': ' + SysErrorMessage(ExitCode); Exit;
  end;
  Log(Title + ': código de salida ' + IntToStr(ExitCode));
  if ExitCode = 3010 then PrerequisiteRestart := True
  else if (ExitCode <> 0) and not (AllowNewer and (ExitCode = 1638)) then
    Result := 'No se pudo instalar ' + Title + ' (código ' + IntToStr(ExitCode) + '). Revisá ' + LogPath;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not DotNet48Installed then begin
    Result := InstallPrerequisite('dotnet48.exe', '.NET Framework 4.8', 'dotnet48.log', False);
    if Result <> '' then Exit;
    if not DotNet48Installed and not PrerequisiteRestart then begin
      Result := '.NET Framework 4.8 no quedó disponible. Revisá Windows Update y el diagnóstico de instalación.'; Exit;
    end;
  end;
  if not VCInstalled('x64', '{#VCX64Version}') then begin
    Result := InstallPrerequisite('vc_redist.x64.exe', 'Microsoft Visual C++ x64', 'vc_x64.log', True);
    if Result <> '' then Exit;
  end;
  if not VCInstalled('x86', '{#VCX86Version}') then
    Result := InstallPrerequisite('vc_redist.x86.exe', 'Microsoft Visual C++ x86', 'vc_x86.log', True);
end;

function NeedRestart: Boolean;
begin
  Result := PrerequisiteRestart;
end;

function CanLaunch: Boolean;
begin
  Result := not PrerequisiteRestart;
end;
