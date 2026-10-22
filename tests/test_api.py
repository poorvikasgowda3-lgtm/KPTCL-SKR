import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from ocr_service import OCRConfigurationError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.valid_data = {
            "report": {
                "date": "22/10/2026",
                "station_name": "SAMPLE STATION",
                "peak_load": "18.6",
                "peak_load_time": "19:30",
                "max_high_voltage": "112",
                "max_low_voltage": "11.2",
                "min_high_voltage": "108",
                "min_low_voltage": "10.8",
                "station_condition": "Normal",
                "signature": "SAMPLE STATION",
            },
            "transformers": [{"rating": "20", "load": "9.2", "time": "19:30"}],
            "interruptions_66": [],
            "interruptions_11": [],
            "nil_66": True,
            "nil_11": True,
            "uncertain_fields": [],
            "ocr_confirmed": False,
        }

    def test_health_and_safe_config_endpoints(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        with patch("backend.main.is_configured", return_value=False):
            config = self.client.get("/api/config").json()
        self.assertFalse(config["ocr_configured"])
        self.assertNotIn("api_key", config)

    def test_generate_uses_existing_report_formatter(self):
        response = self.client.post("/api/reports/generate", json=self.valid_data)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["can_generate"])
        self.assertIn(
            "Station peak load of  SAMPLE STATION on 22/10/2026 is 18.6MW at 19:30Hrs.",
            result["message"],
        )
        self.assertIn("66KV Interruptions: Nil", result["message"])

    def test_generate_returns_validation_issues_not_a_broken_report(self):
        invalid = {**self.valid_data, "report": {**self.valid_data["report"], "date": ""}}
        response = self.client.post("/api/reports/generate", json=invalid)
        self.assertEqual(response.status_code, 422)
        self.assertTrue(any("Report date" in issue["message"] for issue in response.json()["detail"]["issues"]))

    def test_validate_endpoint_returns_live_validation_without_generating(self):
        invalid = {**self.valid_data, "report": {**self.valid_data["report"], "date": ""}}
        response = self.client.post("/api/reports/validate", json=invalid)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["can_generate"])
        self.assertEqual(response.json()["message"], "")
        self.assertTrue(any("Report date" in issue["message"] for issue in response.json()["issues"]))

    def test_uncertain_ocr_requires_user_confirmation(self):
        request_data = {
            **self.valid_data,
            "uncertain_fields": ["Transformer 1 load"],
            "ocr_confirmed": False,
        }
        response = self.client.post("/api/reports/generate", json=request_data)
        self.assertEqual(response.status_code, 422)
        self.assertTrue(any("Confirm uncertain OCR fields" in issue["message"] for issue in response.json()["detail"]["issues"]))
        request_data["ocr_confirmed"] = True
        self.assertTrue(self.client.post("/api/reports/generate", json=request_data).json()["can_generate"])

    def test_rejects_invalid_image_upload(self):
        response = self.client.post(
            "/api/ocr/extract",
            files={"image": ("not-an-image.jpg", b"not image bytes", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 400)

    def test_image_size_limit_is_enforced(self):
        with patch("backend.main.MAX_UPLOAD_BYTES", 4):
            response = self.client.post(
                "/api/ocr/extract",
                files={"image": ("photo.jpg", b"12345", "image/jpeg")},
            )
        self.assertEqual(response.status_code, 413)

    def test_cors_rejects_unconfigured_origins(self):
        response = self.client.get(
            "/api/health",
            headers={"Origin": "https://untrusted.example"},
        )
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_ocr_endpoint_returns_structured_readings_without_storing_photo(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (80, 80), "white").save(image_buffer, format="PNG")
        extracted = {
            "report": self.valid_data["report"],
            "transformers": self.valid_data["transformers"],
            "interruptions_66": [],
            "interruptions_11": [],
            "nil_66": True,
            "nil_11": True,
            "uncertain_fields": ["peak load"],
            "raw_text": "Fictional notebook text",
        }
        with patch("backend.main.extract_readings", return_value=extracted):
            response = self.client.post(
                "/api/ocr/extract",
                files={"image": ("notebook.png", image_buffer.getvalue(), "image/png")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["uncertain_fields"], ["peak load"])
        self.assertNotIn("photo", response.json())

    def test_ocr_endpoint_explains_missing_provider_key(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (80, 80), "white").save(image_buffer, format="PNG")
        with patch(
            "backend.main.extract_readings",
            side_effect=OCRConfigurationError("Set GEMINI_API_KEY to enable handwriting recognition."),
        ):
            response = self.client.post(
                "/api/ocr/extract",
                files={"image": ("notebook.png", image_buffer.getvalue(), "image/png")},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
