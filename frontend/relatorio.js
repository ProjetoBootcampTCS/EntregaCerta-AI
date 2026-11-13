/* Exportação exclusiva do dashboard do analista; indicadores ficam no servidor. */
(() => {
  const botao=document.getElementById('gerar-relatorio-pdf');
  if (!botao) return;
  const rotulo=document.getElementById('relatorio-button-label');
  const status=document.getElementById('relatorio-status');
  let analiseId=null, carregando=false, gerando=false, controlador=null;
  function atualizar() {
    botao.disabled=gerando || carregando || !analiseId || window.ecAuth?.estado.usuario?.perfil!=='analista';
    botao.setAttribute('aria-busy',String(gerando));
    rotulo.textContent=gerando?'Gerando PDF…':'Gerar relatório em PDF';
  }
  document.addEventListener('ec:analise',e=>{
    const mudou=analiseId!==e.detail.analiseId;
    analiseId=e.detail.analiseId;carregando=e.detail.carregando;
    if (mudou && !gerando && analiseId){
      status.textContent='PDF disponível para esta análise por até 30 minutos. Inclui a fila completa, independentemente dos filtros.';
      delete status.dataset.state;
    }
    atualizar();
  });
  document.addEventListener('ec:session',()=>{
    if(window.ecAuth?.estado.usuario?.perfil!=='analista'){analiseId=null;controlador?.abort();}
    atualizar();
  });
  botao.addEventListener('click',async()=>{
    if(botao.disabled)return;
    const id=analiseId, usuario=window.ecAuth.estado.usuario.id;
    gerando=true;controlador=new AbortController();atualizar();
    status.dataset.state='loading';
    status.textContent='Preparando indicadores, gráficos e resumo da GenAI. O download começará automaticamente; pode levar até dois minutos.';
    const timeout=setTimeout(()=>controlador?.abort(),120000);
    try {
      const r=await window.ecFetch('/api/analista/relatorio-pdf',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({analise_id:id}),signal:controlador.signal
      });
      if(!r.ok){
        const erro=await r.json().catch(()=>({}));
        if([404,410].includes(r.status) && analiseId===id)analiseId=null;
        throw new Error(typeof erro.detail==='string'?erro.detail:'Não foi possível gerar o relatório. Tente novamente.');
      }
      if(!r.headers.get('Content-Type')?.includes('application/pdf'))throw new Error('O servidor não retornou um PDF válido. Tente novamente.');
      const arquivo=await r.blob();
      if(window.ecAuth.estado.usuario?.id!==usuario)return;
      const url=URL.createObjectURL(arquivo),a=document.createElement('a');
      a.href=url;a.download='entregacerta-relatorio.pdf';document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),60000);
      status.dataset.state=r.headers.get('X-Resumo-GenAI')==='incluido'?'success':'warning';
      status.textContent=r.headers.get('X-Resumo-GenAI')==='incluido'
        ? 'Download iniciado: PDF com indicadores, gráficos e resumo gerado pela IA. Revise a interpretação antes de usar.'
        : 'Download iniciado: indicadores e gráficos disponíveis. A GenAI ficou indisponível; o PDF inclui um resumo automático identificado.';
      if(analiseId!==id)status.textContent+=' O documento corresponde à análise selecionada ao clicar, anterior à atualização do painel.';
    }catch(e){
      status.dataset.state='error';
      status.textContent=e.name==='AbortError'?'A geração foi interrompida ou excedeu o tempo de espera. Você pode tentar novamente.':e.message;
    }finally{
      clearTimeout(timeout);controlador=null;gerando=false;atualizar();
    }
  });
  atualizar();
})();
