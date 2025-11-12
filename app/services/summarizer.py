import logging
import httpx
import asyncio
import os
from dotenv import load_dotenv
from httpx import Proxy

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')
CHATPDF_MESSAGE_URL = 'https://api.chatpdf.com/v1/chats/message'

def build_proxy_url():
    if PROXY_HOST and PROXY_PORT:
        if PROXY_USER and PROXY_PASS:
            return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        else:
            return f"http://{PROXY_HOST}:{PROXY_PORT}"
    return None

async def ask_chatpdf(source_id: str, question: str, chatpdf_api_key: str, retries: int = 5, backoff_factor: float = 2):
    if not chatpdf_api_key or not isinstance(chatpdf_api_key, str):
        raise ValueError(f"CHATPDF_API_KEY é necessária e deve ser uma string. Recebido: {type(chatpdf_api_key)}")

    headers = {'x-api-key': chatpdf_api_key, 'Content-Type': 'application/json'}
    data = {'sourceId': source_id, 'messages': [{'role': 'user', 'content': question}]}
    proxy_url_str = build_proxy_url()
    transport = httpx.AsyncHTTPTransport(proxy=Proxy(url=proxy_url_str)) if proxy_url_str else None
    timeout_config = httpx.Timeout(15.0, read=60.0)
    last_exception = None

    async with httpx.AsyncClient(transport=transport, timeout=timeout_config) as client:
        for attempt in range(retries):
            try:
                response = await client.post(CHATPDF_MESSAGE_URL, headers=headers, json=data)
                response.raise_for_status()
                return response.json()['content']
            except httpx.HTTPStatusError as e:
                last_exception = e
                if 500 <= e.response.status_code < 600 and attempt + 1 < retries:
                    wait_time = backoff_factor * (2 ** attempt)
                    logging.warning(f"ChatPDF request failed with {e.response.status_code}. Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                else: raise
            except httpx.ReadTimeout as e:
                last_exception = e
                if attempt + 1 < retries:
                    wait_time = backoff_factor * (2 ** attempt)
                    logging.warning(f"ChatPDF request timed out. Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                last_exception = e
                raise
        if last_exception: raise last_exception


async def generate_summary(dados_estruturados: dict, source_ids: list, api_keys: list):
    if not dados_estruturados:
        return "[ERRO: DADOS ESTRUTURADOS VAZIOS OU INVÁLIDOS]"

    cabecalho = dados_estruturados.get("cabecalho", {})
    dados_agregados = dados_estruturados.get("dados_agregados", {})
    tipo = cabecalho.get("tipo do documento", "--")
    
    def formatar_para_exibicao(lista_de_itens: list) -> str:
        if not lista_de_itens: return "--"
        itens_sem_pagina = [item.split(' (Página')[0].strip() for item in lista_de_itens]
        return ", ".join(itens_sem_pagina)
    
    def formatar_campo_longo_para_pdf(lista_de_itens: list) -> str:
        if not lista_de_itens: return "--"
        return "_#_BREAK_#_".join(lista_de_itens)

    leis = formatar_para_exibicao(dados_agregados.get("leis", []))
    assinaturas = formatar_para_exibicao(dados_agregados.get("quem assinou", []))
    orgaos_envolvidos = formatar_para_exibicao(dados_agregados.get("órgãos envolvidos", []))
    
    cronologia_list = dados_agregados.get("resumo da página", [])
    cronologia_para_tabela = formatar_campo_longo_para_pdf(cronologia_list)
    
    resumo_narrativo = "[Nenhum resumo pôde ser gerado.]"
    if cronologia_list and source_ids and api_keys:
        try:
            TAMANHO_DO_BLOCO_CRONOLOGIA = 15 
            blocos_cronologia = [
                cronologia_list[i:i + TAMANHO_DO_BLOCO_CRONOLOGIA]
                for i in range(0, len(cronologia_list), TAMANHO_DO_BLOCO_CRONOLOGIA)
            ]
            
            prompt_resumo_intermediario = (
                "Com base na seguinte lista de eventos, crie um resumo conciso em um único parágrafo. "
                "Eventos: {cronologia_bloco}"
            )
            
            tasks_intermediarias = []
            for i, bloco in enumerate(blocos_cronologia):
                source_id_usado = source_ids[i % len(source_ids)]
                api_key_usada = api_keys[i % len(api_keys)]
                
                texto_do_bloco = ", ".join(bloco)
                prompt = prompt_resumo_intermediario.format(cronologia_bloco=texto_do_bloco)
                tasks_intermediarias.append(ask_chatpdf(source_id_usado, prompt, api_key_usada))
            
            logging.info(f"Gerando {len(tasks_intermediarias)} resumos intermediários...")
            resumos_intermediarios = await asyncio.gather(*tasks_intermediarias, return_exceptions=True)
            
            resumos_validos = [res for res in resumos_intermediarios if isinstance(res, str) and res]

            if resumos_validos:
                texto_consolidado = "\n".join(resumos_validos)
                
                prompt_final = (
                    "Com base nos seguintes parágrafos, que são resumos de partes de um documento, "
                    "crie um resumo narrativo final e coeso em um único parágrafo. "
                    "Conecte as ideias para contar a história completa do documento de forma fluida."
                    "\n--- RESUMOS INTERMEDIÁRIOS ---\n"
                    f"{texto_consolidado}"
                )
                
                logging.info("Gerando resumo narrativo final...")
                resumo_narrativo = await ask_chatpdf(source_ids[0], prompt_final, api_keys[0])

            if not resumo_narrativo or "[Falha" in resumo_narrativo:
                 resumo_narrativo = "[Falha ao gerar o resumo narrativo pelo ChatPDF.]"

        except Exception as e:
            logging.error(f"Erro CRÍTICO durante a sumarização hierárquica: {e}")
            resumo_narrativo = f"[ERRO ao gerar resumo: {e}]"

    markdown_final = f"""| item | detalhes |
|---|---|
| tipo do documento | {tipo} |
| Leis | {leis} |
| Assinaturas | {assinaturas} |
| órgãos envolvidos | {orgaos_envolvidos} |
| Resumo | {resumo_narrativo.replace('|', '\|')} |
| Cronologia | {cronologia_para_tabela} |"""
    
    return markdown_final