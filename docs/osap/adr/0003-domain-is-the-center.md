# ADR-0003 – El dominio es el centro

## Estado

Aceptado.

### Decisión

Todas las capas externas (infraestructura, proveedores, interfaces de usuario) se adaptan al dominio. Nunca al revés.

### Motivación

El dominio contiene la lógica de negocio fundamental. Si el dominio se adapta a herramientas externas, el sistema pierde coherencia y se vuelve dependiente de detalles de implementación.

### Consecuencias

- Los objetos de dominio (`MusicalDocument`, `MusicalSource`, `Score`, `AcquisitionResult`, `PipelineLog`) no dependen de frameworks ni librerías externas.
- Las decisiones de diseño se toman en el dominio, no en la infraestructura.
- El código del dominio es estable y evoluciona lentamente.
- La arquitectura se mantiene limpia durante años.
