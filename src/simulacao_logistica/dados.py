"""Fonte SQL somente leitura + atributos disponíveis na aprovação."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from ..experimento_ctgan import consultar_base
from ..preparar_dados import RAIZ, PASTA_ORIGINAIS, ler, coordenadas_por_cep, distancia_km
from ..testar_historicos_vendedores import acumulados_anteriores

CATEGORICAS = ['customer_state', 'categoria_principal', 'tipo_pagamento_principal', 'transportadora']
NUMERICAS = [
    'distancia_vendedor_cliente_km', 'latitude_cliente', 'longitude_cliente',
    'quantidade_itens', 'quantidade_produtos', 'quantidade_categorias',
    'valor_itens', 'valor_frete', 'valor_pago', 'peso_total_g', 'peso_max_item_g',
    'volume_total_cm3', 'altura_max_item_cm', 'preco_medio_item', 'preco_max_item',
    'frete_sobre_valor_itens', 'frete_por_kg', 'frete_relativo',
    'parcelas_maximas', 'quantidade_pagamentos', 'quantidade_formas_pagamento',
    'prazo_prometido_dias', 'tempo_aprovacao_horas', 'dia_semana_aprovacao',
    'mes_aprovacao', 'hora_aprovacao', 'itens_sem_peso', 'itens_sem_dimensoes',
    'localizacao_ausente', 'nota_historica_vendedor', 'qtd_avaliacoes_vendedor',
    'nota_historica_transportadora', 'qtd_avaliacoes_transportadora',
]
ATRIBUTOS = NUMERICAS + CATEGORICAS
ARTIFICIAIS = ['transportadora', 'nota_historica_transportadora', 'qtd_avaliacoes_transportadora']
PROIBIDAS = {'order_id','seller_id','atrasou','atrasou_observado','atrasou_simulado',
            'particao','probabilidade_regra','faixa_risco_regra','origem_dado','seed'}


def preprocessador(colunas):
    assert not PROIBIDAS.intersection(colunas), 'Alvo ou auditoria nas entradas.'
    nums = [c for c in colunas if c in NUMERICAS]
    cats = [c for c in colunas if c in CATEGORICAS]
    if len(nums)+len(cats) != len(colunas):
        raise ValueError('Atributo fora da lista autorizada.')
    return ColumnTransformer([
        ('numericas', Pipeline([('imputacao', SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)), ('escala', StandardScaler())]), nums),
        ('categorias', Pipeline([('imputacao', SimpleImputer(strategy='constant', fill_value='AUSENTE',keep_empty_features=True)), ('onehot', OneHotEncoder(handle_unknown='ignore',min_frequency=25,sparse_output=False,dtype=np.float32))]), cats)
    ], remainder='drop')


def historico_notas(base, eventos, entidade='seller_id'):
    """Somente avaliações estritamente anteriores, uma observação por pedido."""
    q = base[['order_id','order_approved_at',entidade]].rename(columns={entidade:'seller_id'})
    e = eventos.rename(columns={entidade:'seller_id'}).copy()
    e['contagem'] = 1
    soma, ultima = acumulados_anteriores(e, q, 'disponivel_em', ['nota','contagem'])
    # Média suavizada com duas avaliações neutras, sem consultar o futuro.
    media = (soma.nota + 6) / (soma.contagem + 2)
    assert (ultima.isna() | ultima.lt(q.order_approved_at)).all()
    return media, soma.contagem, ultima


def preparar_base():
    base = consultar_base()  # Consulta real; falha explicitamente se banco indisponível.
    bruto = pd.read_csv(RAIZ/'Dados/pedidos_consolidados_teste.csv', usecols=['order_id','order_delivered_customer_date','order_estimated_delivery_date'])
    conferido = base[['order_id','atrasou']].merge(bruto,on='order_id',validate='one_to_one')
    esperado = pd.to_datetime(conferido.order_delivered_customer_date).dt.normalize().gt(pd.to_datetime(conferido.order_estimated_delivery_date).dt.normalize()).astype(int)
    if not esperado.eq(conferido.atrasou).all():
        raise ValueError('O alvo SQL discorda das datas observadas; não gerar sintéticos.')
    itens = ler('olist_order_items_dataset.csv',PASTA_ORIGINAIS)
    pares = itens[['order_id','seller_id']].drop_duplicates()
    contagens = pares.groupby('order_id').size()
    unicos = pares.loc[pares.order_id.map(contagens).eq(1)]
    n_sql = len(base)
    base = base.merge(unicos,on='order_id',how='inner',validate='one_to_one')
    base = base.rename(columns={'atrasou':'atrasou_observado'})
    produtos = ler('olist_products_dataset.csv',PASTA_ORIGINAIS)
    detalhes = itens.merge(produtos,on='product_id',validate='many_to_one')
    for c in ['product_weight_g','product_height_cm']:
        detalhes[c] = detalhes[c].where(detalhes[c].gt(0))
    extra = detalhes.groupby('order_id').agg(peso_max_item_g=('product_weight_g','max'), altura_max_item_cm=('product_height_cm','max'), preco_max_item=('price','max'))
    base = base.merge(extra,on='order_id',validate='one_to_one')
    geo = ler('olist_geolocation_dataset.csv',PASTA_ORIGINAIS)
    validas = geo.geolocation_lat.between(-34,6)&geo.geolocation_lng.between(-74,-28)
    coords = coordenadas_por_cep(geo.loc[validas])
    clientes = ler('olist_customers_dataset.csv',PASTA_ORIGINAIS)
    pedidos = ler('olist_orders_dataset.csv',PASTA_ORIGINAIS)
    destinos = pedidos[['order_id','customer_id']].merge(clientes[['customer_id','customer_zip_code_prefix']],on='customer_id',validate='many_to_one')
    destinos['customer_zip_code_prefix'] = destinos.customer_zip_code_prefix.str.zfill(5)
    destinos = destinos.merge(coords,left_on='customer_zip_code_prefix',right_on='geolocation_zip_code_prefix',how='left',validate='many_to_one')
    base = base.merge(destinos[['order_id','latitude','longitude']].rename(columns={'latitude':'latitude_cliente','longitude':'longitude_cliente'}),on='order_id',validate='one_to_one')
    vendedores = ler('olist_sellers_dataset.csv',PASTA_ORIGINAIS)
    vendedores['seller_zip_code_prefix'] = vendedores.seller_zip_code_prefix.str.zfill(5)
    vendedores = vendedores.merge(coords,left_on='seller_zip_code_prefix',right_on='geolocation_zip_code_prefix',how='left',validate='many_to_one')
    base = base.merge(vendedores[['seller_id','latitude','longitude']],on='seller_id',how='left',validate='many_to_one')
    base['distancia_vendedor_cliente_km'] = distancia_km(base.latitude_cliente,base.longitude_cliente,base.latitude,base.longitude)
    base['localizacao_ausente'] = base[['latitude_cliente','longitude_cliente','latitude','longitude']].isna().any(axis=1).astype(int)
    base = base.drop(columns=['latitude','longitude'])
    base['preco_medio_item'] = base.valor_itens/base.quantidade_itens
    base['frete_sobre_valor_itens'] = base.valor_frete/base.valor_itens.replace(0,np.nan)
    base['frete_por_kg'] = base.valor_frete/(base.peso_total_g/1000).replace(0,np.nan)
    avaliacoes = ler('olist_order_reviews_dataset.csv',PASTA_ORIGINAIS)
    eventos = avaliacoes[['order_id','review_score','review_answer_timestamp']].merge(unicos,on='order_id',validate='many_to_one')
    eventos = eventos.merge(pedidos[['order_id','order_approved_at']],on='order_id',validate='many_to_one')
    eventos['disponivel_em'] = pd.to_datetime(eventos.review_answer_timestamp,errors='coerce')
    anterior = eventos.disponivel_em.le(pd.to_datetime(eventos.order_approved_at,errors='coerce'))
    eventos = eventos.loc[~anterior & eventos.disponivel_em.notna() & eventos.review_score.between(1,5)]
    eventos = eventos.sort_values(['disponivel_em','order_id']).drop_duplicates('order_id').rename(columns={'review_score':'nota'})
    base = base.sort_values(['order_approved_at','order_id']).reset_index(drop=True)
    base['nota_historica_vendedor'],base['qtd_avaliacoes_vendedor'],base['ultima_avaliacao_vendedor'] = historico_notas(base,eventos)
    base['origem_dado'] = 'atributos_olist'
    # Metadados e alvos permanecem no CSV; o classificador recebe só ATRIBUTOS.
    auditoria = {'pedidos_sql':n_sql,'pedidos_um_vendedor':len(base),'excluidos_multiplos':n_sql-len(base),
                 'avaliacoes_antes_ou_na_aprovacao_excluidas':int(anterior.sum()),
                 'coordenadas_originais_rejeitadas':int((~validas).sum()),
                 'fonte':'PostgreSQL public.vw_pedidos_inferencia + CSVs originais Olist',
                 'hash_base':hashlib.sha256(base.to_csv(index=False).encode()).hexdigest()}
    return base,auditoria
