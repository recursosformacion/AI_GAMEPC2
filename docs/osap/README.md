# Documentación de OSAP

Documentación organizada por **versión general**. Los contratos (`domain/` y `ports/`)
son **API pública congelada**: cambiarlos requiere un ADR.

```
osap/
├── v1/     Base / pre-V2 (arquitectura, API REST, frontend, jobs, datasets, ...)
├── v2/     V2: contratos y diseños congelados
│           · osap-architecture-book.md (fuente de verdad técnica)
│           · architecture-audit.md   (Auditoría 2026, congelada)
│           · provider-contract.md    (Contrato de proveedores)
│           · search-engine-design.md (Search Intelligence V2.1)
│           · normalization-explorable.md (Normalización explicable V2.1.1)
│           · work-matcher-design.md  (WorkMatcher V2.1.2)
│           · ranking-design.md       (Ranking de obras V2.1.3)
│           · evidence-design.md      (Evidence definitivo V2.2.a)
│           · dedup-merge-design.md   (Dedup/Merge V2.2.b)
│           · jobs-design.md          (Jobs V2.2.c)
│           · knowledge-mining-design.md (Knowledge Mining V2.2.d)
│           · web-docs.md             (documentación web)
│           · presentation-v22.md     (presentación 20 diapositivas)
├── v3/     V3: plataforma
│           · api-design.md           (API REST, contrato congelado V3.1.a)
├── adr/    Architecture Decision Records (0001–0028)
└── old/    Documentos obsoletos (histórico, no se editan)
```

## Documentos fundamentales

1. `v2/osap-architecture-book.md` — **fuente de verdad técnica** de OSAP V2.2.
2. `v2/architecture-audit.md` — Auditoría arquitectónica (congelada).
3. `ROADMAP.md` (raíz) — versiones de plataforma.
4. `v2/provider-contract.md` — contrato de proveedores.
5. `v2/search-engine-design.md` — diseño del Search Intelligence.

Chorus (proyecto aparte): `docs/chorus-vision.md`.
