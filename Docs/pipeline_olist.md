# Pipeline Olist: vendedor único, CTGAN e simulação

## Integração e preservação

O mapa anterior às alterações está em `auditoria_pipeline_olist.md`.
`src/dados_vendedor_unico.py` reutiliza `ler`, `validar_chave`,
`coordenadas_por_cep`, `resumir_itens`, `adicionar_tempos_e_alvos`,
`selecionar_coorte`, `separar_por_tempo` e `limpar_atributos`. As extensões das
funções antigas são parâmetros opcionais; os defaults e os consumidores
legados permanecem compatíveis. Não há escrita no PostgreSQL nem troca do
modelo servido pela API.

O contrato real contém 90.167 pedidos nesta fonte. A população é retrospectiva
de entregues com datas confiáveis. Cancelados, entregas não observadas,
aprovações inválidas, ausência de itens e rótulos ainda indisponíveis no corte
são excluídos conforme as rotinas existentes. O filtro bruto exige exatamente
um seller distinto e nenhum item com seller ausente; conserva vários itens.

As partições originais têm cortes em **01/01/2018** e **01/05/2018**, com purga
de entregas ainda não observadas nos cortes. Não houve nova divisão aleatória
ou 70/15/15. O relatório apresenta perdas e prevalência antes/depois do filtro.

O novo alvo é `order_delivered_customer_date > order_estimated_delivery_date`,
como solicitado. No legado a comparação normaliza para dias. Os arquivos
anteriores e seus rótulos ficam intactos; a nova base nasce dos timestamps
originais, com divergências contabilizadas. O prazo continua sendo a diferença
entre os dias da promessa e da aprovação, disponível antes da entrega.

## Ambiente e comandos

Na máquina inspecionada, `.venv` não tinha dependências e `.venv-ctgan` continha
binários NumPy incompatíveis com Python 3.12. Foi criado `.venv-pipeline`, sem
sobrescrevê-los. Em outra máquina, a partir da raiz:

```powershell
python -m venv .venv-pipeline
.\.venv-pipeline\Scripts\python.exe -m pip install -r requirements-ctgan.txt
```

O pipeline usa CTGAN 0.13.0, RDT 2.1.0 e Pandas 2.3.3, coerentes com o arquivo
de requisitos CTGAN existente. Versões efetivas, seeds, hashes dos CSVs, código
e configurações são registrados nos artefatos. A execução é CPU, com número de
threads configurável. Reprodutibilidade entre plataformas/versões de PyTorch
não é garantida apenas pela seed.

Cada etapa pode ser executada separadamente, na ordem abaixo. `all` executa
as nove primeiras, sem executar a EDA. Os caminhos de dados/configuração são
relativos à raiz do repositório; os originais não são baixados ou substituídos.

```powershell
$pythonPipeline = '.\.venv-pipeline\Scripts\python.exe'
$configPipeline = 'config/olist_ctgan.json'
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step audit
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step clean-single-seller
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step enrich
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step ctgan-train
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step ctgan-generate
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step simulate
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step ml-prepare
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step ml-train
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step evaluate
& $pythonPipeline -m src.pipeline_olist --config $configPipeline --step eda
```

Edite uma cópia da configuração e escolha outro `run_id` para novos cenários.
Uma execução com fontes/configuração diferentes não pode reutilizar o mesmo
identificador. Depois da avaliação final, novo treino exige outra execução.
Repetir `evaluate` apenas lê o resultado registrado, desde que os hashes
coincidam. Não usar resultados do teste para retunar coeficientes ou doses.

O padrão prevê **300 épocas e 10.000 sintéticos**. Uma rodada reduzida deve
ser identificada como validação técnica, e não como evidência de convergência
da CTGAN. Falha de amostragem salva as contagens de rejeição e não exporta um
lote incompleto como se tivesse a quantidade solicitada.

## Contratos e tipos

Listas exatas e ordem vivem em `src/contratos_olist.py`, e são verificadas
antes de exportar. Referência completa: `Skills/olist-ctgan-pipeline/CONFERIR_COLUNAS.md`.

| Artefato em datasets/ | Colunas | Uso |
|---|---:|---|
| pedidos_ml_limpo_enriquecido.parquet | 23 | A: reais, 5 metadados + 17 atributos + alvo |
| ctgan_treino_features.parquet | 15 | B: tabela efetivamente passada a CTGAN.fit, codificação técnica |
| pedidos_sinteticos.parquet | 23 | C: mesma ordem de A, origem sintetico_ctgan e alvo simulado |
| pedidos_ml_filtrado.parquet | 23 | D: 4 metadados + 18 features + alvo |

A/C em ordem:

```text
order_id, seller_id, particao, order_approved_at,
customer_state, seller_state, categoria_principal,
quantidade_itens, quantidade_produtos, quantidade_categorias,
valor_itens, valor_frete, peso_total_g, volume_total_cm3,
distancia_vendedor_cliente_km, prazo_prometido_dias,
nota_historica_vendedor_media, qtd_avaliacoes_historicas_vendedor,
frequencia_avaliacoes_baixas_vendedor,
preco_medio_item, proporcao_frete_valor, atrasou, origem_dado
```

B em ordem: de `customer_state` até `frequencia_avaliacoes_baixas_vendedor`
na lista acima (15 campos). Sem IDs, data, mês, rótulo ou razões.

D em ordem: `order_id, seller_id, particao, origem_dado`, seguidos de X abaixo,
seguidos por `atrasou`:

```text
customer_state, seller_state, distancia_vendedor_cliente_km,
categoria_principal, quantidade_itens, quantidade_produtos,
quantidade_categorias, peso_total_g, volume_total_cm3,
nota_historica_vendedor_media, qtd_avaliacoes_historicas_vendedor,
frequencia_avaliacoes_baixas_vendedor, valor_itens, preco_medio_item,
valor_frete, proporcao_frete_valor, prazo_prometido_dias, mes_aprovacao
```

IDs e controles são strings; aprovação é datetime sem timezone como na fonte;
contagens são inteiros; valores, distâncias, razões, nota e frequência são
numéricos; alvo é binário. As UFs são validadas. Exige-se
`itens >= produtos >= categorias >= 1`; valores físicos não negativos;
histórico positivo com nota 1..5 e frequência 0..1. Razões são recalculadas:
valor/itens e frete/valor; valor zero resulta em proporção nula.

Não entram nos contratos flags de falta, pagamentos, latitude/longitude,
quantidade de vendedores/UFs, distâncias plurais, dados pós-entrega, `rotulo_*`,
`experimento_id`, probabilidade simulada ou transportadoras fictícias.

## Tratamento e histórico

- Filtro e mapeamento 1:1 a partir de `order_items`, antes da agregação.
  UF vem de `sellers`; as distâncias média/máxima antigas são conferidas no
  caso singular. Haversine usa medianas por CEP, com o retângulo geográfico
  conservador já adotado no projeto. Distâncias são aproximadas, não rodoviárias.
- Categoria ausente torna-se `nao_informado`, contando como uma categoria
  distinta. Categoria predominante mantém o desempate alfabético do legado.
- Medianas/modas são aprendidas apenas no treino real. O relatório separado
  registra ausências, valores inválidos, estatísticas e ajustes geográficos.
  Peso/volume parcial permanece ausente antes da imputação, como no legado.
- Reviews por pedido são proxies de experiência com o seller, não medida
  pura de sua qualidade. Só entram pedidos de um vendedor. Identidades
  `review_id` com pedidos/notas conflitantes são excluídas; duplicatas válidas
  são deduplicadas pela identidade, usando a primeira resposta válida.
- Resposta exige data válida, posterior à aprovação de origem e não anterior
  à criação da review. Para cada pedido-alvo usa-se **resposta < aprovação**,
  via busca binária/cumulativas. Nota 3 conta como baixa. A review própria
  não entra. Não há imputação de respostas ausentes por data de criação.
- Eventos reais de outros splits só são usados quando já disponíveis na
  data-alvo. Não se inserem reviews sintéticas nos históricos reais.
- Sem eventos: contagem zero e nota/frequência nulas. B representa essas
  ausências com 0 na nota e -1 na frequência, internamente, e aplica log1p
  reversível às grandezas positivas e à contagem de reviews. Na saída,
  contagem zero restaura os nulos; valores inválidos são rejeitados.

## Geração, cenários e comparação

CTGAN recebe as 15 colunas de todos os reais de treino, incluindo ambas as
classes sem passar o alvo. Geração não utiliza os experimentos legados de
positivos/CTGAN condicional. Contagens de itens/produtos/categorias são
discretas; reviews são arredondadas após transformação inversa.

Validação rejeita domínio inválido, extremos fora do suporte do treino,
categorias desconhecidas e cópias/duplicatas. Quotas por 1, 2 e 3+ itens
preservam as proporções medidas no treino, com arredondamento de até uma
linha. Não se corrigem extremos por clipping. Relatórios mostram candidatos,
rejeições, excesso por estrato, quantis, KS, correlações, contingências,
condicionais e vizinhos próximos numa referência de até 5.000 reais de treino.

Um catálogo de perfis UF/histórico extraído do treino só é reutilizado quando
o perfil gerado coincide integralmente; seus IDs são pseudônimos. Sem
correspondência, cada pedido recebe um seller sintético exclusivo. Esse
fallback não representa recorrência real nem uma série observada de reviews.
Datas são amostradas do treino com seed; não comprovam o histórico do seller
fictício. As dependências com calendário podem enfraquecer e são reportadas.

O simulador tem coeficientes explícitos, escalas ajustadas no treino,
intensidade, ajuste de confiança pela contagem de reviews e intercepto
calibrado para probabilidade média de 1/6 nos sintéticos. O sorteio Bernoulli
pode produzir taxa observada diferente; modo exato usa sorteio ponderado sem
reposição. Scores/probabilidades ficam apenas em `reports/`.

ML usa regressão logística, já presente nos experimentos do projeto.
Preprocessador sem flags é ajustado somente no treino real; os candidatos
compartilham essa escala. Doses/pesos são comparados por average precision
na validação real; limiar usa F1 dessa validação. Se não houver sintéticos
suficientes para uma dose, a dose efetiva é limitada ao lote, registrada e
deduplicada na comparação. A avaliação final compara baseline e melhor
aumentado no mesmo teste real. AP, ROC-AUC, precision, recall, F1, Brier,
confusão, suporte e prevalência são salvos. Um resultado pior também é
reportado. O experimento não demonstra causalidade nem ganho em produção.

## Inferência e EDA

O modelo salvo contém pipeline, lista ordenada de 18 features e limiar.
`src/ml_vendedor_unico.py:preparar_features_inferencia` recebe pedidos
pré-entrega já agregados de um seller (mesma agregação/geografia da limpeza),
aplicando as estatísticas de `tratamento_historico.json` e a função as-of
compartilhada. Recebe eventos reais de reviews e o mapeamento bruto validado;
não requer status final nem datas de entrega. `prever_pedido_enriquecido`
deriva mês, seleciona exatamente X, valida o domínio e produz scores.
O caller deve rejeitar pedidos multi-seller antes dessa agregação.

EDA lê apenas A/C e escreve tabelas de itens, faixas de atributos, atraso e
histórico em `eda/`. Não altera os datasets nem executa outra limpeza.

## Artefatos de auditoria

`manifesto.json` guarda configuração/fontes/versões; `reports/etapas.json`
registra etapas concluídas e hashes de código. Relatórios principais:
`filtro_um_vendedor.md`, `auditoria.json`, `tratamento_historico.json`,
`ctgan_fit.json`, `geracao.json`, `qualidade_sintetica.json`, `simulacao.json`,
`probabilidades_simuladas.parquet`, `contratos.json`, `metricas_validacao.csv`,
`selecao.json`, `metricas_teste.csv` e `avaliacao_final.json`.

Arquivos volumosos ficam fora do Git. Os dados originais, CSV ML antigo,
notebooks, Joblib antigo e modelos da aplicação não são sobrescritos.
