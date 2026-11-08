# One-off

Material de análisis, evaluación y migración histórica. **No es código de producción** y no
debe ser invocado por servicios, timers, tests ni la aplicación.

Si un script de esta carpeta pasa a ser recurrente:

1. muévelo a `script/`;
2. añade docstring de propósito y uso;
3. regístralo en `docs/osap/scripts.md`;
4. añade una prueba si toma decisiones sobre datos.
