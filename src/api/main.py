from fastapi import FastAPI
from src.api.routes import router

app = FastAPI(
    title="Bachata Brain Breaks Analytics API",
    description="API for audience retention analysis and strategy generation.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def health_check():
    return {"status": "ok", "version": "1.0.0"}
