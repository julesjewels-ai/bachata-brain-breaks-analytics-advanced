from fastapi import FastAPI
from src.api.routes import router as api_router

app = FastAPI(
    title="Bachata Brain Breaks Analytics API",
    description="API for high-performance bachata analytics and AI strategy generation.",
    version="1.0.0"
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Welcome to Bachata Brain Breaks Analytics API. Connect to /ws/generate-strategy for streaming analysis."}
