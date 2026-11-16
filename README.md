# EntregaCerta AI

Projeto do Bootcamp TCS que combina dados reais da Olist, PostgreSQL, Machine Learning
e GenAI para apoiar a revisão humana de pedidos com risco de atraso. Interface em
HTML, CSS e JavaScript, com backend FastAPI e áreas de cliente e analista.

## Abrir o sistema

Abra o Docker Desktop. No terminal do VS Code, **na pasta deste README**, execute:

```powershell
.\.venv\Scripts\python.exe main.py iniciar
```

Acesse **http://127.0.0.1:8000**. Mantenha o terminal aberto; Ctrl+C encerra a API.
Esse comando inicia o PostgreSQL e a aplicação usando o modelo salvo. Não é preciso
executar notebooks, treinar modelos ou abrir arquivos de src individualmente.

**Fluxo novo de dados e treinamento:** siga o [guia das três etapas](Docs/laboratorio_modelos.md).
O [guia de instalação](Docs/instalacao_novo_pc.md) documenta a aplicação web e seu
modelo anterior. Os notebooks anteriores ficam disponíveis como estudos históricos.

## Comandos principais

Todos usam .\.venv\Scripts\python.exe main.py seguido da ação:

| Ação | Quando usar |
|---|---|
| iniciar | Abrir o sistema no dia a dia |
| preparar-banco | Primeira instalação ou atualização das tabelas web; preserva histórico já carregado |
| criar-analista --nome "Nome" --email "email@equipe.com" | Cadastrar analista; a senha é solicitada no terminal |
| verificar | Conferir conexão, consulta e inferência reais, sem alterar os dados |
| preparar-dados | Criar/atualizar `datasets_merge.csv`, `datasets_engineering.csv` e `dataset_ml.csv` com a PLN legada |
| gerar-sinteticos --nome estudo_01 | Após sua validação: separar os dados e gerar CTGAN |
| treinar --nome estudo_01 | Treinar os modelos configurados sobre a preparação dessa execução |
| avaliar | Consultar métricas da última execução, sem retreinar |
| testar --postgres | Testar aplicação e integração com banco em schemas temporários |
| --help | Consultar a ajuda |

## Pipeline em três comandos

```powershell
.\.venv-pipeline\Scripts\python.exe src/1_preparar_dados.py
# Revise dataset_ml.csv e marque dados_validados=true no JSON de treinamento.
.\.venv-pipeline\Scripts\python.exe src/2_treinar_modelos.py --nome rodada_01
.\.venv-pipeline\Scripts\python.exe src/3_avaliar_modelos.py --nome rodada_01
```

São **7 Python + 2 JSON** para essas etapas; os módulos de web e assistente foram preservados.

## Onde trabalhar

Para comparar modelos e cenários reais/sintéticos/mistos, veja o [laboratório configurável](Docs/laboratorio_modelos.md).
Primeiro execute `python main.py preparar-dados` e trate os dados como desejar.
Depois da sua revisão, marque `dados_validados: true` em `src/configuracoes/2_treinamento.json`.
O treino usa `Dados/dataset_ml.csv`; cada execução salva um único CSV de desempenho
em `Dados/resultados_modelos/`, sem subpastas. Quantidade/semente das transportadoras
ficam em `src/configuracoes/1_dados.json` (padrão: 5 transportadoras, semente 42).
A geração e o treino permanecem bloqueados até isso acontecer, em todas as execuções.
Os CSVs ficam em `Dados/comparacao_modelos/`; modelos, em
`Modelos/comparacao_modelos/`; métricas, em `Dados/resultados_modelos/`. Neste computador, use `.venv-pipeline` para esses comandos.

```text
main.py           Comandos para operar o projeto
src/              Backend, PostgreSQL, dados, inferência e GenAI
  1_*.py          Preparação e PLN
  2_*.py          CTGAN, dados, catálogo e treino automatizado
  3_*.py          Métricas e consulta dos resultados
  configuracoes/  Dois JSONs: dados e treinamento
  experimentos/   Pré-processamento antigo ainda usado pela aplicação
lixeira/          Pipeline e estudos substituídos, preservados
frontend/         Páginas, estilos, scripts e logo em uso
Dados/            CSVs originais e bases preparadas
Modelos/          Modelo da aplicação e evidências dos experimentos
Notebooks/        01/02: preparação e modelo web anteriores, preservados
  experimentos/   CTGAN, históricos e comparações opcionais
  legado/         Estudos antigos preservados para consulta
tests/            Testes da aplicação e da preparação de dados
Docs/             Guia, histórico técnico, proveniência, registros e BPMN
```

Para continuar a pesquisa, consulte o [índice dos experimentos](lixeira/src/experimentos/README.md).
Os resultados, limitações e etapas realizadas estão no [registro técnico](Docs/desenvolvimento.md).
Os dois JSONs de src/configuracoes controlam dados, treinamento e CTGAN; os arquivos
em Modelos registram modelos, parâmetros e resultados, por isso foram preservados.

## Limites atuais

- O dashboard faz reprodução histórica; o score é risco relativo, não probabilidade calibrada.
- A loja é demonstrativa, sem pagamento ou envio real. Seus novos pedidos ainda não recebem score de ML.
- O modelo web mantém a fila de 10% originalmente configurada. Os estudos de recall de 90%/95% são experimentos separados.
- O assistente exige configuração de API. Se ela falhar, consultas, ML e relatório com resumo automático continuam disponíveis.
- Métricas de cenários sintéticos não comprovam desempenho em atrasos reais.

## Pontos de restauração

**Ponto 0:** estado anterior à organização. **Ponto 1:** versão organizada.
As cópias locais ficam na pasta irmã EntregaCertaAI_Pontos, fora do repositório.
Veja a seção de restauração no [guia](Docs/instalacao_novo_pc.md). Dados e modelos
foram preservados; ambientes Python e volume PostgreSQL ficam fora dos ZIPs.

Fonte: Brazilian E-Commerce Public Dataset by Olist, registros anonimizados de
2016–2018. Proveniência e condições de uso em [recebimento_dataset.txt](Docs/recebimento_dataset.txt).
