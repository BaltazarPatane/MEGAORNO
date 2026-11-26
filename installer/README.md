# Instalador completo de MEGAORNO para Windows

## Descargar e instalar

1. Descargar [MEGAORNO-Setup-x64.exe](https://github.com/BaltazarPatane/MEGAORNO/releases/latest/download/MEGAORNO-Setup-x64.exe).
2. Ejecutar el instalador y aceptar la elevación de Windows para instalar el programa y sus componentes compartidos.
3. Completar el asistente. El acceso directo **MEGAORNO** del escritorio se crea automáticamente con la imagen del horno proporcionada para el proyecto. También aparece en el menú Inicio.
4. Reiniciar si el instalador lo solicita y abrir MEGAORNO desde el escritorio.
5. Elegir **Cargar ejemplo** para comprobar el programa sin instrumental.

El paquete es para **Windows 10 2004 o posterior y Windows 11 en una PC x64**. No es un instalador para Windows de 32 bits ni para ARM64.

## Componentes incluidos

| Componente | Instalación |
|---|---|
| MEGAORNO 3.2 | Aplicación, recursos, ejemplo y exportaciones. |
| CPython 3.14.10 x64 | Runtime privado dentro de `runtime`. No depende del Python del sistema ni modifica PATH. |
| PySide6, Matplotlib, NumPy, openpyxl, ReportLab y dependencias transitivas | Ya instaladas en el paquete, según `requirements.lock`, con verificación de hashes al compilar. No se ejecuta pip en la PC del usuario. |
| .NET Framework 4.8 | Redistribuible offline de Microsoft. Se omite si ya existe 4.8 o una versión posterior compatible. |
| Visual C++ v14 x64 y x86 | Redistribuibles oficiales offline; se conservan versiones iguales o más recientes instaladas. |
| Puente WCF x86 | Precompilado e identificado por hashes de fuentes y ejecutable; no requiere un compilador C# en la PC instalada. |

Después de descargar el EXE no se necesita Internet para obtener estos componentes. Los instaladores de Microsoft se verifican mediante Authenticode durante la compilación, y Python se contrasta con el SHA-256 publicado por Python.org. Las versiones y hashes de los archivos se publican en `componentes.json` y `SHA256SUMS.txt`.

**MadgeTech 4, sus DLL propietarias y los controladores específicos del instrumento se descargan e instalan por separado desde [MadgeTech](https://www.madgetech.com/software/madgetech-4-software/).** La aplicación de ejemplo y los históricos funcionan sin MadgeTech. La conexión real requiere MadgeTech abierto, equipo reconocido, adquisición en tiempo real y salida Interop/WCF habilitada.

## Datos y actualizaciones

El programa se instala normalmente en `C:\Program Files\MEGAORNO`. Las capturas y configuraciones permanecen en `%LOCALAPPDATA%\HornoMadgeTech` o en el destino elegido previamente por el usuario. El instalador no borra ni migra automáticamente esas capturas.

Reinstalar actualiza los archivos del programa. Desinstalar elimina el programa y sus accesos directos; conserva capturas, configuración y los runtimes compartidos de Microsoft. El Python privado se elimina junto con MEGAORNO.

El instalador puede solicitar un reinicio por un componente de Microsoft. No fuerza reinicios mientras instala y evita abrir la app al terminar si detectó que hace falta reiniciar.

## Errores de instalación

- **Permisos de administrador:** la instalación de .NET y Visual C++ requiere elevación; una cuenta sin esos permisos necesita al administrador de esa PC.
- **Windows no compatible:** comprobar versión y arquitectura. No se fuerza la instalación de bibliotecas incompatibles.
- **Falla un componente de Microsoft:** el asistente detiene la instalación e indica su código y el registro en `%PROGRAMDATA%\MEGAORNO\Instalacion`. Resolver ese problema antes de volver a ejecutar el instalador.
- **El programa no abre:** comprobar `%LOCALAPPDATA%\HornoMadgeTech\logs`, donde el lanzador conserva el detalle del inicio.
- **Editor desconocido:** el instalador del proyecto no tiene un certificado comercial de firma de código. Contrastá el origen con la publicación de este repositorio y verificá su SHA-256; los redistribuibles internos de Microsoft conservan su firma del fabricante.
- **MadgeTech no aparece o no hay temperaturas:** no es una descarga pendiente del instalador. Instalar el software del fabricante aparte y revisar su equipo, modo de tiempo real, WCF y credenciales.

## Construcción y verificación

El workflow [Instalador Windows](../.github/workflows/windows-installer.yml) compila en `windows-2022` con Python 3.14.10. Puede iniciarse desde Actions y también se ejecuta cuando cambian los archivos de empaquetado en main.

Para compilar localmente en un entorno de desarrollo Windows x64:

```powershell
py -3.14 -m pip install --require-hashes --only-binary=:all: -r requirements.lock
py -3.14 -m unittest discover -s tests -v
py -3.14 installer/build.py
```

La versión concreta del intérprete debe coincidir con `dependencies.json`; el host de compilación necesita Inno Setup 6 y el compilador de .NET Framework. Estas herramientas no se requieren en la PC del usuario final.

La compilación descarga el runtime oficial y los prerrequisitos, instala las bibliotecas en el payload, compila el lanzador y el puente, comprueba el Python aislado, genera el EXE e instala esa salida en una ruta con espacios y caracteres no ASCII. La prueba arranca el lanzador sin Python de sistema en PATH, abre el ejemplo, revisa las cinco pestañas, exporta PDF/Excel/CSV y comprueba guardado, reinstalación y desinstalación sin perder una captura testigo.

Sólo una ejecución que supere las pruebas publica la descarga en Releases. `VALIDACION_WINDOWS.txt` describe lo comprobado. El runner ya tiene .NET y VC++ instalados; esa prueba no equivale a ejecutar los redistribuibles en una máquina completamente limpia ni a validar un instrumento físico.

El código de empaquetado queda en Git y el ejecutable pesado en Releases, junto con sus hashes y manifiesto. Las licencias de las dependencias permanecen junto a sus archivos en la instalación.
