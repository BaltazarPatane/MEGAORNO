# MEGAORNO v3.1

> **Versión histórica congelada.** Usabilidad, avisos y correcciones de adquisición. Para desarrollo futuro utilizar [main](https://github.com/BaltazarPatane/MEGAORNO).

## Qué incorpora esta versión

Reorganiza los mensajes de error y advertencia en Avisos; corrige la disposición de tablas y diagnósticos; despeja la vista Curvas; elimina notificaciones repetidas ante canales vacíos; mejora la denominación de termocuplas y temperaturas ambiente; incorpora zoom vertical con Ctrl + rueda; simplifica la pantalla inicial; limita los gráficos PDF a los canales elegidos, manteniendo las tablas completas.

## Código y pruebas

Este branch contiene **archivos fuente individuales**, no un ZIP. La aplicación se inicia en Windows con `Iniciar.bat` o con Python y las dependencias de `requirements.txt`. Los módulos de interfaz están en `ui/`, el puente MadgeTech en `wcf/`, las pruebas en `tests/`, las referencias en `docs/` y los archivos de demostración en `ejemplos/`.

Detalle técnico y validación en `docs/CAMBIOS_3.1.md`. Sus sesiones v2 y dependencias son compatibles con v3.0.

## Navegación

- [Historial completo y documentación principal](https://github.com/BaltazarPatane/MEGAORNO)
- [v3.0](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.0) · [v3.1](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.1) · [v3.2](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.2)

**Advertencia:** esta aplicación supervisa temperaturas. No controla quemadores ni reemplaza sistemas independientes de seguridad industrial.
