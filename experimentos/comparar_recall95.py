"""Compara artefatos já treinados: mínimo de revisões com recall >= 95% na validação.

Executar: .venv-ctgan/Scripts/python.exe -m experimentos.comparar_recall95
Reavaliar scores salvos: adicionar --reavaliar-recall 0.90
Não treina modelos, não escreve no banco e não altera a política da aplicação.
"""
from __future__ import annotations

import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             precision_recall_curve)
from threadpoolctl import threadpool_limits

from .experimento_ctgan import hash_base
from src.inferencia import carregar_modelos
from src.preparar_dados import COLUNAS_PREVISAO, PASTA_ORIGINAIS, RAIZ
from .testar_historicos_vendedores import criar_historicos, COLUNAS_HISTORICO

META = .95
PASTA = RAIZ / 'Modelos/comparacao_recall95'
DOSES = RAIZ / 'Modelos/experimento_ctgan/doses_20261111'
INICIAL = RAIZ / 'Modelos/experimento_ctgan/ecc4ac30a3df7383'
HISTORICOS = RAIZ / 'Modelos/experimento_historicos'


def sha256(caminho):
    h = hashlib.sha256()
    with Path(caminho).open('rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            h.update(bloco)
    return h.hexdigest()


def validar_scores(y, scores):
    y = np.asarray(y)
    s = np.asarray(scores, dtype=float)
    if y.ndim != 1 or s.ndim != 1 or len(y) != len(s) or not len(y):
        raise ValueError('Alvos e scores devem ser vetores não vazios de mesmo tamanho.')
    if not np.isin(y, [0, 1]).all() or not np.isfinite(s).all():
        raise ValueError('Alvos binários e scores finitos são obrigatórios.')
    return y.astype(int), s


def escolher_limiar_recall(y_validacao, scores_validacao, meta=META):
    """Maior score de corte que captura ceil(meta * positivos), incluindo empates.

    Só recebe validação. Entre políticas determinísticas score >= corte, esta
    encaminha o menor número de pedidos que satisfaz o recall solicitado.
    """
    y, s = validar_scores(y_validacao, scores_validacao)
    if not 0 < meta <= 1:
        raise ValueError('A meta precisa pertencer a (0, 1].')
    positivos = np.sort(s[y == 1])[::-1]
    if not len(positivos):
        raise ValueError('Não é possível ajustar recall sem atrasos observados.')
    necessarios = math.ceil(meta * len(positivos) - 1e-12)
    return float(positivos[necessarios - 1])


def medir(y, scores, limiar, meta=META):
    if not 0 < meta <= 1:
        raise ValueError('A meta precisa pertencer a (0, 1].')
    y, s = validar_scores(y, scores)
    alerta = s >= limiar
    tn, fp, fn, tp = confusion_matrix(y, alerta, labels=[0, 1]).ravel()
    n_pos = int(tp + fn)
    revisoes = int(tp + fp)
    recall = tp / n_pos if n_pos else np.nan
    # Wilson bilateral 95%: descritivo, assume observações independentes.
    z = 1.959963984540054
    if n_pos:
        centro = (recall + z*z/(2*n_pos)) / (1 + z*z/n_pos)
        margem = z * np.sqrt(recall*(1-recall)/n_pos + z*z/(4*n_pos*n_pos)) / (1+z*z/n_pos)
    else:
        centro = margem = np.nan
    return {'pedidos':len(y), 'atrasos':n_pos, 'limiar':float(limiar),
        'recall':float(recall), 'fnr':float(1-recall),
        'recall_ic95_inf':float(centro-margem), 'recall_ic95_sup':float(centro+margem),
        'revisoes':revisoes, 'fracao_revisao':revisoes/len(y),
        'dispensados':int(tn+fn), 'precision':float(tp/revisoes) if revisoes else 0.,
        'AP':float(average_precision_score(y,s)) if n_pos else np.nan,
        'f1':float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.,
        'accuracy':float((tp+tn)/len(y)), 'tn':int(tn), 'fp':int(fp),
        'fn':int(fn), 'tp':int(tp), 'atingiu_meta':bool(n_pos and recall >= meta)}


def preparar_fontes():
    base = joblib.load(DOSES/'snapshot_postgresql.joblib')
    assert base.order_id.is_unique and base.origem_dado.eq('real_olist').all()
    assert base.rotulo_observado.all() and base.atrasou.isin([0,1]).all()
    assert base.groupby('particao').size().to_dict() == {'treino':41173,'validacao':24667,'teste':25550}
    treino = base.loc[base.particao.eq('treino')]
    assert treino.order_approved_at.lt('2018-01-01').all()
    assert treino.rotulo_disponivel_em.lt('2018-01-01').all()
    observados = pd.read_csv(RAIZ/'Dados/pedidos_consolidados_teste.csv',
        usecols=['order_id','order_delivered_customer_date','order_estimated_delivery_date'])
    conferido = base[['order_id','atrasou']].merge(observados,validate='one_to_one',on='order_id')
    assert len(conferido)==len(base)
    real = pd.to_datetime(conferido.order_delivered_customer_date).dt.normalize().gt(
        pd.to_datetime(conferido.order_estimated_delivery_date).dt.normalize()).astype(int)
    assert real.eq(conferido.atrasou).all(), 'Alvo divergente das datas reais.'

    # Atributos históricos do teste não estavam salvos: calculá-los com o mesmo
    # código, sempre usando eventos estritamente anteriores à aprovação.
    consultas = base.loc[base.particao.ne('treino')].copy().reset_index(drop=True)
    pedidos = pd.read_csv(PASTA_ORIGINAIS/'olist_orders_dataset.csv')
    itens = pd.read_csv(PASTA_ORIGINAIS/'olist_order_items_dataset.csv',usecols=['order_id','seller_id'])
    historicos, _ = criar_historicos(pedidos,itens,consultas)
    consultas = consultas.merge(historicos,on='order_id',validate='one_to_one')
    assert (consultas.ultimo_evento_historico.isna() |
            consultas.ultimo_evento_historico.lt(consultas.order_approved_at)).all()
    anterior = joblib.load(HISTORICOS/'base_experimento.joblib').set_index('order_id')
    val = consultas.loc[consultas.particao.eq('validacao')]
    np.testing.assert_allclose(val[COLUNAS_HISTORICO], anterior.loc[val.order_id,COLUNAS_HISTORICO],
                               equal_nan=True,rtol=1e-10,atol=1e-10)
    consultas.to_parquet(PASTA/'pedidos_avaliacao.parquet',index=False)
    return base, consultas


def carregar_candidatos(base):
    """Adapta os formatos existentes; nenhum fit é chamado."""
    candidatos=[]
    def incluir(nome,familia,treino,fonte,preditor,**extras):
        ident=f'm{len(candidatos)+1:02d}'
        candidatos.append({'id':ident,'nome':nome,'familia':familia,'treino':treino,
            'fonte':str(fonte.relative_to(RAIZ)), 'prever':preditor, **extras})

    arq=INICIAL/'modelos_comparacao.joblib'
    inicial=joblib.load(arq)
    assert inicial['metadados']['hash_snapshot']==hash_base(base)
    for (nome,cenario),p in inicial['modelos'].items():
        def prever(tabela,p=p):
            x=inicial['preprocessador'].transform(tabela[inicial['colunas_entrada']]).astype(np.float32)
            if p['usa_gmm']:
                clusters=inicial['gmm'].predict_proba(inicial['pre_gmm'].transform(tabela[inicial['colunas_gmm']]))
                x=np.column_stack([x,clusters]).astype(np.float32)
            return p['modelo'].predict_proba(x)[:,1]
        familia='Regressão logística' if nome.startswith('Logistica') else nome
        dose=int(inicial['metadados']['quantidade']) if 'CTGAN' in cenario else 0
        incluir(f'{nome} / {cenario}',familia,cenario,arq,prever,dose=dose,semente=42,grupo='inicial')

    arq=DOSES/'comparacao.joblib'
    doses=joblib.load(arq)
    assert doses['configuracao']['hash_base']==hash_base(base)
    for chave,p in doses['modelos'].items():
        def prever(tabela,p=p):
            x=doses['preprocessador'].transform(tabela[COLUNAS_PREVISAO]).astype(np.float32)
            s=p['modelo'].predict_proba(x)[:,1]
            if tabela.particao.eq('validacao').all():
                np.testing.assert_allclose(s,p['scores_validacao'],rtol=1e-8,atol=1e-9)
            return s
        incluir(f'Logística / {chave}','Regressão logística',p['metodo'],arq,prever,
                dose=int(p['dose']),semente=int(p['semente']),grupo='doses')

    arq=HISTORICOS/'comparacao.joblib'
    hs=joblib.load(arq)
    assert hs['protocolo']['hash_snapshot']==hash_base(base)
    for chave,p in hs['modelos'].items():
        def prever(tabela,p=p):
            x=p['preprocessador'].transform(tabela[p['colunas']]).astype(np.float32)
            s=p['modelo'].predict_proba(x)[:,1]
            if tabela.particao.eq('validacao').all():
                referencia=pd.Series(p['scores_validacao'],index=p['ids_validacao']).reindex(tabela.order_id)
                assert referencia.notna().all()
                np.testing.assert_allclose(s,referencia,rtol=1e-8,atol=1e-9)
            return s
        familia='HGB' if chave.endswith('HGB') else 'Regressão logística'
        incluir(f'{familia} / {chave}',familia,'Real com históricos' if 'com_historicos' in chave else 'Real',
                arq,prever,dose=0,semente=42,grupo='historicos')

    pacote,rede=carregar_modelos()
    def prever_rede(tabela):
        x=pacote['preprocessador'].transform(tabela[pacote['colunas_entrada']]).astype(np.float32)
        with torch.no_grad():
            return torch.sigmoid(rede(torch.from_numpy(x)).squeeze(1)).numpy()
    incluir('Rede neural / artefato atual','Rede neural','Real',RAIZ/'Modelos/rede_neural.pt',prever_rede,
            dose=0,semente=int(pacote['semente']),grupo='rede')
    return candidatos


def executar():
    PASTA.mkdir(parents=True,exist_ok=True)
    print('Conferindo fontes e construindo históricos sem futuro...',flush=True)
    base,dados=preparar_fontes()
    candidatos=carregar_candidatos(base)
    catalogo=pd.DataFrame([{k:v for k,v in c.items() if k!='prever'} for c in candidatos])
    catalogo.to_csv(PASTA/'catalogo.csv',index=False)
    fontes={RAIZ/c['fonte'] for c in candidatos}
    fontes.update([DOSES/'snapshot_postgresql.joblib',RAIZ/'Modelos/preprocessador_rede.joblib',
        RAIZ/'Dados/pedidos_consolidados_teste.csv',PASTA_ORIGINAIS/'olist_orders_dataset.csv',
        PASTA_ORIGINAIS/'olist_order_items_dataset.csv',Path(__file__),
        RAIZ/'experimentos/testar_historicos_vendedores.py'])
    protocolo={'meta_recall':META,'candidatos':len(candidatos),
        'criterio':'Menor número de revisões com recall >=95% na validação; empate por AP de validação, depois ID.',
        'teste':'Retrospectivo, já consultado em experimentos anteriores; não participa da escolha.',
        'coorte':'Snapshot PostgreSQL com atrasos observados; 24667 validação e 25550 teste.',
        'exclusao':'Modelos de alvo simulado e coortes restritas a um vendedor não entram nesta comparação.',
        'versoes':{p:version(p) for p in ['numpy','pandas','scikit-learn','torch']},
        'fontes_sha256':{str(p.relative_to(RAIZ)):sha256(p) for p in sorted(fontes)}}
    (PASTA/'protocolo.json').write_text(json.dumps(protocolo,ensure_ascii=False,indent=2),encoding='utf-8')
    resultados=[];mensal=[];scores_guardados=[];limiares={}
    val=dados.loc[dados.particao.eq('validacao')].reset_index(drop=True)
    torch.set_num_threads(4)
    with threadpool_limits(limits=4):
        for c in candidatos:
            s=c['prever'](val)
            corte=escolher_limiar_recall(val.atrasou,s)
            # Conferência independente pela curva PR do Scikit-learn.
            _,r,t=precision_recall_curve(val.atrasou,s)
            np.testing.assert_allclose(corte,t[r[:-1]>=META].max(),rtol=0,atol=0)
            limiares[c['id']]=corte
            m=medir(val.atrasou,s,corte)
            assert m['atingiu_meta']
            resultados.append({'id':c['id'],'particao':'validacao',**m})
            scores_guardados.append((c['id'],'validacao',s))
            print(c['id'],c['nome'],'| revisão validação:',f"{m['fracao_revisao']:.2%}",flush=True)
        validacao=pd.DataFrame(resultados).merge(catalogo,on='id',validate='one_to_one')
        ranking=validacao.sort_values(['revisoes','AP','id'],ascending=[True,False,True])
        vencedor=ranking.iloc[0]
        por_familia=ranking.drop_duplicates('familia')
        selecao={'vencedor':vencedor.id,'nome':vencedor.nome,
            'limiar':limiares[vencedor.id],'limiares':limiares,
            'selecionados_por_familia':dict(zip(por_familia.familia,por_familia.id)),
            'regra':protocolo['criterio'],'estado':'congelado antes da inferência de teste'}
        (PASTA/'selecao_antes_teste.json').write_text(json.dumps(selecao,ensure_ascii=False,indent=2),encoding='utf-8')
        ranking.to_csv(PASTA/'ranking_validacao.csv',index=False)
        print('SELEÇÃO CONGELADA:',vencedor.id,vencedor.nome,flush=True)
        teste=dados.loc[dados.particao.eq('teste')].reset_index(drop=True)
        for c in candidatos:
            s=c['prever'](teste)
            resultados.append({'id':c['id'],'particao':'teste',**medir(teste.atrasou,s,limiares[c['id']])})
            scores_guardados.append((c['id'],'teste',s))
    # Política de referência: encaminhar todos; recall 100%, revisão 100%.
    for parte,tabela in [('validacao',val),('teste',teste)]:
        resultados.append({'id':'revisar_todos','particao':parte,**medir(tabela.atrasou,np.ones(len(tabela)),.5)})
    resultado=pd.DataFrame(resultados).merge(catalogo,on='id',how='left',validate='many_to_one')
    resultado.loc[resultado.id.eq('revisar_todos'),'nome']='Revisar todos'
    resultado['selecionado_validacao']=resultado.id.eq(vencedor.id)
    resultado.to_csv(PASTA/'metricas.csv',index=False)
    wide=dados[['order_id','particao','order_approved_at','atrasou']].copy()
    for c in candidatos:
        wide[c['id']]=np.nan
    for ident,parte,s in scores_guardados:
        mask=wide.particao.eq(parte)
        wide.loc[mask,ident]=s
        tabela=wide.loc[mask]
        for mes,g in tabela.groupby(tabela.order_approved_at.dt.strftime('%Y-%m')):
            mensal.append({'id':ident,'particao':parte,'mes':mes,**medir(g.atrasou,g[ident],limiares[ident])})
    wide.to_parquet(PASTA/'scores.parquet',index=False)
    pd.DataFrame(mensal).to_csv(PASTA/'metricas_mensais.csv',index=False)
    # Verificação independente de contagens: ID a ID, após gravar e reler.
    salvo=pd.read_parquet(PASTA/'scores.parquet')
    for linha in resultado.loc[resultado.id.ne('revisar_todos')].itertuples():
        t=salvo.loc[salvo.particao.eq(linha.particao)]
        alerta=t[linha.id].ge(linha.limiar)
        assert int(alerta.sum())==linha.revisoes
        assert int((~alerta & t.atrasou.eq(1)).sum())==linha.fn
        assert int((alerta & t.atrasou.eq(1)).sum())==linha.tp
    foco=resultado.loc[resultado.id.isin(por_familia.id)].sort_values(['familia','particao'])
    foco.to_csv(PASTA/'resumo_por_familia.csv',index=False)
    print(foco[['id','nome','particao','recall','fracao_revisao','fn','precision']].to_string(index=False),flush=True)
    print('CONFERÊNCIA APROVADA: mesmos pedidos, alvos reais, scores e contagens.',flush=True)
    print('Resultados:',PASTA,flush=True)
    return resultado


def reavaliar_meta(meta, pasta=PASTA):
    """Compara outra meta usando os mesmos scores, sem treinar ou sobrescrever 95%.

    Escolha e corte dependem apenas da validação. O teste já foi consultado antes:
    a comparação continua exploratória, mesmo sem usá-lo no cálculo dos cortes.
    """
    if not 0 < meta <= 1:
        raise ValueError('A meta precisa pertencer a (0, 1].')
    pasta = Path(pasta)
    destino = pasta/'metas'/f'recall{meta*100:g}'.replace('.', 'p')
    destino.mkdir(parents=True, exist_ok=True)
    scores = pd.read_parquet(pasta/'scores.parquet')
    catalogo = pd.read_csv(pasta/'catalogo.csv')
    referencia = pd.read_parquet(pasta/'pedidos_avaliacao.parquet').set_index('order_id')
    assert scores.order_id.is_unique and referencia.index.is_unique
    assert set(scores.order_id) == set(referencia.index)
    assert referencia.origem_dado.eq('real_olist').all() and referencia.rotulo_observado.all()
    assert catalogo.id.is_unique and len(catalogo) == 48
    assert scores.groupby('particao').size().to_dict() == {'teste':25550,'validacao':24667}
    for campo in ['atrasou','particao','order_approved_at']:
        assert scores[campo].equals(referencia.loc[scores.order_id,campo].reset_index(drop=True))
    protocolo = {'meta_recall':meta,'fonte':'Scores reais da comparação anterior, sem novo treinamento.',
        'criterio':'Menos revisões com recall mínimo na validação; empate por AP e ID.',
        'limite':'Teste histórico já consultado; evidência exploratória, sem garantia futura ou mensal.',
        'hashes_sha256':{str(p):sha256(p) for p in [pasta/'scores.parquet',
            pasta/'catalogo.csv',pasta/'pedidos_avaliacao.parquet',pasta/'protocolo.json',Path(__file__)]}}
    (destino/'protocolo.json').write_text(json.dumps(protocolo,ensure_ascii=False,indent=2),encoding='utf-8')
    val = scores.loc[scores.particao.eq('validacao')]
    cortes = {}; linhas = []; mensal = []
    for ident in catalogo.id:
        corte = escolher_limiar_recall(val.atrasou,val[ident],meta)
        _, recalls, limites = precision_recall_curve(val.atrasou,val[ident])
        assert corte == limites[recalls[:-1] >= meta].max()
        cortes[ident] = corte
        medida = medir(val.atrasou,val[ident],corte,meta)
        assert medida['atingiu_meta']
        linhas.append({'id':ident,'particao':'validacao','meta_recall':meta,**medida})
    ranking = pd.DataFrame(linhas).merge(catalogo,on='id',validate='one_to_one')
    ranking = ranking.sort_values(['revisoes','AP','id'],ascending=[True,False,True])
    escolhido = ranking.iloc[0]
    familias = ranking.drop_duplicates('familia')
    selecao = {'id':escolhido.id,'nome':escolhido.nome,'meta_recall':meta,
        'limiares':cortes,'familias':dict(zip(familias.familia,familias.id)),
        'estado':'Congelado antes de avaliar os scores de teste nesta reavaliação.'}
    (destino/'selecao_antes_avaliar_teste.json').write_text(
        json.dumps(selecao,ensure_ascii=False,indent=2),encoding='utf-8')
    ranking.to_csv(destino/'ranking_validacao.csv',index=False)
    print('SELEÇÃO PELA VALIDAÇÃO:',escolhido.id,escolhido.nome,flush=True)
    teste = scores.loc[scores.particao.eq('teste')]
    for ident in catalogo.id:
        linhas.append({'id':ident,'particao':'teste','meta_recall':meta,
                       **medir(teste.atrasou,teste[ident],cortes[ident],meta)})
        for (parte,mes),grupo in scores.groupby(['particao',scores.order_approved_at.dt.strftime('%Y-%m')]):
            mensal.append({'id':ident,'particao':parte,'mes':mes,'meta_recall':meta,
                           **medir(grupo.atrasou,grupo[ident],cortes[ident],meta)})
    resultado = pd.DataFrame(linhas).merge(catalogo,on='id',validate='many_to_one')
    resultado['selecionado_validacao'] = resultado.id.eq(escolhido.id)
    resultado.to_csv(destino/'metricas.csv',index=False)
    pd.DataFrame(mensal).to_csv(destino/'metricas_mensais.csv',index=False)
    resumo = resultado.loc[resultado.id.isin(familias.id)]
    resumo.to_csv(destino/'resumo_por_familia.csv',index=False)
    anterior = pd.read_csv(pasta/'metricas.csv')
    comparacao = resultado.merge(anterior[['id','particao','recall','revisoes','fracao_revisao','fn']],
        on=['id','particao'],suffixes=('','_meta95'),validate='one_to_one')
    comparacao['revisoes_a_menos'] = comparacao.revisoes_meta95 - comparacao.revisoes
    comparacao.to_csv(destino/'comparacao_com_meta95.csv',index=False)
    if meta <= META:
        assert comparacao.revisoes.le(comparacao.revisoes_meta95).all()
        assert comparacao.fn.ge(comparacao.fn_meta95).all()
    print(resumo[['id','familia','particao','recall','revisoes','fracao_revisao','fn']].to_string(index=False),flush=True)
    print('Resultados:',destino,flush=True)
    return resultado


if __name__=='__main__':
    import argparse
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reavaliar-recall',type=float,help='Nova meta, entre 0 e 1, usando scores salvos.')
    args = parser.parse_args()
    if args.reavaliar_recall is None:
        executar()
    else:
        reavaliar_meta(args.reavaliar_recall)
