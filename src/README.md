# Código do projeto

| Pasta | Responsabilidade |
|---|---|
| `configuracoes/` | `1_dados.json`: dados/transportadoras/PLN; `2_treinamento.json`: modelos, CTGAN e cenários. |
| `1_preparar_dados.py` | Execute primeiro: merge, engenharia, PLN e exportação de `dataset_ml.csv`. |
| `1_pln.py` | Auxiliar chamado pela preparação, sem execução manual. |
| `2_dados_treino.py`, `2_ctgan.py`, `2_catalogo_modelos.py` | Auxiliares de validação/divisão, geração sintética e catálogo de modelos. |
| `2_treinar_modelos.py` | Execute após revisar os dados: treina CTGAN e modelos em loop e gera o CSV de métricas. |
| `3_avaliar_modelos.py` | Execute por último para consultar os resultados; contém as funções de métricas usadas no treino. |
| `eda/` | Notebook `01_atrasos_geograficos.ipynb`, mapas em `graficos/`, `localizacao.py` e o estudo original `loc.py`. |
| `ml/` | Inferência do modelo da aplicação web, preservada. |
| `postgresql/` | Carga, consultas e SQLs do banco. |
| `web/` | API, login, loja e consulta de pedidos. |
| `assistente/` | GenAI, conversas e feedback. |
| `relatorios/` | PDF do dashboard. |
| `experimentos/pipeline_anterior/` | Pré-processamento ainda necessário à inferência web e ao EDA, preservado. |

Na raiz: `python src/1_preparar_dados.py`; depois da sua revisão,
`python src/2_treinar_modelos.py --nome estudo_01` e
`python src/3_avaliar_modelos.py --nome estudo_01`.
Os nove arquivos do pipeline são os sete Python numerados e os dois JSON;
os outros módulos pertencem às funcionalidades preservadas.

O restante do pipeline anterior e dos estudos foi movido para `../lixeira/src/`. A aplicação
web ainda usa seu modelo anterior até uma substituição explícita, após o novo treino.
O desempenho fica em `Dados/resultados_modelos/<execucao>.csv`, um arquivo por
rodada e sem subpastas; os modelos novos ficam em `Modelos/comparacao_modelos/<execucao>/`.
