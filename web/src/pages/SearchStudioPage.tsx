import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Envelope } from "../components/Envelope";
import type { SearchModelBlock } from "../api/types";
import { useSearches } from "../state/searches";
import { useSearchModel } from "../state/searchModel";

type Criteria = Record<string, string>;
type Multi = Record<string, boolean>;

export function SearchStudioPage() {
  const navigate = useNavigate();
  const { data: model, loading, error, load } = useSearchModel();

  const [text, setText] = useState<Criteria>({});
  const [multi, setMulti] = useState<Multi>({});
  const [confidence, setConfidence] = useState(0.5);

  useEffect(() => {
    void load();
  }, [load]);

  const resolve = () => {
    const payload: Record<string, unknown> = {
      query: text["title"] ?? "",
      limit: 20,
      composer: text["composer"] || null,
      title: text["title"] || null,
      catalogue: text["catalogue"] || null,
      confidence,
    };
    const providers = Object.entries(multi).filter(([, v]) => v).map(([k]) => k);
    const formats = Object.entries(multi).filter(([, v]) => v).map(([k]) => k);
    void useSearches.getState().create({
      query: payload.query as string,
      limit: 50,
      composer: payload.composer as string | null,
      title: payload.title as string | null,
      catalogue: payload.catalogue as string | null,
    });
    void providers;
    void formats;
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
      <h1 className="text-xl font-semibold">Search Studio</h1>

      <Envelope loading={loading} error={error} data={model} emptyMessage="Loading search model…">
        {(m) => (
          <>
            <div className="space-y-4">
              {m.blocks.map((block) => (
                <Block
                  key={block.id}
                  block={block}
                  text={text}
                  setText={setText}
                  multi={multi}
                  setMulti={setMulti}
                  confidence={confidence}
                  setConfidence={setConfidence}
                />
              ))}
            </div>

            {summary.length > 0 ? (
              <Card title="Search Summary">
                <p className="mb-2 text-sm text-osap-muted">{phrase}</p>
                <ul className="space-y-1 text-sm">
                  {summary.map((s) => (
                    <li key={s.label} className="flex justify-between">
                      <span className="text-osap-muted">{s.label}</span>
                      <span>{s.value}</span>
                    </li>
                  ))}
                  {confidence > 0 ? (
                    <li className="flex justify-between">
                      <span className="text-osap-muted">Confidence</span>
                      <span>≥ {Math.round(confidence * 100)}%</span>
                    </li>
                  ) : null}
                </ul>
              </Card>
            ) : null}

            <Button onClick={resolve} className="mt-6 w-full">
              Resolve works
            </Button>
          </>
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
  const { block } = props;
  if (block.kind === "text") {
    return (
      <Card title={block.label}>
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
      <Card title={block.label}>
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
      <Card title={block.label}>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-osap-muted">Confidence</span>
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
  return (
    <Card title={block.label}>
      <div className="flex flex-wrap gap-3">
        {block.criteria.map((c) => (
          <label key={c.key} className="flex items-center gap-1 text-sm">
            <input type="checkbox" onChange={(e) => props.setMulti({ ...props.multi, [c.key]: e.target.checked })} />
            {c.label}
          </label>
        ))}
      </div>
    </Card>
  );
}
