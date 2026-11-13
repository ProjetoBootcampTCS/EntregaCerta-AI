# CTGAN por perfis de referência, sem aprendizado da Olist

A instrução mais recente do usuário substitui, **somente neste novo modo**,
a exigência anterior de treinar CTGAN na Olist. Os contratos continuam
A/C=23, B=15, D=23 e X=18. O fluxo anterior não foi alterado, inclusive
a configuração `config/olist_ctgan.json` modificada pelo usuário.

Configuração: `config/ctgan_perfis_referencias.json`.
Implementação: `src/ctgan_perfis_referencias.py`.

## O que as referências sustentam

- [Correios: encomendas nacionais](https://www.correios.com.br/enviar/encomendas/nacional/nacional):
  preços dependem de peso, dimensões e CEPs; existe prazo contratado por serviço.
- [Correios: preços e prazos](https://www2.correios.com.br/sistemas/precosPrazos/default.cfm):
  prazos variam conforme localidades de origem/destino.
- [CTGAN oficial](https://github.com/sdv-dev/CTGAN): o gerador aprende uma tabela
  com `fit` e amostra linhas com `sample`.

Essas fontes **não publicam as probabilidades de atraso adotadas aqui** e não
demonstram que frete baixo, preço alto ou notas ruins causem atraso. As páginas
consultadas são atuais; não são uma reconstrução das tarifas/regras de 2016–2018.
As referências e os limites de cada uma estão registrados no JSON.

## Perfis iniciais, inteiramente hipotéticos

| Perfil | Participação | Probabilidade de atraso | Prazo prometido |
|---|---:|---:|---:|
| Baixo | 60% | 5% | 20–45 dias |
| Médio | 30% | 20% | 10–25 dias |
| Alto | 10% | 60% | 2–12 dias |

Todos esses números são parâmetros de cenário, não estimativas da Olist.
A taxa esperada da mistura é 15%; o sorteio Bernoulli pode produzir outra
taxa observada. Peso, volume, valor unitário, proporção do frete, itens,
rotas e históricos têm distribuições explícitas e ajustáveis no JSON.
Perfis sobrepõem atributos: baixo risco não significa atraso impossível.

As rotas exemplificativas usam SP como origem e SP/RJ/MG/BA/AM como destinos.
Os intervalos de distância são aproximações hipotéticas; não são distâncias
geocodificadas de pedidos reais. Essa cobertura limitada não representa
todo o Brasil. Categorias são um vocabulário manual compatível com o schema;
frequências não foram extraídas da Olist. Categorias/UFs reais desconhecidas
são tratadas pelo encoder com `handle_unknown='ignore'`.

## Fluxo e isolamento

1. `seed`: gera 2.000 exemplos artificiais por perfil usando somente JSON e
   seed. Nenhum CSV, Parquet ou gerador aprendido na Olist é consultado.
2. `ctgan-train`: verifica a população contra a geração determinística do JSON
   e treina uma CTGAN por perfil nas **mesmas 15 colunas**. IDs, calendário,
   perfil, alvo e probabilidades nunca entram no fit. Treino padrão: 10 épocas.
3. `generate`: amostra 10.000 pedidos distribuídos pelos três perfis; rejeita
   domínio, faixa e rota inconsistentes e cópias da população inicial.
   Perfil define a probabilidade Bernoulli do rótulo, guardada em relatório
   separado. Não há clipping silencioso nem lote parcial exportado.
4. IDs são exclusivos no namespace `ctgan_order_`/`ctgan_seller_`. Datas são
   sorteadas uniformemente entre 01/01/2016 e 31/12/2018. As razões são
   recalculadas. C tem exatamente as mesmas 23 colunas de antes.
5. `ml-train`: deriva mês apenas no D; ajusta imputação, encoder, scaler e
   regressão logística exclusivamente em 80% dos sintéticos. Os outros 20%
   servem ao limiar F1. Esse holdout é interno, sem alterar os contratos que
   marcam sintéticos como treino. Não há refit depois de selecionar o limiar.
6. `evaluate`: só após salvar o preditor, abre a base Olist já enriquecida,
   calcula previsões e métricas sem fit/seleção nos reais. Reporta todos os
   90.167 pedidos e cada partição original separadamente.

Os históricos sintéticos são **resumos hipotéticos anteriores**, não eventos
de avaliações reais. A população inicial usa contagens de notas fictícias;
count=0 preserva média/frequência nulas. As amostras CTGAN são resumos contínuos,
com validação de limites e compatibilidade entre média e frequência baixa;
não representam uma sequência real de reviews. Cada seller sintético exclusivo
evita sugerir recorrência ou série histórica observada.

A avaliação reaproveita a limpeza real existente, inclusive suas estatísticas
de imputação e históricos as-of documentados. Isso é processamento dos inputs
de avaliação, não aprendizado do gerador ou do novo preditor. O arquivo real
não é aberto nas etapas seed, fit da CTGAN, geração ou fit do preditor.
O campo `evaluation_real` apenas identifica sua localização para avaliação.

O modelo aprenderá principalmente as hipóteses impostas, e pode funcionar mal
nos reais. Holdout sintético não prova generalização. A Olist já foi avaliada
em experimentos anteriores nesta conversa; resultados novos são exploratórios,
não teste independente nunca consultado. Não ajustar os perfis pelos resultados
reais sem declarar que se passou a usar a Olist para seleção de hipóteses.

## Execução

```powershell
.\.venv-pipeline\Scripts\python.exe -m src.ctgan_perfis_referencias --step all
```

Etapas isoladas: `seed`, `ctgan-train`, `generate`, `ml-train`, `evaluate`.
Use `--config caminho.json` para outro cenário. Alterar parâmetros exige
outro `run_id`; executar novamente sobre experimento já avaliado é recusado.
Para GPU NVIDIA compatível, configure `ctgan.enable_gpu=true` **neste JSON**;
CUDA precisa estar disponível no PyTorch ou o comando falha explicitamente.

Saídas em `artifacts/ctgan_perfis_referencias/<run_id>/`: populações iniciais,
modelos e tabelas de fit por perfil, `pedidos_sinteticos.parquet` e `.csv`,
`pedidos_ml_filtrado.parquet`, `perfis_probabilidades.parquet`, `geracao.json`,
`preditor_sintetico.joblib`, `validacao_sintetica.json`, `metricas_reais.csv`,
`previsoes_olist.parquet`, manifesto e hashes. Nenhum arquivo legado é substituído.

Testes:

```powershell
.\.venv-pipeline\Scripts\python.exe -m unittest discover -s tests -p test_ctgan_perfis_referencias.py -v
```

## Execução realizada em 13/11/2026

Executado `perfis_referencias_v1`: três CTGANs de 10 épocas, cada uma treinada
em 2.000 exemplos procedurais. Gerados **10.000 pedidos, 1.552 atrasados (15,52%)**:

| Perfil | Pedidos | Atrasados | Taxa observada |
|---|---:|---:|---:|
| Baixo | 6.000 | 325 | 5,42% |
| Médio | 3.000 | 614 | 20,47% |
| Alto | 1.000 | 613 | 61,30% |

As taxas observadas diferem das probabilidades pelo sorteio Bernoulli.
Preditor ajustado em 8.000 sintéticos; limiar escolhido em 2.000 sintéticos.
AP no holdout sintético: 0,46290; F1: 0,50078.

Na Olist completa (90.167 pedidos), AP=0,08413, ROC-AUC=0,52995 e F1=0,11692.
Na partição original de teste (25.120 pedidos), AP=0,10142, ROC-AUC=0,63197
e F1=0,16040. Os perfis hipotéticos generalizaram pouco para os reais.
Nenhum parâmetro foi reajustado após consultar essas métricas.

A rodada curta também foi ineficiente na geração: rejeição de **98,84% a
99,19%** dos candidatos por domínio/faixa/rota/coerência de histórico. Foram
necessários 536.000, 350.433 e 126.880 candidatos por perfil. A primeira
estratégia de lotes não completou o perfil baixo; a reamostragem passou a
dimensionar lotes pela taxa de aceitação, mantendo as mesmas restrições,
configuração, seeds e modelos. Não houve cópias/duplicatas aceitas detectadas.
Isso não demonstra fidelidade das distribuições pretendidas: é uma execução
técnica do cenário, com rejeição alta explicitamente registrada.

O arquivo do usuário `config/olist_ctgan.json` foi preservado. Um teste do
fluxo anterior foi corrigido para comparar a taxa obtida com a taxa configurada
(atualmente 0,1667), em vez de assumir rigidamente 1/6.

Passaram 7 testes novos e os 20 testes do pipeline anterior, além da
verificação dos contratos/IDs, cobertura dos 36 meses e separação 8.000/2.000.
