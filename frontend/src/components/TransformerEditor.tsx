import type { Transformer } from "../types/report";

type Props = { transformers: Transformer[]; onChange: (items: Transformer[]) => void };

export default function TransformerEditor({ transformers, onChange }: Props) {
  function update(id: string, field: keyof Transformer, value: string) {
    onChange(transformers.map((item) => item.id === id ? { ...item, [field]: value } : item));
  }
  return (
    <section className="card">
      <div className="section-heading compact">
        <div><span className="eyebrow">STATION READINGS</span><h2>Transformer readings</h2></div>
      </div>
      <div className="stack">
        {transformers.map((transformer, index) => (
          <div className="transformer-card" key={transformer.id}>
            <div className="entry-title">
              <strong>Transformer {index + 1}</strong>
              <button className="button button-quiet danger-text" type="button" disabled={transformers.length === 1} onClick={() => onChange(transformers.filter((item) => item.id !== transformer.id))}>Remove</button>
            </div>
            <div className="field-grid three">
              <label>Rating <span>(MVA)</span><input inputMode="decimal" value={transformer.rating} onChange={(e) => update(transformer.id, "rating", e.target.value)} /></label>
              <label>Load <span>(MW)</span><input inputMode="decimal" value={transformer.load} onChange={(e) => update(transformer.id, "load", e.target.value)} /></label>
              <label>Reading time<input type="time" value={transformer.time} onChange={(e) => update(transformer.id, "time", e.target.value)} /></label>
            </div>
          </div>
        ))}
      </div>
      <button className="button button-outline add-button" type="button" onClick={() => onChange([...transformers, { id: crypto.randomUUID(), rating: "", load: "", time: "" }])}>＋ Add transformer</button>
    </section>
  );
}
