/* Sessão em cookie HttpOnly; identidade e CSRF ficam somente em memória. */
(() => {
  const privado = document.documentElement.hasAttribute('data-protected');
  const destino = location.pathname === '/pedidos' ? 'pedidos' : 'dashboard';
  const estado = { autenticado: false };
  let verificacao;
  function limparCache() {
    try { sessionStorage.removeItem('entregacerta-dashboard-analise-v1'); } catch { /* Armazenamento bloqueado. */ }
  }
  function limpar() {
    limparCache();
    document.documentElement.classList.remove('session-ready');
  }
  function aplicar(dados) {
    Object.keys(estado).forEach(k => delete estado[k]); Object.assign(estado, dados);
    document.querySelectorAll('[data-user-name]').forEach(el => el.textContent = dados.usuario?.nome || 'Visitante');
    document.querySelectorAll('[data-logout]').forEach(el => el.hidden = !dados.autenticado);
    document.querySelectorAll('[data-login-link]').forEach(el => el.hidden = !!dados.autenticado);
    document.querySelectorAll('[data-account-link]').forEach(el => {
      el.hidden = !dados.autenticado;
      el.href = dados.usuario?.perfil === 'analista' ? '/dashboard' : '/cliente#meus-pedidos';
      el.textContent = dados.usuario?.perfil === 'analista' ? 'Meu dashboard' : 'Meus pedidos';
    });
    if (privado) {
      if (dados.usuario?.perfil !== 'analista') {
        limpar(); location.replace('/entrar?destino=' + destino); return;
      }
      document.documentElement.classList.add('session-ready');
    }
    document.dispatchEvent(new CustomEvent('ec:session', {detail: dados}));
  }
  async function conferir() {
    if (verificacao) return verificacao;
    verificacao = (async () => {
      const resposta = await fetch('/api/auth/sessao', {cache: 'no-store', credentials: 'same-origin'});
      if (!resposta.ok) throw new Error('Não foi possível verificar sua sessão. Confira o servidor.');
      aplicar(await resposta.json()); return estado;
    })();
    try { return await verificacao; } finally { verificacao = null; }
  }
  window.ecAuth = {estado, conferir, aplicar};
  // Limpa o cache de resultados criado pelas versões anteriores do dashboard.
  limparCache();
  window.ecAuth.ready = conferir().catch(erro => {
    if (privado) { limpar(); location.replace('/entrar?destino=' + destino); }
    return {autenticado: false, erro: erro.message};
  });
  window.ecFetch = async (url, opcoes = {}) => {
    await window.ecAuth.ready;
    const headers = new Headers(opcoes.headers);
    if (!['GET','HEAD','OPTIONS'].includes((opcoes.method || 'GET').toUpperCase()) && estado.csrf) {
      headers.set('X-CSRF-Token', estado.csrf);
    }
    const resposta = await fetch(url, {...opcoes, headers, credentials: 'same-origin', cache: 'no-store'});
    if (resposta.status === 401) {
      aplicar({autenticado: false});
      if (!privado) document.dispatchEvent(new Event('ec:expired'));
    }
    return resposta;
  };
  document.querySelectorAll('[data-logout]').forEach(botao => botao.addEventListener('click', async () => {
    botao.disabled = true;
    try {
      const r = await window.ecFetch('/api/auth/sair', {method: 'POST'});
      if (!r.ok && r.status !== 401) throw new Error('Não foi possível sair. Tente novamente.');
      limpar();
      try { localStorage.setItem('entregacerta-logout', String(Date.now())); } catch { /* A sessão já foi revogada no servidor. */ }
      location.assign('/entrar');
    } catch (e) { alert(e.message); botao.disabled = false; }
  }));
  window.addEventListener('storage', e => {
    if (e.key === 'entregacerta-logout') { limpar(); location.reload(); }
  });
  window.addEventListener('pagehide', () => { if (privado) limpar(); });
  window.addEventListener('pageshow', e => { if (e.persisted) conferir().catch(() => location.reload()); });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') conferir().catch(() => { if (privado) location.replace('/entrar'); });
  });
  if (privado) setInterval(() => conferir().catch(() => location.replace('/entrar')), 60000);
})();
