const botao = document.getElementById("carregar");
const mensagem = document.getElementById("mensagem");
const resultado = document.getElementById("resultado");
const corpoTabela = document.getElementById("pedidos");

async function carregarFila() {
  botao.disabled = true;
  resultado.hidden = true;
  mensagem.textContent = "Consultando pedidos e calculando prioridades...";

  try {
    const resposta = await fetch("/api/prioridades", {
      signal: AbortSignal.timeout(60000)
    });

    if (!resposta.ok) {
      throw new Error(`Erro na consulta: ${resposta.status}`);
    }

    const dados = await resposta.json();

    document.getElementById("total").textContent =
      dados.pedidos_avaliados.toLocaleString("pt-BR");

    document.getElementById("prioritarios").textContent =
      dados.pedidos_na_fila.toLocaleString("pt-BR");

    document.getElementById("observacao").textContent =
      dados.observacao;

    const linhas = document.createDocumentFragment();

    for (const pedido of dados.fila) {
      const linha = document.createElement("tr");
      const identificador = document.createElement("td");
      const score = document.createElement("td");

      identificador.textContent = pedido.order_id;
      score.textContent = pedido.score_atraso.toFixed(3);

      linha.append(identificador, score);
      linhas.append(linha);
    }

    corpoTabela.replaceChildren(linhas);

    resultado.hidden = false;
    mensagem.textContent = "Análise concluída. Fila disponível abaixo.";
  } catch (erro) {
    console.error(erro);
    mensagem.textContent =
      "Não foi possível carregar a fila. Tente novamente.";
  } finally {
    botao.disabled = false;
  }
}

botao.addEventListener("click", carregarFila);