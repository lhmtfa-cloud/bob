import logging
import re
import tiktoken

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def estimate_tokens_openai_style(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def split_contexto_por_tokens(texto_completo: str, max_tokens_chunk: int, model_name: str) -> list[str]:
    if not texto_completo or not texto_completo.strip():
        return []

    if estimate_tokens_openai_style(texto_completo, model_name) <= max_tokens_chunk:
        return [texto_completo]
        
    segmentos = texto_completo.split('}')
    chunks = []
    chunk_atual = ""

    for i, segmento in enumerate(segmentos):
        if not segmento.strip() and i < len(segmentos) - 1:
            chunk_atual += '}'
            continue

        if i < len(segmentos) - 1:
            segmento_com_delimitador = segmento + '}'
        else:
            segmento_com_delimitador = segmento

        if not chunk_atual:
            chunk_atual = segmento_com_delimitador
            continue

        if estimate_tokens_openai_style(chunk_atual + segmento_com_delimitador, model_name) <= max_tokens_chunk:
            chunk_atual += segmento_com_delimitador
        else:
            chunks.append(chunk_atual)
            chunk_atual = segmento_com_delimitador
    
    if chunk_atual:
        chunks.append(chunk_atual)
        
    return [c for c in chunks if c.strip()]

def split_prose_text(text: str, max_tokens_chunk: int, model_name: str) -> list[str]:
    if not text or not text.strip():
        return []

    delimiters = r'(?<=[.!?])\s+|\n|(?=\(Página \d+\))|(?<=,)\s*(?=[A-ZÀ-Ú])'
    segments = [s.strip() for s in re.split(delimiters, text.strip()) if s and s.strip()]

    if not segments:
        return [text.strip()] if text.strip() else []

    chunks = []
    current_chunk = ""
    for segment in segments:
        if not current_chunk:
            current_chunk = segment
            continue

        if estimate_tokens_openai_style(current_chunk + " " + segment, model_name) <= max_tokens_chunk:
            current_chunk += " " + segment
        else:
            chunks.append(current_chunk)
            current_chunk = segment
            
    if current_chunk:
        chunks.append(current_chunk)
        
    return [c for c in chunks if c.strip()]