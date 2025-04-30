from pathlib import Path
from app.services.chatpdf_client import process_pdf
import os

async def ask_questions(doc_id):
    caminho_atual = Path(__file__).resolve().parent.parent.parent / 'data' / 'uploads'
    #print("___________________________________________________________________________________________________________________________________")
    #print(caminho_atual)
    file_path = Path(caminho_atual).glob("*.pdf")
    # Exemplo: pegando o primeiro arquivo encontrado (se houver)
    file_path = next(file_path, None)  # Retorna None se não houver arquivos
    #print("___________________________________________________________________________________________________________________________________")
    #print(file_path)
    source_id, resumo = process_pdf(file_path, doc_id)


    return resumo
