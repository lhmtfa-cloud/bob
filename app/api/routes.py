from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from app.services import pdf_uploader, question_answering, summarizer, pdf_generator

router = APIRouter()

@router.post("/process-pdf")
async def process_pdf(file: UploadFile = File(...)):
    doc_id = await pdf_uploader.upload_pdf(file)
    extracted_data = await question_answering.ask_questions(doc_id)
    structured_summary = await summarizer.generate_summary(extracted_data)
    output_path = await pdf_generator.create_summary_pdf(structured_summary)
    return FileResponse(output_path, filename="summary.pdf", media_type="application/pdf")