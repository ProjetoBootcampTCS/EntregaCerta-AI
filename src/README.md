# Código do projeto

| Pasta | Responsabilidade |
|---|---|
| `configuracoes/` | `1_dados.json`: dados/transportadoras/PLN; `2_treinamento.json`: modelos, CTGAN e cenários. |
| `1_preparar_dados.py` | Execute primeiro: merge, engenharia, PLN e exportação de `dataset_ml.csv`. |
| `1_pln.py` | Auxiliar chamado pela preparação, sem execução manual. |
| `2_dados_treino.py`, `2_ctgan.py`, `2_catalogo_modelos.py` | Auxiliares de validação/divisão, geração sintética e catálogo de modelos. |
| `2_treinar_modelos.py` | Execute após revisar os dados: treina CTGAN e modelos em loop e gera o CSV de métricas. |
| `3_avaliar_modelos.py` | Execute por último para consultar os resultados; contém as funções de métricas usadas no treino. |
| `eda/` | `01_atrasos_geograficos.ipynb`, `02_comparacao_modelos_atraso.ipynb`, gráficos e estudos de localização. |
| `ml/` | Inferência do modelo da aplicação web, preservada. |
| `postgresql/` | Carga, consultas e SQLs do banco. |
| `web/` | API, login, loja e consulta de pedidos. |
| `assistente/` | GenAI, conversas e feedback. |
| `relatorios/` | PDF do dashboard. |
| `experimentos/pipeline_anterior/` | Pré-processamento ainda necessário à inferência web e ao EDA, preservado. |

Na raiz: `python src/1_preparar_dados.py`; depois da sua revisão,
`python src/2_treinar_modelos.py --nome estudo_01` e
`python src/3_avaliar_modelos.py --nome estudo_01`.
Os nove arquivos do pipeline são os sete Python numerados e os dois JSON;
os outros módulos pertencem às funcionalidades preservadas.

O restante do pipeline anterior e dos estudos foi movido para `../lixeira/src/`. A aplicação
web ainda usa seu modelo anterior até uma substituição explícita, após o novo treino.
O desempenho fica em `Dados/resultados_modelos/<execucao>.csv`, um arquivo por
rodada e sem subpastas; os modelos novos ficam em `Modelos/comparacao_modelos/<execucao>/`.

As métricas são `mae_dias`, `rmse_dias`, `r2_dias`, `mae_dias_atrasados`, `tn`, `fn`,
`tp`, `fp`, `recall`, `precision`, `accuracy`, `limiar` e `f1`.
Modelo e limiar são escolhidos pelo F1 da validação. F1, precision e recall usam
a classe atrasado (1): `f1 = 2 * tp / (2 * tp + fp + fn)` (zero se o denominador for zero).
Os demais campos identificam execução, cenário, modelo, partição, segmento e
quantidades avaliadas. Dias ausentes ficam fora apenas das métricas de regressão.

## Calendário da entrega à transportadora

`1_preparar_dados.py` calcula as features abaixo tanto na engenharia nova quanto
ao reutilizar um engineering já tratado. As datas originais são ligadas por
`order_id`; a entrega efetiva ao cliente não participa desses cálculos.

| Feature | Significado |
|---|---|
| `delivered_to_carrier_minus_estimative_in_days` | Despacho menos estimativa, em segundos / 86.400. `-2` = dois dias antes; `+2` = dois dias depois. Preserva frações. |
| `delivered_to_carrier_week_day` | `segunda-feira`, `terça-feira`, ..., `domingo`. |
| `delivered_to_carrier_is_holiday` | 1 se o dia do despacho é feriado do calendário brasileiro; 0 caso contrário. |
| `delivered_to_carrier_to_estimative_holidays` | Número de datas de feriado após o dia do despacho, até o dia estimado inclusive. |
| `delivered_to_carrier_to_estimative_business_days` | Dias úteis após o dia do despacho, até o dia estimado inclusive. |
| `delivered_to_carrier_days_until_next_business_day` | Dias corridos até o primeiro dia útil estritamente posterior ao despacho. Sexta → segunda = 3; se segunda for feriado, sexta → terça = 4. |

O engineering também contém `delivered_to_carrier_to_estimative_holiday_dates`,
uma lista JSON com datas e nomes dos feriados contados, apenas para auditoria.
Ela não entra no treino. Intervalos vencidos ou vazios têm zero dias úteis
restantes e zero feriados; a diferença assinada preserva o prazo já ultrapassado.
Datas ausentes ou inválidas permanecem ausentes nas features que dependem delas.

O calendário usa [`holidays`, país BR, categoria PUBLIC](https://holidays.readthedocs.io/en/latest/auto_gen_docs/brazil/),
sem subdivisão e sem transferência automática para outro dia. Inclui
Sexta-feira Santa, conforme a convenção da biblioteca, e respeita a vigência por
ano: 20/11 só é nacional a partir de 2024. Não inclui feriados estaduais/municipais,
Carnaval, Corpus Christi ou outros pontos facultativos. A versão instalada e as
regras ficam em `Dados/datasets_preparacao.json`.

Dias úteis são uma **aproximação operacional**: segunda a sexta sem feriados,
usando as datas locais registradas na Olist. A contagem exclui o dia parcial do
despacho e inclui todo o dia prometido, mesmo quando o timestamp da estimativa
está à meia-noite. Não presume horário de corte, operação aos sábados ou emendas.
Feriado no fim de semana não desconta um dia útil adicional. Por exemplo, um
despacho na sexta com prazo no domingo tem zero dias úteis posteriores disponíveis.

Para atualizar apenas essas features nos CSVs existentes:

```powershell
.\.venv-pipeline\Scripts\python.exe src/1_preparar_dados.py --somente-calendario
```

O comando mantém linhas, ordem, alvos, partições e demais colunas; salva backup em
`Dados/experimentos/antes_preparacao_<data>/`. `--somente-particoes` continua
atualizando exclusivamente as partições. A dependência `holidays` está em
`requirements.txt` e já foi instalada no ambiente `.venv-pipeline` deste computador.

As seis features estão disponíveis no contrato. O JSON de treinamento seleciona
somente a diferença em dias, o dia da semana e a contagem de feriados, além dos
atributos anteriores. O dia da semana
entra no `OneHotEncoder` existente, ajustado dentro de cada pipeline somente no
treino; não se impõe uma ordem numérica entre os dias. CTGAN trata a semana e as
contagens/indicador de feriado como discretas para não gerar contagens fracionárias.
Como gera features conjuntamente sem timestamps, ainda pode criar combinações
incoerentes entre calendário e prazo; cenários sintéticos exigem inspeção.

`excluir_sem_data_transportadora: true` restringe o carregamento para treino aos
pedidos com despacho conhecido **quando há features de calendário selecionadas**.
Não modifica os CSVs e registra a quantidade excluída em `preparacao.json`.
Com a opção desligada, valores ausentes continuam causando o erro de validação
existente. Ausências em outros campos não são imputadas nem descartadas por ela.

Essas features são válidas para previsão **a partir da entrega à transportadora**,
pois antes disso o despacho real ainda é desconhecido. A comparação atual continua
retrospectiva: `order_status` final e o score global do vendedor também entram em X.
Para medir uso operacional, é necessário usar o status conhecido no instante da
previsão, estatísticas de vendedor calculadas só com o passado e cortes compatíveis
com a disponibilidade das features/rótulos. Para medir o ganho do calendário,
compare com/sem as seis features sobre os mesmos pedidos elegíveis, modelos e
cortes temporais, selecionando pelo conjunto de validação e avaliando no teste real.
Os modelos antigos não são retreinados pela atualização dos CSVs; use outro nome
de execução ao treinar a nova versão.

## PCA e K-fold no treinamento

O JSON de treinamento habilita `pca: {"ativado": true, "variancia": 0.95}` e
`kfold: {"ativado": true, "n_splits": 5, "limiar": 0.5}`. Ambos podem ser
desligados separadamente. Configurações antigas sem essas chaves mantêm o fluxo anterior.

O [PCA](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)
entra depois do scaler/encoder, dentro dos pipelines salvos de classificação e
regressão, retendo pelo menos 95% da variância. O número de componentes e a
variância efetiva ficam no CSV de resultados.

O [StratifiedKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedKFold.html)
avalia cada modelo em cinco folds exclusivamente do **treino real**, com semente
reproduzível. Scaler, encoder, PCA e estimadores são ajustados novamente dentro
de cada fold. A classificação usa limiar fixo 0,5 nesse diagnóstico; não otimiza
o limiar no fold avaliado. A regressão usa somente alvos de dias conhecidos.
O terminal mostra as métricas por fold e a média/desvio de F1 e MAE.

Os arquivos `kfold_particoes.csv`, `kfold_metricas.csv` e `kfold_resumo.csv` ficam
na pasta de modelos da execução. A etapa 3 também exibe o resumo de K-fold.
Esse diagnóstico compara os modelos no treino real; não mede a estratégia CTGAN.
Não reutiliza sintéticos nos folds, pois o gerador já viu todo o treino real.
Como os folds são embaralhados, não substituem a avaliação temporal: validação e
teste originais continuam separados, e a seleção final mantém a regra existente.

Para executar a nova configuração, escolha um nome novo:

```powershell
.\.venv-pipeline\Scripts\python.exe src/2_treinar_modelos.py --nome pca_kfold_01
.\.venv-pipeline\Scripts\python.exe src/3_avaliar_modelos.py --nome pca_kfold_01
```
