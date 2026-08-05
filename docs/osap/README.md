# Documentación de OSAP

Documentación organizada por **versión general**. Los contratos (`domain/` y `ports/`)
son **API pública congelada**: cambiarlos requiere un ADR.

```
osap/
├── v1/     Base / pre-V2 (arquitectura, API REST, frontend, jobs, datasets, ...)
├── v2/     V2: contratos y diseños congelados
│           · architecture-audit.md   (Auditoría 2026, congelada)
│           · provider-contract.md    (Contrato de proveedores)
│           · search-engine-design.md (Search Intelligence V2.1)
│           · normalization-explorable.md (Normalización explicable V2.1.1)
│           · work-matcher-design.md  (WorkMatcher V2.1.2)
│           · ranking-design.md       (Ranking de obras V2.1.3)
│           · evidence-design.md      (Evidence definitivo V2.2.a)
├── adr/    Architecture Decision Records (0001–0023)
└── old/    Documentos obsoletos (histórico, no se editan)
```

## Documentos fundamentales

1. `v2/architecture-audit.md` — Auditoría arquitectónica (congelada).
2. `ROADMAP.md` (raíz) — versiones de plataforma.
3. `v2/provider-contract.md` — contrato de proveedores.
4. `v2/search-engine-design.md` — diseño del Search Intelligence.

Chorus (proyecto aparte): `docs/chorus-vision.md`.
