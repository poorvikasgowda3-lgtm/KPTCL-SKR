from __future__ import annotations

import io
import logging
import os
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from ocr_service import OCRConfigurationError, OCRError, extract_readings, is_configured
from report_generator import generate_report
from validators import validate_report


logger = logging.getLogger("kptcl.api")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReportFields(StrictModel):
    date: str = Field(default="", max_length=40)
    station_name: str = Field(default="", max_length=120)
    peak_load: str = Field(default="", max_length=40)
    peak_load_time: str = Field(default="", max_length=20)
    max_high_voltage: str = Field(default="", max_length=40)
    max_low_voltage: str = Field(default="", max_length=40)
    min_high_voltage: str = Field(default="", max_length=40)
    min_low_voltage: str = Field(default="", max_length=40)
    station_condition: str = Field(default="", max_length=200)
    signature: str = Field(default="", max_length=120)


class TransformerReading(StrictModel):
    rating: str = Field(default="", max_length=40)
    load: str = Field(default="", max_length=40)
    time: str = Field(default="", max_length=20)


class Interruption(StrictModel):
    feeder: str = Field(default="", max_length=40)
    start: str = Field(default="", max_length=20)
    end: str = Field(default="", max_length=20)
    reported_duration: str = Field(default="", max_length=20)
    relay: str = Field(default="", max_length=60)
    remarks: str = Field(default="", max_length=500)
    overnight: bool = False


class ReportRequest(StrictModel):
    report: ReportFields
    transformers: list[TransformerReading] = Field(max_length=30)
    interruptions_66: list[Interruption] = Field(max_length=200)
    interruptions_11: list[Interruption] = Field(max_length=200)
    nil_66: bool = False
    nil_11: bool = False
    uncertain_fields: list[str] = Field(default_factory=list, max_length=100)
    ocr_confirmed: bool = False


class ValidationIssue(StrictModel):
    level: Literal["error", "warning", "info"]
    message: str


class GenerateResponse(StrictModel):
    message: str
    issues: list[ValidationIssue]
    can_generate: bool


def _report_issues(request: ReportRequest) -> list[dict[str, str]]:
    data = request.model_dump(exclude={"ocr_confirmed"})
    issues = validate_report(data)
    if request.uncertain_fields and not request.ocr_confirmed:
        issues.append(
            {
                "level": "error",
                "message": "Confirm uncertain OCR fields after checking the original notebook.",
            }
        )
    return issues


app = FastAPI(
    title="KPTCL Daily Station Report API",
    version="1.0.0",
    description="Handwriting extraction and WhatsApp report formatting for station reports.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def get_config() -> dict[str, object]:
    return {
        "title": "KPTCL Daily Station Report Generator",
        "ocr_configured": is_configured(),
        "sample_mode": True,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "draft_storage": "browser-local",
        "supported_image_types": sorted(ALLOWED_IMAGE_TYPES),
    }


def _validate_image(data: bytes, filename: str, content_type: str | None) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content_type not in ALLOWED_IMAGE_TYPES or extension not in {"jpg", "jpeg", "png", "webp", "bmp"}:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WEBP, or BMP image.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a readable image.") from exc
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(status_code=415, detail="The image encoding is not supported.")
    if width < 40 or height < 40:
        raise HTTPException(status_code=400, detail="The image is too small. Upload a larger notebook photo.")
    if width * height > 50_000_000:
        raise HTTPException(status_code=413, detail="The image dimensions are too large to process.")


@app.post("/api/ocr/extract")
def extract_notebook_image(
    image: Annotated[UploadFile, File(description="Notebook photo (JPG, PNG, WEBP, or BMP)")],
) -> dict[str, object]:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WEBP, or BMP image.")
    try:
        contents = image.file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        image.file.close()
    _validate_image(contents, image.filename or "", image.content_type)
    try:
        data = extract_readings(contents)
    except OCRConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OCRError as exc:
        logger.warning("OCR extraction failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    report_data = {
        "report": data["report"],
        "transformers": data["transformers"],
        "interruptions_66": data["interruptions_66"],
        "interruptions_11": data["interruptions_11"],
        "nil_66": data["nil_66"],
        "nil_11": data["nil_11"],
        "uncertain_fields": data["uncertain_fields"],
        "ocr_confirmed": False,
    }
    issues = validate_report(report_data)
    return {
        "data": data,
        "warnings": [
            {
                "level": "warning" if issue["level"] == "error" else issue["level"],
                "message": issue["message"],
            }
            for issue in issues
        ],
    }


@app.post("/api/reports/generate", response_model=GenerateResponse)
def create_report(request: ReportRequest) -> GenerateResponse:
    data = request.model_dump(exclude={"ocr_confirmed"})
    issues = _report_issues(request)
    has_errors = any(issue["level"] == "error" for issue in issues)
    if has_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Correct the validation errors before generating the report.",
                "issues": issues,
            },
        )
    return GenerateResponse(
        message=generate_report(data),
        issues=issues,
        can_generate=True,
    )


@app.post("/api/reports/validate", response_model=GenerateResponse)
def validate_report_request(request: ReportRequest) -> GenerateResponse:
    issues = _report_issues(request)
    return GenerateResponse(
        message="",
        issues=issues,
        can_generate=not any(issue["level"] == "error" for issue in issues),
    )
