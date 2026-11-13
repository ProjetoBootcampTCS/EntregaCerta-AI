# Resultado da implementação — 13/11/2026

Pipeline executado da auditoria à avaliação final, usando os CSVs presentes.
Execução: `validacao_tecnica_20261113`, em
`artifacts/olist_single_seller/validacao_tecnica_20261113/`.

## Dados e preservação

| Contrato | Linhas | Colunas |
|---|---:|---:|
| A: real limpo/enriquecido | 90.167 | 23 |
| B: entrada efetiva CTGAN, treino real | 40.710 | 15 |
| C: sintéticos validados/simulados | 2.000 | 23 |
| D: dataset para ML | 92.167 | 23 |

X tem exatamente 18 atributos antes de codificação categórica. Validação e
teste têm 24.337 e 25.120 pedidos, exclusivamente reais. Os arquivos originais
foram conferidos por hash; todos os novos alvos reais foram reconciliados
com os timestamps de entrega/promessa. Nenhum artefato legado foi sobrescrito.

O filtro bruto removeu 1.278 pedidos multi-seller (1,2852%) e 775 sem seller;
8.525 pedidos com múltiplos itens de um mesmo seller eram elegíveis ao filtro
bruto. As demais exclusões são de elegibilidade/purga temporal.
Detalhes por classe e split: [filtro_um_vendedor.md](filtro_um_vendedor.md).

O CSV legado tinha 44 colunas. Contagem de sellers e UF concordaram com as
fontes; suas duas distâncias já imputadas divergiam em 436 pedidos de seller
único. O código antigo imputava cada coluna separadamente. O novo fluxo
recalcula uma distância e imputa somente essa variável com estatística do
treino. Houve 1.292 diferenças de rótulo por entregas no dia prometido na
fonte, das quais 1.216 estão na coorte temporal comum ao legado.

Antes de imputar, A tinha 22 ausências de peso, 16 de volume e 436 de distância.
Não houve divergência de UF entre a agregação e o cadastro de vendedores.
O histórico utilizou 95.656 eventos de review únicos válidos; 789 identidades
ambíguas foram excluídas. 5.575 pedidos de A não tinham review anterior
(3.310 no treino): contagem zero, nota/frequência nulas.

## Rodada técnica de CTGAN

Foram usadas **10 épocas**, lote 500, camadas 128/128, CPU, seed 42;
geração seed 44, simulação seed 43 e ML seed 45. O padrão de 300 épocas
**não foi executado**. Para reproduzir esta rodada, copie
`config/olist_ctgan.json`, use o run_id acima, `ctgan.epochs=10`,
`synthetic.num_samples=2000` e `ml.synthetic_to_real_ratios=[0.025, 0.049]`.
A configuração exata local está em `artifacts/config_validacao_tecnica.json`.

Dos 8.000 candidatos, 3.737 foram rejeitados por domínio/suporte (46,71%);
2.263 válidos excediam as quotas dos estratos. Não houve cópias/duplicatas
aceitas. Foram retidos 1.817 pedidos de um item, 141 de dois e 42 de três
ou mais. 395 receberam pseudoperfil compatível; 1.605, seller exclusivo.

Probabilidade média simulada: **16,6667%**. Taxa Bernoulli observada:
**17,05% (341/2.000)**. Nenhum rótulo real foi simulado. Regerar com o
modelo salvo e mesmas seeds produziu C idêntico e o mesmo hash de D,
inclusive após reforçar a detecção de cópias contra ruído numérico.

Não há evidência de alta fidelidade nesta rodada curta: KS de frete **0,4004**,
valor dos itens **0,1736**, peso **0,1843**, distância **0,1012**. Variação total
de categoria **0,1722** e de UF do vendedor **0,1703**. Quantis, correlações,
condicionais, calendário e vizinhos próximos estão no relatório de qualidade.
Preservar estratos de itens não assegura preservar todas as distribuições.

## Comparação real

O melhor candidato aumentado na validação usou 1.018 sintéticos, peso 0,5.
Seu AP de validação foi **0,22253**, abaixo do baseline **0,22455**; portanto
o baseline continua sendo a escolha favorecida por essa validação.
Comparação final, com limiares fixados pelo F1 da validação:

| Métrica no teste real | Baseline real | Real + sintéticos selecionado |
|---|---:|---:|
| Pedidos / atrasos | 25.120 / 1.581 | 25.120 / 1.581 |
| Average precision | 0,15020 | 0,15240 |
| ROC-AUC | 0,74582 | 0,74734 |
| Precision | 0,11819 | 0,11738 |
| Recall | 0,72170 | 0,71853 |
| F1 | 0,20312 | 0,20179 |
| Brier | 0,05645 | 0,05638 |
| TN / FP / FN / TP | 15.026 / 8.513 / 440 / 1.141 | 14.997 / 8.542 / 445 / 1.136 |

AP aumentou 0,00220 no teste, enquanto precision, recall e F1 pioraram.
Resultado misto de uma rodada técnica, sem evidência de ganho robusto ou
causalidade. O modelo da aplicação permanece o anterior. Nenhum parâmetro
foi escolhido a partir desse teste.

## Testes e verificações

**41 testes passaram**, distribuídos entre ambientes compatíveis:

- 20 novos testes em `.venv-pipeline`: contratos, filtros, geografia,
  timestamp do alvo, histórico estrito, cópias, IDs, geração, simulação,
  seleção sem teste, inferência e EDA sem mutação.
- 16 testes legados de preparação, experimento e doses no mesmo ambiente.
- 5 testes legados de `test_tratar_dados_ml.py` em `.venv-legacy-check`, com
  Pandas 3.1.1/PyArrow para ler o Joblib preexistente. No ambiente CTGAN,
  Pandas 2.3.3 não consegue desserializar esse artefato criado com Pandas 3.

Também passaram compilação dos módulos, `git diff --check`, conferência das
fontes e alvos completos, schemas dos quatro Parquets, isolamento de splits
e regeneração reprodutível. `reports/verificacao_final.json` registra hashes
e resultados dessa última verificação. EDA dos dados reais ficou disponível
para execução posterior; apenas seu teste técnico foi executado.

## Alterações entregues

Seis módulos novos no `src`: contratos, dados de vendedor único, síntese,
simulação, ML e CLI. Duas extensões opcionais nos módulos anteriores de
preparação/tratamento. Configuração JSON, testes, README e relatórios foram
acrescentados; os ambientes e artefatos gerados ficam fora do Git.
