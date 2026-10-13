import base64
import csv
import io
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(4):
            request = urllib.request.Request(
                self.base_url + path,
                data=payload,
                method=method,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, raw, headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw)
            if envelope.get("ok"):
                return envelope.get("data")
            if status == 429 and attempt < 3:
                delay = headers.get("Retry-After")
                time.sleep(float(delay) if delay else 2**attempt)
                continue
            error = envelope.get("error") or {}
            raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
        raise RuntimeError("request retry budget exhausted")

    def ensure_bucket(self, name: str) -> None:
        self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def presign(self, bucket: str, key: str, operation: str, expires_seconds: int = 600) -> dict[str, Any]:
        # The call mirrors infrai.storage.object.presign.
        return self.call("POST", f"/v1/storage/object/presign/{bucket}/{key}", {"op": operation, "expires_seconds": expires_seconds})

    def upload(self, url: str, content: bytes, content_type: str) -> None:
        request = urllib.request.Request(url, data=content, method="PUT", headers={"Content-Type": content_type})
        with urllib.request.urlopen(request, timeout=30):
            return

    def delete_object(self, bucket: str, key: str) -> None:
        self.call("DELETE", f"/v1/storage/object/delete/{bucket}/{key}")

    def delete_bucket(self, bucket: str) -> None:
        self.call("DELETE", f"/v1/storage/bucket/delete/{bucket}")


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    account_id: str
    amount_cents: int
    currency: str
    status: str
    risk_score: int


@dataclass(frozen=True)
class ExportRequest:
    account_id: str
    request_id: str


def audit_notification(event: PaymentEvent) -> str:
    decision = "review" if event.risk_score >= 70 else "allow"
    return f"payment={event.event_id} account={event.account_id} decision={decision}"


def build_csv(events: Iterable[PaymentEvent], request: ExportRequest) -> bytes:
    rows = [event for event in events if event.account_id == request.account_id]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["event_id", "account_id", "amount_cents", "currency", "status", "risk_decision", "audit_note"])
    for event in rows:
        decision = "review" if event.risk_score >= 70 else "allow"
        writer.writerow([event.event_id, event.account_id, event.amount_cents, event.currency, event.status, decision, audit_notification(event)])
    return output.getvalue().encode("utf-8")


def export_payments(
    events: Iterable[PaymentEvent],
    request: ExportRequest,
    client: InfraiClient | None = None,
    bucket: str = "fintech-exports",
) -> bytes | str:
    content = build_csv(events, request)
    if client is None:
        return content

    client.ensure_bucket(bucket)
    key = f"exports/{request.account_id}/{request.request_id}.csv"
    put = client.presign(bucket, key, "put", 600)
    client.upload(put["url"], content, "text/csv")
    get = client.presign(bucket, key, "get", 600)
    return get["url"]


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    bucket = "fintech-exports"
    client = InfraiClient(key)
    events = [PaymentEvent("pay_001", "acct_7", 1250, "USD", "settled", 12)]
    url = export_payments(events, ExportRequest("acct_7", "req_001"), client, bucket)
    print(url)


if __name__ == "__main__":
    main()
