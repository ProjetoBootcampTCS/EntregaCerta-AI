(() => {
  const $ = s => document.querySelector(s);
  const dinheiro = n => (n / 100).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
  const data = s => new Date(s).toLocaleString('pt-BR', {dateStyle:'short',timeStyle:'short'});
  const etapas = {recebido:'Recebido', em_preparacao:'Em preparação', despachado:'Despachado', entregue:'Entregue'};
  const chave = 'entregacerta-carrinho-v1';
  let produtos = [], carrinho = {}, pedidoPendente = null, enviando = false;
  try { const salvo = JSON.parse(localStorage.getItem(chave) || '{}'); if (salvo && typeof salvo === 'object' && !Array.isArray(salvo)) carrinho = salvo; } catch { /* Carrinho vazio se armazenamento indisponível. */ }
  const el = (tag, classe, texto) => { const n=document.createElement(tag); if(classe)n.className=classe; if(texto !== undefined)n.textContent=texto; return n; };
  const icones = [
    '<path d="M25 17h14v7H25zM29 10h6v7M23 24h18v30H23zM28 36h8m-4-4v8"/>',
    '<circle cx="32" cy="32" r="22"/><path d="m25 25 14 1 3 13-12 7-10-10zM25 25l-7-9m21 10 10-7m-7 20 6 7m-18 0-2 8m-8-18-10 1"/>',
    '<path d="M14 29h36v14a11 11 0 0 1-11 11H25a11 11 0 0 1-11-11zM10 25h44M28 19h8m-4-4v4M14 34H8m42 0h6"/>',
    '<rect x="10" y="13" width="44" height="30" rx="3"/><path d="M26 43v9m12-9v9m-18 0h24M16 36h32"/>',
    '<path d="M18 26h28l7 17H11zM32 43v11m-11 0h22M32 26V13m-5 0h10"/>',
    '<path d="M32 18c-7-5-14-5-23-4v36c9-1 16-1 23 4 7-5 14-5 23-4V14c-9-1-16-1-23 4zm0 0v36M15 23l10 3m-10 6 10 3m14-9 10-3m-10 12 10-3"/>'
  ];
  function mensagem(id, texto, erro=false) { $(id).textContent=texto; $(id).dataset.error=String(erro); }
  async function ler(r) { const d=await r.json(); if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Confira os dados e tente novamente.'); return d; }
  function salvarCarrinho() { try { localStorage.setItem(chave,JSON.stringify(carrinho)); } catch {} }
  function linhas() { return produtos.filter(p => Number.isInteger(carrinho[p.id]) && carrinho[p.id]>0 && carrinho[p.id]<=10); }
  function renderCarrinho() {
    const lista=$('#cart-items'); lista.replaceChildren(); let total=0, quantidade=0;
    linhas().forEach(p => {
      const q=carrinho[p.id]; total+=p.preco_centavos*q; quantidade+=q;
      const row=el('div','cart-line'), copy=el('div'); copy.append(el('strong','',p.categoria),el('span','',dinheiro(p.preco_centavos)+' / unidade'));
      const controles=el('div','cart-quantity');
      [-1,1].forEach((delta,i) => {
        if(i)controles.append(el('span','',String(q)));
        const b=el('button','',delta<0?'−':'+'); b.type='button'; b.disabled=enviando || (delta>0&&q>=10);
        b.setAttribute('aria-label',(delta<0?'Diminuir ':'Aumentar ')+p.categoria);
        b.addEventListener('click',()=>{carrinho[p.id]+=delta;if(!carrinho[p.id])delete carrinho[p.id];pedidoPendente=null;salvarCarrinho();renderCarrinho();}); controles.append(b);
      });
      row.append(copy,controles); lista.append(row);
    });
    if(!quantidade)lista.append(el('p','conta-muted','Seu carrinho está vazio. Explore o catálogo para começar.'));
    $('#cart-count').textContent=quantidade; $('#cart-total').textContent=dinheiro(total);
    const cliente=window.ecAuth.estado.usuario?.perfil==='cliente';
    $('#confirmar-pedido').disabled=!cliente||!quantidade||enviando;
    $('#cart-login').hidden=cliente;
    $('#cart-login').textContent=window.ecAuth.estado.usuario?.perfil==='analista'?'Você está como analista. Saia e entre com uma conta de cliente.':'Entre ou crie uma conta de cliente para continuar ↗';
  }
  async function carregarCatalogo() {
    try {
      const d=await ler(await fetch('/api/loja/catalogo',{cache:'no-store'})); produtos=d.produtos;
      carrinho=Object.fromEntries(linhas().map(p=>[p.id,carrinho[p.id]])); salvarCarrinho();
      const grid=$('#catalog-grid'); grid.replaceChildren();
      produtos.forEach((p,i)=>{
        const card=el('article','product-card'), visual=el('div','product-visual');
        visual.style.setProperty('--card-bg',['#e4e9d9','#e3e4d8','#e8dfd1','#dae5de','#e3e3d1','#dfdfcf'][i%6]);
        // SVGs estáticos, simbólicos; nomes e valores da API entram via textContent.
        visual.innerHTML='<svg viewBox="0 0 64 64" aria-hidden="true">'+icones[i%6]+'</svg>';
        visual.append(el('span','','OLIST / '+String(i+1).padStart(2,'0')));
        const copy=el('div','product-copy'), bottom=el('div','product-bottom'), b=el('button','add-cart','+');
        b.type='button'; b.setAttribute('aria-label','Adicionar '+p.categoria+' ao carrinho');
        b.addEventListener('click',()=>{
          if(enviando)return;
          const q=carrinho[p.id]||0; if(q>=10){mensagem('#catalog-message','Limite de 10 unidades por item.');return;}
          carrinho[p.id]=q+1; pedidoPendente=null;salvarCarrinho();renderCarrinho();mensagem('#catalog-message',p.categoria+' adicionado ao carrinho.');
        });
        bottom.append(el('strong','',dinheiro(p.preco_centavos)),b);
        copy.append(el('h3','',p.categoria),el('p','','Produto anonimizado · preço mediano histórico. Ilustração representativa da categoria.'),bottom);card.append(visual,copy);grid.append(card);
      });
      mensagem('#catalog-message',d.observacao);renderCarrinho();
    } catch(e){mensagem('#catalog-message',e.message,true);}
  }
  async function meusPedidos() {
    await window.ecAuth.ready; const container=$('#client-orders');container.replaceChildren();
    if(window.ecAuth.estado.usuario?.perfil!=='cliente') {
      const box=el('div','orders-empty');box.append(el('p','',window.ecAuth.estado.autenticado?'Use uma conta de cliente para criar e acompanhar seus próprios pedidos.':'Seu histórico aparece após entrar na sua conta.'));
      const a=el('a','', 'Acessar minha conta ↗');a.href='/entrar';box.append(a);container.append(box);mensagem('#client-message','');return;
    }
    const dono=window.ecAuth.estado.usuario.id;
    mensagem('#client-message','Consultando seus pedidos…');$('#atualizar-pedidos').disabled=true;
    try {
      const d=await ler(await window.ecFetch('/api/cliente/pedidos'));
      if(window.ecAuth.estado.usuario?.id!==dono)return;
      if(!d.pedidos.length)container.append(el('p','orders-empty','Você ainda não criou pedidos. Comece pelo catálogo acima.'));
      d.pedidos.forEach(p=>{
        const card=el('article','client-order'),top=el('div','order-top'),info=el('div');
        info.append(el('h3','','Pedido #'+p.id.slice(0,8)),el('p','conta-muted',data(p.criado_em)+' · '+p.uf+' · '+dinheiro(p.total_centavos)));
        top.append(info,el('span','order-badge',etapas[p.status]));
        const timeline=el('ol','order-timeline');timeline.setAttribute('aria-label','Etapas do pedido demonstrativo');
        Object.entries(etapas).forEach(([codigo,nome])=>{const evento=p.eventos.find(e=>e.status===codigo),li=el('li',evento?'done':'',nome);li.append(el('small','',evento?data(evento.em):'Aguardando'));timeline.append(li);});
        const prazo = valor => valor ? valor.split('-').reverse().join('/') : 'Ainda não definido pela equipe';
        const promessa=el('div','order-facts');
        promessa.append(el('p','','Prazo prometido: '+prazo(p.prazo_prometido)));
        if(p.prazo_original && p.prazo_original!==p.prazo_prometido)promessa.append(el('p','','Prazo original: '+prazo(p.prazo_original)));
        const historico=el('details','order-history'), lista=el('ol','history-list');
        historico.append(el('summary','','Histórico de etapas e prazos'));
        [...p.eventos].reverse().forEach(evento=>{
          const item=el('li','');item.append(el('strong','',data(evento.em)));
          if(evento.status)item.append(el('p','',etapas[evento.status] || evento.status));
          (evento.alteracoes || []).forEach(m=>item.append(el('p','','Prazo prometido: '+prazo(m.anterior)+' → '+prazo(m.novo))));
          lista.append(item);
        });
        historico.append(lista);
        card.append(top,el('p','conta-muted',p.itens.map(i=>i.quantidade+' × '+i.nome).join(' · ')),promessa,timeline,historico);container.append(card);
      });mensagem('#client-message',d.pedidos.length+' pedido(s) encontrado(s).');
    }catch(e){mensagem('#client-message',e.message,true);}finally{$('#atualizar-pedidos').disabled=false;}
  }
  'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(' ').forEach(uf=>{const op=el('option','',uf);op.value=uf;$('#destino-uf').append(op);});
  $('#destino-uf').addEventListener('change',()=>pedidoPendente=null);
  $('#abrir-carrinho').addEventListener('click',()=>{renderCarrinho();$('#cart-dialog').showModal();});
  $('#fechar-carrinho').addEventListener('click',()=>$('#cart-dialog').close());
  $('#atualizar-pedidos').addEventListener('click',meusPedidos);
  $('#checkout').addEventListener('submit', async e=>{
    e.preventDefault(); if(enviando||!linhas().length)return;
    enviando=true;renderCarrinho();$('#destino-uf').disabled=true;mensagem('#cart-message','Salvando seu pedido…');
    pedidoPendente ||= crypto.randomUUID();
    try {
      await ler(await window.ecFetch('/api/cliente/pedidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({itens:linhas().map(p=>({produto_id:p.id,quantidade:carrinho[p.id]})),uf:$('#destino-uf').value,chave_requisicao:pedidoPendente})}));
      carrinho={};pedidoPendente=null;salvarCarrinho();$('#cart-dialog').close();await meusPedidos();$('#meus-pedidos').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});mensagem('#cart-message','');
    }catch(err){mensagem('#cart-message',err.message,true);}finally{enviando=false;$('#destino-uf').disabled=false;renderCarrinho();}
  });
  document.addEventListener('ec:session',()=>{
    renderCarrinho();
    if(window.ecAuth.estado.usuario?.perfil!=='cliente')$('#client-orders').replaceChildren();
  });
  window.addEventListener('pageshow',e=>{if(e.persisted)meusPedidos();});
  window.addEventListener('pagehide',()=>$('#client-orders').replaceChildren());
  document.addEventListener('ec:expired',()=>{$('#client-orders').replaceChildren();mensagem('#client-message','Sua sessão expirou. Entre novamente.');});
  carregarCatalogo();meusPedidos();
})();
