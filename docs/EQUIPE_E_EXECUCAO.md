# Equipe e sequência de execução

Quatro papéis, a preencher com os nomes da equipe. Todos devem compreender fonte, alvo, vazamento temporal, métricas e limitações; a divisão não dispensa revisão cruzada.

| Pessoa/papel | Responsabilidade principal | Entrega | Revisão cruzada |
|---|---|---|---|
| 1 · Dados e ML | Fonte, Pandas, EDA, atributos, protocolo e modelos | Etapas 3/4, ficha do modelo | Pessoa 2 confere SQL e tempos; pessoa 4 confere avaliação |
| 2 · Backend e SQL | Esquema/carga, inferência via API, transações e revisões | Etapas 3/4/6 | Pessoa 1 confere atributos; pessoa 3 testa jornada |
| 3 · Interface e demonstração | Streamlit/Plotly, filtros, fila, explicações e apresentação | Etapas 6/7 | Pessoa 2 confere respostas; pessoa 4 revisa clareza e ausência de resultados fictícios |
| 4 · GenAI, qualidade e infraestrutura | Contexto/prompts, falhas/fidelidade, testes e Terraform | Etapas 5/7 | Pessoas 1/2 conferem fatos; pessoa 3 confere fallback |

Artigo, slides, decisões éticas e defesa são compartilhados. Registrar divergências de escopo antes dos experimentos e integrar pequenas entregas revisáveis no Git. Não duplicar regras de atributos entre backend e tela.

## Próximas etapas e critérios de passagem

1. **Etapa 3:** obter os cinco CSVs do ZIP já recebido, validar hashes, auditar/limpar/agregar com Pandas, carregar SQLite, produzir EDA e congelar protocolo temporal. Não treinar nesta etapa.
2. **Etapa 4:** registrar protocolo, executar baselines/logística/árvores, selecionar no desenvolvimento, avaliar teste uma vez e salvar inferência. Relatar resultado ruim se ocorrer.
3. **Etapa 5:** implementar relatórios por API com base de conhecimento, testar chamada real, fidelidade e degradação. Chave ficará no ambiente local.
4. **Etapa 6:** integrar API, banco e interface e percorrer a jornada com pedidos reais.
5. **Etapa 7:** provisionar com Terraform, validar reprodução, concluir artigo/slides/BPMN, ensaiar até 20 min e preparar backup/entrega remota.

Executar integralmente uma etapa quando solicitada, sem avançar automaticamente. A aprovação da proposta e da base já ocorreu; não repeti-la. Credenciais/destino remoto só serão solicitados se indispensáveis à etapa correspondente.

## Riscos e mitigação

| Risco | Resposta planejada |
|---|---|
| Pouca discriminação ou instabilidade temporal | Comparar referências, mostrar erros e incerteza, evitar promessas; não alterar teste para melhorar nota |
| Snapshot sem histórico de atributos | Documentar hipótese; evitar campos posteriores; restringir conclusão à coorte histórica |
| Rótulos apenas dos entregues | Exibir cobertura/exclusões; não extrapolar a cancelados/perdas |
| LLM fora do ar ou sem chave | ML/painéis independentes, resumo factual e aviso; chamada real fica pendente até acesso |
| Ferramentas de infraestrutura indisponíveis | Docker client detectado, Engine sem conexão e Terraform ausente; resolver antes da etapa 7 |
| Prazo e equipe | Priorizar MVP; não incluir distância geográfica, histórico por vendedor ou agentes inicialmente |

Data da banca não informada. Planejar entrega com pelo menos 48h de antecedência, conforme guia; reservar ensaio da equipe e revisão dos arquivos finais. Não converter essa recomendação em prazo fictício.
