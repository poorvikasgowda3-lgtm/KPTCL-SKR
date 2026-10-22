import io
import json
import unittest
from unittest.mock import patch

from PIL import Image
from google import genai
from google.genai import errors, types

import ocr_service


class OCRServiceTests(unittest.TestCase):
    def setUp(self):
        self.image_bytes = io.BytesIO()
        Image.new("RGB", (80, 80), "white").save(self.image_bytes, format="PNG")
        self.image_bytes = self.image_bytes.getvalue()
        self.payload = {
            "report": {
                "date": "22/10/2026",
                "station_name": "DEMO STATION",
                "peak_load": "18.6",
                "peak_load_time": "19:30",
                "max_high_voltage": "112",
                "max_low_voltage": "11.2",
                "min_high_voltage": "108",
                "min_low_voltage": "10.8",
                "station_condition": "Normal",
                "signature": "DEMO STATION",
            },
            "transformers": [
                {"rating": "20", "load": "9.2", "time": "19:30"},
                {"rating": "10", "load": "4.1", "time": "19:30"},
            ],
            "interruptions": {
                "66": [],
                "11": [{
                    "feeder": "F13",
                    "start": "07:51",
                    "end": "08:01",
                    "reported_duration": "00:04",
                    "relay": "EFR+OCR",
                    "remarks": "Tree branch",
                }],
            },
            "nil_66": True,
            "nil_11": False,
            "raw_text": "F13 Tree branch",
            "uncertain_fields": ["Transformer 2 load"],
        }

    def test_normalize_preserves_multiple_transformers_interruptions_and_reported_duration(self):
        result = ocr_service._normalize_result(self.payload)
        self.assertEqual(len(result["transformers"]), 2)
        self.assertEqual(result["interruptions_11"][0]["reported_duration"], "00:04")
        self.assertEqual(result["interruptions_11"][0]["remarks"], "Tree branch")
        self.assertEqual(result["uncertain_fields"], ["Transformer 2 load"])

    def test_gemini_receives_preprocessed_image_and_structured_json_request(self):
        response = type("Response", (), {"text": json.dumps(self.payload)})()
        with (
            patch.object(ocr_service, "_api_key", return_value="test-key"),
            patch.object(ocr_service, "preprocess_image", return_value=Image.new("RGB", (80, 80), "white")),
            patch.object(genai, "Client") as client_factory,
        ):
            client_factory.return_value.models.generate_content.return_value = response
            result = ocr_service.extract_readings(self.image_bytes)

        call = client_factory.return_value.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-2.5-flash")
        self.assertEqual(call.kwargs["config"].response_mime_type, "application/json")
        image_part = call.kwargs["contents"][1]
        self.assertIsInstance(image_part, types.Part)
        self.assertEqual(image_part.inline_data.mime_type, "image/png")
        self.assertEqual(len(result["transformers"]), 2)
        self.assertEqual(result["interruptions_11"][0]["reported_duration"], "00:04")

    def test_missing_key_fails_without_fabricating_readings(self):
        with patch.object(ocr_service, "_api_key", return_value=""):
            with self.assertRaises(ocr_service.OCRConfigurationError):
                ocr_service.extract_readings(self.image_bytes)

    def test_rate_limit_has_actionable_error(self):
        with (
            patch.object(ocr_service, "_api_key", return_value="test-key"),
            patch.object(ocr_service, "preprocess_image", return_value=Image.new("RGB", (80, 80), "white")),
            patch.object(genai, "Client") as client_factory,
        ):
            client_factory.return_value.models.generate_content.side_effect = errors.ClientError(
                429, {"error": {"message": "quota exceeded"}}
            )
            with self.assertRaisesRegex(ocr_service.OCRError, "rate or quota limit"):
                ocr_service.extract_readings(self.image_bytes)

    def test_invalid_credentials_and_provider_outage_have_actionable_errors(self):
        cases = (
            (errors.ClientError, 403, "rejected the API credentials"),
            (errors.ClientError, 404, "not found or is unavailable"),
            (errors.ServerError, 503, "temporarily unavailable"),
        )
        for error_type, status, expected in cases:
            with self.subTest(status=status):
                with (
                    patch.object(ocr_service, "_api_key", return_value="test-key"),
                    patch.object(ocr_service, "preprocess_image", return_value=Image.new("RGB", (80, 80), "white")),
                    patch.object(genai, "Client") as client_factory,
                ):
                    client_factory.return_value.models.generate_content.side_effect = error_type(
                        status, {"error": {"message": "provider detail"}}
                    )
                    with self.assertRaisesRegex(ocr_service.OCRError, expected):
                        ocr_service.extract_readings(self.image_bytes)

    def test_usable_api_key_detects_placeholders_and_formatting(self):
        invalid_keys = [
            "",
            "   ",
            "replace_with_your_api_key",
            '"replace_with_your_api_key"',
            "'your-gemini-api-key'",
            "YOUR_API_KEY",
            "<your_api_key>",
            "changeme",
            "none",
            "null",
        ]
        for key in invalid_keys:
            with self.subTest(key=key):
                self.assertEqual(ocr_service._usable_api_key(key), "")
        self.assertEqual(ocr_service._usable_api_key("  valid_key_123  "), "valid_key_123")
        self.assertEqual(ocr_service._usable_api_key('"valid_key_456"'), "valid_key_456")

    def test_extract_handles_markdown_fenced_json(self):
        fenced = f"```json\n{json.dumps(self.payload)}\n```"
        response = type("Response", (), {"text": fenced})()
        with (
            patch.object(ocr_service, "_api_key", return_value="test-key"),
            patch.object(ocr_service, "preprocess_image", return_value=Image.new("RGB", (80, 80), "white")),
            patch.object(genai, "Client") as client_factory,
        ):
            client_factory.return_value.models.generate_content.return_value = response
            result = ocr_service.extract_readings(self.image_bytes)
        self.assertEqual(result["report"]["station_name"], "DEMO STATION")


if __name__ == "__main__":
    unittest.main()
