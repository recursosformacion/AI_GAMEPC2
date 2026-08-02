# OSAP — Knowledge Base

La Knowledge Base evoluciona de "registro de conversiones" a un **sistema de
aprendizaje estadístico** (reglas + estadísticas, **sin Machine Learning**).

## Registro por evento de resolución

| Campo               | Descripción                                 |
|---------------------|---------------------------------------------|
| documento / obra    | Identidad solicitada                        |
| proveedor           | Proveedor/catálogo usado                    |
| tiempo              | Duración de la operación                    |
| calidad             | `QualityReport` / `QualityLevel` obtenido   |
| errores             | Fallos ocurridos                            |
| intervención humana | ¿Hubo corrección manual?                    |
| resultado           | Éxito / fracaso y resultado                 |

## Uso

Las futuras resoluciones pueden priorizar automáticamente las estrategias con
mayor probabilidad de éxito: por ejemplo, "para obras corales, OpenScore suele
dar `FULL_NOTATION` en < 5s" → el `RankingEngine`/`StrategyPlanner` lo usa como
prioridad, sin redes neuronales.

Se implementa mediante `IKnowledgeBase` (store/find) y un modelo de
`KnowledgeBaseEntry` que acumula las estadísticas consultables por proveedor,
tipo de obra y calidad resultante.
