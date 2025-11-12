prompt_resumo_narrativo = """
Com base no documento já analisado e utilizando APENAS a seguinte cronologia de eventos que foi extraída dele, sua tarefa é escrever um resumo narrativo coeso em um único parágrafo.
Conecte os pontos da cronologia para contar a história do documento de forma fluida e objetiva.
Não adicione informações que não estejam listadas abaixo e não repita as marcações de página (Ex: (Página X)).

CRONOLOGIA DE EVENTOS:
{cronologia}
"""