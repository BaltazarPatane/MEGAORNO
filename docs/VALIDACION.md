# Validación de MEGAORNO 3.2

Fecha: 2026-10-06. Base: Visor_Horno_MadgeTech v2.2 y contexto suministrados por el usuario.

## Comprobado en este entorno

Linux, Python 3.12.14, PySide6 6.11.2, Matplotlib 3.11.2,
openpyxl 3.1.5 y ReportLab 4.5.1. Dependencias de producción fijadas y verificadas
por hash en `requirements.lock` (variantes para Python 3.11 y posteriores).

**115 pruebas ejecutadas, 115 aprobadas; 0 fallidas, 0 omitidas.**

```bash
QT_QPA_PLATFORM=offscreen \
MPLCONFIGDIR=/workspace/.cache/matplotlib \
XDG_CACHE_HOME=/workspace/.cache \
.venv/bin/python -m unittest discover -s tests -v
```

| Área | Evidencia |
|---|---|
| Base de cálculo | Los cálculos e importaciones originales siguen pasando (las expectativas de etiquetas se actualizaron al renombrado solicitado). Δt real, asincronía, huecos, duplicados, perfil y unidades. |
| Captura WCF simulada | Conexión única, selección, autenticación por stdin, timestamp fraccionario, serie inválida, canales inválidos, respuestas tardías y errores de escritura. |
| GUI | Inicio separado, cinco solapas, ejemplo de 93 muestras, menú con tres formatos, bitácora, perfil y modelos de datos sin truncar. |
| Cierre y reconexión | Consume muestras pendientes antes de cerrar; captura conservada tras errores; búsqueda fallida no reabre una sesión anterior. |
| Navegación | Zoom en puntero, arrastre, doble clic, cambio de unidades, seguimiento y preservación de vista manual. |
| Exportación concurrente | QProcess CSV sobre una instantánea mientras llega y se guarda una segunda muestra. |
| Integridad de archivos | Escritura atómica, limpieza tras fallo, NaN/Inf, fechas Excel en texto, encabezados como texto y cortes de curvas Excel. |
| PDF | Perfil/desfase, ambas curvas, canales, última lectura y fechas de extremos y velocidades. Se comprobó también el texto extraído del PDF. |

Se ejecutó además `tools/smoke_gui.py` contra los widgets reales de Qt (plataforma
offscreen): abre el inicio y las cinco vistas, exporta PDF/Excel/CSV, comprueba
93 filas de mediciones, reproduce las 93 muestras conservando fechas/valores,
reabre la sesión guardada y cierra sin errores. Capturas revisadas visualmente.
Se comprobó también la ventana a 1366 × 738 píxeles, apropiada para una pantalla
1366 × 768 con decoración del sistema.

La tabla de Datos fue probada con 25.001 muestras; todas siguen disponibles. Esto
no constituye un ensayo continuo de varios días ni una caracterización del límite
máximo de canales/muestras. Las sesiones sin cortes usan JSON v2; con pausas usan v3, y su costo
de guardado crece con la captura.

## Comprobaciones físicas pendientes

En este entorno no se ejecutaron .NET Framework, la compilación C# de Windows,
las DLL propietarias ni el TCTempX12. No se ha probado el archivo `.bat` con un
shell de Windows. Las pruebas de transporte usan respuestas simuladas; la recepción
real de la versión anterior fue informada por el usuario en el contexto recibido.

Antes de utilizar esta nueva versión en un tratamiento real, en la notebook final:

1. Arrancar MadgeTech, habilitar WCF e iniciar adquisición con una sonda conocida.
2. Conectar desde MEGAORNO y comprobar que la serie sea la esperada; confirmar
   autenticación cuando corresponda y verificar una temperatura frente a MadgeTech.
3. Comparar varias **fechas de medición** y los valores de cada canal; no comparar
   el instante de consulta con el de adquisición. Confirmar físicamente el mapeo
   de posiciones, sin deducir ubicaciones del nombre de una columna histórica.
4. Tomar dos lecturas consecutivas válidas y verificar `ΔT × 3600 / Δsegundos`.
   Probar que la primera tasa sea vacía y que la pérdida de validez interrumpa la derivada.
5. Detener la adquisición en MadgeTech: MEGAORNO debe mostrar espera o el fallo
   reportado, conservar la última fecha real y evitar fabricar temperaturas nuevas.
6. Desconectar y reconectar el equipo; verificar captura conservada, error claro y
   nuevo inicio de sesión. No esperar recuperación de backlog por RequestLatestReading.
7. Exportar los tres formatos durante una captura y contrastar sus valores con Datos.
   Cerrar sesión, abrir su `.horno.json` y comparar las muestras y la bitácora.
8. Hacer un ensayo de la duración prevista, verificando tiempos de guardado,
   espacio en disco y que el sondeo sea menor al intervalo físico de adquisición.

No se certifica la calibración de los sensores, exactitud metrológica global ni
conformidad del tratamiento mediante pruebas de software. MEGAORNO es un visor y
analizador; la actuación sobre el horno permanece fuera de esta aplicación.

## Regresiones específicas de 3.1

- Se reprodujo el desbordamiento del pie de la GUI 3.0: un aviso de 24 líneas
  ocupaba 321 píxeles y reducía el área de Avisos. En 3.1 los mensajes quedan
  en el diagnóstico de esa solapa, con paneles que no se pueden colapsar a cero.
- Avisos probado con 100 líneas y a 1366 × 738, conservando tabla y diagnóstico
  visibles. Curvas ya no contiene los recuadros de canales/avisos.
- 75 respuestas de 24 canales con entradas vacías, SensorError, OverRange y
  NoSensor: no saturan los avisos; se conservan las 75 respuestas originales y
  los valores inválidos como None. Pérdida y recuperación de un sensor activo
  comprobadas, sin derivada a través del hueco.
- Ctrl + rueda mantiene ambos ejes X compartidos exactamente fijos y cambia
  sólo Y, en los modos Temperatura, Gradiente y Ambas.
- PDF comprobado con una sola termocupla elegida: el renderizador recibe sólo
  esa identidad; las tablas conservan el registro completo. También se generó
  un PDF real por QProcess y se revisó visualmente su primera página.
- Nombres contrastados con las 24 posiciones alternadas, numeración histórica
  TC1/TC3, nombre Madge y alias personalizados de ubicación.

## Regresiones específicas de 3.2

- Eventos `QWheelEvent` reales de Qt, en los tres modos y en ambos sentidos:
  Ctrl + rueda mantiene X exactamente fijo; rueda sola mantiene ambos Y fijos.
  Se corrigió un fallo observado con el estado cacheado de Ctrl de Matplotlib.
- Hover y clic muestran datos registrados, sin interpolar, en fuente de 12 puntos.
  Se eliminó también una llamada recursiva a repaint durante el pintado Qt.
  La anotación queda fuera del cálculo de disposición; el fondo completo del
  lienzo se restaura al ocultarla, incluso si sobresale de una subgráfica baja.
- Pausa descarta tramas tardías sin invocar el parser ni escribir datos nuevos.
  Se contrastaron buffer, archivo de sesión y respaldo WCF antes/después.
- Varias pausas y reanudaciones rápidas: los identificadores de intervalo impiden
  aceptar una respuesta vieja aunque llegue después de Reanudar. Una lectura con
  fecha anterior o igual a la última acumulada tampoco reemplaza el historial.
- Se conserva el mismo objeto de sesión y registro, proceso del puente, archivo,
  perfil, selección, solapa y límites manuales del gráfico. Guardar copia durante
  pausa no redirige la captura; cerrar sesión durante pausa no reabre por tramas tardías.
- Fallos de control, reanudación y guardado mantienen lo adquirido; una muestra
  nueva que no se pudo guardar sigue en memoria con su corte para poder rescatarla.
- Cortes persistidos en JSON v3 comprobados en gradientes, canales asíncronos,
  rachas en banda, Matplotlib, trazado Excel y CSV. Sesiones v2 sin ese campo abren
  y recalculan como antes. Las temperaturas previas se compararon sin redondear.
- La reproducción del ejemplo conserva la misma sesión y cola al pausar/reanudar.
- PDF real por QProcess durante pausa, con sólo Termocuplas · 3 seleccionada;
  la exportación no reanuda adquisición ni modifica el archivo de captura.
- Capturas a 1366 × 738: cursor ampliado, Pausa/Reanudar y continuación del
  historial. El flujo WCF mostrado en esas capturas es simulado.

### Puente C# y comunicación entre procesos

Además de las 115 pruebas de Python/Qt:

- Se compiló **todo el puente C# x86** con Mono C# 6.12 y las referencias
  System.ServiceModel, Runtime.Serialization, Web.Services, Web.Extensions y
  Xml.Linq. Compilación sin errores ni advertencias. Esto no prueba `net.pipe`
  en Windows ni la interoperabilidad con las DLL del fabricante.
- `tools/PollGateTests.cs`, compilado con el mismo `wcf/PollGate.cs` de producción:
  **12 comprobaciones aprobadas**. Cubre bloqueo de consultas durante pausa,
  respuesta en vuelo, cambios repetidos, despertar del sondeo largo, EOF y error
  de protocolo sin revelar su contenido.
- `tools/check_bridge_stream.py` ejecutó el **WcfBridge Python real** contra el
  proceso C# de prueba, por stdin/stdout reales. Se verificaron configuración por
  primera línea, comandos posteriores, sobres con epoch, pausa, reanudación con
  el mismo PID/sesión, gradiente interrumpido, persistencia y cierre. La fuente de
  mediciones era simulada; no se usó hardware ni servicio WCF en esta prueba.

Para reproducir la parte portable con Mono instalado:

```bash
mcs -nologo -out:/tmp/PollGateTests.exe -r:System.Web.Extensions.dll \
  wcf/PollGate.cs tools/PollGateTests.cs
mono /tmp/PollGateTests.exe
.venv/bin/python tools/check_bridge_stream.py mono /tmp/PollGateTests.exe
```

En la notebook final falta contrastar la pausa con MadgeTech: acumular lecturas,
pausar, comprobar que el historial no crece, exportar, reanudar y confirmar las
fechas nuevas y el gradiente vacío en la primera muestra. Repetir con Ctrl
presionado antes de enfocar el gráfico y tras cambiar de solapa. Probar también
el tiempo de pausa esperado frente al límite de inactividad del servicio WCF.
