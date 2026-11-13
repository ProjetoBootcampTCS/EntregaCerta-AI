"""Regras hipotéticas explícitas; não alteram o atraso observado da Olist."""
import hashlib
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .dados import NUMERICAS, PROIBIDAS, historico_notas

FRETE_X = ['distancia_vendedor_cliente_km','peso_total_g','volume_total_cm3','quantidade_itens']
SEM_LOG = {'latitude_cliente','longitude_cliente','frete_relativo','nota_historica_vendedor','nota_historica_transportadora','dia_semana_aprovacao','mes_aprovacao','hora_aprovacao'}


def validar_config(config):
    if config['filtro_vendedores'] != 'unico':
        raise ValueError('Esta versão implementa apenas pedidos com um vendedor.')
    if not 0 < config['taxa_atraso_alvo'] < 1:
        raise ValueError('A taxa-alvo deve estar entre zero e um.')
    if not 0 < config['intensidade_sinal'] <= 20 or not 0 <= config['ruido_logit'] <= 10:
        raise ValueError('Intensidade (0,20] e ruído [0,10].')
    if config['vinculo_transportadora'] not in ['vendedor','pedido']:
        raise ValueError('Vínculo deve ser vendedor ou pedido.')
    if not config['transportadoras'] or not all(k.startswith('SIM_') for k in config['transportadoras']):
        raise ValueError('Identifique as transportadoras simuladas com o prefixo SIM_.')
    if PROIBIDAS.intersection(config['influencias']) or not set(config['influencias']).issubset(NUMERICAS):
        raise ValueError('Influências devem usar somente atributos autorizados.')
    for p in config['transportadoras'].values():
        if not 1 <= p['nota_media'] <= 5:
            raise ValueError('Nota simulada deve estar entre 1 e 5.')
    limites=config['limites_risco']
    if not 0 < limites['medio'] < limites['alto'] < 1:
        raise ValueError('Limites de risco fora de ordem.')


def atribuir_transportadoras(base, config):
    """Vínculo por hash de ID+semente, sem olhar rótulos ou avaliações futuras."""
    validar_config(config)
    b=base.copy()
    nomes=sorted(config['transportadoras'])
    coluna='seller_id' if config['vinculo_transportadora']=='vendedor' else 'order_id'
    def nome(chave):
        h=hashlib.sha256(f"{config['seed_transportadoras']}|{chave}".encode()).hexdigest()
        return nomes[int(h[:16],16)%len(nomes)]
    b['transportadora']=b[coluna].map(nome)
    rng=np.random.default_rng(config['seed_simulacao'])
    medias=b.transportadora.map({k:p['nota_media'] for k,p in config['transportadoras'].items()})
    notas=np.clip(np.rint(medias+rng.normal(0,.65,len(b))),1,5)
    eventos=b[['order_id','transportadora']].assign(nota=notas)
    # Uma avaliação fictícia só passa a existir depois da promessa simulada.
    eventos['disponivel_em']=b.order_approved_at+pd.to_timedelta(b.prazo_prometido_dias.fillna(30).clip(lower=1)+1,unit='D')
    b['nota_historica_transportadora'],b['qtd_avaliacoes_transportadora'],b['ultima_avaliacao_transportadora']=historico_notas(b,eventos,'transportadora')
    return b,eventos


class Cenario:
    def __init__(self, config):
        validar_config(config)
        self.config=config
        self.colunas=list(config['influencias'])
        if 'distancia_vendedor_cliente_km' not in self.colunas:
            self.colunas.append('distancia_vendedor_cliente_km')

    def adicionar_frete_relativo(self, base):
        b=base.copy()
        esperado=self.frete.predict(np.log1p(b[FRETE_X].clip(lower=0)))
        b['frete_relativo']=np.log1p(b.valor_frete.clip(lower=0))-esperado
        return b

    def transformar(self, base):
        x=base[self.colunas].copy()
        for c in self.colunas:
            if c not in SEM_LOG:
                x[c]=np.log1p(x[c].clip(lower=0))
        return x

    def ajustar(self, treino):
        if not treino.particao.eq('treino').all() or not treino.origem_dado.eq('atributos_olist').all():
            raise ValueError('Ajuste do cenário permitido somente no treino com atributos reais.')
        self.frete=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True), StandardScaler(), Ridge(alpha=10))
        y=np.log1p(treino.valor_frete.clip(lower=0))
        self.frete.fit(np.log1p(treino[FRETE_X].clip(lower=0)), y.fillna(y.median()))
        b=self.adicionar_frete_relativo(treino)
        self.escala=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler())
        self.escala.fit(self.transformar(b))
        risco=self.risco(b)
        self.intercepto=brentq(lambda v: expit(risco+v).mean()-self.config['taxa_atraso_alvo'],-1000,1000)
        return self

    def risco(self, base):
        z=pd.DataFrame(self.escala.transform(self.transformar(base)),columns=self.colunas,index=base.index).clip(-6,6)
        valor=sum(z[c]*peso for c,peso in self.config['influencias'].items())
        perfis=self.config['transportadoras']
        valor=valor+base.transportadora.map({k:p['efeito'] for k,p in perfis.items()}).to_numpy()
        valor=valor+z.distancia_vendedor_cliente_km*base.transportadora.map({k:p['distancia'] for k,p in perfis.items()}).to_numpy()
        valor=valor+base.categoria_principal.map(self.config.get('efeitos_categoria',{})).fillna(0).to_numpy()
        valor=valor+base.customer_state.map(self.config.get('efeitos_uf',{})).fillna(0).to_numpy()
        return np.asarray(valor*self.config['intensidade_sinal'],float)

    def rotular(self, base, semente):
        b=self.adicionar_frete_relativo(base)
        rng=np.random.default_rng(semente)
        logits=self.risco(b)+self.intercepto+rng.normal(0,self.config['ruido_logit'],len(b))
        b['probabilidade_regra']=expit(logits)
        b['atrasou_simulado']=(rng.random(len(b))<b.probabilidade_regra).astype('int8')
        limites=self.config['limites_risco']
        b['faixa_risco_regra']=np.select([b.probabilidade_regra.ge(limites['alto']),b.probabilidade_regra.ge(limites['medio'])],['alto','medio'],default='baixo')
        return b
