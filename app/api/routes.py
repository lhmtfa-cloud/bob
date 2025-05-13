import os
import tempfile
import zipfile
import shutil
import json
import re 

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

# Supondo que os módulos são importados corretamente
# (adapte os caminhos se a estrutura do seu projeto for diferente)
from app.services import pdf_uploader # Contém processar_pdf_em_partes_e_enviar
from app.services import question_answering # Contém ask_questions (do Canvas)
from app.services import summarizer
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
async def process_pdf_endpoint(file: UploadFile = File(...)): # Renomeado para evitar conflito de nome
    temp_dir_for_zip_contents_manager = None
    temp_dir_path_str = None 
    generated_pdf_path_original = None 
    zip_file_to_send_path = None 
    operation_succeeded = False 

    try:
        # pdf_uploader.processar_pdf_em_partes_e_enviar retorna (source_ids, keys_used)
        all_source_ids, all_keys_used = await pdf_uploader.processar_pdf_em_partes_e_enviar(file) 

        if not all_source_ids or not all_keys_used or len(all_source_ids) != len(all_keys_used):
            # Log ou tratamento de erro se as listas estiverem vazias ou não corresponderem em tamanho
            error_msg = "Falha ao obter IDs de documento e chaves de API correspondentes do uploader."
            print(f"Erro: {error_msg} - IDs: {all_source_ids}, Chaves: {all_keys_used}")
            raise HTTPException(status_code=500, detail=error_msg)

        extracted_data_list = []
        for i in range(len(all_source_ids)):
            doc_id = all_source_ids[i]
            api_key_for_doc = all_keys_used[i]
            
            if not api_key_for_doc: # Segurança adicional
                 print(f"Aviso: Chave de API ausente para doc_id {doc_id}. Pulando perguntas para este documento.")
                 continue

            print(f"Fazendo perguntas para doc_id: {doc_id} usando sua chave API.")
            extracted_data = await question_answering.ask_questions(doc_id, api_key_for_doc) 
            extracted_data_list.append(extracted_data)
        
        contexto_original = "\n\n".join(filter(None, extracted_data_list)) # Filtra Nones se ask_questions retornar None
        
        contexto_ajustado = ajustar_numeros_de_pagina(contexto_original)
        
        # Para summarizer.generate_summary, talvez você queira passar todos os source_ids
        # ou apenas o primeiro, dependendo da lógica do seu sumarizador.
        # Se o sumarizador opera em um contexto combinado, all_source_ids pode ser ok.
        structured_summary = await summarizer.generate_summary(contexto_ajustado, all_source_ids)

        try:
            pdf_generator = PDFGenerator()
            generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
            if not generated_pdf_path_original or not os.path.exists(generated_pdf_path_original):
                raise FileNotFoundError("PDFGenerator não criou o arquivo PDF ou retornou um caminho inválido.")
        except Exception as e_pdf:
            print(f"Erro ao gerar PDF: {e_pdf}")
            if 'structured_summary' in locals(): 
                print("Resumo estruturado que causou o erro na geração do PDF:")
                try:
                    summary_to_print = structured_summary
                    if isinstance(summary_to_print, (dict, list)):
                        print(json.dumps(summary_to_print, indent=2, ensure_ascii=False))
                    else:
                        print(str(summary_to_print))
                except Exception as print_err:
                    print(f"(Não foi possível imprimir structured_summary: {print_err})")
            raise HTTPException(status_code=500, detail=f"Falha ao gerar resumo em PDF: {str(e_pdf)}")

        temp_dir_for_zip_contents_manager = tempfile.TemporaryDirectory()
        temp_dir_path_str = temp_dir_for_zip_contents_manager.name # Usar .name para obter o caminho
        
        pdf_name_in_zip = "summary.pdf"
        context_name_in_zip = "context.txt"
        
        if isinstance(structured_summary, (dict, list)):
            summary_name_in_zip = "structured_summary.json"
        else:
            summary_name_in_zip = "structured_summary.txt"

        path_to_pdf_in_temp_dir = os.path.join(temp_dir_path_str, pdf_name_in_zip)
        path_to_context_in_temp_dir = os.path.join(temp_dir_path_str, context_name_in_zip)
        path_to_summary_in_temp_dir = os.path.join(temp_dir_path_str, summary_name_in_zip)

        shutil.copy(generated_pdf_path_original, path_to_pdf_in_temp_dir)

        with open(path_to_context_in_temp_dir, "w", encoding="utf-8") as f_context:
            f_context.write(contexto_ajustado) 

        with open(path_to_summary_in_temp_dir, "w", encoding="utf-8") as f_summary:
            if isinstance(structured_summary, (dict, list)):
                json.dump(structured_summary, f_summary, indent=4, ensure_ascii=False)
            else:
                f_summary.write(str(structured_summary))

        fd_zip, zip_file_to_send_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd_zip) 

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
        error_message = f"Um erro inesperado ocorreu durante o processamento: {str(e)}"
        print(f"{error_message} - Traceback:")
        import traceback
        traceback.print_exc()
        
        if 'structured_summary' in locals() and "Falha ao gerar resumo em PDF" not in str(e):
            print("Resumo estruturado (se disponível) no momento do erro geral:")
            try:
                summary_to_print_on_error = structured_summary
                if isinstance(summary_to_print_on_error, (dict, list)):
                    print(json.dumps(summary_to_print_on_error, indent=2, ensure_ascii=False))
                else:
                    print(str(summary_to_print_on_error))
            except Exception as print_err_general:
                print(f"(Não foi possível imprimir structured_summary no erro geral: {print_err_general})")
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        if temp_dir_for_zip_contents_manager:
            try:
                temp_dir_for_zip_contents_manager.cleanup()
            except Exception as e_temp_dir:
                print(f"Erro ao limpar diretório temporário '{temp_dir_path_str}': {e_temp_dir}")

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
