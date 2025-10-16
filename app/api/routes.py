# routes.py (CORRIGIDO)

import os
import tempfile
import zipfile
import shutil
import re
import uuid
import asyncio
import logging
import math # Importar math para a função ceil
from pathlib import Path
from datetime import timedelta
from app.prompts.chatPDF import pCabecalho

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.services import limpar
from app.services import pdf_uploader
from app.services import question_answering
from app.services import summarizer
from app.services.pdf_generator import PDFGenerator
from app.services.state_tracker import set_processing_state, get_processing_state, ProcessingStage
from app.services.pdf_uploader import PAGINAS_POR_BLOCO
from . import crud, models, schemas, auth, database

router = APIRouter()
storage_dir = "/app/processed_zips"
os.makedirs(storage_dir, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ... (nenhuma alteração no início do arquivo) ...
@router.post("/token", response_model=schemas.Token, tags=["Autenticação"])
async def login_for_access_token(db: Session = Depends(database.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de utilizador ou palavra-passe incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.User, tags=["Utilizadores"])
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@router.put("/users/me/password", status_code=status.HTTP_204_NO_CONTENT, tags=["Utilizadores"])
async def change_current_user_password(
    password_data: schemas.UserPasswordChange,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    if not auth.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Palavra-passe atual incorreta")
    crud.update_user_password(db, user=current_user, new_password=password_data.new_password)
    return

@router.post("/process-pdf", status_code=202, tags=["Processamento"])
async def start_pdf_processing(
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    code = str(uuid.uuid4())
    crud.create_upload_record(db, user_id=current_user.id, filename=file.filename, tracking_code=code, status=ProcessingStage.RECEIVED.value)
    crud.increment_files_uploaded_stat(db, user_id=current_user.id)
    set_processing_state(code, ProcessingStage.RECEIVED)
    
    temp_file_path = os.path.join(tempfile.gettempdir(), f"{code}_{file.filename}")
    try:
        with open(temp_file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao guardar ficheiro: {str(e)}")
    
    asyncio.create_task(process_pdf_background(
        temp_file_path, 
        code, 
        file.filename, 
        db_session_factory=database.SessionLocal,
        user_api_key=current_user.api_key 
    ))
    return {
        "message": "Processamento iniciado",
        "tracking_code": code,
        "status_url": f"/processing-status/{code}",
    }

@router.get("/processing-status/{code}", tags=["Processamento"])
async def get_status(code: str, current_user: models.User = Depends(auth.get_current_active_user)):
    status = get_processing_state(code)
    if status is None:
        raise HTTPException(status_code=404, detail="Código de processamento não encontrado.")
    return {"code": code, "status": status.value if isinstance(status, ProcessingStage) else str(status)}

@router.get("/download/zip/{code}", tags=["Processamento"])
async def download_zip(code: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_admin_user)):
    upload_record = db.query(models.Upload).filter(models.Upload.tracking_code == code).first()
    if not upload_record:
        raise HTTPException(status_code=404, detail="Registo de upload não encontrado.")

    zip_path = os.path.join(storage_dir, f"{code}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Ficheiro ZIP não encontrado ou processamento não finalizado.")
    return FileResponse(path=zip_path, filename=f"processed_output_{code}.zip", media_type="application/zip")

@router.get("/download/pdf/{code}", tags=["Processamento"])
async def download_summary_pdf(code: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    upload_record = db.query(models.Upload).filter(models.Upload.tracking_code == code).first()
    if not upload_record:
        raise HTTPException(status_code=404, detail="Registo de upload não encontrado.")

    if upload_record.user_id != current_user.id and current_user.role not in [models.Role.admin, models.Role.superuser]:
         raise HTTPException(status_code=403, detail="Não autorizado a aceder a este ficheiro.")

    zip_path = os.path.join(storage_dir, f"{code}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Ficheiro ZIP não encontrado ou processamento não finalizado.")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            summary_pdf_name = "relatorio_resumo.pdf"
            if summary_pdf_name not in zf.namelist():
                raise HTTPException(status_code=404, detail="PDF de resumo não encontrado no arquivo.")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(zf.read(summary_pdf_name))
                tmp_path = tmp.name

        return FileResponse(path=tmp_path, filename=f"resumo_{code}.pdf", media_type="application/pdf", background=BackgroundTask(os.remove, tmp_path))

    except Exception as e:
        logger.error(f"Erro ao extrair PDF do ZIP: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar o ficheiro de download.")

@router.get("/users/me/uploads", response_model=list[schemas.UploadRecord], tags=["Utilizadores"])
async def read_user_uploads(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    return crud.get_uploads_by_user_id(db, user_id=current_user.id)


@router.post("/cancel-processing/{code}", status_code=status.HTTP_200_OK, tags=["Processamento"])
async def cancel_processing(code: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_active_user)):
    upload_record = db.query(models.Upload).filter(models.Upload.tracking_code == code, models.Upload.user_id == current_user.id).first()
    if not upload_record:
        raise HTTPException(status_code=404, detail="Processo não encontrado ou não pertence a si.")
    
    current_status = get_processing_state(code)
    if current_status not in [ProcessingStage.FINISHED, ProcessingStage.ERROR, None]:
        set_processing_state(code, ProcessingStage.CANCELLED)
        crud.update_upload_status(db, tracking_code=code, status=ProcessingStage.CANCELLED.value)
        return {"message": "Processo de cancelamento iniciado."}
    else:
        raise HTTPException(status_code=400, detail="O processo já foi finalizado ou não pôde ser cancelado.")


@router.get("/admin/dashboard", response_model=schemas.DashboardData, tags=["Administração"])
async def get_admin_dashboard(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    recent_uploads = crud.get_uploads_last_24h(db)
    user_stats = crud.get_all_user_stats(db)
    return {"recent_uploads": recent_uploads, "user_stats": user_stats}

@router.get("/admin/users", response_model=list[schemas.User], tags=["Administração"])
async def get_all_users(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    return crud.get_users(db)

@router.post("/admin/users", response_model=schemas.User, tags=["Administração"])
async def create_new_user(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Nome de utilizador já registado")
    
    try:
        return crud.create_user(db=db, user=user)
    except Exception as e:
        logger.error(f"Falha ao criar utilizador na base de dados: {e}")
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno ao criar o utilizador.")

@router.put("/admin/users/{user_id}/role", response_model=schemas.User, tags=["Administração"])
async def update_user_role(
    user_id: int,
    user_role: schemas.UserUpdateRole,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_superuser),
):
    user_to_update = crud.get_user(db, user_id)
    if not user_to_update:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    if user_to_update.role == models.Role.superuser:
        raise HTTPException(status_code=403, detail="Não é possível alterar o papel do superuser")
    return crud.update_user_role(db=db, user_id=user_id, role=user_role.role)

@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Administração"])
async def delete_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_admin_user),
):
    user_to_delete = crud.get_user(db, user_id)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    if user_to_delete.id == current_user.id:
        raise HTTPException(status_code=403, detail="Não pode apagar a si mesmo")
    if user_to_delete.role in [models.Role.admin, models.Role.superuser]:
        if current_user.role != models.Role.superuser:
            raise HTTPException(status_code=403, detail="Admins não podem apagar outros admins")
    
    crud.delete_user(db=db, user_id=user_id)
    return

async def execute_qa_for_document_direct(doc_id: str, api_key: str | None, proc_code: str, chunk_index: int) -> tuple[int, str]:
    print(f"[{proc_code}] Fazendo perguntas para doc_id: {doc_id} (Bloco {chunk_index})...")
    try:
        if not api_key:
            raise ValueError(f"Chave de API ausente para o Bloco {chunk_index}")
        extracted_data = await question_answering.ask_questions(doc_id, api_key)
        return (chunk_index, extracted_data or "")
    except Exception as e:
        print(f"[{proc_code}] Erro no QA para o Bloco {chunk_index}: {e}")
        return (chunk_index, "")
        
     
async def process_pdf_background(temp_file_path: str, code: str, original_filename: str, db_session_factory, user_api_key: str | None = None):
    generated_pdf_path_original = None
    pdf_marcado_path = str(Path(temp_file_path).with_name(f"{code}_marcado.pdf"))
    zip_file_final_path = os.path.join(storage_dir, f"{code}.zip")
    db = db_session_factory()
    
    try:
        def update_state(stage: ProcessingStage):
            if get_processing_state(code) == ProcessingStage.CANCELLED:
                print(f"[{code}] Cancelamento detectado. Interrompendo a tarefa.")
                raise InterruptedError("Processo cancelado pelo utilizador.")
            set_processing_state(code, stage)
            crud.update_upload_status(db, tracking_code=code, status=stage.value)

        update_state(ProcessingStage.PREPARING)

        texto_extraido_completo = limpar.extrair_texto_com_marcacao_de_paginas(temp_file_path)
        paginas_logicas = [p for p in texto_extraido_completo.split('---') if p.strip()]
        num_paginas_logicas = len(paginas_logicas)
        logger.info(f"[{code}] Documento original resultou em {num_paginas_logicas} páginas lógicas com conteúdo.")
        
        pdf_uploader.gerar_pdf_marcado_com_reportlab(texto_extraido_completo, pdf_marcado_path)

        update_state(ProcessingStage.UPLOADING)
        
        all_source_ids, _keys_used_temp = await pdf_uploader.processar_e_enviar_texto_em_blocos(
            texto_extraido_completo, 
            code,
            user_api_key=user_api_key
        )

        update_state(ProcessingStage.QA_PROCESSING)
        
        contexto_final_lista = []
        num_blocos_qa = len(all_source_ids)
        
        if all_source_ids:
            # 1. Extrair o cabeçalho UMA ÚNICA VEZ, usando o primeiro bloco como contexto
            print("A extrair cabeçalho do documento...")
            _, cabecalho_str = await question_answering.process_pdf(
                source_id=all_source_ids[0],
                num_blocos_qa=num_blocos_qa,
                chatpdf_api_key=_keys_used_temp[0],
                prompt_text=pCabecalho
                
            )
            contexto_final_lista.append(cabecalho_str)
            print("Cabeçalho extraído com sucesso.")

            # 2. Recriar os blocos de texto para enviar para a função de páginas
            blocos_de_texto = []
            for i in range(0, len(paginas_logicas), PAGINAS_POR_BLOCO):
                bloco = paginas_logicas[i : i + PAGINAS_POR_BLOCO]
                blocos_de_texto.append("---".join(bloco))

            # --- INÍCIO DO BLOCO DE CÓDIGO MODIFICADO ---
            # 3. Implementar lógica de pausa e retentativa
            
            # Constantes para a nova lógica de controle
            REQUEST_THRESHOLD = 10  # Número de blocos antes da primeira pausa longa
            LONG_PAUSE_DURATION = 30 # Duração da pausa em segundos
            MAX_RETRIES_AFTER_PAUSE = 4 # Máximo de tentativas para um bloco após falha

            requests_since_last_pause = 0
            resultados_dos_blocos_paginas = []

            for i, doc_id in enumerate(all_source_ids):
                if get_processing_state(code) == ProcessingStage.CANCELLED:
                    raise InterruptedError("Processo cancelado pelo utilizador.")

                # Verifica se atingiu o limiar de requisições para fazer uma pausa
                if requests_since_last_pause >= REQUEST_THRESHOLD:
                    logger.info(f"[{code}] Limiar de {REQUEST_THRESHOLD} blocos atingido. Pausando por {LONG_PAUSE_DURATION} segundos.")
                    await asyncio.sleep(LONG_PAUSE_DURATION)
                    requests_since_last_pause = 0 # Reseta o contador

                success = False
                # Loop de retentativas para o bloco atual
                for attempt in range(MAX_RETRIES_AFTER_PAUSE):
                    try:
                        # Garante que ainda temos blocos de texto para processar
                        if i >= len(blocos_de_texto):
                            logger.warning(f"[{code}] Tentando processar o bloco de QA {i+1}, mas não há bloco de texto correspondente.")
                            break 

                        logger.info(f"[{code}] Processando QA para o bloco {i + 1}/{num_blocos_qa} (Tentativa {attempt + 1}/{MAX_RETRIES_AFTER_PAUSE})...")
                        resultado_bloco = await question_answering.ask_questions(
                            source_id=doc_id,
                            num_blocos_qa=num_blocos_qa,
                            chatpdf_api_key=_keys_used_temp[i],
                            texto_do_bloco_atual=blocos_de_texto[i]
                        )
                        resultados_dos_blocos_paginas.append(resultado_bloco)
                        success = True
                        break # Sai do loop de retentativas se for bem-sucedido

                    except Exception as e:
                        logger.error(f"[{code}] Erro ao processar o bloco {i + 1} na tentativa {attempt + 1}: {e}")
                        if attempt < MAX_RETRIES_AFTER_PAUSE - 1:
                            logger.info(f"[{code}] Pausando por {LONG_PAUSE_DURATION}s antes da próxima tentativa.")
                            await asyncio.sleep(LONG_PAUSE_DURATION)
                        else:
                            logger.critical(f"[{code}] Falha definitiva ao processar o bloco {i + 1} após {MAX_RETRIES_AFTER_PAUSE} tentativas.")
                            # Adiciona uma mensagem de erro ao resultado final para este bloco
                            resultados_dos_blocos_paginas.append(f"[ERRO PROCESSANDO BLOCO {i+1}: Falha após {MAX_RETRIES_AFTER_PAUSE} tentativas]")
                
                if success:
                    requests_since_last_pause += 1

            contexto_final_lista.extend(resultados_dos_blocos_paginas)
            # --- FIM DO BLOCO DE CÓDIGO MODIFICADO ---
        
        contexto_corrigido_e_unido = "\n\n".join(contexto_final_lista)
        
        contexto_filtrado = limpar.filtrar_contexto_por_pagina(contexto_corrigido_e_unido, num_paginas_logicas)
        
        dados_estruturados_dict = limpar.estruturar_dados_finais(contexto_filtrado)
        
        update_state(ProcessingStage.SUMMARIZING)
        
        structured_summary = await summarizer.generate_summary(dados_estruturados_dict, all_source_ids, _keys_used_temp)
        
        update_state(ProcessingStage.GENERATING_PDF)
        pdf_generator = PDFGenerator()
        generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
        
        update_state(ProcessingStage.ZIPPING)
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copy(temp_file_path, os.path.join(temp_dir, original_filename))            
            shutil.copy(generated_pdf_path_original, os.path.join(temp_dir, "relatorio_resumo.pdf"))
            shutil.copy(pdf_marcado_path, os.path.join(temp_dir, "documento_marcado_ocr.pdf"))
            with open(os.path.join(temp_dir, "resumo_markdown.md"), "w", encoding="utf-8") as f: f.write(structured_summary)
            with open(os.path.join(temp_dir, "resposta_chatpdf_corrigida.txt"), "w", encoding="utf-8") as f: f.write(contexto_corrigido_e_unido)
            with zipfile.ZipFile(zip_file_final_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in Path(temp_dir).iterdir(): zf.write(file, arcname=file.name)
        
        update_state(ProcessingStage.FINISHED)
        crud.update_upload_status(db, tracking_code=code, status=ProcessingStage.FINISHED.value, zip_path=zip_file_final_path)

    except Exception as e:
        print(f"ERRO CRÍTICO NO PROCESSAMENTO: {e}")
        update_state(ProcessingStage.ERROR)
        import traceback
        traceback.print_exc()
    finally:
        for p in [temp_file_path, pdf_marcado_path, generated_pdf_path_original]:
            if p and os.path.exists(p): os.remove(p)
        db.close()

