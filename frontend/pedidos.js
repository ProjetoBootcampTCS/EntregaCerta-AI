/* Explorador de pedidos: a API filtra o lote inteiro antes de paginar. */
(() => {
  const $ = (id) => document.getElementById(id);
  const form = $("orders-filters");
  if (!form) return;
  const inteiro = new Intl.NumberFormat("pt-BR");
  const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
  const score = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
  const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const chave = "entregacerta-pedidos-filtros-v1";
  const dialog = $("orders-dialog");
  let dados = null, pagina = 1, controle = null, sequencia = 0, timer = null;
  let aberto = null, gatilho = null;

  function texto(tag, valor, classe) {
    const item = document.createElement(tag);
    item.textContent = valor;
    if (classe) item.className = classe;
    return item;
  }
  function rotulo(valor) { return valor ? String(valor).replaceAll("_", " ") : "Não informado"; }
  function numero(valor, formato = decimal, sufixo = "") {
    return typeof valor === "number" && Number.isFinite(valor) ? formato.format(valor) + sufixo : "Não informado";
  }
  // Datas Olist sem fuso: conserva o dia/hora registrado, sem deslocá-lo no navegador.
  function dataOlist(valor, completa = false) {
    if (!valor || !/^\d{4}-\d{2}-\d{2}T/.test(valor)) return "Não informado";
    const [ano, mes, dia] = valor.slice(0, 10).split("-");
    return `${dia}/${mes}/${ano}` + (completa ? ` às ${valor.slice(11, 16)}` : "");
  }
  function parametros() {
    const p = new URLSearchParams();
    for (const [nome, valor] of new FormData(form)) if (valor.trim()) p.set(nome, valor.trim());
    p.set("pagina", pagina);
    p.set("tamanho", $("orders-size").value);
    p.set("ordem", $("orders-sort").value);
    return p;
  }
  function salvar(p) {
    try { sessionStorage.setItem(chave, p.toString()); } catch { /* Consulta funciona sem armazenamento. */ }
  }
  function restaurar() {
    try {
      const p = new URLSearchParams(sessionStorage.getItem(chave) || "");
      for (const campo of form.elements) {
        if (!campo.name || !p.has(campo.name)) continue;
        const valor = p.get(campo.name);
        if (["uf", "categoria"].includes(campo.name) && valor) campo.add(new Option(rotulo(valor), valor));
        campo.value = valor;
      }
      if (["25", "50", "100"].includes(p.get("tamanho"))) $("orders-size").value = p.get("tamanho");
      if ([...$("orders-sort").options].some(o => o.value === p.get("ordem"))) $("orders-sort").value = p.get("ordem");
      pagina = Math.max(1, Number.parseInt(p.get("pagina"), 10) || 1);
      if (["inicio", "fim", "score_min", "score_max"].some(k => p.has(k))) $("orders-filters").querySelector("details").open = true;
    } catch { /* Filtros padrão quando a sessão não estiver disponível. */ }
  }
  function intervalosValidos() {
    const inicio = form.elements.inicio, fim = form.elements.fim;
    const min = form.elements.score_min, max = form.elements.score_max;
    fim.setCustomValidity(inicio.value && fim.value && inicio.value > fim.value ? "A data final deve ser igual ou posterior à inicial." : "");
    max.setCustomValidity(Number(min.value || 0) > Number(max.value || 1) ? "O score máximo deve ser maior ou igual ao mínimo." : "");
    return form.reportValidity();
  }
  function estadoConsulta(carregando) {
    $("lista-pedidos").setAttribute("aria-busy", String(carregando));
    $("orders-refresh").disabled = carregando;
    $("orders-prev").disabled = carregando || !dados || dados.pagina <= 1;
    $("orders-next").disabled = carregando || !dados || dados.pagina >= dados.paginas;
    $("orders-status").dataset.state = carregando ? "loading" : "ready";
    $("orders-status").textContent = carregando ? "Consultando pedidos" : "Lote disponível";
  }
  function opcoes(id, valores, primeiro, selecionado) {
    const select = $(id);
    select.replaceChildren(new Option(primeiro, ""));
    valores.forEach(v => select.add(new Option(rotulo(v), v)));
    // Um filtro antigo não desaparece silenciosamente caso o lote seja atualizado.
    if (selecionado && !valores.includes(selecionado)) select.add(new Option(rotulo(selecionado), selecionado));
    select.value = selecionado || "";
  }
  function badge(pedido) {
    return texto("span", pedido.prioridade === 1 ? "Na fila" : "Fora da fila", `orders-badge${pedido.prioridade === 1 ? " is-priority" : ""}`);
  }
  function renderizar(resposta, p) {
    dados = resposta;
    pagina = dados.pagina;
    p.set("pagina", pagina);
    salvar(p);
    $("orders-total").textContent = inteiro.format(dados.total);
    $("orders-priority").textContent = inteiro.format(dados.na_fila);
    $("orders-capacity").textContent = `${decimal.format(dados.fracao_fila * 100)}% do lote · seleção original`;
    $("orders-filtered").textContent = inteiro.format(dados.filtrados);
    $("orders-filtered-priority").textContent = inteiro.format(dados.filtrados_na_fila);
    $("orders-updated").textContent = "Lote consultado em " + new Date(dados.consultado_em).toLocaleString("pt-BR");
    opcoes("orders-state", dados.opcoes.ufs, "Todas as UFs", p.get("uf"));
    opcoes("orders-category", dados.opcoes.categorias, "Todas as categorias", p.get("categoria"));
    const ativos = [...p].filter(([k, v]) => !["pagina", "tamanho", "ordem", "atualizar"].includes(k) && !(k === "prioridade" && v === "todos")).length;
    $("orders-filter-count").textContent = ativos ? `${ativos} filtro(s) aplicado(s)` : "Todos os pedidos do lote";
    const inicio = dados.filtrados ? (pagina - 1) * dados.tamanho + 1 : 0;
    const fim = Math.min(pagina * dados.tamanho, dados.filtrados);
    $("orders-count").textContent = `${inteiro.format(inicio)}–${inteiro.format(fim)} de ${inteiro.format(dados.filtrados)} pedidos`;
    $("orders-page").textContent = `Página ${inteiro.format(pagina)} de ${inteiro.format(dados.paginas)}`;
    $("orders-empty").hidden = dados.filtrados !== 0;
    $("orders-table-scroll").hidden = dados.filtrados === 0;
    $("orders-pagination").hidden = dados.filtrados === 0;
    const linhas = document.createDocumentFragment();
    for (const pedido of dados.pedidos) {
      const tr = document.createElement("tr");
      const identidade = document.createElement("td");
      const link = texto("button", pedido.order_id, "orders-id");
      link.type = "button";
      link.title = `Ver detalhes do pedido ${pedido.order_id}`;
      link.addEventListener("click", () => abrir(pedido, link));
      identidade.append(link, texto("small", dataOlist(pedido.order_approved_at), "orders-cell-note"));
      const rota = document.createElement("td");
      rota.append(texto("strong", `${pedido.uf_origem || "—"} → ${pedido.customer_state || "—"}`, "orders-route"), texto("small", rotulo(pedido.categoria_principal), "orders-cell-note orders-category"));
      const valor = texto("td", numero(pedido.valor_pago, moeda), "orders-money");
      const risco = document.createElement("td");
      const barra = texto("span", "", "orders-score-track");
      barra.setAttribute("aria-hidden", "true");
      const preenchimento = document.createElement("i");
      preenchimento.style.width = `${pedido.score_atraso * 100}%`;
      barra.append(preenchimento);
      risco.append(texto("strong", score.format(pedido.score_atraso), "orders-score-value"), barra);
      const fila = document.createElement("td"); fila.append(badge(pedido));
      const acao = document.createElement("td");
      const botao = texto("button", "Detalhes ↗", "orders-detail-button");
      botao.type = "button"; botao.setAttribute("aria-label", `Detalhes do pedido ${pedido.order_id}`);
      botao.addEventListener("click", () => abrir(pedido, botao)); acao.append(botao);
      tr.append(identidade, rota, valor, risco, fila, acao); linhas.append(tr);
    }
    $("orders-rows").replaceChildren(linhas);
    $("pedidos-contexto").textContent = `${inteiro.format(dados.total)} pedidos no lote histórico; ${inteiro.format(dados.filtrados)} encontrados pelos filtros. A IA consulta o resumo geral da fila; os filtros e detalhes desta página não são enviados automaticamente.`;
  }
  async function consultar(atualizar = false) {
    clearTimeout(timer);
    controle?.abort();
    const requisicao = ++sequencia;
    if (!intervalosValidos()) {
      estadoConsulta(false);
      $("orders-message").textContent = "Corrija o intervalo. Os resultados ainda correspondem à última consulta concluída.";
      return;
    }
    const p = parametros();
    if (atualizar) p.set("atualizar", "true");
    controle = new AbortController();
    const abortar = controle;
    const timeout = setTimeout(() => abortar.abort(), 60000);
    estadoConsulta(true);
    $("orders-message").textContent = "Consultando… Os resultados anteriores permanecem visíveis até a conclusão.";
    try {
      const resposta = await window.ecFetch(`/api/pedidos?${p}`, { signal: controle.signal, headers: { Accept: "application/json" } });
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const conteudo = await resposta.json();
      if (requisicao !== sequencia) return;
      if (!Array.isArray(conteudo.pedidos) || !Number.isInteger(conteudo.total) || !Array.isArray(conteudo.opcoes?.ufs)
        || !Array.isArray(conteudo.opcoes?.categorias) || !Number.isInteger(conteudo.filtrados)
        || !Number.isInteger(conteudo.pagina) || !Number.isInteger(conteudo.paginas)
        || conteudo.pedidos.some(r => typeof r.order_id !== "string" || !Number.isFinite(r.score_atraso) || r.score_atraso < 0 || r.score_atraso > 1 || ![0, 1].includes(r.prioridade))) throw new Error("Resposta inválida");
      p.delete("atualizar"); renderizar(conteudo, p);
      estadoConsulta(false);
      $("orders-message").textContent = "Consulta concluída. Clique em um pedido para ver os detalhes. Score não é probabilidade calibrada.";
    } catch (erro) {
      if (requisicao !== sequencia) return;
      estadoConsulta(false);
      $("orders-status").dataset.state = "error";
      $("orders-status").textContent = "Consulta indisponível";
      $("orders-message").textContent = (dados ? "A consulta falhou. A lista e os indicadores preservam o último resultado válido, antes dos novos filtros. " : "Não foi possível carregar os pedidos. ")
        + "Verifique a API e o PostgreSQL e tente Atualizar lote. " + (erro.name === "AbortError" ? "Tempo limite de 60 segundos atingido." : "");
    } finally { clearTimeout(timeout); }
  }
  function abrir(pedido, origem) {
    aberto = pedido; gatilho = origem;
    $("orders-detail-id").textContent = pedido.order_id;
    $("orders-detail-score").textContent = score.format(pedido.score_atraso);
    const etiqueta = badge(pedido);
    $("orders-detail-queue").className = etiqueta.className;
    $("orders-detail-queue").textContent = etiqueta.textContent;
    $("orders-copy-status").textContent = "";
    const grupos = [
      ["Pedido e destino", [["Aprovação", dataOlist(pedido.order_approved_at, true)], ["Origem / destino", `${pedido.uf_origem || "Não informado"} → ${pedido.customer_state || "Não informado"}`], ["Categoria principal", rotulo(pedido.categoria_principal)], ["Itens / vendedores", `${numero(pedido.quantidade_itens, inteiro)} / ${numero(pedido.quantidade_vendedores, inteiro)}`]]],
      ["Valores e pagamento", [["Valor dos itens", numero(pedido.valor_itens, moeda)], ["Frete", numero(pedido.valor_frete, moeda)], ["Valor pago", numero(pedido.valor_pago, moeda)], ["Pagamento / parcelas máximas", `${rotulo(pedido.tipo_pagamento_principal)} / ${numero(pedido.parcelas_maximas, inteiro)}`]]],
      ["Informações logísticas", [["Prazo prometido", numero(pedido.prazo_prometido_dias, decimal, " dias")], ["Peso total", numero(pedido.peso_total_g, decimal, " g")], ["Distância média dos vendedores", numero(pedido.distancia_media_vendedores_km, decimal, " km")], ["Distância máxima dos vendedores", numero(pedido.distancia_max_vendedores_km, decimal, " km")]]],
    ];
    const destino = $("orders-detail-fields"); destino.replaceChildren();
    for (const [titulo, campos] of grupos) {
      const secao = texto("section", "", "orders-detail-section"); secao.append(texto("h3", titulo));
      const lista = document.createElement("dl");
      campos.forEach(([nome, valor]) => { const par = document.createElement("div"); par.append(texto("dt", nome), texto("dd", valor)); lista.append(par); });
      secao.append(lista); destino.append(secao);
    }
    destino.append(botaoAssistentePedido(pedido.order_id, 'olist'));
    dialog.showModal(); dialog.scrollTop = 0;
  }
  function limpar() {
    form.reset(); $("orders-sort").value = "score-desc"; pagina = 1; consultar();
  }
  form.addEventListener("submit", event => { event.preventDefault(); pagina = 1; consultar(); });
  form.addEventListener("change", event => { if (event.target.type !== "search") { pagina = 1; consultar(); } });
  $("orders-search").addEventListener("input", () => {
    clearTimeout(timer); controle?.abort(); ++sequencia; estadoConsulta(false);
    $("orders-message").textContent = "Busca alterada; aguardando você terminar de digitar…";
    timer = setTimeout(() => { pagina = 1; consultar(); }, 350);
  });
  $("orders-sort").addEventListener("change", () => { pagina = 1; consultar(); });
  $("orders-size").addEventListener("change", () => { pagina = 1; consultar(); });
  $("orders-prev").addEventListener("click", () => { pagina = Math.max(1, pagina - 1); consultar(); });
  $("orders-next").addEventListener("click", () => { pagina += 1; consultar(); });
  $("orders-reset").addEventListener("click", limpar);
  $("orders-empty-reset").addEventListener("click", limpar);
  $("orders-refresh").addEventListener("click", () => consultar(true));
  $("orders-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
  dialog.addEventListener("close", () => { if (gatilho?.isConnected) gatilho.focus(); });
  $("orders-copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(aberto.order_id); $("orders-copy-status").textContent = "Identificador copiado."; }
    catch { $("orders-copy-status").textContent = "Não foi possível copiar automaticamente. Selecione o identificador acima e copie."; }
  });
  restaurar(); consultar();
})();
