import os
from datetime import datetime, timezone, timedelta

import pandas as pd

JST = timezone(timedelta(hours=9))
DATA_DIR = "data"
WEEKLY_DIR = os.path.join(DATA_DIR, "weekly")
TARGET_DAM_CODE = "90013"


def get_last_week_range(today_jst: datetime):
    """今日(JST)から見て「先週の月曜日〜日曜日」の日付リストを返す"""
    # weekday(): 月=0, 火=1, ... 日=6
    this_monday = today_jst.date() - timedelta(days=today_jst.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = this_monday - timedelta(days=1)

    days = []
    day = last_monday
    while day <= last_sunday:
        days.append(day)
        day += timedelta(days=1)
    return days


def main() -> None:
    today_jst = datetime.now(JST)
    days = get_last_week_range(today_jst)

    print(f"対象期間: {days[0]} 〜 {days[-1]}")

    dfs = []
    for day in days:
        filename = os.path.join(
            DATA_DIR, f"dam_data_{TARGET_DAM_CODE}_{day.strftime('%Y%m%d')}.csv"
        )
        if os.path.exists(filename):
            df = pd.read_csv(filename, encoding="utf-8-sig")
            dfs.append(df)
            print(f"読み込み: {filename} ({len(df)}行)")
        else:
            print(f"見つかりません(スキップ): {filename}")

    if not dfs:
        print("先週分のデータが1件も見つかりませんでした。処理を終了します。")
        return

    combined = pd.concat(dfs, ignore_index=True)

    os.makedirs(WEEKLY_DIR, exist_ok=True)

    # (1) 日付入りのアーカイブ用ファイル(過去分もすべて残る)
    out_filename = os.path.join(
        WEEKLY_DIR,
        f"dam_data_{TARGET_DAM_CODE}_{days[0].strftime('%Y%m%d')}-{days[-1].strftime('%Y%m%d')}.csv",
    )
    combined.to_csv(out_filename, index=False, encoding="utf-8-sig")
    print(f"保存しました: {out_filename} ({len(combined)}行)")

    # (2) 常に同じファイル名で上書きする「最新週」用ファイル
    # デスクネッツ等から固定URLでブックマークして毎週ダウンロードできるようにするため
    latest_filename = os.path.join(WEEKLY_DIR, "latest.csv")
    combined.to_csv(latest_filename, index=False, encoding="utf-8-sig")
    print(f"最新週ファイルも更新しました: {latest_filename}")


if __name__ == "__main__":
    main()
