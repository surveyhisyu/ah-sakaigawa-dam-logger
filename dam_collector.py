import os
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
    df = df.copy()
    df.insert(0, "取得日時", now_jst.strftime("%Y-%m-%d %H:%M:%S"))

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


def main() -> None:
    now_jst = datetime.now(JST)
    print(f"データ取得開始: {now_jst.strftime('%Y-%m-%d %H:%M:%S')} (JST)")

    df = fetch_dam_csv()
    print(f"取得成功: {len(df)}行 x {len(df.columns)}列")

    target_df = filter_target_dam(df)
    print(f"ダムコード {TARGET_DAM_CODE} のデータ: {len(target_df)}行")

    append_to_daily_csv(target_df)
    print("完了")


if __name__ == "__main__":
    main()
