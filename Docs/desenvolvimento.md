# Desenvolvimento do EntregaCerta AI

Histórico técnico acumulado desde 05/11/2026. A organização atual é o **ponto 1**,
registrado ao final. Para executar o sistema, siga [o guia atual](instalacao_novo_pc.md).
Os caminhos/comandos das entradas antigas documentam o estado de cada experimento;
não são uma sequência de inicialização da versão atual.

## Problema e dados

Priorizar pedidos que merecem acompanhamento humano por risco de entrega após o dia prometido. A previsão será feita com informações disponíveis na aprovação; a demonstração será uma reprodução histórica.

Fonte: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), registros reais e anonimizados do comércio eletrônico brasileiro de 2016 a 2018. Licença publicada: CC BY-NC-SA 4.0; preservar atribuição e condições. O recebimento e o hash do ZIP estão em `recebimento_dataset.txt`. Os nove originais estão em `Dados/Brazilian Logistic/`; a consolidação está em `Dados/pedidos_consolidados.csv`.

Unidade: um pedido, agregando seus itens. Positivo: dia da entrega efetiva posterior ao dia prometido. Entrega no mesmo dia é pontual. Cancelados e casos sem desfecho não são rotulados automaticamente como pontuais; o estudo inicial se limita aos entregues elegíveis.

Usar preço/frete informado, composição do pedido, categoria, peso/dimensões, UFs e prazo/calendário quando adequados. Entrega efetiva, passagem à transportadora, status final e avaliações posteriores ficam fora da entrada do modelo. A fonte não tem versões históricas: a disponibilidade dos cadastros e da promessa na aprovação é uma hipótese a documentar.

## Arquitetura prevista

```mermaid
flowchart LR
    A[CSV reais Olist] --> B[Tratamento com Pandas e SQL]
    B --> C[(PostgreSQL)]
    B --> D[Treino e avaliação temporal]
    D --> E[Modelo salvo]
    C --> F[Streamlit e módulos Python]
    E --> F
    F --> G[Revisão humana]
    F --> H[Relatório por API de LLM]
```

Backend em módulos Python e interface Streamlit na mesma aplicação. PyTorch entra em uma rede pequena para comparação; Scikit-learn cobre pré-processamento, referências e modelos clássicos. O modelo final será escolhido pela validação, não pela complexidade da ferramenta.

O BPMN documental já existente foi preservado em `processo.bpmn`, com prévia em `processo.png`. Ele representa o fluxo planejado; será atualizado conforme a implementação. A infraestrutura Terraform ficará para a entrega final.

## Roadmap e modo de trabalho

| Etapa | Trabalho e entrega | Estado |
|---|---|---|
| 1. Escolha | Proposta EntregaCerta e fonte Olist | Escolhidas |
| 2. Preparação simples | Estrutura, ambiente, dependências e conexão PostgreSQL | Estrutura e Pandas verificados; stack completa e conexão pendentes |
| 3. Dados e SQL | Pandas, limpeza, junções, EDA, carga PostgreSQL e divisão temporal | Consolidação, tratamento e divisão temporal executados; EDA relacional e carga SQL pendentes |
| 4. ML | Baselines, modelos Scikit-learn/PyTorch, avaliação e inferência salva | Matrizes e pré-processador prontos; modelos preditivos ainda não treinados |
| 5. GenAI | Relatórios com fatos, conhecimento, API e testes de indisponibilidade | Não iniciada |
| 6. Aplicação | Interface, filtros, gráficos, previsão real, revisão e relatório | Não iniciada |
| 7. Entrega | Testes, Terraform, artigo, slides, demonstração e repositório remoto | Não iniciada |

Para implementar com orientação: **Nos guie pela etapa N, para implementarmos.** Para delegar: **Execute integralmente a etapa N.** Executar a etapa pedida e registrar arquivos, comandos, resultados e pendências, sem iniciar automaticamente a próxima.

## Regras de avaliação e confiabilidade

- Protocolo original: treino e avaliação somente reais. Em 11/11/2026, a equipe autorizou um experimento separado com CTGAN no treino; validação e teste permanecem reais. Não promover os sintéticos à base operacional nem apresentá-los como registros observados.
- Dividir pelo tempo, respeitar quando os rótulos eram conhecidos e ajustar transformações somente no treino. Reservar o teste final.
- Comparar baseline e modelos; avaliar Precision, Recall, F1, matriz de confusão, Average Precision/curva PR e qualidade da fila. Examinar falsos positivos e negativos.
- Definir a política de prioridade no desenvolvimento; os 10% inicialmente propostos são hipótese acadêmica de capacidade, não limiar empresarial comprovado.
- Mostrar probabilidade apenas se a calibração sustentar essa interpretação. Não inventar resultados, causas ou ROI.
- A LLM redige a partir dos fatos do sistema. ML e painéis continuam funcionando se a API falhar. Decisões permanecem humanas.

## Entregáveis e registro atual

### Dataset consolidado em 05/11/2026

O script `src/preparar_dados.py` gera um único CSV com **99.441 linhas e 53 colunas**, mantendo todos os pedidos originais, inclusive aqueles sem itens ou pagamentos correspondentes. Não modifica os nove CSVs de origem. O registro de execução e os hashes SHA-256 estão em `Docs/validacao_dados.txt`.

Executar na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe src\preparar_dados.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Na execução de 05/11/2026, os cinco testes com registros reais passaram: preservação de pedidos/itens, reconciliação financeira com Decimal, datas originais e rótulos, pesos incompletos e distância de um pedido com vários vendedores e quantidades diferentes de itens. Os testes não são evidência de desempenho preditivo.

A consolidação usa sete fontes: pedidos, itens, pagamentos, produtos, clientes, vendedores e geolocalização. Avaliações continuam separadas para análises retrospectivas; a tradução das categorias não foi necessária porque seus nomes em português foram preservados.

| Grupo de colunas | Significado e regra |
|---|---|
| `order_*`, `customer_id` | Campos originais de pedidos; datas e status final são preservados para auditoria, não selecionados automaticamente como entradas. |
| `customer_unique_id`, `customer_city`, `customer_state`, `customer_zip_code_prefix` | Identificação anonimizada e localização do cliente; CEP é identificador de cinco dígitos. |
| `customer_latitude`, `customer_longitude` | Coordenadas aproximadas pela mediana dos pontos do prefixo de CEP; não representam o endereço exato. |
| `quantidade_itens`, `quantidade_produtos`, `quantidade_vendedores` | Número de linhas de itens, produtos distintos e vendedores distintos por pedido. Pedidos com vários vendedores são mantidos. |
| `categoria_principal`, `quantidade_categorias`, `itens_sem_categoria` | Categoria conhecida com mais itens, desempate alfabético; contagem de categorias conhecidas e de itens sem categoria. |
| `valor_itens`, `valor_frete`, `valor_pago` | Somas independentes de itens/frete e pagamentos; sem multiplicar os valores por junções entre tabelas de vários registros por pedido. |
| `peso_total_g`, `volume_total_cm3`, `itens_sem_peso`, `itens_sem_dimensoes` | Somas por item. Peso não positivo e medidas incompletas são desconhecidos para os derivados; o total fica ausente quando qualquer item não tem medida válida. |
| `uf_origem`, `quantidade_ufs_origem`, `vendedores_sem_uf`, `vendedores_ids` | UF comum aos vendedores conhecidos, `MULTIPLAS` quando há várias UFs, ou ausente se falta alguma UF. IDs separados por `\|` servem para rastreabilidade, não como entrada direta. |
| `distancia_media_vendedores_km`, `distancia_max_vendedores_km`, `vendedores_sem_distancia` | Distâncias geodésicas aproximadas por Haversine, uma contribuição por vendedor, sem ponderar pelo número de itens. Não são percursos rodoviários. Média/máximo usam as distâncias conhecidas; o contador informa a cobertura incompleta. |
| `quantidade_pagamentos`, `quantidade_formas_pagamento`, `parcelas_maximas`, `tipo_pagamento_principal` | Registros de pagamento, tipos distintos e maior número de parcelas. Tipo principal é o de maior valor total pago, com desempate alfabético. Quantidade de pagamentos não significa quantidade de parcelas. |
| `prazo_prometido_dias`, `tempo_aprovacao_horas`, `dia_semana_aprovacao`, `mes_aprovacao`, `hora_aprovacao` | Prazo em dias de calendário desde a aprovação, horas entre compra e aprovação e calendário da aprovação. Dia da semana: segunda = 0, domingo = 6. |
| `diferenca_entrega_prazo_dias`, `dias_atraso`, `atrasou`, `rotulo_disponivel` | Desfechos retrospectivos: diferença entre os dias de entrega ao cliente e promessa; atraso é essa diferença limitada a zero no mínimo. `atrasou`: 1 = atraso, 0 = pontual, vazio = sem rótulo observado válido. |
| `elegivel_modelagem`, `entrega_anterior_aprovacao`, `prazo_anterior_aprovacao` | Flags retrospectivas para seleção e auditoria. Elegibilidade inicial exige rótulo observado, aprovação conhecida e cronologia básica coerente; não substitui a avaliação de viés nem a divisão temporal. |
| `tempo_ate_despacho_dias`, `tempo_transporte_dias`, `tempo_entrega_dias` | Durações retrospectivas em dias de 24 horas, preservando frações. Durações negativas ficam indefinidas; timestamps originais permanecem disponíveis para investigar inconsistências. |

Os rótulos são calculados somente para status `delivered`, com entrega, promessa e compra conhecidas, sem entrega anterior à compra. Há **96.470 rótulos observados**, **2.971 pedidos sem rótulo** e **96.394 inicialmente elegíveis para modelagem**. As diferenças decorrem de ausência de desfecho e inconsistências cronológicas; nenhum caso recebeu data ou rótulo inferido por LLM. Pedidos sem rótulo não são negativos.

O CSV é uma **base de análise**, que também contém desfechos e campos posteriores. No treinamento futuro, usar uma seleção explícita: `COLUNAS_PREVISAO`, definida no script, contém 29 entradas candidatas; não usar todas as colunas restantes após retirar apenas o alvo. A disponibilidade de pagamentos, itens, cadastros e promessa na aprovação é uma hipótese, pois a fonte não possui snapshots históricos completos. Históricos de atraso por vendedor/rota ainda não foram calculados: precisam respeitar quando cada desfecho se tornou conhecido.

Há 775 pedidos sem itens, um sem pagamento e 1.278 com vários vendedores. Ausências não foram preenchidas por zero. Ainda faltam EDA completa, tratamento orientado à modelagem, carga PostgreSQL e divisão temporal. Não foi treinado nenhum modelo nesta tarefa.

Manter README, este documento, prompts de desenvolvimento/aplicação, BPMN editável e arquitetura. Ao final: código e dados reproduzíveis conforme licença, testes essenciais, Terraform executado, artigo PDF de até dez páginas, slides/roteiro para até vinte minutos e backup da demonstração.

Nesta reorganização foram criadas as pastas simples, consolidada a documentação e preservados o ambiente, a proveniência e o histórico anterior. Os testes da estrutura antiga não validam PostgreSQL/PyTorch nem uma aplicação futura. A cópia de segurança está na pasta vizinha `EntregaCertaAI_Anterior_884a61b`.

## Registro para o artigo e a apresentação

Checkpoint de 05/11/2026, solicitado pela equipe para preservar as decisões e evidências que serão usadas no artigo PDF de 8 a 10 páginas e na apresentação de até 20 minutos. Este documento é a referência central; `validacao_dados.txt` registra a execução da consolidação e `prompts.txt` guarda os pedidos e decisões de desenvolvimento.

| Assunto | O que podemos registrar neste momento |
|---|---|
| Problema e público | Apoiar analistas de logística de e-commerce na priorização de pedidos com risco de atraso, com revisão humana. |
| Proposta aprovada | EntregaCerta AI com dados reais e anonimizados da Olist. Previsão na aprovação do pedido; demonstração histórica, sem alegar implantação empresarial. |
| Metodologia executada | Leitura dos CSVs com Pandas; agregação de itens/pagamentos antes das junções; uma linha por pedido; produtos e localizações; distância geográfica aproximada; rótulos a partir de datas observadas. |
| Evidência de qualidade | 99.441 pedidos, 53 colunas, zero pedidos duplicados, totais monetários reconciliados e nove originais preservados. Cinco testes com registros reais passaram na geração documentada. |
| Cobertura dos rótulos | 96.470 rótulos observados, 2.971 sem rótulo e 96.394 inicialmente elegíveis para modelagem. Informar qual população sustenta cada resultado futuro. |
| Limitações essenciais | Dados de 2016-2018, cobertura restrita a entregas elegíveis, inconsistências cronológicas, atributos sem snapshots históricos e distâncias por prefixo de CEP. Associações não comprovam causas nem ganhos operacionais. |
| Modelos propostos, ainda não treinados | Regressão Logística como referência e HistGradientBoostingClassifier como principal candidato. MLP em PyTorch como comparação fundamentada. Estimativa da duração do atraso por regressão é uma extensão a validar. |
| Próximo trabalho | EDA, revisão de ausências e inconsistências, seleção explícita de entradas disponíveis na aprovação e divisão temporal. Ajustar transformações somente no treino e preservar o teste final. Carga PostgreSQL também permanece pendente. |
| Resultados ainda inexistentes | Não há desempenho de modelo, aplicação operacional, integração GenAI validada, ROI medido ou redução de atrasos demonstrada. Essas seções do artigo e dos slides só receberão resultados após execução. |

### Identificação do arquivo atualmente disponível

Na conferência deste checkpoint, o arquivo disponível é `Dados/pedidos_consolidados_teste.csv`, com 47.996.599 bytes. Sua leitura confirmou novamente 99.441 linhas, 53 colunas, zero pedidos duplicados e as contagens de rótulos acima. Os cinco testes da geração anterior não foram reexecutados nesta conferência.

- SHA-256 do CSV atual: `d9358143c89395d511effbd99da8dae454fe5824577072916b9a13628bd3e180`.
- SHA-256 de `src/preparar_dados.py`: `7AF45872F24B55013F56856D25231117B21649FC1D0111BF6FE5727EEB589A0F`.
- SHA-256 de `tests/test_preparar_dados.py`: `88670F08293216DDB0140FACAB1A0F6D9D2823148FB6B853D41C96131A497A22`.
- Ambiente conferido: Python 3.12.14. A geração documentada usou Pandas 3.1.0 e NumPy 2.5.4.

O script e os testes continuam apontando para o nome padrão `Dados/pedidos_consolidados.csv`. Ao retomá-los, gerar esse caminho com o script ou adaptar explicitamente a leitura para a cópia escolhida; não substituir silenciosamente um arquivo de trabalho da equipe. Igualdade de contagens não comprova igualdade integral entre arquivos.

### Registro obrigatório ao concluir as próximas etapas

Atualizar este documento com objetivo, decisão e justificativa, arquivos utilizados/alterados, versão ou hash da base, comandos e ambiente, verificações executadas, resultados e limitações. Manter o histórico de resultados anteriores quando o protocolo ou a base mudar, identificando a mudança.

Para os experimentos, guardar datas de corte e populações de treino/validação/teste, seleção de atributos, tratamento aprendido no treino, algoritmo/hiperparâmetros/semente, critério de limiar, métricas e gráficos efetivamente calculados. Diferenciar proposta, hipótese, resultado observado e projeção financeira. Registrar também tentativas com desempenho insatisfatório e os motivos para manter ou descartar um modelo.

Para GenAI e aplicação, registrar prompts, contexto fornecido, testes de confiabilidade e falha da API, versões da arquitetura/BPMN e fluxo demonstrável. Essas evidências alimentarão o artigo e o PowerPoint quando essas entregas forem solicitadas; este checkpoint não significa que já tenham sido produzidos.

## Tratamento para testes de ML — 05/11/2026

Executado `src/tratar_dados_ml.py` sobre `Dados/pedidos_consolidados_teste.csv`, preservando seu conteúdo e os originais. O script gera:

- `Dados/pedidos_ml.csv`: base legível com unidades originais, imputação aprendida no treino, indicadores de ausência, alvos e identificação da partição.
- `Modelos/dados_ml.joblib`: matrizes numéricas prontas, alvos de classificação/duração, metadados e o pré-processador ajustado somente no treino.
- `Docs/tratamento_ml.txt`: registro completo de exclusões, ausências, versões, cortes, contagens e hashes de entrada/saída.

### População, datas e exclusões

Das 99.441 linhas, foram excluídos sequencialmente 2.963 pedidos sem status `delivered`, 22 com datas essenciais ausentes, 61 com entrega anterior à aprovação e um com promessa anterior ao dia da aprovação. Não houve duplicatas idênticas removidas nem exclusões adicionais por ausência de itens. Restaram 96.394 pedidos na coorte básica. Os rótulos existentes foram confrontados com as datas reais, sem imputação ou reclassificação por IA.

Foram definidos cortes calendários antes de avaliar qualquer modelo: **01/01/2018** para início da validação e **01/05/2018** para início do teste. A referência é a data de aprovação; a disponibilidade conservadora do rótulo é a data real de entrega ao cliente. Para poder usar os resultados no momento simulado, foram retirados 2.439 pedidos do treino cujo rótulo só seria conhecido após seu corte e 2.565 da validação cujo rótulo só seria conhecido após o início do teste. Esses 5.004 registros permanecem na base de origem.

| Partição | Pedidos utilizados | Atrasos observados | Proporção da classe positiva |
|---|---:|---:|---:|
| Treino | 41.173 | 1.765 | 4,29% |
| Validação | 24.667 | 2.494 | 10,11% |
| Teste | 25.550 | 1.124 | 4,40% |
| Total | 91.390 | 5.383 | — |

Essas proporções descrevem os dados, não o desempenho de um modelo. A diferença entre períodos e a seleção de entregues exigem discussão de representatividade. A purga de rótulos ainda indisponíveis é conservadora, mas pode sub-representar entregas demoradas junto às fronteiras temporais. Não mover os cortes para melhorar métricas. Validação serve ao desenvolvimento; teste fica reservado para a avaliação final.

Existem 367 pedidos de validação e 290 de teste de clientes que também aparecem no treino. IDs de pedido, cliente e vendedor ficam fora das entradas. O objetivo desta divisão é prever novos pedidos ao longo do tempo, incluindo clientes conhecidos; ela não comprova desempenho em uma população exclusivamente de clientes novos.

### Transformações efetivamente executadas

1. Conferência de duplicatas e chaves; parsing de datas e seleção por cronologia e desfecho observado.
2. Revisão geográfica: foram encontrados pontos como latitude 42°N associados a clientes brasileiros. Excluídos **31 pontos da fonte de geolocalização** fora de um retângulo conservador de latitude −34 a 6 e longitude −74 a −28; esse intervalo inclui ilhas oceânicas e é uma hipótese de controle de qualidade, não uma malha territorial. Recalculadas medianas por prefixo de CEP e distâncias por vendedor; **47 pedidos da coorte básica** tiveram a distância máxima alterada ou tornada desconhecida. Não foram inventadas coordenadas. A referência dos extremos é o [Anuário do IBGE](https://anuario.ibge.gov.br/images/aeb/2024/s1/2_pdf/s1t1101.pdf). Pontos dentro do retângulo ainda podem estar incorretos.
3. Normalização de categorias e UFs; valores numéricos não finitos, negativos ou fora de domínios fixos tornam-se ausentes. Valores extremos válidos foram preservados; não houve cortes por quantis aprendidos na base inteira.
4. Medianas numéricas aprendidas somente no treino, com indicadores para ausências observadas nessa partição. Categorias ausentes recebem `NAO_INFORMADO`. O preenchimento de características é uma transformação técnica identificada; não cria novas observações nem desfechos.
5. Padronização numérica e codificação one-hot, ajustadas somente no treino. Categorias futuras desconhecidas são aceitas sem refazer o ajuste. São **29 características originais**, sendo quatro categóricas, e **159 atributos numéricos transformados**. O uso de transformações ajustadas apenas no treino segue a [orientação do Scikit-learn sobre vazamento](https://scikit-learn.org/stable/common_pitfalls.html).

Antes da imputação e da purga temporal, havia na coorte básica 1.331 categorias ausentes, 22 pesos totais ausentes, 16 volumes ausentes e 477 pedidos sem distâncias calculáveis; um pedido não tinha os campos de pagamento. Esses números não representam a distribuição de ausências de cada partição individual.

Não houve balanceamento artificial ou SMOTE, nem ajuste ao conjunto de teste. Pesos de classe podem ser comparados no treinamento futuro sem gerar exemplos artificiais. A disponibilidade histórica dos cadastros, itens, pagamentos e promessa na aprovação continua sendo uma hipótese da fonte.

### Execução e consumo pelos modelos

```powershell
.\.venv\Scripts\python.exe src\tratar_dados_ml.py --entrada "Dados\pedidos_consolidados_teste.csv"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

O comando completo passou: **10 testes aprovados** e nenhuma dependência quebrada. As verificações incluem reconciliação dos originais, preservação dos rótulos reais, geolocalizações inválidas, separação de pedidos, disponibilidade temporal dos rótulos, medianas e categorias aprendidas apenas no treino e matrizes finitas. Na primeira execução, uma atribuição de tipos incompatíveis no Pandas 3 foi corrigida com substituição explícita das colunas antes da geração bem-sucedida.

Ambiente verificado: Python 3.12.14, Pandas 3.1.0, NumPy 2.5.4, Scikit-learn 1.9.1 e Joblib 1.6.0. Foram instaladas apenas as dependências necessárias de ML; isso não valida a stack completa, PostgreSQL ou PyTorch.

Para os testes dos algoritmos, usar as matrizes já preparadas:

```python
import joblib

dados = joblib.load("Modelos/dados_ml.joblib")
X_treino, y_treino = dados["X"]["treino"], dados["y"]["treino"]
X_validacao, y_validacao = dados["X"]["validacao"], dados["y"]["validacao"]
X_teste, y_teste = dados["X"]["teste"], dados["y"]["teste"]
```

O alvo `y` representa atraso; `y_dias_atraso` contém os dias observados, incluindo zero para pontuais. Uma regressão condicional à ocorrência de atraso deve filtrar os positivos explicitamente e ter avaliação própria.

O CSV tratado mantém categorias legíveis e contém metadados para rastreabilidade; não passar todas as suas colunas diretamente a um estimador. Ele já está imputado: não reaplicar o mesmo pré-processador sobre esse CSV descartando os indicadores, pois isso perderia a informação original de ausência. As matrizes do pacote são a entrada de referência para a comparação inicial dos modelos.

Para inferência futura com dados novos ainda não imputados, usar `limpar_atributos()` e depois `dados["preprocessador"].transform(...)`, sem chamar `fit`. A regra geográfica precisa ser respeitada na preparação dessas novas entradas. Nenhum classificador, regressor, limiar de decisão ou métrica de desempenho preditivo foi produzido nesta etapa. EDA relacional, carga PostgreSQL e treinamento permanecem trabalhos distintos.

## Preparação didática em notebook — 05/11/2026

A equipe pediu uma forma mais acessível de entender os dois scripts. Criado `Notebooks/01_preparacao_dados.ipynb`, com explicações em português, 35 células de código e no máximo 15 linhas por célula. Os scripts e os notebooks anteriores foram preservados.

O fluxo mostra diretamente leitura de sete CSVs originais, agregações e junções, conferência de dinheiro e cardinalidades, coordenadas e distâncias, atributos na aprovação, alvos observados, exclusões, limpeza, cortes temporais, imputação, escala, codificação e persistência. Não importa os scripts para esconder o processamento. Incorpora a correção geográfica já documentada, sem pretender reproduzir byte a byte o consolidado antigo.

Execução final do início ao fim: **35 células, zero erros e zero avisos salvos**. Reproduzidos 96.394 pedidos elegíveis antes da purga temporal e 91.390 na preparação final: treino 41.173, validação 24.667, teste 25.550. As matrizes têm 159 atributos; o CSV legível tem 44 colunas. Comparados todos os metadados, alvos e matrizes com o pacote anterior, com tolerância numérica de `rtol=1e-5`, `atol=1e-5` para ponto flutuante; o CSV também foi comparado. Não houve divergências.

Os dois arquivos de ML já existentes foram preservados. O notebook somente os cria se estiverem ausentes; quando existem, confere compatibilidade antes de prosseguir. Os hashes de 16 arquivos foram iguais antes e depois: nove CSVs originais, consolidado, CSV de ML, pacote Joblib, dois notebooks da equipe e dois scripts.

Dois gráficos descritivos foram gerados e inspecionados individualmente: tamanhos das partições e ausências dos atributos no treino antes da imputação. A revisão visual integral da prévia HTML no navegador ficou indisponível porque o ambiente bloqueia o protocolo local `file:`. Isso não impediu a execução nem a inspeção dos gráficos. Conferir o notebook aberto no VS Code com o kernel `.venv (Python 3.12)` continua sendo a forma de leitura para a equipe.

Validações executadas: `nbformat.validate`, execução com `nbclient` em kernel do Python 3.12 do projeto, conferência de contagens de execução consecutivas, comparação dos artefatos e hashes; `python -m unittest discover -s tests -v` aprovou os **10 testes**. `pip check` não encontrou dependências quebradas.

Instalados no `.venv`: Matplotlib 3.11.2, nbformat 5.11.1, nbclient 0.11.0 e nbconvert 7.17.2, com dependências. As três ferramentas de notebook foram acrescentadas ao `requirements.txt`; Matplotlib já estava previsto. A stack completa ainda não foi instalada ou validada. O README recebeu o acesso ao notebook e a atualização do estado dos dados.

Nenhum modelo preditivo foi treinado, nem houve carga PostgreSQL ou novas métricas de desempenho. Continuam válidas as limitações de representatividade, purga temporal, disponibilidade histórica dos atributos e distância aproximada. O próximo trabalho de ML é a comparação de baseline e modelos; a equipe pode primeiro estudar e explicar cada saída do notebook.


## Experimento CTGAN autorizado — 11/11/2026

A equipe solicitou testar aumento artificial do treino, alterando para este experimento
isolado a preferência anterior de treinar somente com dados reais. O modelo operacional
não é substituído. O notebook 02 permanece intacto; o notebook enviado foi copiado para
`Notebooks/olist_comparacao_otimizada_gmm_treino_teste.ipynb` e a adaptação está em
`Notebooks/olist_comparacao_otimizada_ctgan_postgresql.ipynb`.

A fonte é a consulta PostgreSQL da view `public.vw_pedidos_inferencia` com o alvo em
`public.pedidos`. Contagens conferidas: treino 41.173/1.765 atrasos, validação
24.667/2.494 e teste 25.550/1.124. Preservados os cortes de 01/01/2018 e 01/05/2018,
o alvo por dia e a coorte atual. A revisão proposta da disponibilidade do rótulo
não foi aplicada aqui, para não misturar mudanças no mesmo experimento.

CTGAN recebe apenas atributos dos atrasos reais de treino; o rótulo dos gerados é
condicionante sintético, não observado. Contadores e ausências são representados em
conjunto, contínuas usam log1p, candidatos fora dos intervalos de treino são rejeitados,
a distância média é igualada à máxima para um vendedor, e duplicatas exatas são removidas.
Essas verificações não garantem realismo multivariado nem privacidade diferencial.
Não são inventadas datas de entrega ou dias finais de atraso.

A persistência é isolada em `experimentos_ctgan.execucoes` e `experimentos_ctgan.pedidos`,
com checksum, metadados, teto de 10.000 por experimento e repetição idempotente.
`Dados/pedidos_tratados_e_injetados.csv` reúne reais e sintéticos identificados; os
sintéticos são exclusivamente de treino. Usar somente `COLUNAS_PREVISAO` como entradas.
Não carregar esse CSV com o script que recria as tabelas operacionais.

Comparação: Logística, Random Forest, Extra Trees, HGB e RF com um GMM de distância/frete,
cada um com treino real versus real + CTGAN. Adicionada Logística com pesos como controle.
O GMM e o pré-processador aprendem só no treino real e são compartilhados entre cenários.
Limiar e vencedor são escolhidos por F1 da classe 1 na validação (desempate AP).
Também são medidos accuracy, precision, recall, matriz, AP e fila de 10%.
O teste é apenas descritivo: já foi examinado em outros experimentos deste projeto.
Não usar seus resultados para escolher quantidade sintética, epochs ou hiperparâmetros.

O notebook de referência usa previsão após postagem, split por percentuais e atraso
por timestamp; sua definição não é diretamente comparável ao problema na aprovação.
A adaptação usa o contrato de 29 atributos do projeto e atraso por dia. Não foram
importados atributos futuros nem resultados gráficos antigos como evidência nova.

Dependências do experimento em `requirements-ctgan.txt`, ambiente `.venv-ctgan`
(Pandas 2.3.3, CTGAN 0.13.0, RDT 2.1.0). A `.venv` original foi preservada com Pandas
3.1.0. Notebook, versões, hashes, métricas e gráficos documentam a execução;
resultados definitivos devem ser lidos nas saídas executadas, sem prometer melhora.

### Resultado medido do CTGAN — execução ecc4ac30a3df7383

CTGAN executado por 300 épocas, seed 42, somente 1.765 atrasos reais de treino.
13.398 candidatos amostrados, 10.000 sintéticos finais. CSV com 101.390 linhas.
Conferidos atributos/rótulos/partições de todos os 91.390 pedidos reais exportados,
leitura de retorno dos 10.000 sintéticos no banco, ausência de cópias exatas de atributos
reais, IDs únicos e repetição da carga sem duplicação. Nenhuma data de entrega/aprovação
histórica foi inventada para os sintéticos. Seis testes unitários de isolamento passaram.

Os cinco pares tiveram F1 menor com CTGAN, tanto na validação quanto no teste descritivo.
Na regressão logística (família escolhida pela validação), F1 validação foi 0,269723
com reais versus 0,238583 com CTGAN; no teste, 0,149395 versus 0,129632.
AP teste: 0,096260 versus 0,075173. Accuracy teste aumentou de 0,683562 para 0,747202,
enquanto recall caiu de 0,631673 para 0,427936: o aumento de accuracy não representa
melhor identificação de atrasos. Nenhum desses modelos substituiu a rede da aplicação.

O peso mediano dos sintéticos foi 562,505 g versus 1.000 g nos atrasos reais de treino
(KS=0,180). Há distorções de distribuição apesar das regras de plausibilidade.
Não concluir que dados sintéticos são sempre inúteis, nem que novas gerações resolverão
o problema. Esta execução não justificou adotar o aumento de treino avaliado.

Notebook executado de ponta a ponta (12 células de código, sem erros de célula), quatro
figuras inspecionadas e resultados completos persistidos na pasta do experimento.
Ocorreram avisos de depreciação/CSV e encerramento de workers no Windows; a chamada no
notebook foi ajustada para usar threads em futuras gerações. Arquivo original copiado
byte a byte; notebook 02, dados operacionais, API e modelos atuais não foram alterados.

Teste técnico adicional: CTGAN com threads ajustado por uma época nos mesmos atrasos reais de treino e amostragem de dez linhas, sem persistência ou métricas de desempenho. Execução aprovada. Esse teste verifica a compatibilidade no Windows, não a qualidade do modelo. As métricas publicadas são da geração de 300 épocas.

## Comparação controlada de doses — protocolo de 11/11/2026

Execução solicitada pela equipe para testar a recomendação anterior. Script
`src/testar_doses_ctgan.py` e notebook `Notebooks/04_testes_doses_ctgan.ipynb`.
O banco é somente lido; as tabelas reais, o primeiro CSV combinado e os modelos
operacionais não são substituídos. Resultados em `Modelos/experimento_ctgan/doses_20261111/`.

Comparações pré-definidas: nenhum acréscimo; repetição aleatória de positivos com
reposição; CTGAN aprendendo só positivos; CTGAN aprendendo ambas as classes e
amostrando condicionalmente `atrasou=1`. Doses de 500, 1.000 e 2.000, sementes
7, 42 e 123. Cada dose é prefixo do mesmo lote de 2.000 daquela estratégia/semente.
Os lotes nunca são somados em um único treino. O gerador positivo seed 42 é o
cache anterior; os outros cinco geradores são treinados nesta rodada.

Mantidos fonte PostgreSQL, partições e 29 atributos na aprovação. Pré-processador
ajustado só no treino real, compartilhado. Regressão logística com C=1, liblinear,
max_iter=1500, random_state=42 e sem pesos, igual ao baseline anterior. Sementes
variam o gerador/amostragem, não a divisão temporal ou hiperparâmetros do classificador.
São 28 ajustes de classificação: um baseline e 27 cenários com acréscimo.

Orçamento da GAN definido antes dos resultados: lote 500, redes (128,128), pac=10,
300 épocas/900 atualizações no gerador positivo e 11 épocas/902 atualizações no
gerador condicional (41.173 registros). Igualar épocas faria o segundo executar
cerca de 27 vezes mais atualizações. Esse orçamento limitado não representa
busca de convergência ou ajuste exaustivo da CTGAN condicional. Não escolher épocas
pela avaliação do teste. A condição de geração favorece y=1 mas não o garante:
exemplos gerados com y diferente de 1 são rejeitados, nunca relabelados.

Critério: média de F1 na validação, desempate por AP. Limiar de cada ajuste escolhido
na validação. Registrar também accuracy, balanced accuracy, precision, recall,
matriz, AP e fila fixa de 10%. A seleção agregada é persistida antes de avaliar o
teste, cujo uso permanece descritivo. Intervalos mínimo–máximo e desvio padrão
das três sementes medem variação experimental, não incerteza de generalização.

Qualidade: limites e categorias aprendidos só no treino, estruturas de contagens,
distâncias, duplicatas e procedência, KS numérico, distribuição de categorias,
ausências e correlações. A relação entre valor pago e produtos+frete é auditada
separadamente, sem usar o resultado para selecionar lotes ou alterar o protocolo.
Os sintéticos não contêm datas de entrega fabricadas e seu alvo não é observado.


### Resultados medidos da rodada de doses


**Melhor média de F1 na validação: Somente reais, com 0 exemplos adicionais.**
F1 = **0.2697**, AP = **0.1986**.
São 28 ajustes de regressão logística; nove configurações com acréscimo avaliadas em três sementes
e um baseline fixo. O notebook 02 e o modelo da aplicação permanecem preservados.

A melhor configuração CTGAN pela validação foi **CTGAN condicional +500**:
F1 médio **0.2640**, mínimo–máximo **0.2638–0.2644**,
AP médio **0.1873**. Baseline: F1 **0.2697** e AP **0.1986**.
O desempenho pertence ao orçamento de aproximadamente 900 atualizações por GAN;
não é uma conclusão sobre todas as configurações possíveis dessa arquitetura.

**A rodada não justificou adotar CTGAN no treinamento principal.**

Validação real: 24.667 pedidos, 2.494 atrasos. Médias de três sementes nos acréscimos; baseline único.

| Método | Adicionados | Accuracy | Precision | Recall | F1 | AP | Atrasos na fila |
|---|---:|---:|---:|---:|---:|---:|---:|
| CTGAN condicional | 500 | 78.86% | 20.39% | 37.50% | 26.40% | 0.1873 | 583.3 |
| CTGAN condicional | 1000 | 74.12% | 18.11% | 43.69% | 25.49% | 0.1736 | 538.0 |
| CTGAN condicional | 2000 | 66.98% | 15.25% | 49.39% | 23.26% | 0.1506 | 450.0 |
| CTGAN positivos | 500 | 77.63% | 19.64% | 39.08% | 26.11% | 0.1860 | 576.7 |
| CTGAN positivos | 1000 | 76.99% | 19.03% | 39.20% | 25.61% | 0.1794 | 556.3 |
| CTGAN positivos | 2000 | 75.80% | 18.33% | 39.47% | 24.85% | 0.1694 | 523.0 |
| Somente reais | 0 | 81.27% | 22.27% | 34.20% | 26.97% | 0.1986 | 619.0 |
| Repetição | 500 | 80.36% | 21.77% | 35.86% | 26.97% | 0.1979 | 615.7 |
| Repetição | 1000 | 80.32% | 21.54% | 35.78% | 26.87% | 0.1967 | 613.3 |
| Repetição | 2000 | 78.56% | 20.29% | 38.28% | 26.52% | 0.1941 | 603.7 |

Teste real descritivo: 25.550 pedidos, 1.124 atrasos; mesmos modelos e limiares congelados.

| Método | Adicionados | Accuracy | Precision | Recall | F1 | AP | Atrasos na fila |
|---|---:|---:|---:|---:|---:|---:|---:|
| CTGAN condicional | 500 | 67.93% | 8.09% | 60.68% | 14.27% | 0.0860 | 266.3 |
| CTGAN condicional | 1000 | 63.80% | 7.20% | 60.50% | 12.86% | 0.0742 | 225.0 |
| CTGAN condicional | 2000 | 58.50% | 5.87% | 55.81% | 10.62% | 0.0601 | 180.0 |
| CTGAN positivos | 500 | 65.56% | 8.09% | 65.87% | 14.41% | 0.0925 | 280.7 |
| CTGAN positivos | 1000 | 66.29% | 8.04% | 63.67% | 14.27% | 0.0901 | 278.3 |
| CTGAN positivos | 2000 | 66.96% | 7.95% | 61.27% | 14.06% | 0.0847 | 255.3 |
| Somente reais | 0 | 68.36% | 8.47% | 63.17% | 14.94% | 0.0963 | 288.0 |
| Repetição | 500 | 67.34% | 8.33% | 63.97% | 14.73% | 0.0950 | 285.3 |
| Repetição | 1000 | 67.00% | 8.31% | 64.77% | 14.73% | 0.0939 | 283.7 |
| Repetição | 2000 | 64.60% | 7.94% | 66.55% | 14.19% | 0.0921 | 280.0 |

Os intervalos entre sementes não são intervalos de confiança. A fila tem 2.466 pedidos na validação e 2.555 no teste.
F1/precision/recall/accuracy usam os limiares ajustados na validação; a fila de 10% é uma política separada.

Diagnóstico monetário (pagamento diferente de produtos+frete por mais de 1%):

- Atrasos reais de treino: 0.11%, n=1764.
- CTGAN: positivos: 99.44%, n=5932.
- CTGAN: condicional: 99.25%, n=5999.

Essa diferença evidencia uma limitação de coerência da geração, sem provar causalidade sobre a piora de F1.

Verificação: 56 avaliações e seus scores reproduzidos a partir dos modelos salvos; seis lotes de 2.000 sintéticos isolados, sem alteração dos pedidos reais. Métricas completas, protocolos, hashes, modelos, lotes e gráficos estão na pasta da rodada.

Verificação final concluída: notebook executado integralmente, sem erros de célula;
três figuras inspecionadas e prévia HTML aberta no navegador para conferir resumo,
tabelas e apresentação. Os 11 testes técnicos distintos (seis anteriores e cinco
da rodada) passaram. Nova consulta PostgreSQL confirmou o hash dos 91.390 pedidos
reais e os 10.000 sintéticos do experimento anterior intactos. O novo experimento
não gravou no banco. O servidor local usado apenas na revisão visual foi encerrado.

## Revisão de rótulos e históricos de vendedores — 12/11/2026

Objetivo: verificar se a disponibilidade dos rótulos e novas informações históricas
melhoram a previsão na aprovação. Implementação isolada em
`src/testar_historicos_vendedores.py`, com notebook executado
`Notebooks/05_rotulos_historicos_vendedores.ipynb`. Não substitui o modelo operacional.

### Fontes e auditoria

O PostgreSQL local não respondeu à conexão nesta execução. Foi usada a cópia da
consulta de 11/11 em `Modelos/experimento_ctgan/doses_20261111/snapshot_postgresql.joblib`,
copiada para a pasta do novo experimento. O hash da base é
`304a56814526d2aeccf9df0d72a71fe070b3f61b7c7f4a33b73a332c2a01af8b`.
O SQL está na constante `CONSULTA` de `src/experimento_ctgan.py`. Nenhuma escrita no banco.

Os 99.441 IDs, status e cinco timestamps do consolidado coincidem com
`olist_orders_dataset.csv`. A coorte elegível tem 96.394 pedidos. Nenhuma divergência
entre os alvos existentes e a comparação dos dias reais de entrega e promessa.
Continuam excluídos cancelados/sem desfecho e cronologias inválidas. A amostra não
representa todos os pedidos originalmente aprovados; permanece viés de seleção.

A revisão mantém o alvo: entrega em dia posterior à promessa = atraso. Altera somente
o instante em que o rótulo pode ser conhecido. Para positivos, considera meia-noite
do dia seguinte à promessa; para pontuais, a entrega real. Isso pressupõe promessa
estável e monitoramento sem latência da ausência de entrega. Olist não contém
snapshots operacionais que comprovem essa hipótese. Mantida disponibilidade
estritamente anterior ao corte, inclusive para eventos exatamente à meia-noite.

| Coorte | Treino / atrasos | Validação / atrasos |
|---|---:|---:|
| Original | 41.173 / 1.765 | 24.667 / 2.494 |
| Revisada | 41.504 / 2.096 | 24.901 / 2.728 |

Recuperados 331 positivos no treino e 234 na validação, sem mudar rótulos. Teste
permanece com 25.550 pedidos e não foi avaliado nesta rodada. Continua havendo
desfechos ainda desconhecidos nos cortes que não entram nas coortes.

### Construção dos históricos

Um par pedido-vendedor por associação, deduplicando itens. São 14 novos atributos:
suporte histórico (média/mínimo), taxas de atraso geral e em 90 dias (média/máximo),
fração de vendedores sem desfechos conhecidos, dias de postagem e entrega
(média/máximo), volume aprovado em 30 dias (média/máximo) e folga da promessa frente
ao tempo histórico de entrega. Nas taxas, suavização fixa de força 20 com prior
global calculado apenas com entregas anteriores. Sem desfechos globais anteriores,
taxa ausente, imputada depois apenas com estatísticas do treino.

As datas de eventos usadas precisam ser estritamente anteriores à aprovação.
Histórico de atrasos é atualizado conservadoramente na entrega real, não pela nova
regra de vencimento da promessa. Tempo de postagem entra na passagem real à
transportadora. Volume conta aprovações, incluindo pedidos posteriormente não
entregues; não utiliza status final como filtro. Janelas são [aprovação-dias, aprovação).
IDs, status, entrega atual e instante de disponibilidade do alvo não entram no modelo.

Na validação, eventos já observados atualizam históricos de pedidos posteriores,
sem retreinar o classificador. Esse protocolo simula previsão contínua e requer
armazenamento/atualização de eventos na aplicação. Não é previsão de um lote futuro
inteiro em 01/01. Em pedidos de vários vendedores, o desfecho compartilhado não
permite atribuir causalidade a um vendedor. A disponibilidade histórica de cadastro,
pagamentos, promessa e associação dos itens continua sendo hipótese do projeto.

### Experimento e resultados

Plano definido antes dos treinos: 2 coortes de treino × 2 conjuntos de atributos ×
2 algoritmos, sem busca de hiperparâmetros. Regressão: C=1, liblinear, max_iter=1500,
random_state=42, sem pesos. HGB: 200 iterações, learning_rate=0,07, 15 folhas,
profundidade máxima 5, mínimo 40 amostras por folha, L2=1, early_stopping=False,
random_state=42. Pré-processamento do projeto ajustado só no treino, 159 ou 182
colunas após adicionar 14 atributos e nove indicadores de ausência.

Comparação principal nos **mesmos 24.667 pedidos / 2.494 atrasos**, preservando ordem
dos IDs. Fila global fixa de 2.466 pedidos. AP e captura da fila são as métricas
principais; F1 abaixo usa um limiar que maximiza F1 na validação comum, separado da fila.

| Algoritmo | Treino | Atributos | AP | F1 | Atrasos na fila |
|---|---|---|---:|---:|---:|
| Regressão | Original | Atuais | 0,1986 | 26,97% | 619 |
| Regressão | Original | + históricos | 0,2070 | 27,30% | 630 |
| Regressão | Revisado | Atuais | 0,2127 | 28,78% | 658 |
| Regressão | Revisado | + históricos | 0,2168 | 28,89% | 672 |
| HGB | Original | Atuais | 0,1497 | 21,51% | 422 |
| HGB | Original | + históricos | 0,1598 | 22,52% | 459 |
| HGB | Revisado | Atuais | 0,1512 | 21,79% | 419 |
| HGB | Revisado | + históricos | 0,1649 | 23,48% | 480 |

Regressão completa: 53 atrasos adicionais (+8,56% em relação a 619), recall na fila
24,82% → 26,94% e precisão na fila 25,10% → 27,25%. Ainda distante de recall 95%.
O efeito dos históricos varia por mês: com treino revisado, AP melhora em fevereiro
e diminui em janeiro, março e abril. Não há alegação de significância estatística.

Na população ampliada, comparação secundária com 24.901 pedidos / 2.728 atrasos:
regressão original sem históricos AP=0,2205, F1=28,85%, 699 atrasos na fila; revisada
com históricos AP=0,2408, F1=31,10%, 756 atrasos na fila de 2.490 pedidos. Os dois
modelos são avaliados na mesma população ampliada. Não usar a diferença entre uma
métrica da população original e outra da ampliada como ganho do modelo.

### Evidências e reprodução

`Modelos/experimento_historicos/` contém protocolo com hashes/versões, cópia de entrada,
pedidos recuperados, CSV de atributos com históricos, auditoria por par pedido-vendedor,
oito modelos, métricas comuns/ampliadas/mensais e figuras. Dados reais apenas.
O notebook reabre os artefatos e reproduz 16 conjuntos de scores/métricas sem retreinar.
Para refazer os treinos: `python -m src.testar_historicos_vendedores --snapshot`.

Nove testes passaram: limites de datas/janelas, exclusão do próprio desfecho e de
eventos futuros/simultâneos, itens duplicados, múltiplos vendedores, vendedor novo,
confronto com fontes reais, amostra de 100 históricos calculados por filtro direto,
scores persistidos e igualdade do baseline com a execução CTGAN anterior.
Fixtures artificiais existem apenas nos testes técnicos isolados, não no treinamento.

Próximo passo recomendado: confirmar o ganho em outra janela temporal e avaliar
capacidade diária de revisão antes de integrar atualização de históricos e modelo
na API. A validação foi reutilizada e o teste já foi visto em experimentos anteriores;
os resultados atuais são exploratórios, não uma validação externa independente.

Referências técnicas: [vazamento e pré-processamento](https://scikit-learn.org/stable/common_pitfalls.html)
e [semântica de consultas temporais](https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html).


## Área do cliente e autenticação por perfil — 12/11/2026

**Objetivo:** permitir compras demonstrativas e acompanhamento individual, mantendo
as análises históricas acessíveis somente à equipe. Não altera o pipeline de ML.

**Implementação:** `src/acesso_web.py` centraliza sessões, senhas, cadastro e política
de acesso; `src/gerenciar_acessos.py` cria analistas localmente com senha solicitada
via terminal. A dependência global da FastAPI exige analista por padrão; a lista de
rotas públicas é explícita. As rotas `/api/cliente/` exigem cliente. Documentação da
API está desativada; a rota estática só serve assets, nunca HTML/ZIPs que poderiam
contornar a proteção das páginas. Erros de validação não devolvem valores enviados.

**Persistência:** schema aditivo `app_web`, criado por `src/esquema_web.sql`, com
`usuarios`, `sessoes`, `limites_acesso` e `pedidos_demo`. Consultas usam parâmetros SQL
com filtro de proprietário no servidor. O cookie contém um token aleatório; apenas
seu hash é salvo. Expiração em oito horas, revogação no logout e checagem de usuário
ativo. Ações exigem origem autorizada e CSRF (login/cadastro verificam a origem).
Tentativas de login e cadastro têm limites persistidos no PostgreSQL.

**Loja:** `src/loja_web.py` seleciona um produto de cada uma de seis categorias da
base Olist e calcula a mediana histórica dos preços registrados. Nomes de categoria
e ícones representam os produtos anonimizados, sem inventar marcas ou fotografias.
O servidor calcula os valores e valida quantidades; a chave de idempotência evita
pedidos duplicados em repetições da mesma confirmação. O analista avança somente
para a próxima etapa: recebido → em preparação → despachado → entregue. A linha do
tempo exibe os instantes registrados dessas ações demonstrativas. Não há pagamento,
envio real ou previsão de entrega fabricada. O modelo atual ainda não é aplicado a
esses pedidos, que não contêm todas as entradas históricas necessárias.

**Interface:** `cliente.html/js`, `entrar.html/js`, `auth.js`, `conta.css` e
`operacao.js`; componentes de sessão adicionados ao dashboard e à consulta histórica.
Sessão/CSRF só ficam em memória/cookie; cache antigo de resultados é removido.
Carrinho armazena apenas IDs e quantidades no navegador. Formulários têm rótulos,
estados de erro e foco; o diálogo prende o foco e pode ser fechado com Escape.
Layouts adaptam-se a telas menores e respeitam preferência por movimento reduzido.

**Validação executada:** 14 testes passaram, incluindo nove cenários de integração
em schema PostgreSQL temporário e cinco testes de filtros/HTTP históricos. Não há
substituição da autenticação nos testes de segurança; o teste antigo de filtros
usa override limitado a ele. Contas e pedidos artificiais são fixtures de teste,
sem uso em treinamento ou evidência de desempenho do modelo. Compilação Python e
checagem sintática dos seis JavaScripts também foram executadas.

**Operação:** criar contas de analista com o comando no README. Não há credencial
padrão. Para publicar, HTTPS, cookie Secure e origens exatas devem ser configurados.
Recuperação de senha, verificação de e-mail e MFA ficam fora desta entrega.
Referências para as escolhas: [senhas OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
e [sessões OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

**Conferência no navegador:** cadastro de cliente → carrinho → pedido salvo → logout
→ login do analista → atualização para preparação → consulta do cliente mostrando
essa atualização. O dashboard autenticado consultou PostgreSQL e pontuou 24.667
pedidos históricos, formando a fila de 2.466. Após logout, abrir `/dashboard`
redirecionou ao login. Layouts conferidos em 1280 e 390 pixels, sem transbordamento
horizontal no cliente. Captura: `Docs/imagens/area_cliente.jpg`. A prévia usou contas
isoladas, removidas ao concluir a conferência. A integração GenAI externa não foi
acionada neste teste; sua rota recebeu o mesmo controle de perfil e CSRF.

## Comparação para recall de pelo menos 95% — 13/11/2026

**Objetivo:** encaminhar o menor número de pedidos à revisão humana, encontrando
pelo menos 95% dos atrasos observados. Recall é a proporção de atrasos encontrados;
não é a proporção de alertas corretos nem a accuracy. Não houve novo treinamento,
alteração de rótulos ou substituição do modelo e da política da aplicação.

**Fonte e população:** snapshot já extraído do PostgreSQL em
`Modelos/experimento_ctgan/doses_20261111/snapshot_postgresql.joblib`, com 91.390
pedidos reais. Atraso foi conferido, pedido a pedido, contra as datas reais de
entrega e prometida, comparadas por dia. Validação: 24.667 pedidos / 2.494 atrasos
(janeiro a abril de 2018). Teste: 25.550 pedidos / 1.124 atrasos (maio a agosto de
2018). Todos os candidatos usam exatamente os mesmos pedidos de avaliação,
incluindo pedidos com vários vendedores. Isso difere da comparação anterior do
laboratório de simulação, cuja população tinha apenas um vendedor por pedido.

**Candidatos:** 48 configurações salvas, distribuídas entre regressão logística,
Random Forest, Extra Trees, RF com atributos GMM, HGB e rede neural. Incluem
baselines reais, pesos de classe, repetição de positivos, CTGAN e históricos dos
vendedores. Algumas configurações repetem o mesmo baseline entre experimentos;
48 não significa 48 algoritmos distintos. Sintéticos aparecem somente no treino
de certos candidatos. Modelos treinados para rótulos logísticos simulados e os
modelos de população restrita a um vendedor foram excluídos desta comparação.

**Protocolo:** para cada candidato, selecionar na validação o maior corte de score
que encontra pelo menos 95% dos atrasos. A regra inclui todos os empates no corte.
Como existem 2.494 atrasos, são necessários pelo menos 2.370 acertos, resultando em
95,0281% de recall. Entre cortes determinísticos `score >= limiar`, essa escolha
minimiza a fila para aquele modelo nessa validação. Comparar modelos pelo número
de revisões; desempatar pela AP de validação e pelo identificador. Congelar os
cortes e a seleção em arquivo **antes** de calcular a inferência no teste.
Não reajustar o corte nem trocar o vencedor com base no teste.

Os pré-processadores e pesos dos modelos permanecem os já treinados. Históricos
usam apenas eventos anteriores à aprovação de cada pedido, com conferência de
igualdade dos atributos e scores da validação com os artefatos anteriores. No
teste, históricos podem incorporar desfechos de pedidos anteriores que já seriam
conhecidos naquele instante: é uma avaliação sequencial na aprovação, não uma
previsão de todo o quadrimestre feita em 1º de maio.

**Resultados dos representantes de cada família, escolhidos na validação:**

| Modelo / ID | Revisão na validação | Recall no teste | Revisão no teste | Atrasos não encontrados no teste |
|---|---:|---:|---:|---:|
| Logística com históricos, base original / m42 | 20.467 (82,97%) | 98,22% | 21.681 (84,86%) | 20 |
| HGB com históricos, base revisada / m47 | 20.985 (85,07%) | 89,86% | 17.775 (69,57%) | 114 |
| Rede neural, artefato atual / m48 | 21.018 (85,21%) | 97,42% | 20.550 (80,43%) | 29 |
| RF + GMM real / m09 | 22.129 (89,71%) | 98,22% | 23.101 (90,41%) | 20 |
| Random Forest real / m03 | 22.412 (90,86%) | 98,13% | 23.320 (91,27%) | 21 |
| Extra Trees real / m05 | 22.579 (91,54%) | 96,71% | 23.771 (93,04%) | 37 |

Todas essas configurações atingiram o recall mínimo na validação. O HGB listado
não manteve a meta no teste. A rede neural exigiu menos revisão no teste que a
logística, mas não foi escolhida retrospectivamente como vencedora: a escolha
estava congelada pela validação. Ela continua sendo candidata para confirmação
em outra janela temporal.

**Escolha pelo protocolo:** logística com históricos da base original (m42),
treinada com dados reais. Corte de score: `0.01393251304995104`, específico desse
artefato e pré-processador; não deve ser transplantado para outros modelos nem
apresentado como probabilidade calibrada. No teste: 1.104 atrasos encontrados,
20 não encontrados, 20.577 falsos positivos e 3.849 verdadeiros negativos.
Recall 98,22%; precisão 5,09%; F1 9,68%; AP 0,0989; accuracy 19,39%.
Comparado a revisar todos os 25.550 pedidos, dispensa 3.869 revisões (15,14%),
incluindo os 20 atrasos perdidos. A política de revisar todos encontra 100% dos
atrasos, mas não reduz trabalho. A precisão baixa indica que aproximadamente
95% da fila escolhida seria de pedidos que terminaram no prazo. Encontrar mais
atrasos aqui veio da ampliação da fila, não de uma melhora do treinamento.

**CTGAN:** a melhor configuração com CTGAN pela validação foi a logística com
500 positivos sintéticos, semente 7 (m22): 20.875 revisões na validação (84,63%),
versus 20.467 da logística com históricos. No teste, m22 encontrou 98,75% dos
atrasos, com 22.059 revisões (86,34%) e 14 atrasos perdidos. Portanto, não venceu
o critério combinado de recall mínimo e menor revisão na validação. Não há
evidência nesta comparação de que GAN seja necessária para atingir a meta global.

**Estabilidade temporal:** o recall global não assegura 95% em cada mês.

| Mês de teste | Atrasos reais | Não encontrados por m42 | Recall de m42 |
|---|---:|---:|---:|
| Maio/2018 | 454 | 5 | 98,90% |
| Junho/2018 | 71 | 8 | 88,73% |
| Julho/2018 | 193 | 7 | 96,37% |
| Agosto/2018 | 406 | 0 | 100,00% |

Na própria validação, janeiro ficou em 88,04% e fevereiro em 94,06%. A rede neural
também ficou abaixo da meta em junho do teste (90,14%). Não se alteraram cortes
para corrigir esses meses após ver seus resultados. O teste já foi consultado em
experimentos anteriores e a validação foi reutilizada para comparar muitos
candidatos; esta evidência é retrospectiva e exploratória, não uma garantia
operacional ou avaliação externa independente. Intervalos de Wilson nos CSVs são
descritivos e pressupõem independência, não modelam dependência temporal ou por
vendedor. O próximo passo recomendado é validação em janelas temporais adicionais,
com cortes escolhidos apenas em períodos anteriores, antes de mudar a aplicação.

**Arquivos e reprodução:** `src/comparar_recall95.py` calcula a comparação e
`tests/test_recall95.py` testa os cortes, empates, entradas inválidas, arredondamento
da meta com poucos atrasos e falha possível em outro período. Na raiz do projeto:

```powershell
.\.venv-ctgan\Scripts\python.exe -m unittest tests.test_recall95 -v
.\.venv-ctgan\Scripts\python.exe -m src.comparar_recall95
```

Usar o ambiente dos experimentos, com os artefatos locais já existentes. A pasta
`Modelos/comparacao_recall95/`, ignorada pelo Git, contém `catalogo.csv`,
`ranking_validacao.csv`, `resumo_por_familia.csv`, `metricas.csv`,
`metricas_mensais.csv`, `scores.parquet`, `pedidos_avaliacao.parquet`,
`protocolo.json` (versões e hashes SHA-256) e `selecao_antes_teste.json` (cortes
congelados). Os JSONs são registros de reprodutibilidade, não dados fabricados.

**Verificações executadas:** cinco testes automatizados passaram; inferências dos
48 candidatos concluídas; comparação independente dos cortes com a curva
Precision–Recall do Scikit-learn; verificação dos rótulos contra datas reais, dos
históricos contra eventos passados e de TP/FN/tamanho da fila após gravar e reler
os scores. Nenhuma escrita no PostgreSQL ou alteração do frontend/API foi feita.

## Reavaliação com meta de recall de 90% — 13/11/2026

**Pergunta:** reduzir a meta de 95% para 90% permite diminuir suficientemente a
fila humana? Foram reutilizados os scores reais dos mesmos 48 candidatos, sem
retreinamento, nova inferência ou mudança de dados. A regra permanece escolher
o maior corte que atende a meta na validação e comparar pelo menor número de
revisões. O corte e o vencedor foram registrados antes de avaliar novamente os
scores do teste. Esse teste já foi visto; a comparação permanece exploratória.

**Resultado:** a logística com históricos da base original (m42) continuou em
primeiro lugar na validação. O corte passou de `0.01393251304995104` para o valor
exato registrado em `metas/recall90/selecao_antes_avaliar_teste.json` (aproximadamente
0,018384). O score não é uma probabilidade calibrada. Na validação, a fila caiu
de 20.467 (82,97%) para 18.285 pedidos (74,13%), com recall de 90,0160%.

| Política da logística com históricos | Revisões no teste | Recall no teste | Atrasos encontrados | Atrasos perdidos |
|---|---:|---:|---:|---:|
| Corte escolhido para 95% na validação | 21.681 (84,86%) | 98,22% | 1.104 | 20 |
| Corte escolhido para 90% na validação | 20.151 (78,87%) | 96,09% | 1.080 | 44 |

Mesmo denominador: 25.550 pedidos reais, dos quais 1.124 atrasaram. São 1.530
revisões a menos, redução de 5,99 pontos percentuais da população ou 7,06% da
fila anterior, ao custo de 24 atrasos adicionais não encontrados. Em relação a
revisar todos, dispensa 5.399 revisões (21,13%). O novo corte produziu 19.071
falsos positivos, 5.355 verdadeiros negativos, precisão 5,36%, F1 10,15%, AP
0,0989 e accuracy 25,19%. A AP permanece igual porque os scores não mudaram.

**Comparação dos representantes escolhidos na validação para a nova meta:**

| Família / ID | Revisão na validação | Revisão no teste | Recall no teste | Atingiu 90% no teste completo? |
|---|---:|---:|---:|---|
| Logística com históricos / m42 | 74,13% | 78,87% | 96,09% | Sim |
| HGB com históricos, base revisada / m47 | 77,60% | 60,49% | 84,43% | Não |
| Rede neural / m48 | 76,86% | 74,65% | 94,66% | Sim |
| RF + GMM real / m09 | 81,20% | 82,85% | 96,09% | Sim |
| Random Forest real / m03 | 81,62% | 82,90% | 95,46% | Sim |
| Extra Trees com CTGAN / m06 | 83,36% | 76,10% | 77,31% | Não |

O representante de Extra Trees mudou em relação ao critério de 95%. A rede neural
revisou 19.074 pedidos e perdeu 60 atrasos no teste. É uma alternativa para
investigar em outra janela; não foi promovida com base no teste. A melhor CTGAN
na validação foi a logística com 500 registros condicionais, semente 42 (m34):
76,10% de revisão na validação, 80,52% no teste e recall de teste 96,98%.
Ela não venceu a logística com históricos pelo critério definido.

**Limitação temporal:** junho de 2018 ficou abaixo da meta nos dois modelos:
81,69% de recall para a logística (13 de 71 atrasos perdidos) e 83,10% para a
rede (12 de 71 perdidos). Na validação, janeiro e fevereiro também ficaram abaixo
de 90% nos dois. Atingir 90% no conjunto não significa mantê-lo em cada mês.
Não aumentamos cortes até obter 90% no teste, pois isso usaria o resultado de
avaliação para otimizar a política.

**Direção recomendada, ainda não executada:** confirmar os modelos em janelas
temporais adicionais e experimentar uma segunda previsão durante a operação,
após o despacho ou em instantes anteriores ao prazo. Nesse novo problema, o tempo
até o despacho, os dias restantes e históricos de rota conhecidos no instante
poderiam trazer informação adicional. Comparar com a previsão na aprovação e
medir a antecedência do alerta. Ausência de despacho não pode excluir pedidos da
avaliação; alerta emitido depois do prazo não deve contar como previsão antecipada.
O Olist não contém rastreamento diário detalhado: qualquer novo monitoramento
deve respeitar os eventos realmente disponíveis, sem fabricar transportadoras ou
trajetórias. Não há resultado medido que sustente prometer 90% de recall com uma
fila de 20% ou 30%. Apenas alterar o corte não produziu uma fila pequena aqui.

**Reprodução:** o script e os testes existentes foram estendidos para aceitar
outra meta. Os resultados de 95% foram preservados.

```powershell
.\.venv-ctgan\Scripts\python.exe -m unittest tests.test_recall95 -v
.\.venv-ctgan\Scripts\python.exe -m src.comparar_recall95 --reavaliar-recall 0.90
```

Saídas: `Modelos/comparacao_recall95/metas/recall90/`, com ranking, métricas de
validação/teste, métricas mensais, comparação com 95%, seleção e hashes das fontes.
Seis testes passaram, incluindo a nova verificação de que a meta de 90% reduz a
fila e modifica corretamente o critério de aprovação. Também foram conferidos
IDs, rótulos reais, partições, cortes pela curva PR e redução monotônica da fila.
A aplicação, o banco e os modelos treinados não foram alterados nesta etapa.

## Previsão durante a operação e validação temporal — 13/11/2026

**Objetivo:** comparar a previsão na aprovação com checagens posteriores, buscando
reduzir pedidos únicos na fila e manter recall mínimo de 90%. O experimento usa
os mesmos 91.390 pedidos reais; treino 41.173, calibração 24.667 e teste 25.550.
Não houve CTGAN, balanceamento sintético ou mudança do alvo. São dois algoritmos
(logística e HGB), três momentos e uma política combinada por algoritmo. Foram
treinados 24 modelos: seis em cada uma de três dobras e seis na rodada final.

**Instantes de previsão, definidos antes dos experimentos:**

- Aprovação: baseline com os atributos e históricos de vendedores já existentes.
- Checagem após 48h da aprovação: pode encontrar o pedido ainda em preparação ou
  já em transporte. Para promessas curtas, antecipar a checagem para 24h antes do
  fim do dia prometido.
- Despacho: no timestamp observado de entrega à transportadora. Se o evento ainda
  não ocorreu, fazer uma checagem de segurança 24h antes do fim do prazo. Isso
  mantém pedidos sem despacho na avaliação; não se considera apenas quem saiu.
- Combinada: emitir alerta se qualquer uma das duas checagens posteriores exceder
  seu corte comum. O pedido conta uma vez, e a antecedência é a do primeiro alerta.
  O máximo dos scores é apenas um resumo retrospectivo da política, não uma
  previsão disponível na aprovação nem uma probabilidade calibrada.

Todos os alertas avaliados antecedem o fim do prazo em pelo menos 24h. Pedidos já
entregues naquele instante não recebem alerta, mas continuam no denominador. No
teste, isso ocorreu em 1.205 pedidos na checagem de 48h e 789 na de despacho/D-1;
todos eram pontuais. A redução da fila compara processos em momentos diferentes,
não apenas a capacidade de discriminação de modelos no mesmo instante.

**Dados adicionais e disponibilidade:** tempo decorrido desde a aprovação, dias
restantes, fração do prazo consumida, despacho já ocorrido, tempo até o despacho,
tempo em trânsito, prazo do vendedor para postagem, eventual excesso desse prazo
e folga em relação ao histórico de trânsito. Um despacho futuro nunca entra nos
atributos da checagem anterior. Entrega efetiva só define o alvo e o estado quando
já aconteceu; não é entrada do classificador. Históricos de vendedores ficaram
congelados na aprovação, isolando parte das mudanças em relação ao baseline.
As entradas também foram ampliadas: o ganho não foi atribuído causalmente apenas
à passagem do tempo ou a um atributo específico.

`shipping_limit_date` foi agregado pelo menor prazo dos itens, sem multiplicar
pedidos. Supõe-se que esse prazo e a promessa ao cliente eram conhecidos e estáveis
desde a aprovação; o Olist não oferece versões históricas para confirmar isso.
Supõe-se ainda atualização imediata dos eventos, sem latência. Não foram inventados
rastreamento diário ou transportadoras. Despachos anteriores à aprovação foram
tratados como timestamps inconsistentes e ignorados: 71 no treino, 247 na
calibração e 806 no teste. Não foi inferido um instante correto para substituí-los.

**K-fold:** o script antigo `src/treinar_pedidos.py` possui `StratifiedKFold` e
`KFold` com embaralhamento. As comparações recentes de 95%/90% usaram uma divisão
temporal fixa, não K-fold. Neste experimento foram executadas três dobras por
calendário, com treino crescente, calibração separada do corte e avaliação futura:

| Dobra | Treino: rótulos conhecidos antes de | Calibração | Avaliação futura | Pedidos treino / calibração / avaliação |
|---|---|---|---|---:|
| 1 | 01/05/2017 | Maio–junho/2017 | Julho–agosto/2017 | 6.117 / 5.660 / 8.044 |
| 2 | 01/07/2017 | Julho–agosto/2017 | Setembro–outubro/2017 | 13.091 / 6.737 / 8.599 |
| 3 | 01/09/2017 | Setembro–outubro/2017 | Novembro–dezembro/2017 | 20.847 / 7.117 / 10.389 |

Imputação, escala e codificação foram ajustadas somente no treino de cada dobra.
A calibração também excluiu rótulos ainda desconhecidos no início da avaliação.
Não se embaralharam pedidos nem se colocaram snapshots do mesmo pedido em partes
diferentes. Usou-se divisão explícita por datas, em vez de `TimeSeriesSplit` por
quantidade de linhas, porque os pedidos não são uniformemente espaçados. A CV
serviu para diagnosticar estabilidade; não houve busca ampla de hiperparâmetros.
As configurações dos dois algoritmos foram fixadas antes de olhar os resultados.

**Resultado final:** cada corte foi escolhido para recall mínimo de 90% na
calibração. O vencedor e todos os cortes foram congelados antes de pontuar o teste.
O critério foi menor fila na calibração, com desempate por AP e nome.

| Política | Fila na calibração | Fila no teste | Recall no teste | Atrasos perdidos |
|---|---:|---:|---:|---:|
| Logística na aprovação — baseline | 74,13% | 20.151 (78,87%) | 96,09% | 44 |
| Logística após 48h | 70,72% | 17.955 (70,27%) | 96,17% | 43 |
| Logística no despacho/D-1 — selecionada | 68,99% | 17.574 (68,78%) | 95,55% | 50 |
| Logística combinada | 70,75% | 18.472 (72,30%) | 96,09% | 44 |
| HGB na aprovação | 78,98% | 16.053 (62,83%) | 87,10% | 145 |
| HGB após 48h | 74,09% | 14.827 (58,03%) | 89,77% | 115 |
| HGB no despacho/D-1 | 75,36% | 14.143 (55,35%) | 89,86% | 114 |
| HGB combinado | 74,67% | 14.919 (58,39%) | 90,21% | 110 |

O baseline da logística reproduziu os scores do modelo anterior, pedido a pedido.
A logística no despacho/D-1 poupou 2.577 revisões frente ao baseline (12,79% da
fila anterior, ou 10,09 pontos percentuais da população), perdendo seis atrasos a
mais. No teste foram 1.074 TP, 16.500 FP, 50 FN e 7.926 TN. Precisão 6,11%, F1
11,49%, AP 0,4249 e accuracy 35,23%. Seu corte é `0.013853735514043702`, específico
deste modelo e momento, não intercambiável com os cortes da aprovação.

A mediana da antecedência dos verdadeiros positivos foi de 8,50 dias para o
despacho/D-1, contra 15,38 dias na aprovação e 13,47 dias após 48h. O percentil 10
no despacho/D-1 foi um dia. Há troca entre informação disponível e tempo para agir.
O HGB combinado alcançou a meta no total do teste com fila menor, mas não venceu
na calibração e não foi promovido após ver o teste. As variantes HGB após 48h e
no despacho ficaram abaixo de 90%, mesmo arredondando para perto desse valor.

Para situar a rede neural salva da aplicação: na comparação anterior com corte
calibrado para 90%, ela revisou 19.074 pedidos (74,65%) com recall de 94,66%.
Essa rede não foi retreinada nesta rodada, e a fila de produção não foi alterada.

**A meta ainda não é estável:**

| Período | Recall logística na aprovação | Recall logística despacho/D-1 | Recall HGB combinado |
|---|---:|---:|---:|
| Dobra 1: julho–agosto/2017 | 35,09% | 51,75% | 81,14% |
| Dobra 2: setembro–outubro/2017 | 85,67% | 87,88% | 96,42% |
| Dobra 3: novembro–dezembro/2017 | 54,73% | 60,41% | 74,29% |
| Junho/2018, dentro do teste final | 81,69% | 78,87% | 67,61% |

Esses números usam cortes escolhidos em calibrações anteriores, nunca no próprio
período avaliado. Os demais meses do teste final tiveram recalls de 94,27%, 95,85%
e 99,75% para a logística no despacho/D-1 (maio, julho e agosto). As dobras revelam
instabilidade relevante, não evidência de recall consistentemente acima de 90%.
O K-fold temporal melhora a avaliação da generalização; não acrescenta informação
ao dataset nem garante melhoria automática do modelo.

**Limitações:** coorte retrospectiva restrita a entregues elegíveis; exclusão de
rótulos desconhecidos nas fronteiras pode produzir viés de maturidade; validação e
teste já reutilizados em vários experimentos; sem validação externa. As diferentes
dobras têm volumes, prevalências e quantidade de treino diferentes. Não atribuímos
a instabilidade a uma causa específica sem investigá-la. O próximo experimento
recomendado é atualização periódica com calibração em coortes maduras e avaliação
cronológica, antes de adotar a política como garantia operacional de 90%.

**Arquivos e reprodução:** `src/testar_previsao_operacional.py`,
`tests/test_previsao_operacional.py` e pasta ignorada pelo Git
`Modelos/experimento_operacional/`. Esta contém protocolo/hashes, auditoria de
eventos, fronteiras das dobras, seleções congeladas, métricas por rodada e mês,
snapshots, modelos e previsões por pedido. Executar na raiz:

```powershell
.\.venv-ctgan\Scripts\python.exe -m unittest tests.test_previsao_operacional tests.test_recall95 -v
.\.venv-ctgan\Scripts\python.exe -m src.testar_previsao_operacional
```

**Conferências executadas:** 12 testes técnicos passaram, incluindo invisibilidade
de eventos futuros, entrega já conhecida, timestamp inconsistente, expurgo de
rótulos futuros, antecedência mínima e contagem única da política combinada. Após
gravar e reler, os seis modelos finais reproduziram exatamente seus scores; o
baseline também reproduziu os scores anteriores. As 16 linhas de métricas finais
foram recalculadas a partir das previsões persistidas, mantendo todos os pedidos.
Foram auditados adicionalmente 200 snapshots por etapa (600 ao todo), e os hashes
das fontes foram reconferidos. Não houve alteração do banco, API ou frontend.

Referência: [validação temporal no Scikit-learn](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data).


# Registro das funcionalidades web — preservado do README no ponto 0

Os comandos deste registro são históricos. Para iniciar a versão organizada, use o guia `instalacao_novo_pc.md`.

## Assistente: conversa, pedidos e avaliações — 13/11/2026

- **Memória:** as últimas 6 trocas concluídas acompanham a próxima pergunta.
  Cada conversa pertence à sessão autenticada e a um único contexto. O histórico
  visível dura enquanto a página estiver aberta; no servidor expira após 30 minutos
  sem atividade. Reiniciar a API também apaga essa memória. Limites: 20 perguntas
  por conversa e 100 conversas por processo; usar um único worker nesta versão local.
- **Pedido selecionado:** use **Conversar sobre pedido** em Meus pedidos, na operação
  da loja ou nos detalhes históricos do analista. O servidor verifica o acesso e
  consulta os dados novamente a cada pergunta. Trocar de pedido inicia outra conversa.
  O cliente só acessa pedidos próprios. Pedidos demonstrativos continuam sem previsão
  de ML; o score histórico continua sendo risco relativo, não probabilidade calibrada.
  Nomes, e-mails, IDs e justificativas internas do pedido não compõem o contexto enviado.
- **Controles:** copiar a resposta, repetir uma pergunta que falhou e iniciar nova
  conversa. Repetir uma requisição concluída reutiliza sua resposta sem duplicar a
  memória. Respostas truncadas não são guardadas como concluídas.
- **Avaliações:** 👍 salva uma avaliação positiva; 👎 permite escolher informação
  incorreta, resposta confusa, pergunta não respondida ou outro motivo. A pergunta e
  a resposta avaliadas ficam em `app_web.assistente_feedback`, para revisão da equipe.
  Isso não modifica nem retreina o modelo. Nova conversa limpa a memória, mas não
  remove avaliações já enviadas. Não envie informações sensíveis no chat.

A migração local de feedback já foi aplicada. Em outra instalação, execute:

```powershell
.\.venv\Scripts\python.exe -m src.gerenciar_acessos iniciar
$env:ENTREGACERTA_TEST_POSTGRES="1"
.\.venv\Scripts\python.exe -B -m unittest tests.test_conversas_assistente tests.test_assistente_genai tests.test_relatorio_pdf tests.test_acesso_web -v
```

O comando de testes usa schemas temporários; respostas simuladas são fixtures
técnicas, sem constituir evidência de desempenho do ML. Para verificar os motivos
das avaliações com acesso administrativo ao banco:

```sql
SELECT avaliacao, categoria, COUNT(*) AS quantidade
FROM app_web.assistente_feedback
GROUP BY avaliacao, categoria;
```

Validação de 13/11: 38 casos automatizados aprovados, incluindo a reexecução
da fixture corrigida para o retorno HTTP 201 de criação de pedido. Conferidos no
Edge: fluxos de cliente/analista, troca de pedido, cópia, avaliação, recuperação de
falha sem duplicação, nova conversa, logout, teclado e tela de 390 px. A interface
foi testada com respostas técnicas simuladas em schema temporário. Duas chamadas
ao Gemini configurado também concluíram com `STOP`, mantendo o contexto da
pergunta anterior em um exemplo fictício de contagem de caixas. O ML não foi
treinado ou alterado; a intro e suas animações foram preservadas.

## Relatório PDF do analista — 13/11/2026

No **Dashboard**, gere a fila e clique em **Gerar relatório em PDF**. O download
inclui indicadores, dois gráficos e um resumo da GenAI baseado somente nos
indicadores agregados. O documento usa a análise exibida e a fila completa,
independentemente da busca e da paginação. Scores continuam sendo risco relativo,
sem interpretação como probabilidade calibrada ou métricas de acerto.

Somente analistas autenticados podem gerar o PDF. O servidor confere o perfil,
o dono da análise e o token CSRF. Não são enviados nomes, e-mails ou IDs de pedidos
à GenAI. Se ela falhar ou devolver uma resposta aparentemente interrompida, o PDF
continua disponível com um resumo automático claramente identificado.

O resumo do PDF tem configuração própria: até 4.096 tokens, processamento interno
reduzido nos modelos Gemini 3 e uma nova geração com até 8.192 tokens somente se a
API indicar `MAX_TOKENS`. Só uma resposta concluída (`STOP`) é aceita. O texto não
é cortado na exportação; se necessário, o PDF acrescenta páginas. O prompt continua
pedindo até 150 palavras, e a configuração do chat permanece a mesma.
Cada geração do relatório espera até 45 segundos, sem acumular as repetições
automáticas do SDK. Gemini 3.6 Flash e 3.1 Flash-Lite usam `minimal`; outras
variantes Gemini 3 usam `low`. Os intervalos do histograma ficam no gráfico,
mas não são enviados à IA para evitar inferências de valores exatos a partir deles.

As análises ficam em memória por até 30 minutos, com limite de 16 análises no
processo. Reiniciar a API ou remover uma análise antiga do cache exige atualizar
a fila. Downloads repetidos da mesma análise reutilizam o PDF; para tentar outro
resumo, atualize a análise. Esta implementação local usa um único processo da API.

As dependências estão no `requirements.txt`. Para adicionar apenas o suporte a PDF
em um ambiente já instalado, sem atualizar as bibliotecas de ML:

```powershell
.\.venv\Scripts\python.exe -m pip install "reportlab>=4,<5" "pypdf>=5,<7"
.\.venv\Scripts\python.exe -B -m unittest tests.test_assistente_genai tests.test_relatorio_pdf -v
```

Reinicie a API depois de instalar e atualize o navegador. O módulo de geração é
`src/relatorio_pdf.py`; o botão usa `frontend/relatorio.js`. Nenhum treinamento ou
alteração de modelo é executado para exportar o relatório.


## Área do cliente e acesso dos analistas — 12/11/2026

Com o `.env` do PostgreSQL configurado, execute na raiz do projeto:

```powershell
docker compose up -d postgres
.\.venv\Scripts\python.exe -m src.gerenciar_acessos iniciar
.\.venv\Scripts\python.exe -m src.gerenciar_acessos criar-analista --nome "Nome do analista" --email "analista@equipe.com"
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload
```

O comando de criação pede uma senha de **12 a 128 caracteres** e sua confirmação,
sem exibi-la. Não existe conta ou senha padrão. Crie uma conta por analista.
Clientes se cadastram pela página; o cadastro público não permite escolher perfil.

- **Loja e acompanhamento:** <http://127.0.0.1:8000/cliente>.
- **Entrar / criar conta de cliente:** <http://127.0.0.1:8000/entrar>.
- **Dashboard restrito:** <http://127.0.0.1:8000/dashboard>.
- **Consulta histórica restrita:** <http://127.0.0.1:8000/pedidos>.

A loja oferece catálogo de categorias Olist, carrinho, pedidos por conta e etapas
atualizadas pelo analista no dashboard. Desde 13/11, inclui prazo prometido, responsável
e histórico de alterações, preservando o prazo original. Revisões de prazo exigem
justificativa; edições concorrentes são detectadas. O cliente acompanha seus prazos
e etapas sem receber notas internas. É uma demonstração sem cobrança ou envio:
os produtos são anonimizados e os valores são medianas históricas, não preços atuais.
Novos pedidos ficam no schema `app_web`, separados dos dados usados no ML e ainda
não recebem scores do modelo. As tabelas históricas não são modificadas. Execute novamente `src.gerenciar_acessos iniciar`
para aplicar os novos campos em um ambiente já instalado.

O botão da IA aparece nas cinco páginas, exceto durante a intro. Visitantes recebem
o acesso ao login; clientes autenticados podem consultar orientações gerais da loja
e selecionar seus próprios pedidos. Analistas podem conversar sobre a fila ou um pedido selecionado.
O contexto do cliente orienta respostas curtas e diretas sobre a loja, os prazos e
as etapas. Explicações sobre score ficam reservadas às perguntas sobre a pontuação
ou a priorização, sem acrescentar avisos de ML a dúvidas comuns de acompanhamento.

Sessões duram oito horas, usam cookie HttpOnly/SameSite e são revogadas ao sair.
O backend verifica perfil, dono do pedido, origem das ações e token CSRF. Senhas
são armazenadas com scrypt; os resultados do dashboard não ficam no armazenamento
do navegador. Em HTTPS, configurar `ENTREGACERTA_COOKIE_SECURE=true` e informar
as origens exatas em `ENTREGACERTA_ORIGINS`. Os valores padrão são para localhost
na porta 8000. A implantação pública requer HTTPS e uma revisão operacional;
recuperação de senha, verificação de e-mail e MFA ainda não fazem parte deste escopo.

Para repetir os testes (PostgreSQL disponível; schema temporário criado e removido):

```powershell
$env:ENTREGACERTA_TEST_POSTGRES="1"
.\.venv\Scripts\python.exe -m unittest tests.test_acesso_web tests.test_pedidos_web -v
```

**Validação anterior (12/11): 14 testes aprovados**: bloqueios por perfil, acesso direto às APIs/HTML,
isolamento de pedidos, CSRF/origem, hash e cookie, tentativas de login,
logout/expiração, transições dos pedidos e filtros históricos. O fluxo cliente →
analista → cliente também foi conferido no navegador, assim como a fila histórica
de 24.667 pedidos/2.466 priorizados e layouts desktop/celular. Sem a variável acima,
os testes de integração PostgreSQL são explicitamente ignorados.

**Atualização de 13/11:** os 12 testes de `test_acesso_web.py` passaram, incluindo
prazo, atribuição, auditoria, privacidade, conflitos de edição e migração repetível.
O fluxo foi conferido no Edge em desktop e celular; nesses testes de interface, a
GenAI foi simulada e o ML não foi executado. A migração local do schema web foi aplicada.



## Organização do projeto — ponto 1 (13/11/2026)

Objetivo: separar o uso diário da aplicação dos estudos de ML e diminuir a
quantidade de arquivos sem perder a evidência necessária ao artigo.

### O que mudou

- Ponto 0 guardado antes de mover/remover arquivos: 995 arquivos, 1.464.715.215
  bytes originais, com leitura integral do ZIP e comparação SHA-256.
- main.py reúne iniciar, preparar-banco, criar-analista, verificar e testar.
  Não é necessário executar uma lista de módulos internos para abrir a aplicação.
- Carga e consulta do PostgreSQL foram reunidas em src/banco.py. O comando de
  analistas passou para main.py; imports foram atualizados.
- A pasta src passou de 29 arquivos de código/SQL para 15, contando a pequena
  compatibilidade necessária aos Joblib antigos. Dados/modelos não são retreinados
  nem substituídos ao iniciar a aplicação.
- Scripts de GAN, doses, históricos, recall e previsão operacional, suas configurações
  e seus testes foram agrupados em experimentos/. Os notebooks correspondentes
  ficaram em Notebooks/experimentos/. Os notebooks principais 01 e 02 ficam à vista.
- HGB antigo e o estudo PLN foram separados em experimentos/legado; os resultados
  HGB ficaram em Modelos/legado_hgb. Os notebooks antigos ficaram em Notebooks/legado.
- O guia CTGAN foi integrado ao índice experimentos/README.md. O README principal
  foi reduzido; as funcionalidades recentes do assistente/loja/PDF foram preservadas
  no registro histórico acima. Docs/instalacao_novo_pc.md é o guia atual de execução.
- Saíram da pasta ativa os rascunhos Notebooks/testes (inclusive CSV derivado),
  a página de heatmap sem referência na aplicação, o teste antigo de GenAI sem
  autenticação, a nota PostgreSQL com nome antigo do contêiner, a pasta vazia
  DataSet Emocoes, placeholders desnecessários e caches Python.
- Os ZIPs visuais V1/V2 saíram de frontend/versoes e permanecem no ponto 0.
  Os arquivos ativos do frontend, o .env e as saídas científicas dos notebooks
  foram comparados com o backup e preservados.
- Corrigido um erro preexistente no notebook 02: "7import pandas as pd" virou
  "import pandas as pd". Não houve treinamento nem alteração de suas saídas.
- O código exato das execuções anteriores está em
  experimentos/legado/codigo_execucoes_ponto0.zip. Hashes históricos não foram
  substituídos pelos hashes do código reorganizado. O notebook 05 verifica a cópia
  histórica; um módulo pequeno de compatibilidade abre a classe Cenario dos Joblib.
- Doses/históricos aceitam --saida para novas rodadas, e um protocolo divergente
  agora é recusado antes de regravar o snapshot. Os resultados antigos ficam separados.
- .env.example foi simplificado para as variáveis utilizadas pelo código atual.
  Nenhuma chave real foi alterada, exibida ou incluída na documentação.

### Conferências executadas

- 57 testes de aplicação/dados passaram com integração PostgreSQL habilitada:
  autenticação, permissões, CSRF, pedidos, assistente, PDF, tratamento e inicialização.
  Os testes de banco usam schemas temporários; a GenAI usa fixtures técnicas.
- 40 testes dos experimentos passaram, mais 2 novos testes para compatibilidade
  de serialização e preservação de snapshots: 99 testes aprovados no total.
- main.py verificar consultou 91.390 pedidos, realizou inferência sobre os 24.667
  da validação e formou a fila de 2.466.
- O código original do ponto 0 foi carregado para comparação com o ponto 1:
  mesmos pedidos, scores iguais bit a bit e prioridades idênticas via PostgreSQL.
- 215 arquivos de dados/modelos/métricas mantêm os hashes do ponto 0 (incluindo
  os resultados HGB movidos). O modelo web e sua política de 10% não foram alterados.
- main.py iniciar foi exercitado com Docker e servidor real numa porta local livre,
  para não interromper um servidor da equipe: páginas/assets responderam 200 e
  /api/prioridades retornou 401 sem autenticação. O servidor de teste foi encerrado.
- Sintaxe Python e estrutura/código dos 8 notebooks conferidos. As células de
  leitura/imports dos notebooks 04/05 foram executadas; o notebook 06 foi executado
  em memória, conferindo artefatos, métricas e scores, com treino/regravação desligados.
- O restaurador foi testado em um projeto temporário: recuperou o arquivo da versão
  escolhida e preservou tanto o ambiente quanto a pasta substituída.

### Divergência preexistente e limites

Dados/previsoes_demo_validacao.csv é uma exportação histórica que não corresponde
ao modelo atualmente salvo. Essa diferença já existia no ponto 0: todos os seus
24.667 scores diferem da execução atual (diferença absoluta máxima de aproximadamente
0,2869). O CSV foi preservado como evidência, sem regravar uma rodada antiga.
Para validar a aplicação atual, use main.py verificar e a comparação ponto 0/1
registrada acima; não use esse CSV como referência dos scores atuais.

Não foram retreinados os modelos nem executados integralmente os notebooks 01/02
e o CTGAN inicial. Não houve nova chamada à API externa de GenAI. As verificações
de HTTP não substituem uma nova revisão visual em navegador. A carga inicial inteira
do banco não foi repetida; sua proteção foi testada e os fluxos de aplicação usam o
banco já existente. Alertas de depreciação do NumPy/Pandas e de IDs ausentes em
notebooks antigos não impediram as verificações; versões dos ambientes foram preservadas.

### Restauração

A pasta irmã EntregaCertaAI_Pontos guarda ponto_0.zip, ponto_1.zip e os manifestos
de integridade. O restaurador confere os arquivos antes de trocar pastas e preserva
a versão substituída com data/hora. Ver Docs/instalacao_novo_pc.md.

Os ZIPs incluem o estado local do Git e o .env; não devem ser publicados.
Os ambientes .venv/.venv-ctgan e o volume PostgreSQL ficam fora dos ZIPs.
O banco permanente não foi recarregado; nenhum commit/push ou alteração de autoria
foi feito. O registro detalhado de movimentos está em alteracoes_ponto1.json junto
aos pontos locais.

## Guia do pipeline completo — atualização de documentação (13/11/2026)

O guia de inicialização passou a descrever dez etapas, dos CSVs originais à aplicação.
Foram conferidos os módulos preparar_dados, tratar_dados_ml e inferencia, os comandos
de main.py e as posições/títulos das células do notebook 02. O notebook 01 aparece
como preparação didática/conferência, sem exigir transformação duplicada.

O roteiro registra o nome de consolidado esperado pelo notebook, posterga as
avaliações de teste até depois das escolhas na validação, separa Cross Entropy/PCA
do fluxo MLP exportado e exige gerar o CSV de inferência antes de conferi-lo.
Também distingue primeira carga, recarga histórica e abertura diária.

Alterados apenas este registro, Docs/instalacao_novo_pc.md e a referência no README.
Links locais, marcos das células, entradas executáveis e ajuda de main.py foram
conferidos; diff --check passou. Não houve novo treino, preparação completa ou carga
de banco. Os ZIPs ponto 0/1 permanecem como fotografias anteriores, sem regravação.
