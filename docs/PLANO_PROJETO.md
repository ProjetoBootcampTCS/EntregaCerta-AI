# Plano do EntregaCerta AI

Atualizado em 30/10/2026; planejamento iniciado em 29/10/2026. A escolha do projeto e da base Olist encerra a seleção de tema. O trabalho seguirá em etapas com decisões, arquivos e evidências registradas. Não é necessário solicitar novamente autorização para tarefas rotineiras dentro desse escopo.

## 1. Estado atual

- Leitura do guia, da trilha e dos requisitos adicionais: realizada.
- Pesquisa e auditoria de cinco tabelas Olist: realizadas, preservadas no diretório de pesquisa.
- Seleção do EntregaCerta AI e da base associada: realizada pela equipe nesta conversa.
- Etapa 2: concluída; contrato, diagramas, matriz, ambiente e verificações em `ETAPA_2_RESULTADOS.md`.
- Preparação final de dados, treinamento, aplicação, chamada real de GenAI e provisionamento: pendentes.

## 2. Etapas e critérios de conclusão

O escopo detalhado dos pedidos está em [Etapas de execução](ETAPAS_EXECUCAO.md), e o estado está em `../config/etapas.json`. A etapa 1 já encerrou a seleção; a etapa 2 está concluída; a etapa 3 é a próxima e não foi iniciada.

| Etapa | Objetivo e decisões | Entrega prevista | Como validar |
|---|---|---|---|
| 1. Análise e escolha | Interpretar requisitos, comparar propostas e escolher dados reais | Parecer e auditorias preliminares; seleção registrada | Confirmar fonte, alvo, limites e escolha da equipe; concluída para seleção |
| 2. Planejamento e ambiente | Fixar pergunta, população, momento da previsão, responsabilidades, arquitetura e ambiente independente | Contrato, matriz de requisitos, arquitetura, modelo de dados, BPMN e ambiente | Conferir rastreabilidade, diagramas, configuração e instalação |
| 3. Dados | Reutilizar originais, preservar hashes, concluir limpeza/EDA, SQL e protocolo temporal | Scripts, manifesto, dicionário, relatório de qualidade, banco, figuras e divisões | Conciliar chaves, junções, exclusões e datas; separar atributos de informações futuras |
| 4. ML e inferência | Registrar protocolo, comparar referências e modelos, selecionar no desenvolvimento e avaliar no teste | Artefato, manifestos, métricas, figuras, ficha do modelo e inferência | Reproduzir predições, conferir métricas e preservar a avaliação final |
| 5. GenAI | Produzir relatórios com evidências e documentação concreta | Prompts, base de conhecimento, cliente da API, avaliação e fallback | Testar fidelidade e indisponibilidade; chamada real antes de declarar integração validada |
| 6. Aplicação | Integrar consulta, filtros, gráficos, inferência, revisão e relatório | Backend, frontend, registros e instruções | Percorrer o fluxo com pedidos reais e sem API; rotular a reprodução histórica |
| 7. Infraestrutura e entrega | Provisionar com Terraform, validar integração e preparar a defesa | Infraestrutura executada, documentação, BPMN final, artigo, slides e backup | Conferir requisitos contra evidências e deixar dependências externas pendentes explícitas |

Os experimentos podem indicar baixo ganho preditivo. Nesse caso, investigar qualidade, atributos e erros e relatar a limitação. Uma alteração de alvo ou de instante de previsão deve receber nova versão e novo protocolo, sem reaproveitar o teste para obter um resultado desejado.

## 3. Primeira versão funcional pretendida

O analista seleciona um pedido histórico reservado para avaliação, executa a inferência real, consulta a estimativa e as informações disponíveis na aprovação, registra sua revisão e solicita um relatório fundamentado nos fatos da aplicação. O resultado observado pode ser revelado para comparação depois da previsão.

O conjunto inicial exclui cancelados e casos sem desfecho entregue. Isso delimita a evidência obtida; não comprova cobertura de todos os pedidos futuros. Um escore só será denominado probabilidade se a avaliação de calibração justificar essa interpretação.

## 4. Arquitetura definida para o MVP

- Dados/treinamento: Python, Pandas, SQL e Scikit-learn.
- Persistência: SQLite controlado pelo backend e artefatos de modelo versionados por manifesto.
- Backend: FastAPI para consulta de registros, métricas, inferência, revisão e geração de relatório.
- Frontend: Streamlit e Plotly, consumindo a API HTTP do backend.
- GenAI: API de LLM desacoplada da inferência. Começar com prompts estruturados, dados calculados e documentação selecionada; RAG adicional apenas quando houver necessidade funcional.
- Infraestrutura: Terraform é obrigatório. Verificar primeiro o caminho local com provider Docker, containers, rede e persistência; registrar dependências e executar antes de declarar o provisionamento validado.
- Organização: um repositório, módulos com responsabilidades claras e sem decomposição em microsserviços de domínio.

Os módulos de negócio ainda não foram executados. O ambiente independente e os diagramas foram verificados na etapa 2; implementação nas etapas 3 a 6.

Na etapa 2 foram verificados Git, Python 3.12 e Docker client. O Docker Engine não conectou e Terraform não foi encontrado no PATH. Resolver essas dependências para o provisionamento da etapa 7; nenhuma infraestrutura foi aplicada.

## 5. Organização futura dos arquivos

```text
EntregaCertaAI/
  README.md
  config/                 # contrato, parâmetros e protocolo
  data/                   # manifesto e dados originais/tratados ignorados pelo Git
  src/entregacerta/
    data/                 # aquisição, limpeza e SQL
    training/             # treino e avaliação
    inference/            # pipeline de previsão
    api/                  # backend
    genai/                # contexto, API, validação e fallback
  src/entregacerta/frontend/ # interface futura
  artifacts/              # modelo e manifestos
  reports/                # resultados e figuras efetivamente calculados
  tests/                  # testes essenciais
  infra/terraform/        # provisionamento
  prompts/development/    # prompts do desenvolvimento assistido
  prompts/application/    # prompts generativos em produção acadêmica
  docs/                   # decisões, BPMN, arquitetura e artigo
  presentation/           # slides, roteiro e instruções do backup
```

A árvore é um plano, não uma afirmação de que todos os módulos já existem. Não versionar chaves, arquivos `.env`, dados brutos, estado sensível do Terraform ou volumes locais. A disponibilização dos dados e artefatos deve respeitar a licença e permitir reprodução por manifesto.

## 6. Divisão sugerida para quatro pessoas

1. Dados e ML: qualidade, atributos, protocolo, treinamento e métricas.
2. Backend e persistência: SQL, consultas, inferência, integração e registros.
3. Interface e demonstração: navegação, gráficos, fluxo de revisão e roteiro.
4. Infraestrutura e qualidade: Terraform, ambiente, testes integrados e integração GenAI.

Documentação, entendimento dos modelos, revisão das evidências e preparação da apresentação são compartilhados. Os nomes e a disponibilidade da equipe ainda não foram informados; não se presume uma carga horária individual.

## 7. Entregáveis obrigatórios

Repositório GitHub/GitLab; README executável; registro das etapas; prompts usados no desenvolvimento; aplicação com frontend/backend/banco; ML e GenAI conforme o escopo da equipe; infraestrutura Terraform; testes essenciais; arquitetura; BPMN 2.0 válido e editável; artigo PDF até dez páginas; slides para até vinte minutos; roteiro e demonstração gravada de backup.

## 8. Próxima entrega

A **etapa 2 foi concluída**; consultar `ETAPA_2_RESULTADOS.md`. Na **etapa 3**, incorporar manifesto dos arquivos Olist, concluir tratamento e EDA e construir a base SQL. A análise dos dados precede o treinamento; as próximas etapas devem mostrar a contagem final de pedidos elegíveis, os atributos permitidos, as divisões temporais e a rastreabilidade de cada exclusão.
