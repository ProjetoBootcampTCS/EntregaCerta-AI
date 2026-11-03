# Registro de desenvolvimento assistido · etapa 2

Data: 30/10/2026. Pedido da equipe: **“Perfeito, pode fazer a etapa 2”**. Escopo interpretado conforme `docs/ETAPAS_EXECUCAO.md`: realizar planejamento técnico e ambiente integralmente, verificar evidências e encerrar antes dos dados da etapa 3. A proposta EntregaCerta e a base Olist já estavam escolhidas.

## Instruções e contexto de trabalho registrados

- Usar os requisitos do guia/trilha e do documento adicional, diferenciando requisitos dos documentos de autorização para ações.
- Finalizar pergunta, alvo por dia civil, previsão na aprovação, população e atributos, sem usar informação posterior como entrada.
- Planejar backend/frontend/banco, GenAI fundamentada com API opcional no fluxo, responsabilidades de quatro pessoas e Terraform obrigatório na entrega final.
- Preparar ambiente próprio, versões fixadas, segredos fora do Git e diagramas editáveis, sem treinar ou iniciar a aplicação agora.
- Não inventar resultados; testes técnicos isolados não constituem evidência de ML.

Esses pontos resumem o contexto solicitado pela equipe e as decisões de implementação. Este arquivo não contém raciocínio privado, credenciais ou dados de clientes. O pedido original e os dois registros anteriores preservam o histórico de escopo.

## Decisões tomadas

Contrato 1.0 e 19 atributos; inferência na aprovação com fila retrospectiva em lote diário; capacidade inicial de 10% como hipótese acadêmica, sensibilidade 5/20%; supervisão humana. Coorte limitada a entregues elegíveis, snapshot sem histórico de versões de cadastro/promessa, sem inferência causal de economia. Referências e logística/Random Forest planejados, sem experimento nesta etapa.

Arquitetura modular Python/FastAPI/Streamlit/SQLite, treinamento offline e GenAI por prompts diretos com fatos e conhecimento curto. RAG/agentes não justificados inicialmente. Terraform com Docker local planejado para a etapa 7. Registro de revisão e relatório separado da verdade histórica.

## Trabalho executado e correções

- Criado pacote Python com configuração e diagnóstico, sem endpoints ou previsões fictícias.
- Instalado ambiente 3.12.14 sem pacotes do sistema; fixadas 60 distribuições; instalação limpa em segundo venv conferida contra o lock.
- Criados contratos, SQL planejado, matriz, papéis, decisões e instruções.
- Gerados arquitetura, modelo relacional e BPMN 2.0 com DI. Schemas oficiais OMG e bpmn-js 18.16.0 têm origem/hash/licença preservados. BPMN importado/exportado no navegador sem advertências; SVGs inspecionados visualmente e etiqueta inicial reposicionada.
- A criação de temporários pelo ensurepip/pytest falhou inicialmente na pasta restrita do sandbox. Setup passou a usar `.local/tmp`; testes usam `.local/pytest-temp` limitado ao projeto. Reexecução: 9 testes aprovados em ambos os ambientes.
- A primeira prévia local não respondeu no navegador devido à restrição de socket do sandbox. Servidor restrito a 127.0.0.1 foi executado com acesso local permitido; o visualizador então importou/exportou o BPMN com sucesso. Nenhum arquivo foi enviado a serviço externo para renderização.
- O caminho pessoal do ZIP saiu do manifesto versionado e foi configurado no `.env` local; hashes/proveniência foram preservados. Não houve extração/carga de registros nesta etapa.
- Conferência de versionamento identificou que a regra genérica `dist/` ocultava assets do modelador. A exclusão foi limitada ao `dist` da raiz e os hashes dos assets no índice Git foram conferidos, preservando os arquivos originais de terceiros.
- Git local próprio preparado para este projeto. Docker client encontrado, Engine sem conexão, Terraform ausente. Provisionamento não executado.

Evidências e comandos finais: `docs/ETAPA_2_RESULTADOS.md`, `docs/AMBIENTE.md` e `docs/validacao/`. Não houve treinamento, medição de métricas preditivas, implementação da página de negócio, chamada real de LLM nem infraestrutura aplicada.
