import os
from fpdf import FPDF
from datetime import datetime

summary_dir = os.getenv("SUMMARY_DIR", "./data/summaries")

async def create_summary_pdf(summary_data):
    os.makedirs(summary_dir, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in summary_data.items():
        pdf.multi_cell(0, 10, f"{key}: {value}")
    filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = os.path.join(summary_dir, filename)
    pdf.output(output_path)
    return output_path