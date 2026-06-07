import pytest
import pandas as pd
from src.core.ingestion import SimulationDataIngestionService


@pytest.mark.asyncio
async def test_simulation_data_ingestion_service():
    service = SimulationDataIngestionService()
    df = await service.ingest_data()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 20
    assert "video_id" in df.columns
    assert "title" in df.columns
    assert "views" in df.columns
    assert "retention_avg_pct" in df.columns
    assert "type" in df.columns

    types = df["type"].unique()
    assert set(types).issubset({"Long", "Shorts"})

    views = df["views"]
    assert (views >= 500).all()
    assert (views <= 500000).all()

    retention = df["retention_avg_pct"]
    assert (retention >= 20.0).all()
    assert (retention <= 95.0).all()
