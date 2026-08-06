# ADR-0027 – Cierre del dominio de OSAP (V2.2)

## Estado

Aceptado. Cierre de V2.2 (`v2.2.0`). Documenta que el **núcleo funcional del dominio de
OSAP está completo**.

## Principios

- **V2.2 completa el dominio funcional de OSAP**: Canonicalizer, Matcher, Ranking,
  Merge, Evidence, Jobs y Knowledge Mining.
- **Knowledge Mining nunca modifica el sistema; solo propone; siempre decide un humano.**
  Es un principio que se mantendrá en V3 y previsiblemente en V4.
- **A partir de V3 el trabajo se centra en exponer el dominio** (API, interfaz web y
  herramientas de administración), manteniendo el núcleo estable.
- Los contratos `domain/` y `ports/` permanecen **congelados**; cualquier cambio requiere
  un ADR.

## Contexto

Tras V2.2.a (Evidence), V2.2.b (Merge), V2.2.c (Jobs) y V2.2.d (Knowledge Mining), el
dominio cubre el ciclo completo: **identificar, ordenar, consolidar, explicar, orquestar y
aprender** (sin decidir). No queda ningún bloque de dominio importante sin cubrir.

## Decisión

- Cerrar la versión de plataforma **V2.2** con el tag `v2.2.0`.
- Declarar el **núcleo funcional del dominio completo**.
- A partir de aquí, el foco pasa a la **productización**: V3.0 API (FastAPI), V3.1 Web,
  V3.2 Administración, V3.3 Knowledge Review.
- No se añaden nuevas piezas de dominio hasta que V3 lo exija explícitamente.

## Consecuencias

- El dominio es estable: V3 **expone** lo que ya existe, no lo reimplementa.
- Knowledge Mining produce sugerencias verificables; la **aplicación humana** llega en
  V3.3 (Knowledge Review).
- Los próximos cambios de código se centran en puertos, infraestructura y capa de
  presentación, sin tocar los contratos congelados.
