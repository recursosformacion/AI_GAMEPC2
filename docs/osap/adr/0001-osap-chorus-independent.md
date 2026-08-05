# ADR-0001 – OSAP y Chorus son proyectos independientes

## Estado

Aceptado.

### Decisión

OSAP (Open Score Acquisition Platform) será una plataforma independiente. Chorus Study Generator dependerá únicamente de su API pública.

### Motivación

Permitir reutilizar OSAP en otros proyectos musicales (AI Piano Tutor, Choir Library, Coral Analyzer, etc.) sin acoplamiento.

### Consecuencias

- Chorus nunca conocerá PDF, MusicXML ni Audiveris.
- Chorus solo trabajará con el objeto de dominio `Score`.
- OSAP puede evolucionar y publicarse como proyecto Open Source independiente.
- La comunicación entre ambos proyectos se realiza exclusivamente a través de interfaces bien definidas.
