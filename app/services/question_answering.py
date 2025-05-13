from pathlib import Path
from app.services.chatpdf_client import process_pdf 
from app.prompts.chatPDF import pBase 
import os 


async def ask_questions(doc_id: str, chatpdf_api_key: str):
    prompt_text = str(pBase)

    _source_id_returned, resumo = process_pdf(
        source_id=doc_id, 
        chatpdf_api_key=chatpdf_api_key,
        prompt_text=prompt_text
    )
    return resumo

