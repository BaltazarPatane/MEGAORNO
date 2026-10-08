# MEGAORNO 3.1

Aplicación de escritorio para adquirir temperaturas desde MadgeTech 4, comparar
un tratamiento con su perfil ideal y calcular velocidades de cambio usando el
intervalo real entre mediciones. Interfaz nueva en Qt/PySide6 sobre la base v2.2
recibida del usuario.

## Inicio en Windows

1. Descomprimí **todo** el ZIP en una carpeta con permiso de escritura.
2. Instalá **Python 3.11–3.14 de 64 bits**. Se recomienda Python 3.12.
3. Ejecutá **Iniciar.bat**. Crea `.venv` e instala dependencias verificadas desde
   `requirements.lock` la primera vez; requiere Internet para esa instalación.
4. Pulsá **Cargar ejemplo**. Abre las 93 muestras originales de R59022, con
   Termocuplas · 1 y Termocuplas · 3 (identidades originales Canal 2 y Canal 6). No requiere MadgeTech.
5. También podés abrir un registro MadgeTech `.xlsx` o una sesión `.horno.json`
   mediante **Abrir archivo**.

No hace falta Excel instalado. Las macros de `.xlsm` no se ejecutan. Las
exportaciones de entrada admitidas están en Celsius; no se importa CSV.

## Conectar el equipo real

Requiere Windows, **.NET Framework 4.8** y la instalación completa de MadgeTech 4.
Python y la interfaz son de 64 bits; el puente WCF se compila **x86** para las DLL
del fabricante. No se incluyen ni reemplazan las bibliotecas propietarias.

1. Abrí MadgeTech 4, comprobá el registrador e iniciá su adquisición en tiempo real.
   Debe estar habilitada la salida WCF por tubería.
2. En MEGAORNO dejá `net.pipe://localhost/MT4Data`, salvo configuración distinta
   confirmada. Sondeo predeterminado: 5 s. El sondeo consulta la última muestra;
   **no programa la frecuencia de adquisición del registrador**.
3. Si WCF exige credenciales, activá **Autenticar en MadgeTech** e ingresá las
   credenciales del servicio. No se deducen del PIN ni de la cuenta de Windows.
4. **Configuración del equipo** permite elegir carpeta MadgeTech, carpeta de
   capturas, buscar equipos y seleccionar una serie. La carpeta debe contener
   `WCFInterop.dll`, `DeviceComm.dll` y las dependencias de la instalación.
5. Pulsá **Conectar con MadgeTech**. La autenticación, enumeración y recepción
   usan un mismo canal WCF. El único equipo se elige automáticamente; si hay más
   de uno se solicita una selección. Las solapas se abren después de recibir y
   guardar al menos una temperatura válida.

No hay que pulsar Buscar, Leer muestra ni Iniciar recepción en el flujo habitual.
Una captura `.horno.json` y su respaldo `.horno.json.wcf.jsonl` se preparan antes
de empezar. La ruta figura en **Datos**. Por defecto se usa
`%LOCALAPPDATA%\HornoMadgeTech\capturas`; puede cambiarse desde el inicio.

El botón de **apagado** cierra la sesión de adquisición o de ejemplo y vuelve al
inicio. No controla alimentación del registrador, quemadores ni actuadores.
Ante un fallo se detiene la recepción y se conserva la captura. Para reconectar,
cerrá sesión y conectá nuevamente: se crea otra captura y no se mezclan corridas.
No existe recuperación automática de muestras intermedias: WCF entrega la última;
los históricos se recuperan mediante el XLSX exportado por MadgeTech.

## Las cinco solapas

- **Curvas:** temperatura, velocidad o ambas; canales seleccionables, nombres
  mediante doble clic, referencias y ventana temporal. Las referencias empiezan
  desactivadas para ajustar la escala a las mediciones.
- **Perfil ideal:** temperaturas inicial/objetivo/final, rampas, mantenimiento,
  banda, desfase y límite de huecos. Vista previa inmediata; **Aplicar perfil**
  recalcula análisis y guarda. Importar receta lee el formato del Excel original.
- **Estadísticas:** última lectura válida y su fecha, extremos y sus fechas,
  mayores velocidades y mayor racha continua en banda. Puede desplazarse
  horizontalmente para ver todas las columnas.
- **Datos:** todas las muestras sin truncarlas, temperaturas, velocidades y etapa.
  **Guardar sesión** permite conservar una copia o rescatar los datos en otra
  ubicación. **Bitácora** conserva las anotaciones y ajustes manuales de seis zonas.
  En modo ejemplo aparece **Reproducir ejemplo**: simula la entrada gradual cada
  250 ms, conservando las fechas originales, en una nueva sesión etiquetada.
- **Avisos:** rampas, banda y huecos; notas de importación y diagnóstico de conexión.
  Los mensajes de advertencia/error quedan en esta solapa; no se muestran en Curvas.
  La cabecera conserva únicamente el estado de recepción, por ejemplo «detenida».

La bitácora documenta ajustes del operador; no envía órdenes al horno. Abrir una
sesión histórica no conecta ni reanuda automáticamente la captura.

## Navegación de gráficos

- **Rueda:** zoom temporal centrado en el puntero.
- **Arrastrar con botón izquierdo:** desplazamiento temporal.
- **Ctrl + rueda:** zoom únicamente del eje Y; mantiene fijo el eje X.
- **Ctrl + arrastre:** desplaza ambos ejes.
- **Mayús + rueda:** zoom sólo vertical.
- **Doble clic / Ajustar vista:** encuadre automático y seguimiento.
- **Seguir últimas muestras:** vuelve a avanzar con la adquisición. Al navegar
  manualmente se pausa el seguimiento y se preservan los límites al llegar datos.
- **Cursor:** consulta muestras registradas exactas, sin interpolar.

Los colores de los canales coinciden entre selector, curva y leyenda. Los datos
inválidos y huecos largos cortan las líneas. Cambiar la vista no suaviza ni altera
los valores utilizados para calcular.

## Exportar y guardar

**Exportar** permanece en la cabecera y ofrece **PDF, EXCEL y CSV**. La exportación
usa una instantánea de la sesión en otro proceso; la adquisición puede continuar.
El archivo de destino sólo se reemplaza al completar la exportación.

- **PDF:** ambos gráficos con **sólo los canales seleccionados en Curvas** al
  pulsar Exportar. Debe haber al menos uno seleccionado. Incluye perfil completo,
  estadísticas con fechas, bitácora y avisos; las tablas del informe mantienen
  todos los canales. La selección y el encuadre de pantalla se conservan.
- **EXCEL:** Receta, Datos, Curvas, Estadísticas, Controladores, Avisos e Importación.
  Una hoja auxiliar oculta `Trazado` mantiene los cortes por huecos sin alterar Datos.
  No depende de macros, vínculos externos ni fórmulas de un libro previo.
- **CSV:** UTF-8 con BOM, separador `;`, punto decimal, fechas ISO, temperatura y
  velocidades en °C/h y °C/min. Las lecturas ausentes quedan vacías.

Las sesiones se guardan automáticamente tras recibir datos y aplicar cambios.
La escritura usa un archivo temporal y reemplazo atómico. Si no puede guardar,
la recepción se detiene y la sesión permanece en memoria para elegir otro destino.
Las credenciales sólo se mantienen en memoria y se envían al puente por stdin;
no se guardan en configuración, sesión, respaldo ni argumentos de proceso.

## Precisión y alcance

`velocidad [°C/h] = Δtemperatura × 3600 / Δsegundos de medición`.

Se conserva el timestamp del fabricante, no el instante de consulta. Se ordenan
lotes y se deduplica por fecha/canal. La primera velocidad queda vacía; una lectura
inválida o un hueco mayor al límite configurado interrumpe la derivada. La ausencia
asincrónica de un canal no equivale a una lectura explícitamente inválida.
No se rellenan datos con cero ni se vuelve a calibrar una temperatura de WCF/XLSX.

Valores no finitos, estados inválidos y unidades desconocidas se conservan como
**sin dato**, con diagnóstico. El perfil predeterminado y el límite de huecos
(7,5 min) deben ajustarse al proceso. Las posiciones WCF identifican el orden
recibido; la ubicación física de cada sonda requiere contraste en el equipo.

Las etiquetas visibles usan **Temperatura Ambiente** para Madge/ambiente y
**Termocuplas · n** para las termocuplas. En las 24 posiciones WCF documentadas,
las impares corresponden a ambiente y las pares a termocuplas, por pares 1–12.
La identidad original queda intacta y puede consultarse en el tooltip del canal.
Los nombres personalizados de ubicación se conservan.

Una entrada vacía o sin sensor se conserva como `None`, sin mensajes repetidos.
Si un canal que ya medía pierde su lectura, se avisa una vez por cambio de estado
en Avisos; al recuperarse no se calcula una derivada a través del intervalo
inválido. Unidades desconocidas y valores inválidos continúan diagnosticándose,
agrupados por canal y causa. El respaldo WCF conserva las respuestas originales.

La aplicación calcula **dT/dt**, no un gradiente espacial. No implementa PID,
control de gas ni el protocolo USB HID experimental del contexto. No extrapola
la calibración de TC1 a otros termopares. Las pruebas de software no certifican
la exactitud metrológica del instrumento ni la conformidad del tratamiento.

## Desarrollo y verificación

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements.lock
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python app.py
```

En Linux/macOS funcionan ejemplo, históricos, cálculos y exportaciones. La tubería
real `net.pipe` es exclusiva de Windows. Para pruebas sin pantalla:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/smoke_gui.py --output /tmp/megaorno-smoke
```

`MEGAORNO_STATE_DIR` permite definir una ubicación independiente de configuración
para desarrollo. No usar una carpeta de producción en las pruebas.

- Arquitectura y alcance: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).
- Resultados comprobados y prueba de aceptación física: [docs/VALIDACION.md](docs/VALIDACION.md).
- Documentación original, conservada como referencia histórica: [docs/BASE_V2.2.md](docs/BASE_V2.2.md).
