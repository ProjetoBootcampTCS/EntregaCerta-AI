# Registro de decisões

30/10/2026 · decisões da etapa 2, revisáveis com justificativa e versão.

| Decisão | Motivo | Consequência e limite |
|---|---|---|
| Olist e previsão na aprovação | Fonte real aceita; desfecho observável por datas | Estudo retrospectivo de 2016–2018, restrito aos entregues elegíveis |
| Atraso por dia civil | Promessas à meia-noite não representam limite intradiário | Entrega no mesmo dia é pontual; testar fronteiras na etapa 3 |
| Um pedido por linha | Vários itens/vendedores não são amostras independentes | Agregar antes das junções e conferir cardinalidade |
| 19 atributos declarados | Manter decisão explicável e impedir entradas posteriores | Tipagem e cálculo auditados na 3; imputação no treino na 4 |
| Divisão temporal com rótulo conhecido | Evitar treinar usando entregas que ainda não ocorreram no corte | Datas finais e exclusões de maturação congeladas antes de modelos |
| Fila diária, 10% como hipótese inicial | Traduzir escore em capacidade de revisão verificável | Sensibilidade 5/20%, nenhuma capacidade empresarial medida; sem limiar mágico |
| Logística e Random Forest | Comparação linear/não linear com sklearn e CPU | Ajustes somente no desenvolvimento; ainda não executados |
| FastAPI + Streamlit + SQLite | Backend/frontend explícitos, Python comum e pouca operação | Dois processos da mesma aplicação; API é responsável pelo banco |
| Python 3.12 isolado e dependências fixadas | Ambiente anterior de outro projeto não garante reprodução | `.venv` sem pacotes do sistema; lock Windows/Python 3.12 |
| Prompts diretos com fatos e conhecimento curto | Relatório delimitado, contexto pequeno, evidências controláveis | RAG só se necessidade de recuperação for demonstrada; sem agentes iniciais |
| GenAI opcional no fluxo | Painéis e ML não devem depender de API externa | Fallback factual com aviso e revisão humana; exige teste real na 5 |
| Terraform com Docker local | R10 exige infraestrutura automatizada; nuvem paga é desnecessária | Provisionamento real na 7; Engine/CLI precisam estar disponíveis |
| Repositório local próprio | Evitar misturar EntregaCerta com protótipos anteriores | Metadados ficam dentro do projeto; remoto definido para entrega final |

## Ética, privacidade e limites

Não usar o escore para punir vendedores, cancelar pedidos ou alegar culpa. Região, categoria e frete podem refletir diferenças operacionais e amostrais; avaliar por segmento com tamanho e incerteza, sem atribuir causalidade. Não demonstrar segurança de grupos apenas por métrica agregada. Não há atributos suficientes para medir todas as formas de viés.

Reduzir contexto enviado à API a fatos necessários, sem IDs de cliente ou geografia precisa. Dado público anonimizado ainda exige minimização e cumprimento das condições de uso. Preservar atribuição e CC BY-NC-SA 4.0 da fonte. Não redistribuir automaticamente ZIP/banco no repositório. Avaliar termos do provedor escolhido e retenção de conteúdo na etapa 5.

Métricas e explicações são associativas e históricas. A LLM pode alucinar mesmo com contexto: validação, abstenção e revisão reduzem risco, sem garantir ausência de erro. Ganho de precisão na fila não demonstra redução causal de atrasos. ROI depende de hipóteses e piloto real. Contratos de disponibilidade de atributos são explícitos porque a fonte não contém histórico de versões.
