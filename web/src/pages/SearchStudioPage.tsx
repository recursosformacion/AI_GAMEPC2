import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import type { SearchModelBlock } from "../api/types";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useSearches } from "../state/searches";
import { useSearchModel } from "../state/searchModel";
import { genresToSearch } from "./studioGenre";
import {
  loadVoicingSelection,
  saveVoicingSelection,
  voicingToSearch,
} from "./studioVoicing";

type Criteria = Record<string, string>;
type Multi = Record<string, boolean>;

const STORAGE_KEY = "osap.studio.multi";

// El título de cada bloque viene del backend; lo localizamos por id.
const BLOCK_LABELS: Record<string, string> = {
  what: "studio.what",
  where: "studio.where",
  what_kind: "studio.whatKind",
  voicing: "studio.voicing",
  genre: "studio.genre",
  quality: "studio.quality",
  options: "studio.options",
};

export function SearchStudioPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: model, loading, error, load } = useSearchModel();

  const [text, setText] = useState<Criteria>({});
  const [multi, setMulti] = useState<Multi>({});
  const [voice, setVoice] = useState("");
  const [confidence, setConfidence] = useState(0.5);
  const initialized = useRef(false);

  useEffect(() => {
    void load();
  }, [load]);

  // Inicializa los checkboxes: activados por defecto salvo el bloque de Opciones,
  // y aplica la selección guardada en localStorage si existe.
  useEffect(() => {
    if (!model || initialized.current) return;
    initialized.current = true;

    const defaults: Multi = {};
    for (const block of model.blocks) {
      if (block.kind === "multi") {
        // voicing se gestiona como desplegable (formación única), no como checkboxes.
        // genre es un filtro opcional: por defecto NINGUNA macro-familia activa (sin
        // restricción); marcar familias restringe a esas categorías.
        if (block.id !== "voicing" && block.id !== "genre") {
          for (const o of block.options) defaults[o] = true;
        } else if (block.id === "genre") {
          for (const o of block.options) defaults[o] = false;
        }
      } else if (block.kind === "boolean") {
        for (const c of block.criteria) defaults[c.key] = false;
      }
    }

    let saved: Multi = {};
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      saved = raw ? (JSON.parse(raw) as Multi) : {};
    } catch {
      saved = {};
    }

    const merged: Multi = {};
    for (const key of Object.keys(defaults)) {
      merged[key] = typeof saved[key] === "boolean" ? saved[key] : Boolean(defaults[key]);
    }
    setMulti(merged);
    const voicingBlock = model.blocks.find((b) => b.id === "voicing");
    const voicingOptions = voicingBlock?.options ?? [];
    const savedVoice = loadVoicingSelection();
    setVoice(voicingOptions.includes(savedVoice) ? savedVoice : "");
  }, [model]);

  const updateMulti = (next: Multi) => {
    setMulti(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const updateVoice = (v: string) => {
    setVoice(v);
    saveVoicingSelection(v);
  };

  const resolve = () => {
    // Bloques multi: `where` -> providers (dónde), `what_kind` -> formats (qué tipo),
    // `genre` -> macro-familias de género (solo el índice OMR las aplica).
    // `voicing` -> formación vocal (solo lo consume el provider CPDL).
    // Solo se envían los checkboxes ACTIVOS; vacío = sin filtro.
    const providers: string[] = [];
    const formats: string[] = [];
    const options: Record<string, boolean> = {};
    const genreOptions = model?.blocks.find((b) => b.id === "genre")?.options ?? [];
    for (const block of model?.blocks ?? []) {
      if (block.kind === "multi") {
        for (const o of block.options) {
          if (multi[o]) {
            if (block.id === "where") providers.push(o);
            else if (block.id === "what_kind") formats.push(o);
          }
        }
      } else if (block.kind === "boolean") {
        for (const c of block.criteria) {
          if (multi[c.key]) options[c.key] = true;
        }
      }
    }
    const voices = voicingToSearch(voice);
    // Género: sin selección O todas las familias marcadas = sin filtro de género.
    const genreFilter = genresToSearch(multi, genreOptions);
    const payload = {
      query: text["title"] ?? "",
      limit: 30,
      page: 1,
      composer: text["composer"] || null,
      title: text["title"] || null,
      catalogue: text["catalogue"] || null,
      formats: formats.length > 0 ? formats : undefined,
      providers: providers.length > 0 ? providers : undefined,
      voices,
      genres: genreFilter,
    };
    void options;
    void confidence;
    // Navega tras lanzar la búsqueda: CandidatesPage mostrará la barra de progreso
    // y los resultados parciales del índice mientras se refina con los providers en vivo.
    void useSearches.getState().create(payload);
    navigate("/candidates");
  };

  const summary: { label: string; value: string }[] = [];
  for (const [k, v] of Object.entries(text)) {
    if (v) summary.push({ label: k, value: v });
  }
  for (const [k, v] of Object.entries(multi)) {
    if (v) summary.push({ label: k, value: "yes" });
  }

  const phrase = summary.map((s) => `${s.label} = ${s.value}`).join(" AND ");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">{t("studio.title")}</h1>
        <p className="text-sm text-osap-muted">{t("studio.saved")}</p>
      </div>

      <Envelope loading={loading} error={error} data={model} emptyMessage={t("states.loading")}>
        {(m) => (
          <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
            {/* Columna principal: criterios */}
            <div className="space-y-4">
              {m.blocks
                .filter((b) => b.id !== "quality" && b.id !== "options")
                .map((block) => (
                  <Block
                    key={block.id}
                    block={block}
                    text={text}
                    setText={setText}
                    multi={multi}
                    setMulti={updateMulti}
                    voice={voice}
                    setVoice={updateVoice}
                    confidence={confidence}
                    setConfidence={setConfidence}
                  />
                ))}
              {/* Instrumento: sin datos categorizados todavía -> deshabilitado. */}
              {m.blocks.some((b) => b.id === "genre") ? (
                <Card title={t("studio.instrument")}>
                  <label className="flex flex-col gap-1 text-xs opacity-60">
                    <select
                      disabled
                      aria-label={t("studio.instrument")}
                      className="rounded border border-osap-border bg-osap-surface px-2 py-1"
                    >
                      <option value="">—</option>
                    </select>
                  </label>
                  <p className="mt-1 text-xs text-osap-muted">{t("studio.instrumentHint")}</p>
                </Card>
              ) : null}
            </div>

            {/* Barra lateral: calidad, opciones, resumen y acción */}
            <aside className="space-y-4 lg:sticky lg:top-2 lg:self-start">
              {m.blocks
                .filter((b) => b.id === "quality" || b.id === "options")
                .map((block) => (
                  <Block
                    key={block.id}
                    block={block}
                    text={text}
                    setText={setText}
                    multi={multi}
                    setMulti={updateMulti}
                    confidence={confidence}
                    setConfidence={setConfidence}
                  />
                ))}

              <Card title={t("studio.summary")}>
                {summary.length > 0 ? (
                  <p className="text-sm text-osap-muted">{phrase}</p>
                ) : (
                  <p className="text-sm text-osap-muted">—</p>
                )}
                {confidence > 0 ? (
                  <p className="mt-2 text-sm text-osap-muted">
                    {t("studio.confidence")}: ≥ {Math.round(confidence * 100)}%
                  </p>
                ) : null}
              </Card>

              <Button onClick={resolve} className="w-full">
                {t("studio.resolve")}
              </Button>
            </aside>
          </div>
        )}
      </Envelope>
    </div>
  );
}

function Block(props: {
  block: SearchModelBlock;
  text: Criteria;
  setText: (c: Criteria) => void;
  multi: Multi;
  setMulti: (m: Multi) => void;
  voice?: string;
  setVoice?: (v: string) => void;
  confidence: number;
  setConfidence: (v: number) => void;
}) {
  const { t } = useI18n();
  const { block } = props;
  const labelKey = BLOCK_LABELS[block.id] as TKey | undefined;
  const title = labelKey ? t(labelKey) : block.label;

  if (block.id === "voicing") {
    return (
      <Card title={title}>
        <label className="flex flex-col gap-1 text-xs">
          <select
            aria-label="formación vocal"
            value={props.voice ?? ""}
            onChange={(e) => props.setVoice?.(e.target.value)}
            className="rounded border border-osap-border bg-osap-surface px-2 py-1"
          >
            <option value="">ALL</option>
            {block.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <p className="mt-1 text-xs text-osap-muted">{t("studio.voicingHint")}</p>
      </Card>
    );
  }

  if (block.kind === "text") {
    return (
      <Card title={title}>
        <div className="grid gap-2 sm:grid-cols-2">
          {block.criteria.map((c) => (
            <label key={c.key} className="flex flex-col text-xs">
              {c.label}
              <input
                aria-label={c.key}
                value={props.text[c.key] ?? ""}
                onChange={(e) => props.setText({ ...props.text, [c.key]: e.target.value })}
                className="mt-1 rounded border border-osap-border bg-osap-surface px-2 py-1"
              />
            </label>
          ))}
        </div>
      </Card>
    );
  }
  if (block.kind === "multi") {
    const chosen = block.options.filter((o) => props.multi[o]).length;
    const allActive = chosen === 0 || chosen === block.options.length;
    return (
      <Card title={title}>
        <div className="flex flex-wrap items-center gap-3">
          {block.id === "genre" ? (
            <button
              type="button"
              title={t("studio.all")}
              aria-label={t("studio.all")}
              aria-pressed={allActive}
              onClick={() => {
                const cleared: Record<string, boolean> = {};
                for (const option of block.options) cleared[option] = false;
                props.setMulti({ ...props.multi, ...cleared });
              }}
              className={`rounded p-1 transition-colors ${
                allActive
                  ? "bg-osap-accent-soft text-osap-accent"
                  : "text-osap-muted hover:bg-osap-surface hover:text-osap-accent"
              }`}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </button>
          ) : null}
          {block.options.map((o) => (
            <label key={o} className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={props.multi[o] ?? false}
                onChange={(e) => props.setMulti({ ...props.multi, [o]: e.target.checked })}
              />
              {o}
            </label>
          ))}
        </div>
        {block.id === "genre" ? (
          <p className="mt-1 text-xs text-osap-muted">{t("studio.genreHint")}</p>
        ) : null}
      </Card>
    );
  }
  if (block.kind === "range") {
    return (
      <Card title={title}>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-osap-muted">{t("studio.confidence")}</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={props.confidence}
            onChange={(e) => props.setConfidence(Number(e.target.value))}
            className="flex-1"
          />
          <span>{Math.round(props.confidence * 100)}%</span>
        </div>
      </Card>
    );
  }
  // kind === "boolean" (Options)
  return (
    <Card title={title}>
      <div className="flex flex-wrap gap-3">
        {block.criteria.map((c) => (
          <label key={c.key} className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={props.multi[c.key] ?? false}
              onChange={(e) => props.setMulti({ ...props.multi, [c.key]: e.target.checked })}
            />
            {c.label}
          </label>
        ))}
      </div>
    </Card>
  );
}
