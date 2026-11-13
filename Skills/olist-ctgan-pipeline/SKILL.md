---
name: olist-ctgan-pipeline
# Skill independente, em português, para ser lida por agente de código em repositório existente.
description: Auditar e adaptar projeto Python Olist de previsão de atrasos, restringindo a pedidos com exatamente um vendedor, incorporando seller_id e históricos individuais sem vazamento, preservando tratamento existente, implementando contratos exatos de dados limpos, CTGAN e ML, simulação reprodutível de vieses logísticos e avaliação exclusivamente em dados reais.
---

# SKILL — Olist: um vendedor por pedido → enriquecimento → CTGAN → viés controlado → ML → avaliação

**Leia este documento integralmente antes de editar.** O usuário fornecerá **somente esta skill**, sem a conversa que a originou. A skill é autossuficiente. O projeto Python, seus datasets, notebooks e scripts **já existem**: primeiro examiná-los; depois fazer mudanças pontuais, com compatibilidade, testes e explicação do que foi preservado.

## 0. Objetivo, domínio e decisões fechadas

O problema é **prever se um pedido da Olist será entregue ao comprador após o prazo prometido** (`atrasou` = 0/1). Existem registros reais com grande desbalanceamento (o usuário citou como exemplo ~40 mil no prazo e ~1 mil atrasados; **não tratar essas quantidades como medidas da base atual**). O usuário pretende enriquecer o dataset original, gerar muitos pedidos plausíveis com CTGAN, produzir **cenários propositalmente enviesados** em que certas características elevam ou reduzem a probabilidade sintética de atraso, treinar ML e verificar se os modelos generalizam para **pedidos reais**.

**NOVA DECISÃO MAIS IMPORTANTE (sobrescreve qualquer documentação anterior): considerar SOMENTE PEDIDOS COM EXATAMENTE UM VENDEDOR DISTINTO (`seller_id`).** O usuário informa que pedidos com múltiplos vendedores seriam menos de 3% dos dados originais; **medir essa proporção no repositório**, sem presumir o percentual. Um pedido pode continuar tendo 1, 2 ou mais itens, produtos e categorias — desde que todos os itens venham **do mesmo seller_id**. A granularidade é **uma linha por `order_id`**, e `seller_id` passa a identificar diretamente seu único vendedor.

Regras mandatórias:

1. **Filtrar pedidos com `nunique(seller_id) == 1` ANTES do enriquecimento e da formação do dataset final.** Fazer a contagem usando `order_items` bruto/estágio confiável; não inferir unicidade somente de `quantidade_vendedores` sem conferir. Excluir pedidos sem vendedor ou com mais de um vendedor. Medir e relatar percentuais e classes perdidos, por split. Não eliminar múltiplos ITENS do mesmo vendedor.
2. **Preservar as rotinas já existentes** de leitura, agregação, tratamentos, cálculo de rótulo e treino quando válidas. Evitar reescrever todo o repositório; mapear e adaptar módulos reais. Não apagar dados originais, notebooks ou modelos existentes.
3. **`seller_id` deve ser mantido no arquivo limpo e no filtrado para ML como METADADO, NUNCA como feature de CTGAN/ML.** IDs de vendedores reais vêm de `order_items` e não podem ser inventados. Para pedidos sintéticos, atribuir identificadores explicitamente sintéticos sem fingir que são novos pedidos de vendedores reais (ver seção 6).
4. **Renomear para semântica de vendedor singular**: `uf_origem` → `seller_state`; `distancia_media_vendedores_km` / `distancia_max_vendedores_km` → **uma coluna**, `distancia_vendedor_cliente_km`; `nota_historica_vendedores_media` → `nota_historica_vendedor_media`; `qtd_avaliacoes_historicas_vendedores` → `qtd_avaliacoes_historicas_vendedor`; `frequencia_avaliacoes_baixas_vendedores` → `frequencia_avaliacoes_baixas_vendedor`.
5. **Remover `quantidade_ufs_origem` e `quantidade_vendedores` das features**: após filtragem ambos são constantes (1). Remover as duas distâncias antigas; não mantê-las junto da distância nova. Coordenadas latitude/longitude são insumos temporários de cálculo, não features finais.
6. Não criar transportadoras, envios ou métricas fictícias não presentes no Olist. O usuário cancelou a ideia de transportadoras simuladas; o **viés intencional** virá de regras parametrizadas sobre atributos reais/derivados, não de simular empresa transportadora.
7. Excluir do dataset final todas as colunas que representam dados **faltantes/sem peso/sem dimensões/sem categoria/sem distância/sem UF**, e atributos de pagamento como `valor_pago`, ausência de `valor_pago`, formas de pagamento, parcelas etc. Faltantes podem ser analisados em **relatório separado**, e valores faltantes das features válidas exigem tratamento — não confundir remover flags com dispensar imputação.
8. Manter só os 3 históricos individuais do vendedor: `nota_historica_vendedor_media`, `qtd_avaliacoes_historicas_vendedor`, `frequencia_avaliacoes_baixas_vendedor` (proporção de avaliações com `review_score <= 3`). Somente reviews **disponíveis antes da aprovação do pedido**, com deduplicação e sem reviews do próprio pedido.
9. `mes_aprovacao` **não** integra o dataset limpo nem entrada/saída base da CTGAN. Calcular de `order_approved_at` **somente na montagem do dataset filtrado para ML**. Excluir `hora_aprovacao`, `tempo_aprovacao_horas` e `dia_semana_aprovacao` inteiramente dos contratos finais.
10. **Validação e teste estritamente REAIS** (prevalência natural); CTGAN e simulação atuam somente sobre a partição de treino. Não modificar `atrasou` real. Comparar baseline sem sintéticos, baseline + sintéticos com rótulos hipotéticos e eventuais ablações. A CTGAN **não demonstra causalidade** e os rótulos simulados não provam hipóteses sobre o Olist.
11. Preparar EDA simples executável **posteriormente** e reusar a limpeza já implementada, sem criar uma segunda transformação contraditória.

### Contratos congelados e contagem

| Saída | Total | Composição |
|---|---:|---|
| **A. `pedidos_ml_limpo_enriquecido` real** | **23 colunas** | 5 metadados (inclui `seller_id` e data) + 17 atributos + 1 alvo |
| **B. Entrada da CTGAN** | **15 colunas** | 15 atributos geráveis, sem razões determinísticas, rótulo, IDs, data e controles |
| **C. `pedidos_sinteticos` pós-validação/simulação** | **23 colunas** | Mesmo esquema do A, com IDs sintéticos e alvo simulado |
| **D. `pedidos_ml_filtrado`** | **23 colunas** | 4 metadados (`order_id`, `seller_id`, `particao`, `origem_dado`) + 18 features de ML + 1 alvo |

**Não alterar essas quantidades sem autorização expressa.** Exemplos das quatro listas completas nas seções 3–6 e no `CONFERIR_COLUNAS.md` auxiliar. `seller_id` não integra nem B nem o `X` de D.

## 1. Entender o código e o dataset que já existem — executar antes de editar

### 1.1 Colunas antigas informadas pelo usuário (37)

A relação abaixo descreve **`pedidos_ml` existente**, não o esquema novo. Validar o que realmente existe e identificar origem/uso de cada coluna.

```text
01 order_id
02 particao
03 order_approved_at
04 customer_state
05 uf_origem
06 categoria_principal
07 quantidade_itens
08 quantidade_produtos
09 quantidade_vendedores
10 quantidade_categorias
11 quantidade_ufs_origem
12 valor_itens
13 valor_frete
14 peso_total_g
15 volume_total_cm3
16 itens_sem_peso
17 itens_sem_dimensoes
18 itens_sem_categoria
19 distancia_media_vendedores_km
20 distancia_max_vendedores_km
21 vendedores_sem_distancia
22 vendedores_sem_uf
23 valor_pago
24 quantidade_pagamentos
25 quantidade_formas_pagamento
26 parcelas_maximas
27 tipo_pagamento_principal
28 prazo_prometido_dias
29 tempo_aprovacao_horas
30 dia_semana_aprovacao
31 mes_aprovacao
32 hora_aprovacao
33 rotulo_disponivel_em
34 atrasou
35 origem_dado
36 rotulo_observado
37 experimento_id
```

**`seller_id` não constava dessas 37 colunas**: precisa ser recuperado em `olist_order_items_dataset.csv` ou no estágio real que ainda o contenha. Não deduzir um vendedor pela UF de origem ou pela categoria. `seller_state` corresponde ao `seller_state` do catálogo de vendedores, ou ao `uf_origem` validado como único para o seller; se houver divergências, comparar com `olist_sellers_dataset.csv` e registrar.

### 1.2 Checklist inicial de inspeção do repositório

- Usar `git status`/estrutura atual; identificar CSVs, notebooks, módulos `src`, `requirements`, arquivos de configuração, artefatos `joblib` e scripts de ML existentes. Exemplos conhecidos **não garantidos**: `pedidos_ml.csv`, `Modelos/dados_ml.joblib`, Jupyter/VS Code, RF/HGB/RN/GMM.
- Localizar **o código que hoje produz `pedidos_ml`** e os pontos de agregação por `order_id`, merges, imputações, seleção de colunas e `atrasou`.
- Confirmar quais tabelas Olist já estão disponíveis: orders, order_items, order_reviews, sellers, customers, products, geolocation. Não baixar/sobrescrever sem necessidade; não fabricar dados indisponíveis.
- Validar `seller_id` em `order_items`: agrupamento `order_id -> nunique(seller_id)` e `nunique(order_id,seller_id)`; conferir `quantidade_vendedores` antigo sem usá-lo como verdade exclusiva.
- **Antes de filtrar**: registrar número de pedidos com 0, 1 e >=2 vendedores, proporções e contagem `atrasou` por grupo; **depois de filtrar**, registrar quanto cada split perde e a prevalência real de atraso resultante. Verificar a afirmação de "menos de 3%" contra os dados, sem inverter o filtro caso os percentuais não coincidam.
- Confirmar split temporal já realizado (em conversas anteriores foi considerada proporção 70/15/15 ordenada por data; **não supor que já está assim**). Preservar partições temporais coerentes; se refizer, justificar e manter resultados reproduzíveis. Evitar que pedidos do mesmo ID caiam em splits diferentes.
- Conferir tratamento existente de datas, nulos, duplicatas, volume/quantidade, Haversine, preços e categoria. As agregações devem representar um único vendedor, mas **podem continuar somando vários itens do mesmo vendedor**.
- Criar relatório de auditoria indicando o que será reutilizado, o que precisa de correção, módulos afetados e resultado de testes, antes de refatorar. Respeitar o estilo de código e ambiente já existente (inclusive Windows/Jupyter/Docker, quando aplicável).

### 1.3 Atraso real: não confundir entrega à transportadora com entrega ao comprador

Nos CSVs Olist usuais:

- `order_delivered_carrier_date`: o pedido foi entregue **à transportadora**.
- `order_delivered_customer_date`: o pedido foi entregue **ao comprador**.
- `order_estimated_delivery_date`: data **estimada/prometida ao comprador**.
- `shipping_limit_date` (em itens): prazo relacionado à expedição pelo vendedor, **outro fenômeno**.

Rótulo-alvo para **entrega atrasada ao cliente**: em pedidos elegíveis, entregues e com timestamps confiáveis, `atrasou = int(order_delivered_customer_date > order_estimated_delivery_date)`. Verificar a definição no **código existente** antes de substituir qualquer rotina; documentar filtros de pedidos cancelados, não entregues e rótulos ainda não observáveis. Não classificar silenciosamente entregas não observadas como 0. `order_delivered_customer_date`, `order_delivered_carrier_date`, `review_score` do próprio pedido, `order_status` final e demais variáveis posteriores **jamais entram como features**; permanecem nas tabelas de origem/staging apenas para construção do rótulo ou avaliação retrospectiva.

`prazo_prometido_dias` precisa representar prazo disponível no momento de prever o pedido (p.ex. diferença entre prazo estimado e data de aprovação/compra conforme o código existente); **não é atraso em dias** e não pode usar a data da entrega realizada.

## 2. Fluxo completo obrigatório e critérios por etapa

```text
[01] CSVs originais Olist + código existente de construção de pedidos_ml
     │  INSPECIONAR estrutura e manter transformações confiáveis
     ▼
[02] Tratamento real + validação de atraso + FILTRO 1 SELLER
     │  order_items: nunique(seller_id) == 1; 1 linha por order_id;
     │  seller_id preservado; vários itens do mesmo seller permitidos;
     │  filtros e partições reais documentados
     ▼
[03] Engenharia e enriquecimento sem vazamento
     │  seller_state + 1 distância vendedor–cliente;
     │  3 históricos do seller as-of; 2 razões matemáticas;
     │  preservar os 5 metadados e o rótulo real
     ▼
     DATASET LIMPO REAL A: 23 colunas EXATAS
     │  sem mes_aprovacao, sem pagamentos, sem flags de falta,
     │  sem quantidades/distâncias redundantes de múltiplos sellers
     ▼
[04] Treinar CTGAN — B: 15 colunas EXATAS, somente TREINO REAL
     │  não usar seller_id, order_id, datas, particao, atrasou,
     │  preco_medio_item ou proporcao_frete_valor
     ▼
[05] Gerar muitos pedidos sintéticos e validar
     │  preservar maioria de 1 item quando houver no treino;
     │  criar order_id e seller_id sintéticos; recomputar razões;
     │  conferir distribuições, limites, UFs, históricos e coerência
     ▼
[06] Introduzir VIÉS PROPOSITAL por simulador (seed configurável)
     │  prob. atraso elevada/diminuída por distância, peso, volume,
     │  categoria, preço, frete, prazo, histórico individual;
     │  taxa-alvo inicial ≈1 atraso em cada 6 pedidos SINTÉTICOS;
     │  SEM tocar nos rótulos de pedidos reais
     ▼
     DATASET SINTÉTICO C: 23 colunas EXATAS
     ▼
[07] Construir dataset ML D: 23 colunas
     │  remover order_approved_at; DERIVAR mes_aprovacao AQUI;
     │  18 features X + alvo atrasou + 4 metadados;
     │  splits reais e sintéticos corretamente separados
     ▼
[08] Treinar baseline e modelo com aumento CTGAN; avaliar em reais
     │  validação REAL para seleção de modelos, hiperparâmetros/limiar;
     │  teste REAL para comparação final; relatar ganho ou piora
     ▼
[09] EDA simples POSTERIOR (read-only, não obrigatória para executar)
     │  distribuição 1/2/3+ itens, taxa de atraso real por faixas,
     │  histórico vendedor, real x sintético, vieses e limitações
```

**Etapa 02 deve acontecer antes de treinar CTGAN e antes de calcular históricos agregados do dataset de saída.** Não filtrar um pedido com vários sellers depois de ter misturado seus atributos; o filtro exige retorno ao item bruto/estágio com seller_id. Históricos de seller podem considerar reviews elegíveis de qualquer pedido anterior **com um único vendedor**, de forma coerente com a população filtrada e sem informação futura.

## 3. CONTRATO EXATO A — Dataset LIMPO REAL ENRIQUECIDO: 23 colunas

**Nome sugerido:** `pedidos_ml_limpo_enriquecido.parquet`. Uma linha por `order_id` real, unicamente 1 `seller_id`. A ordem das colunas é esta e não deve variar sem versão de contrato:

| # | Nome EXATO | Tipo | Papel/fonte |
|---:|---|---|---|
| 1 | `order_id` | string | ID real único do pedido, metadado |
| 2 | `seller_id` | string | ID real único do vendedor do pedido, de `order_items`, metadado |
| 3 | `particao` | `treino`/`validacao`/`teste` | Split temporal REAL, metadado |
| 4 | `order_approved_at` | datetime | Referência para histórico e derivação posterior de mês; metadado |
| 5 | `customer_state` | UF | Estado do comprador, feature |
| 6 | `seller_state` | UF | Estado do **único vendedor**; substitui `uf_origem`, feature |
| 7 | `categoria_principal` | categoria | Categoria principal dos itens do pedido, feature |
| 8 | `quantidade_itens` | inteiro >= 1 | Quantidade total de itens, inclusive repetições, feature |
| 9 | `quantidade_produtos` | inteiro >= 1 | Quantidade de produtos distintos, feature |
| 10 | `quantidade_categorias` | inteiro >= 1 | Quantidade de categorias distintas (após política de nulos), feature |
| 11 | `valor_itens` | numérico >= 0 | Soma do preço dos itens, feature |
| 12 | `valor_frete` | numérico >= 0 | Soma do frete dos itens, feature |
| 13 | `peso_total_g` | numérico >= 0 | Soma do peso associado aos itens, feature |
| 14 | `volume_total_cm3` | numérico >= 0 | Soma do volume associado aos itens, feature |
| 15 | `distancia_vendedor_cliente_km` | numérico >= 0 | Uma distância entre seller e cliente, substitui média/máxima, feature |
| 16 | `prazo_prometido_dias` | numérico >= 0 | Prazo prometido conhecido antes da entrega, feature |
| 17 | `nota_historica_vendedor_media` | float [1, 5] ou nulo | Média de reviews **anteriores** do seller, nova feature |
| 18 | `qtd_avaliacoes_historicas_vendedor` | inteiro >= 0 | Nº de reviews **anteriores** do seller, nova feature |
| 19 | `frequencia_avaliacoes_baixas_vendedor` | float [0, 1] ou nulo | Fração das reviews anteriores com nota <= 3, nova feature |
| 20 | `preco_medio_item` | numérico >= 0 | `valor_itens / quantidade_itens`; derivada |
| 21 | `proporcao_frete_valor` | numérico >= 0 ou nulo | `valor_frete / valor_itens`; derivada |
| 22 | `atrasou` | 0/1 | ALVO **REAL** extraído de datas de entrega/promessa |
| 23 | `origem_dado` | `real` | Metadado de origem |

**Contagem:** 5 metadados = `order_id`, `seller_id`, `particao`, `order_approved_at`, `origem_dado`; 17 features; 1 alvo = **23**.

### 3.1 Seleção/derivação detalhada de geografia no caso 1 seller

- `seller_id`: a relação de sellers por pedido nasce de `order_items[['order_id','seller_id']]` sem nulos. Agrupar `nunique()` e **reter somente pedidos com exatamente um ID**. Usar `drop_duplicates(['order_id','seller_id'])` para gerar o mapeamento 1:1; validar com `merge(validate='one_to_one')` quando apropriado. Não duplicar o pedido ao juntar itens.
- `seller_state`: consultar `sellers` pelo `seller_id` e comparar com `uf_origem` anteriormente agregado. Caso haja divergência, gerar auditoria; não substituí-la silenciosamente por outra UF. Pode haver `customer_state` distinto da UF do vendedor.
- `distancia_vendedor_cliente_km`: priorizar recomputar a distância geodésica por Haversine entre localização agregada do CEP de cliente e vendedor, conforme código de geolocalização já existente. Em casos de seller único, `distancia_media_vendedores_km` e `distancia_max_vendedores_km` **deveriam coincidir se tiverem a mesma definição**; usá-las para checagem e eventual migração com tolerância, mas não produzir duas features. Com coordenada inválida/ausente, seguir política de imputação documentada usando **somente o treino**, sem inventar distância física exata. Latitude/longitude e CEPs são colunas de estágio, não do contrato A.
- `quantidade_vendedores` e `quantidade_ufs_origem` **não entram no A** porque sua variância após o filtro seria zero. Verificar que são 1 onde o código prévio mantiver essas colunas para auditoria.
- `quantidade_itens`, `quantidade_produtos` e `quantidade_categorias` continuam relevantes: um seller pode vender vários produtos/categorias no mesmo pedido. `quantidade_itens >= quantidade_produtos >= quantidade_categorias` quando categorias estão preenchidas e definidas como distintas; documentar política para categoria ausente.

### 3.2 Valores faltantes e dados removidos

Remover colunas de *indicadores de ausência* não significa necessariamente remover linhas com `NaN`. Na camada de tratamento, relatar ausência de peso, dimensões, geolocalização, histórico, preço etc. em **arquivo separado**; decidir descartar/imputar conforme cobertura, sem usar informações de validação/teste para ajustar imputador. Se não houver histórico anterior, manter `qtd_avaliacoes_historicas_vendedor=0` e média/frequência como nulo na base conceitual; codificação para CTGAN/ML será técnica, ajustada no treino. Não criar `tem_historico`, `faltante_peso`, `faltante_valor_pago` ou equivalentes como atributos finais.

### 3.3 Comparação EXATA das 37 colunas antigas com o contrato A

**Manter do antigo SEM renomear (15 colunas):**

```text
order_id
particao
order_approved_at
customer_state
categoria_principal
quantidade_itens
quantidade_produtos
quantidade_categorias
valor_itens
valor_frete
peso_total_g
volume_total_cm3
prazo_prometido_dias
atrasou
origem_dado
```

**Manter, mas RENOMEAR (1 coluna):** `uf_origem` → `seller_state` (confirmar valor na fonte `sellers`).

**Remover do contrato A (21 colunas antigas):**

```text
01 quantidade_vendedores
02 quantidade_ufs_origem
03 distancia_media_vendedores_km
04 distancia_max_vendedores_km
05 itens_sem_peso
06 itens_sem_dimensoes
07 itens_sem_categoria
08 vendedores_sem_distancia
09 vendedores_sem_uf
10 valor_pago
11 quantidade_pagamentos
12 quantidade_formas_pagamento
13 parcelas_maximas
14 tipo_pagamento_principal
15 tempo_aprovacao_horas
16 dia_semana_aprovacao
17 mes_aprovacao
18 hora_aprovacao
19 rotulo_disponivel_em
20 rotulo_observado
21 experimento_id
```

**Adicionar ao contrato A (7 colunas, sendo 2 recuperadas/recalculadas + 5 engenheiradas):**

```text
01 seller_id                           # de order_items; novo no agregado pedidos_ml
02 distancia_vendedor_cliente_km      # geodésica de seller ÚNICO ao cliente
03 nota_historica_vendedor_media
04 qtd_avaliacoes_historicas_vendedor
05 frequencia_avaliacoes_baixas_vendedor
06 preco_medio_item
07 proporcao_frete_valor
```

**Conferência de aritmética:** 37 antigas − 21 removidas + 7 adicionadas = **23 colunas**, com 1 coluna original renomeada. Não apagar as colunas removidas dos **CSVs brutos/staging** quando forem necessárias para cálculos, controle de rótulos, auditoria ou reconstrução de features. Retirá-las dos **contratos finais** e entradas dos modelos.

**Não incluir** atributos de transportadoras fictícias, médias/máximas de múltiplos sellers, latitude/longitude/CEP como feature, `seller_id` como feature, taxa histórica de atraso de seller derivada de rótulos futuros, pagamentos, indicadores de falta ou datas de entrega realizada em X.

## 4. CONTRATO EXATO B — Matriz usada em CTGAN.fit(): 15 atributos

**Nome:** `ctgan_treino_features.parquet`. Usar apenas `particao == 'treino'` e `origem_dado == 'real'` do contrato A (após filtrar 1 vendedor e enriquecer), sem aprender estatísticas de validação/teste. **Não** passar identificadores, alvo, datas ou razões determinísticas. A CTGAN gera perfis de pedidos; no experimento principal quem cria `atrasou` é um simulador externo.

```python
CTGAN_FEATURES = [
    "customer_state",
    "seller_state",
    "categoria_principal",
    "quantidade_itens",
    "quantidade_produtos",
    "quantidade_categorias",
    "valor_itens",
    "valor_frete",
    "peso_total_g",
    "volume_total_cm3",
    "distancia_vendedor_cliente_km",
    "prazo_prometido_dias",
    "nota_historica_vendedor_media",
    "qtd_avaliacoes_historicas_vendedor",
    "frequencia_avaliacoes_baixas_vendedor",
]
assert len(CTGAN_FEATURES) == 15
```

Tipos sugeridos: discretas `customer_state`, `seller_state`, `categoria_principal`; contagens de itens/produtos/categorias inteiras (decidir se discretas conforme cardinalidade), numericamente contínuas os valores/peso/volume/distância/prazo/nota/frequência, count de reviews com conversão de inteiro e possível `log1p` reversível. Usar `discrete_columns` na API CTGAN efetivamente instalada, não inventar parâmetros; salvar versão, seed, lote, épocas e transformadores.

**Ausência de histórico:** `n_review=0` implica nota/frequência indisponíveis. Preservar esse significado via representação técnica de nulos compatível com CTGAN (p.ex. sentinelas internas, restrições cruzadas e restauração), documentar e testar; **não permitir nota e frequência fabricadas como histórico observado quando count==0**. Não deixar a rede aprender sentinelas como valores finais inválidos. Ajustar preprocessamento apenas em treino real.

`preco_medio_item` e `proporcao_frete_valor` NÃO participam da CTGAN: serão recalculados exatamente após geração. `seller_id` NÃO participa da CTGAN: cardinalidade alta causaria memorização e não é preditor. `mes_aprovacao` não entra nesta etapa.

**Opcional, experimento independente (não padrão):** treinar uma CTGAN com rótulo `atrasou` REAL como coluna discreta adicional (16 atributos), para comparar com a simulação, mantendo isolamento do teste. Não confundir os dois métodos de rotulagem e não modificar o contrato principal de 15 colunas.

## 5. Engenharia dos 3 históricos do VENDEDOR ÚNICO e de 2 razões

### 5.1 Históricos temporais sem vazamento — algoritmo exigido

O Olist possui reviews por **pedido**, não nota objetiva atribuída diretamente ao vendedor. Como o dataset é restrito a pedidos de **um só vendedor**, a review do pedido pode ser usada como **proxy da experiência com esse seller** com menos ambiguidade — ainda assim envolve também entrega/plataforma, não representa necessariamente a qualidade pura do vendedor.

1. Montar a tabela de relação de pedidos elegíveis com `order_id`, `seller_id`, `order_approved_at` e a origem do split; garantir um único seller por pedido. **Para o histórico**, utilizar eventos reais de reviews anteriores associados a pedidos com um único seller (incluir apenas reviews temporalmente válidas, conforme política documentada).
2. Ler `order_reviews` (`order_id`, `review_id`, `review_score`, `review_answer_timestamp`, `review_creation_date` para auditoria). Inspecionar vários registros por pedido e deduplicar por identidade da avaliação. Uma review de pedido com 5 itens do mesmo seller conta **uma vez**, não cinco.
3. O timestamp da avaliação efetivamente disponível deve ser `review_answer_timestamp` quando confiável: `review_creation_date` costuma indicar emissão/solicitação de review, não preenchimento pelo comprador; não a usar como se provasse disponibilidade da nota.
4. Em cada pedido alvo na data de aprovação T, consultar **somente** reviews desse seller com `review_answer_timestamp < T` (estritamente anterior) e score válido. Nunca incluir review do próprio pedido ou review respondida no futuro. Considere timezone/datetime e eventos com data faltante.
5. Calcular para o seller único: `qtd_avaliacoes_historicas_vendedor = n(T)`; `nota_historica_vendedor_media = sum(review_score) / n(T)`; `frequencia_avaliacoes_baixas_vendedor = count(review_score <= 3) / n(T)`. **Nota exatamente 3 entra no numerador de avaliações baixas; nota 4 não**. Não usar média de sellers, pois existe apenas um seller por pedido.
6. Se `n(T)==0`: count=0 e nota/frequência=NaN (ou outro código técnico **somente durante treino de CTGAN**). Não preencher com a avaliação do próprio pedido. Se optar por smoothing/shrinkage, documentar de forma separada e preservar as três features conceituais.
7. Evitar cálculo ingênuo `groupby('seller_id').mean()` sobre todo o dataset. Preferir `merge_asof`/soma cumulativa temporal ou busca binária por seller, com cuidado para simultaneidade e `<` estrito. Não fundir review que ocorreu antes da compra de um pedido mas depois da compra de outro de maneira a contaminar histórico deste último.
8. Validar por testes manuais: dois pedidos do mesmo seller, uma review respondida entre datas; o segundo pode ver a review, o primeiro não. Repetição de itens não multiplica reviews. Avaliação do próprio pedido não vaza. Review de seller diferente não influencia. Reviewer `<=3` correto. Id de seller real preservado ao juntar.
9. É possível computar históricos cronológicos com todos os **eventos de review reais já observados no momento T**, mesmo que o pedido que gerou a review tenha sido criado em outro split, desde que a review tenha timestamp anterior a T; documentar a política para reprodução do cenário de inferência. Nunca inserir reviews sintéticas no histórico real.

### 5.2 Outras variáveis derivadas

- `preco_medio_item = valor_itens / quantidade_itens`, denominador >=1; recalcular nos sintéticos a partir dos campos gerados.
- `proporcao_frete_valor = valor_frete / valor_itens` para `valor_itens > 0`; para divisor zero/nulo, seguir política de nulo/imputação sem criar divisão infinita.
- `mes_aprovacao = pd.to_datetime(order_approved_at).dt.month` **exclusivamente na etapa [07], preparação ML**. Se a antiga coluna `mes_aprovacao` estiver salva em pedidos_ml, descartar e recalcular na etapa [07]. A CTGAN não modela calendário neste experimento; meses sintéticos gerados de timestamps amostrados do treino podem ter dependência fraca com características geradas — medir isso.

## 6. CONTRATO EXATO C — Pedidos SINTÉTICOS após CTGAN e simulador: 23 colunas

**Mesmo esquema e MESMA ORDEM do contrato A**, com `origem_dado='sintetico_ctgan'`, `particao='treino'`, `atrasou` hipotético (0/1). Os outros valores são produzidos assim:

- **15 características CTGAN**: amostradas exclusivamente do modelo treinado em dados REAIS de treino (contrato B), depois verificadas por regras de integridade e plausibilidade.
- `preco_medio_item`, `proporcao_frete_valor`: recalcular com fórmulas, jamais amostrar as proporções independentes.
- `order_id`: identificador novo que não colida com Olist real, p.ex. `ctgan_order_<run_id>_<i>`.
- `seller_id`: **identificador METADADO sintético**, p.ex. `ctgan_seller_<run_id>_<profile_id>`. Não ajustar CTGAN para IDs, não rotular vendedor real como se tivesse efetuado pedido sintético. **Atribuir de forma coerente:** preferencialmente montar um catálogo de perfis de sellers pseudonimizados (extraídos exclusivamente de treino real) com `seller_state` e históricos observáveis em datas de referência, associando perfis a pedidos amostrados com compatibilidade de UF/avaliações. Se isso for inviável para uma amostra, usar seller_id sintético exclusivo por pedido, **documentando que IDs não representam recorrência real nem série de reviews**. Não reutilizar um mesmo pseudovendedor com UF/histórico incompatível sem validá-lo. Identificação sintética NÃO significa que a CTGAN aprendeu identidade do seller.
- `order_approved_at`: data sintética de referência amostrada apenas das datas de **treino real** com seed (ou política equivalente baseada no treino), para derivar mês depois. Não considerar essas datas prova de histórico real de pseudovendedor.
- `atrasou`: preenchido APÓS a CTGAN por simulador de cenário, não no `fit()` padrão. Não criar falsas datas de entrega ao cliente para justificar o rótulo sintético; claramente identificá-lo como simulado.

### 6.1 Validações obrigatórias antes de exportar

- Uma linha por `order_id`; `seller_id` único **dentro de cada pedido**, sem evidência de múltiplos sellers; UFs válidas. Múltiplos itens continuam possíveis.
- `quantidade_itens`, `quantidade_produtos`, `quantidade_categorias` inteiros com `1 <= quantidade_categorias <= quantidade_produtos <= quantidade_itens`. Se houver categorias faltantes, aplicar a política explícita de categoria desconhecida para permitir coerência.
- `valor_itens` >0 para cálculo de proporção (ou política explícita se zero); frete, peso, volume, distância e prazo não negativos; nada de Inf. Evitar clipping massivo para esconder geração ruim; preferir rejeitar/reamostrar e reportar taxa de rejeição.
- Notas 1..5 e frequência 0..1 quando `qtd_avaliacoes_historicas_vendedor>0`; quando zero, campos históricos indisponíveis conforme política. `qtd_avaliacoes_historicas_vendedor` inteiro não negativo.
- **Não conter** `quantidade_vendedores`, `quantidade_ufs_origem`, `distancia_media_vendedores_km`, `distancia_max_vendedores_km`, colunas de qualidade, pagamentos ou qualquer campo fora das 23 colunas. `seller_state` e distância devem referir-se ao seller único do pedido; se pseudovendedor reutilizado, checar perfil coerente.
- `preco_medio_item` e `proporcao_frete_valor` consistentes matematicamente depois de gerar valores base.
- Preservar a proporção de **pedidos simples (1 item/1 produto)** medida no **treino real já filtrado para 1 seller**. Medir 2 itens e >=3 itens, distribuições condicionais de peso/volume/preço/categoria, não assumir proporção inventada; se CTGAN falhar, usar rejeição/amostragem condicional por estratos com rastreio.
- Inspecionar duplicatas/near-duplicates, tentativas de memorizar pedidos reais, outliers e mudanças relevantes de distribuição; relatório de KS/quantis/correlação/contingência quando possível. Não alegar fidelidade sem medir.

## 7. CONTRATO EXATO D — Dataset FILTRADO ML: 23 colunas, X com 18 features

**Nome sugerido:** `pedidos_ml_filtrado.parquet`. Partir dos contratos A (reais) e C (sintéticos) e trocar `order_approved_at` por `mes_aprovacao`, **somente nesta etapa**. Manter 4 metadados por rastreabilidade (inclusive seller_id, nunca em X). Lista completa de features e ordem:

```python
ML_FEATURES = [
    # Localização: 3
    "customer_state",
    "seller_state",
    "distancia_vendedor_cliente_km",

    # Produtos: 6
    "categoria_principal",
    "quantidade_itens",
    "quantidade_produtos",
    "quantidade_categorias",
    "peso_total_g",
    "volume_total_cm3",

    # Histórico temporal do vendedor: 3
    "nota_historica_vendedor_media",
    "qtd_avaliacoes_historicas_vendedor",
    "frequencia_avaliacoes_baixas_vendedor",

    # Preço e frete: 4
    "valor_itens",
    "preco_medio_item",
    "valor_frete",
    "proporcao_frete_valor",

    # Prazo/calendário: 2
    "prazo_prometido_dias",
    "mes_aprovacao",
]
ML_TARGET = "atrasou"
ML_METADATA = ["order_id", "seller_id", "particao", "origem_dado"]
ML_DATASET_COLUMNS = ML_METADATA + ML_FEATURES + [ML_TARGET]
assert len(ML_FEATURES) == 18
assert len(ML_DATASET_COLUMNS) == 23
```

**Não utilizar `seller_id` nem `order_id` como feature** (alto risco de memorizar identidades, inclusive nos sintéticos). **Não incluir `order_approved_at` no dataset D**; a data entra apenas na construção e na inferência para derivação de `mes_aprovacao`. O alvo `atrasou` só existe em registros com desfecho conhecido/rotulado; em inferência sobre pedido novo, fornecer somente as **18 features** transformadas e processar o seller histórico *as-of*.

Para regressões de risco e simulações, X tem características pré-entrega, sem usar timestamps de entrega, rótulos de revisão do próprio pedido ou probabilidades simuladas como feature.

## 8. Cenário de ATRASO intencionalmente enviesado nos sintéticos

**CTGAN não aprende as relações hipotéticas automaticamente se elas não estiverem nos dados reais.** Implementar a arquitetura **CTGAN geradora de pedidos + validador/seleção opcional + simulador probabilístico configurável do rótulo**. Chamaremos isso de *pipeline de síntese enviesada*, não de causalidade aprendida pela CTGAN. Avaliar se ajuda ou atrapalha no **teste real**.

### 8.1 Hipóteses do usuário e direções experimentais

| Feature CTGAN / derivada | Direção a testar APENAS em rótulos sintéticos | Ressalva |
|---|---|---|
| `distancia_vendedor_cliente_km` | Mais distante → maior `p(atrasou)` | Hipótese logística plausível; medir no real |
| `peso_total_g` | Mais pesado → maior risco | Evitar duplicar efeito de volume |
| `volume_total_cm3` | Maior volume → maior risco | Pode correlacionar com categoria/peso |
| `categoria_principal` | Risco por categoria escolhido em config | Não atribuir riscos arbitrários escondidos |
| `valor_itens`, `preco_medio_item` | Preço maior → risco maior | Hipótese, não um fato Olist |
| `valor_frete`, `proporcao_frete_valor` | Frete menor → maior risco (prioridade hipotética) | Olist não informa prioridade operacional |
| `prazo_prometido_dias` | Prazo prometido menor → risco maior | Testar sentido sem forçar interpretação causal |
| `nota_historica_vendedor_media` | Nota anterior menor → risco maior | É proxy de experiência, não causa provada |
| `frequencia_avaliacoes_baixas_vendedor` | Mais notas <=3 → risco maior | Histórico temporal sem leakage |
| `qtd_avaliacoes_historicas_vendedor` | Ajustar confiança estatística em notas/frequência | Não supor que mais reviews causam atraso |
| `quantidade_itens`, `quantidade_produtos`, `quantidade_categorias` | Pedidos mais complexos → risco eventualmente maior | Mesmo com seller único há múltiplos itens |
| `customer_state`, `seller_state` | Manter contexto geográfico | Não criar vieses regionais não justificados |
| `mes_aprovacao` | Fora do simulador padrão | Só é gerado na etapa ML |

### 8.2 Algoritmo sugerido

1. Seeds separadas e registradas para **CTGAN, sorteio/estratificação, simulação de rótulos e ML** (`42`, `43`, etc.), além das versões do código/bibliotecas.
2. Ajustar quantis, `log1p` e escalas de score usando **treino real filtrado**. Parametrizar coeficientes de cada fator em YAML/JSON; não escondê-los no código. Testar interações não lineares se desejado, sem extrapolar além do suporte plausível.
3. Calcular `score_risco` por composição ponderada com direções explícitas. Para `p_atraso`, usar `sigmoid(intercepto + intensidade * score_risco)`; calibrar o intercepto para média de probabilidades próxima à **taxa-alvo de 1/6 = 16,67% entre os SINTÉTICOS**, mantendo heterogeneidade por risco. O modelo real continua recebendo rótulo real.
4. Amostrar Bernoulli com `seed` (taxa aproximada) ou selecionar exatamente `round(N/6)` positivos por sorteio ponderado sem reposição se o usuário exigir contagem exata. Configurar os modos explicitamente e registrar o resultado. A expressão anterior “um atraso para cada seis pedidos existentes” foi esclarecida na skill anterior como taxa padrão entre pedidos **sintéticos**, não como 1 novo atraso por seis pedidos reais; se necessário tornar isso parâmetro.
5. Para viés **forte**, oferecer parâmetro `scenario_strength` e demonstrar por decis de distância, peso, frete, nota e risco calculado. O contraste de probabilidades pode aumentar mantendo taxa média 1/6. Não forçar anomalias absurdas nas características só para tornar atraso fácil de prever.
6. Opcional gerar mais candidatos CTGAN que o necessário e escolher combinações de risco plausíveis, preservando distribuição de pedidos simples e registrando seleção; comparar com cenário sem seleção.
7. Armazenar `p_atraso_simulada`, score, seed, cenário, coeficientes, taxa atingida e cenários **em arquivo de relatório/manifesto SEPARADO**, não entre as 23 colunas de C nem nas 18 features de ML.
8. Treinar no mínimo `baseline_real` (somente treino real) e `real_mais_ctgan_simulado` (treino real + sintético), variar proporção de sintéticos e pesos, sem balancear artificialmente validação/teste. Opcional `somente_ctgan_simulado` e comparação CTGAN que aprendeu o rótulo real em experimento distinto.

**Importante:** a simulação deliberada pode melhorar classificação dos rótulos sintéticos e **piorar** predição de atraso real. Relatar esse desvio se ocorrer; não usar o teste real para ajustar hipóteses/limiar repetidamente.

## 9. Treino e avaliação de ML — procedimento reprodutível

1. Preservar split temporal original se válido (possível 70/15/15, verificar) **antes** de ajustar imputadores, encoders, normalização, CTGAN, escolha de percentis ou hiperparâmetros. Filtrar 1 seller sem misturar conjuntos; o histórico real de reviews só pode usar eventos anteriores à observação.
2. Criar D com 18 features, com `mes_aprovacao` extraído de data no pré-processamento. `ML_METADATA`, `ML_TARGET` e colunas auxiliares de auditoria não podem entrar em X.
3. `OneHotEncoder(handle_unknown='ignore')` para `customer_state`, `seller_state`, `categoria_principal` se modelo requerer; imputação adequada para números/categorias; scaler quando necessário (RN, regressão logística etc.); ajustar exclusivamente no treino permitido, sem `fit` em val/teste.
4. Reusar os modelos presentes se coerentes (RF, HistGradientBoosting, redes neurais; GMM somente se papel/modelagem forem bem definidos). Não impor TensorFlow a ambiente incompatível. Baseline apenas reais é obrigatório.
5. Escolher hiperparâmetros, peso de sintéticos e limiar com **validação real**; uma comparação final no **mesmo teste real preservado**. Não “corrigir” desbalanceamento de teste com undersampling 1:1 e não contaminar dados reais com rótulos simulados.
6. Medir precision/recall/F1 da classe atrasada, PR-AUC (`average_precision_score`), ROC-AUC quando aplicável, matriz de confusão, suporte/prevalência, eventualmente Brier/curva de calibração e métricas por faixa de risco. Acurácia não basta em dataset desbalanceado.
7. Salvar pipelines de predição, transformadores, lista exata de features/ordem, seeds, versões, métricas de validação e teste. Comparar `baseline_real`, `real_mais_ctgan_simulado` e ablações em tabela. Se não melhorar no real, relatar explicitamente.
8. Manter estratégia de inferência: dado um pedido com seller único e data de aprovação, construir histórico com reviews disponíveis até a data; extrair mês; obter exatamente 18 features. Não exigir dados de entrega realizada nem review daquele pedido.

## 10. Organização sugerida de projeto (adaptar ao repositório real)

**Não criar uma segunda árvore paralela se `src` já tiver funções aproveitáveis.** Estes nomes são uma sugestão de separação de responsabilidades para o Codex analisar e aplicar incrementalmente:

```text
<raiz>/
├── src/
│   ├── data/
│   │   ├── load_olist.py             # localizar fontes e usar loaders existentes
│   │   ├── build_orders.py           # reaproveitar gerador de pedidos_ml
│   │   ├── filter_single_seller.py   # agrupar order_items, mapear seller_id, filtrar 1 seller
│   │   ├── validate_orders.py        # joins, duplicados, datas, labels e contratos
│   │   └── temporal_split.py         # divisão real coerente
│   ├── features/
│   │   ├── seller_geography.py        # seller_state e distância singular
│   │   ├── seller_history.py          # reviews do único seller, temporal/as-of
│   │   ├── enrich_orders.py          # contrato A de 23 colunas
│   │   └── derived_features.py       # razões; mês somente no preparo ML
│   ├── synthetic/
│   │   ├── train_ctgan.py            # fit em 15 colunas do treino real
│   │   ├── generate_orders.py        # gerar candidatos e IDs sintéticos
│   │   ├── validate_synthetic.py     # consistência por pedido/único seller
│   │   └── simulate_delays.py        # regras de vieses, seeds, taxa-alvo 1/6
│   ├── ml/
│   │   ├── build_ml_dataset.py       # contrato D, 18 features + metadados + alvo
│   │   ├── preprocess.py             # pipelines sem vazamento
│   │   ├── train.py                  # baseline x CTGAN sintético
│   │   └── evaluate.py               # métricas em validação/teste reais
│   ├── eda/
│   │   └── simple_eda.py             # executar posteriormente, read-only
│   ├── contracts/
│   │   └── columns.py               # CLEAN_COLUMNS, CTGAN_FEATURES, ML_FEATURES
│   └── pipeline/
│       └── run.py                   # CLI por step, ou integrar CLI atual
├── config/
│   └── experimentos.yaml            # seeds, caminhos reais e coeficientes hipotéticos
├── artifacts/
│   ├── staging/                    # intermediários; dados brutos originais preservados
│   ├── datasets/                   # bases A/B/C/D versionadas
│   ├── ctgan/                      # modelo, transformações, manifests
│   ├── models/                     # ML e preprocessadores
│   ├── reports/                    # qualidade, filtro, métricas, cenários
│   └── eda/                        # resultados posteriores
├── tests/
│   ├── test_filter_single_seller.py
│   ├── test_seller_join_and_distance.py
│   ├── test_seller_history_asof.py
│   ├── test_dataset_contracts.py
│   ├── test_label_definition.py
│   ├── test_ctgan_schema.py
│   ├── test_synthetic_seller_ids.py
│   ├── test_synthetic_constraints.py
│   ├── test_simulator_bias.py
│   └── test_no_leakage.py
└── README.md
```

Preservar scripts numerados, notebooks, entradas `joblib` e convenções existentes; preferir wrappers finos que chamam funções compartilhadas. Usar paths relativos a raiz/config, não caminhos absolutos da máquina. Criar diretórios de artefatos ao executar. Evitar versionar grandes CSVs gerados/arquivos privados. Se houver Docker/Windows/Jupyter, documentar comandos adequados ao ambiente sem quebrar os existentes.

### 10.1 Execução por etapa — nomes exemplificativos, adaptar

```bash
python -m src.pipeline.run --config config/experimentos.yaml --step audit
python -m src.pipeline.run --config config/experimentos.yaml --step clean-single-seller
python -m src.pipeline.run --config config/experimentos.yaml --step enrich
python -m src.pipeline.run --config config/experimentos.yaml --step ctgan-train
python -m src.pipeline.run --config config/experimentos.yaml --step ctgan-generate
python -m src.pipeline.run --config config/experimentos.yaml --step simulate
python -m src.pipeline.run --config config/experimentos.yaml --step ml-prepare
python -m src.pipeline.run --config config/experimentos.yaml --step ml-train
python -m src.pipeline.run --config config/experimentos.yaml --step evaluate
python -m src.pipeline.run --config config/experimentos.yaml --step eda  # depois
```

### 10.2 Configuração ilustrativa (não afirmar que estes coeficientes são estimativas reais)

```yaml
seed: 42
paths:
  raw_dir: "<DESCOBRIR_NO_REPOSITORIO>"
  pedidos_ml: "<DESCOBRIR_NO_REPOSITORIO>"
  artifacts_dir: artifacts
filter:
  distinct_sellers_required: 1
  preserve_multi_item_single_seller: true
contracts:
  clean_columns: 23
  ctgan_features: 15
  ml_features: 18
  ml_dataset_columns: 23
ctgan:
  epochs: 300
  batch_size: 500
  num_samples: 10000
  seed: 42
  preserve_simple_order_distribution: true
  include_target: false
synthetic:
  reject_invalid: true
  max_resample_attempts: 10
  seller_id_policy: pseudonymous_profile_from_train
  date_policy: sample_from_real_train
simulation:
  enabled: true
  seed: 43
  target_delay_rate: 0.1666666667
  exact_count: false
  scenario_strength: 1.0
  coefficients:  # hipóteses didáticas; devem ser configuráveis
    distance: 0.8
    weight: 0.3
    volume: 0.3
    price: 0.25
    freight: -0.35
    freight_ratio: -0.25
    promised_days: -0.3
    seller_rating: -0.5
    seller_low_review_frequency: 0.55
    order_complexity: 0.15
  category_adjustments: {}
ml:
  experiments: [baseline_real, real_mais_ctgan_simulado]
  synthetic_to_real_ratio: 1.0
  tune_on: validacao_real
  final_evaluation: teste_real
  primary_metric: average_precision
```

## 11. Testes obrigatórios e critérios de aceitação

- **Filtro seller único**: linhas com 0 ou >=2 `seller_id` distintos excluídas; linhas com múltiplos itens do mesmo seller mantidas; nenhum `order_id` duplicado; vendedor válido e não nulo em todos os reais. Registrar proporção de multi-seller e efeito sobre atraso.
- **Nomes singulares**: `seller_state`, `distancia_vendedor_cliente_km`, `nota_historica_vendedor_media`, `qtd_avaliacoes_historicas_vendedor`, `frequencia_avaliacoes_baixas_vendedor`; nenhum nome plural legado nas matrizes/contratos. `seller_id` presente apenas nos metadados de A/C/D.
- **Contratos exatos e ordem**: A=23, B=15, C=23, D=23; `len(ML_FEATURES)=18`; X nunca contém IDs, origem, split, timestamp, alvo nem probabilidade simulada; D não contém `order_approved_at` e A/B/C não contêm `mes_aprovacao`.
- **Exclusões**: nenhuma coluna `itens_sem_*`, `vendedores_sem_*`, `faltante_*`, `faltantes_*`, `missing_*`, valores/formas de pagamento, `quantidade_vendedores`, `quantidade_ufs_origem`, distância plural, transportadora fictícia, hora/tempo/dia semana de aprovação, `rotulo_*` ou `experimento_id` nos contratos finais.
- **Históricos**: as-of real `< timestamp aprovação`; reviews do próprio pedido não contaminam; nota 3 conta em `<=3`; duplicata por item de mesmo seller não infla; 0 reviews produz 0 e nota/frequência indisponíveis, sem falsa avaliação; sem seller de teste contaminando histórico passado.
- **Geo**: um seller por pedido, UF obtida de sellers/fonte validada; distância singular consistente, sem duplicação ou média de vendedores inexistentes.
- **CTGAN**: recebe **somente** 15 colunas de TREINO REAL filtrado e enriquecido, salva metadados e pesos; dataset sintético preserva predominância de pedido de um item observada (sem supor percentuais), restrições e valores plausíveis.
- **Sellers sintéticos**: IDs no namespace sintético, não colidem com reais; mesmos IDs reaproveitados apenas se perfil/UF/histórico consistentes; ID jamais é feature; origem marcada como artificial.
- **Viés**: mesma entrada e seed geram mesmas probabilidades e rótulos quando tecnicamente determinístico; mais distância maior risco condicional, menor frete maior risco condicional no cenário escolhido, e assim por diante; taxa 1/6 é medida e reportada no sintético, não imposta ao real.
- **ML**: 18 features em ordem, validação e teste **só reais** com prevalência natural; transformadores ajustados no treino; comparação com baseline sem CTGAN; métricas da classe atrasada e arquivo do experimento.
- **EDA**: comando ou notebook simples disponibilizado para execução posterior, **sem alterar datasets**.

## 12. Entregáveis finais ao usuário (Codex)

1. Mapa resumido da estrutura original e do fluxo que gerava `pedidos_ml`, com decisões de **preservar/alterar** e diff de mudanças.
2. Relatório `filtro_um_vendedor.md` ou equivalente: proporção real por quantidade de sellers, exclusões, `order_id` duplicados, alterações de prevalência e partições.
3. Código integrado e testado para estágios 01–08; comandos executáveis de cada etapa e README atualizado; **não declarar execução se CSVs não estiverem disponíveis**.
4. Os quatro esquemas exatos e documentação das listas (A=23 / B=15 / C=23 / D=23), tipos, origem e exclusões; contratos de treino e inferência.
5. Relatórios de histórico as-of, tratamento de ausências, distribuição dos pedidos simples e qualidade real versus sintético; artefatos técnicos separados dos datasets finais.
6. Modelo CTGAN treinável/reprodutível e gerador de pedidos sintéticos com perfis coerentes, seller IDs sintéticos e simulador de rótulos por seed com cenários auditáveis.
7. Baseline ML real e comparação com ML real+sintético em **validação/teste reais**, com métricas apropriadas para classe rara e ressalvas de causalidade/shift.
8. Estrutura para EDA simples **posterior** sem alterar pipeline já executado.

Se faltarem CSVs (especialmente `order_items` com `seller_id` ou `order_reviews` com timestamps), não inventar vendedores, avaliações, notas ou distâncias. Executar o que for possível com arquivos presentes e **relatar bloqueios explicitamente**. Preservar a parte funcional do código, mesmo quando etapas novas não puderem rodar.

## 13. Instrução operacional final ao Codex

> Você recebeu somente esta skill. Leia-a por completo, depois audite o repositório real. **Não refaça o projeto do zero.** Reaproveite a geração/tratamento existentes de `pedidos_ml`, mas volte aos itens originais para filtrar **apenas pedidos com exatamente um `seller_id`**. Preserve pedidos com vários itens do mesmo seller. Agregue corretamente `seller_id` e `seller_state`, calcule **uma distância** `distancia_vendedor_cliente_km` e **três históricos individuais** temporais sem vazamento. Remova dos datasets finais colunas irrelevantes, de falta/pagamento, de composição logística inexistente, `quantidade_vendedores`, `quantidade_ufs_origem` e nomes/dimensões plurais de vendedores. Gere **A=23 colunas**, treine CTGAN com **B=15**, gere sintéticos **C=23** com seller IDs explicitamente sintéticos e simule rótulos de atraso fortemente condicionados a distância, peso, volume, categoria, valor, frete, prazo e avaliações anteriores, tudo configurável e reprodutível. Extraia `mes_aprovacao` **somente** na preparação do dataset **D=23**, no qual ML usa **18 features** e `seller_id` fica **somente como metadado**. Não modifique rótulos reais. Compare baseline e ML aumentado em validação/teste reais; organize src/módulos/testes sem quebrar o código existente, deixe a EDA simples para depois e documente o resultado sem inventar execução nem causalidade.

## 14. Referências técnicas para conferir, não para sobrepor ao repositório

- Referência pública do dataset: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
- CTGAN (versões e interface variam): <https://github.com/sdv-dev/CTGAN>
- As colunas `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date` e `review_answer_timestamp` devem ser conferidas diretamente nas fontes e no código já existente.
