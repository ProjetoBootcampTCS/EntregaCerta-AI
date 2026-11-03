# Escopo e contrato do EntregaCerta AI

Versão 1.0 · 30/10/2026 · planejamento concluído na etapa 2.

O sistema ajudará o analista de operações de comércio eletrônico a escolher quais pedidos acompanhar primeiro. Na aprovação, o modelo atribuirá um escore de risco de atraso; a interface apresentará uma fila, evidências do pedido e indicadores. O analista registrará sua decisão e poderá solicitar um relatório assistido por IA. Nenhum pedido será cancelado, bloqueado ou alterado automaticamente.

## Pergunta e alvo

**Pergunta:** entre os pedidos elegíveis com entrega posteriormente observada, quais apresentam maior risco de chegar após o dia prometido, usando apenas informações presumidamente disponíveis na aprovação?

- Unidade: um pedido, com seus itens agregados; um pedido com vários vendedores continua sendo uma observação.
- Momento da previsão: `order_approved_at`. A demonstração será uma reprodução histórica, identificada na tela.
- Tarefa: classificação supervisionada de um desfecho futuro, avaliada retrospectivamente.
- Positivo (`is_late=1`): dia civil de `order_delivered_customer_date` **maior** que o dia civil de `order_estimated_delivery_date`.
- Negativo (`is_late=0`): entrega até o dia prometido, inclusive.
- Não comparar horários para definir atraso: as promessas estão registradas à meia-noite. Não inventar fuso horário.

O rótulo é derivado de duas datas observadas, com regra verificável; não é uma avaliação humana de culpa, qualidade ou responsabilidade. Para reconstruir treino em uma data de corte, considerar o rótulo conhecido somente a partir da entrega registrada (`label_observed_at`), de forma conservadora.

## População e restrições

O estudo inicial abrange pedidos com status final entregue, datas de entrega e promessa preenchidas e cronologia compatível. Excluir da avaliação supervisionada: aprovação/compra ausente ou inválida, aprovação anterior à compra, entrega anterior à aprovação e promessa com dia já vencido na aprovação. Não descartar silenciosamente valores: registrar motivos, interseções e cobertura na etapa 3. Ausência de atributos não equivale automaticamente a exclusão; tratar conforme o contrato.

Cancelados, indisponíveis, não entregues e casos sem desfecho **não são negativos**. Essa seleção usa informação posterior para definir a coorte do estudo, nunca como entrada do classificador. Portanto, o desempenho medido será condicional aos entregues elegíveis. Na demonstração, selecionar pedidos reais dessa coorte; uso sobre todos os aprovados exigirá dados que representem cancelamentos, perdas e censura, e outra validação. Não prometer uma solução de produção para toda a operação.

A Olist contém registros reais e anonimizados de comércio eletrônico brasileiro de 2016–2018, não dados bancários. Cinco CSVs do ZIP recebido coincidem por SHA-256 com os anteriormente auditados. A auditoria preliminar identificou 96.394 candidatos após exclusões iniciais; esse total pode mudar com a auditoria completa. Não é o tamanho do treino. Nenhum modelo desta proposta foi treinado.

## Entradas e disponibilidade

A lista de 19 atributos, fontes, agregações, nulos e desempates está em [atributos.json](../config/atributos.json). Usar preço/frete informado, composição do pedido, categoria, peso/dimensões, UFs e calendário/prazo disponível. Manter IDs apenas para rastreabilidade. Entrega efetiva, passagem efetiva à transportadora, status final, reviews, `shipping_limit_date` e transformações do alvo ficam fora da primeira versão.

A fotografia da fonte não permite comprovar quando o cadastro ou a promessa foram alterados. A disponibilidade desses campos na aprovação é uma **hipótese**, não um fato demonstrado. Históricos por vendedor ficam fora do MVP: exigiriam reconstrução com eventos e rótulos já conhecidos em cada instante. Pré-processamento, imputação, seleção e codificação serão ajustados somente no treino.

## Priorização e sucesso experimental

A fila ordenará o escore em ordem decrescente. Como hipótese acadêmica inicial, avaliar os 10% de maior escore em cada dia de aprovação: `K=ceil(0,10*N)`, mínimo de 1 para dias com pedidos, e 0 para dias vazios. Empates pelo ID, apenas para ordenar. Comparar também 5% e 20% como sensibilidade previamente declarada. Essa capacidade **não foi medida em empresa** e não é limiar universal de risco. O lote diário usa somente pedidos daquele dia; não fingir decisão em tempo real antes do fechamento do lote. A inferência de um pedido pode ocorrer na aprovação, enquanto sua posição final na fila diária depende do lote.

Referências: classificador trivial com prevalência do treino; fila aleatória (valor esperado e semente registrados); regra simples priorizando menor prazo prometido. Comparar regressão logística e um modelo de árvores, inicialmente Random Forest. Não escolher pela accuracy isolada. Medir Average Precision (AP), curva Precision-Recall, Precision/Recall/F1, matriz de confusão, Precision@K, Recall@K e lift da fila contra referências na mesma coorte. Explicar se PR-AUC significar AP ou integração trapezoidal; não tratá-las como idênticas.

Na etapa 3, fixar divisões por aprovação e disponibilidade de desfechos; na 4, registrar protocolo antes de medir desempenho. Reservar teste final e selecionar modelo, calibração, limiar e política apenas no desenvolvimento. Examinar variação mensal, erro por segmento com amostra suficiente e intervalos de incerteza com reamostragem temporal justificada.

**Critério de utilidade a testar:** superar a fila aleatória e a regra de prazo em Precision@K na capacidade principal, sem esconder Recall@K e a incerteza. Se a superioridade não for sustentada ou houver degradação relevante entre períodos, registrar que a utilidade não foi demonstrada. Concluir a etapa experimental honestamente é diferente de comprovar benefício empresarial. Probabilidade percentual só será apresentada se a avaliação de calibração a sustentar; caso contrário, mostrar escore.

## GenAI e resultado de negócio

Prompts diretos com contexto estruturado serão a primeira opção: fatos do pedido, versão do modelo, métricas e trechos curtos da base de conhecimento (dicionário, ficha do modelo e procedimento acadêmico de revisão). Não há justificativa inicial para agentes ou banco vetorial. Se o acervo crescer e a busca demonstrar necessidade, avaliar RAG na etapa 5.

A LLM redigirá interpretação e relatório; não calculará o risco nem inventará causa de atraso. Valores e referências serão validados pela aplicação. Contexto insuficiente deve gerar abstenção explícita; instruções em textos externos serão tratadas como dados. Sem chave, com timeout ou erro, a aplicação manterá ML e painéis e oferecerá resumo factual com aviso. Uma chamada real e testes de fidelidade serão necessários para declarar a integração validada.

Indicadores de negócio retrospectivos: atrasos capturados na fila, falsos alertas, volume de revisão e cobertura. Tempo de análise, redução de atrasos e economia dependem de piloto real; não estão medidos. Frete informado não é custo operacional. Qualquer ROI futuro deverá separar hipóteses de resultados observados.

## Aceite do MVP final

Selecionar pedido real → consultar atributos na aprovação → executar pipeline salvo → mostrar escore/fila/versão → registrar revisão no SQL → gerar relatório com evidências → repetir o fluxo sem API. Reproduzir dados e modelos por scripts, exibir limitações, preservar licença e fornecer Terraform executado, BPMN, artigo e apresentação. O aceite do planejamento atual não equivale a esse aceite final.

Fonte: [Olist no Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), licença publicada CC BY-NC-SA 4.0; preservar atribuição e condições, sem presumir autorização comercial.
