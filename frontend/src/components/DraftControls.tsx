import { useEffect, useState } from "react";
import type { ReportData } from "../types/report";

const STORAGE_KEY = "kptcl-local-drafts-v1";
type SavedDraft = { name: string; savedAt: string; data: ReportData };

function readDrafts(): SavedDraft[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed as SavedDraft[] : [];
  } catch {
    return [];
  }
}

export default function DraftControls({ data, onLoad }: { data: ReportData; onLoad: (data: ReportData) => void }) {
  const [drafts, setDrafts] = useState<SavedDraft[]>([]);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => setDrafts(readDrafts()), []);

  function saveDraft() {
    const draftName = name.trim();
    if (!draftName) {
      setMessage("Enter a draft name first.");
      return;
    }
    const next = [...drafts.filter((draft) => draft.name !== draftName), { name: draftName, savedAt: new Date().toISOString(), data }];
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setDrafts(next);
      setMessage("Draft saved in this browser.");
    } catch {
      setMessage("Could not save this draft in browser storage.");
    }
  }

  return (
    <details className="draft-controls">
      <summary>Save or open a local draft</summary>
      <p className="helper-text">Drafts are stored in this browser only, without encryption. Photos are not stored.</p>
      <div className="draft-row">
        <input value={name} placeholder="Draft name" onChange={(e) => setName(e.target.value)} aria-label="Draft name" />
        <button className="button button-secondary" type="button" onClick={saveDraft}>Save</button>
      </div>
      {drafts.map((draft) => (
        <div className="saved-draft" key={draft.name}>
          <span>{draft.name}</span>
          <div>
            <button className="button button-quiet" type="button" onClick={() => { onLoad(draft.data); setMessage(`Opened ${draft.name}.`); }}>Open</button>
            <button className="button button-quiet danger-text" type="button" onClick={() => {
              const next = drafts.filter((item) => item.name !== draft.name);
              localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
              setDrafts(next);
              setMessage(`Deleted ${draft.name}.`);
            }}>Delete</button>
          </div>
        </div>
      ))}
      {message && <p className="helper-text" role="status">{message}</p>}
    </details>
  );
}
