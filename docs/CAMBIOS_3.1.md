# Cambios en MEGAORNO 3.1

1. Advertencias y errores de la sesión dentro de **Avisos**, sin mensajes extensos
   ni recuentos de alertas en la pantalla principal. La cabecera indica el estado
   de recepción; los errores para iniciar conexión siguen disponibles en Inicio.
2. Avisos con tabla y diagnóstico visibles, tamaños mínimos y paneles no colapsables.
   Se eliminó el desbordamiento provocado por copiar avisos largos al pie global.
3. Eliminados los recuadros **Canales con datos** y **Avisos del proceso** de Curvas.
4. Entradas vacías silenciosas y diagnósticos por cambio de estado. Se conserva
   `None` y el respaldo original para mantener la precisión de la derivada.
5. **Temperatura Ambiente** y **Termocuplas · n**, conservando identidades originales,
   numeración histórica y alias personalizados de ubicación.
6. **Ctrl + rueda** cambia únicamente Y. El zoom temporal conserva su rueda normal.
7. Panel azul inicial reducido a Control de tratamiento, gráfica, MadgeTech 4 /
   Interoperabilidad, **Baltazar Patané** y **Juan Marcos Macagno**.
8. Las gráficas del **PDF** contienen sólo los canales seleccionados al exportar.
   Las tablas del informe mantienen todos los canales de la sesión.

## Actualizar

Descomprimí `MEGAORNO_3.1.zip` en una carpeta nueva y ejecutá `Iniciar.bat`.
Se mantienen el formato de sesiones v2 y las dependencias de la versión 3.0.
La configuración y las capturas están en la ubicación elegida (por defecto
`%LOCALAPPDATA%\HornoMadgeTech`), fuera de la carpeta del programa.

Validación: 101 pruebas aprobadas, smoke GUI completo y PDF con selección real.
La nueva versión del transporte continúa pendiente de validación física con
Windows, .NET Framework y el equipo MadgeTech.
