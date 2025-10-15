import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Importações da sua aplicação
from app.api import models, database
from app.api.routes import router
from app.api.auth import create_superuser_on_startup

# Importação do novo módulo de backup
from app.services.backup_manager import create_backup, cleanup_old_backups

# Cria as tabelas no banco de dados, se não existirem
models.Base.metadata.create_all(bind=database.engine)

# Inicializa a aplicação FastAPI e o agendador
app = FastAPI(title="BobIA PDF Processor")
scheduler = AsyncIOScheduler()

# --- LÓGICA DE STARTUP E SHUTDOWN ATUALIZADA ---

@app.on_event("startup")
async def on_startup():
    """
    Executa tarefas na inicialização da aplicação.
    """
    # Cria o superusuário padrão, se não existir
    create_superuser_on_startup()

    # Agenda a tarefa de limpeza de backups antigos para executar diariamente à 01:00
    scheduler.add_job(
        cleanup_old_backups,
        'cron',
        hour=18,
        minute=00,
        id="cleanup_backups_job",
        name="Limpeza diária de backups antigos",
        replace_existing=True
    )
    
    # Agenda a tarefa de backup diário para executar diariamente às 02:00
    scheduler.add_job(
        create_backup,
        'cron',
        hour=17,
        minute=0,
        args=['daily'],
        id="daily_backup_job",
        name="Backup diário dos dados",
        replace_existing=True
    )
    
    # Agenda a tarefa de backup semanal para executar todo Domingo às 03:00
    scheduler.add_job(
        create_backup,
        'cron',
        day_of_week='sun',
        hour=3,
        minute=0,
        args=['weekly'],
        id="weekly_backup_job",
        name="Backup semanal dos dados",
        replace_existing=True
    )

    # Inicia o agendador
    scheduler.start()
    print("Agendador de backup e limpeza iniciado e tarefas agendadas.")

@app.on_event("shutdown")
async def on_shutdown():
    """
    Executa tarefas no encerramento da aplicação.
    """
    scheduler.shutdown()
    print("Agendador parado.")

# --- CONFIGURAÇÃO DAS ROTAS E FICHEIROS ESTÁTICOS (sem alterações) ---

# Define o diretório do frontend para servir os ficheiros estáticos (CSS, JS, etc.)
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# Inclui as rotas da API definidas em app/api/routes.py
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