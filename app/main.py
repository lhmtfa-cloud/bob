import os
import time
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api import models, database, auth
from app.api.routes import router
from app.api.auth import create_superuser_on_startup

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="BobIA PDF Processor")
scheduler = AsyncIOScheduler()

STORAGE_DIR = "/app/processed_zips"
RETENTION_DAYS = 30

def cleanup_old_files():
    print("A executar a limpeza de ficheiros antigos...")
    now = time.time()
    cutoff = now - (RETENTION_DAYS * 86400)

    if not os.path.exists(STORAGE_DIR):
        return

    for filename in os.listdir(STORAGE_DIR):
        file_path = os.path.join(STORAGE_DIR, filename)
        if os.path.isfile(file_path):
            file_mtime = os.path.getmtime(file_path)
            if file_mtime < cutoff:
                print(f"A apagar ficheiro antigo: {filename}")
                os.remove(file_path)

@app.on_event("startup")
def on_startup():
    create_superuser_on_startup()
    scheduler.add_job(
        cleanup_old_files,
        trigger=IntervalTrigger(days=1),
        id="cleanup_job",
        name="Limpeza diária de ficheiros antigos",
        replace_existing=True,
    )
    scheduler.start()
    print("Agendador de limpeza iniciado, será executado diariamente.")


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()
    print("Agendador de limpeza parado.")

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
app.include_router(router)

@app.get("/login", response_class=FileResponse, tags=["Frontend"])
async def get_login_page():
    return os.path.join(frontend_dir, "login.html")

@app.get("/app", response_class=FileResponse, tags=["Frontend"])
async def get_main_app_page():
    return os.path.join(frontend_dir, "index.html")

@app.get("/admin", response_class=FileResponse, tags=["Frontend"])
async def get_admin_page():
    return os.path.join(frontend_dir, "admin.html")

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def read_root():
    return RedirectResponse(url="/login")
