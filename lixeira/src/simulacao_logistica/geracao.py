"""CTGAN aprende atributos de ambas as classes, só do treino; alvos vêm do simulador."""
import os
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from .dados import ATRIBUTOS, NUMERICAS, CATEGORICAS

DERIVADAS=['frete_relativo','frete_sobre_valor_itens','frete_por_kg','preco_medio_item','valor_pago','localizacao_ausente']
ENTRADAS=[c for c in ATRIBUTOS if c not in DERIVADAS]
CALENDARIO=['dia_semana_aprovacao','mes_aprovacao','hora_aprovacao']
CONTAGENS=[c for c in NUMERICAS if c.startswith(('quantidade_','qtd_','itens_sem_'))]+['parcelas_maximas']


def validar_geracao(config):
    if not 1 <= config['epocas'] <= 2000:
        raise ValueError('Épocas devem estar entre 1 e 2000.')
    if config['batch_size']%10 or config['batch_size']<10:
        raise ValueError('Batch deve ser positivo e múltiplo de 10 (pac).')
    limite=config['limite_por_particao']
    if not isinstance(limite,int) or not 0<=limite<=30000:
        raise ValueError('O limite por partição pode ser de até 30 mil.')
    for parte in ['treino','validacao','teste']:
        if type(config[parte]) is not int or not 0<=config[parte]<=limite:
            raise ValueError(f'Quantidade inválida em {parte}: use 0 a {limite}.')


def ajustar_gerador(treino, config):
    validar_geracao(config)
    if not treino.particao.eq('treino').all() or not treino.origem_dado.eq('atributos_olist').all():
        raise ValueError('CTGAN só pode aprender com atributos reais do treino.')
    import torch
    from ctgan import CTGAN
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    torch.manual_seed(config['seed_ctgan'])
    tabela=treino[ENTRADAS].copy().reset_index(drop=True)
    discretas=CATEGORICAS+CALENDARIO
    continuas=[c for c in ENTRADAS if c not in discretas]
    flags={}
    medianas={}
    for c in continuas:
        if tabela[c].isna().any():
            flags[c]='ausente__'+c
            tabela[flags[c]]=tabela[c].isna().astype(int).astype(str)
            discretas.append(flags[c])
        medianas[c]=float(tabela[c].median()) if tabela[c].notna().any() else 0.
        tabela[c]=tabela[c].fillna(medianas[c])
        if c not in ['latitude_cliente','longitude_cliente']:
            tabela[c]=np.log1p(tabela[c].clip(lower=0))
    for c in discretas:
        tabela[c]=tabela[c].fillna('AUSENTE').astype(str)
    constantes={c:tabela[c].iloc[0] for c in tabela if tabela[c].nunique()==1}
    tabela=tabela.drop(columns=list(constantes))
    modelo=CTGAN(epochs=config['epocas'],batch_size=config['batch_size'],pac=10,
                 generator_dim=(128,128),discriminator_dim=(128,128),embedding_dim=64,
                 verbose=True,enable_gpu=False)
    modelo.set_random_state(config['seed_ctgan'])
    modelo.fit(tabela,discrete_columns=[c for c in discretas if c in tabela])
    return {'modelo':modelo,'constantes':constantes,'continuas':continuas,'flags':flags,
            'medianas':medianas,'treino':treino[ATRIBUTOS].copy(),'config':config,
            'ids_ajuste':treino.order_id.tolist()}


def corrigir_gerados(b, treino):
    """Restrições físicas e contábeis explícitas, sem usar validação/teste."""
    b=b.copy()
    for c in CONTAGENS:
        b[c]=pd.to_numeric(b[c],errors='coerce').fillna(0).round().clip(lower=0)
    for c in ['quantidade_itens','quantidade_produtos','quantidade_pagamentos','quantidade_formas_pagamento']:
        b[c]=b[c].clip(lower=1)
    b['quantidade_produtos']=np.minimum(b.quantidade_produtos,b.quantidade_itens)
    b['quantidade_categorias']=np.minimum(b.quantidade_categorias,b.quantidade_produtos)
    b['quantidade_formas_pagamento']=np.minimum(b.quantidade_formas_pagamento,b.quantidade_pagamentos)
    for c in ['itens_sem_peso','itens_sem_dimensoes']:
        b[c]=np.minimum(b[c],b.quantidade_itens)
    b.loc[b.itens_sem_peso.gt(0),'peso_total_g']=np.nan
    b.loc[b.itens_sem_dimensoes.gt(0),'volume_total_cm3']=np.nan
    b['peso_max_item_g']=np.minimum(b.peso_max_item_g,b.peso_total_g)
    b['valor_itens']=b.valor_itens.clip(lower=.01).round(2)
    b['valor_frete']=b.valor_frete.clip(lower=0).round(2)
    b['preco_medio_item']=b.valor_itens/b.quantidade_itens
    b['preco_max_item']=b.preco_max_item.clip(lower=b.preco_medio_item,upper=b.valor_itens)
    b['valor_pago']=b.valor_itens+b.valor_frete
    b['frete_sobre_valor_itens']=b.valor_frete/b.valor_itens
    b['frete_por_kg']=b.valor_frete/(b.peso_total_g/1000).replace(0,np.nan)
    for c,lo,hi in [('dia_semana_aprovacao',0,6),('mes_aprovacao',1,12),('hora_aprovacao',0,23)]:
        b[c]=pd.to_numeric(b[c],errors='coerce').fillna(lo).round().clip(lo,hi)
    for entidade in ['vendedor','transportadora']:
        b['nota_historica_'+entidade]=b['nota_historica_'+entidade].clip(1,5)
        b.loc[b['qtd_avaliacoes_'+entidade].eq(0),'nota_historica_'+entidade]=3.
    # Aproximação do destino: encaixa lat/lon geradas em pares observados no
    # treino da mesma UF. Não representa endereço ou rota de um vendedor real.
    for uf, grupo in b.groupby('customer_state'):
        doadores=treino.loc[treino.customer_state.eq(uf),['latitude_cliente','longitude_cliente']].dropna().drop_duplicates()
        if doadores.empty:
            b.loc[grupo.index,['latitude_cliente','longitude_cliente']]=np.nan
            continue
        consultas=grupo[['latitude_cliente','longitude_cliente']]
        presentes=consultas.notna().all(axis=1)
        if presentes.any():
            nn=NearestNeighbors(n_neighbors=1).fit(doadores)
            ids=nn.kneighbors(consultas.loc[presentes],return_distance=False).ravel()
            b.loc[consultas.index[presentes],doadores.columns]=doadores.iloc[ids].to_numpy()
    b['localizacao_ausente']=b[['latitude_cliente','longitude_cliente','distancia_vendedor_cliente_km']].isna().any(axis=1).astype(int)
    return b


def gerar(pacote, quantidade, parte, semente):
    if not 0<=quantidade<=30000:
        raise ValueError('O limite deste laboratório é 30 mil por partição.')
    if quantidade==0:
        return pd.DataFrame()
    modelo=pacote['modelo']
    modelo.set_random_state(semente)
    b=modelo.sample(quantidade)
    for c,v in pacote['constantes'].items():
        b[c]=v
    treino=pacote['treino']
    for c in pacote['continuas']:
        b[c]=pd.to_numeric(b[c],errors='coerce')
        if c not in ['latitude_cliente','longitude_cliente']:
            b[c]=np.expm1(b[c].clip(-20,30))
        b[c]=b[c].clip(treino[c].min(),treino[c].max())
        if c in pacote['flags']:
            b.loc[pd.to_numeric(b[pacote['flags'][c]],errors='coerce').eq(1),c]=np.nan
    b= b[ENTRADAS].replace('AUSENTE',np.nan)
    b=corrigir_gerados(b,treino)
    b['order_id']=[f'SIM-{parte}-{semente}-{i:06d}' for i in range(quantidade)]
    b['seller_id']=pd.NA
    b['particao']=parte
    b['origem_dado']='sintetico_ctgan'
    b['atrasou_observado']=pd.NA
    b['order_approved_at']=pd.NaT
    return b
