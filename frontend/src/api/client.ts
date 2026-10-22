import type { AppConfig, GeneratedReport, ReportData } from "../types/report";

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

export async function extractReadings(file: File): Promise<{ data: ReportData; warnings: {level: string; message: string}[] }> {
  const form = new FormData();
  form.append("image", file);
  return request("/api/ocr/extract", { method: "POST", body: form });
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
