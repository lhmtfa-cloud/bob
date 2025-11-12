import os
import tempfile
import zipfile
import shutil
import re
import asyncio
import time 
import traceback 
from pathlib import Path

from fastapi import APIRouter

from app.services import limpar
from app.services import pdf_uploader
from app.services import question_answering
from app.services import summarizer
from app.services.pdf_generator import PDFGenerator
from app.services.state_tracker import set_processing_state, get_processing_state, ProcessingStage
from app.services.pdf_uploader import PAGINAS_POR_BLOCO
from . import crud

router = APIRouter()
storage_dir = "/app/processed_zips"
os.makedirs(storage_dir, exist_ok=True)

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
        
async def process_pdf_background(temp_file_path: str, code: str, original_filename: str, db_session_factory):
    generated_pdf_path_original = None
    pdf_marcado_path = str(Path(temp_file_path).with_name(f"{code}_marcado.pdf"))
    zip_file_final_path = os.path.join(storage_dir, f"{code}.zip")
    db = db_session_factory()
    
    start_time = time.time()  
    error_logs = []  
    try:
        def update_state(stage: ProcessingStage):
            set_processing_state(code, stage)
            crud.update_upload_status(db, tracking_code=code, status=stage.value)

        update_state(ProcessingStage.PREPARING)
        texto_extraido_completo = limpar.extrair_texto_com_marcacao_de_paginas(temp_file_path)
        num_paginas_logicas = len([p for p in texto_extraido_completo.split('---') if p.strip()])
        pdf_uploader.gerar_pdf_marcado_com_reportlab(texto_extraido_completo, pdf_marcado_path)

        update_state(ProcessingStage.UPLOADING)
        all_source_ids, _keys_used_temp = await pdf_uploader.processar_e_enviar_texto_em_blocos(
            texto_extraido_completo, code
        )

        update_state(ProcessingStage.QA_PROCESSING)
        contexto_bruto_lista = []
        if all_source_ids:
            qa_coroutines = [
                execute_qa_for_document_direct(doc_id, _keys_used_temp[i], code, i)
                for i, doc_id in enumerate(all_source_ids)
            ]
            resultados_com_indice = await asyncio.gather(*qa_coroutines)
            resultados_com_indice.sort(key=lambda x: x[0])
            contexto_bruto_lista = [res[1] for res in resultados_com_indice]
        
        partes_finais_contexto = []
        page_offset = 0
        pegou_primeiro_cabecalho = False

        for resposta_bloco in contexto_bruto_lista:
            if not resposta_bloco.strip():
                page_offset += PAGINAS_POR_BLOCO
                continue

            if not pegou_primeiro_cabecalho:
                cabecalho_match = re.search(r"(\{[\s\S]*?Tipo do documento:[\s\S]*?\})", resposta_bloco)
                if cabecalho_match:
                    partes_finais_contexto.append(cabecalho_match.group(1))
                    pegou_primeiro_cabecalho = True
            
            paginas_neste_bloco = re.findall(r"(\{[\s\S]*?página:[\s\S]*?\})", resposta_bloco)
            
            for bloco_pagina in paginas_neste_bloco:
                bloco_corrigido = re.sub(
                    r"(página:\s*)(\d+)",
                    lambda m: f"{m.group(1)}{int(m.group(2)) + page_offset}",
                    bloco_pagina, 1
                )
                partes_finais_contexto.append(bloco_corrigido)
            page_offset += PAGINAS_POR_BLOCO
        
        contexto_corrigido_e_unido = "\n\n".join(partes_finais_contexto)
        contexto_filtrado = limpar.filtrar_contexto_por_pagina(contexto_corrigido_e_unido, num_paginas_logicas)
        contexto_estruturado = limpar.estruturar_dados_finais(contexto_filtrado)
        
        update_state(ProcessingStage.SUMMARIZING)
        structured_summary = await summarizer.generate_summary(contexto_estruturado, code)
        
        update_state(ProcessingStage.GENERATING_PDF)
        pdf_generator = PDFGenerator()
        generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
        
        update_state(ProcessingStage.ZIPPING)
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copy(generated_pdf_path_original, os.path.join(temp_dir, "relatorio_resumo.pdf"))
            shutil.copy(pdf_marcado_path, os.path.join(temp_dir, "documento_marcado_ocr.pdf"))
            with open(os.path.join(temp_dir, "resumo_markdown.md"), "w", encoding="utf-8") as f: f.write(structured_summary)
            with open(os.path.join(temp_dir, "resposta_chatpdf_bruta_ordenada.txt"), "w", encoding="utf-8") as f: f.write("\n\n--- FIM DO BLOCO ---\n\n".join(contexto_bruto_lista))
            with open(os.path.join(temp_dir, "resposta_chatpdf_corrigida.txt"), "w", encoding="utf-8") as f: f.write(contexto_corrigido_e_unido)
           
            end_time = time.time()
            duration = end_time - start_time
            
            details_file_path = os.path.join(temp_dir, "processing_details.txt")
            with open(details_file_path, "w", encoding="utf-8") as f:
                f.write(f"Tempo de processamento: {duration:.2f} segundos\n")
                if error_logs:
                    f.write("\nLogs de Erro:\n")
                    for log in error_logs:
                        f.write(f"- {log}\n")

            with zipfile.ZipFile(zip_file_final_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in Path(temp_dir).iterdir(): zf.write(file, arcname=file.name)
        
        update_state(ProcessingStage.FINISHED)
        crud.update_upload_status(db, tracking_code=code, status=ProcessingStage.FINISHED.value, zip_path=zip_file_final_path)

    except Exception as e:
        print(f"ERRO CRÍTICO NO PROCESSAMENTO: {e}")
        error_logs.append(f"Erro: {e}\n{traceback.format_exc()}") 
        update_state(ProcessingStage.ERROR)
        import traceback
        traceback.print_exc()
    finally:
        for p in [temp_file_path, pdf_marcado_path, generated_pdf_path_original]:
            if p and os.path.exists(p): os.remove(p)
        db.close()