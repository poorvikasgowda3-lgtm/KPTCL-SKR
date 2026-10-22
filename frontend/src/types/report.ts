export type Transformer = {
  id: string;
  rating: string;
  load: string;
  time: string;
};

export type Interruption = {
  id: string;
  feeder: string;
  start: string;
  end: string;
  reported_duration: string;
  relay: string;
  remarks: string;
  overnight: boolean;
};

export type ReportFields = {
  date: string;
  station_name: string;
  peak_load: string;
  peak_load_time: string;
  max_high_voltage: string;
  max_low_voltage: string;
  min_high_voltage: string;
  min_low_voltage: string;
  station_condition: string;
  signature: string;
};

export type ReportData = {
  report: ReportFields;
  transformers: Transformer[];
  interruptions_66: Interruption[];
  interruptions_11: Interruption[];
  nil_66: boolean;
  nil_11: boolean;
  uncertain_fields: string[];
  ocr_confirmed: boolean;
};

export type ValidationIssue = {
  level: "error" | "warning" | "info";
  message: string;
};

export type AppConfig = {
  title: string;
  ocr_configured: boolean;
  sample_mode: boolean;
  max_upload_bytes: number;
  draft_storage: string;
  supported_image_types: string[];
};

export type GeneratedReport = {
  message: string;
  issues: ValidationIssue[];
  can_generate: boolean;
};

export const emptyReport = (): ReportData => ({
  report: {
    date: "",
    station_name: "",
    peak_load: "",
    peak_load_time: "",
    max_high_voltage: "",
    max_low_voltage: "",
    min_high_voltage: "",
    min_low_voltage: "",
    station_condition: "",
    signature: "",
  },
  transformers: [{ id: crypto.randomUUID(), rating: "", load: "", time: "" }],
  interruptions_66: [],
  interruptions_11: [],
  nil_66: false,
  nil_11: false,
  uncertain_fields: [],
  ocr_confirmed: false,
});

export const sampleReport = (): ReportData => ({
  report: {
    date: "22/10/2026",
    station_name: "SAMPLE 110KV STATION",
    peak_load: "18.6",
    peak_load_time: "19:30",
    max_high_voltage: "112",
    max_low_voltage: "11.2",
    min_high_voltage: "108",
    min_low_voltage: "10.8",
    station_condition: "Normal",
    signature: "SAMPLE STATION",
  },
  transformers: [
    { id: crypto.randomUUID(), rating: "20", load: "9.2", time: "19:30" },
    { id: crypto.randomUUID(), rating: "20", load: "9.4", time: "19:30" },
  ],
  interruptions_66: [],
  interruptions_11: [
    {
      id: crypto.randomUUID(),
      feeder: "F13",
      start: "07:51",
      end: "08:01",
      reported_duration: "00:04",
      relay: "EFR+OCR",
      remarks: "",
      overnight: false,
    },
  ],
  nil_66: true,
  nil_11: false,
  uncertain_fields: [],
  ocr_confirmed: true,
});
