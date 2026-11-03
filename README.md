# 🚚 EntregaCerta AI

**Inteligência Artificial aplicada à previsão de atrasos e à priorização de pedidos no e-commerce.**

O **EntregaCerta AI** é um projeto de apoio à decisão logística que propõe integrar **Machine Learning (ML), análise de dados e Inteligência Artificial Generativa (GenAI)** para identificar pedidos com maior risco de atraso e auxiliar analistas na definição de prioridades operacionais.

A solução foi concebida para transformar dados históricos de pedidos em informações úteis à tomada de decisão, oferecendo previsões de risco, evidências explicativas, acompanhamento de decisões e geração assistida de relatórios.

O objetivo não é substituir o analista, mas fornecer informações estruturadas para apoiar decisões mais rápidas, consistentes e rastreáveis.

## 📌 Status do projeto

**Última atualização:** 30 de outubro de 2026

**Etapa atual:** Etapa 2 concluída — Planejamento técnico e preparação do ambiente.

**Próxima etapa:** Etapa 3 — Engenharia e análise dos dados.

O projeto está em desenvolvimento. Até o momento, foram concluídos o planejamento técnico, a definição metodológica, a estruturação do ambiente e as validações iniciais.

**Ainda não foram implementados:**

- Modelo de Machine Learning treinado.
- Interface operacional de análise logística.
- Banco de dados populado para utilização pela aplicação.
- Integração funcional com uma API de LLM.
- Pipeline completo de previsão em produção.

Os comandos disponíveis atualmente permitem executar diagnósticos, testes automatizados, verificações de planejamento e visualização dos diagramas técnicos.

A documentação detalhada está disponível em [Resultados da Etapa 2](docs/ETAPA_2_RESULTADOS.md).

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

## Estado e próximo trabalho

Estrutura inicial simplificada em 30/10/2026. Dataset escolhido e planejamento anterior preservados no Git e em uma cópia de segurança local fora desta pasta. Em 03/11/2026, o `.venv` foi recriado para corrigir a mistura de Python 3.14 com bibliotecas compiladas para Python 3.12; o ambiente anterior ficou em backup fora desta pasta.

O código de negócio, os notebooks, o banco PostgreSQL e os modelos serão desenvolvidos nas próximas etapas. Ainda não há comando para abrir a aplicação web.

O próximo trabalho é concluir a preparação do ambiente/PostgreSQL e depois iniciar o tratamento dos dados. Consulte [desenvolvimento e roadmap](Docs/desenvolvimento.md). O registro de prompts está em [prompts.txt](Docs/prompts.txt).
