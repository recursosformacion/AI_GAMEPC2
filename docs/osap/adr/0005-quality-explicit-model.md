# ADR-0005 – Calidad como modelo explícito

## Estado

Aceptado.

### Decisión

Cada `Score` posee un `QualityLevel` explícito en lugar de un único valor numérico de confianza.

### Motivación

Un modelo de calidad explícito permite tomar decisiones más ricas y mantenibles sobre qué materiales generar. Facilita la comunicación con el usuario y la evolución del sistema.

### Consecuencias

- Se definen niveles de calidad: Unreadable, Partial structure, Basic melody, Full notation, Human validated.
- Chorus puede decidir qué materiales generar en función del nivel de calidad.
- El Quality Model puede evolucionar independientemente del motor de adquisición.
