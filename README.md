# air-type

iPhone から同一 Wi-Fi 上の Mac を簡易リモート操作する Flask アプリ。テキスト入力、Enter / Backspace、画面プレビュー、タップでクリックに対応。

## 動作環境

- macOS（Apple Silicon / Intel）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- 同一 Wi-Fi 上の iPhone（Safari）

## セットアップ

```bash
uv sync
```

## 起動

```bash
./run.sh
# または
uv run python app.py
```

起動するとターミナルに `http://<MacのIP>:5050` が表示されるので、iPhone の Safari で開く。

## 必要な権限（macOS）

「システム設定 → プライバシーとセキュリティ」で以下を許可。許可するのは `app.py` を起動しているターミナル（iTerm / ターミナル.app など）。

- **アクセシビリティ** … キーボード入力・クリック送信のため
- **画面収録** … 画面プレビューのスクリーンショット取得のため

権限を変更した後はターミナルを再起動。

## 機能

| 機能 | 操作 |
| --- | --- |
| 文字入力（逐次） | テキストエリアに入力。1キー単位で Mac のフォーカス先にペーストされる |
| 日本語入力 | IME 確定単位で送信（`compositionend` を見て分岐） |
| ⌫（Backspace） | iPhone のキーボードの ⌫ で削除すると Mac 側にも転送 |
| ↵（Enter） | 「↵」ボタン |
| ズーム | 「−」「＋」ボタン。右上に現在の倍率表示 |
| プレビュー | 1 秒ごとに自動更新 |
| クリック | 「クリック」ボタンで ON にしてから画像をタップ |
| 追従 | 「追従」ボタン ON で、Mac のテキスト入力カーソル位置にプレビューを自動スクロール（Accessibility API 使用） |
| クリア | テキストバッファをローカルでリセット（Mac には送らない） |

## 設定（環境変数）

| 変数 | デフォルト | 用途 |
| --- | --- | --- |
| `PORT` | `5050` | サーバ待受ポート |
| `SCREENSHOT_WIDTH` | `1800` | プレビュー幅（px）。大きいほど鮮明だが帯域・CPU を消費 |
| `SCREENSHOT_QUALITY` | `70` | JPEG 品質（1–100） |

例: `PORT=8080 SCREENSHOT_WIDTH=2200 ./run.sh`

## ファイル構成

```
.
├── app.py              # Flask ルート
├── mac_io.py           # pyautogui / pyperclip / mss のラッパ
├── templates/
│   └── index.html      # iPhone 側 UI
├── pyproject.toml      # uv 管理
├── uv.lock
└── run.sh
```

## 注意

- `app.run(debug=True)` で起動しています。ローカル LAN 内専用とし、外部に公開しないでください（任意コード実行が可能なデバッガが開きます）。
- 1 文字ごとに Cmd+V を発火するので、超高速タイプ時はもたつくことがあります。
- クリック座標は `pyautogui.size()` の論理ピクセル基準です。マルチモニタは主モニタのみ対応。
