# Chorus — Frontera arquitectónica OSAP ≠ Chorus

> Decisión y estado real de la frontera entre OSAP y Chorus. Complementa
> `docs/chorus-vision.md` (visión) y `docs/chorus-product.md` (producto). Responde a:
> ¿dónde vive Chorus?, ¿es independiente?, ¿qué dependencia existe hoy?, ¿cuál es la
> frontera futura?

## 1. Decisión arquitectónica

```text
          ┌──────────────┐
          │     OSAP     │  plataforma (descubrir/adquirir/catálogo)
          └──────┬───────┘
                 │
          contrato Score
                 │
          ┌──────▼───────┐
          │    Chorus    │  aplicación (estudiar/analizar/practicar/materiales)
          └──────────────┘
```

Reglas fijadas (consistentes con ADR-0000/0001/0004/0008 y con la decisión de producto):

1. **OSAP y Chorus son productos independientes.** Chorus no es una sección de OSAP ni
   viceversa.
2. **La frontera es el contrato `Score`.** Chorus solo recibe objetos de dominio `Score`
   de OSAP y no conoce el resto del ecosistema (storage, proveedores, resolve, web de OSAP).
3. **Sin dependencia conceptual:** OSAP no "contiene" a Chorus. El subcomando
   `osap chorus-generate` es un *harness de demostración* del contrato, no el entry del
   producto Chorus.
4. **Extracción física posterior:** hoy Chorus vive en el monorepo; se extraerá a su
   propio proyecto cuando el contrato `Score` sea estable y serializable sin romper el
   circuito (ver §6).

## 2. Estado físico actual (auditado)

- Chorus es un paquete Python autocontenido: `src/chorus/` (domain / application /
  ports / infrastructure / bootstrap).
- Vive dentro del repo `osap-api` (monorepo de capas), junto a `src/osap/` y la SPA `web/`
  (osap-app). No se ha movido a otro directorio ni a otro repo (decisión ADR-010:
  separación física incremental y reversible).
- `D:\Proyectos\AI_OSAP\Chorus\` contiene hoy solo copias de configuración
  (`osapx.toml`, `osap.productionx.toml`), sin código.

## 3. Dependencias reales (inventario)

### Chorus → OSAP (acoplamiento técnico del contrato `Score`)
Únicamente dos símbolos de OSAP:

| Fichero | Import | Tipo |
|---|---|---|
| `src/chorus/ports/study_material_generator.py` | `Score` | typing (`TYPE_CHECKING`) |
| `src/chorus/application/use_cases/generate_materials.py` | `Score` | typing (`TYPE_CHECKING`) |
| `src/chorus/infrastructure/generators/exercise_generator.py` | `Score` | typing (`TYPE_CHECKING`) |
| `src/chorus/infrastructure/generators/exercise_generator.py` | `QualityReport` | runtime (`isinstance` sobre `score.metadata["quality_report"]`) |
| `src/chorus/infrastructure/generators/pdf_generator.py` / `audio_generator.py` | `Score` | typing (`TYPE_CHECKING`) |

Consecuencia: **`import src.chorus` ya no carga módulos de OSAP** (todo el acoplamiento
de tipos es typing-only). La única dependencia runtime restante es `QualityReport`
en `ExerciseGenerator`, necesaria para leer la calidad real del Score.

### OSAP → Chorus
Un único punto: `src/osap/cli/main.py` (`_run_chorus_generate`, import lazy dentro de la
función, subcomando `chorus-generate`). Solo se activa al ejecutar ese subcomando; el
módulo `osap.cli.main` no importa chorus al cargarse. `tests/osap/**` no importa Chorus.

### No acoplados
- `src/shared/**`: sin consumidores (ni OSAP ni Chorus). No forma parte de la frontera.
- Configuración (`osap.toml` y derivados): sin secciones de chorus.
- Web `web/src/**`: sin acoplamiento a Chorus (solo comentarios históricos).
- CI/Docker/tooling: no existen workflows ni Dockerfiles en este repo.

### Compartidos entre paquetes
- Fixtures de test `.mxl` (`tests/fixtures/musicxml/real_short.mxl`, `real_large.mxl`),
  usadas por tests de OSAP y de Chorus.
- Una única distribución en `pyproject.toml` empaqueta `src/` completo
  (`name = "chorus-study-generator"`, console script `osap`).

## 4. El contrato mínimo OSAP → Chorus (`ScoreContract`)

**Necesidad real:** para generar un material, Chorus necesita conocer la obra con la que
trabaja. El contrato **`ScoreContract`** (`src/chorus/contract/`, `schema_version=1`)
representa **una obra ya validada y estructurada en forma de `Score`**, lista para
`GenerateMaterialsUseCase`. NO representa búsqueda ni adquisición.

**Qué contiene (datos que usa Chorus):**

- identidad: `title`, `composer`;
- estructura: `parts`, `measures`, `notes`, `voices`, `has_lyrics`;
- calidad: `quality.level` (0-4) + `quality.report` (dimensiones `str → [0,1]`);
- diagnósticos: `errors`, `warnings`.

**Qué queda deliberadamente fuera** (decisión consciente, no pérdida silenciosa):

- `content` (bytes de la obra original): Chorus no lo usa hoy; marcador vacío al reconstruir.
- `score_id` interno de OSAP: no se transporta; id marcador al reconstruir.
- `valid`: derivable (`quality.level > 0`); no se serializa.
- Detalles internos de OSAP (proveedores, resolución, adquisición, storage).

**Independencia:** el contrato se expresa como datos (dict/JSON) y **no importa clases
Python de OSAP** (verificado: `import src.chorus.contract` no carga módulos de OSAP).
Los adaptadores `score_to_contract` / `contract_to_score` viven en
`src/chorus/contract/bridge.py` con imports de OSAP lazy y localizados.

**Versionado:** mínimo y explícito mediante `schema_version` (entero). Versiones no
soportadas se rechazan de forma controlada (`ContractError`).

**Estado:** contrato establecido y probado (round-trip real + equivalencia funcional ante
`ExerciseGenerator`). El **transporte** HTTP OSAP → Chorus y la sustitución definitiva de
la entrada provisional `.mxl` quedan para incrementos posteriores; hoy la web recibe el
contrato en `POST /generate` y mantiene `/generate-file` como demo provisional.

## 5. Criterios para la extracción física (incremento futuro)

La extracción de `src/chorus` a proyecto propio (directorio hermano o repo) se hará
cuando se cumplan todos:

1. El `ScoreContract` esté producido por OSAP (hoy existe el contrato; el productor
   serializable y su transporte por red están pendientes).
2. El circuito actual siga funcionando (tests end-to-end) sin importar OSAP desde
   Chorus en runtime (hoy: solo adapters con import lazy; el `.mxl` provisional aún
   usa el validador de OSAP en la web).
3. Los fixtures `.mxl` compartidos tengan dueño claro (p. ej. copia en Chorus o corpus
   externo).
4. Se defina el packaging de cada producto (pyproject propio, console script `chorus`
   frente a `osap`) sin distribución mixta.
5. Se separe el harness `osap chorus-generate` (demo) del entry real de Chorus.

Mientras no se cumplan, se mantiene el monorepo con la frontera documentada aquí.

## 6. Cierre del incremento

- Frontera conceptual: **independiente** (productos distintos, reglas 1-4).
- Frontera física: **monorepo** (paquete `src/chorus` autocontenido; extracción futura).
- Contrato serializable: **`ScoreContract` establecido** (JSON, `schema_version`, sin
  clases Python de OSAP), con adaptadores `score_to_contract` / `contract_to_score`.
- Dependencia funcional de OSAP: queda en los adaptadores de frontera (import lazy:
  contrato ↔ Score) y en la demo provisional `.mxl` de la web; `import src.chorus`,
  `import src.chorus.contract` e `import src.chorus.web` no cargan OSAP.
- Sin transporte HTTP OSAP → Chorus, sin stubs conectados, sin abstracciones sin
  consumidor.
