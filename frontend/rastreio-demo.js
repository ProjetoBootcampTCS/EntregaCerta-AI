/* Cenários fictícios e fixos para demonstração da interface. Não usa rede, banco ou ML. */
(() => {
  const form = document.getElementById('tracking-demo-form');
  if (!form) return;
  const input = document.getElementById('tracking-demo-code');
  const mensagem = document.getElementById('tracking-demo-message');
  const vazio = document.getElementById('tracking-demo-empty');
  const resultado = document.getElementById('tracking-demo-result');
  const exemplos = [...document.querySelectorAll('[data-tracking-demo]')];
  const etapas = ['Pedido criado', 'Postado', 'Em trânsito', 'Saiu para entrega', 'Entregue'];
  const referencia = '13/11/2026 às 10h';

  // Os três exemplos usam a mesma data de referência, mesmo em acessos futuros.
  // Datas são dias civis: nenhuma conversão de fuso ou preenchimento de dados reais.
  const cenarios = {
    ECDEMO001: {
      origem:'Campinas, SP', destino:'Belo Horizonte, MG', etapa:2,
      prazo:'16/11/2026', estimativa:'16/11/2026', atencao:false,
      leitura:'No cenário, a entrega está estimada dentro do prazo prometido.',
      eventos:[
        ['13/11/2026 · 09h10','Pedido em trânsito','Transferência de Campinas, SP, para Belo Horizonte, MG.'],
        ['12/11/2026 · 18h40','Pedido recebido no centro de distribuição','Separação concluída para a próxima etapa.'],
        ['11/11/2026 · 08h30','Pedido postado','Coleta registrada em Campinas, SP.'],
        ['10/11/2026 · 14h20','Pedido criado','A loja preparou o envio.']
      ]
    },
    ECDEMO002: {
      origem:'Recife, PE', destino:'Olinda, PE', etapa:3,
      prazo:'13/11/2026', estimativa:'13/11/2026', atencao:false,
      leitura:'No cenário, o pedido saiu para entrega na data estimada. A entrega ainda não foi confirmada.',
      eventos:[
        ['13/11/2026 · 08h15','Saiu para entrega','Pedido encaminhado para a rota de entrega em Olinda, PE.'],
        ['12/11/2026 · 17h30','Pedido chegou à unidade de destino','Pedido recebido em Olinda, PE.'],
        ['11/11/2026 · 10h00','Pedido postado','Coleta registrada em Recife, PE.'],
        ['10/11/2026 · 16h10','Pedido criado','A loja preparou o envio.']
      ]
    },
    ECDEMO003: {
      origem:'São Paulo, SP', destino:'Salvador, BA', etapa:2,
      prazo:'14/11/2026', estimativa:'17/11/2026', atencao:true,
      leitura:'Neste exemplo, a estimativa está 3 dias após o prazo prometido. É uma situação fictícia para demonstrar um alerta, sem cálculo de probabilidade.',
      eventos:[
        ['13/11/2026 · 09h00','Reprogramação da transferência','O cenário inclui uma nova data estimada de entrega.'],
        ['12/11/2026 · 12h30','Pedido em trânsito','Transferência de São Paulo, SP, para Salvador, BA.'],
        ['10/11/2026 · 15h00','Pedido postado','Coleta registrada em São Paulo, SP.'],
        ['09/11/2026 · 11h45','Pedido criado','A loja preparou o envio.']
      ]
    }
  };
  const elemento = (tag, classe, texto) => {
    const n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texto !== undefined) n.textContent = texto;
    return n;
  };
  function limparResultado() {
    resultado.hidden = true;
    resultado.replaceChildren();
    vazio.hidden = false;
    input.removeAttribute('aria-invalid');
    exemplos.forEach(b => b.setAttribute('aria-pressed','false'));
    mensagem.textContent = '';
    mensagem.removeAttribute('data-error');
  }
  function mostrar(codigo) {
    limparResultado();
    const c = cenarios[codigo];
    if (!Object.hasOwn(cenarios, codigo)) {
      input.setAttribute('aria-invalid','true');
      mensagem.dataset.error = 'true';
      mensagem.textContent = 'Código fora da demonstração. Escolha ECDEMO001, ECDEMO002 ou ECDEMO003. Nenhum rastreio real foi consultado.';
      return;
    }
    input.value = codigo;
    const topo = elemento('div','tracking-demo-result-top');
    const titulo = elemento('h3','',codigo); titulo.id = 'tracking-demo-result-title';
    const nome = elemento('div',''); nome.append(elemento('p','eyebrow','RASTREIO SIMULADO'),titulo);
    topo.append(nome,elemento('span','tracking-demo-status',etapas[c.etapa]));
    const rota = elemento('p','tracking-demo-route',c.origem+' → '+c.destino);
    const fonte = elemento('p','tracking-demo-source','Transportadora fictícia · referência: '+referencia);
    const progresso = elemento('ol','tracking-demo-steps'); progresso.setAttribute('aria-label','Etapas do cenário fictício');
    etapas.forEach((e,i) => {
      const li = elemento('li',i<=c.etapa?'is-done':'',e);
      if(i===c.etapa)li.setAttribute('aria-current','step');
      progresso.append(li);
    });
    const datas = elemento('dl','tracking-demo-dates');
    [['Prazo prometido · exemplo',c.prazo],['Estimativa ilustrativa',c.estimativa]].forEach(([rotulo,data])=>{
      const item=elemento('div','');item.append(elemento('dt','',rotulo),elemento('dd','',data));datas.append(item);
    });
    const leitura = elemento('div','tracking-demo-reading'); leitura.dataset.attention = String(c.atencao);
    leitura.append(elemento('strong','',c.atencao?'Possível atraso · cenário fictício':'Leitura do cenário'),elemento('p','',c.leitura));
    const eventos = elemento('ol','tracking-demo-events'); eventos.setAttribute('aria-label','Movimentações fictícias, da mais recente para a mais antiga');
    c.eventos.forEach(([data,titulo,descricao])=>{
      const li=elemento('li','');li.append(elemento('span','tracking-demo-event-date',data),elemento('h4','',titulo),elemento('p','',descricao));eventos.append(li);
    });
    resultado.append(topo,rota,fonte,progresso,datas,leitura,elemento('h4','tracking-demo-events-title','Histórico ilustrativo'),eventos);
    vazio.hidden=true;resultado.hidden=false;
    if (window.matchMedia('(max-width:980px)').matches) {
      resultado.scrollIntoView({block:'start', behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth'});
    }
    exemplos.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.trackingDemo===codigo)));
    mensagem.textContent='Exemplo '+codigo+' exibido. '+etapas[c.etapa]+'. Datas e movimentações fictícias.';
  }
  form.addEventListener('submit',e=>{
    e.preventDefault();
    mostrar(input.value.trim().replace(/\s+/g,'').toUpperCase());
  });
  exemplos.forEach(b=>b.addEventListener('click',()=>mostrar(b.dataset.trackingDemo)));
  // Não mantém na tela um resultado que pertence ao código anterior.
  input.addEventListener('input',limparResultado);
})();
