# 境川ダムデータ自動収集（GitHub Actions版）

`nisizatoriver-logger` と同じ考え方で、PCをつけっぱなしにせず
GitHub Actionsが1時間ごとに自動でデータを取得・保存します。

対象サイトはもともとCSVを直接配布しているため、Playwrightなどの
ブラウザ操作は不要で、`requests` + `pandas` だけで完結します。

## ファイル構成

```
（リポジトリ直下）
├── dam_collector.py          データ取得・保存スクリプト
├── requirements.txt          必要ライブラリ
├── .github/
│   └── workflows/
│       └── dam_scrape.yml    1時間ごとの自動実行設定
└── data/
    └── dam_data_90013_20260915.csv  日ごとの収集データ（自動生成）
```

## セットアップ手順

1. **GitHubで新規リポジトリを作成**
   例: `toyama-dam-logger`（`nisizatoriver-logger`と同じアカウントでOK）

2. **ファイルをアップロード**
   - `dam_collector.py` と `requirements.txt` をリポジトリ直下にアップロード
   - `dam_scrape.yml` は「Create new file」から
     `.github/workflows/dam_scrape.yml` というパスを直接入力して作成し、
     中身を貼り付ける（隠しフォルダは手動でパスごと作る必要があります）

3. **Workflow permissionsを変更**
   `Settings → Actions → General → Workflow permissions` を
   **「Read and write permissions」** に変更（これがないと自動コミットできません）

4. **手動実行して動作確認**
   `Actions` タブ → 「境川ダムデータ自動収集」→ `Run workflow` で
   一度手動実行し、`data/2026-09.csv` のようなファイルが
   自動でコミットされることを確認する

5. あとは放置でOK。毎時08分に自動でデータが追記されます。

## データ形式

- 日ごとにファイルを分割: `data/dam_data_90013_YYYYMMDD.csv`（PCで動かしていた版と同じファイル名規則）
- 先頭列に「取得日時」を追加（日本時間 JST）
- ダムコード90013の行のみを抽出して保存
- 列構成: 取得日時, ダムコード, 日付, 時刻, 貯水位, 区分, 全流入量, 全放流量, 貯水率利水容量, 貯水率有効容量, 予備
  （「予備」列は全行で-99.9固定のため、境川ダムでは使われていない欠測値・未使用のプレースホルダーと思われます）

### 重要: 元サイトのCSVには列名が入っていない

富山県サイトが配布する`dam_data.csv`にはヘッダー行がなく、そのまま読み込むと
1行目のデータを列名と誤認識してしまいます（これが原因で、以前PCで運用していた
際に統合Excelファイルが数百列にまで膨れ上がる不具合がありました）。
`dam_collector.py`では`header=None`で読み込み、固定の列名を明示的に割り当てる
ことでこれを回避しています。

## 注意点・前回との違い

- **Excel(.xlsx)への統合保存はしていません。** git管理はテキスト形式のCSVと
  相性が良い一方、xlsxのようなバイナリファイルを毎回追記するとファイルが
  肥大化し、変更履歴も見えなくなるためです。CSVを溜めておけば、あとで
  Excelで開く・pandasで結合するのはいつでもできます。
- サイトが元々CSVを配っているため、時刻はサーバー側のCSVの値をそのまま
  使いつつ、「取得日時」列だけこちら側でJST基準にして付与しています。
  （river.go.jp版のように、ブラウザのタイムゾーン設定で「今」を判定させる
  必要はありません）
- cronは `"8 * * * *"`（毎時8分）としています。ちょうど0分は世界中の
  ワークフローが集中するため公式に非推奨、という点は前回と同じ理由です。

## トラブルシューティング

- **新規アカウント直後は自動実行(schedule)がブロックされることがある**
  → 前回同様、作成から24〜48時間程度で解除されることが多いです。
    それまでは `workflow_dispatch`（手動実行）だけ使えます。
- **エラー: dam_data.csv (404)**
  → ブラウザで `https://kawa.pref.toyama.jp/camera/data/dam_data.csv`
    にアクセスできるか確認してください。サイト構造が変わった可能性があります。
- **ダムコード90013が見つからない**
  → `https://kawa.pref.toyama.jp/camera/02condlist.html?id=0&sel=3` で
    正しいダムコードを確認し、`dam_collector.py` の `TARGET_DAM_CODE` を修正してください。
- **失敗時のメール通知を止めたい**
  → `Settings → Notifications → Email notification preferences` から停止できます。
