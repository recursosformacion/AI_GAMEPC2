# ADR-0004 – Chorus nunca procesa formatos, solo objetos de dominio

## Estado

Aceptado.

### Decisión

Chorus no consume ni produce formatos intermedios (MusicXML, MEI, etc.) en su lógica interna. Solo opera con objetos de dominio inmutables.

### Motivación

Esta regla obliga a mantener la arquitectura limpia y evita acoplamientos innecesarios con formatos específicos.

### Consecuencias

- Toda conversión de formato se realiza en la capa de infraestructura de OSAP.
- Chorus es inmune a cambios en formatos externos.
- Los tests de Chorus no dependen de archivos de formato.
