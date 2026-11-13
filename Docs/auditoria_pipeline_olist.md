# Auditoria anterior à implementação — 13/11/2026

Leitura integral de `Skills/olist-ctgan-pipeline/SKILL.md` e
`CONFERIR_COLUNAS.md`; inspeção dos módulos de preparação, tratamento,
experimentos, treinamento, inferência e testes antes de editar o código.
O único conteúdo inicialmente não rastreado pelo Git era `Skills/`.

## Fluxo existente e decisões

- `preparar_dados.py`: loaders, validação de chaves, categorias predominantes,
  somas por item, coordenadas medianas por CEP e Haversine reutilizáveis.
  Seu consolidado retrospectivo e pagamentos ficam preservados.
- `tratar_dados_ml.py`: cortes fixos **2018-01-01 / 2018-05-01**, com purga
  de entregas ainda não observadas em cada corte. Preservar essa política;
  não substituir por 70/15/15. Reutilizar limpeza de domínio e separação temporal.
- O CSV local `pedidos_ml.csv` tem **44 colunas**, não as 37 ilustrativas da
  skill; inclui flags e campos de regressão. Não o sobrescrever.
- O rótulo antigo compara dias normalizados. O contrato novo exige
  `entrega_cliente > promessa` com timestamps. Nos originais há 1.292
  entregas no dia prometido que diferem entre as definições. Construir o
  rótulo novo diretamente das fontes, registrar a diferença e manter os
  rótulos/artefatos legados intactos. Simulação nunca altera rótulos reais.
- `experimento_ctgan.py` e `testar_doses_ctgan.py`: experimentos anteriores
  aprendem positivos ou alvo condicional, usando esquema e banco legados.
  Preservar essas entradas; o contrato B de 15 campos requer novo adaptador.
- `treinar_pedidos.py`: HGB atual usa CV aleatória e refit com validação;
  não reutilizar esse protocolo no experimento temporal novo. Reutilizar
  a regressão logística já presente em doses, com seleção na validação real.
- API, frontend, PostgreSQL, notebooks e modelos existentes permanecem
  compatíveis. Novos módulos no próprio `src`, sem duplicar a árvore do projeto;
  artefatos separados em `artifacts/olist_single_seller/`.

## Medições iniciais nas fontes (biblioteca padrão)

99.441 pedidos: 775 sem vendedor; 97.388 com um; 1.219 com dois;
54 com três; 3 com quatro; 2 com cinco. Multi-seller: **1,2852%** de todos
os pedidos (a afirmação de menos de 3% se confirma). Há **8.525 pedidos
com múltiplos itens do mesmo vendedor**, que o filtro deve preservar.

No CSV ML legado, o filtro remove 463/41.173 do treino (4 atrasos antigos),
330/24.667 da validação (5 atrasos antigos) e 430/25.550 do teste (1 atraso
antigo). Restam respectivamente 40.710, 24.337 e 25.120, antes de eventuais
inconsistências adicionais. O relatório executável apresentará também a
nova definição de atraso e as proporções por split.

## Ambiente e verificações iniciais

A suíte preexistente foi tentada antes das alterações: os quatro módulos
falharam na importação porque `.venv` não tem NumPy/Pandas/Joblib.
`.venv-ctgan` também está inconsistente: Python 3.12 com binários NumPy
cp315. Esses ambientes não serão sobrescritos. Usar ambiente isolado para
validar e registrar resultados finais ao concluir a implementação.

## Alterações previstas e aceitação

Contratos centralizados A/C=23, B=15, D=23 e X=18; filtro bruto antes de
agregar; histórico estrito por timestamp de resposta; imputação só no treino;
CTGAN sem IDs/alvo/calendário; rejeição auditável e estratos 1/2/3+ itens;
IDs artificiais coerentes; simulação configurável; comparação temporal real;
CLI por etapa e EDA posterior. Testes deverão cobrir vazamento, rótulo,
histórico, geografia, esquemas, restrições sintéticas e direções do simulador.

## Resultado após implementação

A execução técnica chegou da auditoria à avaliação final: A=90.167×23,
B=40.710×15, C=2.000×23 e D=92.167×23, com X de 18 features.
O modelo CTGAN foi treinado por 10 épocas; a configuração padrão de 300
épocas permanece disponível, mas não foi executada nesta validação.
Fontes foram conferidas por hash; todos os alvos reais novos foram
reconciliados com os timestamps originais. Regerar CTGAN e simulação com
as mesmas seeds produziu C idêntico, também preservando o hash de D.

O Joblib legado exige Pandas 3; seus cinco testes passaram em
`.venv-legacy-check` (Pandas 3.1.1 e PyArrow), sem converter o arquivo.
Os outros 16 testes legados passaram no ambiente CTGAN. As verificações
novas e os resultados medidos estão em `resultado_pipeline_olist.md`.

Mudanças nos módulos anteriores: apenas parâmetros opcionais para definição
do alvo e seleção de colunas de limpeza, preservando os defaults. Os seis
módulos adicionados no `src` separam contratos, enriquecimento, síntese,
simulação, ML e orquestração. README/configuração/testes foram acrescentados;
API, frontend, SQL, notebooks e modelos anteriores não foram modificados.
