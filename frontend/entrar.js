(() => {
  let modo = 'entrar';
  const form = document.querySelector('#login-form'), msg = document.querySelector('#login-message');
  const senha = document.querySelector('#senha'), submit = document.querySelector('#login-submit');
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => {
    modo = b.dataset.mode;
    document.querySelectorAll('[data-mode]').forEach(el => el.setAttribute('aria-pressed', String(el === b)));
    document.querySelector('#campo-nome').hidden = modo !== 'cadastrar';
    document.querySelector('#nome').required = modo === 'cadastrar';
    document.querySelector('#senha-ajuda').hidden = modo !== 'cadastrar';
    senha.minLength = modo === 'cadastrar' ? 12 : 1;
    senha.autocomplete = modo === 'cadastrar' ? 'new-password' : 'current-password';
    submit.textContent = modo === 'cadastrar' ? 'Criar minha conta ↗' : 'Entrar na minha conta ↗';
    msg.textContent = '';
  }));
  document.querySelector('#ver-senha').addEventListener('click', e => {
    const mostrar = senha.type === 'password'; senha.type = mostrar ? 'text' : 'password';
    e.target.textContent = mostrar ? 'Ocultar' : 'Mostrar'; e.target.setAttribute('aria-pressed', String(mostrar));
  });
  function destino(usuario) {
    if (usuario.perfil !== 'analista') return '/cliente#meus-pedidos';
    return new URLSearchParams(location.search).get('destino') === 'pedidos' ? '/pedidos' : '/dashboard';
  }
  window.ecAuth.ready.then(s => {
    if (s.autenticado) {
      document.querySelector('#login-area').hidden = true;
      document.querySelector('#conta-atual').hidden = false;
      document.querySelector('#perfil-atual').textContent = s.usuario.perfil === 'cliente' ? 'Perfil cliente. O dashboard é exclusivo para analistas. Para usar outra conta, saia primeiro.' : 'Perfil analista. Seu dashboard está disponível.';
    } else if (s.erro) { msg.textContent = s.erro; msg.dataset.error = 'true'; }
  });
  form.addEventListener('submit', async e => {
    e.preventDefault(); submit.disabled = true; msg.dataset.error = 'false'; msg.textContent = 'Verificando…';
    const dados = {email: form.email.value, senha: senha.value};
    if (modo === 'cadastrar') dados.nome = form.nome.value;
    try {
      const r = await window.ecFetch('/api/auth/' + modo, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(dados)});
      const resposta = await r.json();
      if (!r.ok) throw new Error(typeof resposta.detail === 'string' ? resposta.detail : 'Confira os campos. A senha do cadastro deve ter pelo menos 12 caracteres.');
      senha.value = ''; window.ecAuth.aplicar(resposta); location.assign(destino(resposta.usuario));
    } catch (err) { msg.textContent = err.message; msg.dataset.error = 'true'; }
    finally { submit.disabled = false; }
  });
})();
