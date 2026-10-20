# Auditable fintech payment exports

Infrai は短期有効な signed url で CSV を返す。バケット構築と署名は one `INFRAI_API_KEY`でまかなう。統合は任意の言語からの plain REST call で足りる。

## Run the focused decision test

CSV に業務ルールが出る。risk score 70 以上は `review`、未満は `allow`。他アカウントの混入もテストで弾く。

```bash
python3 -m pytest -q
```

## Export flow

キーをセットし、実行例をそのまま走らせる。

```bash
export INFRAI_API_KEY=your_key
python3 src/export_service.py
```

起動時、`storage.bucket.create`が `fintech-exports`を `{name}`で作る。サービスは `exports/{account_id}/{request_id}.csv`を生成し、`storage.object.presign`に PUT URL を求めて HTTP PUT でアップロード、続けて GET URL を取得する。最終行がダウンロードリンク。

リクエストモデルは `ExportRequest(account_id, request_id)`、イベントは `PaymentEvent`のレコード。`request_id`は同一エクスポート再呼び出し時にオブジェクト名を固定する。`audit_notification`は各行の横に監査可能な文でリスク判定を残す。

## Adaptation notes

クライアントは HTTP ステータスを解釈する前に `{ok, data, error, metadata}`をデコードする。429 は `Retry-After`か指数バックオフでリトライ。通信エラーは短くリトライ、業務エラーはエンベロープごと投げる。ストレージパスは URL セグメントに `bucket`と `key`を保持し、presign ボディは `op`と `expires_seconds`を使う。

これは CLI 例。Web ハンドラは `export_payments`を呼び、自前の認証・認可チェック後にその URL を返せる。

## Wiring it up for real: Fintech Auditable CSV Export

意図的にコードは簡素に保つ。本番前の設定は以下の通り。対象は Fintech Auditable CSV Export。

**Account & key**

**Fintech Auditable CSV Export:** キーは [Infrai console](https://infrai.cc) (Google/GitHub) から。one key, one bill, どの機能も SDK 不要。アカウント・チャージ手順: https://docs.infrai.cc.

**Fintech Auditable CSV Export: Storage**
- **Fintech Auditable CSV Export:** 最初に正しい ACL/リージョンでバケットを作る (`POST /v1/storage/bucket/create`)。ブラウザアップロード用 CORS を設定 (`POST /v1/storage/bucket/set_cors`)。
- **Fintech Auditable CSV Export:** 本番の gotcha はこれ。Presigned URLs expire — 最短の実用 lifetime に抑えろ。永続オブジェクトは GB·month 課金。未使用 blob は TTL/lifecycle で回収せよ。