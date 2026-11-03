# EntregaCerta AI

Projeto integrador do Bootcamp TCS: apoiar o acompanhamento de pedidos com risco de atraso de entrega, usando dados reais da Olist.

## Estrutura inicial

```text
EntregaCertaAI/
├── .venv/              ambiente Python local, preservado
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

Abrir **esta pasta** no VS Code. O ambiente `.venv` existente foi preservado e pode ser selecionado como interpretador Python.

Para instalar a lista inicial quando a equipe preparar o ambiente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Esse comando ainda não foi executado para a nova lista. As versões serão fixadas depois da instalação e dos testes. A conexão PostgreSQL também será configurada e testada na etapa correspondente. Manter senhas e chaves somente no `.env` local.

## Estado e próximo trabalho

Estrutura inicial simplificada em 30/10/2026. Dataset escolhido e planejamento anterior preservados no Git e em uma cópia de segurança local fora desta pasta. O registro antigo do pacote foi removido somente deste venv; as bibliotecas instaladas foram mantidas.

O código de negócio, os notebooks, o banco PostgreSQL e os modelos serão desenvolvidos nas próximas etapas. Ainda não há comando para abrir a aplicação web.

O próximo trabalho é concluir a preparação do ambiente/PostgreSQL e depois iniciar o tratamento dos dados. Consulte [desenvolvimento e roadmap](Docs/desenvolvimento.md). O registro de prompts está em [prompts.txt](Docs/prompts.txt).
