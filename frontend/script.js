"use strict";

// O backend calcula a fila. O navegador apresenta e organiza a resposta.
const elementos = {
  resultado: document.getElementById("resultado"),
  mensagem: document.getElementById("mensagem"),
  conexao: document.getElementById("connection-status"),
  atualizado: document.getElementById("updated-at"),
  total: document.getElementById("total"),
  prioritarios: document.getElementById("prioritarios"),
  capacidade: document.getElementById("capacidade"),
  maiorScore: document.getElementById("maior-score"),
  contexto: document.getElementById("contexto"),
  observacao: document.getElementById("observacao"),
  filaStatus: document.getElementById("fila-status"),
  vazio: document.getElementById("empty-state"),
  tituloVazio: document.getElementById("empty-title"),
  descricaoVazio: document.getElementById("empty-description"),
  areaTabela: document.getElementById("table-area"),
  tabela: document.getElementById("pedidos"),
  contagem: document.getElementById("resultado-contagem"),
  busca: document.getElementById("busca-pedido"),
  ordem: document.getElementById("ordem"),
  tamanhoPagina: document.getElementById("tamanho-pagina"),
  limpar: document.getElementById("limpar-filtros"),
  exportar: document.getElementById("exportar-csv"),
  anterior: document.getElementById("pagina-anterior"),
  proxima: document.getElementById("pagina-proxima"),
  paginaInfo: document.getElementById("pagina-info"),
  distribuicao: document.getElementById("score-distribution"),
  legendaDistribuicao: document.getElementById("distribution-caption"),
  dialogo: document.getElementById("pedido-dialog"),
  feedbackDetalhe: document.getElementById("detalhe-feedback"),
};

const botoesCarregar = [...document.querySelectorAll("[data-load]")];
const formatoInteiro = new Intl.NumberFormat("pt-BR");
const formatoScore = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});
const formatoPercentual = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 1,
});
const formatoHorario = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "medium",
});

const estado = {
  dados: null,
  filtrados: [],
  pagina: 1,
  carregando: false,
  atualizadoEm: null,
  pedidoAberto: null,
  gatilhoDetalhe: null,
};

function compararId(a, b) {
  return a.order_id < b.order_id ? -1 : a.order_id > b.order_id ? 1 : 0;
}

// Recusa respostas incompletas antes de substituir o último resultado válido.
function validarResposta(dados) {
  const erro = () => new Error("A API retornou dados incompletos ou inconsistentes.");
  if (!dados || !Array.isArray(dados.fila)) throw erro();
  if (!Number.isSafeInteger(dados.pedidos_avaliados) || dados.pedidos_avaliados < 0) throw erro();
  if (!Number.isSafeInteger(dados.pedidos_na_fila) || dados.pedidos_na_fila < 0) throw erro();
  if (!Number.isFinite(dados.fracao_fila) || dados.fracao_fila < 0 || dados.fracao_fila > 1) throw erro();
  if (dados.pedidos_na_fila !== dados.fila.length || dados.pedidos_na_fila > dados.pedidos_avaliados) throw erro();
  if (Math.floor(dados.pedidos_avaliados * dados.fracao_fila) !== dados.pedidos_na_fila) throw erro();
  if (typeof dados.contexto !== "string" || !dados.contexto.trim()) throw erro();
  if (typeof dados.observacao !== "string" || !dados.observacao.trim()) throw erro();

  const identificadores = new Set();
  const fila = dados.fila.map((pedido) => {
    if (!pedido || typeof pedido.order_id !== "string" || !pedido.order_id.trim()) throw erro();
    if (identificadores.has(pedido.order_id)) throw erro();
    if (!Number.isFinite(pedido.score_atraso) || pedido.score_atraso < 0 || pedido.score_atraso > 1) throw erro();
    if (pedido.prioridade !== 1) throw erro();
    identificadores.add(pedido.order_id);
    return { order_id: pedido.order_id, score_atraso: pedido.score_atraso, prioridade: 1 };
  });

  fila.sort((a, b) => b.score_atraso - a.score_atraso || compararId(a, b));
  fila.forEach((pedido, indice) => { pedido.posicao = indice + 1; });
  return { ...dados, fila };
}

function mostrarEstadoVazio(titulo, descricao) {
  elementos.vazio.hidden = false;
  elementos.areaTabela.hidden = true;
  elementos.tituloVazio.textContent = titulo;
  elementos.descricaoVazio.textContent = descricao;
}

function atualizarControles() {
  for (const botao of botoesCarregar) {
    botao.disabled = estado.carregando;
    botao.setAttribute("aria-busy", String(estado.carregando));
    const texto = botao.querySelector("[data-load-label]");
    if (texto) texto.textContent = estado.carregando ? "Calculando fila…" : estado.dados ? "Atualizar análise" : "Gerar fila de prioridade";
  }
  for (const controle of [elementos.busca, elementos.ordem, elementos.tamanhoPagina, elementos.limpar]) {
    controle.disabled = !estado.dados;
  }
  elementos.exportar.disabled = estado.carregando || !estado.filtrados.length;
}

async function carregarFila() {
  if (estado.carregando) return;
  estado.carregando = true;
  elementos.resultado.dataset.state = "loading";
  elementos.resultado.setAttribute("aria-busy", "true");
  elementos.conexao.textContent = "Processando";
  elementos.conexao.dataset.state = "loading";
  elementos.mensagem.textContent = estado.dados
    ? "Atualizando a análise. O último resultado válido continua disponível abaixo."
    : "Consultando o PostgreSQL e executando o modelo. Isso pode levar alguns segundos.";
  if (!estado.dados) mostrarEstadoVazio("Preparando sua fila", "Consultando pedidos e calculando os scores com o modelo salvo.");
  atualizarControles();

  const controlador = new AbortController();
  const timeout = window.setTimeout(() => controlador.abort(), 60000);
  try {
    const resposta = await fetch("/api/prioridades", {
      signal: controlador.signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!resposta.ok) throw new Error(`A API não concluiu a consulta (HTTP ${resposta.status}).`);
    const dados = validarResposta(await resposta.json());
    estado.dados = dados;
    estado.atualizadoEm = new Date();
    estado.pagina = 1;
    atualizarIndicadores();
    renderizarDistribuicao();
    aplicarFiltros();
    elementos.resultado.dataset.state = "success";
    elementos.conexao.textContent = "Consulta concluída";
    elementos.conexao.dataset.state = "success";
    elementos.mensagem.textContent = "Análise concluída. Explore a fila ou abra um pedido para consultar seu score.";
  } catch (erro) {
    console.error("Não foi possível atualizar a fila:", erro);
    const explicacao = erro.name === "AbortError"
      ? "A consulta ultrapassou 60 segundos."
      : erro instanceof TypeError
        ? "Não foi possível conectar à API."
        : erro instanceof SyntaxError
          ? "A API retornou uma resposta inválida."
          : erro.message;
    elementos.resultado.dataset.state = "error";
    elementos.conexao.textContent = "Falha na atualização";
    elementos.conexao.dataset.state = "error";
    const anterior = estado.dados
      ? ` O resultado de ${formatoHorario.format(estado.atualizadoEm)} foi mantido.`
      : " Nenhum resultado foi carregado.";
    elementos.mensagem.textContent = `${explicacao}${anterior} Clique em gerar ou atualizar para tentar novamente.`;
    if (!estado.dados) mostrarEstadoVazio("A consulta não foi concluída", "Verifique se a API e o PostgreSQL estão disponíveis e tente novamente.");
  } finally {
    window.clearTimeout(timeout);
    estado.carregando = false;
    elementos.resultado.setAttribute("aria-busy", "false");
    atualizarControles();
    atualizarContextoAssistente();
  }
}

function atualizarIndicadores() {
  const dados = estado.dados;
  elementos.total.textContent = formatoInteiro.format(dados.pedidos_avaliados);
  elementos.prioritarios.textContent = formatoInteiro.format(dados.pedidos_na_fila);
  elementos.capacidade.textContent = formatoPercentual.format(dados.fracao_fila);
  elementos.maiorScore.textContent = dados.fila.length ? formatoScore.format(dados.fila[0].score_atraso) : "—";
  elementos.contexto.textContent = dados.contexto;
  elementos.observacao.textContent = dados.observacao;
  elementos.atualizado.textContent = `Última consulta: ${formatoHorario.format(estado.atualizadoEm)}`;
  elementos.atualizado.setAttribute("datetime", estado.atualizadoEm.toISOString());
  elementos.filaStatus.textContent = `${formatoInteiro.format(dados.fila.length)} pedidos priorizados`;
}

function aplicarFiltros() {
  if (!estado.dados) return;
  const termo = elementos.busca.value.trim().toLowerCase();
  estado.filtrados = estado.dados.fila.filter((pedido) => pedido.order_id.toLowerCase().includes(termo));
  const comparadores = {
    "score-desc": (a, b) => b.score_atraso - a.score_atraso || compararId(a, b),
    "score-asc": (a, b) => a.score_atraso - b.score_atraso || compararId(a, b),
    "id-asc": compararId,
  };
  estado.filtrados.sort(comparadores[elementos.ordem.value] || comparadores["score-desc"]);
  estado.pagina = 1;
  renderizarTabela();
  atualizarControles();
}

function criarCelula(texto, classe) {
  const celula = document.createElement("td");
  if (texto !== undefined) celula.textContent = texto;
  if (classe) celula.className = classe;
  return celula;
}

function renderizarTabela() {
  const tamanho = Number(elementos.tamanhoPagina.value) || 25;
  const quantidade = estado.filtrados.length;
  const paginas = Math.max(1, Math.ceil(quantidade / tamanho));
  estado.pagina = Math.min(estado.pagina, paginas);
  const inicio = (estado.pagina - 1) * tamanho;
  const fim = Math.min(inicio + tamanho, quantidade);
  const fragmento = document.createDocumentFragment();

  for (const pedido of estado.filtrados.slice(inicio, fim)) {
    const linha = document.createElement("tr");
    const id = document.createElement("button");
    id.type = "button";
    id.className = "order-id";
    id.textContent = pedido.order_id;
    id.setAttribute("aria-label", `Abrir pedido ${pedido.order_id}`);
    id.addEventListener("click", () => abrirDetalhe(pedido, id));
    const celulaId = criarCelula();
    celulaId.append(id);

    const celulaScore = criarCelula(undefined, "score-cell");
    const display = document.createElement("div");
    display.className = "score-display";
    const valor = document.createElement("span");
    valor.className = "score-value";
    valor.textContent = formatoScore.format(pedido.score_atraso);
    const trilha = document.createElement("span");
    trilha.className = "score-track";
    trilha.setAttribute("aria-hidden", "true");
    const preenchimento = document.createElement("span");
    preenchimento.style.setProperty("--score-width", `${pedido.score_atraso * 100}%`);
    trilha.append(preenchimento);
    display.append(valor, trilha);
    celulaScore.append(display);

    const detalhe = document.createElement("button");
    detalhe.type = "button";
    detalhe.className = "row-detail";
    detalhe.textContent = "Ver pedido ↗";
    detalhe.setAttribute("aria-label", `Ver detalhes do pedido ${pedido.order_id}`);
    detalhe.addEventListener("click", () => abrirDetalhe(pedido, detalhe));
    const acao = criarCelula(undefined, "row-action");
    acao.append(detalhe);
    linha.append(criarCelula(String(pedido.posicao).padStart(2, "0"), "row-rank"), celulaId, celulaScore, acao);
    fragmento.append(linha);
  }
  elementos.tabela.replaceChildren(fragmento);
  // Cada página começa na primeira linha; mantém a rolagem horizontal.
  const rolagemTabela = elementos.areaTabela.querySelector(".table-scroll");
  if (rolagemTabela) rolagemTabela.scrollTop = 0;
  elementos.areaTabela.hidden = quantidade === 0;
  elementos.vazio.hidden = quantidade > 0;
  if (!quantidade) mostrarEstadoVazio(
    estado.dados.fila.length ? "Nenhum pedido encontrado" : "A fila está vazia",
    estado.dados.fila.length ? "Tente outro trecho do identificador ou limpe os filtros. A busca considera somente a fila priorizada." : "A consulta foi concluída e não retornou pedidos para priorização."
  );
  elementos.contagem.textContent = quantidade
    ? `Exibindo ${formatoInteiro.format(inicio + 1)}–${formatoInteiro.format(fim)} de ${formatoInteiro.format(quantidade)} pedidos${elementos.busca.value.trim() ? " encontrados na fila" : " na fila"}.`
    : "Nenhum pedido para exibir.";
  elementos.paginaInfo.textContent = `Página ${quantidade ? estado.pagina : 0} de ${quantidade ? paginas : 0}`;
  elementos.anterior.disabled = !quantidade || estado.pagina <= 1;
  elementos.proxima.disabled = !quantidade || estado.pagina >= paginas;
}

// Distribuição dos scores recebidos: não é uma métrica de desempenho do modelo.
function renderizarDistribuicao() {
  const faixas = [0, 0, 0, 0, 0];
  for (const pedido of estado.dados.fila) faixas[Math.min(4, Math.floor(pedido.score_atraso * 5))]++;
  const maximo = Math.max(1, ...faixas);
  const fragmento = document.createDocumentFragment();
  faixas.forEach((quantidade, indice) => {
    const linha = document.createElement("div");
    linha.className = "distribution-row";
    const legenda = document.createElement("span");
    legenda.className = "distribution-label";
    const inicio = (indice / 5).toFixed(1).replace(".", ",");
    const fim = ((indice + 1) / 5).toFixed(1).replace(".", ",");
    legenda.textContent = `${inicio}–${fim}`;
    linha.setAttribute("aria-label", `Score maior ou igual a ${inicio} e ${indice === 4 ? "menor ou igual a" : "menor que"} ${fim}: ${quantidade} pedidos`);
    const trilha = document.createElement("div");
    trilha.className = "distribution-track";
    trilha.setAttribute("aria-hidden", "true");
    const barra = document.createElement("span");
    barra.style.setProperty("--bar-width", `${quantidade / maximo * 100}%`);
    trilha.append(barra);
    const valor = document.createElement("strong");
    valor.className = "distribution-value";
    valor.textContent = formatoInteiro.format(quantidade);
    linha.append(legenda, valor, trilha);
    fragmento.append(linha);
  });
  elementos.distribuicao.replaceChildren(fragmento);
  elementos.legendaDistribuicao.textContent = `Distribuição dos ${formatoInteiro.format(estado.dados.fila.length)} pedidos da fila completa. Não inclui todos os pedidos avaliados e não mede acurácia. Cada faixa inclui seu início; a última também inclui 1.`;
}

function abrirDetalhe(pedido, gatilho) {
  estado.pedidoAberto = pedido;
  estado.gatilhoDetalhe = gatilho;
  document.getElementById("detalhe-id").textContent = pedido.order_id;
  document.getElementById("detalhe-score").textContent = formatoScore.format(pedido.score_atraso);
  document.getElementById("detalhe-posicao").textContent = formatoInteiro.format(pedido.posicao);
  document.getElementById("detalhe-total").textContent = formatoInteiro.format(estado.dados.fila.length);
  document.getElementById("detalhe-capacidade").textContent = formatoPercentual.format(estado.dados.fracao_fila);
  elementos.feedbackDetalhe.textContent = "";
  elementos.dialogo.showModal();
}

async function copiarIdentificador() {
  if (!estado.pedidoAberto) return;
  try {
    await navigator.clipboard.writeText(estado.pedidoAberto.order_id);
    elementos.feedbackDetalhe.textContent = "Identificador copiado.";
  } catch {
    elementos.feedbackDetalhe.textContent = "O navegador não permitiu copiar. Selecione o identificador acima e use Ctrl+C ou o comando Copiar.";
  }
}

function campoCsv(valor) {
  let texto = String(valor);
  // Evita executar conteúdo como fórmula ao abrir a exportação em planilhas.
  if (/^[\s]*[=+\-@\t\r]/.test(texto)) texto = "'" + texto;
  return '"' + texto.replaceAll('"', '""') + '"';
}

function exportarCsv() {
  if (!estado.filtrados.length) return;
  const linhas = ["posicao,order_id,score_atraso,prioridade"];
  for (const pedido of estado.filtrados) {
    linhas.push([pedido.posicao, pedido.order_id, pedido.score_atraso, pedido.prioridade].map(campoCsv).join(","));
  }
  const arquivo = new Blob(["\uFEFF", linhas.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  const endereco = URL.createObjectURL(arquivo);
  const link = document.createElement("a");
  link.href = endereco;
  link.download = `entregacerta-fila-${estado.atualizadoEm.toISOString().replace(/[:.]/g, "-")}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(endereco), 1000);
  elementos.mensagem.textContent = `Exportação preparada com ${formatoInteiro.format(estado.filtrados.length)} pedidos: todos os resultados do filtro atual, em todas as páginas.`;
}

// Movimento é opcional e respeita a preferência de acessibilidade do sistema.
function configurarMovimento() {
  const preferencia = window.matchMedia("(prefers-reduced-motion: reduce)");
  const ponteiroPreciso = window.matchMedia("(hover: hover) and (pointer: fine)");
  const botao = document.getElementById("motion-toggle");
  const cena = document.querySelector(".parcel-scene");
  let pausaManual = false;
  try { pausaManual = localStorage.getItem("entregacerta-motion-paused") === "true"; } catch { /* Preferência vale só nesta visita. */ }

  function atualizarMovimento() {
    const pausado = preferencia.matches || pausaManual;
    document.documentElement.classList.toggle("motion-paused", pausado);
    botao.setAttribute("aria-pressed", String(pausado));
    botao.disabled = preferencia.matches;
    document.getElementById("motion-label").textContent = preferencia.matches ? "Movimento reduzido" : pausado ? "Ativar movimento" : "Pausar movimento";
    if (cena && pausado) {
      cena.style.setProperty("--tilt-x", "0deg");
      cena.style.setProperty("--tilt-y", "0deg");
    }
  }
  botao.addEventListener("click", () => {
    pausaManual = !pausaManual;
    try { localStorage.setItem("entregacerta-motion-paused", String(pausaManual)); } catch { /* Armazenamento pode estar bloqueado. */ }
    atualizarMovimento();
  });
  preferencia.addEventListener("change", atualizarMovimento);
  atualizarMovimento();

  if (cena) {
    cena.addEventListener("pointermove", (evento) => {
      if (!ponteiroPreciso.matches || document.documentElement.classList.contains("motion-paused")) return;
      const limites = cena.getBoundingClientRect();
      cena.style.setProperty("--tilt-x", `${-(evento.clientY - limites.top - limites.height / 2) / limites.height * 5}deg`);
      cena.style.setProperty("--tilt-y", `${(evento.clientX - limites.left - limites.width / 2) / limites.width * 6}deg`);
    });
    cena.addEventListener("pointerleave", () => {
      cena.style.setProperty("--tilt-x", "0deg");
      cena.style.setProperty("--tilt-y", "0deg");
    });
  }

  if ("IntersectionObserver" in window && !document.documentElement.classList.contains("motion-paused")) {
    // O conteúdo só fica oculto depois que o observador está disponível.
    // Sem JavaScript ou com movimento reduzido, tudo permanece legível.
    const observador = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (entrada.isIntersecting) {
          entrada.target.classList.add("is-visible");
          observador.unobserve(entrada.target);
        }
      }
    }, { threshold: 0.08, rootMargin: "0px 0px -32px 0px" });
    document.querySelectorAll(".reveal").forEach((item) => {
      item.classList.add("reveal-pending");
      observador.observe(item);
    });
    // Navegação pelo teclado também revela o bloco que recebe o foco.
    document.addEventListener("focusin", (evento) => {
      const bloco = evento.target.closest(".reveal-pending");
      if (bloco) {
        bloco.classList.add("is-visible");
        observador.unobserve(bloco);
      }
    });
  }
  const cabecalho = document.getElementById("site-header");
  const atualizarCabecalho = () => cabecalho.classList.toggle("is-scrolled", window.scrollY > 24);
  window.addEventListener("scroll", atualizarCabecalho, { passive: true });
  atualizarCabecalho();
}

// Resumo determinístico dos dados já recebidos; nenhuma chamada a uma LLM.
function atualizarContextoAssistente() {
  const resumo = document.getElementById("assistente-contexto");
  if (!estado.dados) {
    resumo.textContent = estado.carregando
      ? "Análise em andamento. O resumo aparecerá quando a consulta for concluída."
      : "Gere uma análise para consultar aqui o resumo do lote.";
    return;
  }
  const dados = estado.dados;
  resumo.textContent = `${formatoInteiro.format(dados.pedidos_avaliados)} pedidos avaliados, `
    + `${formatoInteiro.format(dados.pedidos_na_fila)} na fila e capacidade de ${formatoPercentual.format(dados.fracao_fila)}. `
    + `${dados.contexto}. Última consulta concluída: ${formatoHorario.format(estado.atualizadoEm)}.`
    + (elementos.resultado.dataset.state === "error" ? " A atualização falhou; este é o último resultado válido." : "");
}

function configurarAssistente() {
  const abrir = document.getElementById("abrir-assistente");
  const painel = document.getElementById("assistente-dialog");
  const pergunta = document.getElementById("assistente-pergunta");
  const copiar = document.getElementById("copiar-pergunta");
  const feedback = document.getElementById("assistente-feedback");
  let fechamentoPendente = null;

  function atualizarRascunho() {
    document.getElementById("assistente-contagem").textContent = `${pergunta.value.length} / 1000`;
    copiar.disabled = !pergunta.value.trim();
    feedback.textContent = "";
  }

  function concluirFechamento() {
    if (painel.open) painel.close();
  }

  function fecharPainel() {
    if (!painel.open || painel.classList.contains("is-closing")) return;
    if (document.documentElement.classList.contains("motion-paused")) {
      concluirFechamento();
      return;
    }
    painel.classList.add("is-closing");
    // Também fecha se o navegador não emitir animationend.
    fechamentoPendente = window.setTimeout(concluirFechamento, 240);
  }

  abrir.addEventListener("click", () => {
    atualizarContextoAssistente();
    painel.showModal();
    document.documentElement.classList.add("assistant-open");
    abrir.setAttribute("aria-expanded", "true");
  });
  document.getElementById("fechar-assistente").addEventListener("click", fecharPainel);
  painel.addEventListener("cancel", (evento) => {
    evento.preventDefault();
    fecharPainel();
  });
  painel.addEventListener("keydown", (evento) => {
    if (evento.key !== "Tab") return;
    const controles = [...painel.querySelectorAll("button:not(:disabled), textarea")];
    const primeiro = controles[0];
    const ultimo = controles[controles.length - 1];
    if (evento.shiftKey && document.activeElement === primeiro) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primeiro.focus();
    }
  });
  painel.addEventListener("animationend", (evento) => {
    if (evento.target === painel && evento.animationName === "drawer-out") concluirFechamento();
  });
  painel.addEventListener("click", (evento) => {
    if (evento.target !== painel) return;
    const limites = painel.getBoundingClientRect();
    if (evento.clientX < limites.left || evento.clientX > limites.right || evento.clientY < limites.top || evento.clientY > limites.bottom) fecharPainel();
  });
  painel.addEventListener("close", () => {
    window.clearTimeout(fechamentoPendente);
    painel.classList.remove("is-closing");
    document.documentElement.classList.remove("assistant-open");
    abrir.setAttribute("aria-expanded", "false");
    abrir.focus({ preventScroll: true });
  });
  pergunta.addEventListener("input", atualizarRascunho);
  document.querySelectorAll("[data-prompt]").forEach((botao) => {
    botao.addEventListener("click", () => {
      pergunta.value = botao.dataset.prompt;
      atualizarRascunho();
      pergunta.focus();
    });
  });
  copiar.addEventListener("click", async () => {
    if (!pergunta.value.trim()) return;
    try {
      await navigator.clipboard.writeText(pergunta.value.trim());
      feedback.textContent = "Pergunta copiada. Nenhuma mensagem foi enviada à IA.";
    } catch {
      feedback.textContent = "Selecione o rascunho e use o comando Copiar do seu dispositivo.";
    }
  });
  document.getElementById("assistente-form").addEventListener("submit", (evento) => {
    evento.preventDefault();
    feedback.textContent = "Envio indisponível: a GenAI ainda não está conectada.";
  });
  abrir.hidden = false;
}

botoesCarregar.forEach((botao) => botao.addEventListener("click", () => {
  // A ação do destaque leva ao painel para mostrar progresso e resultado.
  if (botao.id === "carregar") {
    elementos.resultado.scrollIntoView({
      behavior: document.documentElement.classList.contains("motion-paused") ? "auto" : "smooth",
      block: "start",
    });
  }
  carregarFila();
}));
elementos.busca.addEventListener("input", aplicarFiltros);
elementos.ordem.addEventListener("change", aplicarFiltros);
elementos.tamanhoPagina.addEventListener("change", aplicarFiltros);
elementos.limpar.addEventListener("click", () => {
  elementos.busca.value = "";
  elementos.ordem.value = "score-desc";
  elementos.tamanhoPagina.value = "25";
  aplicarFiltros();
  elementos.busca.focus();
});
elementos.anterior.addEventListener("click", () => { estado.pagina--; renderizarTabela(); });
elementos.proxima.addEventListener("click", () => { estado.pagina++; renderizarTabela(); });
elementos.exportar.addEventListener("click", exportarCsv);
document.getElementById("copiar-id").addEventListener("click", copiarIdentificador);
document.getElementById("fechar-detalhe").addEventListener("click", () => elementos.dialogo.close());
elementos.dialogo.addEventListener("click", (evento) => {
  if (evento.target !== elementos.dialogo) return;
  const limites = elementos.dialogo.getBoundingClientRect();
  if (evento.clientX < limites.left || evento.clientX > limites.right || evento.clientY < limites.top || evento.clientY > limites.bottom) elementos.dialogo.close();
});
elementos.dialogo.addEventListener("close", () => {
  estado.gatilhoDetalhe?.focus();
  estado.pedidoAberto = null;
});

atualizarControles();
configurarMovimento();
configurarAssistente();
