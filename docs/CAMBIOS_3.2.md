# Cambios en MEGAORNO 3.2

1. **Cursor legible:** anotaciones de 12 puntos (antes 8), con canal, lectura,
   unidad y fecha en líneas separadas. Disponibles al mover el cursor o hacer clic.
2. **Zoom por eje:** rueda sola modifica X; Ctrl + rueda modifica Y. Se corrigió
   la lectura de modificadores de Qt para no usar un Ctrl desactualizado.
3. **Pausa / Reanudar:** botón permanente durante la sesión; detiene el sondeo
   sin cerrar el canal WCF, reiniciar el buffer ni reemplazar el gráfico. Se
   descartan respuestas tardías. Al reanudar se conserva el historial y se marca
   el intervalo sin adquisición, también en análisis, gráficos y exportaciones.
4. **Gradiente:** nombre unificado en interfaz, modelo, gráficas, estadísticas,
   perfil ideal, PDF, Excel y CSV. Misma fórmula y unidades, sin cambiar valores.

El ejemplo también admite pausa y reanudación de su reproducción sin reiniciarse.
Las mejoras de 3.1, incluida la selección de canales de la gráfica PDF, se conservan.

## Actualizar

Descomprimí `MEGAORNO_3.2.zip` en una carpeta nueva y ejecutá `Iniciar.bat`.
No cambian las dependencias de Python. El puente WCF se recompila automáticamente
al conectar porque cambió su código; sigue requiriendo .NET Framework 4.8.

Las sesiones v2 anteriores son compatibles. Las nuevas capturas **con pausas**
usan formato v3; deben reabrirse con 3.2 o posterior para respetar sus cortes.
Sin pausas se conserva el formato v2. Los archivos históricos no se sobrescriben
al instalar esta versión.

Pausa controla la recepción de MEGAORNO, no la adquisición interna de MadgeTech.
Al reanudar no se recuperan muestras intermedias del intervalo pausado.

Resultados y límites de verificación: [VALIDACION.md](VALIDACION.md).
