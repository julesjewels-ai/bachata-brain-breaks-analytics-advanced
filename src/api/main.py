from fastapi import FastAPI
from src.api.endpoints import router

app = FastAPI(
    title="Bachata Brain Breaks Analytics API",
    description="API for accessing analytics and AI insights via REST and WebSockets.",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
async def root():
    return {"message": "Welcome to Bachata Brain Breaks Analytics API. Connect to /ws/analyze for streaming."}
