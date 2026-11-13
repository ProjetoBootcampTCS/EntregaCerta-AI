"""Compara alvos observados e simulados em quadros separados, sem escolher pelo teste."""
import joblib
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.metrics import (brier_score_loss, precision_recall_curve, confusion_matrix,
    accuracy_score, precision_score, recall_score, f1_score, average_precision_score)
from sklearn.calibration import calibration_curve
from .dados import ATRIBUTOS, ARTIFICIAIS, NUMERICAS, CATEGORICAS, preprocessador
from ..testar_historicos_vendedores import escolher_limiar


def metricas(y, scores, limiar):
    """Métricas inclusive para diagnósticos pequenos ou sem positivos; indefinidas = NaN."""
    y = np.asarray(y, dtype=int)
    scores = np.asarray(scores, dtype=float)
    if len(y) == 0 or len(scores) != len(y):
        raise ValueError('Avaliação requer alvos e scores não vazios de mesmo tamanho.')
    previsto = scores >= limiar
    tn, fp, fn, tp = confusion_matrix(y, previsto, labels=[0, 1]).ravel()
    k = int(len(y) * .10)
    positivos = int(y.sum())
    acertos = int(y[np.argsort(-scores, kind='stable')[:k]].sum())
    return {'pedidos':len(y), 'atrasos':positivos, 'limiar':limiar,
        'accuracy':accuracy_score(y, previsto),
        'precision':precision_score(y, previsto, zero_division=0),
        'recall':recall_score(y, previsto, zero_division=0),
        'f1':f1_score(y, previsto, zero_division=0),
        'AP':average_precision_score(y, scores) if positivos else np.nan,
        'tn':int(tn), 'fp':int(fp), 'fn':int(fn), 'tp':int(tp),
        'fila10':k, 'atrasos_top10':acertos,
        'precision_top10':acertos/k if k else np.nan,
        'recall_top10':acertos/positivos if positivos else np.nan}


def avaliar(base,sinteticos,config,pasta):
    classificadores={
        'Dummy':DummyClassifier(strategy='prior'),
        'Logistica':LogisticRegression(C=.3,max_iter=2000,random_state=config['seed_modelo']),
        'HGB':HistGradientBoostingClassifier(max_iter=180,max_leaf_nodes=15,learning_rate=.08,l2_regularization=2,early_stopping=False,random_state=config['seed_modelo'])}
    resultados=[];predicoes=[];eleitos=[]
    treino=base.loc[base.particao.eq('treino')]
    validacao=base.loc[base.particao.eq('validacao')]
    teste=base.loc[base.particao.eq('teste')]
    cenarios=[('observado_sem_injecao','atrasou_observado',False),('simulado_sem_ctgan','atrasou_simulado',False)]
    if not sinteticos.empty and sinteticos.particao.eq('treino').any():
        cenarios.append(('simulado_com_ctgan','atrasou_simulado',True))
    for experimento,alvo,aumentar in cenarios:
        colunas=[c for c in ATRIBUTOS if alvo!='atrasou_observado' or c not in ARTIFICIAIS]
        dados_treino=treino
        if aumentar:
            dados_treino=pd.concat([treino,sinteticos.loc[sinteticos.particao.eq('treino')]],ignore_index=True)
        # Transformações estatísticas aprendidas só em atributos reais do treino,
        # iguais nos braços com e sem aumento; evita outra variável na comparação.
        tratamento=preprocessador(colunas).fit(treino[colunas])
        x=tratamento.transform(dados_treino[colunas]).astype(np.float32)
        xv=tratamento.transform(validacao[colunas]).astype(np.float32)
        xt=tratamento.transform(teste[colunas]).astype(np.float32)
        y=dados_treino[alvo].to_numpy(dtype=int)
        candidatos=[]
        for nome,estimador in classificadores.items():
            print(f'Treinando {experimento} / {nome}: {len(y)} pedidos',flush=True)
            modelo=clone(estimador).fit(x,y)
            sv=modelo.predict_proba(xv)[:,1]
            limiar=.5 if nome=='Dummy' else escolher_limiar(validacao[alvo].to_numpy(int),sv)
            caminho=pasta/f'modelo_{experimento}_{nome}.joblib'
            # A inferência deve usar a mesma precisão numérica das matrizes treinadas.
            # Sem isso, limites das árvores podem mudar ao receber float64.
            pipeline=Pipeline([('tratamento',tratamento),
                ('float32',FunctionTransformer(np.asarray,kw_args={'dtype':np.float32})),
                ('modelo',modelo)])
            joblib.dump({'pipeline':pipeline,'colunas':colunas,'alvo':alvo,'limiar':limiar,'experimento':experimento},caminho)
            for parte,tabela,scores in [('validacao',validacao,sv),('teste',teste,modelo.predict_proba(xt)[:,1])]:
                real=tabela[alvo].to_numpy(dtype=int)
                linha={'experimento':experimento,'modelo':nome,'particao':parte,'populacao':'atributos_olist',
                       'alvo':alvo,'treino_pedidos':len(y),**metricas(real,scores,limiar),
                       'brier':brier_score_loss(real,scores),'taxa_atraso':float(real.mean())}
                resultados.append(linha)
                if parte=='validacao':candidatos.append(linha)
                predicoes.append(pd.DataFrame({'order_id':tabela.order_id.to_numpy(),'experimento':experimento,'modelo':nome,'particao':parte,'real':real,'score':scores,'limiar':limiar}))
            if alvo=='atrasou_simulado' and not sinteticos.empty:
                for parte in ['validacao','teste']:
                    diagnostico=sinteticos.loc[sinteticos.particao.eq(parte)]
                    if diagnostico.empty:continue
                    scores=modelo.predict_proba(tratamento.transform(diagnostico[colunas]).astype(np.float32))[:,1]
                    real=diagnostico[alvo].to_numpy(int)
                    resultados.append({'experimento':experimento,'modelo':nome,'particao':parte,'populacao':'CTGAN_DIAGNOSTICO_NAO_INDEPENDENTE',
                        'alvo':alvo,'treino_pedidos':len(y),**metricas(real,scores,limiar),'brier':brier_score_loss(real,scores),'taxa_atraso':float(real.mean())})
        vencedor=max(candidatos,key=lambda r:(r['f1'],r['AP']))
        eleitos.append({'experimento':experimento,'modelo':vencedor['modelo'],'criterio':'F1 na validacao, desempate AP','f1_validacao':vencedor['f1']})
    tabela=pd.DataFrame(resultados);predicoes=pd.concat(predicoes,ignore_index=True)
    tabela.to_csv(pasta/'metricas.csv',index=False)
    predicoes.to_csv(pasta/'previsoes.csv',index=False)
    pd.DataFrame(eleitos).to_csv(pasta/'selecionados_na_validacao.csv',index=False)
    if not sinteticos.empty:
        st=sinteticos.loc[sinteticos.particao.eq('treino')]
        if not st.empty:
            qualidade=[]
            for c in NUMERICAS:
                a,b=treino[c].dropna(),st[c].dropna()
                qualidade.append({'coluna':c,'tipo':'numerica','distancia_ks':ks_2samp(a,b).statistic if len(a) and len(b) else np.nan,
                    'media_olist':a.mean(),'media_ctgan':b.mean(),'fracao_nulos_olist':treino[c].isna().mean(),'fracao_nulos_ctgan':st[c].isna().mean()})
            for c in CATEGORICAS:
                a=treino[c].fillna('AUSENTE').value_counts(normalize=True)
                b=st[c].fillna('AUSENTE').value_counts(normalize=True)
                qualidade.append({'coluna':c,'tipo':'categorica','distancia_tvd':a.subtract(b,fill_value=0).abs().sum()/2})
            pd.DataFrame(qualidade).to_csv(pasta/'qualidade_sinteticos.csv',index=False)
            hreal=set(pd.util.hash_pandas_object(treino[ATRIBUTOS],index=False))
            hsint=pd.util.hash_pandas_object(st[ATRIBUTOS],index=False)
            (pasta/'duplicatas_sinteticas.txt').write_text(f'Linhas identicas entre sinteticos: {int(hsint.duplicated().sum())}\nLinhas identicas ao treino: {int(hsint.isin(hreal).sum())}\nNao equivale a uma auditoria de privacidade.',encoding='utf-8')
    return tabela,predicoes


def criar_graficos(base,sinteticos,metricas_df,previsoes,pasta):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.facecolor':'white'})
    cores=['#267278','#dc7f27','#8562b5']
    def salvar(fig,nome):
        fig.tight_layout();fig.savefig(pasta/nome,dpi=145,bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.5))
    taxas=base.groupby('particao')[['atrasou_observado','atrasou_simulado']].mean().reindex(['treino','validacao','teste'])
    taxas.rename(columns={'atrasou_observado':'Atraso observado','atrasou_simulado':'Atraso por regra simulada'}).plot.bar(ax=ax,color=cores[:2],rot=0)
    ax.set(title='A taxa muda ao trocar o alvo observado por uma hipótese',ylabel='Proporção de atrasos',xlabel='Partição temporal',ylim=(0,max(.25,float(taxas.max().max())*1.3)))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    salvar(fig,'01_classes.png')
    fig,ax=plt.subplots(figsize=(9,4.5))
    b=base.assign(faixa=pd.cut(base.distancia_vendedor_cliente_km,[0,100,300,600,1000,2000,20000],labels=['Até 100','100–300','300–600','600–1.000','1.000–2.000','Acima de 2.000'],include_lowest=True))
    b.groupby('faixa',observed=True)[['atrasou_observado','atrasou_simulado']].mean().rename(columns={'atrasou_observado':'Observado Olist','atrasou_simulado':'Regra simulada'}).plot.bar(ax=ax,color=cores[:2],rot=0)
    ax.set(title='Distância e atraso: associação observada versus regra imposta',xlabel='Faixa de distância geodésica (km)',ylabel='Proporção de atrasos',ylim=(0,1));ax.yaxis.set_major_formatter(PercentFormatter(1))
    salvar(fig,'02_distancia.png')
    sim=metricas_df.loc[metricas_df.experimento.str.startswith('simulado')&metricas_df.populacao.eq('atributos_olist')]
    fig,ax=plt.subplots(figsize=(11,5))
    r=sim.pivot(index=['experimento','modelo'],columns='particao',values='f1').reindex(columns=['validacao','teste'])
    r.index=[('Com CTGAN' if a=='simulado_com_ctgan' else 'Sem CTGAN')+' / '+m for a,m in r.index]
    r.plot.barh(ax=ax,color=cores[:2]);ax.set(title='Cenário simulado: comparação no mesmo conjunto reservado',xlabel='F1 (limiar escolhido na validação)',ylabel='',xlim=(0,1));ax.xaxis.set_major_formatter(PercentFormatter(1));salvar(fig,'03_f1_cenario.png')
    eleitos=pd.read_csv(pasta/'selecionados_na_validacao.csv')
    fig,axes=plt.subplots(1,len(eleitos),figsize=(15,4.8))
    fig2,calibs=plt.subplots(1,len(eleitos),figsize=(15,4.8))
    fig3,cms=plt.subplots(1,len(eleitos),figsize=(14,4.5))
    titulos={'observado_sem_injecao':'Atrasos observados\nSem injeção','simulado_sem_ctgan':'Alvo simulado\nSem CTGAN','simulado_com_ctgan':'Alvo simulado\nCom CTGAN'}
    for i,e in enumerate(eleitos.itertuples()):
        for parte,cor in [('validacao',cores[0]),('teste',cores[1])]:
            p=previsoes.loc[previsoes.experimento.eq(e.experimento)&previsoes.modelo.eq(e.modelo)&previsoes.particao.eq(parte)]
            precision,recall,_=precision_recall_curve(p.real,p.score)
            axes[i].plot(recall,precision,label=parte,color=cor,ls='-' if parte=='validacao' else '--')
            obs,estimada=calibration_curve(p.real,p.score,n_bins=8,strategy='quantile')
            calibs[i].plot(estimada,obs,'o-' if parte=='validacao' else 's--',label=parte,color=cor)
        axes[i].axhline(p.real.mean(),color='gray',ls='--',label='Taxa de teste')
        axes[i].set(title=titulos[e.experimento]+' / '+e.modelo,xlabel='Recall',ylabel='Precision',xlim=(0,1),ylim=(0,1));axes[i].legend(fontsize=8)
        calibs[i].plot([0,1],[0,1],'--',color='gray');calibs[i].set(title=titulos[e.experimento]+' / '+e.modelo,xlabel='Probabilidade estimada média',ylabel='Frequência observada no alvo',xlim=(0,1),ylim=(0,1));calibs[i].legend(fontsize=8)
        cm=confusion_matrix(p.real,p.score.ge(p.limiar),labels=[0,1]);cms[i].imshow(cm,cmap='Blues',vmin=0,vmax=len(p))
        for a in range(2):
            for c in range(2):cms[i].text(c,a,str(cm[a,c]),ha='center',va='center',color='white' if cm[a,c]>len(p)/2 else '#153147')
        cms[i].set(title=titulos[e.experimento]+' / '+e.modelo,xlabel='Predição',ylabel='Alvo no teste',xticks=[0,1],yticks=[0,1],xticklabels=['No prazo','Atrasou'],yticklabels=['No prazo','Atrasou'])
        for eixo in [axes[i],calibs[i]]:
            eixo.xaxis.set_major_formatter(PercentFormatter(1));eixo.yaxis.set_major_formatter(PercentFormatter(1))
    salvar(fig,'04_precision_recall.png');salvar(fig2,'05_calibracao.png');salvar(fig3,'06_confusao.png')
    if not sinteticos.empty:
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        for ax,col in zip(axes,['distancia_vendedor_cliente_km','peso_total_g','valor_frete']):
            valores=[np.log1p(t.loc[t.particao.eq('treino'),col].dropna()) for t in [base,sinteticos]]
            bins=np.histogram_bin_edges(np.concatenate(valores),bins=35)
            for tabela,nome,cor in [(base,'Atributos Olist',cores[0]),(sinteticos,'CTGAN',cores[1])]:
                v=np.log1p(tabela.loc[tabela.particao.eq('treino'),col].dropna())
                ax.hist(v,bins=bins,histtype='step',density=True,label=nome,color=cor,linewidth=1.7,linestyle='-' if nome=='Atributos Olist' else '--')
            nomes={'distancia_vendedor_cliente_km':'Distância (km)','peso_total_g':'Peso total (g)','valor_frete':'Frete (R$)'}
            ax.set(title=nomes[col],xlabel='log(1 + valor)',ylabel='Densidade');ax.legend(fontsize=8)
        salvar(fig,'07_distribuicoes.png')
