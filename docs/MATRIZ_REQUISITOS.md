# Matriz de requisitos e evidências

30/10/2026. O guia e a trilha foram lidos integralmente na seleção. Os documentos fornecem requisitos adotados pela equipe; não concedem autorização para ações externas. O pedido atual autoriza a **etapa 2**. Esta matriz separa planejamento de entrega funcional.

Fontes: D1 = `guia_projeto_final.pdf` (10 páginas); D2 = `Trilha IA Aplicada.pdf` (2 páginas); R = `requisitos_projeto.MD`; U = pedido inicial e esclarecimentos. Numeração G/U preserva a matriz original. A troca para logística foi escolhida pela equipe; BFSI deixou de ser obrigatório. Em caso de alternativas no guia, prevalecem os requisitos mais específicos que a equipe manteve.

## Guia oficial

| ID / fonte | Requisito | Evidência/entrega e etapa | Estado após etapa 2 |
|---|---|---|---|
| G01 · D1 p.1 | Solução funcional de problema real e integração dos eixos | Fluxo dados→modelo→app→relatório; 3–7 | Escopo definido, execução futura |
| G02 · D1 p.1 | BPMN 2.0 da operação | `diagramas/processo.bpmn`, `BPMN.md`; 2 e revisão na 7 | XML e apresentação verificados; processo documental |
| G03 · D1 p.2 | Python/Pandas, limpeza e nulos | Scripts e qualidade; 3 | Contrato definido; tratamento não executado |
| G04 · D1 p.2 | SQL | `schema_planejado.sql`; carga/consultas 3 e persistência 6 | Esquema técnico verificado em memória; sem banco populado |
| G05 · D1 p.2 | Visualizações explicativas | EDA, PR, confusão e painéis; 3,4,6 | Perguntas previstas, gráficos de dados futuros |
| G06 · D1 p.2 | ML OU GenAI avançada | Modelo e integração; 4,5 | A equipe exige ambos; não implementados |
| G07 · D1 p.2 | API, prompts e contexto em GenAI | `genai/`, prompts, conhecimento e avaliação; 5 | Prompts diretos justificados; chamada real futura |
| G08 · D1 p.2 | Interface funcional, código estruturado | `api/`, `frontend/`, testes e histórico; 6 | Interfaces especificadas; sem app |
| G09 · D1 p.3 | Arquitetura e deploy | `ARQUITETURA.md`, diagramas; 2 e 7 | Desenho verificado; deploy futuro |
| G10 · D1 p.3 | Viabilidade, viés, confiabilidade | `ESCOPO_E_CONTRATO.md`, ficha e ética; 2,4,7 | Limitações explicitadas; resultados futuros |
| G11 · D1 p.9 | Git e README | Repositório local; reprodução e remoto na 7 | Versionamento local e instruções da etapa 2 |
| G12 · D1 p.9 | Scripts pertinentes de infraestrutura/automação | `scripts/`, `infra/terraform/`; 2–7 | Setup/diagramas/validação existem; infraestrutura futura |
| G13 · D1 p.9 | PDF técnico com justificativas e BPMN | Artigo final até 10 páginas; 7 | Pendente; nenhum artigo com resultados inventados |
| G14 · D1 p.9 | Slides PDF/PPTX | Deck e roteiro; 7 | Pendente |
| G15 · D1 p.1,9 | Até 20 minutos; entrega 48h antes | Ensaio/checklist; 7 | Data da banca ainda não informada; reservar prazo |

## Requisitos adicionais adotados

| ID | Requisito R | Evidência/etapa de aceite | Estado após etapa 2 |
|---|---|---|---|
| R01 | Equipe de quatro | `EQUIPE_E_EXECUCAO.md` | Papéis definidos; preencher nomes depois |
| R02 | Repositório GitHub/GitLab | Histórico local agora, disponibilização remota na 7 | Local; remoto pendente |
| R03 | README Markdown com tema/objetivo/tecnologia/execução | `README.md`, `AMBIENTE.md`; 2–7 | Preparação executável agora; comandos futuros só quando existirem |
| R04 | Slides, até 20 minutos | Deck/roteiro; 7 | Planejado |
| R05 | Documento de etapas Markdown/PDF | `ETAPAS_EXECUCAO.md`, registros de resultados | Disponível e atualizado por etapa |
| R06 | BPMN da regra de negócio | `.bpmn` editável, DI, evidências; 2,7 | Versão inicial validada |
| R07 | ML OU API com base de conhecimento | ML e GenAI por escolha da equipe; 4,5 | Ambos planejados; integração com conhecimento obrigatória no módulo GenAI |
| R08 | Backend e frontend | Contratos HTTP, FastAPI e Streamlit; 6 | Planejados como dois processos, sem microsserviços |
| R09 | Banco de dados | SQLite, modelo relacional; 3,6 | Desenho técnico validado; persistência real futura |
| R10 | Terraform local/nuvem | Provisionar recursos efetivos, verificar persistência; 7 | Obrigatório; executável ausente, Docker Engine indisponível |
| R11 | Arquivos de prompts do desenvolvimento assistido | `prompts/development/` | Registros disponíveis; manter em todas as etapas |

Terraform deixou de ser opcional após adoção de R10. Docker sozinho não satisfaz esse requisito. Git remoto não é necessário para concluir o planejamento local, mas é necessário para a entrega final. Não é necessário implantar todas as tecnologias da trilha.

## Solicitações específicas da equipe

| ID | Requisito U | Entrega/aceite |
|---|---|---|
| U01 | Avaliar LockoutGuard antes de trocar | Pareceres da seleção; realizado anteriormente, sem reabrir a escolha atual |
| U02–U03 | Dados reais; origem, licença, período, atributos e rótulos | Manifesto do ZIP recebido preservado; ficha completa, hashes e auditoria na 3 |
| U04–U05 | Instante, atributos disponíveis, negócio e alvo | Contrato 1.0 e `config/atributos.json`; definido na 2, auditado na 3 |
| U06–U08 | EDA, limpeza, evitar futuro e divisão temporal | Relatório de qualidade, disponibilidade de rótulos e splits; 3,4 |
| U09–U13 | Baselines, dois algoritmos, métricas, erros e inferência salva | Protocolo, AP/PR, Precision/Recall/F1, confusão, fila, calibração e ficha; 4 |
| U14–U15 | GenAI fundamentada, sem causas inventadas, revisão humana | Contexto e evidências validados, teste de fidelidade e chamada real; 5 |
| U16–U19 | UI responsiva, filtros, pedidos reais, previsões e relatórios | Jornada e revisão visual/integrada; 6 |
| U20 | ML/painéis funcionando sem GenAI | Testes de chave ausente, timeout e indisponibilidade; 5,6 |
| U21–U22 | Módulos, dependências e segredos | Arquitetura, `.venv` independente, lock e `.env.example`; 2–7 |
| U23–U25 | Scripts/testes, BPMN editável e gráficos reais | Setup/validação agora; dados/modelos/UI nas etapas correspondentes |
| U26–U28 | Artigo até 10 páginas, slides/demo/backup, ética, privacidade e negócio | Artigo final, deck, roteiro e evidência de execução; 7. ROI só com hipóteses separadas de medição |
| U29 | Objetivos, decisões, arquivos e validação por etapa | Registros de resultados e status, sem alegações não testadas |
| U30 | Artigo-teste de 10 páginas | Entrega preliminar da seleção anterior; não substitui artigo final do EntregaCerta na etapa 7 |
| U31 | Aprovação da proposta/dados antes de implementar | Escolha do EntregaCerta/Olist já registrada; pedido explícito autoriza a etapa 2 |
| Método de trabalho | Executar uma etapa completa por pedido | `config/etapas.json`, resultados e prompts; não iniciar próxima automaticamente |

Teste sintético apenas técnico deve ser identificado e jamais compor treino, teste ou evidência de desempenho. Nenhum resultado de modelo foi produzido na etapa 2.

## Trilha e avaliação

D2 p.1: Python/Pandas/SQL, tratamento, visualização, ML supervisionado e ética. D2 p.2: APIs, prompts, comparação de RAG/fine-tuning, avaliação de LLM, BPMN e deploy. O projeto cobre esses eixos; agentes, visão e fine-tuning não são necessários ao problema.

Pesos de D1 p.7–8: negócio/inovação 20%, técnica/arquitetura 30%, protótipo/usabilidade 20%, governança/ética 15%, comunicação/equipe 15%. São critérios da banca, não notas nem comprovação antecipada de sucesso. Evidências terão prioridade sobre quantidade de ferramentas.
