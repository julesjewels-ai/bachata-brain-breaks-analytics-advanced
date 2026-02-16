"""
Data ingestion services.
"""
import random
import pandas as pd
from src.core.models import VideoAnalysisInput
from src.core.interfaces import DataIngestionService

class SimulationDataIngestionService:
    """
    Simulates ingesting channel data (Shorts and Long-form).
    """
    def ingest_data(self) -> pd.DataFrame:
        """
        Generates mock data for testing/demo purposes.
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

        # Validate data using VideoAnalysisInput (Ensures type safety & security)
        validated_data = [
            VideoAnalysisInput.model_validate(record).model_dump()
            for record in raw_data
        ]

        return pd.DataFrame(validated_data)
