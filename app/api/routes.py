import os
import tempfile
import zipfile
import shutil
import json
import re
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import traceback

from app.services import pdf_uploader
from app.services import question_answering
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
async def process_pdf_endpoint(file: UploadFile = File(...)):
    temp_dir_for_zip_contents_manager = None
    temp_dir_path_str = None
    generated_pdf_path_original = None
    zip_file_to_send_path = None
    operation_succeeded = False

    all_source_ids = []
    _keys_used_temp = []
    extracted_data_list_for_context = []
    contexto_ajustado = "Contexto não pôde ser gerado devido a falhas no processamento."
    structured_summary = {"error": "Resumo não pôde ser gerado.", "details": "Etapa de sumarização não foi concluída ou falhou."}

    try:
        try:
            _source_ids_temp, _keys_used_temp = await pdf_uploader.processar_pdf_em_partes_e_enviar(file)
            if _source_ids_temp and _keys_used_temp and len(_source_ids_temp) == len(_keys_used_temp):
                all_source_ids = _source_ids_temp
                print(f"PDF uploader processou e obteve {len(all_source_ids)} source_id(s).")
            else:
                error_msg = f"Falha ao obter IDs de documento e chaves de API correspondentes do uploader. IDs: {_source_ids_temp}, Chaves: {_keys_used_temp}"
                print(f"Erro (Uploader): {error_msg}")
                extracted_data_list_for_context.append(f"Erro no Uploader: {error_msg}")
        except Exception as e_uploader:
            print(f"Erro crítico durante o upload do PDF (pdf_uploader): {e_uploader}")
            traceback.print_exc()
            extracted_data_list_for_context.append(f"Erro crítico no Uploader: {str(e_uploader)}")

        if all_source_ids:
            print(f"Iniciando extração de dados para {len(all_source_ids)} documento(s)...")
            for i in range(len(all_source_ids)):
                doc_id = all_source_ids[i]
                api_key_for_doc = _keys_used_temp[i] if i < len(_keys_used_temp) else None

                if not api_key_for_doc:
                    message = f"Chave de API ausente para doc_id {doc_id}. Pulando perguntas para este documento."
                    print(f"Aviso (Question Answering): {message}")
                    extracted_data_list_for_context.append(f"Para Doc ID {doc_id}: {message}")
                    continue
                try:
                    print(f"Fazendo perguntas para doc_id: {doc_id}...")
                    extracted_data = await question_answering.ask_questions(doc_id, api_key_for_doc)
                    if extracted_data:
                        extracted_data_list_for_context.append(extracted_data)
                    else:
                        message = f"Nenhum dado extraído para doc_id {doc_id}."
                        print(f"Aviso (Question Answering): {message}")
                        extracted_data_list_for_context.append(f"Para Doc ID {doc_id}: {message}")
                except Exception as e_qa:
                    message = f"Erro ao fazer perguntas para doc_id {doc_id}: {e_qa}"
                    print(f"Erro (Question Answering): {message}")
                    traceback.print_exc()
                    extracted_data_list_for_context.append(f"Para Doc ID {doc_id}: Erro na extração - {str(e_qa)}")
        elif not extracted_data_list_for_context:
             extracted_data_list_for_context.append("Nenhum documento foi processado pelo uploader, portanto, nenhuma pergunta foi feita.")

        if extracted_data_list_for_context:
            contexto_original_temp = "\n\n".join(filter(None, extracted_data_list_for_context))
            contexto_ajustado = ajustar_numeros_de_pagina(contexto_original_temp)
            if not contexto_ajustado.strip():
                contexto_ajustado = "Contexto final vazio ou contém apenas mensagens de erro/aviso. Verifique os logs."
        else:
            contexto_ajustado = "Não foi possível coletar dados para formar o contexto."
        print(f"Contexto preparado para sumarização (primeiros 100 chars): {contexto_ajustado[:100]}...")

        try:
            is_context_meaningful = contexto_ajustado and \
                                   "não pôde ser gerado" not in contexto_ajustado.lower() and \
                                   "nenhum documento foi processado" not in contexto_ajustado.lower() and \
                                   "contexto final vazio" not in contexto_ajustado.lower() and \
                                   len(contexto_ajustado.strip()) > 50

            if is_context_meaningful:
                print("Gerando resumo com LLM (summarizer)...")
                _summary_candidate = await summarizer.generate_summary(contexto_ajustado, all_source_ids)
                if _summary_candidate:
                    structured_summary = _summary_candidate
                    print("Resumo gerado com sucesso pelo LLM.")
                else:
                    message = "O sumarizador (LLM) retornou um resultado vazio ou inválido."
                    print(f"Erro (Summarizer): {message}")
                    structured_summary = {"error": message, "context_provided_to_llm": contexto_ajustado}
            else:
                message = "Sumarização (LLM) pulada: contexto insuficiente ou contém apenas erros."
                print(f"Aviso (Summarizer): {message}")
                structured_summary = {"error": message, "reason": contexto_ajustado}
        except Exception as e_summarizer:
            message = f"Erro ao gerar resumo com LLM (summarizer): {e_summarizer}"
            print(f"Erro (Summarizer): {message}")
            traceback.print_exc()
            structured_summary = {"error": message, "context_used_for_llm": contexto_ajustado}

        try:
            print("Tentando gerar PDF do resumo...")
            pdf_generator = PDFGenerator()
            _generated_pdf_path = await pdf_generator.create_summary_pdf(structured_summary)
            print(f"Timestamp após tentativa de geração de PDF: {datetime.now().strftime('%H:%M:%S')}")

            if _generated_pdf_path and os.path.exists(_generated_pdf_path):
                generated_pdf_path_original = _generated_pdf_path
                print(f"PDF do resumo gerado com sucesso: {generated_pdf_path_original}")
            else:
                print("Erro (PDF Generator): PDFGenerator não criou o arquivo PDF ou retornou um caminho inválido. PDF não será incluído no ZIP.")
        except Exception as e_pdf:
            print(f"Erro crítico ao gerar PDF do resumo (PDF Generator): {e_pdf}")
            traceback.print_exc()
            print("PDF do resumo não será incluído no ZIP devido a erro na geração.")
            if 'structured_summary' in locals() and isinstance(structured_summary, (dict, list)):
                print("Resumo estruturado (ou erro) que causou a falha na geração do PDF:")
                try:
                    print(json.dumps(structured_summary, indent=2, ensure_ascii=False))
                except Exception as print_err:
                    print(f"(Não foi possível imprimir structured_summary: {print_err})")
            elif 'structured_summary' in locals():
                 print(f"Resumo (string): {structured_summary}")

        print("Iniciando criação do arquivo ZIP...")
        temp_dir_for_zip_contents_manager = tempfile.TemporaryDirectory()
        temp_dir_path_str = temp_dir_for_zip_contents_manager.name

        pdf_name_in_zip = "relatorio_resumo.pdf"
        context_name_in_zip = "contexto_extracao.txt"
        summary_name_in_zip = "resumo_estruturado.json" if isinstance(structured_summary, (dict, list)) and not ("error" in structured_summary and len(structured_summary) <= 2) else "resumo_estruturado.txt"

        path_to_pdf_in_temp_dir = os.path.join(temp_dir_path_str, pdf_name_in_zip)
        path_to_context_in_temp_dir = os.path.join(temp_dir_path_str, context_name_in_zip)
        path_to_summary_in_temp_dir = os.path.join(temp_dir_path_str, summary_name_in_zip)

        files_to_zip_info = []

        if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
            try:
                shutil.copy(generated_pdf_path_original, path_to_pdf_in_temp_dir)
                files_to_zip_info.append((path_to_pdf_in_temp_dir, pdf_name_in_zip))
                print(f"Arquivo '{pdf_name_in_zip}' preparado para o ZIP.")
            except Exception as e_copy_pdf:
                print(f"Erro ao copiar PDF gerado ('{generated_pdf_path_original}') para diretório temporário: {e_copy_pdf}. PDF não será incluído.")
        else:
            print(f"PDF do resumo ('{pdf_name_in_zip}') não disponível para inclusão no ZIP.")

        try:
            with open(path_to_context_in_temp_dir, "w", encoding="utf-8") as f_context:
                f_context.write(contexto_ajustado)
            files_to_zip_info.append((path_to_context_in_temp_dir, context_name_in_zip))
            print(f"Arquivo '{context_name_in_zip}' preparado para o ZIP.")
        except Exception as e_write_context:
            print(f"Erro ao escrever arquivo de contexto ('{path_to_context_in_temp_dir}'): {e_write_context}. Contexto não será incluído.")

        try:
            with open(path_to_summary_in_temp_dir, "w", encoding="utf-8") as f_summary:
                if isinstance(structured_summary, (dict, list)):
                    json.dump(structured_summary, f_summary, indent=4, ensure_ascii=False)
                else:
                    f_summary.write(str(structured_summary))
            files_to_zip_info.append((path_to_summary_in_temp_dir, summary_name_in_zip))
            print(f"Arquivo '{summary_name_in_zip}' preparado para o ZIP.")
        except Exception as e_write_summary:
            print(f"Erro ao escrever arquivo de resumo estruturado ('{path_to_summary_in_temp_dir}'): {e_write_summary}. Resumo não será incluído.")

        fd_zip, zip_file_to_send_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd_zip)

        if not files_to_zip_info:
            print("Aviso: Nenhum arquivo de resultado (PDF, contexto, resumo) pôde ser preparado. Criando arquivo de status no ZIP.")
            status_content = f"Processamento do arquivo '{file.filename}' concluído com falhas em todas as etapas principais de geração de conteúdo.\n"
            status_content += f"Data/Hora: {datetime.now().isoformat()}\n"
            status_content += "Verifique os logs do servidor para detalhes.\n\n"
            status_content += "Dados parciais (podem indicar onde as falhas ocorreram):\n"
            status_content += f"Source IDs processados: {all_source_ids if all_source_ids else 'Nenhum ou falha no Uploader'}\n"
            status_content += f"Contexto (tentativa de formação): {contexto_ajustado}\n"
            status_content += f"Resumo Estruturado (tentativa de geração): "
            if isinstance(structured_summary, (dict, list)):
                status_content += json.dumps(structured_summary, indent=2, ensure_ascii=False)
            else:
                status_content += str(structured_summary)
            status_content += "\n"

            status_file_name_in_zip = "status_processamento.txt"
            path_to_status_in_temp_dir = os.path.join(temp_dir_path_str, status_file_name_in_zip)
            try:
                with open(path_to_status_in_temp_dir, "w", encoding="utf-8") as f_status:
                    f_status.write(status_content)
                files_to_zip_info.append((path_to_status_in_temp_dir, status_file_name_in_zip))
                print(f"Arquivo '{status_file_name_in_zip}' preparado para o ZIP.")
            except Exception as e_write_status:
                print(f"Erro crítico ao tentar escrever arquivo de status para o ZIP: {e_write_status}")

        with zipfile.ZipFile(zip_file_to_send_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            if not files_to_zip_info:
                print("Aviso: Nenhum arquivo para adicionar ao ZIP. O ZIP será criado vazio (ou com erro se a lib não permitir).")
            for file_path, arcname in files_to_zip_info:
                if os.path.exists(file_path):
                    zf.write(file_path, arcname=arcname)
                    print(f"Adicionado ao ZIP: '{arcname}' de '{file_path}'")
                else:
                    print(f"Aviso: Arquivo '{file_path}' (para ser '{arcname}') não encontrado no momento de zipar. Omitido.")

        operation_succeeded = True
        print(f"Processamento concluído. Enviando ZIP: {zip_file_to_send_path}")
        return FileResponse(
            path=zip_file_to_send_path,
            filename="resultado_processamento.zip",
            media_type="application/zip",
            background=BackgroundTask(os.remove, zip_file_to_send_path)
        )

    except Exception as e_global:
        error_message = f"Um erro global inesperado ocorreu durante o processamento: {str(e_global)}"
        print(f"ERRO GLOBAL: {error_message}")
        traceback.print_exc()

        if temp_dir_for_zip_contents_manager is None:
             temp_dir_for_zip_contents_manager = tempfile.TemporaryDirectory()
             temp_dir_path_str = temp_dir_for_zip_contents_manager.name

        if zip_file_to_send_path is None:
            try:
                fd_zip, zip_file_to_send_path = tempfile.mkstemp(suffix="-ERROR.zip")
                os.close(fd_zip)
            except Exception as e_temp_zip_fail:
                print(f"Falha ao criar arquivo ZIP temporário para log de erro: {e_temp_zip_fail}")
                raise HTTPException(status_code=500, detail=error_message) from e_global

        try:
            error_log_content = f"ERRO GLOBAL INESPERADO DURANTE O PROCESSAMENTO DO ARQUIVO '{file.filename}':\n\n"
            error_log_content += f"Mensagem: {str(e_global)}\n\n"
            error_log_content += "Traceback:\n"
            error_log_content += traceback.format_exc() + "\n\n"
            error_log_content += "Dados coletados até a falha (se disponíveis):\n"
            error_log_content += f"  Source IDs: {all_source_ids}\n"
            error_log_content += f"  Contexto Parcial: {contexto_ajustado[:500]}...\n"
            if isinstance(structured_summary, (dict, list)):
                 error_log_content += f"  Resumo Parcial/Erro: {json.dumps(structured_summary, indent=2, ensure_ascii=False)}\n"
            else:
                 error_log_content += f"  Resumo Parcial/Erro: {str(structured_summary)}\n"

            error_log_path = os.path.join(temp_dir_path_str, "global_error_log.txt")
            with open(error_log_path, "w", encoding="utf-8") as f_err_log:
                f_err_log.write(error_log_content)

            with zipfile.ZipFile(zip_file_to_send_path, 'w', zipfile.ZIP_DEFLATED) as zf_err:
                zf_err.write(error_log_path, arcname="global_error_log.txt")

            print(f"Erro global. Enviando ZIP de erro: {zip_file_to_send_path}")
            return FileResponse(
                path=zip_file_to_send_path,
                filename="falha_processamento.zip",
                media_type="application/zip",
                background=BackgroundTask(os.remove, zip_file_to_send_path)
            )
        except Exception as e_zipping_error_log:
            print(f"Falha adicional ao tentar criar ZIP com log de erro global: {e_zipping_error_log}")
            raise HTTPException(status_code=500, detail=error_message) from e_global

    finally:
        if temp_dir_for_zip_contents_manager:
            try:
                temp_dir_for_zip_contents_manager.cleanup()
                print(f"Diretório temporário '{temp_dir_path_str}' limpo.")
            except Exception as e_temp_dir:
                print(f"Erro ao limpar diretório temporário '{temp_dir_path_str}': {e_temp_dir}")

        if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
            try:
                os.remove(generated_pdf_path_original)
                print(f"PDF original gerado '{generated_pdf_path_original}' limpo.")
            except OSError as e_remove_pdf:
                print(f"Aviso: Não foi possível limpar o PDF original gerado '{generated_pdf_path_original}': {e_remove_pdf}")

        if not operation_succeeded and zip_file_to_send_path and os.path.exists(zip_file_to_send_path):
            try:
                print(f"Tentando limpar arquivo zip intermediário devido a falha antes do envio: {zip_file_to_send_path}")
            except OSError as e_remove_zip:
                print(f"Aviso: Não foi possível limpar o arquivo zip intermediário '{zip_file_to_send_path}' no bloco finally: {e_remove_zip}")