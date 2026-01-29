from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile

from src.core.services import AnalyticsService
from src.api.dependencies import get_analytics_service
from src.api.schemas import AnalysisResponse

router = APIRouter()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_data(
    service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Triggers the analytics pipeline and returns the strategy.
    (In a real app, this might accept a file upload or JSON body)
    """
    try:
        df = service.ingest_data()
        anomalies = service.detect_outliers(df)
        strategy = service.analyze_semantics(df)

        counts = {k: len(v) for k, v in anomalies.items()}

        return AnalysisResponse(
            message="Analysis complete",
            anomalies_count=counts,
            strategy=strategy
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/report")
async def generate_report(
    background_tasks: BackgroundTasks,
    service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Generates and returns the Excel report.
    """
    try:
        # Re-run analysis for simplicity (state management is out of scope for now)
        df = service.ingest_data()
        anomalies = service.detect_outliers(df)
        strategy = service.analyze_semantics(df)

        # Create a temporary file with .xlsx extension
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp_path = tmp.name

        filepath = service.generate_report(anomalies, strategy, filepath=tmp_path)

        if not os.path.exists(filepath):
             raise HTTPException(status_code=500, detail="Report generation failed")

        # Schedule cleanup
        background_tasks.add_task(os.remove, filepath)

        return FileResponse(
            path=filepath,
            filename="bachata_analytics.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))
