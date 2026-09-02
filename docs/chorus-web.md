# Chorus — Web independiente (estado real + vertical slice)

> Estado: **primer vertical slice web cerrado con contrato serializable `Score`**
> (ver `docs/chorus-separation.md` para la frontera OSAP ≠ Chorus y el `ScoreContract`).
> Este documento describe qué se ha construido, qué entrada usa, qué caso de uso
> ejecuta y qué queda fuera.

## 1. Principio

```text
OSAP web    → producto OSAP (descubrir, buscar, catálogo, admin, soporte)
Chorus web  → producto Chorus (trabajar con música: estudiar, generar materiales)
```

Chorus web **no** se añade a `web/` de OSAP. Es una aplicación propia dentro del paquete
`src/chorus/web/` (no se ha extraído físicamente; la extracción sigue siendo un
incremento posterior).

## 2. Qué existe hoy

Circuito real implementado y probado de extremo a extremo sobre la **frontera estable**
(contrato serializable):

```text
POST /generate (body JSON = ScoreContract)
   ↓
contract_to_score   [adapter: ScoreContract → Score de dominio]
   ↓
GenerateMaterialsUseCase.generate(score, MaterialType.EXERCISE)
   ↓
ExerciseGenerator
   ↓
StudyMaterial
   ↓
respuesta JSON → navegador → material renderizado
```

### Backend (mínimo)
- `src/chorus/web/app.py` — `create_chorus_web_app()` (FastAPI):
  - `GET /` → página HTML mínima (sin build, sin framework de frontend).
  - `POST /generate` → frontera estable: recibe un `ScoreContract` serializado (JSON),
    lo convierte a `Score` y genera el material.
  - `POST /generate-file` → **entrada PROVISIONAL/legacy**: fichero `.mxl`/`.xml` en
    crudo (demo por navegador mientras no exista productor OSAP del contrato).
- La web invoca siempre el caso de uso `GenerateMaterialsUseCase` (inyectable en la
  factory solo para tests); no duplica la lógica de `ExerciseGenerator`.

### Pantalla y estados
- **Inicial**: «Proporciona una obra» (selector de archivo + botón «Generar material»).
- **Procesando**: «Generando material…» (botón deshabilitado).
- **Éxito**: «Material generado» con datos reales del `StudyMaterial`
  (tipo, título, partes, compases, notas, voces, letra, `QualityLevel`,
  dimensiones del `QualityReport`, warnings cuando existen).
- **Error de entrada**: mensaje controlado (contrato inválido / obra no legible /
  archivo no válido), sin stack traces.
- **Error de generación**: 500 controlado con mensaje genérico; detalle solo en logs.

## 3. Entradas

### Frontera estable (contrato `ScoreContract`)
`POST /generate` recibe el contrato serializado (JSON, `application/json`) definido en
`src/chorus/contract/` y documentado en `docs/chorus-separation.md`. El contrato es
datos puros (JSON), no depende de clases Python de OSAP, y está versionado
(`schema_version`). Las versiones no soportadas y los contratos inválidos se rechazan
con error controlado (400).

### Entrada provisional (`.mxl`), no eliminada
`POST /generate-file` mantiene la demo por fichero (el navegador no puede producir aún
un contrato sin un productor OSAP). Usa el `BasicValidator` de OSAP dentro del adapter
`_build_score_from_mxl` (import lazy, localizado). **Sigue siendo provisional** y será
retirada cuando exista el transporte del contrato OSAP → Chorus.

`import src.chorus.web`, `import src.chorus.contract` e `import src.chorus` no cargan
módulos de OSAP (verificado).

## 4. Cómo se ejecuta

```powershell
python -m uvicorn src.chorus.web.app:create_chorus_web_app --factory `
    --host 127.0.0.1 --port 8123
```

Abrir `http://127.0.0.1:8123/`, seleccionar un `.mxl` y pulsar «Generar material»
(demo provisional por fichero). Esta web es independiente de la SPA de OSAP (`web/`);
no se sirve desde Apache/osap-app.

## 5. Fuera de alcance (no implementado)

- Transporte HTTP OSAP → Chorus (el contrato es datos; el transporte llega en otro
  incremento).
- Búsqueda de obras, adquisición, `resolve`, proveedores, catálogo.
- Autenticación, cuentas, pagos, membresías.
- Persistencia (el flujo es 100 % temporal).
- PDF real, audio real, karaoke, reproductor, biblioteca.
- `REDUCED_SCORE`, `INDIVIDUAL_PART`, `VOCAL_GUIDE` (solo `EXERCISE` hoy).
- Extracción física a repo independiente.

## 6. Tests

- `tests/chorus/test_score_contract.py` (12): serialización/deserialización, round-trip
  con `.mxl` real, equivalencia funcional ante `ExerciseGenerator`, rechazo de
  contratos inválidos/incompatibles, independencia (`import src.chorus.contract` no
  carga OSAP).
- `tests/chorus/test_web.py` (11): página servida; `POST /generate` con contrato real
  desde `.mxl` (partes/compases/notas reales); obra ilegible e JSON inválido → 400;
  `schema_version` no soportada → 400; usa `GenerateMaterialsUseCase`; error de
  generación controlado; `POST /generate-file` (legacy) sigue funcionando.
- Validación: `ruff`, `mypy` y prueba end-to-end real con uvicorn + `.mxl` real.
