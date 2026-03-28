from django.test import TestCase

from emergency.services.severity import predict_severity_and_priority


class SeverityTests(TestCase):
    def test_critical_keywords(self):
        r = predict_severity_and_priority("patient is unconscious and not breathing", None)
        self.assertGreaterEqual(r.severity_level, 4)
        self.assertGreater(r.priority_score, 30)

    def test_user_report_raises_floor(self):
        r = predict_severity_and_priority("slight cough", user_reported_severity=5)
        self.assertEqual(r.severity_level, 5)
