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
- F1 binário da classe 1; limiares/hiperparâmetros/grupos escolhidos na validação.
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

Estado inicial: fontes e configuração conferidas; referências sendo examinadas;
dependências de boosting em instalação; nenhum novo treino final executado ainda.
