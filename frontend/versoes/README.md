# Versões da interface

Atualizado em 10/11/2026. A versão ativa após esta atualização é a **V3**.

| Pacote | Conteúdo |
| --- | --- |
| `V1.zip` | Cópia exata do HTML, CSS e JavaScript anteriores: painel grafite/verde-lima, fila, filtros, detalhes e CSV. |
| `V2.zip` | HTML, CSS, JavaScript e logo SVG: painel lateral da futura GenAI, botão flutuante, entrada dos blocos na rolagem e nova identidade visual. |
| `V3.zip` | Interface da V2 com GSAP e ScrollTrigger locais: abertura em sequência, animações na rolagem, faixa de texto, progresso de leitura e percurso visual do processo. Inclui `motion.js` e `vendor/gsap/`. |

A GenAI ainda não está conectada. O painel permite preparar e copiar um rascunho e consultar um resumo determinístico da análise carregada. Nenhuma pergunta é enviada e nenhuma resposta de IA é simulada. O rascunho dura somente enquanto esta página permanece aberta.

Na V3, `motion.js` cuida exclusivamente das animações. `script.js` mantém consulta, filtros, paginação, detalhes e exportação. Os valores exibidos vêm da API; as animações não geram scores nem modificam a fila. Há pausa de movimento no cabeçalho e no rodapé, com preferência salva no navegador e respeito a `prefers-reduced-motion`.

Ajuste da V3 em 10/11/2026: os blocos repetem a animação a cada reentrada na tela, ao descer e ao subir. A animação se prepara novamente quando o bloco sai da área visível; controles em foco permanecem legíveis. A alternativa com IntersectionObserver também mantém a observação para repetir as entradas. O pacote `V3.zip` inclui esse ajuste. Os eventos de entrada e saída seguem a [documentação do ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/).

Ritmo de entrada atualizado: duração de 1,2 segundo (antes 0,7), deslocamento de 44 px (antes 28) e intervalo de 0,12 segundo entre cards no GSAP. A desaceleração usa `power2.out`, tornando a progressão mais perceptível. A alternativa CSS também usa 1,2 segundo e 44 px. A repetição, a pausa e o respeito ao movimento reduzido permanecem ativos.

GSAP e ScrollTrigger 3.15.1 estão em `frontend/vendor/gsap/`, obtidos do pacote oficial do npm com integridade SHA-512 verificada. Os avisos originais, a declaração de licença e sua fonte foram preservados nessa pasta. Não é necessário acessar uma CDN para animar a página. Caso as bibliotecas não carreguem, a interface mantém a alternativa anterior em CSS e IntersectionObserver.

## Voltar para uma versão

No PowerShell, a partir da raiz `EntregaCertaAI`, execute **um** dos comandos abaixo. Eles substituem somente os arquivos da interface contidos no pacote. Preserve suas edições posteriores antes de restaurar.

Voltar à V1:

```powershell
Expand-Archive -LiteralPath .\frontend\versoes\V1.zip -DestinationPath .\frontend -Force
```

Voltar à V2:

```powershell
Expand-Archive -LiteralPath .\frontend\versoes\V2.zip -DestinationPath .\frontend -Force
```

Retornar à V3:

```powershell
Expand-Archive -LiteralPath .\frontend\versoes\V3.zip -DestinationPath .\frontend -Force
```

Com o PostgreSQL disponível e a API local em execução, abra `http://127.0.0.1:8000/` e pressione **Ctrl + F5**. Para iniciar a API na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

Arquivos extras de uma versão mais nova podem permanecer após a restauração: o HTML antigo não os carrega. Não é necessário apagar `motion.js`, `vendor/` ou `logo.svg` para voltar à V1/V2.

Os pacotes são retratos fixos destas versões. Backend, modelos, notebooks e dados não fazem parte deles. O arquivo independente `entregacerta_heatmap_novo.html` foi preservado.

## Conferências da V2

- JavaScript passou em `node --check`; IDs do HTML e referências do script conferidos; logo validado como SVG/XML.
- Navegador em desktop e largura de 390 px: abertura/fechamento, Escape, ciclo de foco com Tab, rascunho, cópia e envio desabilitado conferidos.
- Cards ocultos antes da entrada na tela e visíveis após rolagem; pausa de movimento mantém o conteúdo legível.
- Consulta real retornou 24.667 pedidos e fila de 2.466; o contexto do assistente acompanhou a conclusão da consulta. Nenhum erro ou aviso foi registrado no console dessa verificação.
- V1 comparada byte a byte com os três arquivos anteriores antes da edição. V2 comparada byte a byte com os quatro arquivos ativos; ambos os ZIPs passaram na verificação de integridade.

## Conferências da V3

- Sintaxe de `script.js` e `motion.js` conferida com `node --check`; referências locais e IDs do HTML conferidos.
- Navegador em 1280 px e 390 px: layout sem transbordamento horizontal da página; painel lateral e sugestões de rascunho funcionando. Escape fechou o assistente e devolveu o foco ao botão de abertura.
- Pausa manual tornou os blocos legíveis e interrompeu a camada GSAP. Cards do processo passaram de ocultos para visíveis com a rolagem, com progresso na linha do processo. A preferência do sistema está implementada, mas não foi alterada no computador para este teste.
- Consulta real via interface retornou 24.667 pedidos, fila de 2.466 e maior score 0,9884. Busca por identificador, ordenação crescente, paginação e detalhes conferidos. O contexto do assistente acompanhou os resultados reais.
- CSV baixado pela interface: 2.466 identificadores únicos, quatro colunas, scores na ordenação escolhida e todos com prioridade 1.
- Indisponibilidade do banco exercitada: a página informou o timeout e liberou nova tentativa. Após iniciar o contêiner existente, a consulta funcionou. Nenhum resultado fictício foi inserido.
- Nenhum erro ou aviso de JavaScript no fluxo bem-sucedido observado. A alternativa sem GSAP foi revisada no código, mas não foi exercitada removendo as bibliotecas no navegador.
- V1 e V2 preservadas; V3 empacotada com comparação byte a byte dos arquivos ativos e verificação de integridade ZIP. Backend, notebooks e artefatos de ML não foram alterados nesta versão.
- Repetição conferida após o ajuste: indicadores visíveis com opacidade 1, novamente preparados com opacidade 0 fora da tela e animando ao retornar na rolagem para cima e para baixo. Pausa manual manteve todos os blocos legíveis.
