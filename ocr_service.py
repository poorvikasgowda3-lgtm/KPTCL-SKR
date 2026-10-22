from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from dotenv import load_dotenv


def _usable_api_key(value: Any) -> str:
    if not value or not isinstance(value, str):
        return ""
    key = value.strip().strip("'\"").strip()
    placeholder = key.casefold()
    if (
        not key
        or placeholder in {
            "your_api_key",
            "your-gemini-api-key",
            "your_gemini_api_key",
            "changeme",
            "placeholder",
            "none",
            "null",
            "undefined",
            "replace_with_your_api_key",
            "replace_with_your_key",
        }
        or placeholder.startswith("replace_with_")
        or placeholder.startswith("your_")
        or (placeholder.startswith("<") and placeholder.endswith(">"))
    ):
        return ""
    return key


def _load_env() -> None:
    """Load project-root .env securely relative to this file."""
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / ".env",
        base_dir.parent / ".env",
    ]
    for env_path in candidates:
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=True)
            if _usable_api_key(os.environ.get("GEMINI_API_KEY", "")):
                break


_load_env()


class OCRConfigurationError(RuntimeError):
    """Raised when the vision service is not configured."""


class OCRError(RuntimeError):
    """Raised when image extraction fails."""


def _api_key() -> str:
    key = _usable_api_key(os.environ.get("GEMINI_API_KEY", ""))
    if not key:
        try:
            import streamlit as st

            key = _usable_api_key(str(st.secrets.get("GEMINI_API_KEY", "")))
        except (ImportError, FileNotFoundError, KeyError, AttributeError):
            key = ""
    return key


def is_configured() -> bool:
    return bool(_api_key())


def preprocess_image(image_bytes: bytes) -> Image.Image:
    """Correct orientation and improve contrast/readability for a notebook photo."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            rgb = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise OCRError("The selected file is not a readable image.") from exc
    if rgb.width < 40 or rgb.height < 40:
        raise OCRError("The image is too small to read. Upload a larger photo.")
    array = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY)
    max_dimension = 2400
    scale = min(2.0, max_dimension / max(array.shape))
    if scale > 1:
        array = cv2.resize(array, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    array = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(array)
    denoised = cv2.fastNlMeansDenoising(array, None, h=8)
    return Image.fromarray(denoised).convert("RGB")


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _normalize_result(payload: dict[str, Any]) -> dict[str, Any]:
    raw_report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    report_fields = (
        "date", "station_name", "peak_load", "peak_load_time",
        "max_high_voltage", "max_low_voltage", "min_high_voltage",
        "min_low_voltage", "station_condition", "signature",
    )
    report = {field: _clean_string(raw_report.get(field)) for field in report_fields}
    transformers = []
    raw_transformers = payload.get("transformers", [])
    if isinstance(raw_transformers, list):
        for item in raw_transformers:
            if isinstance(item, dict):
                transformers.append(
                    {
                        "rating": _clean_string(item.get("rating")),
                        "load": _clean_string(item.get("load")),
                        "time": _clean_string(item.get("time")),
                    }
                )
    interruptions: dict[str, list[dict[str, Any]]] = {"66": [], "11": []}
    raw_interruptions = payload.get("interruptions", {})
    if isinstance(raw_interruptions, dict):
        for voltage in interruptions:
            rows = raw_interruptions.get(voltage, [])
            if isinstance(rows, list):
                for item in rows:
                    if isinstance(item, dict):
                        interruptions[voltage].append(
                            {
                                "feeder": _clean_string(item.get("feeder")),
                                "start": _clean_string(item.get("start")),
                                "end": _clean_string(item.get("end")),
                                "reported_duration": _clean_string(item.get("reported_duration")),
                                "relay": _clean_string(item.get("relay")),
                                "remarks": _clean_string(item.get("remarks")),
                                "overnight": bool(item.get("overnight", False)),
                            }
                        )
    uncertain = payload.get("uncertain_fields", [])
    if not isinstance(uncertain, list):
        uncertain = []
    return {
        "report": report,
        "transformers": transformers or [{"rating": "", "load": "", "time": ""}],
        "interruptions_66": interruptions["66"],
        "interruptions_11": interruptions["11"],
        "nil_66": payload.get("nil_66") is True and not interruptions["66"],
        "nil_11": payload.get("nil_11") is True and not interruptions["11"],
        "uncertain_fields": [_clean_string(field) for field in uncertain if _clean_string(field)],
        "raw_text": _clean_string(payload.get("raw_text")),
    }


def extract_readings(image_bytes: bytes) -> dict[str, Any]:
    """Extract notebook readings using Gemini; image data stays server-side."""
    api_key = _api_key()
    if not api_key:
        raise OCRConfigurationError(
            "Handwriting recognition is not configured. Set GEMINI_API_KEY in your environment "
            "or Streamlit secrets, then restart the app. You can still edit readings manually "
            "or use the fictional sample mode."
        )
    try:
        from google import genai
        from google.genai import errors
        from google.genai import types
    except ImportError as exc:
        raise OCRError("The Gemini client is not installed. Run: pip install -r requirements.txt") from exc

    processed = preprocess_image(image_bytes)
    image_buffer = io.BytesIO()
    processed.save(image_buffer, format="PNG")
    prompt = """
Read every legible item from this electrical station daily-report notebook image.
Do not guess, calculate, normalize, or invent readings. Preserve written values and times.
Return one JSON object with this exact shape:
{
 "report": {
   "date":"", "station_name":"", "peak_load":"", "peak_load_time":"",
   "max_high_voltage":"", "max_low_voltage":"", "min_high_voltage":"",
   "min_low_voltage":"", "station_condition":"", "signature":""
 },
 "transformers":[{"rating":"","load":"","time":""}],
 "interruptions":{
   "66":[{"feeder":"","start":"","end":"","reported_duration":"","relay":"","remarks":""}],
   "11":[{"feeder":"","start":"","end":"","reported_duration":"","relay":"","remarks":""}]
 },
 "nil_66":false,
 "nil_11":false,
 "raw_text":"all legible notebook text, retaining line breaks where possible",
 "uncertain_fields":["field names or short descriptions for unclear readings"]
}
Use empty strings for unreadable or absent values. Use empty arrays when no interruption entries can be read.
Set a nil flag true only when the notebook explicitly states Nil/no interruptions for that voltage level.
Keep notebook duration separate exactly as written. Include all legible transformers; never assume there are three.
Mark uncertain readings in uncertain_fields. Do not infer a date from today's date. Return JSON only.
"""
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_buffer.getvalue(), mime_type="image/png"),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if not response.text:
            raise OCRError("The vision provider returned an empty response.")
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise OCRError("The vision provider returned an unexpected response format.")
        return _normalize_result(parsed)
    except OCRError:
        raise
    except json.JSONDecodeError as exc:
        raise OCRError("The vision provider response could not be read. Try reprocessing the photo.") from exc
    except errors.APIError as exc:
        code = getattr(exc, "code", None)
        if code in (401, 403):
            message = "Gemini rejected the API credentials or access. Check GEMINI_API_KEY and that the selected model is enabled."
        elif code == 404:
            message = f"The selected Gemini model ('{model_name}') was not found or is unavailable for this API key. Set GEMINI_MODEL in .env to an available model."
        elif code == 429:
            message = "Gemini rate or quota limit reached. Check the project's usage limits, then retry later."
        elif code is not None and code >= 500:
            message = "Gemini is temporarily unavailable. Wait a moment and retry."
        else:
            message = f"Gemini rejected the extraction request (HTTP {code}). Check the model configuration and try another clear image."
        raise OCRError(message) from exc
    except Exception as exc:
        raise OCRError(
            "Could not reach Gemini to read the photo. Check the backend internet connection and retry."
        ) from exc
