# Arquitectura de MEGAORNO 3.2

## Separación de responsabilidades

| Módulo | Responsabilidad |
|---|---|
| app.py / gui.py | Arranque Qt, navegación, coordinación de sesión y exportaciones. |
| ui/login.py | Conexión con configuración progresiva y acceso a históricos/ejemplo. |
| ui/curves.py / ui/chart_widget.py | Selección, referencias, navegación y consulta de puntos reales. |
| ui/detail_pages.py / ui/table_models.py | Perfil, estadísticas, datos virtualizados, avisos y bitácora. |
| acquisition.py | Máquina de estados, identidad, validación, captura y descarte de eventos tardíos. |
| live.py | Subproceso WCF y decodificación de estados/unidades/fechas. |
| wcf/MadgeTechClient.cs | Contrato instalado del fabricante, mismo canal para Authenticate/listado/lecturas. |
| wcf/Bridge.cs | Transporte, límites WCF, compilación x86 y eventos JSON. |
| models.py | Datos originales, derivadas, perfil, análisis, sesiones e importación. |
| charts.py / reports.py | Renderizado y exportaciones independientes de widgets. |
| tools/export_session.py | Proceso de exportación sobre instantánea, reemplazo atómico del resultado. |

## Ciclo de adquisición

Inicio → crear captura y respaldo → conectar/autenticar → enumerar → elegir el
único equipo o solicitar selección → consultar → validar → registrar original y
sesión → abrir las vistas. Un puerto abierto no constituye una lectura válida.

Los eventos se consumen en el hilo Qt. El puente usa un hilo/subproceso, con
identificador de generación y request_id. Los resultados de procesos cancelados
se descartan. La compilación compartida está protegida contra reconexiones rápidas.
Las credenciales viajan por stdin y los diagnósticos ocultan sus valores.

El guardado es síncrono antes de publicar una muestra como recibida. No se informa
un éxito de persistencia cuando falla el disco. Las tablas formatean bajo demanda;
sólo se actualiza la solapa visible. El refresco visual se agrupa cada 750 ms y no
se repite por lecturas idénticas; ello no modifica el muestreo ni el guardado.

## Cambios respecto de v2.2

Se reemplaza Tkinter por PySide6; se mantienen las fórmulas y el contrato interno
de las mediciones. El flujo automático usa un solo canal WCF y ya no necesita tres
procesos separados para buscar, previsualizar y recibir. Se preserva la bitácora en
Datos. El WCF genérico sigue en los módulos de transporte como herramienta interna,
pero no agrega solapas al flujo del operador.

Se corrigieron fechas de Excel almacenadas como texto, errores/celdas no finitas,
validación de respuestas malformadas, conversión Fahrenheit con valores extremos,
protección de encabezados Excel como texto, trazado con huecos en Excel, fechas en
PDF, guardado durable y carreras de cancelación/compilación.

La integridad de software se prueba con respuestas simuladas. La DLL del fabricante,
.NET Framework y el dispositivo real no están disponibles en el entorno Linux.
No se afirma que las pruebas con doble de transporte certifiquen el hardware.

## Ajustes de interfaz y diagnóstico en 3.1

Las etiquetas visibles se resuelven mediante `Sesion.nombre` sin cambiar las
claves fecha/canal. El parser mantiene None para entradas vacías y entrega
diagnósticos estructurados al controlador. Éste agrupa cambios por canal/causa
y silencia las entradas sin sensor que nunca midieron; las pérdidas de un canal
activo y las unidades desconocidas siguen diagnosticándose.

El PDF recibe como argumento JSON la lista de identidades seleccionadas junto a
la instantánea; ninguna modificación posterior en la GUI altera esa selección.
Las tablas del informe siguen completas. El widget permite Ctrl + rueda sólo
sobre Y; compartir X entre paneles no cambia esa restricción.

## Adquisición y gráficos en 3.2

- `Registro.gradientes` sustituye el nombre anterior; cada fila mantiene dT/dt en
  °C/min sin redondear. `Sesion.analisis()` expone `gradiente` como valor actual.
- `Registro.cortes` guarda la fecha de la primera muestra posterior a cada pausa.
  Recalcular borra la base anterior en ese límite, sin cambiar muestras previas.
  El mismo límite corta líneas de Matplotlib/Excel y la racha de mantenimiento.
- Sesiones sin cortes siguen en formato v2; con cortes se guardan en v3. El lector
  admite ambos. Esto evita que un visor antiguo ignore silenciosamente las pausas.
- `AcquisitionController.pause()/resume()` conservan sesión, registro, puente y
  archivo. `running` incluye `paused`: ni conectar ni buscar reemplazan una captura
  pausada, y Guardar copia no cambia su destino automático.
- El stdin del puente permanece abierto. La primera línea JSON contiene la
  configuración; las siguientes contienen `command` (`pause`/`resume`) y `epoch`.
  `PollGate.cs` bloquea el sondeo conservando el proxy WCF autenticado, interrumpe
  la espera del período de sondeo y descarta resultados de llamadas en vuelo.
- Cada resultado lleva el epoch del inicio de la consulta. Python elimina
  resultados pendientes de otro intervalo incluso si ya se reanudó. Después de
  una pausa sólo se aceptan fechas de medición nuevas, sin sobrescribir historial.
- Los fallos del transporte, control o disco conservan los datos en memoria y la
  última captura atómica. Se notifican en Avisos y se deshabilita Pausa/Reanudar.
- La reproducción tiene una pausa propia: conserva su cola, fechas y sesión.
- El zoom toma modificadores del evento Qt actual; el estado de tecla cacheado
  por Matplotlib puede quedar desactualizado al cambiar el foco. Cada gesto
  modifica sólo un eje. `draw_event` no llama a repaint/blit dentro del pintado Qt.
  Las anotaciones ampliadas no participan en constrained_layout; se conserva el
  fondo de toda la figura para restaurar también los márgenes al ocultarlas.
