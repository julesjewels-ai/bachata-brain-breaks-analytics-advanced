"""
Analytics Service for data ingestion and processing.
"""
import random
from typing import Dict
import pandas as pd
from src.core.domain import VideoAnalysisInput


class AnalyticsService:
    """
    Handles data ingestion, validation, and statistical analysis.
    """

    def ingest_data(self) -> pd.DataFrame:
        """
        Simulates ingesting channel data (Shorts and Long-form).
        """
        # Generate mock data
        titles = [
            'Basic Step Tutorial', 'Sensual Bachata Demo', 'Viral Short Dance',
            'Advanced Footwork', 'Partner Connection Secrets', 'Musicality 101',
            'Funny Bloopers', 'Festival Vlog', 'Dip Technique', 'Spin Drill'
        ] * 2

        raw_data = []
        for i in range(1, 21):
            raw_data.append({
                'video_id': f'vid_{i}',
                'title': titles[i-1],
                'views': random.randint(500, 500000),
                'retention_avg_pct': random.uniform(20.0, 95.0),
                'type': 'Long' if i % 3 != 0 else 'Shorts'
            })

        # Validate data using VideoAnalysisInput
        validated_data = [
            VideoAnalysisInput(**record).model_dump() for record in raw_data
        ]

        return pd.DataFrame(validated_data)

    def detect_outliers(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Implements statistical outlier detection for viral anomalies.
        """
        results: Dict[str, pd.DataFrame] = {}
        if df.empty:
            return results

        # Check if we have enough data to groupby
        if 'type' not in df.columns or 'views' not in df.columns:
            return results

        for v_type, group in df.groupby('type'):
            # Simple statistical outlier detection using Quantiles
            threshold = group['views'].quantile(0.90)
            results[str(v_type)] = group[group['views'] > threshold]

        return results
