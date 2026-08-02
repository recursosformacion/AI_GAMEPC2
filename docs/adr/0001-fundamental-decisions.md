# ADR-0001 – Decisiones fundamentales del proyecto
## ADR-0000 – Objetivo del proyecto
### Decisión

El objetivo de Chorus Study Generator es generar materiales de estudio coral, no obtener MusicXML.

### Motivación

Durante el análisis inicial se comprobó que la adquisición de una representación musical fiable es un problema independiente y mucho más amplio que el objetivo principal del proyecto.

Por ello se crea OSAP como plataforma especializada.

### Consecuencias
Chorus nunca se convierte en un proyecto OMR.
OSAP puede evolucionar independientemente.
El éxito del proyecto se mide por la calidad de los materiales de estudio generados, no por el porcentaje de reconocimiento de partituras.

## ADR-0001 – OSAP y Chorus son proyectos independientes

### Decisión

OSAP (Open Score Acquisition Platform) será una plataforma independiente. Chorus Study Generator dependerá únicamente de su API pública.

### Motivación

Permitir reutilizar OSAP en otros proyectos musicales (AI Piano Tutor, Choir Library, Coral Analyzer, etc.) sin acoplamiento.

### Consecuencias

- Chorus nunca conocerá PDF, MusicXML ni Audiveris.
- Chorus solo trabajará con el objeto de dominio `Score`.
- OSAP puede evolucionar y publicarse como proyecto Open Source independiente.
- La comunicación entre ambos proyectos se realiza exclusivamente a través de interfaces bien definidas.

---

## ADR-0002 – Chorus nunca implementará un OMR propio

### Decisión

No se desarrollará un motor OMR propio.

### Motivación

El coste de desarrollo es desproporcionado respecto al valor añadido. Existen soluciones existentes (Audiveris, OMRs comerciales, servicios en la nube) que cubren este espacio.

### Consecuencias

- Toda adquisición musical se realizará mediante proveedores externos a través de puertos.
- El sistema debe diseñarse para soportar múltiples proveedores simultáneamente.
- Si un proveedor desaparece o deja de ser gratuito, se puede sustituir sin modificar el núcleo.

---

## ADR-0003 – El dominio es el centro

### Decisión

Todas las capas externas (infraestructura, proveedores, interfaces de usuario) se adaptan al dominio. Nunca al revés.

### Motivación

El dominio contiene la lógica de negocio fundamental. Si el dominio se adapta a herramientas externas, el sistema pierde coherencia y se vuelve dependiente de detalles de implementación.

### Consecuencias

- Los objetos de dominio (`MusicalDocument`, `MusicalSource`, `Score`, `AcquisitionResult`, `PipelineLog`) no dependen de frameworks ni librerías externas.
- Las decisiones de diseño se toman en el dominio, no en la infraestructura.
- El código del dominio es estable y evoluciona lentamente.
- La arquitectura se mantiene limpia durante años.

---

## ADR-0004 – Chorus nunca procesa formatos, solo objetos de dominio

### Decisión

Chorus no consume ni produce formatos intermedios (MusicXML, MEI, etc.) en su lógica interna. Solo opera con objetos de dominio inmutables.

### Motivación

Esta regla obliga a mantener la arquitectura limpia y evita acoplamientos innecesarios con formatos específicos.

### Consecuencias

- Toda conversión de formato se realiza en la capa de infraestructura de OSAP.
- Chorus es inmune a cambios en formatos externos.
- Los tests de Chorus no dependen de archivos de formato.

---

## ADR-0005 – Calidad como modelo explícito

### Decisión

Cada `Score` posee un `QualityLevel` explícito en lugar de un único valor numérico de confianza.

### Motivación

Un modelo de calidad explícito permite tomar decisiones más ricas y mantenibles sobre qué materiales generar. Facilita la comunicación con el usuario y la evolución del sistema.

### Consecuencias

- Se definen niveles de calidad: Unreadable, Partial structure, Basic melody, Full notation, Human validated.
- Chorus puede decidir qué materiales generar en función del nivel de calidad.
- El Quality Model puede evolucionar independientemente del motor de adquisición.

---

## ADR-0006 – Knowledge Base para experiencias de conversión

### Decisión

Cada conversión alimenta una base de conocimiento que registra qué estrategias funcionaron mejor para cada tipo de documento.

### Motivación

Permite mejorar la selección de proveedores a lo largo del tiempo sin necesidad de aprendizaje automático complejo.

### Consecuencias

- Se registra: documento de entrada, proveedores ejecutados, resultados, intervenciones humanas, estrategia ganadora.
- El `CapabilityAnalyzer` y el `ScoreSelector` pueden consultar esta base para tomar decisiones informadas.
- La base puede empezar siendo estadística y evolucionar hacia modelos más sofisticados.

---

## ADR-0007 – Motor de decisión, no ejecución secuencial

### Decisión

El Score Acquisition Pipeline utiliza un motor de decisión (`CapabilityAnalyzer` + `Selector`) en lugar de ejecutar proveedores en orden de preferencia.

### Motivación

Permite incorporar nuevos proveedores sin modificar el pipeline. El sistema decide qué proveedores ejecutar en función de las capacidades del documento, no de una lista hardcodeada.

### Consecuencias

- Se añaden proveedores registrándolos en el sistema, no modificando el pipeline.
- El `CapabilityAnalyzer` determina qué proveedores son compatibles con cada `MusicalDocument`.
- El `ScoreSelector` escoge el mejor resultado entre múltiples `AcquisitionResults`.

---

## ADR-0008 – Regla de acceso a proveedores externos

### Decisión

Ningún proveedor externo podrá ser utilizado directamente desde Chorus. Siempre se accederá a través de puertos, adaptadores y proveedores.

### Motivación

Garantizar la independencia de Chorus respecto a herramientas externas y facilitar la sustitución de proveedores en el futuro.

### Consecuencias

- Se define un puerto (`IScoreProvider`) en el dominio de OSAP.
- Cada proveedor se implementa como un adaptador que implementa el puerto.
- Chorus solo conoce el puerto, nunca el proveedor concreto.
- Dentro de tres años se podrá cambiar Audiveris por otro OMR sin tocar Chorus.

## ADR-0009 – Human in the Loop
### Decisión

El sistema acepta explícitamente la intervención humana cuando ningún proveedor alcanza el nivel de calidad requerido.

### Motivación

No existe actualmente ningún sistema gratuito capaz de convertir de forma fiable cualquier partitura escaneada en un Score perfecto.

Intentar automatizar el 100 % del proceso incrementaría enormemente la complejidad y el coste del proyecto.

###  Consecuencias
El usuario podrá corregir únicamente los elementos ambiguos.
La intervención humana deberá ser mínima y guiada.
Todas las correcciones alimentarán la Knowledge Base.
La intervención humana forma parte del flujo normal del sistema y no representa un error.