import csv
import io

from src import export_service
from src.export_service import ExportRequest, PaymentEvent, build_csv, export_payments


def test_high_risk_payment_is_marked_for_review():
    events = [
        PaymentEvent("safe", "acct", 100, "USD", "settled", 10),
        PaymentEvent("flagged", "acct", 200, "USD", "held", 85),
        PaymentEvent("other", "other", 300, "USD", "settled", 99),
    ]
    rows = list(csv.DictReader(io.StringIO(build_csv(events, ExportRequest("acct", "r1")).decode("utf-8"))))
    assert [row["risk_decision"] for row in rows] == ["allow", "review"]
    assert rows[1]["audit_note"].endswith("decision=review")


def test_export_payments_returns_csv_without_persistent_storage():
    events = [PaymentEvent("payment", "acct", 100, "USD", "settled", 10)]

    content = export_payments(events, ExportRequest("acct", "request"))

    assert content == build_csv(events, ExportRequest("acct", "request"))


def test_main_leaves_download_available_for_caller(monkeypatch, capsys):
    class Client:
        def __init__(self, api_key):
            assert api_key == "test-key"

        def delete_object(self, bucket, key):
            raise AssertionError("main deleted the exported object")

        def delete_bucket(self, bucket):
            raise AssertionError("main deleted the export bucket")

    monkeypatch.setenv("INFRAI_API_KEY", "test-key")
    monkeypatch.setattr(export_service, "InfraiClient", Client)
    monkeypatch.setattr(export_service, "export_payments", lambda *args, **kwargs: "https://download.example/export.csv")

    export_service.main()

    assert capsys.readouterr().out == "https://download.example/export.csv\n"
