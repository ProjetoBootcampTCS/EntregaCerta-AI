# Conferir colunas — Olist / 1 vendedor por pedido / CTGAN / ML

Este arquivo é um **resumo de revisão**. A especificação integral e operacional está em `SKILL.md`, que é autossuficiente e deve ser fornecido ao Codex. **Filtrar `nunique(seller_id)==1` usando `order_items`**, mantendo pedidos com múltiplos itens do mesmo seller. Verificar no dataset real a afirmação de que pedidos com múltiplos vendedores são menos de 3%.

## A. Dataset real LIMPO/ENRIQUECIDO — 23 colunas exatas

| # | Coluna | Categoria | CTGAN aprende? | Entra no X do ML? |
|---:|---|---|---|---|
| 1 | `order_id` | Identificador pedido | Não | Não |
| 2 | `seller_id` | Identificador vendedor | Não | Não |
| 3 | `particao` | Controle | Não | Não |
| 4 | `order_approved_at` | Data de referência | Não | Não diretamente |
| 5 | `customer_state` | Geografia | Sim | Sim |
| 6 | `seller_state` | Geografia; antes `uf_origem` | Sim | Sim |
| 7 | `categoria_principal` | Produtos | Sim | Sim |
| 8 | `quantidade_itens` | Produtos | Sim | Sim |
| 9 | `quantidade_produtos` | Produtos | Sim | Sim |
| 10 | `quantidade_categorias` | Produtos | Sim | Sim |
| 11 | `valor_itens` | Valor | Sim | Sim |
| 12 | `valor_frete` | Frete | Sim | Sim |
| 13 | `peso_total_g` | Peso | Sim | Sim |
| 14 | `volume_total_cm3` | Volume | Sim | Sim |
| 15 | `distancia_vendedor_cliente_km` | Uma distância, vendedor único | Sim | Sim |
| 16 | `prazo_prometido_dias` | Prazo | Sim | Sim |
| 17 | `nota_historica_vendedor_media` | Histórico as-of | Sim | Sim |
| 18 | `qtd_avaliacoes_historicas_vendedor` | Histórico as-of | Sim | Sim |
| 19 | `frequencia_avaliacoes_baixas_vendedor` | Histórico as-of (nota <=3) | Sim | Sim |
| 20 | `preco_medio_item` | Fórmula derivada | Não | Sim |
| 21 | `proporcao_frete_valor` | Fórmula derivada | Não | Sim |
| 22 | `atrasou` | Alvo real | Não | É y, não X |
| 23 | `origem_dado` | Controle | Não | Não |

**5 metadados + 17 atributos + 1 alvo = 23.** Em sintéticos o contrato **C é o mesmo** (23), com `order_id`, `seller_id` no namespace sintético, `origem_dado='sintetico_ctgan'` e alvo rotulado pelo simulador. `mes_aprovacao` não aparece em A/B/C.

## B. Entrada CTGAN — 15 colunas exatas, somente treino real

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
```

Sem `seller_id`, `order_id`, `particao`, `order_approved_at`, `mes_aprovacao`, `origem_dado`, `atrasou`, `preco_medio_item` ou `proporcao_frete_valor`. As razões serão recalculadas matematicamente. A CTGAN não aprende identidade de vendedor.

## D. Dataset FILTRADO PARA ML — 23 colunas, 18 features

```python
ML_FEATURES = [
    "customer_state",
    "seller_state",
    "distancia_vendedor_cliente_km",
    "categoria_principal",
    "quantidade_itens",
    "quantidade_produtos",
    "quantidade_categorias",
    "peso_total_g",
    "volume_total_cm3",
    "nota_historica_vendedor_media",
    "qtd_avaliacoes_historicas_vendedor",
    "frequencia_avaliacoes_baixas_vendedor",
    "valor_itens",
    "preco_medio_item",
    "valor_frete",
    "proporcao_frete_valor",
    "prazo_prometido_dias",
    "mes_aprovacao",
]
ML_TARGET = "atrasou"
ML_METADATA = ["order_id", "seller_id", "particao", "origem_dado"]
ML_DATASET_COLUMNS = ML_METADATA + ML_FEATURES + [ML_TARGET]
```

**18 features + `atrasou` + 4 metadados = 23.** `mes_aprovacao` será calculado de `order_approved_at` somente no preparo para ML; o timestamp sai de D. `seller_id` fica no arquivo para rastreio, mas NÃO em X.

## Remover das 37 colunas antigas — 21

```text
quantidade_vendedores
quantidade_ufs_origem
distancia_media_vendedores_km
distancia_max_vendedores_km
itens_sem_peso
itens_sem_dimensoes
itens_sem_categoria
vendedores_sem_distancia
vendedores_sem_uf
valor_pago
quantidade_pagamentos
quantidade_formas_pagamento
parcelas_maximas
tipo_pagamento_principal
tempo_aprovacao_horas
dia_semana_aprovacao
mes_aprovacao
hora_aprovacao
rotulo_disponivel_em
rotulo_observado
experimento_id
```

**Renomear:** `uf_origem` → `seller_state` (validar em tabela `sellers`).

**Adicionar ao agregado:** `seller_id`, `distancia_vendedor_cliente_km`, `nota_historica_vendedor_media`, `qtd_avaliacoes_historicas_vendedor`, `frequencia_avaliacoes_baixas_vendedor`, `preco_medio_item`, `proporcao_frete_valor`.

Conferência: **37 − 21 + 7 = 23**, com um nome antigo substituído sem mudar a contagem. Esses campos podem permanecer nos CSVs brutos/staging para auditoria; são excluídos dos contratos finais. Qualquer coluna `faltante_*`, `faltantes_*`, `itens_sem_*`, `vendedores_sem_*`, `missing_*`, `sem_*` referente a ausência e transportadora artificial também fica fora.

## Fluxo obrigatório

`Olist bruto → auditoria/rotinas atuais → filtro exatamente 1 seller + split temporal → engenharia de atributos históricos e geográficos → A (23) → CTGAN.fit(B=15, treino real) → gerar e validar pedidos → atribuir seller IDs sintéticos coerentes → simular atraso probabilístico com seed e hipóteses logísticas (1/6 em sintéticos) → C (23) → calcular mes_aprovacao só no ML → D (23, X=18) → baseline real versus real+sintético → validação e teste só reais → EDA simples posterior`.

**Atraso real:** `order_delivered_customer_date > order_estimated_delivery_date` em pedidos efetivamente entregues com datas válidas, após conferir código existente. `order_delivered_carrier_date` não representa chegada ao consumidor.

**Histórico:** um seller por pedido; reviews anteriores a `order_approved_at`; nota média, total de reviews e fração `review_score<=3`. Nunca utilizar review do próprio pedido nem reviews futuras.
