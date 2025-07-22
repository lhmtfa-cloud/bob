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

FONT_FAMILY = 'Times'
FONT_FAMILY_BOLD = 'Times-Bold' 


class PDFGenerator:
    def __init__(self, output_dir="output_pdfs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    async def create_summary_pdf(self, structured_summary: str) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        tabela_raw = self._extrair_tabela(structured_summary)
        tabela_processada = self._processar_tabela(tabela_raw)
        
        nome_arquivo = f"{uuid.uuid4().hex}.pdf"
        caminho_pdf = os.path.join(self.output_dir, nome_arquivo)
        
        try:
            self._gerar_pdf_reportlab(tabela_processada, caminho_pdf)
            return caminho_pdf
        except Exception as e:
            print(f"Erro completo ao gerar PDF com ReportLab: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _extrair_tabela(self, texto: str) -> list[str]:
        linhas_tabela = []
        capturando = False
        for linha in texto.splitlines():
            linha = linha.strip()
            if linha.startswith("|") and not linha.startswith("|--"):
                capturando = True
                linhas_tabela.append(linha)
            elif capturando and linha.startswith("|--"):
                continue
            elif capturando and not linha.startswith("|"):
                break
        return linhas_tabela

    def _processar_tabela(self, linhas_tabela: list[str]) -> list[list[str]]:
        tabela = []
        for linha_raw in linhas_tabela:
            celulas_raw = [celula.strip() for celula in linha_raw.strip().strip('|').split('|')]
            # Substituir <br> e \n por quebras de linha que o Paragraph entende
            celulas_processadas = [
                re.sub(r'\s+', ' ', celula.replace("<br>", "\n").replace("\\n", "\n")).strip()
                for celula in celulas_raw
            ]
            tabela.append(celulas_processadas)
        return tabela

    def _determine_reportlab_style(self, text_content, is_header_row, is_item_column, is_details_column, base_style):
        text_to_draw = str(text_content)
        current_style = ParagraphStyle(name=f'Style_{uuid.uuid4().hex}', parent=base_style)
        # Herda fontName, fontSize, leading, alignment de base_style

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
            current_style.alignment = TA_JUSTIFY # Ou TA_LEFT se preferir justificado
            # Mantém a fonte base (não negrito por padrão para detalhes)
        
        if is_markdown_bold: # Markdown tem prioridade para negrito
            current_style.fontName = FONT_FAMILY_BOLD
            # Centralizar markdown apenas se não for coluna de detalhes e se já não estiver centralizado por outra regra
            if not is_details_column and current_style.alignment == TA_LEFT:
                 current_style.alignment = TA_CENTER
        
        return text_to_draw, current_style

    def _gerar_pdf_reportlab(self, tabela_processada: list[list[str]], caminho_pdf: str):
        doc = SimpleDocTemplate(caminho_pdf, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        elements = []
        
        styles = getSampleStyleSheet()
        base_paragraph_style = styles['Normal']
        base_paragraph_style.fontName = FONT_FAMILY 
        base_paragraph_style.fontSize = 12 # Restaurado para 12pt
        base_paragraph_style.leading = base_paragraph_style.fontSize * 1.5 # Restaurado (18pt)
        base_paragraph_style.alignment = TA_LEFT

        empty_cell_style = ParagraphStyle(name='EmptyCellStyleForSpan', parent=base_paragraph_style)
        
        if not tabela_processada:
            doc.build(elements); return
        
        num_cols = max(len(r) for r in tabela_processada) if tabela_processada else 0
        if num_cols == 0:
            doc.build(elements); return

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
            item_col_width_percent = 0.25 # Ajuste conforme necessário
            details_col_width_percent = 1.0 - item_col_width_percent
            if item_column_index == 0 and details_column_index == 1: # Item | Detalhes
                 col_widths_rl = [available_width_for_table * item_col_width_percent, available_width_for_table * details_col_width_percent]
            elif item_column_index == 1 and details_column_index == 0: # Detalhes | Item
                 col_widths_rl = [available_width_for_table * details_col_width_percent, available_width_for_table * item_col_width_percent]
            else: # Fallback, caso os índices não sejam (0,1) ou (1,0)
                 col_widths_rl = [available_width_for_table * item_col_width_percent, available_width_for_table * details_col_width_percent]
        elif num_cols > 2 and details_column_index != -1:
            details_width_percentage = 0.50 # Ex: 50% para detalhes se houver muitas colunas
            remaining_percentage = 1.0 - details_width_percentage
            other_col_percentage = remaining_percentage / (num_cols - 1) if num_cols > 1 else 0
            col_widths_rl = [available_width_for_table * other_col_percentage] * num_cols
            col_widths_rl[details_column_index] = available_width_for_table * details_width_percentage
        else: 
            col_widths_rl = [available_width_for_table / num_cols] * num_cols
        
        data_for_rl_table = []
        WORDS_PER_CHUNK_DETAILS = 30 # Reduzido para testar se força o chunking nos seus dados

        for row_idx, original_row_content in enumerate(tabela_processada):
            current_processed_cells = list(original_row_content)
            while len(current_processed_cells) < num_cols: current_processed_cells.append("")
            current_processed_cells = current_processed_cells[:num_cols]

            is_header_row_flag = (row_idx == 0 and is_first_row_semantically_header)

            if is_header_row_flag:
                header_row_paras = []
                for c_idx in range(num_cols):
                    text, style = self._determine_reportlab_style(
                        str(current_processed_cells[c_idx]), 
                        True, # is_header_row
                        (c_idx==item_column_index), 
                        (c_idx==details_column_index), 
                        base_paragraph_style)
                    header_row_paras.append(Paragraph(text, style))
                data_for_rl_table.append(header_row_paras)
                continue

            item_text_for_row = str(current_processed_cells[item_column_index]) if item_column_index != -1 and item_column_index < num_cols else ""
            details_text_for_row = str(current_processed_cells[details_column_index]) if details_column_index != -1 and details_column_index < num_cols else ""
            
            other_cols_paras_for_row = {} # Usar dict para fácil acesso por c_idx
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
                        str(current_processed_cells[c_idx]), 
                        False, 
                        (c_idx==item_column_index), 
                        (c_idx==details_column_index), 
                        base_paragraph_style)
                    full_row_paras[c_idx] = Paragraph(text, style)
                data_for_rl_table.append(full_row_paras)

        if not data_for_rl_table:
            doc.build(elements); return

        table_obj = Table(data_for_rl_table, colWidths=col_widths_rl, repeatRows=(1 if is_first_row_semantically_header else 0))
        
        table_style_cmds = [
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 2*mm),
            ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
            ('TOPPADDING', (0,0), (-1,-1), 1*mm),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1*mm),
        ]
        table_obj.setStyle(TableStyle(table_style_cmds))
        elements.append(table_obj)
        doc.build(elements)