import os
import logging
import shutil
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SOURCE_DATA_DIR = "/app/data"
SOURCE_ZIPS_DIR = "/app/processed_zips"
BACKUP_DIR = "/app/backups"

RETENTION_DAYS_DAILY = 7
RETENTION_DAYS_WEEKLY = 30

def create_backup(backup_type: str):

    if backup_type not in ['daily', 'weekly']:
        logging.error(f"Tipo de backup inválido: {backup_type}")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    temp_backup_source_dir = f"/tmp/backup_source_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.makedirs(temp_backup_source_dir, exist_ok=True)

    try:
        if os.path.exists(SOURCE_DATA_DIR):
            shutil.copytree(SOURCE_DATA_DIR, os.path.join(temp_backup_source_dir, 'data'))
        if os.path.exists(SOURCE_ZIPS_DIR):
            shutil.copytree(SOURCE_ZIPS_DIR, os.path.join(temp_backup_source_dir, 'processed_zips'))
 
        timestamp = datetime.now().strftime("%Y-%m-%d")
        archive_name = f"backup_{backup_type}_{timestamp}"
        archive_path = os.path.join(BACKUP_DIR, archive_name)

        shutil.make_archive(archive_path, 'zip', temp_backup_source_dir)
        
        logging.info(f"Backup '{backup_type}' criado com sucesso em: {archive_path}.zip")

    except Exception as e:
        logging.error(f"Falha ao criar o backup '{backup_type}': {e}")
    finally:
        if os.path.exists(temp_backup_source_dir):
            shutil.rmtree(temp_backup_source_dir)


def cleanup_old_backups():

    logging.info("Iniciando limpeza de backups antigos...")
    if not os.path.exists(BACKUP_DIR):
        logging.warning("Diretório de backup não encontrado. Pulando a limpeza.")
        return

    now = datetime.now()
    for filename in os.listdir(BACKUP_DIR):
        if not filename.startswith('backup_') or not filename.endswith('.zip'):
            continue

        try:
            parts = filename.replace('.zip', '').split('_')
            backup_type = parts[1]
            date_str = parts[2]
            backup_date = datetime.strptime(date_str, "%Y-%m-%d")

            if backup_type == 'daily':
                retention_days = RETENTION_DAYS_DAILY
            elif backup_type == 'weekly':
                retention_days = RETENTION_DAYS_WEEKLY
            else:
                continue

            if now - backup_date > timedelta(days=retention_days):
                file_path = os.path.join(BACKUP_DIR, filename)
                os.remove(file_path)
                logging.info(f"Backup antigo removido: {filename}")

        except (IndexError, ValueError) as e:
            logging.warning(f"Não foi possível processar o nome do arquivo '{filename}': {e}")
            continue
    logging.info("Limpeza de backups concluída.")