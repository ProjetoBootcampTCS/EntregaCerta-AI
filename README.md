# EntregaCerta AI

Apoio ao analista de logística para priorizar pedidos com risco de atraso. Na aprovação, o modelo estimará o risco; o analista consultará evidências, registrará sua decisão e poderá solicitar um relatório assistido por GenAI.

**Estado em 30/10/2026: etapa 2 concluída — planejamento técnico e ambiente.** A etapa 3 não foi iniciada. Ainda não há modelo treinado, página de negócio, banco populado ou chamada real de LLM. Os comandos atuais executam diagnóstico, testes e prévia dos diagramas.

## Decisões fundamentais

- Fonte escolhida pela equipe: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), registros reais e anonimizados de 2016–2018. Licença publicada CC BY-NC-SA 4.0; preservar atribuição e condições, sem presumir uso comercial autorizado.
- Um pedido por observação; atraso significa entrega **após o dia prometido**, sem comparar horários da promessa à meia-noite.
- Estudo retrospectivo condicionado aos entregues elegíveis. Cancelamentos e casos sem desfecho não são pontuais automaticamente; não extrapolar o desempenho para todos os aprovados.
- 19 atributos previstos na aprovação, sem datas posteriores, status final, avaliações ou IDs brutos. Disponibilidade do cadastro/promessa é hipótese, pois a fonte não tem versões históricas.
- Divisão temporal, baselines, regressão logística e Random Forest; seleção no desenvolvimento e teste reservado. Nenhuma métrica preditiva foi calculada.
- Fila diária com capacidade hipotética inicial de 10%, sensibilidade 5/20%; nenhum limiar universal ou ganho de negócio prometido. Resultado percentual somente se a calibração sustentar essa interpretação.

## Preparação e verificações disponíveis

Usar Python **3.12**. No PowerShell, dentro desta pasta:

```powershell
.\scripts\setup.ps1 -PythonExecutable "CAMINHO_DO_PYTHON_3_12\python.exe"
.\.venv\Scripts\python.exe -m entregacerta.cli doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/validate_planning.py
```

No computador atual, `.venv` já está preparado. Não usar o Python global 3.14 nem o ambiente de outro projeto. O setup instala as 60 versões fixadas em `requirements.lock` e o pacote local, preservando `.env` existente. `requirements.txt` aponta para o mesmo lock. Instruções completas: [Ambiente](docs/AMBIENTE.md).

O `.env` local já aponta para o ZIP recebido; esse caminho não é versionado. Em outro computador, configurar `ENTREGACERTA_DATASET_ZIP`. Deixar campos da LLM vazios nesta etapa. Não compartilhar chaves, banco, dados brutos, cache ou estado Terraform no Git.

**Verificado:** instalação independente e repetição limpa em segundo venv; `pip check`; nove testes aprovados em cada ambiente; importações das bibliotecas; SQL em memória com 11 tabelas/11 FKs; BPMN validado pelo XSD oficial e pelo bpmn-js sem advertências. Detalhes e limites: [Resultados da etapa 2](docs/ETAPA_2_RESULTADOS.md).

## Diagramas e documentação

- [Escopo e contrato](docs/ESCOPO_E_CONTRATO.md) · [atributos](config/atributos.json).
- [Arquitetura e interfaces](docs/ARQUITETURA.md) · [imagem](docs/diagramas/arquitetura.png) · [Mermaid editável](docs/diagramas/arquitetura.mmd).
- [Modelo de dados](docs/MODELO_DADOS.md) · [SQL planejado](docs/schema_planejado.sql) · [imagem](docs/diagramas/modelo_dados.png).
- [BPMN](docs/BPMN.md) · [arquivo editável](docs/diagramas/processo.bpmn) · [imagem](docs/diagramas/processo.png).
- [Matriz de requisitos](docs/MATRIZ_REQUISITOS.md) · [papéis da equipe](docs/EQUIPE_E_EXECUCAO.md) · [decisões](docs/DECISOES.md).
- [Etapas combinadas](docs/ETAPAS_EXECUCAO.md) · [plano](docs/PLANO_PROJETO.md) · [status](config/etapas.json) · [prompts de desenvolvimento](prompts/development/003-etapa-2.md).

Prévia documental local, com BPMN editável:

```powershell
.\.venv\Scripts\python.exe scripts/preview_diagrams.py
```

Abrir `http://127.0.0.1:8766/`; encerrar com Ctrl+C. A prévia não é a aplicação de logística. Assets/schema e suas licenças estão preservados localmente. A exportação permite validar novamente a compatibilidade do BPMN.

## Arquitetura prevista

Python/Pandas e SQL para preparação; Scikit-learn para treino/inferência; FastAPI no backend; Streamlit/Plotly no frontend; SQLite para dados e acompanhamento; API de LLM para relatórios com fatos e conhecimento controlado. Prompts diretos inicialmente, sem agentes ou RAG desnecessário. ML e painéis continuarão utilizáveis se a API falhar. Portas futuras: backend 8000 e frontend 8502.

Terraform é obrigatório pelo documento adicional. Provisionamento com Docker local está planejado para a etapa 7. Git está disponível; Docker client 29.8.1 foi encontrado, mas o Engine não conectou; Terraform não foi encontrado no PATH. Nenhuma infraestrutura foi aplicada. Essas condições foram registradas para resolver antes do deploy.

O projeto tem repositório Git local próprio, separado dos protótipos anteriores. O primeiro commit técnico usa autoria de automação Codex apenas nesse comando, sem configurar identidade global. A equipe deve configurar sua identidade antes dos próximos commits. GitHub/GitLab será preparado para a entrega final, sem exigir acesso remoto nesta etapa.

## Dados recebidos e próximo passo

O ZIP possui nove CSVs; os cinco principais (pedidos, itens, clientes, produtos e vendedores) coincidem por SHA-256 com a fonte anteriormente auditada. [Manifesto de recebimento](config/fonte_dataset_recebida.json). A auditoria preliminar contou 99.441 pedidos e 112.650 itens; propôs 96.394 candidatos após exclusões iniciais. Esses números não são o tamanho do treino e serão reconciliados na etapa 3. Nenhum resultado preditivo foi medido.

**Próximo pedido: execute a etapa 3 do EntregaCerta AI.** Ela inclui aquisição portátil a partir do ZIP, qualidade/limpeza com Pandas, agregação, EDA, carga SQL e protocolo temporal. O treinamento pertence à etapa 4.

## Entrega final prevista

Aplicação integrada, código/pipeline reproduzível, repositório GitHub/GitLab, testes, Terraform executado, documentação ética/técnica, BPMN editável, artigo PDF até dez páginas, slides/roteiro para até vinte minutos e demonstração de backup. Não alegar economia, redução de atraso ou ROI sem evidência ou hipóteses identificadas.
