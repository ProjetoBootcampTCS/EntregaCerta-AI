"""Previsões na aprovação, após 48h e no despacho, com validação temporal.

Executar no ambiente dos experimentos: python -m experimentos.testar_previsao_operacional
Somente dados reais; não altera banco, modelos da aplicação ou frontend.
"""
from __future__ import annotations

import json
from importlib.metadata import version

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from .comparar_recall95 import escolher_limiar_recall, medir, sha256
from src.preparar_dados import RAIZ, COLUNAS_PREVISAO, PASTA_ORIGINAIS
from .testar_historicos_vendedores import COLUNAS_HISTORICO
from src.tratar_dados_ml import criar_preprocessador, NUMERICAS

PASTA = RAIZ/'Modelos/experimento_operacional'
ANTERIOR = RAIZ/'Modelos/comparacao_recall95'
META = .90
ANTECEDENCIA_HORAS = 24
ETAPAS = ['aprovacao', 'preparacao48h', 'despacho']
ALGORITMOS = ['Logistica', 'HGB']
ORIGINAIS = COLUNAS_PREVISAO + COLUNAS_HISTORICO
OPERACIONAIS = ['dias_decorridos', 'dias_restantes', 'fracao_prazo_consumida',
    'despachado', 'dias_ate_despacho', 'dias_em_transito',
    'dias_ate_limite_postagem', 'postagem_fora_limite', 'folga_transito_historico']
# Dobras por calendário: treino, calibração do corte, avaliação futura.
DOBRAS = [
    ('2017-05-01', '2017-07-01', '2017-09-01'),
    ('2017-07-01', '2017-09-01', '2017-11-01'),
    ('2017-09-01', '2017-11-01', '2018-01-01'),
]


def dias(delta):
    return delta.dt.total_seconds()/86400


def criar_snapshot(base, etapa):
    """Estado observado naquele instante; nenhum timestamp futuro vira atributo.

    48h: consulta fixa após aprovação, antecipada se o prazo for curto.
    Despacho: no evento, ou 24h antes do fim do prazo se ainda não ocorreu.
    Pedidos já entregues não recebem alerta e continuam no denominador.
    """
    b = base.copy()
    limite = b.fim_prazo - pd.Timedelta(hours=ANTECEDENCIA_HORAS)
    despacho = b.order_delivered_carrier_date.where(
        b.order_delivered_carrier_date.ge(b.order_approved_at))
    if etapa == 'aprovacao':
        agora = b.order_approved_at.copy()
    elif etapa == 'preparacao48h':
        agora = pd.concat([b.order_approved_at + pd.Timedelta(hours=48), limite], axis=1).min(axis=1)
    elif etapa == 'despacho':
        agora = pd.concat([despacho, limite], axis=1).min(axis=1)
    else:
        raise ValueError('Etapa desconhecida.')
    b['instante'] = agora
    # Entrega só determina o estado se JÁ aconteceu no instante consultado.
    b['ja_entregue'] = b.order_delivered_customer_date.le(agora)
    b['elegivel'] = (agora.ge(b.order_approved_at) & agora.le(limite) & ~b.ja_entregue)
    conhecido = despacho.where(despacho.le(agora))
    b['dias_decorridos'] = dias(agora-b.order_approved_at)
    b['dias_restantes'] = dias(b.fim_prazo-agora)
    b['fracao_prazo_consumida'] = b.dias_decorridos/dias(b.fim_prazo-b.order_approved_at)
    b['despachado'] = conhecido.notna().astype(int)
    b['dias_ate_despacho'] = dias(conhecido-b.order_approved_at)
    b['dias_em_transito'] = dias(agora-conhecido)
    b['dias_ate_limite_postagem'] = dias(b.limite_postagem-agora)
    b['postagem_fora_limite'] = dias(conhecido-b.limite_postagem).clip(lower=0)
    historico_transito = (b.hist_entrega_dias_media-b.hist_postagem_dias_media).clip(lower=0)
    b['folga_transito_historico'] = b.dias_restantes-historico_transito
    # Ausência de entrega futura jamais permite descartar um atraso da avaliação.
    assert not (b.ja_entregue & b.atrasou.eq(1)).any()
    assert (conhecido.isna() | conhecido.le(agora)).all()
    assert b.loc[b.elegivel,'dias_restantes'].ge(ANTECEDENCIA_HORAS/24).all()
    return b


def preparar_base():
    base = joblib.load(RAIZ/'Modelos/experimento_ctgan/doses_20261111/snapshot_postgresql.joblib')
    assert base.order_id.is_unique and base.origem_dado.eq('real_olist').all()
    assert base.rotulo_observado.all()
    htreino = joblib.load(RAIZ/'Modelos/experimento_historicos/base_experimento.joblib')
    haval = pd.read_parquet(ANTERIOR/'pedidos_avaliacao.parquet')
    historicos = pd.concat([htreino.loc[htreino.particao.eq('treino')], haval],ignore_index=True)
    historicos = historicos.loc[historicos.order_id.isin(base.order_id)]
    cols = ['order_id','ultimo_evento_historico'] + COLUNAS_HISTORICO
    base = base.merge(historicos[cols],on='order_id',validate='one_to_one')
    assert len(base)==91390
    assert (base.ultimo_evento_historico.isna() |
            base.ultimo_evento_historico.lt(base.order_approved_at)).all()
    # Históricos são congelados na aprovação para isolar o efeito do evento novo.
    cols = ['order_id','order_delivered_carrier_date','order_delivered_customer_date',
            'order_estimated_delivery_date']
    pedidos = pd.read_csv(PASTA_ORIGINAIS/'olist_orders_dataset.csv',usecols=cols)
    for c in cols[1:]:
        pedidos[c] = pd.to_datetime(pedidos[c],errors='coerce')
    base = base.merge(pedidos,on='order_id',validate='one_to_one')
    assert base[cols[2:]].notna().all().all()
    alvo = base.order_delivered_customer_date.dt.normalize().gt(base.order_estimated_delivery_date.dt.normalize())
    assert alvo.astype(int).eq(base.atrasou).all()
    assert base.rotulo_disponivel_em.eq(base.order_delivered_customer_date).all()
    itens = pd.read_csv(PASTA_ORIGINAIS/'olist_order_items_dataset.csv',
                       usecols=['order_id','shipping_limit_date'],parse_dates=['shipping_limit_date'])
    limites = itens.groupby('order_id').shipping_limit_date.min().rename('limite_postagem')
    base = base.merge(limites,on='order_id',how='left',validate='one_to_one')
    base['fim_prazo'] = base.order_estimated_delivery_date.dt.normalize()+pd.Timedelta(days=1)
    base = base.sort_values(['order_approved_at','order_id']).reset_index(drop=True)
    assert base.groupby('particao').size().to_dict()=={'treino':41173,'validacao':24667,'teste':25550}
    return base


def divisao_temporal(base, inicio_calibracao, inicio_avaliacao, fim_avaliacao):
    """Expurga desfechos que ainda não eram conhecidos no início de cada fase."""
    c,e,f = map(pd.Timestamp,[inicio_calibracao,inicio_avaliacao,fim_avaliacao])
    if not c<e<f:
        raise ValueError('Fronteiras temporais fora de ordem.')
    treino = base.index[base.order_approved_at.lt(c) & base.rotulo_disponivel_em.lt(c)]
    calibracao = base.index[base.order_approved_at.ge(c) & base.order_approved_at.lt(e)
                           & base.rotulo_disponivel_em.lt(e)]
    avaliacao = base.index[base.order_approved_at.ge(e) & base.order_approved_at.lt(f)]
    return treino,calibracao,avaliacao


def treinar(snapshot, indices, etapa, algoritmo):
    g = snapshot.loc[indices]
    g = g.loc[g.elegivel]
    extras = COLUNAS_HISTORICO + ([] if etapa=='aprovacao' else OPERACIONAIS)
    colunas = COLUNAS_PREVISAO + extras
    pre = criar_preprocessador()
    pre.transformers[0] = (pre.transformers[0][0],pre.transformers[0][1],NUMERICAS+extras)
    x = pre.fit_transform(g[colunas]).astype(np.float32)
    if algoritmo=='Logistica':
        modelo = LogisticRegression(C=1,max_iter=1500,solver='liblinear',random_state=42)
    else:
        modelo = HistGradientBoostingClassifier(max_iter=200,learning_rate=.07,max_leaf_nodes=15,
            max_depth=5,min_samples_leaf=40,l2_regularization=1,early_stopping=False,random_state=42)
    modelo.fit(x,g.atrasou.to_numpy(int))
    return {'preprocessador':pre,'modelo':modelo,'colunas':colunas,'n_treino':len(g)}


def pontuar(pacote, snapshot, indices):
    g = snapshot.loc[indices]
    # -1 é sentinela operacional para não emitir alerta; não é probabilidade.
    scores = np.full(len(g),-1.,dtype=float)
    ativos = g.elegivel.to_numpy()
    if ativos.any():
        x = pacote['preprocessador'].transform(g.loc[g.elegivel,pacote['colunas']]).astype(np.float32)
        scores[ativos] = pacote['modelo'].predict_proba(x)[:,1]
    return scores


def politica(scores, chave):
    algoritmo, etapa = chave.split('/',1)
    if etapa=='combinada':
        return np.maximum(scores[f'{algoritmo}/preparacao48h'],scores[f'{algoritmo}/despacho'])
    return scores[chave]


def medir_politica(base, snapshots, indices, scores, chave, corte):
    g = base.loc[indices]
    s = politica(scores,chave)
    m = medir(g.atrasou,s,corte,meta=META)
    algoritmo,etapa = chave.split('/',1)
    etapas = ['preparacao48h','despacho'] if etapa=='combinada' else [etapa]
    instantes = []
    for e in etapas:
        q = snapshots[e].loc[indices]
        alerta = scores[f'{algoritmo}/{e}']>=corte
        assert q.loc[alerta,'elegivel'].all()
        instantes.append(q.instante.where(alerta))
    primeiro = pd.concat(instantes,axis=1).min(axis=1)
    assert int(primeiro.notna().sum())==m['revisoes']
    antecedencia = dias(g.fim_prazo-primeiro)
    acertos = primeiro.notna() & g.atrasou.eq(1)
    m.update({'antecedencia_tp_mediana_dias':float(antecedencia[acertos].median()),
        'antecedencia_tp_p10_dias':float(antecedencia[acertos].quantile(.1)),
        'antecedencia_minima_dias':float(antecedencia.min()),
        'eventos_alerta':int(sum((scores[f'{algoritmo}/{e}']>=corte).sum() for e in etapas)),
        'apenas_monitoramento_sem_score':int((s<0).sum())})
    assert m['antecedencia_minima_dias']>=1
    return m,primeiro


def avaliar_rodada(base,snapshots,treino,calibracao,avaliacao,nome,final=False):
    scores_cal = {}; scores_aval = {}; pacotes = {}; modelos = []
    chaves = [f'{a}/{e}' for a in ALGORITMOS for e in ETAPAS+['combinada']]
    for algoritmo in ALGORITMOS:
        for etapa in ETAPAS:
            chave=f'{algoritmo}/{etapa}'
            print(nome,'TREINANDO',chave,flush=True)
            pacote=treinar(snapshots[etapa],treino,etapa,algoritmo)
            pacotes[chave]=pacote
            scores_cal[chave]=pontuar(pacote,snapshots[etapa],calibracao)
            modelos.append({'rodada':nome,'modelo':chave,'n_treino':pacote['n_treino']})
    linhas=[]; cortes={}
    for chave in chaves:
        s=politica(scores_cal,chave)
        corte=escolher_limiar_recall(base.loc[calibracao,'atrasou'],s,META)
        if corte<0:
            raise ValueError('Cobertura insuficiente para a meta antes do prazo.')
        cortes[chave]=corte
        m,_=medir_politica(base,snapshots,calibracao,scores_cal,chave,corte)
        linhas.append({'rodada':nome,'particao':'calibracao','modelo':chave,**m})
    ranking=pd.DataFrame(linhas).sort_values(['revisoes','AP','modelo'],ascending=[True,False,True])
    escolhido=ranking.iloc[0].modelo
    selecao={'escolhido':escolhido,'cortes':cortes,'meta':META,
             'criterio':'Menor fila com recall >=90% na calibração; desempate AP e nome.',
             'estado':'Congelado antes das predições da avaliação desta rodada.'}
    (PASTA/f'selecao_{nome}.json').write_text(json.dumps(selecao,ensure_ascii=False,indent=2),encoding='utf-8')
    for algoritmo in ALGORITMOS:
        for etapa in ETAPAS:
            chave=f'{algoritmo}/{etapa}'
            scores_aval[chave]=pontuar(pacotes[chave],snapshots[etapa],avaliacao)
    mensal=[]; predicoes=[]
    for parte,indices,scores in [('calibracao',calibracao,scores_cal),('avaliacao',avaliacao,scores_aval)]:
        for chave in chaves:
            m,primeiro=medir_politica(base,snapshots,indices,scores,chave,cortes[chave])
            if parte=='avaliacao':
                linhas.append({'rodada':nome,'particao':parte,'modelo':chave,**m})
            if final:
                p=base.loc[indices,['order_id','particao','atrasou','order_approved_at','fim_prazo']].copy()
                p['modelo']=chave;p['score_politica']=politica(scores,chave)
                p['alerta']=p.score_politica.ge(cortes[chave]).astype(int)
                p['primeiro_alerta']=primeiro
                predicoes.append(p)
                for mes,g in p.groupby(p.order_approved_at.dt.strftime('%Y-%m')):
                    mensal.append({'modelo':chave,'particao':parte,'mes':mes,
                        **medir(g.atrasou,g.score_politica,cortes[chave],META)})
    resultado=pd.DataFrame(linhas)
    resultado['selecionado_calibracao']=resultado.modelo.eq(escolhido)
    resultado.to_csv(PASTA/f'metricas_{nome}.csv',index=False)
    pd.DataFrame(modelos).to_csv(PASTA/f'tamanhos_treino_{nome}.csv',index=False)
    if final:
        # Reproduzir o baseline real do experimento anterior antes de concluir.
        anteriores=pd.read_parquet(ANTERIOR/'scores.parquet').set_index('order_id')
        for indices,scores in [(calibracao,scores_cal),(avaliacao,scores_aval)]:
            np.testing.assert_allclose(scores['Logistica/aprovacao'],
                anteriores.loc[base.loc[indices,'order_id'],'m42'],rtol=1e-8,atol=1e-9)
        pd.concat(predicoes).to_parquet(PASTA/'previsoes.parquet',index=False)
        pd.DataFrame(mensal).to_csv(PASTA/'metricas_mensais.csv',index=False)
        joblib.dump({'pacotes':pacotes,'selecao':selecao},PASTA/'modelos.joblib',compress=3)
        relido=joblib.load(PASTA/'modelos.joblib')
        for chave,pacote in relido['pacotes'].items():
            etapa=chave.split('/')[1]
            np.testing.assert_allclose(pontuar(pacote,snapshots[etapa],avaliacao),scores_aval[chave],rtol=0,atol=0)
    print(resultado.loc[resultado.particao.eq('avaliacao'),
        ['modelo','recall','fracao_revisao','fn','antecedencia_tp_mediana_dias']].to_string(index=False),flush=True)
    print('ESCOLHIDO ANTES DA AVALIAÇÃO:',escolhido,flush=True)
    return resultado


def executar():
    PASTA.mkdir(parents=True,exist_ok=True)
    fontes=[RAIZ/'Modelos/experimento_ctgan/doses_20261111/snapshot_postgresql.joblib',
            RAIZ/'Modelos/experimento_historicos/base_experimento.joblib',
            ANTERIOR/'pedidos_avaliacao.parquet',ANTERIOR/'scores.parquet',
            PASTA_ORIGINAIS/'olist_orders_dataset.csv',PASTA_ORIGINAIS/'olist_order_items_dataset.csv',
            RAIZ/'experimentos/testar_previsao_operacional.py']
    protocolo={'meta':META,'antecedencia_minima_horas':ANTECEDENCIA_HORAS,'dobras':DOBRAS,
        'dados':'Mesmos 91390 pedidos reais da comparação anterior; nenhuma amostra sintética.',
        'hipoteses':['Promessa de entrega e shipping_limit_date conhecidos e estáveis desde a aprovação.',
            'Eventos disponibilizados sem latência; timestamp anterior à aprovação é ignorado.',
            'Históricos de vendedores mantidos no estado da aprovação.',
            'Checagem 48h inclui pedidos já despachados; no despacho há checagem de segurança a D-1.',
            'Predições são pré-intervenção; não medem atrasos evitados.',
            'Teste já consultado anteriormente: estudo retrospectivo exploratório.'],
        'versoes':{p:version(p) for p in ['numpy','pandas','scikit-learn']},
        'sha256':{str(p.relative_to(RAIZ)):sha256(p) for p in fontes}}
    (PASTA/'protocolo.json').write_text(json.dumps(protocolo,ensure_ascii=False,indent=2),encoding='utf-8')
    base=preparar_base()
    snapshots={e:criar_snapshot(base,e) for e in ETAPAS}
    auditoria=[]
    for e,b in snapshots.items():
        for parte,g in b.groupby('particao'):
            auditoria.append({'etapa':e,'particao':parte,'pedidos':len(g),'atrasos':int(g.atrasou.sum()),
                'elegiveis':int(g.elegivel.sum()),'ja_entregues':int(g.ja_entregue.sum()),
                'sem_despacho_conhecido':int(g.despachado.eq(0).sum()),
                'timestamp_despacho_invalido':int(g.order_delivered_carrier_date.lt(g.order_approved_at).sum())})
    pd.DataFrame(auditoria).to_csv(PASTA/'auditoria.csv',index=False)
    joblib.dump(snapshots,PASTA/'snapshots.joblib',compress=3)
    resultados=[]; fronteiras=[]
    desenvolvimento=base.loc[base.particao.eq('treino')]
    with threadpool_limits(limits=4):
        for i,(c,e,f) in enumerate(DOBRAS,1):
            t,ca,a=divisao_temporal(desenvolvimento,c,e,f)
            assert base.loc[t,'rotulo_disponivel_em'].lt(c).all()
            assert base.loc[ca,'rotulo_disponivel_em'].lt(e).all()
            fronteiras.append({'dobra':i,'inicio_calibracao':c,'inicio_avaliacao':e,'fim_avaliacao':f,
                'n_treino':len(t),'n_calibracao':len(ca),'n_avaliacao':len(a),
                'atrasos_avaliacao':int(base.loc[a,'atrasou'].sum())})
            resultados.append(avaliar_rodada(base,snapshots,t,ca,a,f'dobra{i}'))
        pd.DataFrame(fronteiras).to_csv(PASTA/'dobras.csv',index=False)
        pd.concat(resultados).to_csv(PASTA/'validacao_temporal.csv',index=False)
        t=base.index[base.particao.eq('treino')]
        ca=base.index[base.particao.eq('validacao')]
        a=base.index[base.particao.eq('teste')]
        assert base.loc[t,'rotulo_disponivel_em'].lt('2018-01-01').all()
        assert base.loc[ca,'rotulo_disponivel_em'].lt('2018-05-01').all()
        resultado=avaliar_rodada(base,snapshots,t,ca,a,'final',final=True)
    print('CONCLUÍDO: baseline reproduzido e modelos salvos conferidos.',flush=True)
    return resultado


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    executar()
