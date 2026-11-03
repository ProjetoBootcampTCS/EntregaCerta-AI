# Etapas de execução do EntregaCerta AI

Este documento define o escopo de cada pedido de execução. A numeração mantém as sete etapas originalmente combinadas. A etapa 1 está concluída para seleção do projeto; a etapa 2 está concluída; evidências em `ETAPA_2_RESULTADOS.md`. Não confundir a auditoria preliminar com a preparação final dos dados.

## Regra de trabalho

Quando a equipe pedir `Execute a etapa N do EntregaCerta AI`, realizar todas as tarefas daquela etapa, criar os entregáveis, executar as verificações pertinentes, corrigir os problemas encontrados e atualizar README, registro de desenvolvimento e status. O pedido abrange o trabalho técnico rotineiro necessário dentro do escopo já escolhido, sem nova confirmação para cada arquivo ou ajuste reversível.

Trabalhar em sequência, verificar os pré-requisitos em disco e reutilizar o que já estiver correto. Não repetir uma etapa concluída sem necessidade. Não iniciar a etapa seguinte automaticamente: encerrar a etapa pedida com o resultado e suas evidências.

Se houver dependência de uma credencial, autenticação, permissão ou informação externa indispensável, concluir as partes independentes, explicar exatamente o que falta e solicitar apenas o necessário. Nunca inventar essa informação ou marcar a etapa inteira como concluída enquanto um critério obrigatório estiver pendente. Chaves devem ser configuradas localmente, sem serem coladas na conversa ou versionadas.

Ao final de cada execução, informar: objetivo atendido, decisões, arquivos criados/alterados, comandos de uso, verificações efetivamente executadas e pendências. Resultados de desempenho só podem ser apresentados após os experimentos correspondentes. Dados sintéticos ficam restritos a testes técnicos identificados e nunca entram na evidência de desempenho do modelo.

Uma etapa pode ser tecnicamente concluída com desempenho de ML insatisfatório, desde que os resultados sejam reproduzíveis e relatados honestamente. Isso não autoriza alegar utilidade empresarial comprovada. Mudanças de alvo ou momento da previsão exigem nova versão explícita e protocolo compatível.

## Etapa 1 — Análise, viabilidade e escolha

**Estado atual: concluída para seleção.**

- Ler guia, trilha e requisitos adicionais.
- Comparar ideias, fontes reais, alvos e limitações.
- Auditar preliminarmente as tabelas candidatas da Olist.
- Registrar a escolha do EntregaCerta e da base associada pela equipe.

**Evidências existentes:** parecer da etapa inicial, auditorias e scripts em `../selecao_logistica_20261028`, requisitos consolidados e contrato inicial do problema.

**Conclusão:** proposta e fonte escolhidas com limitações conhecidas. Não inclui modelo treinado, aplicação pronta ou alegação de ganho operacional.

## Etapa 2 — Planejamento técnico e ambiente

**Pré-requisito:** etapa 1. **Estado atual: concluída em 30/10/2026.** Ver `ETAPA_2_RESULTADOS.md`.

### Fazer integralmente

- Finalizar objetivo, usuário, ação apoiada, alvo, unidade por pedido, instante da previsão e população avaliada.
- Documentar atributos permitidos, proibidos, hipóteses de disponibilidade e critérios de sucesso, sem prometer uma accuracy.
- Definir a arquitetura simples, interfaces dos módulos, modelo de dados e organização do repositório.
- Criar diagrama de arquitetura e modelo de dados editáveis.
- Criar BPMN 2.0 editável da operação, com início/fim, atividades, decisões e revisão humana; verificar o XML e sua apresentação em ferramenta compatível quando disponível.
- Preparar ambiente Python independente, dependências com versões registradas, exemplo de configuração e proteção de segredos.
- Verificar Git, Docker e Terraform; registrar versões/disponibilidade e o caminho de provisionamento. A execução da infraestrutura completa pertence à etapa 7.
- Definir frentes de trabalho para quatro pessoas e matriz de requisitos versus entregáveis. A ausência dos nomes não impede definir responsabilidades por papel.
- Preparar versionamento local adequado, sem alterar outros projetos ou exigir acesso remoto nesta etapa.
- Registrar os prompts usados no desenvolvimento e atualizar instruções de preparação.

**Entregáveis:** contrato revisado; arquitetura; modelo de dados; BPMN inicial; matriz de requisitos; ambiente e dependências reproduzíveis; configuração de exemplo; README e registro de decisões.

**Como concluir:** conferir os requisitos, abrir/validar os diagramas com os meios disponíveis e executar a instalação e as verificações de ambiente pertinentes. Separar disponibilidade de executáveis, funcionamento do Docker Engine e provisionamento efetivo; não declarar um a partir do outro.

## Etapa 3 — Dados, análise exploratória e SQL

**Pré-requisito:** etapa 2.

### Fazer integralmente

- Incorporar de forma portátil a aquisição dos cinco arquivos originais já auditados, evitando novo download se os arquivos disponíveis e seus hashes forem válidos.
- Registrar origem, licença, arquivos, hashes, data de aquisição, dicionário e limitações. O pipeline deve funcionar fora do diretório de pesquisa anterior.
- Preservar dados brutos e criar scripts reproduzíveis de preparação.
- Tratar nulos, categorias, duplicatas e inconsistências sem inventar valores de desfecho.
- Finalizar a elegibilidade e o alvo por dia civil; registrar motivo e quantidade de cada exclusão, inclusive sobreposições entre regras.
- Agregar itens e vendedores por pedido antes das junções; conferir chaves e cardinalidade.
- Construir SQLite com tabelas, relacionamentos, consultas úteis e base analítica.
- Produzir gráficos reais de volume, atraso, evolução temporal e relações relevantes, com interpretação e cobertura explícita.
- Definir atributos disponíveis na aprovação e preparar o protocolo temporal para revisão final antes do primeiro treinamento. Respeitar quando os rótulos ficaram conhecidos.
- Registrar as divisões/manifestos e como o teste será preservado; análises exploratórias não autorizam otimizar modelos no teste.

**Entregáveis:** scripts de aquisição/preparação; manifesto; dicionário; relatório de qualidade; banco SQL; base analítica; figuras de EDA; contrato de atributos e protocolo temporal.

**Como concluir:** executar o pipeline a partir dos arquivos originais, conciliar contagens e exclusões, verificar chaves/junções, conferir consultas e gráficos e demonstrar a separação entre atributos e informações futuras. Reexecuções devem produzir resultados equivalentes, sem depender de caminhos pessoais ou de outro projeto.

## Etapa 4 — Machine Learning, avaliação e inferência

**Pré-requisito:** etapa 3.

### Fazer integralmente

- Registrar o protocolo final, os conjuntos e os critérios de seleção antes de medir desempenho dos candidatos.
- Implementar referência trivial e regra operacional de prazo disponível.
- Treinar pelo menos regressão logística e um modelo de árvores justificado, com pré-processamento ajustado somente no treino.
- Tratar desbalanceamento e seleção de atributos de forma compatível com os dados. Não balancear artificialmente o teste.
- Selecionar configurações e limiar somente no desenvolvimento, com capacidade de revisão e hipóteses de custo explícitas.
- Avaliar Precision, Recall, F1, matriz de confusão, Average Precision/curva Precision-Recall e qualidade da fila (Precision@K/Recall@K). Identificar a convenção de cada métrica.
- Avaliar variação temporal, segmentos com amostra suficiente, falsos positivos/negativos e incerteza pertinente.
- Avaliar calibração antes de apresentar o escore como probabilidade.
- Interpretar fatores associados às previsões sem inferir causas não demonstradas.
- Avaliar o modelo selecionado no teste reservado, sem usar o resultado para escolher novos ajustes na mesma rodada.
- Salvar pipeline, configuração, versões e manifestos; criar inferência reproduzível.
- Produzir gráficos e ficha do modelo com resultados reais e limites. Se não superar referências, registrar e investigar; não manipular a avaliação.

**Entregáveis:** treinamento/avaliação; referências; artefato de inferência; manifesto experimental; métricas; figuras; relatório de erros; ficha do modelo; instruções e testes essenciais.

**Como concluir:** executar os experimentos e a inferência salva; conferir métricas e isolamento dos conjuntos; reproduzir predições em registros reais reservados. Modelos com resultado ruim continuam sendo resultados válidos, com a limitação explícita e sem promessa de benefício comprovado.

## Etapa 5 — GenAI fundamentada e funcionamento sem API

**Pré-requisito:** etapa 4.

### Fazer integralmente

- Definir os tipos de relatório e as informações concretas fornecidas pelo sistema.
- Preparar base de conhecimento pertinente: dicionário, ficha do modelo, significado das métricas, limitações e procedimento de revisão. Não inventar políticas de uma empresa real.
- Implementar integração por API, configuração segura, timeout, tratamento de erro e limite de uso.
- Criar e versionar prompts e contexto; justificar prompts diretos ou RAG sem acrescentar complexidade sem necessidade.
- Restringir afirmações a fatos e evidências rastreáveis; validar números, IDs e estrutura de saída quando aplicável.
- Manter revisão humana e evitar que a geração substitua o classificador ou atribua causas não comprovadas.
- Implementar funcionamento degradado explícito: ML e indicadores continuam utilizáveis se a API falhar.
- Avaliar fidelidade, falta de contexto, entrada adversarial, chave ausente, timeout e indisponibilidade.
- Executar chamada real do provedor antes de declarar a integração validada. Registrar evidências sem segredos.

**Entregáveis:** módulo GenAI; prompts; contexto/base de conhecimento; exemplo de configuração; relatório de avaliação e testes de falha/fidelidade.

**Como concluir:** chamada real bem-sucedida e verificações de conteúdo e falha executadas. Se faltar chave ou acesso do provedor, deixar esse item pendente e concluir o restante possível; não apresentar saída de teste como chamada real.

## Etapa 6 — Aplicação web integrada

**Pré-requisitos:** etapas 3 e 4, e módulo GenAI da etapa 5 com seus eventuais bloqueios explícitos.

### Fazer integralmente

- Implementar backend de consulta, métricas, inferência, revisão humana e relatório.
- Implementar interface organizada e responsiva com filtros, gráficos, registros e fila de acompanhamento.
- Permitir seleção de pedidos reais e execução do pipeline salvo; apresentar versão do modelo, resultado e significado da sinalização.
- Mostrar probabilidade somente quando sua interpretação for sustentada pela avaliação; caso contrário, usar a identificação correta de escore.
- Separar o que estava disponível na aprovação do desfecho posterior; identificar a demonstração como reprodução histórica.
- Registrar revisão e observações do analista em SQL; não confundir registros criados durante a demonstração com impacto operacional medido.
- Integrar GenAI, relatório exportável e tratamento de indisponibilidade.
- Implementar validações e mensagens úteis, sem botões fictícios ou predições pré-programadas.
- Executar testes essenciais dos endpoints, persistência, inferência e navegação; realizar inspeção visual quando houver acesso ao navegador, distinguindo-a de testes sem interface visual.
- Atualizar instruções e decisões de arquitetura/BPMN conforme o fluxo realmente implementado.

**Entregáveis:** backend; frontend; persistência de acompanhamento; relatórios; verificações de integração; instruções de execução local e registros de evidência.

**Como concluir:** percorrer consulta → inferência real → revisão → relatório, conferir dados/indicadores e repetir o fluxo principal sem API de GenAI. Declarar separadamente eventuais verificações visuais ou integrações externas que não puderem ser realizadas.

## Etapa 7 — Infraestrutura, validação final e apresentação

**Pré-requisito:** etapa 6 e estado explícito da integração generativa.

### Fazer integralmente

- Implementar infraestrutura Terraform com recursos efetivos pertinentes à aplicação; execução local é aceita. Docker sozinho ou documentação de Terraform não substitui provisionamento.
- Configurar containers, rede e persistência se esse for o caminho escolhido; proteger segredos e estado sensível do Terraform.
- Executar as verificações de infraestrutura e o provisionamento, registrar evidências e conferir persistência e funcionamento da aplicação.
- Fazer validação integrada em ambiente limpo/isolado quando possível; corrigir falhas e atualizar dependências e instruções.
- Concluir testes essenciais, documentação de decisões, privacidade, segurança, vieses e limitações.
- Finalizar README, guia de reprodução, BPMN 2.0 editável e diagrama de arquitetura.
- Gerar artigo final em PDF de até dez páginas, preferencialmente oito a dez, usando resultados reais.
- Criar slides profissionais, roteiro para até vinte minutos e orientações de apresentação para a equipe.
- Preparar a demonstração de backup; produzir gravação se a captura for viável e registrar honestamente seu estado. Não afirmar que houve ensaio real da equipe sem realizá-lo.
- Consolidar os prompts de desenvolvimento e os da aplicação, sem incluir segredos.
- Preparar a entrega em GitHub/GitLab com os acessos/destino disponíveis. Se faltar autenticação, preparar o pacote local e instruções e registrar a disponibilização remota como pendente.
- Apresentar indicadores de operação avaliados retrospectivamente; ROI somente com hipóteses explícitas e separado de resultados medidos.

**Entregáveis:** Terraform executado; versão reproduzível da aplicação; documentação final; artigo PDF; slides; roteiro; backup ou instruções/pendências de gravação; repositório/pacote de entrega e registro da validação final.

**Como concluir:** conferir cada requisito contra um arquivo ou evidência real. Pendências de credencial, provisionamento, acesso remoto, gravação ou ensaio devem permanecer visíveis. Para declarar o projeto integralmente entregue, resolver os itens obrigatórios ainda pendentes.

## Estado e pedido seguinte

O estado por etapa está em `../config/etapas.json`. Atualizar esse arquivo depois das execuções e manter as evidências detalhadas no registro de desenvolvimento.

O próximo pedido é: **Execute a etapa 3 do EntregaCerta AI.**
