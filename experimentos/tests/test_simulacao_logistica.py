"""Fixtures artificiais para testar regras de laboratório, nunca métricas do ML."""
import copy
import json
import unittest
import numpy as np
import pandas as pd
from experimentos.simulacao_logistica.dados import RAIZ, ATRIBUTOS, NUMERICAS, PROIBIDAS, historico_notas, preprocessador
from experimentos.simulacao_logistica.cenario import Cenario, atribuir_transportadoras, validar_config
from experimentos.simulacao_logistica.geracao import validar_geracao, corrigir_gerados, ENTRADAS


def fixture():
    rng=np.random.default_rng(123)
    b=pd.DataFrame({c:rng.uniform(1,100,60) for c in NUMERICAS})
    b['order_id']=[f'p{i}' for i in range(60)]
    b['seller_id']=[f'v{i%4}' for i in range(60)]
    b['order_approved_at']=pd.date_range('2017-01-01',periods=60)
    b['customer_state']='SP';b['categoria_principal']='moveis_decoracao';b['tipo_pagamento_principal']='credit_card'
    b['particao']='treino';b['origem_dado']='atributos_olist';b['atrasou_observado']=rng.integers(0,2,60)
    b['latitude_cliente']=-23.;b['longitude_cliente']=-46.;b['transportadora']='SIM_A'
    b['itens_sem_peso']=0;b['itens_sem_dimensoes']=0
    return b


class SimulacaoTest(unittest.TestCase):
    def test_diagnostico_pequeno_sem_atrasos(self):
        from experimentos.simulacao_logistica.avaliacao import metricas
        m = metricas([0, 0], [.2, .8], .5)
        self.assertEqual((m['tn'], m['fp'], m['fn'], m['tp']), (1, 1, 0, 0))
        self.assertEqual(m['fila10'], 0)
        self.assertTrue(np.isnan(m['AP']))
        self.assertTrue(np.isnan(m['precision_top10']))
        self.assertTrue(np.isnan(m['recall_top10']))

    def setUp(self):
        self.config=json.loads((RAIZ/'experimentos/configuracoes/cenario_logistico.json').read_text(encoding='utf-8'))
        self.geracao=json.loads((RAIZ/'experimentos/configuracoes/geracao_ctgan.json').read_text(encoding='utf-8'))

    def test_lista_explicita_impede_vazamento(self):
        self.assertFalse(PROIBIDAS.intersection(ATRIBUTOS))
        self.assertFalse(PROIBIDAS.intersection(ENTRADAS))
        with self.assertRaises(AssertionError):preprocessador(['probabilidade_regra'])
        with self.assertRaises(ValueError):preprocessador(['order_delivered_customer_date'])

    def test_historico_exclui_eventos_futuros_e_simultaneos(self):
        q=pd.DataFrame({'order_id':['b','c'],'seller_id':['v','v'],'order_approved_at':pd.to_datetime(['2017-01-02','2017-01-03'])})
        e=pd.DataFrame({'order_id':['a','b','futuro'],'seller_id':['v']*3,'nota':[5,1,1],'disponivel_em':pd.to_datetime(['2017-01-01','2017-01-02','2018-01-01'])})
        media,qtd,ultima=historico_notas(q,e)
        np.testing.assert_array_equal(qtd,[1,2])
        np.testing.assert_allclose(media,[11/3,3])
        self.assertTrue(ultima.lt(q.order_approved_at).all())

    def test_transportadora_independe_do_desfecho(self):
        b=fixture();a,eventos=atribuir_transportadoras(b,self.config)
        b['atrasou_observado']=1-b.atrasou_observado
        outro,_=atribuir_transportadoras(b,self.config)
        pd.testing.assert_series_equal(a.transportadora,outro.transportadora)
        self.assertTrue(a.groupby('seller_id').transportadora.nunique().eq(1).all())
        self.assertTrue((a.ultima_avaliacao_transportadora.isna()|a.ultima_avaliacao_transportadora.lt(a.order_approved_at)).all())

    def test_cenario_so_ajusta_treino_e_nao_muda_alvo_real(self):
        b,_=atribuir_transportadoras(fixture(),self.config)
        c=Cenario(self.config).ajustar(b)
        p=c.rotular(b,42);r=c.rotular(b,42)
        pd.testing.assert_series_equal(p.atrasou_observado,b.atrasou_observado)
        pd.testing.assert_series_equal(p.atrasou_simulado,r.atrasou_simulado)
        np.testing.assert_allclose(p.probabilidade_regra,r.probabilidade_regra)
        congelado=c.intercepto
        c.rotular(b.assign(peso_total_g=1e6,particao='teste'),99)
        self.assertEqual(c.intercepto,congelado)
        with self.assertRaises(ValueError):Cenario(self.config).ajustar(b.assign(particao='validacao'))

    def test_meta_calibrada_apenas_no_treino(self):
        config=copy.deepcopy(self.config);config['ruido_logit']=0
        b,_=atribuir_transportadoras(fixture(),config)
        c=Cenario(config).ajustar(b)
        self.assertAlmostEqual(c.rotular(b,1).probabilidade_regra.mean(),config['taxa_atraso_alvo'],places=7)

    def test_limites_e_configuracoes_invalidas(self):
        validar_geracao(self.geracao)
        with self.assertRaises(ValueError):validar_geracao({**self.geracao,'treino':30001})
        with self.assertRaises(ValueError):validar_geracao({**self.geracao,'teste':-1})
        with self.assertRaises(ValueError):validar_config({**self.config,'influencias':{'atrasou_observado':1}})
        with self.assertRaises(ValueError):validar_config({**self.config,'taxa_atraso_alvo':1})

    def test_gerados_respeitam_contagens_e_totais(self):
        treino=fixture();b=treino.copy()
        b['quantidade_itens']=2;b['quantidade_produtos']=30;b['quantidade_categorias']=90
        b['quantidade_pagamentos']=1;b['quantidade_formas_pagamento']=5
        b['preco_max_item']=99999;b['valor_itens']=100;b['valor_frete']=20
        r=corrigir_gerados(b,treino)
        self.assertTrue(r.quantidade_produtos.le(r.quantidade_itens).all())
        self.assertTrue(r.quantidade_categorias.le(r.quantidade_produtos).all())
        self.assertTrue(r.quantidade_formas_pagamento.le(r.quantidade_pagamentos).all())
        self.assertTrue(r.preco_max_item.le(r.valor_itens).all())
        np.testing.assert_allclose(r.valor_pago,120)
        self.assertTrue(r.latitude_cliente.eq(-23).all())


if __name__=='__main__':unittest.main()
