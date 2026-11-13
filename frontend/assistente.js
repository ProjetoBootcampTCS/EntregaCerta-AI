// Componente compartilhado por todas as páginas; independente da animação de abertura.
if (!document.getElementById("abrir-assistente")) {
  const template = document.createElement("template");
  template.innerHTML = "  <button id=\"abrir-assistente\" class=\"assistant-launcher\" type=\"button\" aria-label=\"Abrir assistente de IA\" aria-haspopup=\"dialog\" aria-controls=\"assistente-dialog\" aria-expanded=\"false\" hidden>\n    <span class=\"launcher-icon\" aria-hidden=\"true\"><svg viewBox=\"0 0 24 24\" fill=\"none\"><path d=\"M20 10.5v4a4 4 0 0 1-4 4H9l-5 3v-6a4 4 0 0 1-1-2.5v-6a4 4 0 0 1 4-4h6\"/><path d=\"m19 2 1.2 2.8L23 6l-2.8 1.2L19 10l-1.2-2.8L15 6l2.8-1.2Z\"/></svg></span>\n    <span class=\"launcher-copy\">Assistente <strong>AI</strong><small>Pergunte sobre a análise</small></span><span class=\"launcher-arrow\" aria-hidden=\"true\">↗</span>\n  </button>\n  <dialog id=\"assistente-dialog\" class=\"assistant-drawer\" aria-labelledby=\"assistente-titulo\" aria-describedby=\"assistente-descricao\">\n    <header class=\"assistant-header\">\n      <img src=\"/static/logo.svg?v=2\" width=\"40\" height=\"40\" alt=\"\">\n      <div><p class=\"eyebrow\">SEU PRÓXIMO PONTO DE VISTA</p><h2 id=\"assistente-titulo\">Assistente EntregaCerta</h2></div>\n      <button id=\"fechar-assistente\" class=\"assistant-close\" type=\"button\" aria-label=\"Fechar assistente\" autofocus><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" focusable=\"false\"><path d=\"m6 6 12 12M18 6 6 18\"/></svg></button>\n    </header>\n    <div id=\"assistente-conteudo\" class=\"assistant-content\">\n      <div id=\"assistente-boas-vindas\">\n        <span class=\"assistant-status\"><span aria-hidden=\"true\"></span> Assistente com IA</span>\n        <div class=\"assistant-intro\"><span class=\"assistant-orbit\" aria-hidden=\"true\">✳</span><h3>Boas perguntas.<br><em>Novas perspectivas.</em></h3><p id=\"assistente-descricao\">Tire dúvidas sobre a análise ou faça uma pergunta geral.</p></div>\n        <div class=\"assistant-suggestions\"><p>Escolha uma pergunta para começar</p><button type=\"button\" data-prompt=\"Como interpretar o score de atraso dos pedidos?\">Como interpretar o score? <span aria-hidden=\"true\">↗</span></button><button type=\"button\" data-prompt=\"Como funciona a seleção dos pedidos para a fila de análise?\">Como a fila é formada? <span aria-hidden=\"true\">↗</span></button><button type=\"button\" data-prompt=\"Quais limitações devo considerar ao usar esta análise histórica?\">Quais são os limites da análise? <span aria-hidden=\"true\">↗</span></button></div>\n      </div>\n      <details class=\"assistant-context assistant-context-details\">\n        <summary>Contexto do painel</summary>\n        <p id=\"assistente-contexto\">Acesse o Dashboard para gerar a análise e consultar o resumo do lote.</p><p class=\"assistant-context-note\">Dados da aplicação. Este resumo não é uma resposta gerada por IA. Sua pergunta e o resumo da fila são enviados à IA. Confira as respostas antes de tomar decisões.</p>\n      </details>\n      <div id=\"assistente-historico\" class=\"assistant-conversation\" role=\"log\" aria-label=\"Conversa com o assistente\" aria-live=\"polite\" aria-relevant=\"additions text\" hidden></div>\n    </div>\n    <form id=\"assistente-form\" class=\"assistant-composer\">\n      <div class=\"composer-label\"><label for=\"assistente-pergunta\">Mensagem</label><span id=\"assistente-contagem\">0 / 1000</span></div>\n      <textarea id=\"assistente-pergunta\" rows=\"2\" maxlength=\"1000\" placeholder=\"Pergunte ao EntregaCerta…\" aria-describedby=\"assistente-aviso assistente-atalhos\"></textarea>\n      <div class=\"composer-actions\"><button id=\"copiar-pergunta\" class=\"text-button\" type=\"button\" disabled>Copiar pergunta</button><button id=\"enviar-pergunta\" class=\"assistant-send\" type=\"submit\" disabled><span aria-hidden=\"true\">↗</span> <span id=\"enviar-pergunta-texto\">Enviar pergunta</span></button></div>\n      <p id=\"assistente-atalhos\" class=\"composer-shortcuts\">Enter envia · Shift + Enter quebra a linha</p>\n      <p id=\"assistente-aviso\">Histórico enquanto a página estiver aberta. A IA recebe uma pergunta por vez.</p>\n      <p id=\"assistente-feedback\" class=\"assistant-feedback\" role=\"status\" aria-live=\"polite\"></p>\n    </form>\n  </dialog>";
  document.body.append(template.content);
}

// Resumo determinístico dos dados já recebidos; nenhuma chamada a uma LLM.
function atualizarContextoAssistente() {
  const resumo = document.getElementById("assistente-contexto");
  if (!resumo) return;
  if (window.ecAuth?.estado.usuario?.perfil !== 'analista') {
    resumo.textContent = 'Orientações sobre a loja demonstrativa, prazos e etapas. O chat não consulta pedidos individuais nem estima probabilidades ou datas de entrega.';
    return;
  }
  const contextoPedidos = document.getElementById("pedidos-contexto");
  if (contextoPedidos) {
    resumo.textContent = contextoPedidos.textContent;
    return;
  }
  if (typeof elementos === "undefined" || !elementos.resultado) {
    resumo.textContent = "Acesse o Dashboard para gerar a análise e consultar o resumo do lote.";
    return;
  }
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

// Markdown básico com elementos permitidos. O texto da IA nunca vira HTML bruto.
function formatarTextoAssistente(destino, texto) {
  function adicionarTrecho(elemento, trecho, nivel = 0) {
    if (nivel > 8) {
      elemento.append(document.createTextNode(trecho));
      return;
    }
    const marcadores = /\\([\\`*_])|`([^`\n]+)`|\*\*\*([^\n]+?)\*\*\*|\*\*([^\n]+?)\*\*|(?<!\w)__([^\n]+?)__(?!\w)|\*([^*\n]+?)\*|(?<!\w)_([^_\n]+?)_(?!\w)/g;
    let inicio = 0;
    for (const parte of trecho.matchAll(marcadores)) {
      elemento.append(document.createTextNode(trecho.slice(inicio, parte.index)));
      if (parte[1] !== undefined) {
        elemento.append(document.createTextNode(parte[1]));
      } else if (parte[2] !== undefined) {
        const codigo = document.createElement("code");
        codigo.textContent = parte[2];
        elemento.append(codigo);
      } else {
        const negrito = parte[3] ?? parte[4] ?? parte[5];
        const destaque = document.createElement(negrito !== undefined ? "strong" : "em");
        if (parte[3] !== undefined) {
          const italico = document.createElement("em");
          adicionarTrecho(italico, parte[3], nivel + 1);
          destaque.append(italico);
        } else {
          adicionarTrecho(destaque, negrito ?? parte[6] ?? parte[7], nivel + 1);
        }
        elemento.append(destaque);
      }
      inicio = parte.index + parte[0].length;
    }
    elemento.append(document.createTextNode(trecho.slice(inicio)));
  }

  destino.replaceChildren();
  destino.classList.add("chat-markdown");
  let paragrafo = [];
  let lista = null;
  let blocoCodigo = null;
  function concluirParagrafo() {
    if (!paragrafo.length) return;
    const elemento = document.createElement("p");
    adicionarTrecho(elemento, paragrafo.join("\n"));
    destino.append(elemento);
    paragrafo = [];
  }
  function concluirCodigo() {
    const pre = document.createElement("pre");
    const codigo = document.createElement("code");
    codigo.textContent = blocoCodigo.join("\n");
    pre.append(codigo);
    destino.append(pre);
    blocoCodigo = null;
  }

  for (const linha of texto.replace(/\r\n?/g, "\n").split("\n")) {
    if (/^\s{0,3}```/.test(linha)) {
      concluirParagrafo();
      lista = null;
      if (blocoCodigo !== null) concluirCodigo();
      else blocoCodigo = [];
      continue;
    }
    if (blocoCodigo !== null) {
      blocoCodigo.push(linha);
      continue;
    }
    const titulo = linha.match(/^\s{0,3}(#{1,6})\s+(.+?)(?:\s+#+)?\s*$/);
    const item = linha.match(/^\s*(?:([-+*])\s+|(\d+)[.)]\s+)(.+)$/);
    if (!linha.trim() || titulo || item) concluirParagrafo();
    if (titulo) {
      lista = null;
      // O painel já tem h2; os títulos das respostas começam em h3.
      const elemento = document.createElement(`h${Math.min(6, titulo[1].length + 2)}`);
      adicionarTrecho(elemento, titulo[2]);
      destino.append(elemento);
    } else if (item) {
      const tipo = item[1] ? "ul" : "ol";
      if (!lista || lista.tagName.toLowerCase() !== tipo) {
        lista = document.createElement(tipo);
        if (tipo === "ol") lista.setAttribute("start", String(Number(item[2])));
        destino.append(lista);
      }
      const elemento = document.createElement("li");
      adicionarTrecho(elemento, item[3]);
      lista.append(elemento);
    } else {
      lista = null;
      if (linha.trim()) paragrafo.push(linha);
    }
  }
  concluirParagrafo();
  if (blocoCodigo !== null) concluirCodigo();
}

function configurarAssistente() {
  const abrir = document.getElementById("abrir-assistente");
  const painel = document.getElementById("assistente-dialog");
  const pergunta = document.getElementById("assistente-pergunta");
  const copiar = document.getElementById("copiar-pergunta");
  const feedback = document.getElementById("assistente-feedback");
  const formulario = document.getElementById("assistente-form");
  const enviar = document.getElementById("enviar-pergunta");
  const rotuloEnviar = document.getElementById("enviar-pergunta-texto");
  const conteudo = document.getElementById("assistente-conteudo");
  const historico = document.getElementById("assistente-historico");
  const boasVindas = document.getElementById("assistente-boas-vindas");
  const sugestoes = [...painel.querySelectorAll("[data-prompt]")];
  let fechamentoPendente = null;
  let consultando = false;
  let controladorAtivo = null;
  let identidade = window.ecAuth?.estado.usuario?.id || null;
  const login = document.createElement('a');
  login.href = '/entrar'; login.className = 'assistant-login';
  login.textContent = 'Entre na sua conta para conversar com o assistente ↗';
  formulario.prepend(login);
  function atualizarSessao() {
    const usuario = window.ecAuth?.estado.usuario;
    if ((usuario?.id || null) !== identidade) {
      controladorAtivo?.abort();
      historico.replaceChildren(); historico.hidden = true; boasVindas.hidden = false;
      pergunta.value = ''; identidade = usuario?.id || null;
    }
    const autenticado = !!window.ecAuth?.estado.autenticado;
    login.hidden = autenticado;
    pergunta.disabled = !autenticado;
    const nota = painel.querySelector('.assistant-context-note');
    nota.textContent = usuario?.perfil === 'analista'
      ? 'A IA recebe sua pergunta e o resumo geral da fila histórica. Filtros e detalhes individuais não são enviados automaticamente. Confira as respostas antes de decidir.'
      : 'A IA recebe sua pergunta e orientações gerais da loja. Não envie informações sensíveis. Confira as respostas antes de decidir.';
    const prompts = usuario?.perfil === 'analista'
      ? ['Como interpretar o score de atraso dos pedidos?', 'Como funciona a seleção dos pedidos para a fila de análise?', 'Quais são os limites desta análise histórica?']
      : ['Onde acompanho meus pedidos?', 'O que significa prazo prometido não definido?', 'Esta loja realiza entregas reais?'];
    sugestoes.forEach((b,i) => { b.dataset.prompt = prompts[i]; b.textContent = prompts[i] + ' ↗'; });
    atualizarContextoAssistente(); atualizarRascunho();
  }

  function atualizarRascunho() {
    document.getElementById("assistente-contagem").textContent = `${pergunta.value.length} / 1000`;
    copiar.disabled = consultando || !pergunta.value.trim();
    enviar.disabled = consultando || !window.ecAuth?.estado.autenticado || !pergunta.value.trim();
    if (!consultando) feedback.textContent = "";
  }

  function atualizarConsulta(emAndamento) {
    consultando = emAndamento;
    pergunta.readOnly = emAndamento;
    formulario.setAttribute("aria-busy", String(emAndamento));
    sugestoes.forEach((botao) => { botao.disabled = emAndamento; });
    rotuloEnviar.textContent = emAndamento ? "Consultando..." : "Enviar pergunta";
    atualizarRascunho();
  }

  function acompanharConversa(forcar = false) {
    const pertoDoFim = conteudo.scrollHeight - conteudo.scrollTop - conteudo.clientHeight < 100;
    if (painel.open && (forcar || pertoDoFim)) conteudo.scrollTop = conteudo.scrollHeight;
  }

  function adicionarMensagem(autor, texto, estadoMensagem = "ready") {
    const elemento = document.createElement("article");
    elemento.className = `chat-message chat-message-${autor}`;
    elemento.dataset.state = estadoMensagem;
    elemento.setAttribute("aria-busy", String(estadoMensagem === "loading"));
    const rotulo = document.createElement("p");
    rotulo.className = "chat-message-author";
    rotulo.textContent = autor === "user" ? "Você" : "EntregaCerta AI";
    const corpo = document.createElement("div");
    corpo.className = "chat-message-text";
    // Perguntas e respostas são texto não confiável, nunca HTML.
    corpo.textContent = texto;
    elemento.append(rotulo, corpo);
    historico.append(elemento);
    return { elemento, rotulo, corpo };
  }

  function mostrarResposta(mensagem, estadoResposta, texto) {
    // Só acompanha a resposta se a pessoa não estiver lendo mensagens antigas.
    const acompanhar = conteudo.scrollHeight - conteudo.scrollTop - conteudo.clientHeight < 100;
    mensagem.elemento.dataset.state = estadoResposta;
    mensagem.rotulo.textContent = estadoResposta === "ready" ? "EntregaCerta AI · resposta gerada" : "Aviso do sistema";
    if (estadoResposta === "ready") formatarTextoAssistente(mensagem.corpo, texto);
    else mensagem.corpo.textContent = texto;
    mensagem.elemento.setAttribute("aria-busy", "false");
    if (acompanhar) acompanharConversa(true);
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
    if (!historico.hidden) acompanharConversa(true);
  });
  document.getElementById("fechar-assistente").addEventListener("click", fecharPainel);
  painel.addEventListener("cancel", (evento) => {
    evento.preventDefault();
    fecharPainel();
  });
  painel.addEventListener("keydown", (evento) => {
    if (evento.key !== "Tab") return;
    const controles = [...painel.querySelectorAll("button:not(:disabled), textarea, summary")]
      .filter((controle) => controle.getClientRects().length > 0);
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
  pergunta.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey && !evento.isComposing) {
      evento.preventDefault();
      if (!consultando) formulario.requestSubmit();
    }
  });
  sugestoes.forEach((botao) => {
    botao.addEventListener("click", () => {
      if (consultando) return;
      pergunta.value = botao.dataset.prompt;
      atualizarRascunho();
      pergunta.focus();
    });
  });
  copiar.addEventListener("click", async () => {
    if (!pergunta.value.trim()) return;
    try {
      await navigator.clipboard.writeText(pergunta.value.trim());
      feedback.textContent = "Pergunta copiada.";
    } catch {
      feedback.textContent = "Selecione a pergunta e use o comando Copiar do seu dispositivo.";
    }
  });
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (consultando || !window.ecAuth?.estado.autenticado) return;

    const texto = pergunta.value.trim();
    if (!texto || texto.length > 1000) {
      feedback.textContent = texto ? "Use até 1000 caracteres." : "Digite uma pergunta.";
      pergunta.focus();
      return;
    }

    boasVindas.hidden = true;
    historico.hidden = false;
    adicionarMensagem("user", texto);
    const mensagemResposta = adicionarMensagem("assistant", "Aguardando resposta…", "loading");
    pergunta.value = "";
    atualizarConsulta(true);
    acompanharConversa(true);
    feedback.textContent = "Consultando o assistente...";

    // Um prazo finito permite recuperar o formulário se a conexão não responder.
    const controlador = new AbortController();
    controladorAtivo = controlador;
    const identidadeConsulta = identidade;
    const temporizador = window.setTimeout(() => controlador.abort(), 120000);
    let mensagemFinal = "";

    try {
      const resposta = await window.ecFetch("/api/assistente", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta: texto }),
        signal: controlador.signal,
      });
      if (!resposta.ok) throw new Error("Falha na consulta ao backend.");

      const dados = await resposta.json();
      if (identidadeConsulta !== identidade) return;
      if (typeof dados?.disponivel !== "boolean" || typeof dados?.resposta !== "string" || !dados.resposta.trim()) {
        throw new Error("Resposta inesperada do backend.");
      }

      if (dados.disponivel) {
        mostrarResposta(mensagemResposta, "ready", dados.resposta.trim());
        mensagemFinal = "Resposta recebida.";
      } else {
        mostrarResposta(mensagemResposta, "unavailable", dados.resposta.trim());
        mensagemFinal = "Assistente indisponível nesta consulta.";
      }
    } catch (erro) {
      if (identidadeConsulta !== identidade) return;
      const mensagem = erro.name === "AbortError"
        ? "O tempo de espera terminou. Tente novamente mais tarde."
        : "Não foi possível consultar o assistente. Tente novamente mais tarde.";
      mostrarResposta(mensagemResposta, "error", mensagem);
      mensagemFinal = "Não foi possível concluir a consulta.";
    } finally {
      window.clearTimeout(temporizador);
      atualizarConsulta(false);
      controladorAtivo = null;
      atualizarSessao();
      feedback.textContent = identidadeConsulta === identidade ? mensagemFinal : '';
    }
  });
  atualizarRascunho();
  abrir.hidden = false;
  document.addEventListener('ec:session', atualizarSessao);
  window.ecAuth?.ready.then(atualizarSessao);
  atualizarSessao();
}


document.addEventListener('DOMContentLoaded', configurarAssistente);
