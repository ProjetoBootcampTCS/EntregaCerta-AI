"""Execute: python -m experimentos.simulacao_logistica --etapa tudo."""
import argparse
import hashlib
import json
import time
from importlib.metadata import version
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .dados import RAIZ, ATRIBUTOS, preparar_base
from .cenario import Cenario, atribuir_transportadoras, validar_config
from .geracao import ajustar_gerador, gerar, validar_geracao

MODELOS=RAIZ/'Modelos/experimento_simulacao'
DADOS=RAIZ/'Dados/simulacao_ctgan'


def digest(valor):
    return hashlib.sha256(json.dumps(valor,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]


def preparar(config, geracao):
    validar_config(config); validar_geracao(geracao)
    print('Consultando PostgreSQL e preparando atributos sem futuro...',flush=True)
    base,auditoria=preparar_base()
    base,eventos=atribuir_transportadoras(base,config)
    cenario=Cenario(config).ajustar(base.loc[base.particao.eq('treino')])
    grupos=[]
    for i,parte in enumerate(['treino','validacao','teste']):
        grupos.append(cenario.rotular(base.loc[base.particao.eq(parte)],config['seed_simulacao']+100+i))
    base=pd.concat(grupos,ignore_index=True)
    fontes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    identidade=digest({'config':config,'geracao':geracao,'base':auditoria['hash_base'],'codigo':fontes})
    pasta=MODELOS/identidade; destino=DADOS/identidade
    pasta.mkdir(parents=True,exist_ok=True); destino.mkdir(parents=True,exist_ok=True)
    manifesto={'id':identidade,'config_cenario':config,'config_geracao':geracao,'auditoria':auditoria,
        'codigo_sha256':fontes,'atributos':ATRIBUTOS,'fonte_referencia':'https://chatgpt.com/s/cx_6af5e63747a48191915d29e4c1cdad3c',
        'versoes':{n:version(n) for n in ['numpy','pandas','scikit-learn','torch','ctgan','rdt']},
        'aviso':'TRANSPORTADORAS, AVALIACOES DE TRANSPORTADORAS E ALVO SIMULADO SAO HIPOTESES. NAO COMPROVAM DESEMPENHO REAL.',
        'intercepto_regra':cenario.intercepto}
    (pasta/'manifesto.json').write_text(json.dumps(manifesto,ensure_ascii=False,indent=2),encoding='utf-8')
    joblib.dump({'base':base,'cenario':cenario,'eventos_transportadora':eventos,'manifesto':manifesto},pasta/'preparacao.joblib')
    base.groupby('particao').agg(pedidos=('order_id','size'),atrasos_observados=('atrasou_observado','sum'),atrasos_simulados=('atrasou_simulado','sum'),probabilidade_media_regra=('probabilidade_regra','mean')).to_csv(pasta/'coortes.csv')
    base[ATRIBUTOS].isna().sum().rename('ausentes').to_csv(pasta/'nulos.csv')
    MODELOS.mkdir(exist_ok=True)
    (MODELOS/'ultima_execucao.txt').write_text(identidade,encoding='utf-8')
    print('Experimento:',identidade,flush=True)
    print(pd.read_csv(pasta/'coortes.csv').to_string(index=False),flush=True)
    return pasta,destino,base,cenario


def gerar_tabelas(pasta,destino,base,cenario,geracao):
    if sum(geracao[p] for p in ['treino','validacao','teste'])==0:
        sinteticos=pd.DataFrame()
    else:
        treino=base.loc[base.particao.eq('treino')]
        config_fit={k:v for k,v in geracao.items() if k not in ['treino','validacao','teste','limite_por_particao']}
        assinatura=hashlib.sha256(treino[ATRIBUTOS].to_csv(index=False).encode()).hexdigest()
        chave=digest({'atributos':assinatura,'config':config_fit,'codigo':hashlib.sha256(Path(__file__).with_name('geracao.py').read_bytes()).hexdigest()})
        arquivo=MODELOS/'geradores'/f'{chave}.joblib';arquivo.parent.mkdir(exist_ok=True)
        if arquivo.exists():
            print('Reutilizando gerador treinado com os mesmos atributos e configuração.',flush=True)
            pacote=joblib.load(arquivo)
        else:
            print(f"Treinando CTGAN: {len(treino)} pedidos, {geracao['epocas']} épocas (CPU).",flush=True)
            inicio=time.monotonic()
            pacote=ajustar_gerador(treino,geracao)
            pacote['segundos_treino']=time.monotonic()-inicio
            joblib.dump(pacote,arquivo)
        if set(pacote['ids_ajuste'])!=set(treino.order_id):
            raise AssertionError('Gerador incompatível com IDs do treino atual.')
        blocos=[]
        for i,parte in enumerate(['treino','validacao','teste']):
            q=geracao[parte]
            if q:
                b=gerar(pacote,q,parte,geracao['seed_ctgan']+1000+i)
                b=cenario.rotular(b,cenario.config['seed_simulacao']+2000+i)
                blocos.append(b)
        sinteticos=pd.concat(blocos,ignore_index=True)
        perdas=getattr(pacote['modelo'],'loss_values',pd.DataFrame())
        perdas.to_csv(pasta/'perdas_ctgan.csv',index=False)
        (pasta/'gerador_usado.txt').write_text(str(arquivo.relative_to(RAIZ)),encoding='utf-8')
    joblib.dump(sinteticos,pasta/'sinteticos.joblib')
    combinado=pd.concat([base,sinteticos],ignore_index=True)
    if not combinado.order_id.is_unique or (not sinteticos.empty and sinteticos.atrasou_observado.notna().any()):
        raise AssertionError('Identidade duplicada ou alvo real inventado.')
    combinado.to_csv(destino/'pedidos_cenario_e_injetados.csv',index=False)
    print('CSV:',destino/'pedidos_cenario_e_injetados.csv',flush=True)
    print('Sintéticos gerados:',len(sinteticos),flush=True)
    return sinteticos


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--etapa',choices=['preparar','gerar','avaliar','tudo'],default='tudo')
    parser.add_argument('--cenario',type=Path,default=RAIZ/'experimentos/configuracoes/cenario_logistico.json')
    parser.add_argument('--geracao',type=Path,default=RAIZ/'experimentos/configuracoes/geracao_ctgan.json')
    args=parser.parse_args()
    config=json.loads(args.cenario.read_text(encoding='utf-8'))
    geracao=json.loads(args.geracao.read_text(encoding='utf-8'))
    with threadpool_limits(limits=4):
        if args.etapa=='avaliar':
            pasta=MODELOS/(MODELOS/'ultima_execucao.txt').read_text(encoding='utf-8').strip()
            pacote=joblib.load(pasta/'preparacao.joblib')
            base,cenario=pacote['base'],pacote['cenario']
            if pacote['manifesto']['config_cenario']!=config or pacote['manifesto']['config_geracao']!=geracao:
                raise ValueError('Configuração mudou. Execute --etapa tudo para criar outro experimento.')
            sinteticos=joblib.load(pasta/'sinteticos.joblib')
        else:
            pasta,destino,base,cenario=preparar(config,geracao)
            if args.etapa=='preparar':
                return
            sinteticos=gerar_tabelas(pasta,destino,base,cenario,geracao)
        if args.etapa in ['avaliar','tudo']:
            from .avaliacao import avaliar, criar_graficos
            metricas,previsoes=avaliar(base,sinteticos,config,pasta)
            criar_graficos(base,sinteticos,metricas,previsoes,pasta)
            print(metricas[['experimento','modelo','particao','f1','precision','recall','AP']].to_string(index=False),flush=True)
            print('Resultados:',pasta,flush=True)


if __name__=='__main__':
    main()
