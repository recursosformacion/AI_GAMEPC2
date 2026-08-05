# ADR-0008 – Regla de acceso a proveedores externos

## Estado

Aceptado.

### Decisión

Ningún proveedor externo podrá ser utilizado directamente desde Chorus. Siempre se accederá a través de puertos, adaptadores y proveedores.

### Motivación

Garantizar la independencia de Chorus respecto a herramientas externas y facilitar la sustitución de proveedores en el futuro.

### Consecuencias

- Se define un puerto (`IScoreProvider`) en el dominio de OSAP.
- Cada proveedor se implementa como un adaptador que implementa el puerto.
- Chorus solo conoce el puerto, nunca el proveedor concreto.
- Dentro de tres años se podrá cambiar Audiveris por otro OMR sin tocar Chorus.
