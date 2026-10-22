import type { ValidationIssue } from "../types/report";

type Props = {
  message: string;
  issues: ValidationIssue[];
  onEdit: () => void;
  onNew: () => void;
  onCopy: () => Promise<void>;
};

export default function ReportPreview({ message, issues, onEdit, onNew, onCopy }: Props) {
  return (
    <section className="card final-card">
      <div className="section-heading">
        <div><span className="eyebrow">STEP 3</span><h2>WhatsApp message</h2><p>Review this text, then paste it into WhatsApp yourself.</p></div>
        <span className="step-icon" aria-hidden="true">03</span>
      </div>
      {issues.filter((issue) => issue.level === "warning").map((issue, index) => (
        <div className="notice notice-warning" key={`${issue.message}-${index}`}>{issue.message}</div>
      ))}
      <pre className="report-preview">{message}</pre>
      <div className="final-actions">
        <button className="button button-primary" type="button" onClick={() => void onCopy()}>Copy Report</button>
        <button className="button button-secondary" type="button" onClick={onEdit}>Edit Readings</button>
        <button className="button button-quiet" type="button" onClick={onNew}>Start New Report</button>
      </div>
    </section>
  );
}
