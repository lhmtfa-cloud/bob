import re
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

# --- Bloco de registro de fontes (inalterado) ---
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

    def _add_header(self, canvas, doc):
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

    async def create_summary_pdf(self, structured_summary: str) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        
        tabela_processada = self._parse_structured_text_to_table(structured_summary)
        
        nome_arquivo = f"{uuid.uuid4().hex}.pdf"
        caminho_pdf = os.path.join(self.output_dir, nome_arquivo)
        
        try:
            self._gerar_pdf_reportlab(tabela_processada, caminho_pdf)
            return caminho_pdf
        except Exception:
            import traceback
            traceback.print_exc()
            raise

    def _parse_structured_text_to_table(self, texto: str) -> list[list[str]]:

        tabela_final = []
        item_atual = None
        detalhes_atuais = []

        linhas = texto.splitlines()

        for linha in linhas:
            linha_strip = linha.strip()
            if not linha_strip or linha_strip.startswith('|--'):
                continue

            if 'item' in linha_strip.lower() and 'detalhes' in linha_strip.lower() and len(linha_strip) < 50:
                 continue

            if linha_strip.startswith('|'):
                if item_atual is not None:
                    detalhes_str = "<br/>".join(detalhes_atuais).replace("<br/><br/>", "<br/>")

                    if item_atual.strip().lower() == 'resumo':
                        # --- ALTERAÇÃO PRINCIPAL AQUI ---
                        # Padrão agora captura o bloco inteiro, incluindo os parênteses
                        padrao = r'(\(P[áa]gina\s+\d+\))'
                        # Substituição coloca o <br/> DEPOIS do bloco capturado (\1)
                        substituicao = r'\1<br/>'
                        detalhes_str = re.sub(padrao, substituicao, detalhes_str, flags=re.IGNORECASE)
                    
                    tabela_final.append([item_atual, detalhes_str])
                    detalhes_atuais = []

                partes = [p.strip() for p in linha_strip.strip('|').split('|', 1)]
                item_atual = partes[0]
                
                if len(partes) > 1 and partes[1]:
                    detalhes_atuais.append(partes[1])
            
            elif item_atual is not None:
                 detalhes_atuais.append(linha_strip)

        if item_atual is not None:
            detalhes_str = "<br/>".join(detalhes_atuais).replace("<br/><br/>", "<br/>")
            
            if item_atual.strip().lower() == 'resumo':
                # Aplica a mesma lógica para o último item do loop
                padrao = r'(\(P[áa]gina\s+\d+\))'
                substituicao = r'\1<br/>'
                detalhes_str = re.sub(padrao, substituicao, detalhes_str, flags=re.IGNORECASE)

            tabela_final.append([item_atual, detalhes_str])
            
        tabela_final = [row for row in tabela_final if row[0].lower() not in ['item', 'detalhes']]
        tabela_final.insert(0, ['Item', 'Detalhes'])

        return tabela_final

    def _determine_reportlab_style(self, text_content, is_header_row, is_item_column, is_details_column, base_style):
        # A linha problemática foi REMOVIDA daqui.
        # Agora o texto com <br/> é passado diretamente para o Paragraph.
        text_to_draw = str(text_content)
        
        current_style = ParagraphStyle(name=f'Style_{uuid.uuid4().hex}', parent=base_style)
        is_markdown_bold = text_to_draw.startswith("**") and text_to_draw.endswith("**") and len(text_to_draw) > 4
        
        if is_markdown_bold:
            text_to_draw = text_to_draw[2:-2].strip()
            
        if is_header_row:
            current_style.fontName = FONT_FAMILY_BOLD
            current_style.alignment = TA_CENTER
        elif is_item_column:
            current_style.fontName = FONT_FAMILY_BOLD
            current_style.alignment = TA_CENTER
        elif is_details_column:
            current_style.alignment = TA_JUSTIFY
            
        if is_markdown_bold:
            current_style.fontName = FONT_FAMILY_BOLD
            if not is_details_column and current_style.alignment == TA_LEFT:
                 current_style.alignment = TA_CENTER
                 
        return text_to_draw, current_style

    def _gerar_pdf_reportlab(self, tabela_processada: list[list[str]], caminho_pdf: str):
        # ... (código de geração do PDF inalterado, pois agora ele recebe a tabela correta) ...
        doc = SimpleDocTemplate(caminho_pdf, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=self.TOTAL_HEADER_HEIGHT, 
                                bottomMargin=15*mm)
        elements = []
        styles = getSampleStyleSheet()
        base_paragraph_style = styles['Normal']
        base_paragraph_style.fontName = FONT_FAMILY 
        base_paragraph_style.fontSize = 12
        base_paragraph_style.leading = base_paragraph_style.fontSize * 1.5
        base_paragraph_style.alignment = TA_LEFT
        empty_cell_style = ParagraphStyle(name='EmptyCellStyleForSpan', parent=base_paragraph_style)
        if not tabela_processada:
            doc.build(elements, onFirstPage=self._add_header, onLaterPages=self._add_header)
            return
        num_cols = max(len(r) for r in tabela_processada) if tabela_processada else 0
        if num_cols == 0:
            doc.build(elements, onFirstPage=self._add_header, onLaterPages=self._add_header)
            return
        item_column_index = -1
        details_column_index = -1
        is_first_row_semantically_header = False
        if tabela_processada[0]:
            header_candidate = [str(h).strip().lower() for h in tabela_processada[0]]
            if "item" in header_candidate:
                item_column_index = header_candidate.index("item")
                is_first_row_semantically_header = True
            if "detalhes" in header_candidate:
                details_column_index = header_candidate.index("detalhes")
                is_first_row_semantically_header = True
        if num_cols == 2 and item_column_index == -1 and details_column_index == -1 :
            item_column_index = 0
            details_column_index = 1
        available_width_for_table = doc.width 
        col_widths_rl = None
        if num_cols == 1:
            col_widths_rl = [available_width_for_table]
        elif num_cols == 2:
            item_col_width_percent = 0.25 # Ajustado para dar mais espaço aos detalhes
            details_col_width_percent = 1.0 - item_col_width_percent
            if item_column_index == 0 and details_column_index == 1:
                 col_widths_rl = [available_width_for_table * item_col_width_percent, available_width_for_table * details_col_width_percent]
            elif item_column_index == 1 and details_column_index == 0:
                 col_widths_rl = [available_width_for_table * details_col_width_percent, available_width_for_table * item_col_width_percent]
            else: 
                 col_widths_rl = [available_width_for_table * item_col_width_percent, available_width_for_table * details_col_width_percent]
        else: 
            col_widths_rl = [available_width_for_table / num_cols] * num_cols
        data_for_rl_table = []
        WORDS_PER_CHUNK_DETAILS = 100
        for row_idx, original_row_content in enumerate(tabela_processada):
            # ... (restante do código da função inalterado) ...
            current_processed_cells = list(original_row_content)
            while len(current_processed_cells) < num_cols: current_processed_cells.append("")
            current_processed_cells = current_processed_cells[:num_cols]
            is_header_row_flag = (row_idx == 0 and is_first_row_semantically_header)
            if is_header_row_flag:
                header_row_paras = []
                for c_idx in range(num_cols):
                    text, style = self._determine_reportlab_style(
                        str(current_processed_cells[c_idx]), True, (c_idx==item_column_index), (c_idx==details_column_index), base_paragraph_style)
                    header_row_paras.append(Paragraph(text, style))
                data_for_rl_table.append(header_row_paras)
                continue
            item_text_for_row = str(current_processed_cells[item_column_index]) if item_column_index != -1 and item_column_index < num_cols else ""
            details_text_for_row = str(current_processed_cells[details_column_index]) if details_column_index != -1 and details_column_index < num_cols else ""
            other_cols_paras_for_row = {}
            for c_idx in range(num_cols):
                if c_idx != item_column_index and c_idx != details_column_index:
                    text, style = self._determine_reportlab_style(
                        str(current_processed_cells[c_idx]), False, False, False, base_paragraph_style)
                    other_cols_paras_for_row[c_idx] = Paragraph(text, style)
            detail_words = details_text_for_row.split()
            if details_column_index != -1 and len(detail_words) > WORDS_PER_CHUNK_DETAILS:
                first_chunk_for_this_item_entry = True
                for i in range(0, len(detail_words), WORDS_PER_CHUNK_DETAILS):
                    chunk_text = " ".join(detail_words[i:i+WORDS_PER_CHUNK_DETAILS])
                    row_segment_paras = [Paragraph("", empty_cell_style)] * num_cols
                    if item_column_index != -1:
                        if first_chunk_for_this_item_entry:
                            text, style = self._determine_reportlab_style(item_text_for_row, False, True, False, base_paragraph_style)
                            row_segment_paras[item_column_index] = Paragraph(text, style)
                    text, style = self._determine_reportlab_style(chunk_text, False, False, True, base_paragraph_style)
                    row_segment_paras[details_column_index] = Paragraph(text, style)
                    for c_idx, para in other_cols_paras_for_row.items():
                        if first_chunk_for_this_item_entry:
                            row_segment_paras[c_idx] = para
                    data_for_rl_table.append(row_segment_paras)
                    first_chunk_for_this_item_entry = False
            else: 
                full_row_paras = [None] * num_cols
                for c_idx in range(num_cols):
                    text, style = self._determine_reportlab_style(
                        str(current_processed_cells[c_idx]), False, (c_idx==item_column_index), (c_idx==details_column_index), base_paragraph_style)
                    full_row_paras[c_idx] = Paragraph(text, style)
                data_for_rl_table.append(full_row_paras)
        if not data_for_rl_table:
            doc.build(elements, onFirstPage=self._add_header, onLaterPages=self._add_header)
            return
        table_obj = Table(data_for_rl_table, colWidths=col_widths_rl, repeatRows=(1 if is_first_row_semantically_header else 0))
        table_style_cmds = [
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 2*mm),
            ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
            ('TOPPADDING', (0,0), (-1,-1), 1*mm),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1*mm),
        ]
        if is_first_row_semantically_header:
            table_style_cmds.append(('BACKGROUND', (0,0), (-1,0), colors.lightgrey))

        table_obj.setStyle(TableStyle(table_style_cmds))
        elements.append(table_obj)
        doc.build(elements, onFirstPage=self._add_header, onLaterPages=self._add_header)