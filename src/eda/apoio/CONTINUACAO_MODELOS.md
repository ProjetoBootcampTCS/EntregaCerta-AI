# Estudo ativo: modelos de atraso — 16/11/2026

Pedido: comparar modelos/pipelines e regiões/distâncias no notebook
`src/eda/02_comparacao_modelos_atraso.ipynb`, buscar F1 da classe atrasado >= 0,5,
documentar referências e resultados reais e concluir mesmo após interrupção de contexto.

## Continuidade

A tarefa contínua está registrada no chat. Salvar cada experimento concluído em
`.cache/eda_modelos_20261116/`; retomar verificando os hashes das fontes/configuração.
Não repetir treinos cujo checkpoint esteja concluído e corresponda aos mesmos dados.
Não programar automação recorrente: os checkpoints e a tarefa contínua atendem à retomada.

## Protocolo planejado

- Preservar CSVs tratados, scripts do pipeline principal, web e assistente.
- Cortes atuais: validação em 01/03/2018; teste em 01/05/2018.
- Meta alterada explicitamente pelo usuário: F1 MACRO >= 0,5; limiares/modelos escolhidos na validação.
- Exportar somente mae_dias, rmse_dias, r2_dias, mae_dias_atrasados, tn, fn, tp, fp, recall,
  precision, accuracy, limiar, f1_macro, f1_micro e metadados de execução/partição/modelo/segmento/contagens.
- Não perseguir F1 no teste trocando configurações depois de observar o resultado.
- Cenário atual é diagnóstico retrospectivo (status final e nota global têm informação futura).
- Comparar aprovação, despacho e monitoramento anterior ao prazo; não misturar populações/horizontes ao afirmar ganho.
- Validar modelos lineares, árvores/ensembles, boosting, desbalanceamento, regiões com fallback e pipelines.
- Experimentar geração sintética somente a partir do treino e avaliar ganho em pedidos reais.
- Distinguir rótulos pelas datas de rótulos PLN. Teste real observado é a referência operacional.
- Se F1 >= 0,5 não for atingido no horizonte antecipado, informar sem fabricar resultado.

## Entregas

- Notebook executado e documentado ao lado do notebook geográfico.
- Um CSV consolidado de resultados em `Dados/resultados_modelos/`.
- Modelos/pipeline selecionados e gráficos que permitam reutilização e auditoria.
- Conclusão clara: melhor alternativa por horizonte, cobertura, limitações e F1 real.

Estado: treinos de classificação, expansão, especialistas, ensembles e CTGAN concluídos;
regressões em andamento, teste ainda não pontuado neste registro. 21 testes do pipeline passaram.
Código provisório completo em `.cache/estudo_atrasos_engine.py` e
`.cache/estudo_atrasos_extensoes.py`; incorporar as funções no notebook final.
Logs: `.cache/expansao_atrasos.log`, `.cache/ctgan_atrasos.log`, `.cache/conclusao_atrasos.log`.
Cada modelo tem joblib, JSON e scores de treino/validação.
Atualizar limiares dos checkpoints para macro sem repetir ajuste dos estimadores.

Notebook já criado com 33 células documentadas: `src/eda/02_comparacao_modelos_atraso.ipynb`.
Gerador provisório `.cache/gerar_notebook_modelos.py` incorpora todo o código dos scripts
`.cache/estudo_atrasos_{engine,extensoes,sinteticos,avaliacao}.py` e as conclusões/gráficos de
`.cache/notebook_modelos_resultados.py`. Regerar antes da execução final se ajustar o código.
O processo `.cache/concluir_estudo_atrasos.py` conclui regressões, congela a seleção e pontua
o teste automaticamente. Retomá-lo reaproveita checkpoints. Não interromper apenas por compaction.
Ainda falta: aguardar conclusão, executar notebook com nbclient (kernel entregacerta-eda),
verificar plots/saídas, corrigir eventuais falhas, atualizar README e relatório final.

Nova solicitação: auditar integração (sem alterar web). Evidência: banco.py lê
Dados/pedidos_ml.csv e view usa esquema antigo; src/ml/inferencia.py carrega
preprocessador_rede.joblib + rede_neural.pt; API/assistente usam esses scores antigos.
Não há consumidor do novo CSV de métricas, nem carregamento dos modelos da comparação.
Avaliação principal src/3_avaliar_modelos.py já foi simplificada às métricas solicitadas.
