import pytest
import pandas as pd
from src.core.ingestion import CSVDataIngestionService, SimulationDataIngestionService
from src.core.models import VideoAnalysisInput
from src.core.interfaces import DataIngestionError

def test_simulation_data_ingestion():
    service = SimulationDataIngestionService()
    df = service.ingest_data()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 20
    assert set(df.columns) == {'video_id', 'title', 'views', 'retention_avg_pct', 'type'}

def test_csv_ingestion_valid(tmp_path):
    # Create a valid CSV
    csv_file = tmp_path / "valid_data.csv"
    csv_content = """video_id,title,views,retention_avg_pct,type
vid_1,Test Video 1,1000,50.5,Shorts
vid_2,Test Video 2,2000,75.0,Long
"""
    csv_file.write_text(csv_content)

    service = CSVDataIngestionService(filepath=str(csv_file))
    df = service.ingest_data()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0]['video_id'] == 'vid_1'
    assert df.iloc[1]['type'] == 'Long'

def test_csv_ingestion_invalid_schema(tmp_path):
    # Create an invalid CSV (missing column)
    csv_file = tmp_path / "invalid_schema.csv"
    csv_content = """video_id,title,views
vid_1,Test Video 1,1000
"""
    csv_file.write_text(csv_content)

    service = CSVDataIngestionService(filepath=str(csv_file))
    with pytest.raises(DataIngestionError, match="CSV is missing required columns"):
        service.ingest_data()

def test_csv_ingestion_invalid_data(tmp_path):
    # Create an invalid CSV (bad type for views)
    csv_file = tmp_path / "invalid_data.csv"
    csv_content = """video_id,title,views,retention_avg_pct,type
vid_1,Test Video 1,not_a_number,50.5,Shorts
"""
    csv_file.write_text(csv_content)

    service = CSVDataIngestionService(filepath=str(csv_file))
    with pytest.raises(DataIngestionError, match="Validation failed for row"):
        service.ingest_data()
