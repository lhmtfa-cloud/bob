# BobIA

O que Bob faz:
- [x] Aceita upload de PDF
- [x] Envia o PDF para a API do ChatPDF
- [x] Pergunta para o chatPDF
- [x] Gera dados estruturados com agentes de IA locais
- [x] Cria um PDF com o resumo e assinaturas

## 🚀 Run Locally

 - Criar arquivo .env na raíz do projeto

```
CHATPDF_API_KEY1=sec_XXXXXX
CHATPDF_API_KEY2=sec_XXXXXX
CHATPDF_API_KEY3=sec_XXXXXX
PROXY_USER=usuario
PROXY_PASS=senha
PROXY_HOST=proxy01.seti.parana
PROXY_PORT=8080
```

 - Para executar o projeto rodar

```bash
docker-compose up --build

docker build --no-cache -t bob-fastapi-pdf .
docker run -d -p 8000:8000 --name bob-app bob-fastapi-pdf