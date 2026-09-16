import os
import time
from datetime import datetime, timezone, timedelta
from io import StringIO

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JST = timezone(timedelta(hours=9))

BASE_URL = "https://kawa.pref.toyama.jp/camera/data/"
TARGET_DAM_CODE = "90013"
DATA_DIR = "data"
TARGET_MINUTE = 8  # 毎時何分に取得を合わせるか

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://kawa.pref.toyama.jp/camera/02condlist.html",
}

# 富山県サイトのCSVには列名(ヘッダー行)が含まれていないため、
# 固定の列名をこちらで割り当てる。
# ※「予備」列は全行で-99.9固定のため、境川ダムでは使われていない
#   欠測値・未使用のプレースホルダーと思われる。
COLUMN_NAMES = [
    "ダムコード",
    "日付",
    "時刻",
    "貯水位",
    "区分",
    "全流入量",
    "全放流量",
    "貯水率利水容量",
    "貯水率有効容量",
    "予備",
]


def fetch_dam_csv() -> pd.DataFrame:
    """富山県サイトから dam_data.csv を取得してDataFrameで返す"""
    url = BASE_URL + "dam_data.csv"
    response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    response.raise_for_status()
    response.encoding = "shift-jis"

    # 重要: header=None にして、1行目をデータ扱いする
    # (指定しないと1行目のデータが列名として誤認識され、
    #  月次CSVのヘッダー行が意味不明な値になったり、
    #  取得のたびに列名がズレて壊れる原因になる)
    df = pd.read_csv(StringIO(response.text), header=None)

    names = COLUMN_NAMES[: len(df.columns)]
    if len(names) < len(df.columns):
        names += [f"不明列{i}" for i in range(len(df.columns) - len(names))]
    df.columns = names

    # 「予備」列は境川ダムでは使われていない(-99.9固定)ため出力から除外する
    df = df.drop(columns=["予備"], errors="ignore")
    return df


def filter_target_dam(df: pd.DataFrame) -> pd.DataFrame:
    """対象ダムコードの行だけを抽出する"""
    dam_code_column = "ダムコード" if "ダムコード" in df.columns else None

    if dam_code_column is None:
        raise ValueError("ダムコード列が見つかりませんでした")

    filtered = df[df[dam_code_column].astype(str) == TARGET_DAM_CODE].copy()
    if filtered.empty:
        raise ValueError(f"ダムコード '{TARGET_DAM_CODE}' のデータが0件でした")
    return filtered


def append_to_daily_csv(df: pd.DataFrame) -> None:
    """JSTの日付ごとのファイル(data/dam_data_90013_YYYYMMDD.csv)に追記保存する"""
    os.makedirs(DATA_DIR, exist_ok=True)

    now_jst = datetime.now(JST)
    filename = os.path.join(
        DATA_DIR, f"dam_data_{TARGET_DAM_CODE}_{now_jst.strftime('%Y%m%d')}.csv"
    )
    file_exists = os.path.exists(filename)

    df.to_csv(
        filename,
        mode="a" if file_exists else "w",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
    )
    print(f"保存しました: {filename} ({len(df)}行)")


def append_to_all_csv(df: pd.DataFrame) -> None:
    """全期間分をまとめて1ファイルに追記保存する(data/dam_data_90013_all.csv)"""
    os.makedirs(DATA_DIR, exist_ok=True)

    filename = os.path.join(DATA_DIR, f"dam_data_{TARGET_DAM_CODE}_all.csv")
    file_exists = os.path.exists(filename)

    df.to_csv(
        filename,
        mode="a" if file_exists else "w",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
    )
    print(f"保存しました: {filename} ({len(df)}行)")


def wait_until_target_minute() -> None:
    """JSTの時計がTARGET_MINUTEになるまで待機する。

    GitHub Actionsのスケジュール実行は、指定した時刻ちょうどに
    始まる保証がなく、混雑状況によっては数分〜数十分ずれることがある。
    ワークフロー自体は早め(バッファを持たせた時刻)に起動しておき、
    ここで本当にTARGET_MINUTEになるまで待つことで、取得日時と
    サイト側の更新タイミングを毎回なるべく揃える。
    """
    now = datetime.now(JST)
    target = now.replace(minute=TARGET_MINUTE, second=0, microsecond=0)

    if now >= target:
        # すでにTARGET_MINUTEを過ぎている場合は待たずに即取得する
        # (遅延しすぎてこれ以上待つとデータが古くなるため)
        print(f"すでに{TARGET_MINUTE}分を過ぎているため、待たずに取得します")
        return

    wait_seconds = (target - now).total_seconds()
    print(f"{TARGET_MINUTE}分になるまで {wait_seconds:.0f}秒 待機します")
    time.sleep(wait_seconds)


def main() -> None:
    wait_until_target_minute()

    now_jst = datetime.now(JST)
    print(f"データ取得開始: {now_jst.strftime('%Y-%m-%d %H:%M:%S')} (JST)")

    df = fetch_dam_csv()
    print(f"取得成功: {len(df)}行 x {len(df.columns)}列")

    target_df = filter_target_dam(df)
    print(f"ダムコード {TARGET_DAM_CODE} のデータ: {len(target_df)}行")

    # サイト側の実際の更新間隔(10分刻み)とGitHub Actionsの起動遅延により、
    # 「時刻」列がXX:10やXX:20になることがある。1時間に1回のスナップショット
    # として扱いたいため、分の部分を強制的に00に書き換える。
    # (「取得日時」列は実際に取得した時刻のまま、正直な値を残す)
    target_df["時刻"] = target_df["時刻"].astype(str).str.split(":").str[0] + ":00"

    # 「取得日時」はここで1回だけ付与し、日次ファイル・全期間ファイルの
    # 両方に同じ値を使う
    target_df = target_df.copy()
    target_df.insert(0, "取得日時", now_jst.strftime("%Y-%m-%d %H:%M:%S"))

    append_to_daily_csv(target_df)
    append_to_all_csv(target_df)
    print("完了")


if __name__ == "__main__":
    main()
