# Versões da interface

Registro de 09/11/2026. A versão ativa após esta atualização é a **V2**.

| Pacote | Conteúdo |
| --- | --- |
| `V1.zip` | Cópia exata do HTML, CSS e JavaScript anteriores: painel grafite/verde-lima, fila, filtros, detalhes e CSV. |
| `V2.zip` | HTML, CSS, JavaScript e logo SVG: painel lateral da futura GenAI, botão flutuante, entrada dos blocos na rolagem e nova identidade visual. |

A GenAI da V2 ainda não está conectada. O painel permite preparar e copiar um rascunho e consultar um resumo determinístico da análise carregada. Nenhuma pergunta é enviada e nenhuma resposta de IA é simulada. O rascunho dura somente enquanto esta página permanece aberta.

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

Com a API local em execução, abra `http://127.0.0.1:8000/` e pressione **Ctrl + F5**. A V1 não usa o arquivo `logo.svg` que pode permanecer na pasta após uma restauração; isso não altera sua aparência.

Os pacotes são retratos fixos destas versões. Backend, modelos, notebooks e dados não fazem parte deles. O arquivo independente `entregacerta_heatmap_novo.html` foi preservado.

## Navegação em duas páginas — 12/11/2026

Os arquivos ativos agora usam `/` para o Início e `/dashboard` para o painel do analista.
A apresentação e a animação da caixa ficam em `index.html`; `dashboard.html` reúne
menu lateral, indicadores, fila, filtros, detalhes, exportação e assistente.
`dashboard.css` complementa os estilos compartilhados de `style.css`.
A nova rota em `src/api.py` apenas serve o HTML; as APIs de dados e GenAI continuam as mesmas.

O painel guarda o último resultado e os filtros em `sessionStorage`, somente nesta aba.
Ao restaurar, informa a data original e mostra “Resultado da sessão”; não faz uma
consulta automática. “Atualizar análise” consulta novamente a API. Os links de retorno
`/#inicio` e `/#como-funciona` entram no conteúdo sem repetir a animação.
Reinicie a API se estiver sem `--reload` e atualize o navegador com Ctrl + F5.
Esta atualização não modifica os ZIPs V1/V2 acima.

Validação: rotas `/`, `/dashboard` e CSS responderam HTTP 200 no TestClient da API.
No navegador, a fila foi exercitada com `Dados/previsoes_demo_validacao.csv`
(24.667 previsões reais salvas, 2.466 priorizadas), interceptando apenas a resposta
HTTP durante o teste. Conferidos contagens, distribuição, busca, paginação, detalhes,
CSV, restauração, navegação, menu móvel, teclado e movimento reduzido.
Indisponibilidade das APIs e cache inválido foram simulados como testes técnicos.
Essas verificações não executaram novo treinamento ou consulta ao PostgreSQL.

## Página Pedidos — 12/11/2026

A rota `/pedidos` mantém o menu e a identidade do Dashboard. Consulta todo o lote
histórico de validação, com busca por ID, filtros de fila, UF de destino, categoria,
data de aprovação e score. Há ordenação, paginação de 25/50/100 registros e detalhes
com valores, pagamento e logística disponíveis. Filtros não recalculam a prioridade;
“fora da fila” não significa entrega no prazo. Campos ausentes são identificados.

Arquivos próprios: `frontend/pedidos.html`, `pedidos.css`, `pedidos.js` e
`src/pedidos_web.py`; as rotas estão em `src/api.py`. A API executa a inferência
com o modelo salvo e guarda um lote em memória por processo. “Atualizar lote”
consulta novamente o PostgreSQL. Somente filtros ficam no `sessionStorage` da aba.
A GenAI continua usando o resumo geral da fila, não os detalhes ou filtros de Pedidos.

A transição entre páginas usa [View Transitions entre documentos](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@view-transition),
com links e histórico nativos. Pausa de animações e movimento reduzido são respeitados.
Em navegadores sem suporte, a navegação continua funcionando sem essa transição.
A caixa animada permanece somente no Início. Reinicie a API sem `--reload` e use Ctrl+F5.

Verificações executadas: cinco testes em `tests/test_pedidos_web.py` (fixtures
artificiais exclusivamente técnicas), sintaxe JS/Python, IDs/links e UTF-8.
Comando: `.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_pedidos_web.py -v`.
Edge: busca, filtros, detalhes/cópia, paginação, sessão, vazio/erro, navegação/Voltar,
menu/teclado, redução de movimento e larguras 320/390/768/1440 px; sem erros JS ao final.
O teste visual serviu 24.667 registros reais do snapshot PostgreSQL junto dos scores
históricos salvos. A fonte foi substituída somente no servidor temporário de teste;
a aplicação não faz fallback silencioso para CSV.

Limitação: a conexão direta ao PostgreSQL local na porta 5433 expirou nesta conferência.
A rota foi também exercitada com inferência atual sobre o snapshot real. Os artefatos
atuais não reproduzem o CSV antigo `previsoes_demo_validacao.csv`: diferença máxima
de score de aproximadamente 0,2869004 e 472 prioridades diferentes, tanto usando o
snapshot quanto o CSV de entradas da demonstração. Isso não é métrica de desempenho;
registra apenas a divergência entre artefatos atuais e resultados históricos salvos.
Nenhum treinamento ou alteração dos modelos foi realizado nesta atualização visual.

## Conferências da V2

- JavaScript passou em `node --check`; IDs do HTML e referências do script conferidos; logo validado como SVG/XML.
- Navegador em desktop e largura de 390 px: abertura/fechamento, Escape, ciclo de foco com Tab, rascunho, cópia e envio desabilitado conferidos.
- Cards ocultos antes da entrada na tela e visíveis após rolagem; pausa de movimento mantém o conteúdo legível.
- Consulta real retornou 24.667 pedidos e fila de 2.466; o contexto do assistente acompanhou a conclusão da consulta. Nenhum erro ou aviso foi registrado no console dessa verificação.
- V1 comparada byte a byte com os três arquivos anteriores antes da edição. V2 comparada byte a byte com os quatro arquivos ativos; ambos os ZIPs passaram na verificação de integridade.

## Operação da loja e acesso ao assistente — 13/11/2026

Os pedidos demonstrativos da loja agora têm prazo prometido (dia civil), primeiro
prazo preservado, responsável escolhido entre analistas ativos e histórico com
momento, autor, valores anteriores/novos e justificativa. Revisar um prazo exige
justificativa. O cliente vê as etapas e os prazos do próprio pedido, sem nomes da
equipe ou notas internas. Pedidos antigos continuam sem prazo e responsável até
preenchimento explícito; autores antigos ausentes não são reconstruídos.

No Dashboard, consulte **Pedidos da área do cliente**, edite os campos e salve.
O campo `versao` evita sobrescrever uma edição feita por outro analista. A gravação
e o evento de auditoria ocorrem na mesma transação PostgreSQL. Nada deste fluxo
alimenta o treinamento, o lote histórico ou as métricas de ML.

A migração aditiva está em `src/esquema_web.sql`. Para outro ambiente, executar
`.\.venv\Scripts\python.exe -m src.gerenciar_acessos iniciar` antes de iniciar a API.
No ambiente local, aplicada e conferida (a tabela operacional estava vazia).
Código: `src/loja_web.py`, formulários em `frontend/operacao.js`, acompanhamento em
`frontend/cliente.js` e estilos em `frontend/conta.css`.

O componente `frontend/assistente.js` é compartilhado por Início, Dashboard,
Pedidos, Cliente e Entrar. O botão permanece fixo e é ocultado durante a intro.
Visitantes podem abrir o painel e acessar o login; conversar requer uma sessão.
Clientes recebem orientação geral da loja, sem consulta individual ou acesso ao
lote do analista. Analistas mantêm o contexto histórico existente. CSRF, controle
de perfil e separação de dados continuam ativos. A intro e o ML não foram editados.

Validação: 12 testes PostgreSQL em schema temporário aprovados, incluindo
persistência, propriedade do pedido, histórico, validação, migração repetível,
conflito de versões e permissões. Comando PowerShell:
`$env:ENTREGACERTA_TEST_POSTGRES='1'; .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_acesso_web.py -v`.
Sintaxe JS conferida com `node --check`. Edge conferiu a edição e recarga dos
pedidos, prazo no cliente, histórico, botão nas cinco páginas e ocultação na intro.
Contas e pedidos artificiais foram usados somente nesses testes técnicos, em schema
isolado removido ao final. A resposta da GenAI foi substituída por uma resposta de
teste; nenhuma chamada externa nem avaliação do modelo foi executada.
