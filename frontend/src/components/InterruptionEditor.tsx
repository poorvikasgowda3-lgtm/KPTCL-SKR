import type { Interruption } from "../types/report";

type Props = {
  voltage: "66" | "11";
  rows: Interruption[];
  isNil: boolean;
  onRowsChange: (items: Interruption[]) => void;
  onNilChange: (value: boolean) => void;
};

export default function InterruptionEditor({ voltage, rows, isNil, onRowsChange, onNilChange }: Props) {
  function update(id: string, field: keyof Interruption, value: string | boolean) {
    onRowsChange(rows.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }
  return (
    <section className="card">
      <div className="section-heading compact">
        <div><span className="eyebrow">INTERRUPTIONS</span><h2>{voltage}KV interruptions</h2></div>
      </div>
      <label className="nil-toggle">
        <input type="checkbox" checked={isNil} onChange={(event) => onNilChange(event.target.checked)} />
        <span>Nil — no interruptions</span>
      </label>
      {!isNil && (
        <>
          {!rows.length && <p className="helper-text">No entries yet. Add an interruption or select Nil if there were none.</p>}
          <div className="stack">
            {rows.map((row, index) => (
              <article className="interruption-card" key={row.id}>
                <div className="entry-title">
                  <strong>Interruption {index + 1}</strong>
                  <button className="button button-quiet danger-text" type="button" onClick={() => onRowsChange(rows.filter((item) => item.id !== row.id))}>Delete</button>
                </div>
                <div className="field-grid two">
                  <label>Feeder number<input value={row.feeder} placeholder="F13" onChange={(e) => update(row.id, "feeder", e.target.value)} /></label>
                  <label>Protection / relay
                    <select value={["EFR", "OCR", "EFR+OCR"].includes(row.relay) ? row.relay : row.relay ? "Other" : ""} onChange={(e) => update(row.id, "relay", e.target.value === "Other" ? "" : e.target.value)}>
                      <option value="">Select type</option><option>EFR</option><option>OCR</option><option>EFR+OCR</option><option value="Other">Other</option>
                    </select>
                    {(row.relay === "" || !["EFR", "OCR", "EFR+OCR"].includes(row.relay)) && (
                      <input className="other-relay" aria-label="Other protection or relay type" value={row.relay} placeholder="Enter protection type" onChange={(e) => update(row.id, "relay", e.target.value)} />
                    )}
                  </label>
                  <label>Start time<input type="time" value={row.start} onChange={(e) => update(row.id, "start", e.target.value)} /></label>
                  <label>End time<input type="time" value={row.end} onChange={(e) => update(row.id, "end", e.target.value)} /></label>
                  <label>Reported duration<input type="text" inputMode="numeric" placeholder="00:04" value={row.reported_duration} onChange={(e) => update(row.id, "reported_duration", e.target.value)} /></label>
                  <label className="remarks-field">Remarks <span>(optional)</span><input value={row.remarks} onChange={(e) => update(row.id, "remarks", e.target.value)} /></label>
                </div>
                <label className="nil-toggle overnight-toggle">
                  <input type="checkbox" checked={row.overnight} onChange={(e) => update(row.id, "overnight", e.target.checked)} />
                  <span>This interruption continued overnight</span>
                </label>
              </article>
            ))}
          </div>
          <button className="button button-outline add-button" type="button" onClick={() => onRowsChange([...rows, { id: crypto.randomUUID(), feeder: "", start: "", end: "", reported_duration: "", relay: "", remarks: "", overnight: false }])}>＋ Add interruption</button>
        </>
      )}
      {isNil && rows.length > 0 && <button className="button button-quiet" type="button" onClick={() => onNilChange(false)}>Show and edit saved entries</button>}
      <p className="helper-text">Notebook-reported durations are preserved. Any elapsed-time difference is only a warning.</p>
    </section>
  );
}
