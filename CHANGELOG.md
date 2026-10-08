# Historial de versiones de MEGAORNO

El repositorio conserva **código fuente navegable por rama**. Cada rama de versión representa una entrega histórica, mientras que [`main`](https://github.com/BaltazarPatane/MEGAORNO) contiene la versión estable más reciente (v3.2). Los ZIP originales dejaron de formar parte del árbol actual; se conservan en el historial Git anterior a la reorganización.

| Versión | Rama | Principales cambios |
| --- | --- | --- |
| **3.0** | [`version/v3.0`](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.0) | Base Qt/PySide6, conexión MadgeTech, importaciones, curvas, perfil ideal, bitácora, análisis de gradiente, exportaciones y pruebas. |
| **3.1** | [`version/v3.1`](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.1) | Corrección de Avisos e interfaz, identificación de sensores, zoom Y, selección de canales en PDF. |
| **3.2** | [`version/v3.2`](https://github.com/BaltazarPatane/MEGAORNO/tree/version/v3.2) | Pausa/reanudación del sondeo y continuidad de la sesión, corte explícito de gradientes, cursor y zoom, nomenclatura unificada y sesión v3 con pausas. |

## Detalles de las entregas

### 3.0

Consolida el visor de tratamientos térmicos en una aplicación de escritorio modular con interoperabilidad WCF, cálculo basado en timestamps de medición y exportaciones independientes. Incluye pruebas automatizadas y ejemplos reproducibles.

### 3.1

Mejora la experiencia de operación y el manejo de errores. Se evita saturar la vista principal con avisos; se conservan datos originales y lecturas inválidas sin introducir valores ficticios. El PDF grafica la selección actual de sensores, sin perder las tablas completas.

Documento completo [CAMBIOS_3.1.md](docs/CAMBIOS_3.1.md).

### 3.2

Permite pausar y reanudar la **recepción de MEGAORNO**, manteniendo el canal de comunicación y la información adquirida. La pausa crea una discontinuidad documentada y evita derivar una tasa de temperatura a través de un intervalo no observado. Las pausas guardadas exigen una sesión v3; los archivos sin pausas conservan compatibilidad v2. Incluye zoom por eje y mejores anotaciones del cursor.

Documento completo [CAMBIOS_3.2.md](docs/CAMBIOS_3.2.md).

## Convenciones para versiones futuras

1. Desarrollar cambios en ramas cortas `feature/<tema>` o `fix/<tema>` basadas en `main`.
2. Validar pruebas y documentación antes de fusionar mediante pull request.
3. Actualizar `CHANGELOG.md`, `VERSION` y la documentación en el mismo cambio.
4. Crear una etiqueta Git inmutable `vX.Y.Z` para cada publicación estable y conservar `version/vX.Y` sólo para mantenimiento de versiones históricas si hace falta.
5. Evitar añadir ZIP de todo el código fuente a Git. Si se necesitan paquetes descargables, publicarlos como artefactos de GitHub Releases, manteniendo el código navegable.

La línea base del proyecto fue creada por el usuario y su equipo. Las ramas aquí documentadas se reconstruyeron desde las entregas ZIP que ya constaban en el repositorio, preservando el historial anterior.
