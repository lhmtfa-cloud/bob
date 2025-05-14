import os
from fastapi import FastAPI
from app.api.routes import router
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PDF Summary Generator")
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")
app.include_router(router)