# Análise geográfica dos atrasos

Abra **01_atrasos_geograficos.ipynb**, selecione o ambiente `.venv-pipeline` e execute as células.
O notebook contém a lógica completa e saídas executadas, sem alterar os dados ou os modelos.

- `graficos/01_mapa_calor.html`: taxa por célula e camada de concentração dos atrasos.
- `graficos/02_mapa_pontos.html`: pontos coloridos por situação da entrega ou UF, com filtros.
- Os três PNGs em `graficos/` podem ser vistos offline; os mapas HTML precisam de internet para bibliotecas e cartografia.

Na primeira célula de código, ajuste localização (cliente/vendedor), limite de distância
(padrão 500 km), partição, fonte do rótulo (datas/PLN) e volume mínimo por célula.
SP é o estado inteiro e o restante do Sudeste não inclui SP. Norte e Centro-Oeste também
aparecem. Os mapas agrupam pedidos na mesma coordenada e categoria, sem amostragem.

A análise usa `Dados/dataset_ml.csv` e liga as coordenadas de `datasets_engineering.csv`
pelo ID do pedido. Coordenadas ausentes/fora da área de referência são apenas omitidas
dos mapas e contabilizadas no notebook. A comparação regional usa todos os pedidos do recorte.

A malha simplificada das UFs está em `apoio/br_ufs.geojson`; sua fonte é a
[API do IBGE](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3), com URL registrada
em `apoio/fonte_malha.json`. Não é necessário baixar novamente para executar o notebook.

Se usar outro ambiente Python, instale `src/eda/requirements.txt`. Para decidir os futuros
grupos de treino, repita a análise com `PARTICAO='treino'` e compare o volume e a taxa de atraso.

## Comparação de modelos

Abra **02_comparacao_modelos_atraso.ipynb** no mesmo ambiente e execute as células em ordem.
Ele contém o código completo, protocolo temporal, pesquisa, treinos, avaliação e conclusões.
O critério de seleção e a meta de 0,5 são **F1 macro**, confirmado pelo usuário.
Precision e recall representam a classe atrasado; F1 micro coincide com accuracy.

- Ajuste execução, semente, threads e CTGAN na primeira célula; os cortes vêm de
  `src/configuracoes/2_treinamento.json`. O catálogo/grades estão nas células de implementação.
- Resultados: `Dados/resultados_modelos/eda_modelos_20261116.csv`, sem subpastas.
- Dados para inspeção: nove CSVs em `Dados/eda_conjuntos_20261116/`, cobrindo as três
  origens (real/sintético/misto) e as três partições.
- Modelos escolhidos: `Modelos/eda_modelos_20261116/`; os estimadores são escolhidos
  pela validação antes de pontuar o teste. O notebook demonstra como recarregar o pacote.
- Checkpoints: `.cache/eda_modelos_20261116/`; reexecutar recupera treinos concluídos.
  Para novos experimentos após a seleção congelada, mude o nome da execução.
- Gráficos: `src/eda/graficos/eda_modelos_20261116/`, também incorporados no notebook.

A divisão operacional e os atributos experimentais são calculados em cópias; os CSVs
tratados pelo usuário são preservados. A análise inclui as limitações dos rótulos PLN,
das notas globais, do status final e da transportadora aleatória.
PostgreSQL/API/assistente/frontend continuam usando a rede anterior: este notebook
documenta o que falta para integrar os novos modelos e métricas, sem implantar mudanças.
