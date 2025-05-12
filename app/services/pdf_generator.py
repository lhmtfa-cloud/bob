from fpdf import FPDF
import math
import re
import os
import uuid

class PDFGenerator:
    def __init__(self, output_dir="output_pdfs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def create_summary_pdf(self, structured_summary: str) -> str:
        # Extrai a tabela do texto usando regex
        tabela_raw = self._extrair_tabela(structured_summary)

        # Processa a tabela
        tabela = self._processar_tabela(tabela_raw)

        # Gera o PDF
        nome_arquivo = f"{uuid.uuid4().hex}.pdf"
        caminho_pdf = os.path.join(self.output_dir, nome_arquivo)
        self._gerar_pdf(tabela, caminho_pdf)

        return caminho_pdf

    def _extrair_tabela(self, texto: str) -> list[list[str]]:
        tabelas = []
        tabela_atual = []
        capturando = False

        for linha in texto.splitlines():
            linha = linha.strip()

            if linha.startswith("|") and not linha.startswith("|--"):
                capturando = True
                tabela_atual.append(linha)
            elif capturando and linha.startswith("|--"):
                continue
            elif capturando and not linha.startswith("|"):
                if tabela_atual:
                    tabelas.append(tabela_atual)
                    tabela_atual = []
                capturando = False

        if tabela_atual:
            tabelas.append(tabela_atual)

        # Junta todas as tabelas em uma só (opcional, dependendo do seu objetivo)
        return [linha for tabela in tabelas for linha in tabela]

    def _processar_tabela(self, linhas_tabela: list[str]) -> list[list[str]]:
        tabela = []
        for linha in linhas_tabela:
            partes = [parte.strip() for parte in linha.strip('|').split('|')]
            tabela.append(partes)
        return tabela

    def _gerar_pdf(self, tabela: list[list[str]], caminho_pdf: str):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", size=10)

        line_height = 8
        if tabela:
            num_cols = max(len(linha) for linha in tabela)
            col_width = 190 / num_cols
            col_widths = [col_width] * num_cols

        for idx_linha, linha in enumerate(tabela):
            while len(linha) < len(col_widths):
                linha.append("")

            n_linhas_por_celula = []
            for i, texto in enumerate(linha):
                largura = col_widths[i]
                texto_limpo = texto[2:-2] if texto.startswith("**") and texto.endswith("**") else texto
                n_linhas = max(1, math.ceil(pdf.get_string_width(texto_limpo) / largura))
                n_linhas_por_celula.append(n_linhas)

            max_linhas = max(n_linhas_por_celula)
            altura_total = max_linhas * line_height

            x_inicial = pdf.get_x()
            y_inicial = pdf.get_y()

            for i, texto in enumerate(linha):
                largura = col_widths[i]
                x = x_inicial + sum(col_widths[:i])
                y = y_inicial

                pdf.set_xy(x, y)
                conteudo = texto[2:-2].strip() if texto.startswith("**") and texto.endswith("**") else texto.strip()

                # Calcula altura do texto atual
                texto_largura = pdf.get_string_width(conteudo)
                linhas_texto = max(1, math.ceil(texto_largura / largura))
                altura_texto = linhas_texto * line_height
                y_offset = (altura_total - altura_texto) / 2

                # Decide se centraliza vertical e horizontal
                align = 'C' if idx_linha == 0 or i == 0 else 'L'
                estilo = "B" if idx_linha == 0 else ""
                pdf.set_font("Helvetica", style=estilo, size=10)

                pdf.set_xy(x, y + y_offset)
                pdf.multi_cell(w=largura, h=line_height, border=0, align=align, txt=conteudo)

                pdf.set_font("Helvetica", style="", size=10)
                pdf.rect(x, y_inicial, largura, altura_total)

            pdf.set_xy(x_inicial, y_inicial + altura_total)

        pdf.output(caminho_pdf)



