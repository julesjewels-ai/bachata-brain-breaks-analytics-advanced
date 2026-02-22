"""
Data ingestion services.
"""
import random
import pandas as pd
from typing import List, Dict, Any
from src.core.interfaces import UserInterface
from src.core.models import VideoAnalysisInput

class SimulationDataIngestionService:
    """
    Simulates ingesting channel data (Shorts and Long-form).
    In a real app, this would connect to YouTube Analytics API.
    """
    def __init__(self, ui: UserInterface):
        self.ui = ui

    def ingest_data(self) -> pd.DataFrame:
        """
        Simulates ingesting channel data.
        """
        with self.ui.loading("Ingesting channel data..."):
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
            # Explicitly type the record to avoid MyPy strictness errors
            validated_data = []
            for record in raw_data:
                 typed_record: Dict[str, Any] = record
                 validated_data.append(VideoAnalysisInput(**typed_record).model_dump())

            return pd.DataFrame(validated_data)
