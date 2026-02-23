"""
Data ingestion services for Bachata Brain Breaks Analytics.
"""
import random
from typing import Any, List, Dict
import pandas as pd
from src.core.interfaces import DataIngestionService
from src.core.models import VideoAnalysisInput


class SimulationDataIngestionService(DataIngestionService):
    """
    Simulates data ingestion from an external source.
    """
    def ingest_data(self) -> pd.DataFrame:
        """
        Generates mock data for testing and development.
        """
        # Generate mock data
        titles = [
            'Basic Step Tutorial', 'Sensual Bachata Demo',
            'Viral Short Dance', 'Advanced Footwork',
            'Partner Connection Secrets', 'Musicality 101',
            'Funny Bloopers', 'Festival Vlog', 'Dip Technique', 'Spin Drill'
        ] * 2

        raw_data: List[Dict[str, Any]] = []
        for i in range(1, 21):
            raw_data.append({
                'video_id': f'vid_{i}',
                'title': titles[i-1],
                'views': random.randint(500, 500000),
                'retention_avg_pct': random.uniform(20.0, 95.0),
                'type': 'Long' if i % 3 != 0 else 'Shorts'
            })

        # Validate data using VideoAnalysisInput (Ensures type safety &
        # security)
        validated_data = [
            VideoAnalysisInput(**record).model_dump()
            for record in raw_data
        ]

        return pd.DataFrame(validated_data)
