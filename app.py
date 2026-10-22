from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image

from ocr_service import (
    OCRConfigurationError,
    OCRError,
    extract_readings,
    is_configured,
    preprocess_image,
)
from report_generator import generate_report
from validators import validate_report


APP_DIR = Path(__file__).resolve().parent
DRAFT_DIR = APP_DIR / "drafts"
CONFIG_PATH = APP_DIR / "station_configs.json"
DEFAULT_STATION = {
    "station_name": "",
    "signature": "",
    "transformers": [{"rating": "", "load": "", "time": ""}],
}

st.set_page_config(
    page_title="KPTCL Daily Station Report Generator",
    page_icon="⚡",
    layout="centered",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 900px; padding: 1.25rem 1rem 3rem;}
    div.stButton > button, div.stDownloadButton > button {
        min-height: 2.8rem; width: 100%; font-weight: 600;
    }
    input, textarea {font-size: 1rem !important;}
    [data-testid="stMetric"] {padding: .6rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("KPTCL Daily Station Report Generator")
st.caption("Turn notebook readings into a reviewed WhatsApp report. Nothing is sent automatically.")
if not is_configured():
    st.info(
        "Handwriting recognition is not configured. Set GEMINI_API_KEY in your environment "
        "or Streamlit secrets and restart the app. Manual entry and fictional sample mode "
        "are available without a key."
    )


def init_state() -> None:
    defaults: dict[str, Any] = {
        "report": {
            "date": "",
            "station_name": "",
            "peak_load": "",
            "peak_load_time": "",
            "max_high_voltage": "",
            "max_low_voltage": "",
            "min_high_voltage": "",
            "min_low_voltage": "",
            "station_condition": "",
            "signature": "",
        },
        "transformers": [dict(item) for item in DEFAULT_STATION["transformers"]],
        "interruptions_66": [],
        "interruptions_11": [],
        "nil_66": False,
        "nil_11": False,
        "ocr_text": "",
        "uncertain_fields": [],
        "image_bytes": None,
        "image_name": None,
        "last_report": "",
        "editable_report": "",
        "ocr_confirmed": False,
        "form_revision": 0,
        "image_widget_revision": 0,
        "transformer_revision": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def read_configs() -> dict[str, dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Could not read saved station configurations: {exc}")
        return {}


def write_configs(configs: dict[str, dict[str, Any]]) -> None:
    CONFIG_PATH.write_text(json.dumps(configs, indent=2, ensure_ascii=False), encoding="utf-8")


def fresh_id() -> str:
    return uuid.uuid4().hex[:10]


def normalize_transformers(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    return [
        {
            "rating": str(row.get("rating", "") or ""),
            "load": str(row.get("load", "") or ""),
            "time": str(row.get("time", "") or ""),
        }
        for row in items
        if isinstance(row, dict)
    ]


def normalize_interruptions(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, str]] = []
    for row in items:
        if isinstance(row, dict):
            normalized.append(
                {
                    "id": str(row.get("id") or fresh_id()),
                    "feeder": str(row.get("feeder", "") or ""),
                    "start": str(row.get("start", "") or ""),
                    "end": str(row.get("end", "") or ""),
                    "reported_duration": str(row.get("reported_duration", "") or ""),
                    "relay": str(row.get("relay", "") or ""),
                    "remarks": str(row.get("remarks", "") or ""),
                    "overnight": bool(row.get("overnight", False)),
                }
            )
    return normalized


def load_report_data(data: dict[str, Any]) -> None:
    report = data.get("report", {})
    for key in st.session_state.report:
        st.session_state.report[key] = str(report.get(key, "") or "")
    st.session_state.transformers = normalize_transformers(data.get("transformers", []))
    st.session_state.interruptions_66 = normalize_interruptions(data.get("interruptions_66", []))
    st.session_state.interruptions_11 = normalize_interruptions(data.get("interruptions_11", []))
    st.session_state.nil_66 = bool(data.get("nil_66", False))
    st.session_state.nil_11 = bool(data.get("nil_11", False))
    st.session_state.uncertain_fields = data.get("uncertain_fields", [])
    st.session_state.ocr_text = str(data.get("ocr_text", "") or "")
    st.session_state.ocr_confirmed = False
    st.session_state.last_report = ""
    st.session_state.editable_report = ""
    st.session_state.form_revision += 1
    st.session_state.transformer_revision += 1


def current_data() -> dict[str, Any]:
    return {
        "report": dict(st.session_state.report),
        "transformers": normalize_transformers(st.session_state.transformers),
        "interruptions_66": normalize_interruptions(st.session_state.interruptions_66),
        "interruptions_11": normalize_interruptions(st.session_state.interruptions_11),
        "nil_66": bool(st.session_state.nil_66),
        "nil_11": bool(st.session_state.nil_11),
        "uncertain_fields": list(st.session_state.uncertain_fields),
        "ocr_text": st.session_state.ocr_text,
    }


def show_interruption_editor(section_key: str, title: str) -> None:
    st.subheader(title)
    nil_key = f"nil_{section_key}"
    rows_key = f"interruptions_{section_key}"
    nil_value = st.checkbox(
        "Nil — no interruptions",
        value=st.session_state[nil_key],
        key=f"ui_{nil_key}_{st.session_state.form_revision}",
    )
    st.session_state[nil_key] = nil_value
    if st.session_state[nil_key]:
        return

    rows = st.session_state[rows_key]
    for index, row in enumerate(rows):
        with st.container(border=True):
            st.markdown(f"**Interruption {index + 1}**")
            first, second = st.columns(2)
            row["feeder"] = first.text_input(
                "Feeder (e.g. F13)", value=row["feeder"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_feeder"
            )
            row["relay"] = second.text_input(
                "Protection / relay", value=row["relay"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_relay",
                placeholder="EFR, OCR, EFR+OCR",
            )
            start_col, end_col, duration_col = st.columns(3)
            row["start"] = start_col.text_input(
                "Start time", value=row["start"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_start",
                placeholder="07:51",
            )
            row["end"] = end_col.text_input(
                "End time", value=row["end"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_end",
                placeholder="08:01",
            )
            row["reported_duration"] = duration_col.text_input(
                "Notebook duration", value=row["reported_duration"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_duration", placeholder="00:04",
                help="Keep the notebook's official duration. It is never replaced automatically.",
            )
            row["remarks"] = st.text_input(
                "Remarks (optional)", value=row["remarks"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_remarks"
            )
            row["overnight"] = st.checkbox(
                "This interruption continued overnight",
                value=row["overnight"],
                key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_overnight",
            )
            if st.button("Delete interruption", key=f"{section_key}_{row['id']}_{st.session_state.form_revision}_delete"):
                st.session_state[rows_key] = [entry for entry in rows if entry["id"] != row["id"]]
                st.rerun()
    if st.button("＋ Add interruption", key=f"{section_key}_{st.session_state.form_revision}_add", type="secondary"):
        rows.append(
            {
                "id": fresh_id(), "feeder": "", "start": "", "end": "",
                "reported_duration": "", "relay": "", "remarks": "", "overnight": False,
            }
        )
        st.session_state[rows_key] = rows
        st.session_state[nil_key] = False
        st.rerun()


init_state()

with st.expander("Station setup and saved configurations", expanded=False):
    configs = read_configs()
    config_col, load_col = st.columns([3, 1])
    config_name = config_col.text_input("Configuration name", placeholder="e.g. North Station")
    if configs:
        selected_config = load_col.selectbox("Saved", ["—"] + sorted(configs.keys()), label_visibility="collapsed")
        if selected_config != "—" and st.button("Load configuration", key="load_config"):
            saved = configs[selected_config]
            st.session_state.report["station_name"] = str(saved.get("station_name", ""))
            st.session_state.report["signature"] = str(saved.get("signature", ""))
            st.session_state.transformers = normalize_transformers(saved.get("transformers", []))
            st.session_state.form_revision += 1
            st.session_state.transformer_revision += 1
            st.session_state.last_report = ""
            st.session_state.editable_report = ""
            st.rerun()
    else:
        load_col.caption("No saved configurations")
    if st.button("Save current station setup", key="save_config"):
        if not config_name.strip():
            st.warning("Enter a configuration name first.")
        else:
            configs[config_name.strip()] = {
                "station_name": st.session_state.report["station_name"],
                "signature": st.session_state.report["signature"],
                "transformers": normalize_transformers(st.session_state.transformers),
            }
            try:
                write_configs(configs)
                st.success("Station configuration saved on this device.")
            except OSError as exc:
                st.error(f"Could not save station configuration: {exc}")

with st.expander("Open or save a local draft", expanded=False):
    try:
        DRAFT_DIR.mkdir(exist_ok=True)
        draft_names = sorted(p.stem for p in DRAFT_DIR.glob("*.json"))
    except OSError as exc:
        draft_names = []
        st.warning(f"Local draft storage is unavailable: {exc}")
    draft_col, draft_load_col = st.columns([3, 1])
    draft_name = draft_col.text_input("Draft name", placeholder="e.g. daily-report")
    selected_draft = draft_load_col.selectbox(
        "Available drafts", ["—"] + draft_names, label_visibility="collapsed"
    )
    save_col, open_col = st.columns(2)
    if save_col.button("Save draft on this device", key="save_draft"):
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", draft_name.strip()).strip("_")
        if not safe_name:
            st.warning("Enter a draft name using letters or numbers.")
        else:
            try:
                (DRAFT_DIR / f"{safe_name}.json").write_text(
                    json.dumps(current_data(), ensure_ascii=False, indent=2), encoding="utf-8"
                )
                st.success("Draft saved locally. Uploaded images are not included.")
                st.rerun()
            except OSError as exc:
                st.error(f"Could not save draft: {exc}")
    if open_col.button("Open selected draft", key="open_draft", disabled=selected_draft == "—"):
        try:
            content = json.loads((DRAFT_DIR / f"{selected_draft}.json").read_text(encoding="utf-8"))
            if not isinstance(content, dict):
                raise ValueError("Draft contents are not a JSON object.")
            load_report_data(content)
            st.success(f"Opened draft: {selected_draft}")
            st.rerun()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            st.error(f"Could not open draft: {exc}")

st.divider()
st.header("Step 1: Upload Notebook Photo")
st.caption("Take a clear, well-lit photo or select a saved image. You can review the processed image before OCR.")
camera_file = st.camera_input("Take a notebook photo", key=f"camera_{st.session_state.image_widget_revision}")
uploaded_file = st.file_uploader(
    "Or upload a notebook image", type=["png", "jpg", "jpeg", "webp", "bmp"],
    key=f"upload_{st.session_state.image_widget_revision}",
)
chosen_image = camera_file if camera_file is not None else uploaded_file
if chosen_image is not None:
    new_bytes = chosen_image.getvalue()
    if new_bytes != st.session_state.image_bytes:
        st.session_state.image_bytes = new_bytes
        st.session_state.image_name = chosen_image.name or "camera-photo"
if st.session_state.image_bytes:
    try:
        original = Image.open(__import__("io").BytesIO(st.session_state.image_bytes))
        st.image(original, caption=st.session_state.image_name, use_container_width=True)
        with st.expander("Preview enhanced image"):
            st.image(preprocess_image(st.session_state.image_bytes), use_container_width=True)
    except (OSError, ValueError) as exc:
        st.error(f"The selected image could not be opened: {exc}")
    clear_col, process_col = st.columns(2)
    if clear_col.button("Clear uploaded image"):
        st.session_state.image_bytes = None
        st.session_state.image_name = None
        st.session_state.ocr_text = ""
        st.session_state.uncertain_fields = []
        st.session_state.image_widget_revision += 1
        st.rerun()
    process_label = "Reprocess image" if st.session_state.ocr_text else "Extract readings"
    if process_col.button(process_label, type="primary"):
        try:
            with st.spinner("Enhancing the image and asking the vision service to read the notebook…"):
                result = extract_readings(st.session_state.image_bytes)
            load_report_data(result)
            st.session_state.ocr_text = result.get("raw_text", "")
            st.session_state.uncertain_fields = result.get("uncertain_fields", [])
            st.success("Extraction complete. Review every value before using the report.")
            st.rerun()
        except OCRConfigurationError as exc:
            st.error(str(exc))
        except OCRError as exc:
            st.error(f"Handwriting recognition failed: {exc}")
        except Exception as exc:
            st.error(f"Unexpected image-processing error: {exc}")
else:
    st.info("Upload or take a photo to use handwriting recognition. You can also try the fictional sample mode below.")
    if st.button("Load fictional sample report", type="secondary"):
        load_report_data(
            {
                "report": {
                    "date": "22/10/2026", "station_name": "SAMPLE 110KV STATION",
                    "peak_load": "18.6", "peak_load_time": "19:30",
                    "max_high_voltage": "112", "max_low_voltage": "11.2",
                    "min_high_voltage": "108", "min_low_voltage": "10.8",
                    "station_condition": "Normal", "signature": "SAMPLE STATION",
                },
                "transformers": [
                    {"rating": "20", "load": "9.2", "time": "19:30"},
                    {"rating": "20", "load": "9.4", "time": "19:30"},
                ],
                "interruptions_66": [],
                "interruptions_11": [
                    {
                        "feeder": "F13", "start": "07:51", "end": "08:01",
                        "reported_duration": "00:04", "relay": "EFR+OCR",
                        "remarks": "", "overnight": False,
                    }
                ],
                "nil_66": True, "nil_11": False,
                "uncertain_fields": [],
            }
        )
        st.session_state.ocr_text = "Fictional sample data — not extracted from a real station notebook."
        st.success("Fictional sample loaded. Replace or edit values before generating.")
        st.rerun()

if st.session_state.ocr_text:
    with st.expander("OCR source text and review notes", expanded=True):
        st.text_area(
            "Text recognized from the notebook", value=st.session_state.ocr_text,
            height=140, disabled=True, key=f"ocr_text_{st.session_state.form_revision}",
        )
        if st.session_state.uncertain_fields:
            st.warning("The vision service marked these fields as uncertain. Check the notebook and confirm below.")
            st.write(", ".join(str(field) for field in st.session_state.uncertain_fields))
            st.checkbox(
                "I checked the uncertain OCR fields against the notebook",
                key="ocr_confirmed",
            )

st.header("Step 2: Extract Readings")
st.caption("Every field below can be corrected. Missing notebook values should remain blank, not guessed.")
report = st.session_state.report
with st.container(border=True):
    st.subheader("Station readings")
    c1, c2 = st.columns(2)
    revision = st.session_state.form_revision
    report["station_name"] = c1.text_input("Station name", value=report["station_name"], key=f"report_station_{revision}")
    report["date"] = c2.text_input(
        "Report date (as written in notebook)", value=report["date"], key=f"report_date_{revision}",
        placeholder="DD/MM/YYYY",
    )
    c3, c4 = st.columns(2)
    report["peak_load"] = c3.text_input("Station peak load (MW)", value=report["peak_load"], key=f"peak_load_{revision}")
    report["peak_load_time"] = c4.text_input(
        "Peak load time", value=report["peak_load_time"], key=f"peak_time_{revision}", placeholder="HH:MM"
    )
    report["station_condition"] = st.text_input(
        "Station condition", value=report["station_condition"], key=f"station_condition_{revision}",
        placeholder="e.g. Normal",
    )
    report["signature"] = st.text_input(
        "AE(M) station signature", value=report["signature"], key=f"report_signature_{revision}"
    )

with st.container(border=True):
    st.subheader("Transformer readings")
    st.caption("Add or remove transformer rows to match this station. Ratings and readings remain editable.")
    for index, transformer in enumerate(st.session_state.transformers):
        st.markdown(f"**Transformer {index + 1}**")
        rating_col, load_col, time_col, remove_col = st.columns([1, 1, 1, .7])
        transformer["rating"] = rating_col.text_input(
            "Rating (MVA)", value=transformer["rating"],
            key=f"tr_{st.session_state.transformer_revision}_{index}_rating"
        )
        transformer["load"] = load_col.text_input(
            "Load (MW)", value=transformer["load"],
            key=f"tr_{st.session_state.transformer_revision}_{index}_load"
        )
        transformer["time"] = time_col.text_input(
            "Reading time", value=transformer["time"],
            key=f"tr_{st.session_state.transformer_revision}_{index}_time", placeholder="HH:MM"
        )
        if remove_col.button(
            "Remove", key=f"tr_{st.session_state.transformer_revision}_{index}_remove",
            disabled=len(st.session_state.transformers) <= 1,
        ):
            st.session_state.transformers.pop(index)
            st.session_state.transformer_revision += 1
            st.rerun()
    if st.button("＋ Add transformer", key=f"add_transformer_{st.session_state.transformer_revision}"):
        st.session_state.transformers.append({"rating": "", "load": "", "time": ""})
        st.session_state.transformer_revision += 1
        st.rerun()

with st.container(border=True):
    st.subheader("Voltage readings")
    max_high_col, max_low_col = st.columns(2)
    report["max_high_voltage"] = max_high_col.text_input(
        "Maximum high-side voltage (kV)", value=report["max_high_voltage"], key=f"max_hv_{revision}"
    )
    report["max_low_voltage"] = max_low_col.text_input(
        "Maximum low-side voltage (kV)", value=report["max_low_voltage"], key=f"max_lv_{revision}"
    )
    min_high_col, min_low_col = st.columns(2)
    report["min_high_voltage"] = min_high_col.text_input(
        "Minimum high-side voltage (kV)", value=report["min_high_voltage"], key=f"min_hv_{revision}"
    )
    report["min_low_voltage"] = min_low_col.text_input(
        "Minimum low-side voltage (kV)", value=report["min_low_voltage"], key=f"min_lv_{revision}"
    )

with st.container(border=True):
    show_interruption_editor("66", "66KV interruptions")
with st.container(border=True):
    show_interruption_editor("11", "11KV interruptions")

data = current_data()
issues = validate_report(data)
if issues:
    with st.expander("Review validation messages", expanded=True):
        for issue in issues:
            if issue["level"] == "error":
                st.error(issue["message"])
            elif issue["level"] == "warning":
                st.warning(issue["message"])
            else:
                st.info(issue["message"])

st.header("Step 3: Review and Edit")
st.caption("Inspect the complete message carefully. Reported interruption durations are preserved exactly.")
can_generate = not any(issue["level"] == "error" for issue in issues)
if st.session_state.uncertain_fields and not st.session_state.ocr_confirmed:
    can_generate = False
    st.info("Confirm the uncertain OCR fields above after checking them against the notebook.")
if st.button("Generate Report", type="primary", disabled=not can_generate):
    st.session_state.last_report = generate_report(data)
    st.session_state.editable_report = st.session_state.last_report
    st.success("Report generated. Review and edit the text before copying.")

if st.session_state.last_report:
    st.header("Step 4: Generate Report")
    st.text_area(
        "WhatsApp message (editable)", key="editable_report", height=430,
        help="You can edit the final message here; these edits are kept in the copy/download output.",
    )
    st.header("Step 5: Copy WhatsApp Message")
    report_text = st.session_state.get("editable_report", st.session_state.last_report)
    st.caption("Review the final text, copy it, then paste into the appropriate WhatsApp group yourself.")
    st.code(report_text, language=None)
    st.download_button(
        "Download report as .txt",
        data=report_text.encode("utf-8"),
        file_name="kptcl_daily_station_report.txt",
        mime="text/plain",
    )
    escaped = (
        json.dumps(report_text)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    st.html(
        f"""
        <button id="copy-report" style="width:100%;min-height:46px;border:0;border-radius:8px;
            background:#087443;color:white;font-size:16px;font-weight:600;cursor:pointer">
            Copy Report
        </button>
        <div id="copy-status" style="padding-top:8px;font-size:14px"></div>
        <script>
        const text = {escaped};
        const button = document.getElementById("copy-report");
        button.addEventListener("click", async () => {{
          const status = document.getElementById("copy-status");
          try {{
            await navigator.clipboard.writeText(text);
            status.textContent = "Copied. You can now paste the report into WhatsApp.";
          }} catch (error) {{
            status.textContent = "Clipboard access is unavailable here. Select and copy the complete message shown above.";
          }}
        }});
        </script>
        """,
        unsafe_allow_javascript=True,
    )

with st.expander("Clear report and start a new one", expanded=False):
    st.warning("This clears the current report values and uploaded photo from this browser session.")
    if st.button("Clear current report", key="clear_all"):
        st.session_state.report = {
            "date": "",
            "station_name": "",
            "peak_load": "",
            "peak_load_time": "",
            "max_high_voltage": "",
            "max_low_voltage": "",
            "min_high_voltage": "",
            "min_low_voltage": "",
            "station_condition": "",
            "signature": "",
        }
        st.session_state.transformers = [dict(item) for item in DEFAULT_STATION["transformers"]]
        st.session_state.interruptions_66 = []
        st.session_state.interruptions_11 = []
        st.session_state.nil_66 = False
        st.session_state.nil_11 = False
        st.session_state.ocr_text = ""
        st.session_state.uncertain_fields = []
        st.session_state.image_bytes = None
        st.session_state.image_name = None
        st.session_state.last_report = ""
        st.session_state.editable_report = ""
        st.session_state.ocr_confirmed = False
        st.session_state.form_revision += 1
        st.session_state.transformer_revision += 1
        st.session_state.image_widget_revision += 1
        st.rerun()

st.divider()
st.caption(
    "Privacy: image contents are sent to the configured vision provider only when you choose Extract readings. "
    "Do not upload operational data unless your organization authorizes that service."
)
