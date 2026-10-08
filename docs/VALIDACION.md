# Validación de MEGAORNO 3.0

Fecha: 2026-10-06. Base: Visor_Horno_MadgeTech v2.2 y contexto suministrados por el usuario.

## Comprobado en este entorno

Linux, Python 3.12.14, PySide6 6.11.2, Matplotlib 3.11.2,
openpyxl 3.1.5 y ReportLab 4.5.1. Dependencias de producción fijadas y verificadas
por hash en `requirements.lock` (variantes para Python 3.11 y posteriores).

**89 pruebas ejecutadas, 89 aprobadas; 0 fallidas, 0 omitidas.**

```bash
QT_QPA_PLATFORM=offscreen \
MPLCONFIGDIR=/workspace/.cache/matplotlib \
XDG_CACHE_HOME=/workspace/.cache \
.venv/bin/python -m unittest discover -s tests -v
```

| Área | Evidencia |
|---|---|
| Base de cálculo | Las 18 pruebas originales siguen pasando. Δt real, asincronía, huecos, duplicados, perfil y unidades. |
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
máximo de canales/muestras. El formato de sesión se mantiene en JSON v2 y su costo
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
