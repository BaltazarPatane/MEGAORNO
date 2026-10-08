# MEGAORNO v3.0

> **Versión histórica congelada.** Base Qt, adquisición y análisis térmico. Para desarrollo futuro utilizar [main](https://github.com/BaltazarPatane/MEGAORNO).

## Qué incorpora esta versión

Introduce la aplicación reorganizada en Qt/PySide6 sobre el prototipo previo. Incluye el flujo de inicio, lectura de históricos y sesiones, integración WCF con MadgeTech 4, visualización de curvas, comparación con perfil ideal, cálculo de gradientes por tiempo real, estadísticas, avisos, bitácora, exportación PDF/Excel/CSV, pruebas y archivos de ejemplo.

## Código y pruebas

Este branch contiene **archivos fuente individuales**, no un ZIP. La aplicación se inicia en Windows con `Iniciar.bat` o con Python y las dependencias de `requirements.txt`. Los módulos de interfaz están en `ui/`, el puente MadgeTech en `wcf/`, las pruebas en `tests/`, las referencias en `docs/` y los archivos de demostración en `ejemplos/`.

Consultar `LEEME.md`, `docs/ARQUITECTURA.md` y `docs/VALIDACION.md`.

## Navegación

- [Historial completo y documentación principal](https://github.com/BaltazarPatane/MEGAORNO)
- [v3.0](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.0) · [v3.1](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.1) · [v3.2](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.2)

**Advertencia:** esta aplicación supervisa temperaturas. No controla quemadores ni reemplaza sistemas independientes de seguridad industrial.
