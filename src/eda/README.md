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
