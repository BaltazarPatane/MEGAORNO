$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root 'build\windows'
$installer = Join-Path $build 'dist\MEGAORNO-Setup-x64.exe'
$destination = Join-Path $env:RUNNER_TEMP 'MEGAORNO instalación prueba'
$results = Join-Path $build 'verificacion-instalada'
$null = New-Item -ItemType Directory -Force -Path $results
$sentinelDirectory = Join-Path $env:LOCALAPPDATA 'HornoMadgeTech\capturas'
$null = New-Item -ItemType Directory -Force -Path $sentinelDirectory
$sentinel = Join-Path $sentinelDirectory 'CI-preservar.horno.json'
$sentinelContent = '{"prueba":"captura que debe conservarse"}'
[IO.File]::WriteAllText($sentinel, $sentinelContent)

function Run-Installer {
    param([string]$LogName)
    $log = Join-Path $results $LogName
    $parameters = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RESTARTEXITCODE=3010 /DIR="' + $destination + '" /LOG="' + $log + '"'
    $process = Start-Process -FilePath $installer -ArgumentList $parameters -Wait -PassThru
    if ($process.ExitCode -notin @(0,3010)) { throw "Instalador falló: $($process.ExitCode). Revisá $log" }
}

Run-Installer 'instalacion.log'
$launcher = Join-Path $destination 'MEGAORNO.exe'
if (-not (Test-Path -LiteralPath $launcher)) { throw 'Falta el ejecutable instalado.' }
$desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
$shortcutFile = Join-Path $desktop 'MEGAORNO.lnk'
if (-not (Test-Path -LiteralPath $shortcutFile)) { throw 'No se creó automáticamente el acceso directo.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutFile)
if ($shortcut.TargetPath -ne $launcher) { throw 'El acceso directo no apunta al ejecutable instalado.' }
if ($shortcut.IconLocation -notlike '*ui\icons\megaorno.ico*') { throw 'El acceso directo no utiliza el icono del horno.' }

# Remove access to system Python from PATH. The native launcher must work with
# only its private runtime; PYTHONPATH is deliberately unusable as well.
$previousPath = $env:PATH
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PATH = "$env:WINDIR\System32;$env:WINDIR"
    $env:PYTHONPATH = 'C:\python-que-no-existe'
    $process = Start-Process -FilePath $launcher -ArgumentList ('--self-test "' + $results + '"') -PassThru
    if (-not $process.WaitForExit(300000)) { $process.Kill(); throw 'La prueba del ejecutable instalado superó el límite.' }
    if ($process.ExitCode -ne 0) { throw "La prueba instalada falló ($($process.ExitCode)). Revisá el registro del lanzador." }
} finally {
    $env:PATH = $previousPath
    $env:PYTHONPATH = $previousPythonPath
}
$verification = Get-Content -Raw -LiteralPath (Join-Path $results 'resultado.json') | ConvertFrom-Json
if ($verification.resultado -ne 'OK') { throw 'La prueba funcional no terminó correctamente.' }

# Exercise an update over the existing installation, then uninstall. The
# application capture must survive both operations.
Run-Installer 'reinstalacion.log'
if ([IO.File]::ReadAllText($sentinel) -ne $sentinelContent) { throw 'Se modificó una captura al reinstalar.' }
$uninstaller = Join-Path $destination 'unins000.exe'
$process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Falló la desinstalación: $($process.ExitCode)" }
if (Test-Path -LiteralPath $launcher) { throw 'La desinstalación dejó el ejecutable registrado.' }
if (Test-Path -LiteralPath $shortcutFile) { throw 'La desinstalación dejó el acceso directo.' }
if ([IO.File]::ReadAllText($sentinel) -ne $sentinelContent) { throw 'La desinstalación borró o modificó capturas.' }

$summary = @'
Validación automatizada en Windows x64

OK - Instalador EXE compilado e instalación silenciosa completada.
OK - Ruta de instalación con espacios y caracteres no ASCII.
OK - Acceso directo del escritorio creado automáticamente con el icono del horno.
OK - Lanzador nativo ejecutado sin Python del sistema en PATH.
OK - Python privado y bibliotecas cargadas desde la instalación.
OK - Inicio, cinco pestañas y ejemplo de 93 muestras.
OK - Exportaciones PDF, Excel y CSV desde la instalación.
OK - Guardado y reapertura de sesión.
OK - Puente WCF x86 precompilado y verificación de integridad.
OK - Reinstalación, desinstalación y conservación de capturas.

El runner ya dispone de componentes compartidos de Microsoft. La ejecución de
sus instaladores en una PC sin .NET/VC++ no se simula como prueba física de una
máquina limpia. El instalador contiene los paquetes offline auténticos, verifica
versiones y maneja los errores y reinicios que reporten.
No se conectó un registrador MadgeTech físico en estas pruebas.
'@
[IO.File]::WriteAllText((Join-Path $build 'dist\VALIDACION_WINDOWS.txt'), $summary, [Text.UTF8Encoding]::new($false))
$hashes = Get-ChildItem -LiteralPath (Join-Path $build 'dist') -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object {
    (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.Name
}
[IO.File]::WriteAllLines((Join-Path $build 'dist\SHA256SUMS.txt'), $hashes, [Text.UTF8Encoding]::new($false))
Write-Host $summary
