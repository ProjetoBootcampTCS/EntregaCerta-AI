# 🚚 EntregaCerta AI

## Comparação de doses CTGAN e repetição — 11/11/2026

Notebook: [doses de dados sintéticos e repetição de atrasos](Notebooks/04_testes_doses_ctgan.ipynb).
Compara 500, 1.000 e 2.000 exemplos adicionais com três sementes, mantendo a regressão
logística e a avaliação em pedidos reais. Inclui CTGAN nos positivos e CTGAN condicional
ajustada no treino completo. Resultados e caches em `Modelos/experimento_ctgan/doses_20261111/`.

Para reproduzir, use o ambiente CTGAN descrito abaixo e execute na raiz:

```powershell
.\.venv-ctgan\Scripts\python.exe -m src.testar_doses_ctgan
```

A consulta ao PostgreSQL é somente leitura. O notebook lê as evidências da execução;
as três sementes medem variação experimental, não substituem validação temporal independente.
O modelo da aplicação, o notebook 02 e o CSV combinado do primeiro experimento são preservados.
Esta rodada reaproveita o gerador e uma amostra do lote anterior da seed 42. Para reproduzir
os mesmos lotes do zero, execute primeiro o notebook CTGAN de 10.000 exemplos e depois
o script de doses, usando as versões registradas no protocolo. Sem esse cache anterior,
o script treina a seed 42 e faz uma nova amostragem, cujos números podem diferir desta rodada.

## Experimento CTGAN — 11/11/2026

Notebook: [comparação CTGAN com PostgreSQL](Notebooks/olist_comparacao_otimizada_ctgan_postgresql.ipynb).
A cópia original enviada pela equipe também está em `Notebooks/olist_comparacao_otimizada_gmm_treino_teste.ipynb`.

Selecione no VS Code o kernel `.venv-ctgan/Scripts/python.exe`, mantenha o PostgreSQL ligado
e execute o notebook em ordem. Para instalar em outra máquina, use um ambiente separado:

```powershell
python -m venv .venv-ctgan
.\.venv-ctgan\Scripts\python.exe -m pip install -r requirements-ctgan.txt
```

O experimento aprende com atrasos reais de treino e gera até 10.000 exemplos sintéticos,
identificados como `origem_dado=sintetico_ctgan` e `rotulo_observado=False`.
Eles entram exclusivamente no treino; validação e teste continuam reais. A carga escreve
somente no schema `experimentos_ctgan`, sem modificar os pedidos usados pela aplicação.
O CSV combinado fica em `Dados/pedidos_tratados_e_injetados.csv`.
Métricas, gráficos, cache e modelos experimentais ficam em `Modelos/experimento_ctgan/`.
Nenhum ganho é presumido: compare as saídas executadas do notebook.

**As seções antigas abaixo descrevem o estado em 05/11/2026**, não o estado completo atual.

**Inteligência Artificial aplicada à previsão de atrasos e à priorização de pedidos no e-commerce.**

O **EntregaCerta AI** é um projeto de apoio à decisão logística que propõe integrar **Machine Learning (ML), análise de dados e Inteligência Artificial Generativa (GenAI)** para identificar pedidos com maior risco de atraso e auxiliar analistas na definição de prioridades operacionais.

A solução foi concebida para transformar dados históricos de pedidos em informações úteis à tomada de decisão, oferecendo previsões de risco, evidências explicativas, acompanhamento de decisões e geração assistida de relatórios.

O objetivo não é substituir o analista, mas fornecer informações estruturadas para apoiar decisões mais rápidas, consistentes e rastreáveis.

## 📌 Status do projeto

**Última atualização:** 5 de novembro de 2026

**Etapa atual:** Etapa 3 — Consolidação e preparação temporal dos dados para ML implementadas.

**Próximos trabalhos:** concluir a EDA relacional e a carga PostgreSQL; comparar baseline e modelos.

O projeto está em desenvolvimento. Há dados reais consolidados e matrizes preparadas para ML. O notebook abaixo apresenta esse fluxo de forma didática, sem treinar modelos preditivos.

**Ainda não foram implementados:**

- Modelo de Machine Learning treinado.
- Interface operacional de análise logística.
- Banco de dados populado para utilização pela aplicação.
- Integração funcional com uma API de LLM.
- Pipeline completo de previsão em produção.

Os comandos disponíveis permitem consolidar e tratar os dados e executar os testes da preparação.

A documentação atual está em [desenvolvimento e roadmap](Docs/desenvolvimento.md).

---

## 🎯 Objetivos

O EntregaCerta AI busca desenvolver uma solução capaz de:

1. **Prever riscos:** estimar, no momento da aprovação do pedido, a probabilidade de atraso na entrega.
2. **Priorizar pedidos:** organizar uma fila de análise conforme o risco previsto e a capacidade operacional.
3. **Apoiar decisões:** disponibilizar evidências e informações relevantes para interpretação dos resultados.
4. **Registrar ações:** permitir que o analista documente suas decisões e acompanhe os pedidos.
5. **Gerar relatórios:** utilizar GenAI para produzir sínteses assistidas baseadas em informações verificáveis.
6. **Avaliar o desempenho:** medir a qualidade das previsões e investigar a utilidade operacional da solução.

A arquitetura prevê que os recursos de ML e visualização continuem disponíveis mesmo em caso de indisponibilidade da API de LLM.

## 🗂️ Dataset

O projeto utiliza o [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), disponibilizado publicamente no Kaggle.

O conjunto contém registros reais e anonimizados de operações de comércio eletrônico realizadas entre 2016 e 2018.

Entre as informações disponíveis estão pedidos, clientes, vendedores, produtos, pagamentos, avaliações e eventos logístico

# EntregaCerta AI

Projeto integrador do Bootcamp TCS: apoiar o acompanhamento de pedidos com risco de atraso de entrega, usando dados reais da Olist.

## Estrutura inicial

```text
EntregaCertaAI/
├── .venv/              ambiente Python local (3.12)
├── Dados/              arquivos originais e dados tratados
├── Docs/               desenvolvimento, BPMN e registro de prompts
├── Modelos/            modelos treinados, quando existirem
├── Notebooks/          exploração e experimentos
├── src/                código Python, criado por etapa
├── .env.example        exemplo de configuração sem credenciais
├── .gitignore          proteção de dados e segredos
├── requirements.txt    bibliotecas previstas
└── README.md
```

As pastas ainda vazias têm `.gitkeep` para serem preservadas no Git. `.git` guarda o versionamento e `.env` guarda a configuração local, sem publicação.

## Tecnologias escolhidas

VS Code, Python, Pandas, PostgreSQL, Scikit-learn e PyTorch. Streamlit está previsto para a interface; Matplotlib/Seaborn/Plotly para gráficos; uma API de LLM para relatórios fundamentados. Terraform permanece como requisito da entrega final.

## Como começar

Abrir **esta pasta** no VS Code. Usar o ambiente `.venv` com **Python 3.12** como interpretador. Ao mudar a versão do Python, criar um ambiente limpo: reutilizar uma pasta com bibliotecas compiladas para outra versão pode causar erros de importação.

Nos notebooks, clicar em **Select Kernel / Selecionar Kernel**, escolher **Python Environments → .venv (Python 3.12)** e reiniciar o kernel antes de executar as células.

Para instalar a lista inicial quando a equipe preparar o ambiente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

A instalação completa dessa lista ainda não foi validada. Em 03/11/2026, foram instalados e verificados Python 3.12.14, NumPy 2.5.4, Pandas 3.1.0 e ipykernel 7.4.0. A importação do Pandas, a leitura dos cinco CSVs do notebook de tratamento e `pip check` passaram no terminal. O kernel do VS Code deve ser selecionado e reiniciado pela equipe.

A conexão PostgreSQL será configurada e testada na etapa correspondente. Manter senhas e chaves somente no `.env` local.

## Preparação didática no notebook

Abra [01_preparacao_dados.ipynb](Notebooks/01_preparacao_dados.ipynb) no VS Code, selecione **.venv (Python 3.12)** e execute as células na ordem.

O notebook explica a leitura dos sete CSVs usados, agregações e junções, distâncias, alvos observados, limpeza, divisão temporal e transformações ajustadas apenas no treino. As saídas incluem conferências e dois gráficos descritivos. Os scripts atuais continuam disponíveis para automatizar o mesmo trabalho.

Ele calcula a preparação diretamente dos originais. Se `Dados/pedidos_ml.csv` e `Modelos/dados_ml.joblib` já existirem, compara os resultados e os preserva; uma divergência interrompe a execução. Se estiverem ausentes, cria esses arquivos. Ainda não treina classificadores ou regressores.

## Dataset consolidado

Os nove CSVs originais ficam em `Dados/Brazilian Logistic/`. Para gerar `Dados/pedidos_consolidados.csv`, com uma linha por pedido:

```powershell
.\.venv\Scripts\python.exe src\preparar_dados.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A execução de 05/11/2026 gerou 99.441 linhas e 53 colunas; cinco testes com registros reais passaram. Os originais foram preservados e os totais monetários reconciliados. O CSV contém campos retrospectivos para análise: no treinamento futuro, selecionar explicitamente as entradas candidatas em `COLUNAS_PREVISAO`, sem usar datas reais de entrega, status final, rótulos ou flags de elegibilidade como atributos. Há 2.971 pedidos sem rótulo, mantidos sem inventar desfechos.

Regras das colunas e limitações estão em [desenvolvimento e roadmap](Docs/desenvolvimento.md); o registro de geração está em [validação dos dados](Docs/validacao_dados.txt).

## Dados preparados para testes de ML

```powershell
.\.venv\Scripts\python.exe src\tratar_dados_ml.py --entrada "Dados\pedidos_consolidados_teste.csv"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Gera `Dados/pedidos_ml.csv` (base legível já imputada) e `Modelos/dados_ml.joblib` (matrizes, alvos e pré-processador). Foram preparados 91.390 pedidos: 41.173 de treino, 24.667 de validação e 25.550 de teste, respeitando a disponibilidade dos rótulos. Imputação, escala e codificação são ajustadas somente no treino. Os 10 testes passaram.

Para comparar os algoritmos, carregar as matrizes prontas; elas já excluem IDs, datas reais e demais campos posteriores da entrada do modelo:

```python
import joblib
dados = joblib.load("Modelos/dados_ml.joblib")
X_treino, y_treino = dados["X"]["treino"], dados["y"]["treino"]
X_validacao, y_validacao = dados["X"]["validacao"], dados["y"]["validacao"]
X_teste, y_teste = dados["X"]["teste"], dados["y"]["teste"]
```

O CSV tratado tem categorias legíveis e metadados: não é uma matriz para passar inteira ao estimador. Usar as matrizes do pacote evita refazer transformações e perder os indicadores de ausência. Manter o teste reservado até a avaliação final. Consultar [registro do tratamento](Docs/tratamento_ml.txt) e [metodologia e limitações](Docs/desenvolvimento.md). Nenhum modelo preditivo foi treinado nesta etapa.

## Estado e próximo trabalho

Estrutura inicial simplificada em 30/10/2026. Dataset escolhido e planejamento anterior preservados no Git e em uma cópia de segurança local fora desta pasta. Em 03/11/2026, o `.venv` foi recriado para corrigir a mistura de Python 3.14 com bibliotecas compiladas para Python 3.12; o ambiente anterior ficou em backup fora desta pasta.

A consolidação, o tratamento para ML e a divisão temporal estão implementados; EDA relacional, carga PostgreSQL, modelos e aplicação permanecem pendentes de desenvolvimento e validação. Ainda não há comando para abrir a aplicação web.

O próximo trabalho de ML é comparar o baseline e os modelos usando as matrizes preparadas. EDA relacional e carga PostgreSQL também precisam ser concluídas. Consulte [desenvolvimento e roadmap](Docs/desenvolvimento.md). O registro de prompts está em [prompts.txt](Docs/prompts.txt).
