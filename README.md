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
