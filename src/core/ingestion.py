"""
Data Ingestion Services.
Implements the DataIngestionService protocol for various data sources.
"""
import random
import pandas as pd
from typing import List, Dict, Any
from pathlib import Path
from src.core.models import VideoAnalysisInput
from src.core.interfaces import DataIngestionService, DataIngestionError

class SimulationDataIngestionService:
    """
    Generates mock data for demonstration and testing purposes.
    """
    def ingest_data(self) -> pd.DataFrame:
        """
        Simulates ingesting channel data.
        """
        # Generate mock data
        titles = [
            'Basic Step Tutorial', 'Sensual Bachata Demo', 'Viral Short Dance',
            'Advanced Footwork', 'Partner Connection Secrets', 'Musicality 101',
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

        # Validate data using VideoAnalysisInput (Ensures type safety & security)
        validated_data = [VideoAnalysisInput(**record).model_dump() for record in raw_data]

        return pd.DataFrame(validated_data)

class CSVDataIngestionService:
    """
    Ingests data from a CSV file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def ingest_data(self) -> pd.DataFrame:
        """
        Reads CSV and validates content.
        """
        try:
            df = pd.read_csv(self.filepath)
        except FileNotFoundError:
             raise DataIngestionError(f"CSV file not found: {self.filepath}")
        except pd.errors.EmptyDataError:
            raise DataIngestionError("CSV file is empty")
        except Exception as e:
            raise DataIngestionError(f"Failed to read CSV: {e}")

        # Ensure required columns exist
        required_columns = {'video_id', 'title', 'views', 'retention_avg_pct', 'type'}
        if not required_columns.issubset(df.columns):
            missing = required_columns - set(df.columns)
            raise DataIngestionError(f"CSV is missing required columns: {missing}")

        # Validate each row
        validated_data = []
        for idx, row in df.iterrows():
            # Convert row to dict
            record = row.to_dict()
            try:
                # Validate using Pydantic model
                validated_data.append(VideoAnalysisInput(**record).model_dump())
            except Exception as e:
                raise DataIngestionError(f"Validation failed for row {idx + 1}: {e}")

        return pd.DataFrame(validated_data)
