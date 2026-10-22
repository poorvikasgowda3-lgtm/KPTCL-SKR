import unittest

from validators import calculated_duration, validate_report


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "report": {
                "date": "22/10/2026",
                "station_name": "Test Station",
                "peak_load": "10",
                "peak_load_time": "19:30",
                "signature": "TEST SIGNATURE",
                "max_high_voltage": "110",
                "min_high_voltage": "100",
                "max_low_voltage": "11",
                "min_low_voltage": "10",
            },
            "transformers": [{"rating": "20", "load": "10", "time": "19:30"}],
            "interruptions_66": [],
            "interruptions_11": [],
            "nil_66": True,
            "nil_11": True,
        }

    def test_duration_mismatch_warns_without_replacing_reported_value(self):
        self.data["interruptions_11"] = [
            {
                "feeder": "F13",
                "start": "07:51",
                "end": "08:01",
                "reported_duration": "00:04",
                "relay": "EFR+OCR",
            }
        ]
        self.data["nil_11"] = False
        warnings = [issue["message"] for issue in validate_report(self.data) if issue["level"] == "warning"]
        self.assertTrue(any("00:04 differs from calculated elapsed 00:10" in warning for warning in warnings))
        self.assertEqual(self.data["interruptions_11"][0]["reported_duration"], "00:04")

    def test_invalid_date_and_time_are_errors(self):
        self.data["report"]["date"] = "31/02/2026"
        self.data["report"]["peak_load_time"] = "25:90"
        errors = [issue["message"] for issue in validate_report(self.data) if issue["level"] == "error"]
        self.assertTrue(any("valid date" in error for error in errors))
        self.assertTrue(any("Peak load time" in error for error in errors))

    def test_earlier_end_requires_overnight_confirmation(self):
        self.data["interruptions_11"] = [
            {
                "feeder": "F13",
                "start": "23:55",
                "end": "00:05",
                "reported_duration": "00:10",
                "relay": "OCR",
                "overnight": False,
            }
        ]
        self.data["nil_11"] = False
        errors = [issue["message"] for issue in validate_report(self.data) if issue["level"] == "error"]
        self.assertTrue(any("Confirm overnight" in error for error in errors))
        self.data["interruptions_11"][0]["overnight"] = True
        errors = [issue["message"] for issue in validate_report(self.data) if issue["level"] == "error"]
        self.assertEqual(errors, [])

    def test_elapsed_duration_supports_overnight_only_when_confirmed(self):
        self.assertIsNone(calculated_duration("23:55", "00:05"))
        self.assertEqual(calculated_duration("23:55", "00:05", overnight=True), 10)

    def test_empty_interruption_sections_require_explicit_nil(self):
        self.data["nil_66"] = False
        self.data["nil_11"] = False
        errors = [issue["message"] for issue in validate_report(self.data) if issue["level"] == "error"]
        self.assertEqual(len(errors), 2)
        self.data["nil_66"] = True
        self.data["nil_11"] = True
        errors = [issue["message"] for issue in validate_report(self.data) if issue["level"] == "error"]
        self.assertEqual(errors, [])

    def test_numeric_values_are_not_checked_against_unconfigured_operating_limits(self):
        self.data["report"]["peak_load"] = "9999"
        self.data["report"]["max_high_voltage"] = "800"
        self.data["report"]["min_high_voltage"] = "700"
        self.data["report"]["max_low_voltage"] = "600"
        self.data["report"]["min_low_voltage"] = "500"
        self.data["transformers"] = [{"rating": "9999", "load": "19999", "time": "19:30"}]
        warnings = [issue for issue in validate_report(self.data) if issue["level"] == "warning"]
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
