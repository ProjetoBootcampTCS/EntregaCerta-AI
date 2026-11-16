# Pipeline anterior

Estes arquivos foram substituídos pelo fluxo de `datasets_merge.csv` e
`datasets_engineering.csv` e ficam preservados para consulta:

- `preparar_dados.py`: consolidação antiga de 53 colunas.
- `tratar_dados_ml.py`: filtros, correção geográfica, imputação e cortes antigos.
- `avaliacoes.py`: reputação progressiva anterior dos vendedores.
- `geracao.py`: CTGAN antiga com transformações/correções automáticas.
- `comparador.py`: comparador anterior, com as colunas antigas.
- `configuracoes/`: cópias exatas das configurações antes da mudança.
- `test_laboratorio_ml.py`: testes do contrato anterior, preservados para consulta.

Os notebooks anteriores e a inferência do modelo web já salvo ainda referenciam
as funções antigas necessárias. A preparação e o treinamento novos não as usam.
Não execute estes scripts para preparar os novos CSVs.
