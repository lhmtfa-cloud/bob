from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse 
from app.services import pdf_uploader, question_answering, summarizer
from app.services.pdf_generator import PDFGenerator
import io 
import zipfile 
import os 

router = APIRouter()

@router.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...)):
    doc_id = await pdf_uploader.upload_pdf(file)
    extracted_data = await question_answering.ask_questions(doc_id)

    structured_summary = await summarizer.generate_summary(extracted_data, doc_id)
    pdf_generator = PDFGenerator() 
    output_pdf_path = await pdf_generator.create_summary_pdf(structured_summary)

   
    base_filename = os.path.splitext(file.filename)[0] if file.filename else "document"

 
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(output_pdf_path, arcname=f"{base_filename}_summary.pdf")
        zip_file.writestr(f"{base_filename}_extracted_data.txt", extracted_data.encode('utf-8'))
        zip_file.writestr(f"{base_filename}_structured_summary.txt", structured_summary.encode('utf-8'))
    zip_buffer.seek(0)
    zip_filename = f"{base_filename}_processed_files.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )

