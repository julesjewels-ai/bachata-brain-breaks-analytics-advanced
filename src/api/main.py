from fastapi import FastAPI
from src.api.routes import router

app = FastAPI(
    title="Bachata Analytics API",
    description="API for Bachata Brain Breaks Analytics with Streaming AI capabilities.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "Bachata Analytics API is running. Documentation at /docs"}
