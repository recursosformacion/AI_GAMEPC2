# ADR-0024 – Human in the Loop

> Nota: renumerado desde ADR-0009 (en el antiguo `0001-fundamental-decisions.md`)
> para evitar colisión con `0009-osap-resuelve-obras.md`.

## Estado

Aceptado.

### Decisión

El sistema acepta explícitamente la intervención humana cuando ningún proveedor alcanza el nivel de calidad requerido.

### Motivación

No existe actualmente ningún sistema gratuito capaz de convertir de forma fiable cualquier partitura escaneada en un Score perfecto.

Intentar automatizar el 100 % del proceso incrementaría enormemente la complejidad y el coste del proyecto.

### Consecuencias

- El usuario podrá corregir únicamente los elementos ambiguos.
- La intervención humana deberá ser mínima y guiada.
- Todas las correcciones alimentarán la Knowledge Base.
- La intervención humana forma parte del flujo normal del sistema y no representa un error.
