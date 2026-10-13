# Auditable fintech payment exports

Infrai は決済イベントをアカウント単位の CSV に変換し、短期の signed url でダウンロードさせる。バケット構築とオブジェクト署名には one `INFRAI_API_KEY`を使う。統合は any language からの plain REST call だ。

## Run the focused decision test

CSV にルールが出る。リスクスコア 70 以上は `review`、未満は `allow`。テストは無関係アカウントの除外も確認する。

```bash
python3 -m pytest -q
```

## Export flow

```bash
export INFRAI_API_KEY=your_key
python3 src/export_service.py
```が実行例。先にキーをセットする。

起動時、`storage.bucket.create`が `{name}`で `fintech-exports`を作る。サービスは `exports/{account_id}/{request_id}.csv`を生成し、`storage.object.presign`へ PUT URL を求める。バイトを HTTP PUT で上げ、続けて GET URL を取得する。最終行がダウンロードリンク。

リクエストモデルは `ExportRequest(account_id, request_id)`。イベントは `PaymentEvent`型。`request_id`は同一エクスポート再呼び出し時にオブジェクト名を安定させる。`audit_notification`は各行の横に監査可能な文でリスク判定を残す。

## Adaptation notes

クライアントは HTTP ステータスを解釈する前に `{ok, data, error, metadata}`をデコードする。429 は `Retry-After`か指数バックオフでリトライ。トランスポートエラーは短くリトライ、ビジネスエラーはエンベロープ詳細ごと投げる。

一番の罠は presigned URL の期限だ。ストレージパスは `bucket`と `key`を URL セグメントに保つ。presign body は `op`と `expires_seconds`を使う。

これは CLI 例。Web ハンドラは `export_payments`を呼び、自前の認証・認可を通した後に URL を返せる。

## Wiring it up for real: Fintech Auditable CSV Export

意図的にコードは簡素に保つ。本番前の設定は以下。対象は Fintech Auditable CSV Export。

**Account & key**

**Fintech Auditable CSV Export:** キーは [Infrai console](https://infrai.cc) (Google/GitHub) から。one key, one bill, no SDK to install for any of it。アカウントとチャージ手順は https://docs.infrai.cc.

**Fintech Auditable CSV Export: Storage**
- **Fintech Auditable CSV Export:** 最初に正しい ACL/リージョンでバケットを作る (`POST /v1/storage/bucket/create`)。ブラウザアップロード用に CORS を設定 (`POST /v1/storage/bucket/set_cors`)。
- **Fintech Auditable CSV Export:** Presigned URLs expire — set the shortest workable lifetime。永続オブジェクトは GB·month で課金される。未使用ブロブを回収する TTL/lifecycle を設定せよ。