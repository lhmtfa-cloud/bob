import os
import tempfile
import zipfile
import shutil
import json
import re 

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.services import pdf_uploader, question_answering, summarizer
from app.services.pdf_generator import PDFGenerator

def ajustar_numeros_de_pagina(raw_contexto_str: str) -> str:

    blocks = re.findall(r"(\{[\s\S]*?\})", raw_contexto_str)
    if not blocks:
        return raw_contexto_str

    page_offset = 0

    processed_first_document_header = False 
    adjusted_block_strings = []

    for block_str in blocks:
        modified_block_str = block_str 
        if "Tipo do documento:" in block_str:
            if processed_first_document_header: 
                page_offset += 10
            else: 
                processed_first_document_header = True

        elif "página:" in block_str:
            match = re.search(r"(página:\s*)(\d+)", modified_block_str)
            if match:
                prefix = match.group(1) 
                original_page_num_str = match.group(2) 
                try:
                    original_page_num = int(original_page_num_str)
                    new_page_num = original_page_num + page_offset
                    modified_block_str = re.sub(r"(página:\s*)\d+", 
                                                f"{prefix}{new_page_num}", 
                                                modified_block_str, 
                                                count=1)
                except ValueError:

                    pass 
        
        adjusted_block_strings.append(modified_block_str)

    return "\n\n".join(adjusted_block_strings)


router = APIRouter()

@router.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...)):

    temp_dir_for_zip_contents_manager = None
    temp_dir_path = None 
    generated_pdf_path_original = None 
    zip_file_to_send_path = None 
    operation_succeeded = False 

    try:
        # Envia as partes do PDF e retorna os IDs
        doc_ids = await pdf_uploader.processar_pdf_em_partes_e_enviar(file)  

        extracted_data_list = []
        for doc_id in doc_ids:
            extracted_data = await question_answering.ask_questions(doc_id) 
            extracted_data_list.append(extracted_data)
        
        contexto_original = "\n\n".join(extracted_data_list)
        
        contexto_ajustado = ajustar_numeros_de_pagina(contexto_original)
        
        structured_summary = await summarizer.generate_summary(contexto_ajustado, doc_ids)

        # --- Geração de PDF ---
        try:
            pdf_generator = PDFGenerator()
            generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
            if not os.path.exists(generated_pdf_path_original):
                raise FileNotFoundError("PDFGenerator não criou o arquivo PDF.")
        except Exception as e:
            print(f"Erro ao gerar PDF: {e}")
            if 'structured_summary' in locals(): 
                print("Resumo estruturado que causou o erro:")
                try:
                    if isinstance(structured_summary, (dict, list)):
                        print(json.dumps(structured_summary, indent=2, ensure_ascii=False))
                    else:
                        print(structured_summary)
                except Exception as print_err:
                    print(f"(Não foi possível imprimir structured_summary: {print_err})")
            #raise HTTPException(status_code=500, detail=f"Falha ao gerar resumo em PDF: {str(e)}")

        # --- Preparar arquivos para Zipping em um diretório temporário ---
        temp_dir_for_zip_contents_manager = tempfile.TemporaryDirectory()
        temp_dir_path = temp_dir_for_zip_contents_manager.__enter__() 
        
        pdf_name_in_zip = "summary.pdf"
        context_name_in_zip = "context.txt"
        
        if isinstance(structured_summary, (dict, list)):
            summary_name_in_zip = "structured_summary.json"
        else:
            summary_name_in_zip = "structured_summary.txt"

        path_to_pdf_in_temp_dir = os.path.join(temp_dir_path, pdf_name_in_zip)
        path_to_context_in_temp_dir = os.path.join(temp_dir_path, context_name_in_zip)
        path_to_summary_in_temp_dir = os.path.join(temp_dir_path, summary_name_in_zip)

        shutil.copy(generated_pdf_path_original, path_to_pdf_in_temp_dir)

        with open(path_to_context_in_temp_dir, "w", encoding="utf-8") as f_context:
            f_context.write(contexto_ajustado) 

        with open(path_to_summary_in_temp_dir, "w", encoding="utf-8") as f_summary:
            if isinstance(structured_summary, (dict, list)):
                json.dump(structured_summary, f_summary, indent=4, ensure_ascii=False)
            else:
                f_summary.write(str(structured_summary))

        # --- Criar o arquivo ZIP ---
        fd, zip_file_to_send_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)  

        with zipfile.ZipFile(zip_file_to_send_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(path_to_pdf_in_temp_dir, arcname=pdf_name_in_zip)
            zf.write(path_to_context_in_temp_dir, arcname=context_name_in_zip)
            zf.write(path_to_summary_in_temp_dir, arcname=summary_name_in_zip)
        
        operation_succeeded = True 
        return FileResponse(
            path=zip_file_to_send_path,
            filename="processed_output.zip", 
            media_type="application/zip",
            background=BackgroundTask(os.remove, zip_file_to_send_path) 
        )

    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Um erro inesperado ocorreu durante o processamento e zipping do arquivo: {str(e)}"
        print(error_message) 
        if 'structured_summary' in locals() and "Falha ao gerar resumo em PDF" not in str(e):
            print("Resumo estruturado no momento do erro:")
            try:
                if isinstance(structured_summary, (dict, list)):
                    print(json.dumps(structured_summary, indent=2, ensure_ascii=False))
                else:
                    print(structured_summary)
            except Exception as print_err:
                print(f"(Não foi possível imprimir structured_summary: {print_err})")
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        # --- Limpeza ---
        if temp_dir_for_zip_contents_manager:
            try:
                temp_dir_for_zip_contents_manager.__exit__(None, None, None) 
            except Exception as e_temp_dir:
                print(f"Erro ao limpar diretório temporário '{temp_dir_path}': {e_temp_dir}")

        if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
            try:
                os.remove(generated_pdf_path_original)
            except OSError as e_remove_pdf:
                print(f"Aviso: Não foi possível limpar o PDF original '{generated_pdf_path_original}': {e_remove_pdf}")

        if not operation_succeeded and zip_file_to_send_path and os.path.exists(zip_file_to_send_path):
            try:
                os.remove(zip_file_to_send_path)
                print(f"Arquivo zip intermediário limpo devido a erro: {zip_file_to_send_path}")
            except OSError as e_remove_zip:
                print(f"Aviso: Não foi possível limpar o arquivo zip intermediário '{zip_file_to_send_path}': {e_remove_zip}")

