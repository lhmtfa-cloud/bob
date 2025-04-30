import os

upload_dir = os.getenv("UPLOAD_DIR", "./data/uploads")

async def upload_pdf(file):
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Simulate sending to API
    return f"doc_{file.filename}"