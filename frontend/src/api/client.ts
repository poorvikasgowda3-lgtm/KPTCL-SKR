import type {
  AppConfig,
  ExtractedInterruption,
  ExtractedReportData,
  ExtractedTransformer,
  GeneratedReport,
  ReportData,
  ReportFields,
  ValidationIssue,
} from "../types/report";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");

function connectionError(): ApiRequestError {
  if (import.meta.env.DEV) {
    return new ApiRequestError(
      "The report backend is not running. From the project folder, start it with `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`, then retry.",
    );
  }
  return new ApiRequestError(
    "The report backend is unreachable. Set VITE_API_BASE_URL to the deployed FastAPI URL, allow this frontend origin in FRONTEND_ORIGINS, and rebuild the frontend.",
  );
}

export class ApiRequestError extends Error {
  issues: { level: "error" | "warning" | "info"; message: string }[];

  constructor(message: string, issues: { level: "error" | "warning" | "info"; message: string }[] = []) {
    super(message);
    this.issues = issues;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw connectionError();
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    if (detail && typeof detail === "object") {
      throw new ApiRequestError(
        typeof detail.message === "string" ? detail.message : "The request could not be completed.",
        Array.isArray(detail.issues) ? detail.issues : [],
      );
    }
    if (response.status === 404 && !API_BASE && !import.meta.env.DEV) {
      throw connectionError();
    }
    throw new ApiRequestError(typeof detail === "string" ? detail : "The request could not be completed.");
  }
  return body as T;
}

export const getConfig = () => request<AppConfig>("/api/config");

type OcrResponse = { data: ExtractedReportData; warnings: ValidationIssue[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredStringFields<T extends object>(value: unknown, fields: (keyof T)[]): value is T {
  return isRecord(value) && fields.every((field) => typeof value[field as string] === "string");
}

function parseOcrResponse(value: unknown): OcrResponse {
  const invalid = () => new ApiRequestError(
    "The OCR service returned incomplete or invalid structured readings. Reprocess the photo or enter the readings manually.",
  );
  if (!isRecord(value) || !isRecord(value.data)) throw invalid();
  const data = value.data;
  const reportFields: (keyof ReportFields)[] = [
    "date", "station_name", "peak_load", "peak_load_time",
    "max_high_voltage", "max_low_voltage", "min_high_voltage",
    "min_low_voltage", "station_condition", "signature",
  ];
  const transformerFields: (keyof ExtractedTransformer)[] = ["rating", "load", "time"];
  const interruptionFields: (keyof ExtractedInterruption)[] = [
    "feeder", "start", "end", "reported_duration", "relay", "remarks", "overnight",
  ];
  const isTransformer = (item: unknown) => requiredStringFields<ExtractedTransformer>(item, transformerFields);
  const isInterruption = (item: unknown): item is ExtractedInterruption => {
    if (!isRecord(item)) return false;
    const stringFields = interruptionFields.filter((field) => field !== "overnight") as Exclude<
      keyof ExtractedInterruption,
      "overnight"
    >[];
    const hasOvernightFlag = typeof item.overnight === "boolean";
    return hasOvernightFlag
      && requiredStringFields<Omit<ExtractedInterruption, "overnight">>(item, stringFields);
  };
  if (
    !requiredStringFields<ReportFields>(data.report, reportFields)
    || !Array.isArray(data.transformers) || !data.transformers.every(isTransformer)
    || !Array.isArray(data.interruptions_66) || !data.interruptions_66.every(isInterruption)
    || !Array.isArray(data.interruptions_11) || !data.interruptions_11.every(isInterruption)
    || typeof data.nil_66 !== "boolean" || typeof data.nil_11 !== "boolean"
    || !Array.isArray(data.uncertain_fields) || !data.uncertain_fields.every((item) => typeof item === "string")
    || typeof data.raw_text !== "string"
    || !Array.isArray(value.warnings)
    || !value.warnings.every((item) =>
      isRecord(item)
      && (item.level === "error" || item.level === "warning" || item.level === "info")
      && typeof item.message === "string")
  ) {
    throw invalid();
  }
  return value as OcrResponse;
}

export async function extractReadings(file: File): Promise<OcrResponse> {
  const form = new FormData();
  form.append("image", file);
  const response = await request<unknown>("/api/ocr/extract", { method: "POST", body: form });
  return parseOcrResponse(response);
}

export const generateReport = (report: ReportData) =>
  request<GeneratedReport>("/api/reports/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...report,
      transformers: report.transformers.map(({ rating, load, time }) => ({ rating, load, time })),
      interruptions_66: report.interruptions_66.map(({ feeder, start, end, reported_duration, relay, remarks, overnight }) => ({
        feeder, start, end, reported_duration, relay, remarks, overnight,
      })),
      interruptions_11: report.interruptions_11.map(({ feeder, start, end, reported_duration, relay, remarks, overnight }) => ({
        feeder, start, end, reported_duration, relay, remarks, overnight,
      })),
    }),
  });

export const validateReport = (report: ReportData) =>
  request<GeneratedReport>("/api/reports/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...report,
      transformers: report.transformers.map(({ rating, load, time }) => ({ rating, load, time })),
      interruptions_66: report.interruptions_66.map(({ feeder, start, end, reported_duration, relay, remarks, overnight }) => ({
        feeder, start, end, reported_duration, relay, remarks, overnight,
      })),
      interruptions_11: report.interruptions_11.map(({ feeder, start, end, reported_duration, relay, remarks, overnight }) => ({
        feeder, start, end, reported_duration, relay, remarks, overnight,
      })),
    }),
  });
