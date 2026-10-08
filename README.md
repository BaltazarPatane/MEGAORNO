# MEGAORNO v3.2

> **Versión histórica congelada.** Pausa/reanudación y mejora de gradientes y gráficos. Para desarrollo futuro utilizar [main](https://github.com/BaltazarPatane/MEGAORNO).

## Qué incorpora esta versión

Amplía las anotaciones del cursor; corrige el comportamiento del zoom horizontal y vertical; incorpora pausa y reanudación del sondeo sin destruir la sesión ni el canal WCF; evita mezclar respuestas tardías; conserva los cortes por pausa en análisis, gráficos e informes; unifica el término gradiente en interfaz y exportaciones. Las capturas con pausas utilizan formato de sesión v3 y requieren v3.2 o superior.

## Código y pruebas

Este branch contiene **archivos fuente individuales**, no un ZIP. La aplicación se inicia en Windows con `Iniciar.bat` o con Python y las dependencias de `requirements.txt`. Los módulos de interfaz están en `ui/`, el puente MadgeTech en `wcf/`, las pruebas en `tests/`, las referencias en `docs/` y los archivos de demostración en `ejemplos/`.

Detalles en `docs/CAMBIOS_3.2.md` y `docs/VALIDACION.md`. Pausar MEGAORNO no detiene la adquisición interna del equipo MadgeTech.

## Navegación

- [Historial completo y documentación principal](https://github.com/BaltazarPatane/MEGAORNO)
- [v3.0](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.0) · [v3.1](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.1) · [v3.2](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.2)

**Advertencia:** esta aplicación supervisa temperaturas. No controla quemadores ni reemplaza sistemas independientes de seguridad industrial.
