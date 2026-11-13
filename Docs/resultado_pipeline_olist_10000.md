# Teste com 10.000 sintéticos — 13/11/2026

Execução `teste_10000_20261113`, preservando a rodada de 2.000 registros.
Reutilizado o mesmo gerador CTGAN de **10 épocas**, treinado somente nos
40.710 pedidos reais de treino. Seeds e hipóteses de simulação mantidas.
Não houve novo treinamento de 300 épocas.

Foram gerados e validados **10.000 pedidos sintéticos**, com 23 colunas:
**1.672 atrasados (16,72%)** e **8.328 no prazo**. Todos ficam no treino.
Contratos e preservação dos artefatos anteriores foram conferidos.

O ML usou todos os 10.000 sintéticos, comparando pesos 0,5 e 1,0 na
validação real. O peso selecionado foi 0,5. Validação e teste permanecem
reais, com as mesmas partições e prevalências.

| Métrica no teste real | Baseline | Com 10.000 sintéticos |
|---|---:|---:|
| Average precision | 0,15020 | 0,14795 |
| ROC-AUC | 0,74582 | 0,74363 |
| Precision | 0,11819 | 0,11217 |
| Recall | 0,72170 | 0,77040 |
| F1 | 0,20312 | 0,19582 |

O aumento melhorou recall, mas piorou AP, precision e F1. Esta rodada não
justifica substituir o baseline. Como o teste já foi consultado na rodada
anterior, esta comparação é exploratória, não uma avaliação independente.
Nenhum coeficiente da simulação foi ajustado a partir desse resultado.

Artefatos: `artifacts/olist_single_seller/teste_10000_20261113/`.
Configuração: `artifacts/config_teste_10000.json`.
Script da execução: `artifacts/executar_teste_10000.py`.
Dataset: `datasets/pedidos_sinteticos.parquet` dentro da pasta da execução.
Métricas, geração, qualidade e verificações ficam em `reports/`.
