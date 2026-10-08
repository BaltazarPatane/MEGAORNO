# Visor de horno — versión 2.2

Aplicación local para comparar temperaturas con una receta, calcular velocidades,
registrar ajustes de los operadores y probar la salida WCF de MadgeTech 4.

## Empezar en Windows

1. Descomprimí todo el ZIP en una carpeta nueva.
2. Tené instalado Python 3.11 o posterior, con Tcl/Tk. Se verificó con Python 3.12.
3. Abrí **Iniciar.bat**. La primera vez crea un entorno `.venv` e instala las dependencias;
   esa instalación requiere Internet. Luego reutiliza ese entorno.
4. Pulsá **Cargar ejemplo**. Está incluido el registro R59022 de 93 muestras y dos canales.
5. Para tus archivos, usá **Abrir registro** y elegí la exportación `.xlsx` de MadgeTech.

También podés iniciar desde una terminal en esta carpeta:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

No hace falta tener Microsoft Excel instalado. No se ejecutan macros de los `.xlsm`.
La importación reconoce el formato Fecha/Tiempo/°C del registro recibido; otros formatos,
CSV de entrada o exportaciones en °F necesitan adaptación.

## Pantallas

| Pantalla | Funciones |
|---|---|
| Curvas | Vista de temperatura, velocidad o ambas. Escalas ajustadas al registro, ventana de tiempo y cursor de lectura. Ideal y banda opcionales. |
| Perfil ideal | Inicio, objetivo, final, rampas, mantenimiento, banda y desfase editables. Importa los parámetros del Excel de los operadores. |
| Estadísticas | Última lectura con fecha, máxima y mínima, mayor subida y descenso con fecha y mayor tramo continuo medido dentro de banda. |
| Datos | Cada muestra, ideal, etapa prevista y velocidad por canal. |
| Controladores | Fecha, operador, porcentajes manuales de hasta seis zonas, temperaturas disponibles e incidencias. |
| Avisos | Rampas fuera de límite, temperatura fuera de banda durante el mantenimiento previsto y huecos de datos. |
| Tiempo real | Conexión directa al contrato instalado de MadgeTech 4, selección de equipo, vista previa, recepción, diagnóstico y simulación histórica. |

Los canales conservan sus nombres de origen: el ejemplo contiene Termopar 1 y Termopar 3.
Podés renombrarlos para indicar su ubicación. No se crean termopares faltantes.
En las tablas, usá la barra horizontal inferior para ver todas las columnas.

Los porcentajes de Controladores son un registro manual; la aplicación no gobierna los quemadores.
La temperatura asociada a un evento es la última disponible de cada canal en ese momento,
si su antigüedad no supera el límite de huecos. Un campo vacío significa que no había dato utilizable.

## Gráfica similar a MadgeTech — nueva en v2.2

- **Temperatura** ocupa toda el área de gráfica por defecto. Un solo canal se dibuja
  en rojo, con línea fina, fondo blanco y cuadrícula. Varios canales tienen colores diferentes.
- El eje X usa la **hora de medición**, con horas, minutos, segundos y fecha para
  registros cortos. Se ajusta explícitamente a las muestras: una sola fecha ya no
  produce una escala de meses o años. La primera muestra aparece como un punto.
- La escala Y se ajusta a los valores de los canales seleccionados dentro de la
  ventana visible. Para una curva como la referencia, seleccioná un solo canal
  y dejá Curva ideal y Banda de mantenimiento desmarcadas.
- **Gráfica → Velocidad** muestra el gradiente; **Ambas** muestra los dos gráficos.
  El selector superior °C/h / °C/min sigue controlando la unidad de velocidad.
- **Tiempo** permite Todo el registro o los últimos 5, 15, 30 o 60 minutos medidos.
  La ventana avanza al recibirse una muestra nueva. **Ajustar vista** restaura el
  encuadre automático después de usar el zoom de la barra inferior.
- Al mover el puntero, el cursor marca la muestra más cercana e informa el canal,
  su fecha/hora y valor. Durante zoom o desplazamiento, el cursor se oculta.
- **Curva ideal** agrega la referencia dentro del tiempo visible y los límites de
  rampa en la vista de velocidad. **Banda de mantenimiento** agrega su intervalo.
  Estas opciones amplían la escala Y para que también se vean las referencias.
- **Ver programa completo**, con Tiempo en Todo el registro, extiende X hasta el
  final de la receta. Dejalo desmarcado para seguir una prueba de pocos minutos.
- Los máximos y sus fechas siguen disponibles en **Estadísticas**.

Podés usar **Abrir sesión** para visualizar las capturas de v2.1 con la escala corregida.
La exportación PDF incluye todos los canales, las dos gráficas y la receta completa;
luego restaura la vista seleccionada en pantalla.

## Receta inicial tomada del Excel

- Inicio **10 °C**; ascenso **150 °C/h**; objetivo **630 °C**.
- Mantenimiento **60 minutos**, banda **620–640 °C**.
- Descenso **150 °C/h** hasta **300 °C**.
- Duración calculada: **248 + 60 + 132 = 440 minutos**.
- Límite inicial de huecos para interrumpir la derivada: **7,5 minutos**.

El perfil empieza en la primera muestra más el desfase configurado. Ajustá ese punto para
alinearlo con el inicio real del programa. La curva ideal se mantiene en 300 °C después del final.
La curva se construye desde la receta: el Excel tenía además celdas y tramos copiados manualmente.

### Velocidad y multiplicador 12

```text
velocidad en °C/h = (temperatura actual − anterior) × 3600 / segundos transcurridos
```

Con 300 segundos exactos equivale a multiplicar la diferencia por 12.
El ejemplo tiene intervalos de 299, 300 y 301 segundos: aquí se usa el intervalo real.
Por eso puede haber pequeñas diferencias respecto de la fórmula fija del Excel.
La visualización permite °C/h o °C/min; la primera velocidad queda sin dato.
Una lectura explícitamente vacía/inválida o un hueco excesivo corta la derivada.
Si los canales llegan en instantes distintos, cada uno usa su propia muestra anterior.

El tiempo en banda suma los intervalos entre muestras consecutivas del canal cuyos dos
extremos están en banda; se informa el mayor tramo continuo. No se interpolan cruces ni
se asegura que entre dos muestras la temperatura haya permanecido en banda.
El mantenimiento programado y el tiempo observado en banda son métricas distintas.

## Guardar y compartir

- **Guardar sesión** conserva datos, receta, nombres y anotaciones en `.horno.json`.
  Recuperala con **Abrir sesión**. Una vez elegida la ubicación, los cambios aplicados
  y las nuevas lecturas se guardan automáticamente.
- **Exportar Excel** genera un libro independiente con Receta, Datos, Curvas,
  Estadísticas, Controladores, Avisos e Importación. Son resultados calculados, sin macros
  ni vínculos externos. Para recalcular con otra receta, exportá nuevamente desde la aplicación.
- **Informe PDF** incluye todos los canales, la curva ideal, receta, resumen, controladores y avisos.
- **CSV** contiene temperaturas y ambas unidades de velocidad. Usa `;` y punto decimal.
  Si Excel no interpreta los números, importá indicando esos separadores.
- **Exportar controladores CSV** genera sólo el registro de intervenciones.

En `ejemplos` hay una planilla y un PDF de resultado. La anotación de controlador incluida
está marcada como demostración y no corresponde al registro original del horno.

## Conexión con MadgeTech 4 — nueva en v2.1

El ZIP recibido permitió identificar `WCFInterop.IMT4RealTimeNotifierService`,
versión de biblioteca **1.1.0.2**. La aplicación ahora usa esa interfaz directamente,
cargándola desde la instalación de MadgeTech. **No necesita descubrir metadatos MEX,
configurar XML ni usar WcfTestClient para conectarse a MadgeTech.**

En tu instalación ya se confirmó la autenticación y recepción de 24 valores por WCF.
MadgeTech muestra temperatura ambiente y termopar para cada uno de los 12 canales.
La correspondencia de posiciones debe comprobarse conectando una termocupla conocida.
Las pruebas del código y de la gráfica se ejecutaron localmente con datos simulados;
el entorno de desarrollo no dispone del transporte de tuberías de Windows.

### Primera prueba, incluso sin el adquisidor

1. Descomprimí la versión nueva en una carpeta propia y ejecutá **Iniciar.bat**.
2. Abrí MadgeTech 4 y habilitá su salida WCF por tubería.
3. En el visor, entrá en **Tiempo real → MadgeTech 4**.
4. Dejá la dirección `net.pipe://localhost/MT4Data`.
5. Revisá **Carpeta MadgeTech 4**. Normalmente es
   `C:\Program Files (x86)\MadgeTech\MadgeTech 4`.
   Usá la carpeta de instalación completa: debe contener `WCFInterop.dll`,
   `DeviceComm.dll` y sus dependencias. No uses la carpeta donde descomprimiste
   solamente las tres bibliotecas que enviaste para analizar.
6. Dejá **Usar Authenticate** desmarcado si la salida WCF no tiene credenciales
   configuradas. Si las tiene, marcá la opción e ingresá ese usuario y contraseña.
   No corresponden automáticamente a tu cuenta de Windows ni al PIN del equipo.
   Las credenciales se envían al puente por su entrada estándar y no se guardan
   en la configuración ni en el diagnóstico.
7. Pulsá **1. Buscar equipos**.

Si aparece **«El servicio respondió correctamente, pero no informa equipos conectados»**,
la consulta WCF ya funcionó. No hace falta un equipo conectado para intentar esta
consulta. Sin adquisición disponible no habrá temperaturas para recibir.
Si el servicio devuelve otro resultado o falla, guardá el diagnóstico para revisarlo.

### Con el adquisidor conectado

1. Verificá que MadgeTech detecte el equipo e iniciá la adquisición en tiempo real
   con el intervalo de muestreo que necesites.
2. Pulsá **1. Buscar equipos** y elegí su **Número de serie**.
3. Pulsá **2. Leer última muestra**. Revisá la hora de medición, la unidad,
   el estado de cada canal y la temperatura convertida a °C.
4. Compará la vista previa con MadgeTech. El contrato recibido incluye una lista
   de canales sin sus nombres físicos: **Posición WCF 1** significa primer elemento
   recibido, y no garantiza que sea el termopar físico 1. Usá posteriormente
   **Curvas → Asignar nombre / ubicación** cuando hayas verificado la correspondencia.
5. Conservá **Unidad: Auto** y **Estado válido: Auto** si interpreta correctamente.
   Auto reconoce nombres habituales de Celsius, Fahrenheit y Kelvin, y estados
   nominales como Valid, OK y Success. No presupone que el estado numérico 0 sea válido.
   Los nombres concretos se obtienen de `DeviceComm.dll` al conectar.
6. Si una unidad o un estado nominal no se reconoce, confirmá su significado en
   MadgeTech antes de seleccionarlo manualmente y pulsá **Actualizar vista previa**.
   La unidad manual se aplica a todos los canales del equipo seleccionado;
   utilizala sólo si todos representan esa misma unidad de temperatura.
   No selecciones estados de error o saturación como válidos.
7. Pulsá **3. Iniciar recepción** y elegí dónde guardar la sesión `.horno.json`.
   La unidad y el estado válido quedan fijados para esa recepción: para cambiarlos,
   detené la captura e iniciá una nueva.
8. En **Curvas**, **Datos** y **Estadísticas** se actualizan las temperaturas y
   velocidades. Con sólo una muestra todavía no se puede calcular la velocidad.

**Sondeo y muestreo son distintos:** consultar cada 5 segundos no cambia el intervalo
programado en MadgeTech. Si mide cada 5 minutos, las consultas intermedias normalmente
repiten la última muestra. Se conserva la hora de medición y se deduplica por fecha y canal.

`RequestLatestReading` solicita la última lectura; esta interfaz no ofrece un método
para recuperar todo el historial. Un corte prolongado o un sondeo demasiado lento
puede hacer que se pierdan muestras intermedias. Usá un sondeo menor que el intervalo
de adquisición. El visor permite importar el registro completo exportado cuando se necesite.

Las lecturas con estado no válido, unidad no reconocida o valor no finito se registran
como **sin dato** y cortan el cálculo de velocidad. No se convierten a cero.
Las fechas con zona horaria se convierten a la hora local de Windows. Las fechas sin
zona conservan la hora recibida: comprobá su coincidencia con MadgeTech.

Se guarda un archivo `.wcf.jsonl` junto a la sesión con las respuestas diferentes,
incluidas las unidades y estados originales. Los datos recibidos se conservan si
se corta la comunicación. Cada inicio de recepción pide una sesión nueva y no hay
reconexión automática. La hora de medición permanece visible para detectar lecturas antiguas.

### Diagnóstico

En **Diagnóstico / respuesta → Guardar diagnóstico y última respuesta** podés exportar
un JSON con contrato, acciones, estados/unidades disponibles y última respuesta.

| Mensaje | Qué revisar |
|---|---|
| No informa equipos conectados | La consulta respondió; conectá el equipo y comprobalo en MadgeTech. |
| No hay lectura en tiempo real disponible | Iniciá la adquisición en tiempo real; abrir un registro histórico no genera lecturas nuevas. |
| UnauthorizedAccessException / Authenticate rechazado | Credenciales de la salida WCF y opción Usar Authenticate. |
| DeviceOfflineException / CommunicationLostException | Conexión entre MadgeTech y el adquisidor. |
| DeviceNotFoundException | Volvé a buscar equipos y elegí la serie actual. |
| Falta WCFInterop.dll o DeviceComm.dll | Elegí la carpeta de instalación completa. |
| ActionNotSupported / AddressFilter / error 109 | Guardá el diagnóstico; verificá la dirección, salida por tubería y versión instalada. |
| Sin temperaturas válidas | Compará unidad, estado y sensores con MadgeTech; el diagnóstico conserva sus nombres originales. |

La conexión MadgeTech usa `NetNamedPipeBinding` con seguridad de transporte, el modo
que sí produjo respuestas SOAP en tu prueba. Se autentica, lista equipos y consulta
lecturas sobre un mismo canal WCF. El puente se compila localmente en x86 usando
**.NET Framework 4.8**, también requerido por las bibliotecas recibidas. No necesita
Visual Studio ni WcfTestClient si el compilador de Framework está disponible.

Las pantallas **WCF genérico (avanzado)** y **Campos XML (genérico)** conservan las
pruebas de MEX y operaciones manuales para otros servicios y el ejemplo incluido.
No forman parte de los pasos de conexión directa a MadgeTech.

## Probar sin el aparato

### Reproducción del registro

En **Tiempo real**, pulsá **Reproducir ejemplo (simulado)**. Agrega las 93 muestras
de forma acelerada, manteniendo sus fechas. La sesión figura como SIMULACIÓN.
Permite ensayar la interfaz; no prueba la comunicación WCF.

### Servicio WCF de demostración en Windows

1. Abrí **Probar_tuberia_demo.bat** y dejá su consola abierta.
2. Cambiá la dirección a `net.pipe://localhost/HornoDemo`.
3. Entrá en **WCF genérico (avanzado)**, pulsá **Descubrir servicio genérico (MEX)**,
   elegí **GetLecturas** y leé una respuesta.
4. Configurá:

| Campo | Valor |
|---|---|
| Elemento XML de cada lectura | `Lectura` |
| Campo fecha y hora | `Fecha` |
| Campo temperatura | `Temperatura` |
| Campo canal | `Canal` |
| Dispositivo / canal fijo | vacíos |
| Unidad | `°C` |

5. Previsualizá e iniciá recepción. Deben aparecer dos canales DEMO.
6. Detené la recepción y presioná Enter en la consola del servicio.
7. Para usar MadgeTech, restaurá `net.pipe://localhost/MT4Data` y volvé a la pestaña
   **MadgeTech 4 → Buscar equipos**.

GetLecturas es exclusivamente el método del servicio de demostración incluido, no una
afirmación sobre la API de MadgeTech. Esta prueba permite aislar WCF en Windows.

## Verificación

- Registro real: 93 muestras; máximos **652,5 y 644,4 °C**, ambos a las **12:44:11**.
- Pruebas de intervalos, receta, faltantes, huecos, canales asincrónicos, deduplicación,
  guardado/apertura, exportación y conversión XML.
- Interfaz, Excel/PDF y cola de recepción verificados con datos de ejemplo.
- Puente C# compilado; contrato del archivo WCFInterop recibido verificado mediante
  metadatos y reflexión. Se comprobó la conversión de sus objetos usando una dependencia
  DeviceComm ficticia sólo para la prueba local: no valida los valores del enum real.
- Flujo de interfaz probado con eventos simulados: búsqueda sin equipo, selección,
  vista previa, inicio, autoguardado, duplicados y fallas de sensor.
- El usuario confirmó la conexión real por tubería tras habilitar Authenticate.
  Queda completar la comparación de termocuplas físicas, posiciones y temperaturas.
- Gráfica v2.2: probados una sola muestra, cinco minutos de datos, escalas, ideal,
  ventanas temporales, faltantes, tres vistas, cursor y restauración tras exportar PDF.

Pruebas de cálculo, decodificación y gráfica (18 casos): `py -m unittest discover -s tests -v`.
El código del puente y del servicio de demostración está en `wcf`.

Referencias de implementación WCF: [mensajes sin tipos](https://learn.microsoft.com/en-us/dotnet/framework/wcf/samples/untyped-request-reply)
y [clase Message](https://learn.microsoft.com/en-us/dotnet/framework/wcf/feature-details/using-the-message-class), documentación de Microsoft.
