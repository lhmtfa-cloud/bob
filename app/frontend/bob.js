
let trackingCode = "";
let statusInterval;
const statusMap = {
  received: { value: 10, text: "Arquivo recebido" },
  uploading: { value: 20, text: "Enviando arquivo para processamento..." },
  question_answering: { value: 30, text: "Respondendo perguntas..." },
  summarizing: { value: 60, text: "Gerando resumo..." },
  generating_pdf: { value: 80, text: "Gerando PDF..." },
  zipping: { value: 90, text: "Compactando arquivos..." },
  finished: { value: 100, text: "Processamento finalizado!" },
  error: { value: 0, text: "Erro no processamento." }
};

// Adiciona um listener para atualizar o texto do label quando um arquivo é selecionado
const pdfInput = document.getElementById('pdfInput');
const fileUploadLabel = document.querySelector('.custom-file-upload');
const defaultLabelText = fileUploadLabel.innerHTML; // Guarda o texto original do label

pdfInput.addEventListener('change', function(e){
  if(e.target.files && e.target.files.length > 0) {
    // Mostra o nome do arquivo no label
    // Pode precisar de um ícone diferente ou estilo para o nome do arquivo
    fileUploadLabel.innerHTML = `<i class="fas fa-file-pdf"></i> ${e.target.files[0].name}`;
  } else {
    // Volta ao texto original se nenhum arquivo for selecionado
    fileUploadLabel.innerHTML = defaultLabelText;
  }
});


async function uploadPDF() {
  // Limpa qualquer intervalo de verificação anterior
  clearInterval(statusInterval);

  const pdfInput = document.getElementById("pdfInput");
  if (!pdfInput.files.length) {
    showModal("Selecione um arquivo PDF");
    return;
  }

  const formData = new FormData();
  formData.append("file", pdfInput.files[0]);

  // Reseta a interface para o novo envio
  document.getElementById("progressSection").classList.remove("hidden");
  document.getElementById("downloadContainer").classList.add("hidden"); // Esconde o link de download antigo
  document.getElementById("statusText").textContent = "Enviando...";
  document.getElementById("progressBar").value = 5;


  try {
    const response = await fetch("/process-pdf", {
      method: "POST",
      body: formData
    });
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    trackingCode = data.tracking_code;

    // Inicia o loop de verificação para o *novo* código de rastreamento
    checkStatusLoop(trackingCode, data.download_url);
  } catch (error) {
    console.error('Erro ao enviar o PDF:', error);
    document.getElementById("statusText").textContent = "Erro ao enviar o arquivo.";
    showModal(`Erro ao enviar o arquivo: ${error.message}`);
    // Limpa o intervalo em caso de erro no envio
    clearInterval(statusInterval);
    // Reseta o label do input
    fileUploadLabel.innerHTML = defaultLabelText;
  }
}
function checkStatusLoop(code, downloadUrl) {
  statusInterval = setInterval(async () => {
    try {
      const res = await fetch(`/processing-status/${code}`);
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();

      const status = data.status;
      const statusInfo = statusMap[status] || { value: 0, text: "Status desconhecido" };
      document.getElementById("statusText").textContent = statusInfo.text;
      document.getElementById("progressBar").value = statusInfo.value;

      if (status === "finished") {
        clearInterval(statusInterval);
        document.getElementById("downloadLink").href = downloadUrl;
        document.getElementById("downloadContainer").classList.remove("hidden");
        // Resetar o label do input de arquivo após o sucesso
        fileUploadLabel.innerHTML = defaultLabelText;
      }

      if (status === "error") {
        clearInterval(statusInterval);
        showModal("Ocorreu um erro durante o processamento do arquivo.");
          // Resetar o label do input de arquivo após erro
        fileUploadLabel.innerHTML = defaultLabelText;
      }
    } catch(error) {
      console.error('Erro ao consultar status:', error);
      document.getElementById("statusText").textContent = "Erro ao consultar status.";
      showModal(`Erro ao consultar status: ${error.message}`);
      clearInterval(statusInterval);
        // Resetar o label do input de arquivo após erro na consulta
      fileUploadLabel.innerHTML = defaultLabelText;
    }
  }, 2000);
}

function showModal(message) {
    const existingModal = document.getElementById('customModal');
    if (existingModal) {
        existingModal.remove();
    }

    const modal = document.createElement('div');
    modal.id = 'customModal';
    modal.style.position = 'fixed';
    modal.style.left = '50%';
    modal.style.top = '50%';
    modal.style.transform = 'translate(-50%, -50%)';
    modal.style.padding = '25px'; // Aumentar padding
    modal.style.backgroundColor = '#fff'; // Fundo branco
    modal.style.border = 'none'; // Remover borda
    modal.style.borderRadius = '10px'; // Cantos mais arredondados
    modal.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15), 0 6px 10px rgba(0,0,0,0.1)'; // Sombra mais pronunciada
    modal.style.zIndex = '1000';
    modal.style.textAlign = 'center';
    modal.style.minWidth = '300px'; // Largura mínima
    modal.style.maxWidth = '90%'; // Largura máxima responsiva

    const messageP = document.createElement('p');
    messageP.textContent = message;
    messageP.style.marginBottom = '20px'; // Aumentar margem
    messageP.style.fontSize = '1.1em'; // Aumentar tamanho da fonte
    messageP.style.color = '#333'; // Cor do texto

    const closeButton = document.createElement('button');
    closeButton.textContent = 'OK';
    // Reutilizar o estilo do botão principal, mas talvez com cores diferentes ou mais simples
    closeButton.style.padding = '10px 25px';
    closeButton.style.backgroundImage = 'linear-gradient(to right, #667eea 0%, #764ba2 51%, #667eea 100%)';
    closeButton.style.backgroundSize = '200% auto';
    closeButton.style.color = 'white';
    closeButton.style.border = 'none';
    closeButton.style.borderRadius = '8px';
    closeButton.style.cursor = 'pointer';
    closeButton.style.fontSize = '1em';
    closeButton.style.fontWeight = '500';
    closeButton.style.transition = 'all 0.3s ease';
    closeButton.style.boxShadow = '0 2px 8px rgba(116, 79, 168, 0.5)';

    closeButton.onmouseover = () => {
        closeButton.style.backgroundPosition = 'right center';
        closeButton.style.boxShadow = '0 4px 12px rgba(116, 79, 168, 0.65)';
    };
    closeButton.onmouseout = () => {
        closeButton.style.backgroundPosition = 'left center';
        closeButton.style.boxShadow = '0 2px 8px rgba(116, 79, 168, 0.5)';
    };
    closeButton.onclick = () => modal.remove();

    modal.appendChild(messageP);
    modal.appendChild(closeButton);
    document.body.appendChild(modal);
}

