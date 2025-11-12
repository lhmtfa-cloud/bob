
import re
import os
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm, cm  
from reportlab.lib.enums import TA_LEFT
import os
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

try:
    arial_path = 'arial.ttf' 
    arial_bold_path = 'arialbd.ttf'

    if not os.path.exists(arial_path) and os.name == 'nt':
        arial_path_windows = 'C:/Windows/Fonts/arial.ttf'
        if os.path.exists(arial_path_windows):
            arial_path = arial_path_windows

    if not os.path.exists(arial_bold_path) and os.name == 'nt':
        arial_bold_path_windows = 'C:/Windows/Fonts/arialbd.ttf'
        if os.path.exists(arial_bold_path_windows):
            arial_bold_path = arial_bold_path_windows
    
    pdfmetrics.registerFont(TTFont('Arial', arial_path))
    pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
    FONT_FAMILY = 'Arial'
    FONT_FAMILY_BOLD = 'Arial-Bold'
except Exception as e:
    print(f"Alerta: Não foi possível registrar as fontes Arial. Usando Times como fallback. Erro: {e}")
    FONT_FAMILY = 'Times-Roman'
    FONT_FAMILY_BOLD = 'Times-Bold'


SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ABSOLUTE_LOGO_PATH = os.path.join(SCRIPT_DIRECTORY, "logo.png")

class PDFGenerator:

    LOGO_FILE_PATH = ABSOLUTE_LOGO_PATH 
    LOGO_MAX_HEIGHT_MM = 15 
    HEADER_PADDING_ABOVE_LOGO_MM = 5
    HEADER_PADDING_BELOW_LOGO_MM = 5
    
    TOTAL_HEADER_HEIGHT = (
        LOGO_MAX_HEIGHT_MM + 
        HEADER_PADDING_ABOVE_LOGO_MM + 
        HEADER_PADDING_BELOW_LOGO_MM
    ) * mm


    def __init__(self, output_dir="output_pdfs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _add_page_header(self, canvas, doc):
        if not os.path.exists(self.LOGO_FILE_PATH): 
            return
        try:
            logo = ImageReader(self.LOGO_FILE_PATH)
        except Exception:
            return
        img_original_width, img_original_height = logo.getSize()
        if img_original_height == 0: return
        aspect_ratio = img_original_width / float(img_original_height)
        logo_display_height = self.LOGO_MAX_HEIGHT_MM * mm
        logo_display_width = logo_display_height * aspect_ratio
        page_width = doc.pagesize[0]
        x_centered = (page_width - logo_display_width) / 2.0
        padding_above_logo = self.HEADER_PADDING_ABOVE_LOGO_MM * mm
        y_pos = doc.pagesize[1] - padding_above_logo - logo_display_height
        canvas.saveState()
        canvas.drawImage(logo, x_centered, y_pos, width=logo_display_width, height=logo_display_height, mask='auto', preserveAspectRatio=True)
        canvas.restoreState()

    def _prepare_data_for_table(self, markdown_text: str, styles: dict) -> list:
            processed_data = []
            markdown_rows = [line for line in markdown_text.splitlines() if line.startswith('|') and not line.startswith('|--')]

            for row_str in markdown_rows:
                parts = [p.strip() for p in row_str.strip('|').split('|')]
                if len(parts) != 2:
                    continue
                
                key, value = parts
                key_paragraph = Paragraph(key, styles['key_style'])

                if '_#_BREAK_#_' in value:
                    lines = value.split('_#_BREAK_#_')
                else:
                    value_with_newlines = re.sub(r'(\(Página\s+\d+\)),\s*', r'\1\n', value)
                    lines = value_with_newlines.split('\n')
                
                if lines:
                    first_line_paragraph = Paragraph(lines[0].strip(), styles['value_style'])
                    processed_data.append([key_paragraph, first_line_paragraph])
                
                for line in lines[1:]:
                    if line.strip():
                        line_paragraph = Paragraph(line.strip(), styles['value_style'])
                        processed_data.append(['', line_paragraph])

            return processed_data


    async def create_summary_pdf(self, structured_summary: str) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        nome_arquivo = f"{uuid.uuid4().hex}.pdf"
        caminho_pdf = os.path.join(self.output_dir, nome_arquivo)
        
        doc = SimpleDocTemplate(caminho_pdf, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=30*mm, bottomMargin=20*mm) 
        
        styles = {}
        base_style = getSampleStyleSheet()['Normal']
        base_style.fontName = FONT_FAMILY
        base_style.fontSize = 11
        base_style.leading = 14

        styles['key_style'] = ParagraphStyle(name='KeyStyle', parent=base_style, fontName=FONT_FAMILY_BOLD, alignment=TA_LEFT)
        styles['value_style'] = ParagraphStyle(name='ValueStyle', parent=base_style, alignment=TA_LEFT)

        try:
            prepared_data = self._prepare_data_for_table(structured_summary, styles)
            if not prepared_data:
                doc.build([], onFirstPage=self._add_page_header, onLaterPages=self._add_page_header)
                return caminho_pdf

            table = Table(prepared_data, colWidths=[doc.width * 0.25, doc.width * 0.75])
            
            style_commands = [
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4*mm),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4*mm),
                ('TOPPADDING', (0, 0), (-1, -1), 2*mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
                ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
            ]

            for i, row_data in enumerate(prepared_data):
                if i > 0 and row_data[0] == '':
                    style_commands.append(('LINEABOVE', (0, i), (0, i), 1, colors.whitesmoke))
                    style_commands.append(('LINEABOVE', (1, i), (1, i), 1, colors.white))

            table.setStyle(TableStyle(style_commands))

            doc.build([table], onFirstPage=self._add_page_header, onLaterPages=self._add_page_header)
            return caminho_pdf
            
        except Exception as e:
            print(f"Erro completo ao gerar PDF com ReportLab: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise