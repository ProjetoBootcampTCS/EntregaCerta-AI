/* Operação da loja demonstrativa. Alterações são persistidas e auditadas no servidor. */
(() => {
  const lista = document.querySelector('#demo-orders');
  const mensagem = document.querySelector('#demo-message');
  const consultar = document.querySelector('#demo-refresh');
  if (!lista) return;
  const etapas = {recebido:'Recebido', em_preparacao:'Em preparação', despachado:'Despachado', entregue:'Entregue'};
  const seguintes = {recebido:'em_preparacao', em_preparacao:'despachado', despachado:'entregue'};
  const dia = valor => valor ? valor.split('-').reverse().join('/') : 'Não definido';
  const horario = valor => new Date(valor).toLocaleString('pt-BR', {dateStyle:'short', timeStyle:'short'});
  const el = (tag, classe, texto) => { const n=document.createElement(tag); n.className=classe; if(texto !== undefined)n.textContent=texto; return n; };
  let responsaveis = [], salvando = false;
  async function ler(r) {
    const d = await r.json();
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Confira os campos antes de salvar.');
    return d;
  }
  function campo(formulario, texto, controle) {
    const label = el('label', 'operation-field', texto);
    label.append(controle); formulario.append(label); return controle;
  }
  function valor(campo, v) {
    if (campo === 'prazo_prometido') return dia(v);
    if (campo === 'status') return etapas[v] || v;
    return v || 'Não atribuído';
  }
  function historico(p) {
    const detalhes=el('details','order-history'), resumo=el('summary','','Histórico de alterações · '+p.eventos.length);
    const eventos=el('ol','history-list');
    [...p.eventos].reverse().forEach(e => {
      const item=el('li','');
      item.append(el('strong','',horario(e.em)+' · '+(e.autor?.nome || 'Autor não registrado')));
      if (e.alteracoes?.length) e.alteracoes.forEach(m => {
        const campo={prazo_prometido:'Prazo prometido',responsavel:'Responsável',status:'Etapa'}[m.campo] || m.campo;
        item.append(el('p','',campo+': '+valor(m.campo,m.anterior)+' → '+valor(m.campo,m.novo)));
      });
      else item.append(el('p','',e.tipo==='criacao' ? 'Pedido criado' : 'Etapa registrada: '+(etapas[e.status] || e.status)));
      if(e.motivo) item.append(el('p','history-reason','Justificativa interna: '+e.motivo));
      eventos.append(item);
    });
    detalhes.append(resumo,eventos); return detalhes;
  }
  function montar(p) {
    const card=el('article','operation-card'); card.dataset.orderId=p.id;
    const cabecalho=el('div','order-top'), info=el('div','');
    info.append(el('h3','','Pedido #'+p.id.slice(0,8)),el('p','conta-muted',p.cliente+' · '+p.uf+' · '+(p.total_centavos/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})));
    cabecalho.append(info,el('span','order-badge',etapas[p.status]));
    const dados=el('div','order-facts');
    dados.append(el('p','','Prazo prometido: '+dia(p.prazo_prometido)),el('p','','Responsável: '+(p.responsavel || 'Não atribuído')));
    if(p.prazo_original && p.prazo_original!==p.prazo_prometido)dados.append(el('p','','Prazo original: '+dia(p.prazo_original)));
    const form=el('form','operation-form');
    form.setAttribute('aria-label','Editar pedido '+p.id.slice(0,8));
    const prazo=campo(form,'Prazo prometido',el('input','')); prazo.type='date'; prazo.name='prazo_prometido'; prazo.value=p.prazo_prometido||'';
    // Datas são dias civis, não timestamps de meia-noite convertidos para o fuso local.
    prazo.min = new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo'}).format(new Date(p.criado_em));
    const responsavel=campo(form,'Responsável',el('select','')); responsavel.name='responsavel_id';
    responsavel.add(new Option('Não atribuído',''));
    responsaveis.forEach(r=>responsavel.add(new Option(r.nome,r.id)));
    if(p.responsavel_id && !responsaveis.some(r=>r.id===p.responsavel_id))responsavel.add(new Option((p.responsavel||'Analista')+' (inativo)',p.responsavel_id));
    responsavel.value=p.responsavel_id||'';
    const status=campo(form,'Etapa do pedido',el('select','')); status.name='status';
    status.add(new Option(etapas[p.status],p.status));
    if(seguintes[p.status])status.add(new Option('Avançar para '+etapas[seguintes[p.status]],seguintes[p.status]));
    const motivo=campo(form,'Justificativa (obrigatória ao revisar o prazo)',el('textarea','')); motivo.name='motivo'; motivo.maxLength=500; motivo.rows=2;
    motivo.placeholder='Registre o motivo da mudança para a equipe. Não incluir dados sensíveis.';
    motivo.parentElement.classList.add('operation-wide');
    prazo.addEventListener('input',()=>{motivo.required=!!p.prazo_prometido && prazo.value!==p.prazo_prometido;});
    const rodape=el('div','operation-actions operation-wide'), aviso=el('p','form-message',''); aviso.setAttribute('role','status');
    const salvar=el('button','button button-dark button-small','Salvar alterações'); salvar.type='submit';
    rodape.append(aviso,salvar); form.append(rodape);
    form.addEventListener('submit',async e=>{
      e.preventDefault(); if(salvando)return;
      const envio={versao:p.versao, motivo:motivo.value.trim()};
      if(prazo.value!==(p.prazo_prometido||''))envio.prazo_prometido=prazo.value||null;
      if(responsavel.value!==(p.responsavel_id||''))envio.responsavel_id=responsavel.value||null;
      if(status.value!==p.status)envio.status=status.value;
      if(Object.keys(envio).length===2){aviso.textContent='Nenhuma alteração para salvar.';return;}
      salvando=true; consultar.disabled=true; salvar.disabled=true; aviso.textContent='Salvando alterações…';
      try {
        const atualizado=await ler(await window.ecFetch('/api/analista/pedidos-loja/'+p.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(envio)}));
        const novo=montar(atualizado); card.replaceWith(novo);
        novo.querySelector('.form-message').textContent='Alterações salvas e registradas no histórico.';
        novo.querySelector('button[type="submit"]').focus({preventScroll:true});
      } catch(erro) { aviso.textContent=erro.message; aviso.dataset.error='true'; }
      finally {salvando=false;consultar.disabled=false;salvar.disabled=false;}
    });
    card.append(cabecalho,dados,form,historico(p)); return card;
  }
  async function carregar() {
    if(salvando)return;
    consultar.disabled=true;mensagem.textContent='Consultando pedidos e responsáveis…';
    try {
      const [dados,equipe]=await Promise.all([
        window.ecFetch('/api/analista/pedidos-loja').then(ler),
        window.ecFetch('/api/analista/responsaveis').then(ler)
      ]);
      responsaveis=equipe.responsaveis;
      lista.replaceChildren(...dados.pedidos.map(montar));
      mensagem.textContent=dados.pedidos.length ? dados.pedidos.length+' pedido(s). Últimos 100 · alterações de prazo mantêm a promessa original no histórico.' : 'Nenhum pedido criado na loja demonstrativa.';
    }catch(erro){mensagem.textContent=erro.message;}finally{consultar.disabled=false;}
  }
  consultar.addEventListener('click',carregar);
})();
