"""Web independiente de Chorus — vertical slice con contrato serializable `Score`.

Circuito principal (frontera estable del vertical slice):

    POST /generate  (body JSON = ScoreContract)
        → contract_to_score (Score de dominio)
        → GenerateMaterialsUseCase.generate(score, MaterialType.EXERCISE)
        → StudyMaterial → JSON

La entrada `.mxl` sigue disponible de forma PROVISIONAL en `POST /generate-file`
(conversión con el validador de OSAP) para la demostración desde el navegador y los
tests, mientras no exista productor OSAP del contrato.

Sin persistencia, sin búsqueda, sin resolve, sin auth. Un único caso de uso real.
`import src.chorus.web` no carga módulos de OSAP (la dependencia queda en los
adapters con import lazy).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.chorus.bootstrap.container import Container
from src.chorus.bootstrap.wiring import wire
from src.chorus.contract import ContractError, ScoreContract, contract_to_score, is_readable_contract
from src.chorus.domain.material_type import MaterialType

if TYPE_CHECKING:
    from src.chorus.application.use_cases.generate_materials import GenerateMaterialsUseCase
    from src.chorus.domain.study_material import StudyMaterial
    from src.osap.domain.score import Score

logger = logging.getLogger("chorus.web")


class _InputError(Exception):
    """Entrada no procesable como partitura (mensaje seguro para el usuario)."""


def _build_score_from_mxl(content: bytes, title: str | None = None) -> Score:
    """Frontera PROVISIONAL/legacy: bytes de MXL/MusicXML → `Score` de OSAP.

    Solo para la demostración por fichero mientras no exista un productor del
    contrato. Será sustituida por el transporte del contrato OSAP → Chorus.
    """
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.musical_source import MusicalSource
    from src.osap.domain.output_format import OutputFormat
    from src.osap.domain.quality_level import QualityLevel
    from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
    from src.osap.infrastructure.adapters.validation import BasicValidator

    acquisition = AcquisitionResult(
        provider_id=ProviderId("file"),
        source=MusicalSource(
            source_id=SourceId("file-upload"),
            content=content,
            format=OutputFormat.MUSICXML,
            metadata={"title": title, "composer": None},
        ),
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=OutputFormat.MUSICXML,
    )
    score = BasicValidator().validate(acquisition)
    if score.quality_level == QualityLevel.UNREADABLE:
        raise _InputError("No se ha podido leer la obra como partitura válida.")
    return score


def _material_payload(material: StudyMaterial) -> dict[str, object]:
    """Serializa el `StudyMaterial` real (sin inventar campos)."""
    content = (
        material.content
        if isinstance(material.content, dict)
        else {"text": str(material.content)}
    )
    return {
        "material_type": material.material_type.value,
        "voice": material.voice,
        "metadata": dict(material.metadata),
        "content": content,
    }


def create_chorus_web_app(use_case: GenerateMaterialsUseCase | None = None) -> FastAPI:
    """Aplicación web Chorus (vertical slice). `use_case` es inyectable para tests."""
    materials_use_case = use_case or wire(Container()).generate_materials_use_case()

    app = FastAPI(title="Chorus Web (vertical slice)", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(_INDEX_HTML)

    @app.post("/generate")
    async def generate(request: Request) -> JSONResponse:
        """Frontera estable: recibe un `ScoreContract` serializado (JSON)."""
        raw = (await request.body()).decode("utf-8", errors="replace")
        if not raw.strip():
            return JSONResponse({"error": "No se ha enviado ningún contrato."}, status_code=400)
        try:
            contract = ScoreContract.from_json(raw)
            if not is_readable_contract(contract):
                raise ContractError("La obra no es legible (sin material aprovechable).")
            score = contract_to_score(contract)
            material = materials_use_case.generate(score, MaterialType.EXERCISE)
        except ContractError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception:
            logger.exception("No se ha podido generar el material de estudio")
            return JSONResponse(
                {"error": "No se ha podido generar el material de estudio."},
                status_code=500,
            )
        return JSONResponse(_material_payload(material))

    @app.post("/generate-file")
    async def generate_file(request: Request, title: str | None = None) -> JSONResponse:
        """Entrada PROVISIONAL (legacy): fichero .mxl/.xml en crudo para la demo."""
        raw = await request.body()
        if not raw:
            return JSONResponse({"error": "No se ha enviado ningún archivo."}, status_code=400)
        try:
            score = _build_score_from_mxl(raw, title)
            material = materials_use_case.generate(score, MaterialType.EXERCISE)
        except _InputError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception:
            logger.exception("No se ha podido validar la obra de entrada")
            return JSONResponse({"error": "El archivo no es válido."}, status_code=400)
        return JSONResponse(_material_payload(material))

    return app


_INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chorus — Trabajar una obra</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f7f7f5; color: #23211e; }
  main { max-width: 640px; margin: 0 auto; padding: 24px 16px; }
  h1 { margin: 0; font-size: 26px; }
  .tagline { margin: 4px 0 20px; color: #6b675f; font-size: 14px; }
  section { background: #fff; border: 1px solid #e2dfd8; border-radius: 8px;
            padding: 16px; margin-bottom: 16px; }
  h2 { margin: 0 0 8px; font-size: 16px; }
  .hint { color: #6b675f; font-size: 13px; margin: 0 0 12px; }
  input[type="file"] { display: block; margin-bottom: 12px; }
  button { background: #b84a2c; color: #fff; border: 0; border-radius: 6px;
           padding: 10px 16px; font-size: 14px; cursor: pointer; }
  button:disabled { background: #c9b7ae; cursor: default; }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px;
       margin: 8px 0; font-size: 14px; }
  dt { color: #6b675f; }
  dd { margin: 0; }
  pre { background: #f1efe9; border-radius: 6px; padding: 12px; white-space: pre-wrap;
        font-size: 13px; }
  .error { color: #a11; font-size: 14px; }
</style>
</head>
<body>
<main>
  <h1>Chorus</h1>
  <p class="tagline">Trabajar una obra · generación de material de estudio</p>

  <section id="entrada">
    <h2>Proporciona una obra</h2>
    <p class="hint">
      Demo provisional por fichero .mxl / MusicXML. La frontera estable de Chorus
      recibe el contrato serializable de Score (JSON).
    </p>
    <input id="file" type="file" accept=".mxl,.xml,.musicxml">
    <button id="generate" type="button">Generar material</button>
  </section>

  <section id="status" hidden></section>

  <section id="result" hidden>
    <h2>Material generado</h2>
    <p id="material-type"></p>
    <dl id="metadata"></dl>
    <pre id="content"></pre>
  </section>
</main>
<script>
  var fileInput = document.getElementById("file");
  var button = document.getElementById("generate");
  var statusBox = document.getElementById("status");
  var resultBox = document.getElementById("result");

  function setStatus(text, isError) {
    statusBox.hidden = false;
    statusBox.className = isError ? "error" : "";
    statusBox.textContent = text;
  }

  function setProcessing(on) {
    button.disabled = on;
    button.textContent = on ? "Generando material…" : "Generar material";
    if (on) {
      resultBox.hidden = true;
      setStatus("Generando material…", false);
    }
  }

  function setMeta(label, value) {
    var row = document.createElement("dl");
    var dt = document.createElement("dt");
    var dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    row.appendChild(dt);
    row.appendChild(dd);
    return row;
  }

  function renderResult(data) {
    var meta = data.metadata || {};
    var container = document.getElementById("metadata");
    container.textContent = "";
    document.getElementById("material-type").textContent =
      "Tipo: " + (data.material_type || "—");
    container.appendChild(setMeta("Título", meta.title || "—"));
    if (meta.parts !== null && meta.parts !== undefined) {
      container.appendChild(setMeta("Partes", meta.parts));
    }
    if (meta.measures !== null && meta.measures !== undefined) {
      container.appendChild(setMeta("Compases", meta.measures));
    }
    if (meta.notes !== null && meta.notes !== undefined) {
      container.appendChild(setMeta("Notas", meta.notes));
    }
    if (meta.voices !== null && meta.voices !== undefined) {
      container.appendChild(setMeta("Voces", meta.voices));
    }
    container.appendChild(setMeta("Con letra", meta.has_lyrics ? "sí" : "no"));
    container.appendChild(setMeta("Calidad (QualityLevel)", meta.quality_level));
    var report = meta.quality_report;
    if (report && typeof report === "object") {
      var dims = Object.keys(report).sort().map(function (k) {
        return k + "=" + report[k];
      }).join(", ");
      container.appendChild(setMeta("QualityReport", dims));
    }
    var errors = meta.errors || [];
    var warnings = meta.warnings || [];
    if (errors.length) { container.appendChild(setMeta("Errores", errors.join("; "))); }
    if (warnings.length) { container.appendChild(setMeta("Warnings", warnings.join("; "))); }
    var content = data.content || {};
    document.getElementById("content").textContent = content.text || "";
    statusBox.hidden = true;
    resultBox.hidden = false;
  }

  async function generate() {
    var file = fileInput.files && fileInput.files[0];
    if (!file) { setStatus("Selecciona un archivo primero.", true); return; }
    setProcessing(true);
    try {
      var bytes = await file.arrayBuffer();
      var baseName = file.name.replace(/\\.(mxl|xml|musicxml)$/i, "");
      var url = "/generate-file?title=" + encodeURIComponent(baseName);
      var res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: bytes
      });
      var data = await res.json();
      if (!res.ok) {
        setStatus(data.error || "No se ha podido procesar la obra.", true);
        return;
      }
      renderResult(data);
    } catch (err) {
      setStatus("No se ha podido procesar la obra.", true);
    } finally {
      setProcessing(false);
    }
  }

  button.addEventListener("click", generate);
</script>
</body>
</html>
"""
