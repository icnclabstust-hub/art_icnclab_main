#!/usr/bin/env python3
"""
資料品質監控儀表板
提供即時資料品質監控、統計分析和視覺化
"""

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """品質指標"""

    COMPLETENESS = "completeness"  # 完整性
    ACCURACY = "accuracy"  # 準確性
    CONSISTENCY = "consistency"  # 一致性
    TIMELINESS = "timeliness"  # 時效性
    VALIDITY = "validity"  # 有效性
    UNIQUENESS = "uniqueness"  # 唯一性


class AlertLevel(Enum):
    """警報級別"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QualityScore:
    """品質分數"""

    metric: QualityMetric
    score: float  # 0-100
    details: dict[str, Any]
    timestamp: datetime


@dataclass
class DataQualityAlert:
    """資料品質警報"""

    alert_id: str
    level: AlertLevel
    metric: QualityMetric
    message: str
    affected_records: list[str]
    timestamp: datetime
    resolved: bool = False


@dataclass
class SourceQualityReport:
    """資料來源品質報告"""

    source_id: str
    source_name: str
    total_records: int
    quality_scores: dict[QualityMetric, float]
    overall_score: float
    alerts: list[DataQualityAlert]
    last_updated: datetime
    trend: str  # "improving", "stable", "declining"


class DataQualityMonitor:
    """資料品質監控器"""

    def __init__(self, output_dir: str = "quality_reports"):
        self.output_dir = output_dir
        self.alerts: list[DataQualityAlert] = []
        self.quality_history: dict[str, list[QualityScore]] = defaultdict(list)
        os.makedirs(output_dir, exist_ok=True)

    def assess_data_quality(
        self, data_records: list[dict[str, Any]], source_id: str = "unknown"
    ) -> SourceQualityReport:
        """評估資料品質"""
        logger.info(f"🔍 評估資料來源 {source_id} 的品質...")

        if not data_records:
            logger.warning(f"⚠️ {source_id} 沒有資料記錄")
            return self._create_empty_report(source_id)

        # 評估各項品質指標
        quality_scores = {}

        quality_scores[QualityMetric.COMPLETENESS] = self._assess_completeness(data_records)
        quality_scores[QualityMetric.ACCURACY] = self._assess_accuracy(data_records)
        quality_scores[QualityMetric.CONSISTENCY] = self._assess_consistency(data_records)
        quality_scores[QualityMetric.TIMELINESS] = self._assess_timeliness(data_records)
        quality_scores[QualityMetric.VALIDITY] = self._assess_validity(data_records)
        quality_scores[QualityMetric.UNIQUENESS] = self._assess_uniqueness(data_records)

        # 計算總體分數（加權平均）
        weights = {
            QualityMetric.COMPLETENESS: 0.25,
            QualityMetric.ACCURACY: 0.25,
            QualityMetric.CONSISTENCY: 0.15,
            QualityMetric.TIMELINESS: 0.10,
            QualityMetric.VALIDITY: 0.15,
            QualityMetric.UNIQUENESS: 0.10,
        }

        overall_score = sum(quality_scores[metric] * weight for metric, weight in weights.items())

        # 生成警報
        source_alerts = self._generate_alerts(quality_scores, source_id, data_records)

        # 分析趨勢
        trend = self._analyze_trend(source_id, overall_score)

        report = SourceQualityReport(
            source_id=source_id,
            source_name=self._get_source_name(source_id),
            total_records=len(data_records),
            quality_scores={k: v for k, v in quality_scores.items()},
            overall_score=overall_score,
            alerts=source_alerts,
            last_updated=datetime.now(),
            trend=trend,
        )

        logger.info(f"✅ {source_id} 品質評估完成，總分: {overall_score:.2f}")
        return report

    def _assess_completeness(self, records: list[dict[str, Any]]) -> float:
        """評估完整性"""
        if not records:
            return 0.0

        # 定義必需欄位
        required_fields = ["title", "description", "date", "creator"]
        optional_fields = ["medium", "dimensions", "provenance", "image"]

        total_score = 0
        for record in records:
            record_score = 0

            # 必需欄位（70%）
            for field in required_fields:
                if field in record and record[field]:
                    record_score += 70 / len(required_fields)

            # 可選欄位（30%）
            for field in optional_fields:
                if field in record and record[field]:
                    record_score += 30 / len(optional_fields)

            total_score += record_score

        return total_score / len(records)

    def _assess_accuracy(self, records: list[dict[str, Any]]) -> float:
        """評估準確性"""
        total_score = 0

        for record in records:
            record_score = 100  # 從滿分開始

            # 檢查日期格式
            if "date" in record:
                if not self._is_valid_date(record["date"]):
                    record_score -= 20

            # 檢查數值範圍
            if "quality_score" in record:
                score = record.get("quality_score", 0)
                if not (0 <= score <= 100):
                    record_score -= 15

            # 檢查文本長度合理性
            if "description" in record:
                desc_len = len(str(record["description"]))
                if desc_len < 10 or desc_len > 10000:
                    record_score -= 10

            total_score += max(0, record_score)

        return total_score / len(records) if records else 0

    def _assess_consistency(self, records: list[dict[str, Any]]) -> float:
        """評估一致性"""
        if len(records) < 2:
            return 100.0

        # 檢查欄位一致性
        field_sets = [set(record.keys()) for record in records]
        common_fields = set.intersection(*field_sets) if field_sets else set()
        all_fields = set.union(*field_sets) if field_sets else set()

        # 欄位一致性分數
        field_consistency = len(common_fields) / len(all_fields) if all_fields else 1.0

        # 檢查命名一致性
        naming_score = self._check_naming_consistency(records)

        # 綜合一致性分數
        consistency_score = (field_consistency * 0.6 + naming_score * 0.4) * 100

        return consistency_score

    def _check_naming_consistency(self, records: list[dict[str, Any]]) -> float:
        """檢查命名一致性"""
        # 檢查相似欄位的命名是否一致
        naming_patterns = defaultdict(int)

        for record in records:
            for key in record.keys():
                # 標準化命名
                standardized = key.lower().replace("-", "_").replace(" ", "_")
                naming_patterns[standardized] += 1

        # 如果大部分記錄使用相同的命名模式，分數較高
        if naming_patterns:
            max_pattern_count = max(naming_patterns.values())
            return max_pattern_count / len(records)

        return 1.0

    def _assess_timeliness(self, records: list[dict[str, Any]]) -> float:
        """評估時效性"""
        now = datetime.now()
        total_score = 0

        for record in records:
            # 檢查資料的更新時間
            if "timestamp" in record or "last_updated" in record or "created_at" in record:
                timestamp_field = (
                    record.get("timestamp")
                    or record.get("last_updated")
                    or record.get("created_at")
                )

                try:
                    if isinstance(timestamp_field, str):
                        record_time = datetime.fromisoformat(timestamp_field.replace("Z", "+00:00"))
                    else:
                        record_time = timestamp_field

                    age_days = (now - record_time).days

                    # 根據資料年齡評分
                    if age_days <= 7:
                        total_score += 100
                    elif age_days <= 30:
                        total_score += 90
                    elif age_days <= 90:
                        total_score += 75
                    elif age_days <= 365:
                        total_score += 60
                    else:
                        total_score += 40

                except:
                    total_score += 50  # 無法解析時間戳，給予中等分數

            else:
                total_score += 70  # 沒有時間戳，給予較高分數（可能是歷史資料）

        return total_score / len(records) if records else 0

    def _assess_validity(self, records: list[dict[str, Any]]) -> float:
        """評估有效性"""
        total_score = 0

        for record in records:
            record_score = 100

            # 檢查必需欄位是否為空
            if "title" in record and not record["title"]:
                record_score -= 30

            # 檢查資料類型是否正確
            if "quality_score" in record:
                try:
                    float(record["quality_score"])
                except (ValueError, TypeError):
                    record_score -= 20

            # 檢查URL格式
            url_fields = ["url", "image_url", "source_url"]
            for field in url_fields:
                if field in record and record[field]:
                    if not self._is_valid_url(record[field]):
                        record_score -= 10

            total_score += max(0, record_score)

        return total_score / len(records) if records else 0

    def _assess_uniqueness(self, records: list[dict[str, Any]]) -> float:
        """評估唯一性"""
        if len(records) < 2:
            return 100.0

        # 檢查重複記錄
        seen_titles = set()
        seen_ids = set()
        duplicate_count = 0

        for record in records:
            # 檢查標題重複
            title = record.get("title", "").lower().strip()
            if title:
                if title in seen_titles:
                    duplicate_count += 1
                else:
                    seen_titles.add(title)

            # 檢查ID重複
            record_id = record.get("id") or record.get("record_id")
            if record_id:
                if record_id in seen_ids:
                    duplicate_count += 1
                else:
                    seen_ids.add(record_id)

        # 計算唯一性分數
        uniqueness_score = (1 - (duplicate_count / len(records))) * 100
        return max(0, uniqueness_score)

    def _generate_alerts(
        self,
        quality_scores: dict[QualityMetric, float],
        source_id: str,
        records: list[dict[str, Any]],
    ) -> list[DataQualityAlert]:
        """生成品質警報"""
        alerts = []

        for metric, score in quality_scores.items():
            alert = None

            if score < 50:
                alert = DataQualityAlert(
                    alert_id=f"{source_id}_{metric.value}_{datetime.now().timestamp()}",
                    level=AlertLevel.CRITICAL,
                    metric=metric,
                    message=f"{metric.value}分數極低 ({score:.1f}/100)",
                    affected_records=[r.get("id", "unknown") for r in records[:5]],
                    timestamp=datetime.now(),
                )
            elif score < 70:
                alert = DataQualityAlert(
                    alert_id=f"{source_id}_{metric.value}_{datetime.now().timestamp()}",
                    level=AlertLevel.WARNING,
                    metric=metric,
                    message=f"{metric.value}分數偏低 ({score:.1f}/100)",
                    affected_records=[r.get("id", "unknown") for r in records[:3]],
                    timestamp=datetime.now(),
                )
            elif score < 85:
                alert = DataQualityAlert(
                    alert_id=f"{source_id}_{metric.value}_{datetime.now().timestamp()}",
                    level=AlertLevel.INFO,
                    metric=metric,
                    message=f"{metric.value}分數中等 ({score:.1f}/100)",
                    affected_records=[],
                    timestamp=datetime.now(),
                )

            if alert:
                alerts.append(alert)
                self.alerts.append(alert)

        return alerts

    def _analyze_trend(self, source_id: str, current_score: float) -> str:
        """分析品質趨勢"""
        history = self.quality_history.get(source_id, [])

        # 記錄當前分數
        self.quality_history[source_id].append(
            QualityScore(
                metric=QualityMetric.COMPLETENESS,  # 用於總體分數
                score=current_score,
                details={},
                timestamp=datetime.now(),
            )
        )

        if len(history) < 2:
            return "stable"

        # 計算趨勢
        recent_scores = [s.score for s in history[-5:]]  # 最近5次
        if len(recent_scores) >= 2:
            avg_change = (recent_scores[-1] - recent_scores[0]) / len(recent_scores)

            if avg_change > 2:
                return "improving"
            elif avg_change < -2:
                return "declining"

        return "stable"

    def _is_valid_date(self, date_str: Any) -> bool:
        """驗證日期格式"""
        if not date_str:
            return False

        try:
            # 嘗試多種日期格式
            date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y", "%d-%m-%Y", "%m/%d/%Y"]

            for fmt in date_formats:
                try:
                    datetime.strptime(str(date_str), fmt)
                    return True
                except:
                    continue

            return False
        except:
            return False

    def _is_valid_url(self, url: str) -> bool:
        """驗證URL格式"""
        if not url:
            return False

        return url.startswith(("http://", "https://"))

    def _get_source_name(self, source_id: str) -> str:
        """獲取資料來源名稱"""
        source_names = {
            "harvard_art_museums": "Harvard Art Museums",
            "met_museum": "Metropolitan Museum of Art",
            "europeana": "Europeana",
            "google_books": "Google Books",
            "google_scholar": "Google Scholar",
        }
        return source_names.get(source_id, source_id)

    def _create_empty_report(self, source_id: str) -> SourceQualityReport:
        """創建空報告"""
        return SourceQualityReport(
            source_id=source_id,
            source_name=self._get_source_name(source_id),
            total_records=0,
            quality_scores={metric: 0.0 for metric in QualityMetric},
            overall_score=0.0,
            alerts=[],
            last_updated=datetime.now(),
            trend="stable",
        )

    def generate_dashboard_data(self, reports: list[SourceQualityReport]) -> dict[str, Any]:
        """生成儀表板數據"""
        logger.info("📊 生成品質監控儀表板數據...")

        # 總體統計
        total_records = sum(r.total_records for r in reports)
        avg_overall_score = sum(r.overall_score for r in reports) / len(reports) if reports else 0

        # 分類統計
        quality_distribution = {
            "excellent": len([r for r in reports if r.overall_score >= 90]),
            "good": len([r for r in reports if 75 <= r.overall_score < 90]),
            "fair": len([r for r in reports if 60 <= r.overall_score < 75]),
            "poor": len([r for r in reports if r.overall_score < 60]),
        }

        # 警報統計
        alert_stats = {
            "critical": len(
                [a for a in self.alerts if a.level == AlertLevel.CRITICAL and not a.resolved]
            ),
            "warning": len(
                [a for a in self.alerts if a.level == AlertLevel.WARNING and not a.resolved]
            ),
            "info": len([a for a in self.alerts if a.level == AlertLevel.INFO and not a.resolved]),
        }

        # 趨勢統計
        trend_stats = {
            "improving": len([r for r in reports if r.trend == "improving"]),
            "stable": len([r for r in reports if r.trend == "stable"]),
            "declining": len([r for r in reports if r.trend == "declining"]),
        }

        # 各指標平均分數
        metric_averages = {}
        for metric in QualityMetric:
            scores = [r.quality_scores.get(metric, 0) for r in reports]
            metric_averages[metric.value] = sum(scores) / len(scores) if scores else 0

        dashboard = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_sources": len(reports),
                "monitoring_period": "real-time",
            },
            "overview": {
                "total_records": total_records,
                "average_quality_score": avg_overall_score,
                "quality_distribution": quality_distribution,
                "trend_statistics": trend_stats,
            },
            "alerts": {
                "summary": alert_stats,
                "active_alerts": [
                    {
                        "alert_id": a.alert_id,
                        "level": a.level.value,
                        "metric": a.metric.value,
                        "message": a.message,
                        "timestamp": a.timestamp.isoformat(),
                    }
                    for a in self.alerts
                    if not a.resolved
                ][-10:],  # 最近10個未解決警報
            },
            "metric_averages": metric_averages,
            "source_reports": [
                {
                    "source_id": r.source_id,
                    "source_name": r.source_name,
                    "total_records": r.total_records,
                    "overall_score": r.overall_score,
                    "quality_scores": {k.value: v for k, v in r.quality_scores.items()},
                    "trend": r.trend,
                    "alert_count": len(r.alerts),
                }
                for r in reports
            ],
        }

        logger.info("✅ 儀表板數據生成完成")
        return dashboard

    def save_dashboard(
        self, dashboard_data: dict[str, Any], filename: str = "quality_dashboard.json"
    ):
        """保存儀表板數據"""
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 儀表板數據已保存到 {output_path}")

    def generate_html_dashboard(self, dashboard_data: dict[str, Any]) -> str:
        """生成HTML儀表板"""
        # 資料來源卡片先在 f-string 外組好，再以單一變數插入。
        # 原本寫成三層同款三引號的巢狀 f-string，py3.11 不允許重用外層引號
        # （PEP 701 要到 3.12 才放寬）；且趨勢標籤的 dict 查表被寫成雙層大括號，
        # 在 f-string 中會逃逸成字面大括號而非查表，並留下一個落單的右括號。
        trend_labels = {
            "improving": "📈 改善中",
            "stable": "➡️ 穩定",
            "declining": "📉 下降中",
        }

        metric_tpl = (
            '<div class="metric">'
            '<div class="label">{label}</div>'
            '<div class="score" style="font-size: 1.2em;">{score:.0f}</div>'
            "</div>"
        )

        card_tpl = """
            <div class="source-card">
                <h3>{source_name} ({source_id})</h3>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div>總記錄數: <strong>{total_records:,}</strong></div>
                        <div>趨勢: <span class="trend {trend}">{trend_label}</span></div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 2em; color: #667eea; font-weight: bold;">{overall_score:.1f}</div>
                        <div style="font-size: 0.9em; color: #6b7280;">總分</div>
                    </div>
                </div>
                <div class="metric-grid" style="grid-template-columns: repeat(6, 1fr);">
                    {metrics}
                </div>
            </div>
"""

        source_cards_html = "".join(
            card_tpl.format(
                source_name=source["source_name"],
                source_id=source["source_id"],
                total_records=source["total_records"],
                trend=source["trend"],
                trend_label=trend_labels.get(source["trend"], source["trend"]),
                overall_score=source["overall_score"],
                metrics="".join(
                    metric_tpl.format(label=metric.split("_")[0][:4], score=score)
                    for metric, score in source["quality_scores"].items()
                ),
            )
            for source in dashboard_data["source_reports"]
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>藝術史資料品質監控儀表板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }}
        .header h1 {{
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #666;
            font-size: 1.1em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        .stat-card h3 {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-card .trend {{
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .trend.up {{ color: #10b981; }}
        .trend.down {{ color: #ef4444; }}
        .trend.stable {{ color: #6b7280; }}
        .section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        .alert {{
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .alert.critical {{
            background: #fee2e2;
            border-left: 4px solid #dc2626;
        }}
        .alert.warning {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
        }}
        .alert.info {{
            background: #dbeafe;
            border-left: 4px solid #3b82f6;
        }}
        .quality-bar {{
            height: 30px;
            background: #e5e7eb;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .quality-fill {{
            height: 100%;
            background: linear-gradient(90deg, #10b981 0%, #667eea 100%);
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            color: white;
            font-weight: bold;
        }}
        .source-card {{
            background: #f9fafb;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 15px;
        }}
        .source-card h3 {{
            color: #374151;
            margin-bottom: 15px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 15px;
        }}
        .metric {{
            text-align: center;
            padding: 10px;
            background: white;
            border-radius: 8px;
        }}
        .metric .label {{
            font-size: 0.8em;
            color: #6b7280;
        }}
        .metric .score {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎨 藝術史資料品質監控儀表板</h1>
            <p>即時監控資料品質，確保資料的準確性與完整性</p>
            <p style="margin-top: 10px; color: #999;">更新時間: {
            dashboard_data["metadata"]["generated_at"]
        }</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>總體品質分數</h3>
                <div class="value">{dashboard_data["overview"]["average_quality_score"]:.1f}</div>
                <div class="trend stable">滿分 100</div>
            </div>
            <div class="stat-card">
                <h3>資料來源數量</h3>
                <div class="value">{dashboard_data["metadata"]["total_sources"]}</div>
                <div class="trend stable">個資料源</div>
            </div>
            <div class="stat-card">
                <h3>總記錄數</h3>
                <div class="value">{dashboard_data["overview"]["total_records"]:,}</div>
                <div class="trend up">筆資料</div>
            </div>
            <div class="stat-card">
                <h3>待處理警報</h3>
                <div class="value">{
            dashboard_data["alerts"]["summary"]["critical"]
            + dashboard_data["alerts"]["summary"]["warning"]
        }</div>
                <div class="trend {
            "down" if dashboard_data["alerts"]["summary"]["critical"] > 0 else "stable"
        }">需要關注</div>
            </div>
        </div>

        <div class="section">
            <h2>📊 品質分佈</h2>
            <div class="metric-grid">
                <div class="metric">
                    <div class="label">優秀 (90+)</div>
                    <div class="score" style="color: #10b981;">{
            dashboard_data["overview"]["quality_distribution"]["excellent"]
        }</div>
                </div>
                <div class="metric">
                    <div class="label">良好 (75-89)</div>
                    <div class="score" style="color: #3b82f6;">{
            dashboard_data["overview"]["quality_distribution"]["good"]
        }</div>
                </div>
                <div class="metric">
                    <div class="label">一般 (60-74)</div>
                    <div class="score" style="color: #f59e0b;">{
            dashboard_data["overview"]["quality_distribution"]["fair"]
        }</div>
                </div>
                <div class="metric">
                    <div class="label">待改進 (<60)</div>
                    <div class="score" style="color: #ef4444;">{
            dashboard_data["overview"]["quality_distribution"]["poor"]
        }</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>⚠️ 即時警報</h2>
            {
            "".join(
                [
                    f'''
            <div class="alert {alert['level']}">
                <div>
                    <strong>{alert['metric'].upper()}</strong>
                    <div>{alert['message']}</div>
                    <small style="color: #6b7280;">{alert['timestamp']}</small>
                </div>
            </div>
            '''
                    for alert in dashboard_data["alerts"]["active_alerts"][:5]
                ]
            )
            if dashboard_data["alerts"]["active_alerts"]
            else '<p style="color: #10b981;">✅ 目前沒有警報</p>'
        }
        </div>

        <div class="section">
            <h2>📈 各項品質指標</h2>
            {
            "".join(
                [
                    f'''
            <div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span style="font-weight: 500;">{metric}</span>
                    <span style="color: #667eea; font-weight: bold;">{score:.1f}/100</span>
                </div>
                <div class="quality-bar">
                    <div class="quality-fill" style="width: {score}%;">
                    </div>
                </div>
            </div>
            '''
                    for metric, score in dashboard_data["metric_averages"].items()
                ]
            )
        }
        </div>

        <div class="section">
            <h2>📦 資料來源詳情</h2>
            {source_cards_html}
        </div>
    </div>
</body>
</html>"""

        output_path = os.path.join(self.output_dir, "quality_dashboard.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"🎨 HTML儀表板已生成: {output_path}")
        return output_path


def main():
    """主函數"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("🔍 藝術史資料品質監控系統")
    print("=" * 60)

    monitor = DataQualityMonitor()

    # 測試資料
    test_data = {
        "harvard_art_museums": [
            {
                "id": "001",
                "title": "The Starry Night",
                "description": "Famous painting by Van Gogh",
                "date": "1889",
                "creator": "Vincent van Gogh",
                "medium": "Oil on canvas",
                "quality_score": 95,
                "timestamp": "2025-10-15T10:00:00",
            },
            {
                "id": "002",
                "title": "Mona Lisa",
                "description": "Portrait by Leonardo da Vinci",
                "date": "1503",
                "creator": "Leonardo da Vinci",
                "medium": "Oil on panel",
                "quality_score": 98,
                "timestamp": "2025-10-14T15:30:00",
            },
        ],
        "met_museum": [
            {
                "id": "003",
                "title": "The Great Wave",
                "description": "",  # 缺少描述
                "date": "1831",
                "creator": "Hokusai",
                "quality_score": 85,
                "timestamp": "2025-09-20T12:00:00",
            }
        ],
        "europeana": [
            {
                "id": "004",
                "title": "Birth of Venus",
                "description": "Renaissance masterpiece",
                "date": "1486",
                "creator": "Botticelli",
                "medium": "Tempera on canvas",
                "image_url": "https://example.com/image.jpg",
                "quality_score": 92,
                "timestamp": "2025-10-10T09:00:00",
            }
        ],
    }

    # 評估各資料源
    reports = []
    for source_id, records in test_data.items():
        report = monitor.assess_data_quality(records, source_id)
        reports.append(report)
        print(f"\n📊 {report.source_name}: {report.overall_score:.2f}/100 (趨勢: {report.trend})")

    # 生成儀表板
    print("\n" + "=" * 60)
    dashboard_data = monitor.generate_dashboard_data(reports)

    # 保存數據
    monitor.save_dashboard(dashboard_data)

    # 生成HTML儀表板
    html_path = monitor.generate_html_dashboard(dashboard_data)

    print("\n✅ 品質監控完成！")
    print(f"📁 JSON數據: {os.path.join(monitor.output_dir, 'quality_dashboard.json')}")
    print(f"🎨 HTML儀表板: {html_path}")
    print("\n💡 在瀏覽器中打開 HTML 文件查看完整儀表板")


if __name__ == "__main__":
    main()
