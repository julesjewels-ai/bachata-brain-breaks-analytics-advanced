from fastapi import FastAPI
from src.api.routes import router

app = FastAPI(
    title="Bachata Brain Breaks Analytics API",
    description="API for streaming analysis and data processing.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Bachata Analytics API is running"}
