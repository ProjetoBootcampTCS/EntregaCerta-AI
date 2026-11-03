# Etapa 2 · resultados e verificação

30/10/2026 · EntregaCerta AI · planejamento técnico e ambiente.

## Objetivo atendido

Definir como o sistema será construído e preparar base técnica reproduzível, encerrando antes da etapa 3. Contrato 1.0: estimar risco de atraso na aprovação, em estudo retrospectivo de pedidos Olist entregues elegíveis, com revisão humana. Alvo por dia civil, 19 atributos com fontes/regras e exclusão de campos posteriores. Capacidade de fila de 10% é hipótese acadêmica, sem limiar universal nem benefício prometido.

## Arquivos e decisões entregues

| Entrega | Arquivos |
|---|---|
| Negócio, alvo, coorte, limites, métricas e sucesso | `ESCOPO_E_CONTRATO.md`, `../config/contrato_problema.json`, `../config/atributos.json` |
| Arquitetura modular e interfaces futuras | `ARQUITETURA.md`, `diagramas/arquitetura.mmd`, `.svg`, `.png` |
| Modelo relacional e DDL | `MODELO_DADOS.md`, `schema_planejado.sql`, `diagramas/modelo_dados.mmd`, `.svg`, `.png` |
| Processo com revisão humana e falha de API | `BPMN.md`, `diagramas/processo.bpmn`, `.svg`, `.png`, prévia `index.html` |
| Requisitos, responsabilidades e decisões | `MATRIZ_REQUISITOS.md`, `EQUIPE_E_EXECUCAO.md`, `DECISOES.md` |
| Ambiente, configuração e versões | `AMBIENTE.md`, `../pyproject.toml`, `../requirements.lock`, `../.env.example`, `../scripts/setup.ps1` |
| Diagnóstico e verificações técnicas | `../src/entregacerta/`, `../tests/`, `../scripts/validate_planning.py` |
| Desenvolvimento assistido e andamento | `../prompts/development/003-etapa-2.md`, `../config/etapas.json`, `ETAPAS_EXECUCAO.md` |

FastAPI e Streamlit serão dois processos da mesma aplicação, com SQLite e treinamento offline. GenAI recebe fatos e conhecimento curto por prompts diretos; RAG só se houver necessidade comprovada. A interface/modelo devem funcionar sem API. Terraform/Docker local é o caminho de provisionamento para a etapa 7.

## O que foi efetivamente verificado

| Verificação executada | Resultado | Evidência |
|---|---|---|
| Venv principal e instalação limpa adicional | Python 3.12.14, ambos sem pacotes do sistema; 60 versões coincidem com lock | `validacao/ambiente.json`, `ambiente_reproducao.json`, `reproducao.json` |
| Setup final e `pip check` | Execução concluída; nenhum conflito detectado | Script executado nesta etapa; diagnósticos e reprodução |
| Testes técnicos nos dois ambientes | **9 aprovados em cada**, sem falhas finais | `validacao/tests.xml`, `tests_reproducao.xml` |
| Importações de 12 bibliotecas principais | Todas concluídas; nenhum treinamento | `validacao/planejamento.json`, `planejamento_reproducao.json` |
| BPMN fonte e XML reexportado | XSD oficial válido, 18 nós, 19 fluxos, duas raias, referências/DI e alcance dos finais conferidos | `validacao/planejamento.json`, `processo_roundtrip.bpmn` |
| Importação/exportação no bpmn-js 18.16.0 | Sucesso, **zero advertências** | `validacao/bpmn_render.json` e SVG exportado |
| Arquitetura, modelo relacional e BPMN | SVGs renderizados e inspecionados visualmente; rótulo inicial ajustado | `diagramas/*.png` e fontes editáveis |
| SQL planejado em memória | 11 tabelas e 11 FKs; integridade e rejeição de referência órfã verificadas | `validacao/planejamento.json` e teste SQL |
| Contrato e proteção de segredos | Rejeição de fontes posteriores, validação de configuração e chave omitida do repr | Testes e contratos |
| Git/Docker/Terraform | Git 2.55.0, Docker client 29.8.1, Engine sem conexão, Terraform não encontrado | `validacao/ambiente.json` |

Testes não avaliam ML: incluem configuração de teste e um identificador fictício isolado para conferir FK em memória. Nenhum registro de teste entra no dataset. A primeira tentativa de pytest teve 5 erros de criação de temporário no sandbox; a configuração local foi corrigida e os 9 testes passaram nos dois ambientes. Não ocultar essa correção nem confundir falha ambiental com resultado de modelo.

## Como conferir

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m entregacerta.cli doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/validate_planning.py
.\.venv\Scripts\python.exe scripts/preview_diagrams.py
```

Abrir a prévia documental em `http://127.0.0.1:8766/`; encerrar com Ctrl+C. Setup e configuração estão em `AMBIENTE.md`. `validate_planning.py` usa os assets locais e a evidência de exportação já preservada; para gerar uma evidência nova do renderizador, abrir a prévia novamente.

## Limites e pendências das próximas etapas

Não houve extração/preparação final do dataset, carga real de banco, EDA nova, treinamento, métrica preditiva, interface de negócio, chamada real de LLM ou provisionamento. O SQL foi validado em memória; não existe banco populado. A presença de bibliotecas não comprova a aplicação futura. Repositório local não significa entrega em GitHub/GitLab. O commit técnico inicial usa autoria de automação Codex apenas no comando, sem alterar a configuração global; a identidade real da equipe deve ser configurada para o trabalho seguinte.

Docker Engine e Terraform precisam estar disponíveis antes do provisionamento da etapa 7. Não foram instalados/iniciados globalmente nem aplicados recursos. Nomes da equipe, data da banca, provedor/chave LLM e destino remoto serão preenchidos quando necessários; não impedem concluir esta etapa.

**Próximo passo: etapa 3**, aproveitando o ZIP já recebido para documentar fonte/licença, auditar e tratar os dados, construir SQLite/EDA e fixar o protocolo temporal. A etapa 3 não foi iniciada automaticamente.
