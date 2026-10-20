"""
构建真实舆情时间序列（mirofish/seed/real_timeline.csv）
来源：
  - data/02_weibo/hourly_counts.csv      辟谣帖评论量（小时级）
  - data/06_analysis/sentiment_hourly.csv 小时级 SnowNLP 情感均值
  - data/01_official/official_debunks.csv 官方通报时间戳（用于标注干预节点）
输出列：hour, comments, mean_sentiment, n_sentiment, event_flag
局限（写入报告）：
  - 评论全部采集自辟谣帖下方，不能代表谣言原帖扩散；
  - SnowNLP 负面 ≠ 信谣/恐慌/囤货（仅情绪极性参考）；
  - 2026-09-06 前后数据稀疏（hourly_counts 44 行内存在长间隔）。
"""
import pandas as pd

REPO_ROOT = "C:/Users/Kevin/Desktop/gba-public-governance-data-analysis-6th"
OUT = f"{REPO_ROOT}/mirofish/seed/real_timeline.csv"

# 官方关键干预节点（GMT+8，源自 official_debunks.csv 与 Seed §1.2 时间线）
EVENTS = {
    "2026-08-09T17:00:00+08:00": "台风白海豚玉环登陆（真实灾情）",
    "2026-08-10T08:00:00+08:00": "浦东警方首发辟谣通报（首次官方定性，08:35）",
    "2026-08-11T11:00:00+08:00": "上海网络辟谣通报两人行拘（11:16）",
    "2026-08-11T17:00:00+08:00": "上海警方总通报12人被处罚（17:07/17:17）",
}


def main():
    hourly = pd.read_csv(f"{REPO_ROOT}/data/02_weibo/hourly_counts.csv")
    senti = pd.read_csv(f"{REPO_ROOT}/data/06_analysis/sentiment_hourly.csv")

    # 统一为 ISO 时间格式
    hourly["hour"] = pd.to_datetime(hourly["hour"]).dt.tz_convert("Asia/Shanghai")
    senti["hour"] = pd.to_datetime(senti["hour"]).dt.tz_convert("Asia/Shanghai")

    df = pd.merge(hourly, senti.rename(columns={"n": "n_sentiment"}), on="hour", how="outer")
    df = df.sort_values("hour").reset_index(drop=True)
    df["comments"] = df["comments"].fillna(0).astype(int)
    df["event_flag"] = ""

    for ts, label in EVENTS.items():
        t = pd.Timestamp(ts)
        mask = (df["hour"] >= t) & (df["hour"] < t + pd.Timedelta(hours=1))
        df.loc[mask, "event_flag"] = label

    df["hour"] = df["hour"].dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    n_ev = (df["event_flag"] != "").sum()
    print(f"real_timeline.csv: {len(df)} 小时点, {n_ev} 个干预标注, "
          f"峰值 {df['comments'].max()} 条/小时")


if __name__ == "__main__":
    main()
