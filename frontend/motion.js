"use strict";

// Camada visual da V3. Não calcula scores nem altera a fila recebida da API.
(() => {
  const raiz = document.documentElement;
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  if (!gsap || !ScrollTrigger) return; // O script principal mantém a alternativa em CSS.

  gsap.registerPlugin(ScrollTrigger);
  const entradas = new WeakMap();
  const efeitos = new Set();
  let contexto = null;
  let aberturaExecutada = false;
  let ativo = false;
  let atualizarPonteiro = null;
  let restaurarPonteiro = null;
  let atualizarHover = null;

  function limparEfeitos() {
    efeitos.forEach((efeito) => { efeito.progress(1); efeito.kill(); });
    efeitos.clear();
  }

  function efeitoEntrada(alvos, configuracao = {}) {
    if (!ativo || !alvos.length) return;
    const efeito = gsap.fromTo(alvos, { opacity: 0, y: 10 }, {
      opacity: 1, y: 0, duration: 0.4, stagger: 0.025,
      ease: "power2.out", overwrite: true, clearProps: "opacity,transform",
      ...configuracao,
      onComplete: () => efeitos.delete(efeito),
    });
    efeitos.add(efeito);
  }

  function construir() {
    const primeiraAbertura = !aberturaExecutada && window.scrollY < 120;
    aberturaExecutada = true;
    contexto = gsap.context(() => {
      if (primeiraAbertura) {
        gsap.timeline({ defaults: { ease: "power3.out" } })
          .from(".hero-eyebrow", { opacity: 0, y: 14, duration: 0.55 })
          .from(".headline-text", { yPercent: 110, rotation: 3, duration: 0.95, stagger: 0.13 }, 0.1)
          .from(".hero-description, .hero-actions, .hero-caption", { opacity: 0, y: 16, duration: 0.65, stagger: 0.1 }, 0.55)
          .from(".parcel-art", { opacity: 0, scale: 0.86, rotation: -7, duration: 1.1, transformOrigin: "50% 50%" }, 0.15)
          .from(".visual-coordinate, .visual-label, .visual-index", { opacity: 0, y: 12, duration: 0.65, stagger: 0.08 }, 0.7);
      }

      // Movimento discreto da embalagem; pausa quando a abertura sai da tela.
      const flutuacao = gsap.timeline({ repeat: -1, yoyo: true, paused: true });
      flutuacao.fromTo(".floating-parcel", { y: -14 }, { y: -29, duration: 2.4, ease: "sine.inOut" }, 0)
        .fromTo(".parcel-shadow", { scale: 1, opacity: 0.8 }, { scale: 0.88, opacity: 0.5, duration: 2.4, transformOrigin: "50% 50%", ease: "sine.inOut" }, 0);
      const rota = gsap.to(".route-line", { strokeDashoffset: -140, duration: 7, ease: "none", repeat: -1, paused: true });
      ScrollTrigger.create({ trigger: ".hero", start: "top bottom", end: "bottom top", onToggle: ({ isActive }) => {
        const tocar = isActive && !document.hidden;
        flutuacao.paused(!tocar); rota.paused(!tocar);
      } });
      if (document.querySelector(".hero").getBoundingClientRect().bottom > 0 && !document.hidden) {
        flutuacao.play(); rota.play();
      }

      // Repete a entrada nos dois sentidos; reinicia só depois de sair da tela.
      document.querySelectorAll(".reveal").forEach((bloco) => {
        const irmaos = [...bloco.parentElement.children].filter((item) => item.classList.contains("reveal"));
        const atraso = ["metrics-grid", "process-grid"].some((classe) => bloco.parentElement.classList.contains(classe))
          ? irmaos.indexOf(bloco) * 0.12 : 0;
        const entrada = gsap.fromTo(bloco, { opacity: 0, y: 44 }, {
          opacity: 1, y: 0, duration: 1.2, delay: atraso, ease: "power2.out",
          clearProps: "opacity,transform", paused: true,
        });
        entradas.set(bloco, entrada);
        const mostrar = () => {
          if (bloco.contains(document.activeElement)) entrada.progress(1).pause();
          else entrada.restart(true);
        };
        const prepararEntrada = () => {
          // Um controle em foco nunca fica invisível durante a navegação por teclado.
          if (!bloco.contains(document.activeElement)) entrada.pause(0);
        };
        ScrollTrigger.create({
          trigger: bloco, start: "top bottom", end: "bottom top",
          onEnter: mostrar, onEnterBack: mostrar,
          onLeave: prepararEntrada, onLeaveBack: prepararEntrada,
        });
        if (bloco.contains(document.activeElement)) entrada.progress(1).pause();
      });

      gsap.fromTo(".reading-progress > span", { scaleX: 0 }, {
        scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: true },
      });
      gsap.fromTo(".flow-ribbon-track", { x: 40 }, {
        x: -180, ease: "none", scrollTrigger: { trigger: ".flow-ribbon", start: "top bottom", end: "bottom top", scrub: 0.8 },
      });
      gsap.fromTo(".journey-fill", { scaleX: 0 }, {
        scaleX: 1, ease: "none", scrollTrigger: { trigger: ".process-grid", start: "top 85%", end: "bottom 45%", scrub: 0.5 },
      });
      gsap.from(".journey-node", {
        backgroundColor: "#f3f4ed", borderColor: "#c6d0ba", stagger: 0.18, duration: 0.35,
        scrollTrigger: {
          trigger: ".process-grid", start: "top bottom", end: "bottom top",
          toggleActions: "restart reset restart reset",
        },
      });
      gsap.fromTo(".hero-aura", { xPercent: 0, scale: 1 }, {
        xPercent: 12, scale: 1.18, ease: "none",
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 },
      });

      // Só desloca a arte, mantendo botões e alvos de clique no lugar.
      const moverX = gsap.quickTo(".parcel-scene", "rotationY", { duration: 0.7, ease: "power2.out" });
      const moverY = gsap.quickTo(".parcel-scene", "rotationX", { duration: 0.7, ease: "power2.out" });
      gsap.set(".parcel-scene", { transformPerspective: 900 });
      atualizarPonteiro = (x, y) => { moverX(x * 8); moverY(-y * 6); };
      restaurarPonteiro = () => { moverX(0); moverY(0); };
    });
    atualizarHover = (alvo, entrou) => {
      if (!ativo) return;
      const seta = alvo.querySelector(".button-arrow, .launcher-arrow");
      if (!seta) return;
      gsap.to(seta, { x: entrou ? 4 : 0, y: entrou ? -4 : 0, duration: 0.25, overwrite: true });
    };
    ScrollTrigger.refresh();
  }

  function setPaused(pausado) {
    ativo = false;
    atualizarPonteiro = restaurarPonteiro = atualizarHover = null;
    limparEfeitos();
    contexto?.revert();
    contexto = null;
    gsap.killTweensOf(".button-arrow, .launcher-arrow");
    gsap.set(".button-arrow, .launcher-arrow", { clearProps: "transform" });
    raiz.classList.remove("motion-enhanced");
    if (pausado) return;
    try {
      ativo = true;
      raiz.classList.add("motion-enhanced");
      construir();
    } catch (erro) {
      contexto?.revert();
      raiz.classList.remove("motion-enhanced");
      gsap.set(".reveal, .headline-text", { clearProps: "opacity,transform" });
      ativo = false;
      console.warn("Movimento avançado indisponível; conteúdo permanece acessível.", erro);
    }
  }

  document.addEventListener("focusin", (evento) => {
    if (!ativo) return;
    const bloco = evento.target.closest(".reveal");
    if (!bloco) return;
    entradas.get(bloco)?.progress(1).pause();
  });
  const visual = document.querySelector(".hero-visual");
  const ponteiro = window.matchMedia("(hover: hover) and (pointer: fine)");
  visual?.addEventListener("pointermove", (evento) => {
    if (!ativo || !ponteiro.matches) return;
    const r = visual.getBoundingClientRect();
    atualizarPonteiro?.((evento.clientX - r.left) / r.width - 0.5, (evento.clientY - r.top) / r.height - 0.5);
  });
  visual?.addEventListener("pointerleave", () => restaurarPonteiro?.());
  document.querySelectorAll(".button, .assistant-launcher").forEach((botao) => {
    botao.addEventListener("pointerenter", () => { if (ponteiro.matches && !botao.disabled) atualizarHover?.(botao, true); });
    botao.addEventListener("pointerleave", () => atualizarHover?.(botao, false));
  });
  document.addEventListener("visibilitychange", () => {
    if (contexto) setPaused(raiz.classList.contains("motion-paused") || document.hidden);
    else if (!document.hidden && !raiz.classList.contains("motion-paused")) setPaused(false);
  });
  document.addEventListener("ec:table-rendered", () => {
    if (!ativo) return;
    limparEfeitos();
    efeitoEntrada([...document.querySelectorAll("#pedidos tr")], { y: 0, duration: 0.3, stagger: 0.012 });
    ScrollTrigger.refresh();
  });
  document.addEventListener("ec:data-ready", () => {
    efeitoEntrada([...document.querySelectorAll(".metric strong")]);
    efeitoEntrada([...document.querySelectorAll(".distribution-row")], { stagger: 0.07 });
  });
  document.addEventListener("ec:assistant-open", () => {
    efeitoEntrada([...document.querySelectorAll(".assistant-status, .assistant-intro, .assistant-context, .assistant-suggestions")], { stagger: 0.06 });
  });
  window.addEventListener("load", () => { if (ativo) ScrollTrigger.refresh(); }, { once: true });
  window.EntregaCertaMotion = { setPaused };
})();
