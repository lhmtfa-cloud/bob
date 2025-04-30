from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="PDF Summary Generator")
app.include_router(router)