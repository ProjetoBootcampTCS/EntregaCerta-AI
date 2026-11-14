"""Fixtures artificiais para verificar tempo e contagem; não medem desempenho."""
import unittest
import numpy as np
import pandas as pd
from experimentos.testar_previsao_operacional import (
    criar_snapshot, divisao_temporal, medir_politica, OPERACIONAIS)


def base_teste():
    b=pd.DataFrame({
        'order_approved_at':pd.to_datetime(['2017-01-01']*5),
        'order_delivered_carrier_date':pd.to_datetime([
            '2017-01-05','2017-01-02',None,'2016-12-31','2017-01-01']),
        'order_delivered_customer_date':pd.to_datetime([
            '2017-01-15','2017-01-08','2017-01-15','2017-01-15','2017-01-02']),
        'fim_prazo':pd.to_datetime(['2017-01-11']*5),
        'limite_postagem':pd.to_datetime(['2017-01-04']*5),
        'hist_entrega_dias_media':[7.]*5,'hist_postagem_dias_media':[2.]*5,
        'atrasou':[1,0,1,1,0]})
    b['rotulo_disponivel_em']=b.order_delivered_customer_date
    return b


class PrevisaoOperacionalTest(unittest.TestCase):
    def test_futuro_nao_altera_atributos_da_preparacao(self):
        b=base_teste(); a=criar_snapshot(b,'preparacao48h')
        b.loc[0,'order_delivered_carrier_date']=pd.Timestamp('2017-01-07')
        b.loc[0,'order_delivered_customer_date']=pd.Timestamp('2017-01-20')
        c=criar_snapshot(b,'preparacao48h')
        pd.testing.assert_series_equal(a.loc[0,OPERACIONAIS],c.loc[0,OPERACIONAIS])
        self.assertEqual(a.loc[0,'despachado'],0)
        self.assertTrue(pd.isna(a.loc[0,'dias_ate_despacho']))

    def test_evento_de_despacho_conhecido_no_instante(self):
        s=criar_snapshot(base_teste(),'despacho')
        self.assertEqual(s.loc[0,'instante'],pd.Timestamp('2017-01-05'))
        self.assertEqual(s.loc[0,'despachado'],1)
        self.assertEqual(s.loc[0,'dias_ate_despacho'],4)
        self.assertEqual(s.loc[0,'dias_em_transito'],0)

    def test_sem_despacho_e_timestamp_invalido_nao_sao_excluidos(self):
        s=criar_snapshot(base_teste(),'despacho')
        for i in [2,3]:
            self.assertTrue(s.loc[i,'elegivel'])
            self.assertEqual(s.loc[i,'instante'],pd.Timestamp('2017-01-10'))
            self.assertEqual(s.loc[i,'dias_restantes'],1)
            self.assertEqual(s.loc[i,'despachado'],0)

    def test_prazo_curto_antecipa_checagem_e_entregue_nao_recebe_alerta(self):
        b=base_teste(); b.loc[0,'fim_prazo']=pd.Timestamp('2017-01-03')
        s=criar_snapshot(b,'preparacao48h')
        self.assertEqual(s.loc[0,'instante'],pd.Timestamp('2017-01-02'))
        self.assertFalse(s.loc[4,'elegivel'])
        self.assertTrue(s.loc[4,'ja_entregue'])

    def test_corte_temporal_expurga_rotulo_futuro(self):
        b=pd.DataFrame({'order_approved_at':pd.to_datetime([
            '2017-01-01','2017-01-02','2017-02-01','2017-02-02','2017-03-01']),
            'rotulo_disponivel_em':pd.to_datetime([
            '2017-01-15','2017-02-15','2017-02-15','2017-03-15','2017-03-20'])})
        t,c,a=divisao_temporal(b,'2017-02-01','2017-03-01','2017-04-01')
        self.assertEqual(list(t),[0]);self.assertEqual(list(c),[2]);self.assertEqual(list(a),[4])

    def test_politica_combinada_conta_pedido_uma_vez(self):
        b=base_teste(); ss={e:criar_snapshot(b,e) for e in ['preparacao48h','despacho']}
        scores={'Logistica/preparacao48h':np.array([.9,.1,.2,.3,-1]),
                'Logistica/despacho':np.array([.8,.1,.9,.2,.1])}
        m,primeiro=medir_politica(b,ss,b.index,scores,'Logistica/combinada',.5)
        self.assertEqual(m['revisoes'],2)
        self.assertEqual(m['eventos_alerta'],3)
        self.assertEqual(primeiro.loc[0],pd.Timestamp('2017-01-03'))
        self.assertEqual(m['fn'],1)
        self.assertGreaterEqual(m['antecedencia_minima_dias'],1)


if __name__=='__main__':unittest.main()
