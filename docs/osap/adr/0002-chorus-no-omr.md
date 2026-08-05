# ADR-0002 – Chorus nunca implementará un OMR propio

## Estado

Aceptado.

### Decisión

No se desarrollará un motor OMR propio.

### Motivación

El coste de desarrollo es desproporcionado respecto al valor añadido. Existen soluciones existentes (Audiveris, OMRs comerciales, servicios en la nube) que cubren este espacio.

### Consecuencias

- Toda adquisición musical se realizará mediante proveedores externos a través de puertos.
- El sistema debe diseñarse para soportar múltiples proveedores simultáneamente.
- Si un proveedor desaparece o deja de ser gratuito, se puede sustituir sin modificar el núcleo.
