import os
import tempfile
import zipfile
import shutil
import json 

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from app.services import pdf_uploader, question_answering, summarizer
from app.services.pdf_generator import PDFGenerator

router = APIRouter()

@router.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...)):    
    temp_dir_for_zip_contents_manager = None
    temp_dir_path = None 
    generated_pdf_path_original = None 
    zip_file_to_send_path = None 
    operation_succeeded = False 

    try:
        doc_ids = await pdf_uploader.processar_pdf_em_partes_e_enviar(file)  

        extracted_data_list = []
        for doc_id in doc_ids:

            extracted_data = await question_answering.ask_questions(doc_id)
            extracted_data_list.append(extracted_data)
        
        contexto = "\n\n".join(extracted_data_list)
        structured_summary = await summarizer.generate_summary(contexto, doc_ids)

        # --- PDF Generation ---
        try:
            pdf_generator = PDFGenerator()

            generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
            if not os.path.exists(generated_pdf_path_original):
                raise FileNotFoundError("PDFGenerator did not create the PDF file.")
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
                    print(f"(Could not print structured_summary: {print_err})")
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF summary: {str(e)}")

        # --- Prepare files for Zipping in a temporary directory ---
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
            f_context.write(contexto)

        with open(path_to_summary_in_temp_dir, "w", encoding="utf-8") as f_summary:
            if isinstance(structured_summary, (dict, list)):
                json.dump(structured_summary, f_summary, indent=4, ensure_ascii=False)
            else:
                f_summary.write(str(structured_summary))

        # --- Create the ZIP file ---
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
        error_message = f"An unexpected error occurred during file processing and zipping: {str(e)}"
        print(error_message) # Log to server console
        if 'structured_summary' in locals() and "Failed to generate PDF summary" not in str(e):
            print("Structured summary at time of error:")
            try:
                if isinstance(structured_summary, (dict, list)):
                    print(json.dumps(structured_summary, indent=2, ensure_ascii=False))
                else:
                    print(structured_summary)
            except Exception as print_err:
                print(f"(Could not print structured_summary: {print_err})")
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        # --- Cleanup ---
        if temp_dir_for_zip_contents_manager:
            try:
                temp_dir_for_zip_contents_manager.__exit__(None, None, None) 
            except Exception as e_temp_dir:
                print(f"Error cleaning up temporary directory '{temp_dir_path}': {e_temp_dir}")

        if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
            try:
                os.remove(generated_pdf_path_original)
            except OSError as e_remove_pdf:
                print(f"Warning: Could not clean up original PDF '{generated_pdf_path_original}': {e_remove_pdf}")


        if not operation_succeeded and zip_file_to_send_path and os.path.exists(zip_file_to_send_path):
            try:
                os.remove(zip_file_to_send_path)
                print(f"Cleaned up intermediate zip file due to error: {zip_file_to_send_path}")
            except OSError as e_remove_zip:
                print(f"Warning: Could not clean up intermediate zip file '{zip_file_to_send_path}': {e_remove_zip}")

