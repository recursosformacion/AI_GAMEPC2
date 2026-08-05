# ADR-0006 – Knowledge Base para experiencias de conversión

## Estado

Aceptado.

### Decisión

Cada conversión alimenta una base de conocimiento que registra qué estrategias funcionaron mejor para cada tipo de documento.

### Motivación

Permite mejorar la selección de proveedores a lo largo del tiempo sin necesidad de aprendizaje automático complejo.

### Consecuencias

- Se registra: documento de entrada, proveedores ejecutados, resultados, intervenciones humanas, estrategia ganadora.
- El `CapabilityAnalyzer` y el `ScoreSelector` pueden consultar esta base para tomar decisiones informadas.
- La base puede empezar siendo estadística y evolucionar hacia modelos más sofisticados.
