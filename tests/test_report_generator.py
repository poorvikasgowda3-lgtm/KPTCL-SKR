import unittest

from report_generator import generate_report


class ReportGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "report": {
                "date": "22/10/2026",
                "station_name": "SAMPLE",
                "peak_load": "18.6",
                "peak_load_time": "19:30",
                "max_high_voltage": "112",
                "max_low_voltage": "11.2",
                "min_high_voltage": "108",
                "min_low_voltage": "10.8",
                "station_condition": "Normal",
                "signature": "SAMPLE",
            },
            "transformers": [
                {"rating": "20", "load": "9.2", "time": "19:30"},
                {"rating": "20", "load": "9.4", "time": "19:30"},
                {"rating": "10", "load": "7.1", "time": "19:30"},
                {"rating": "5", "load": "2.0", "time": "19:30"},
            ],
            "interruptions_66": [],
            "nil_66": True,
            "interruptions_11": [
                {
                    "feeder": "F13",
                    "start": "07:51",
                    "end": "08:01",
                    "reported_duration": "00:04",
                    "relay": "EFR+OCR",
                },
                {
                    "feeder": "F13",
                    "start": "10:00",
                    "end": "10:08",
                    "reported_duration": "00:08",
                    "relay": "OCR",
                },
                {
                    "feeder": "F14",
                    "start": "12:00",
                    "end": "12:02",
                    "reported_duration": "00:02",
                    "relay": "EFR",
                },
            ],
            "nil_11": False,
        }

    def test_standard_three_transformer_format_and_additional_rows(self):
        text = generate_report(self.data)
        self.assertIn("Station peak load of  SAMPLE on 22/10/2026 is 18.6MW at 19:30Hrs.", text)
        self.assertIn("1)20MVA Tr1- 9.2MW at 19:30 Hrs.", text)
        self.assertIn("2)20MVA Tr2 -  9.4MW at 19:30hrs", text)
        self.assertIn("3)10MVA Tr3 - 7.1MW at 19:30Hrs.", text)
        self.assertIn("4)5MVA Tr4 - 2.0MW at 19:30Hrs.", text)

    def test_groups_interruptions_and_preserves_reported_duration(self):
        text = generate_report(self.data)
        self.assertIn("F13 -\n07:51 to 08:01 = 00:04(EFR+OCR)\n10:00 to 10:08 = 00:08(OCR)\n\nF14 -", text)
        self.assertIn("66KV Interruptions: Nil", text)

    def test_omits_incomplete_values_and_none_placeholders(self):
        data = {
            "report": {"station_name": "Station", "date": "22/10/2026", "peak_load": "None"},
            "transformers": [{"rating": "", "load": "", "time": ""}],
            "interruptions_66": [],
            "interruptions_11": [],
            "nil_66": True,
            "nil_11": True,
        }
        text = generate_report(data)
        self.assertNotIn("None", text)
        self.assertNotIn("null", text)
        self.assertNotIn("MVA", text)
        self.assertIn("66KV Interruptions: Nil", text)


if __name__ == "__main__":
    unittest.main()
