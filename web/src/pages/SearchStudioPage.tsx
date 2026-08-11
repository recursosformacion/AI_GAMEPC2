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

type Criteria = Record<string, string>;
type Multi = Record<string, boolean>;

const STORAGE_KEY = "osap.studio.multi";

// El título de cada bloque viene del backend; lo localizamos por id.
const BLOCK_LABELS: Record<string, string> = {
  what: "studio.what",
  where: "studio.where",
  what_kind: "studio.whatKind",
  quality: "studio.quality",
  options: "studio.options",
};

export function SearchStudioPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: model, loading, error, load } = useSearchModel();

  const [text, setText] = useState<Criteria>({});
  const [multi, setMulti] = useState<Multi>({});
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
        for (const o of block.options) defaults[o] = true;
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
  }, [model]);

  const updateMulti = (next: Multi) => {
    setMulti(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const resolve = () => {
    const payload: Record<string, unknown> = {
      query: text["title"] ?? "",
      limit: 20,
      composer: text["composer"] || null,
      title: text["title"] || null,
      catalogue: text["catalogue"] || null,
      confidence,
    };
    void useSearches.getState().create({
      query: payload.query as string,
      limit: 50,
      composer: payload.composer as string | null,
      title: payload.title as string | null,
      catalogue: payload.catalogue as string | null,
    });
    void payload;
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
                    confidence={confidence}
                    setConfidence={setConfidence}
                  />
                ))}
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
  confidence: number;
  setConfidence: (v: number) => void;
}) {
  const { t } = useI18n();
  const { block } = props;
  const labelKey = BLOCK_LABELS[block.id] as TKey | undefined;
  const title = labelKey ? t(labelKey) : block.label;

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
    return (
      <Card title={title}>
        <div className="flex flex-wrap gap-3">
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
