# FastAPI PDF Summarization App

This service:
- Accepts a PDF upload
- Sends it to an API (e.g., for OCR/vectorization)
- Asks questions using LLMs
- Generates structured data via agent/system prompt
- Creates a summary PDF

## 🚀 Run Locally

```bash
docker-compose up --build