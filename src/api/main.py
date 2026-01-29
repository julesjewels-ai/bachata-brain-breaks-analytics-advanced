from fastapi import FastAPI
from src.api.routers import analytics

app = FastAPI(
    title="Bachata Brain Breaks Analytics API",
    description="API for accessing analytics and generating reports.",
    version="1.0.0"
)

app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
