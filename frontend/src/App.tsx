import { useEffect, useState } from "react";
import { ApiRequestError, extractReadings, generateReport, getConfig, validateReport } from "./api/client";
import DraftControls from "./components/DraftControls";
import InterruptionEditor from "./components/InterruptionEditor";
import PhotoUploader from "./components/PhotoUploader";
import ReportPreview from "./components/ReportPreview";
import TransformerEditor from "./components/TransformerEditor";
import { emptyReport, sampleReport } from "./types/report";
import type { AppConfig, GeneratedReport, ReportData, ValidationIssue } from "./types/report";

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState("");
  const [data, setData] = useState<ReportData>(emptyReport);
  const [page, setPage] = useState<"edit" | "final">("edit");
  const [busy, setBusy] = useState(false);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [formError, setFormError] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [report, setReport] = useState<GeneratedReport | null>(null);
  const [originalOcr, setOriginalOcr] = useState<{ data: ReportData; rawText: string } | null>(null);
  const [validationStarted, setValidationStarted] = useState(false);

  useEffect(() => {
    getConfig().then(setConfig).catch((error: Error) => setConfigError(error.message));
  }, []);

  useEffect(() => {
    if (!validationStarted || page !== "edit") return;
    const timeout = window.setTimeout(() => {
      validateReport(data)
        .then((result) => {
          setIssues(result.issues);
          setFormError(result.can_generate ? "" : "Review the highlighted items below before generating the report.");
        })
        .catch((error: Error) => {
          if (error instanceof ApiRequestError) setIssues(error.issues);
          setFormError(error.message);
        });
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [data, page, validationStarted]);

  function updateReport(field: keyof ReportData["report"], value: string) {
    setData((current) => ({ ...current, report: { ...current.report, [field]: value } }));
  }

  async function onExtract(file: File) {
    setBusy(true);
    setFormError("");
    setIssues([]);
    try {
      const result = await extractReadings(file);
      const extracted = result.data;
      const nextData: ReportData = {
        report: extracted.report,
        transformers: extracted.transformers.map((item) => ({ ...item, id: crypto.randomUUID() })),
        interruptions_66: extracted.interruptions_66.map((item) => ({ ...item, id: crypto.randomUUID() })),
        interruptions_11: extracted.interruptions_11.map((item) => ({ ...item, id: crypto.randomUUID() })),
        nil_66: extracted.nil_66,
        nil_11: extracted.nil_11,
        uncertain_fields: extracted.uncertain_fields,
        ocr_confirmed: false,
      };
      setData(nextData);
      setOriginalOcr({
        data: nextData,
        rawText: extracted.raw_text,
      });
      setIssues(result.warnings);
      setPage("edit");
    } finally {
      setBusy(false);
    }
  }

  async function createReport() {
    setBusy(true);
    setFormError("");
    setCopyStatus("");
    setValidationStarted(true);
    try {
      const result = await generateReport(data);
      setIssues(result.issues);
      if (!result.can_generate) {
        setFormError("Review the highlighted items below before generating the report.");
        return;
      }
      setReport(result);
      setPage("final");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      if (error instanceof ApiRequestError) setIssues(error.issues);
      setFormError(error instanceof Error ? error.message : "The report could not be generated.");
    } finally {
      setBusy(false);
    }
  }

  async function copyReport() {
    if (!report?.message) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard is unavailable");
      await navigator.clipboard.writeText(report.message);
      setCopyStatus("Report copied. Paste it into WhatsApp when ready.");
    } catch {
      setCopyStatus("Clipboard permission is unavailable. Select and copy the report text below.");
    }
  }

  function loadDraft(draft: ReportData) {
    setData(draft);
    setReport(null);
    setOriginalOcr(null);
    setIssues([]);
    setValidationStarted(false);
    setPage("edit");
  }

  function startNew() {
    setData(emptyReport());
    setReport(null);
    setOriginalOcr(null);
    setIssues([]);
    setValidationStarted(false);
    setFormError("");
    setCopyStatus("");
    setPage("edit");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const issueList = [...issues];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">⚡</div>
        <div>
          <p className="brand-overline">KPTCL · DAILY REPORT</p>
          <h1>KPTCL Daily Station<br className="mobile-break" /> Report Generator</h1>
        </div>
        <span className="secure-pill">Manual review required</span>
      </header>
      <div className="workflow">
        <span className={page === "edit" ? "workflow-active" : ""}>1&nbsp; Upload &amp; edit</span>
        <span className={page === "final" ? "workflow-active" : ""}>2&nbsp; Review &amp; copy</span>
      </div>
      {configError && <div className="notice notice-warning">{configError} You can still enter readings manually.</div>}
      {page === "edit" ? (
        <>
          <PhotoUploader
            config={config}
            busy={busy}
            onExtract={onExtract}
            onSample={() => { setData(sampleReport()); setOriginalOcr(null); setIssues([]); setFormError(""); setValidationStarted(false); }}
          />
          <DraftControls data={data} onLoad={loadDraft} />
          {data.uncertain_fields.length > 0 && (
            <section className="notice notice-warning uncertainty-box">
              <strong>Check uncertain OCR fields against the notebook</strong>
              <ul>{data.uncertain_fields.map((field, index) => <li key={`${field}-${index}`}>{field}</li>)}</ul>
              <label className="confirm-toggle">
                <input type="checkbox" checked={data.ocr_confirmed} onChange={(event) => setData((current) => ({ ...current, ocr_confirmed: event.target.checked }))} />
                I checked these values against the original notebook
              </label>
            </section>
          )}
          {originalOcr && (
            <details className="draft-controls ocr-reference">
              <summary>Original OCR extraction (reference)</summary>
              {originalOcr.rawText && <><strong>Recognized notebook text</strong><pre className="ocr-text">{originalOcr.rawText}</pre></>}
              <strong>Structured values returned by OCR</strong>
              <pre className="ocr-text">{JSON.stringify({
                report: originalOcr.data.report,
                transformers: originalOcr.data.transformers,
                interruptions_66: originalOcr.data.interruptions_66,
                interruptions_11: originalOcr.data.interruptions_11,
              }, null, 2)}</pre>
            </details>
          )}
          <section className="card">
            <div className="section-heading compact">
              <div><span className="eyebrow">STEP 2</span><h2>Review station readings</h2><p>Correct any extracted value; blank fields are never guessed.</p></div>
              <span className="step-icon" aria-hidden="true">02</span>
            </div>
            <div className="field-grid two">
              <label>Station name<input value={data.report.station_name} onChange={(e) => updateReport("station_name", e.target.value)} /></label>
              <label>Report date<input value={data.report.date} placeholder="DD/MM/YYYY" onChange={(e) => updateReport("date", e.target.value)} /></label>
              <label>Station peak load <span>(MW)</span><input inputMode="decimal" value={data.report.peak_load} onChange={(e) => updateReport("peak_load", e.target.value)} /></label>
              <label>Peak load time<input type="time" value={data.report.peak_load_time} onChange={(e) => updateReport("peak_load_time", e.target.value)} /></label>
              <label>Station condition<input value={data.report.station_condition} onChange={(e) => updateReport("station_condition", e.target.value)} /></label>
              <label>AE(M) station signature<input value={data.report.signature} onChange={(e) => updateReport("signature", e.target.value)} /></label>
            </div>
          </section>
          <TransformerEditor transformers={data.transformers} onChange={(transformers) => setData((current) => ({ ...current, transformers }))} />
          <section className="card">
            <div className="section-heading compact">
              <div><span className="eyebrow">STATION READINGS</span><h2>Voltage readings</h2></div>
            </div>
            <div className="field-grid two">
              <label>Maximum high-side <span>(kV)</span><input inputMode="decimal" value={data.report.max_high_voltage} onChange={(e) => updateReport("max_high_voltage", e.target.value)} /></label>
              <label>Maximum low-side <span>(kV)</span><input inputMode="decimal" value={data.report.max_low_voltage} onChange={(e) => updateReport("max_low_voltage", e.target.value)} /></label>
              <label>Minimum high-side <span>(kV)</span><input inputMode="decimal" value={data.report.min_high_voltage} onChange={(e) => updateReport("min_high_voltage", e.target.value)} /></label>
              <label>Minimum low-side <span>(kV)</span><input inputMode="decimal" value={data.report.min_low_voltage} onChange={(e) => updateReport("min_low_voltage", e.target.value)} /></label>
            </div>
          </section>
          <InterruptionEditor
            voltage="66"
            rows={data.interruptions_66}
            isNil={data.nil_66}
            onRowsChange={(interruptions_66) => setData((current) => ({ ...current, interruptions_66 }))}
            onNilChange={(nil_66) => setData((current) => ({ ...current, nil_66 }))}
          />
          <InterruptionEditor
            voltage="11"
            rows={data.interruptions_11}
            isNil={data.nil_11}
            onRowsChange={(interruptions_11) => setData((current) => ({ ...current, interruptions_11 }))}
            onNilChange={(nil_11) => setData((current) => ({ ...current, nil_11 }))}
          />
          {issueList.length > 0 && (
            <section className="validation-list" aria-live="polite">
              <h2>Review before generating</h2>
              {issueList.map((issue, index) => <div className={`notice notice-${issue.level}`} key={`${issue.message}-${index}`}>{issue.message}</div>)}
            </section>
          )}
          {formError && <div className="notice notice-error" role="alert">{formError}</div>}
          <button className="button button-primary generate-button" type="button" disabled={busy || (validationStarted && issueList.some((issue) => issue.level === "error"))} onClick={() => void createReport()}>
            {busy ? "Preparing report…" : "Generate WhatsApp Report"}
          </button>
          <p className="privacy-note">Notebook images are sent to the configured OCR provider only when you choose extraction. Reports are not sent automatically.</p>
        </>
      ) : report && (
        <>
          <ReportPreview
            message={report.message}
            issues={report.issues}
            onEdit={() => { setPage("edit"); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            onNew={startNew}
            onCopy={copyReport}
          />
          {copyStatus && <div className="notice notice-success copy-status" role="status">{copyStatus}</div>}
          <label className="fallback-label">Selectable text fallback
            <textarea readOnly value={report.message} onFocus={(event) => event.currentTarget.select()} />
          </label>
        </>
      )}
      <footer>For official use, verify every value against the station notebook before sharing.</footer>
    </main>
  );
}
