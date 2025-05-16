import re
import os
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_FAMILY = 'Times'
FONT_FAMILY_BOLD = 'Helvetica-Bold'


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
            print(f"Erro ao gerar PDF com ReportLab: {e}")
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
            celulas_processadas = [
                re.sub(r'\s+', ' ', celula.replace("<br>", " ").replace("\\n", " ")).strip()
                for celula in celulas_raw
            ]
            tabela.append(celulas_processadas)
        return tabela

    def _determine_reportlab_style(self, text_content, is_header, is_item_col, is_details_header_col, base_style):
        text_to_draw = str(text_content)
        current_style = ParagraphStyle(name=f'Style_{uuid.uuid4().hex}', parent=base_style)
        current_style.fontName = FONT_FAMILY 
        current_style.alignment = base_style.alignment 

        is_markdown = False
        if text_to_draw.startswith("**") and text_to_draw.endswith("**") and len(text_to_draw) > 4:
            text_to_draw = text_to_draw[2:-2].strip()
            is_markdown = True

        content_lower = text_to_draw.lower()

        if is_header:
            if is_item_col and content_lower == "item":
                current_style.fontName = FONT_FAMILY_BOLD
                current_style.alignment = TA_CENTER
            elif is_details_header_col and content_lower == "detalhes":
                current_style.fontName = FONT_FAMILY_BOLD
                current_style.alignment = TA_CENTER
        elif is_item_col:
            current_style.fontName = FONT_FAMILY_BOLD
            current_style.alignment = TA_CENTER
        
        if is_markdown:
            current_style.fontName = FONT_FAMILY_BOLD
            if current_style.alignment == TA_LEFT:
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
        base_paragraph_style.fontSize = 12
        base_paragraph_style.leading = 12 * 1.5

        if not tabela_processada: doc.build(elements); return
        
        num_cols = 0
        if any(isinstance(row, list) for row in tabela_processada):
            valid_rows = [r for r in tabela_processada if isinstance(r, list) and r]
            if valid_rows: num_cols = max(len(r) for r in valid_rows)
            elif tabela_processada and isinstance(tabela_processada[0], list): num_cols = len(tabela_processada[0])
        if num_cols == 0: doc.build(elements); return

        item_column_index = -1; details_column_index = -1
        if tabela_processada and tabela_processada[0]:
            header_cleaned = [str(h).strip().lower() for h in tabela_processada[0]]
            if "item" in header_cleaned: item_column_index = header_cleaned.index("item")
            if "detalhes" in header_cleaned: details_column_index = header_cleaned.index("detalhes")
        
        if num_cols == 2 and item_column_index == -1 and details_column_index == -1:
            item_column_index = 0; details_column_index = 1
        
        available_width_for_table = doc.width
        if num_cols == 1: col_widths_rl = [available_width_for_table]
        elif num_cols == 2: col_widths_rl = [available_width_for_table * 0.25, available_width_for_table * 0.75]
        elif num_cols == 3 and item_column_index != -1 and details_column_index != -1:
            col_widths_rl = [available_width_for_table * 0.20, available_width_for_table * 0.60, available_width_for_table * 0.20]
        else: col_widths_rl = [available_width_for_table / num_cols] * num_cols
        
        data_for_rl_table = []
        
        for row_idx, original_row in enumerate(tabela_processada):
            is_header_row = (row_idx == 0)
            
            current_row_cells = list(original_row)
            while len(current_row_cells) < num_cols: current_row_cells.append("")
            current_row_cells = current_row_cells[:num_cols]

            styled_row_cells = [None] * num_cols

            if item_column_index != -1 and item_column_index < len(current_row_cells):
                current_item_text = str(current_row_cells[item_column_index])
                item_text_to_draw, item_style = self._determine_reportlab_style(
                    current_item_text, is_header_row, True, False, base_paragraph_style
                )

                styled_row_cells[item_column_index] = Paragraph(item_text_to_draw, item_style)


            if details_column_index != -1 and details_column_index < len(current_row_cells):
                current_details_text = str(current_row_cells[details_column_index])
                
                if is_header_row:
                    text_to_draw, details_style = self._determine_reportlab_style(
                        current_details_text, True, False, True, base_paragraph_style
                    )
                    styled_row_cells[details_column_index] = Paragraph(text_to_draw, details_style)
                else:
                    _, details_style = self._determine_reportlab_style(
                        current_details_text, False, False, False, base_paragraph_style
                    )
 
                    details_paragraph = Paragraph(current_details_text, details_style)
                    styled_row_cells[details_column_index] = details_paragraph
            
            for c_idx in range(num_cols):
                if styled_row_cells[c_idx] is not None: 
                    continue

                cell_content = str(current_row_cells[c_idx])
                is_current_cell_item_col = (c_idx == item_column_index) 
                is_current_cell_details_header = (is_header_row and c_idx == details_column_index)

                text_to_draw, cell_style_obj = self._determine_reportlab_style(
                    cell_content, is_header_row, 
                    is_current_cell_item_col, 
                    is_current_cell_details_header,
                    base_paragraph_style
                )
                styled_row_cells[c_idx] = Paragraph(text_to_draw, cell_style_obj)
            
            for c_idx in range(num_cols):
                if styled_row_cells[c_idx] is None:
                    _, style_empty = self._determine_reportlab_style("", False, False, False, base_paragraph_style)
                    styled_row_cells[c_idx] = Paragraph("", style_empty)
            
            data_for_rl_table.append(styled_row_cells)

        if not data_for_rl_table: doc.build(elements); return

        table_obj = Table(data_for_rl_table, colWidths=col_widths_rl, 
                          repeatRows=(1 if tabela_processada and tabela_processada[0] and row_idx == 0 else 0), 
                         ) 
        
        table_style_cmds = [
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2*mm),
            ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
            ('TOPPADDING', (0,0), (-1,-1), 1*mm),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1*mm),
        ]

 
        table_obj.setStyle(TableStyle(table_style_cmds))
        elements.append(table_obj)
        doc.build(elements)
