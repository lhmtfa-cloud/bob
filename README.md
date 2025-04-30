# BobIA

O que Bob faz:
- [x] Aceita upload de PDF
- [x] Envia o PDF para a API do ChatPDF
- [ ] Pergunta para o chatPDF
- [ ] Gera dados estruturados com agentes de IA locais
- [ ] Cria um PDF com o resumo e assinatura

## 🚀 Run Locally

 - Criar arquivo .env na raíz do projeto

```
CHATPDF_API_KEY=sec_XXXXXX
PROXY_USER=usuario
PROXY_PASS=senha
PROXY_HOST=proxy01.seti.parana
PROXY_PORT=8080
```

 - Para executar o projeto rodar

```bash
docker-compose up --build
