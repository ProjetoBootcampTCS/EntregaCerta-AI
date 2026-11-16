"""Contratos novos; somente fixtures para treinos de teste, nunca a base real."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.dados.preparar_dados import (construir_merge, engenharia, estatisticas_vendedores,
    atribuir_transportadoras, confiabilidade_vendedor, preencher_atrasos_pln)
from src.experimentos.legado.pln_status_entrega import comentarios, rotular_texto
from src.ml.metricas import avaliar
from src.dados.esquema import ATRIBUTOS, sha256
from src.ml.dados_treino import exigir_revisao, validar_tabela, carregar
from src.ml.experimentos import executar, treinar, montar_particao, assinaturas
from src.ctgan.geracao import ajustar, amostrar


def fontes_fixture():
    return {
        'orders': pd.DataFrame({
            'order_id':['o1','o2'], 'customer_id':['c1','c2'], 'order_status':['delivered','canceled'],
            'order_purchase_timestamp':['2020-01-01 12:00:00','2020-01-02 10:00:00'],
            'order_approved_at':['2020-01-02 12:00:00','2020-01-02 11:00:00'],
            'order_delivered_carrier_date':['2020-01-03',None],
            'order_delivered_customer_date':['2020-01-08',None],
            'order_estimated_delivery_date':['2020-01-10','2020-01-15']}),
        'customers':pd.DataFrame({'customer_id':['c1','c2'],'customer_zip_code_prefix':['001','002'],'customer_state':['SP','RJ']}),
        'sellers':pd.DataFrame({'seller_id':['s1','s2'],'seller_zip_code_prefix':['003','004'],'seller_state':['SP','RJ']}),
        'order_items':pd.DataFrame({'order_id':['o1','o1','o1'],'order_item_id':[1,2,3],
            'product_id':['p1','p1','p2'],'seller_id':['s1','s1','s1'],'price':[10.,10.,30.],'freight_value':[1.,1.,3.]}),
        'products':pd.DataFrame({'product_id':['p1','p2'],'product_category_name':['livro','roupa'],
            'product_weight_g':[100.,300.],'product_length_cm':[2.,3.],'product_height_cm':[3.,4.],'product_width_cm':[4.,5.]}),
        'order_payments':pd.DataFrame({'order_id':['o1','o1'],'payment_sequential':[1,2],
            'payment_installments':[2,3],'payment_value':[20.,35.]}),
        'order_reviews':pd.DataFrame({'order_id':['o1','o1'],'review_score':[1,5],
            'review_comment_title':['A','B'],'review_comment_message':['primeira','segunda']}),
        'geolocation':pd.DataFrame({'geolocation_zip_code_prefix':['001','001','002','003','004'],
            'geolocation_lat':[0.,0.,1.,0.,0.],'geolocation_lng':[0.,0.,1.,1.,3.]})}


class PreparacaoTest(unittest.TestCase):
    def test_transportadora_reproduzivel_independente_da_ordem(self):
        base=pd.DataFrame({'order_id':[str(i) for i in range(100)]})
        a=atribuir_transportadoras(base,{'quantidade':3,'semente':42})
        b=atribuir_transportadoras(base.iloc[::-1],{'quantidade':3,'semente':42})
        pd.testing.assert_series_equal(a,b.sort_index())
        self.assertEqual(set(a),{'transportadora_1','transportadora_2','transportadora_3'})
        self.assertFalse(a.equals(atribuir_transportadoras(base,{'quantidade':3,'semente':43})))
        with self.assertRaises(ValueError):atribuir_transportadoras(base,{'quantidade':0})

    def test_score_composto_sem_imputar_nota(self):
        base=pd.DataFrame({'seller_review_score_mean':[5.,3.,np.nan],'seller_sales_count':[100,50,5]})
        score=confiabilidade_vendedor(base)
        self.assertEqual(score[:2].tolist(),[5.,2.8])
        self.assertTrue(pd.isna(score.iloc[2]))
        self.assertEqual(confiabilidade_vendedor(base.assign(seller_sales_count=0)).iloc[0],3.)

    def test_pln_preserva_rotulos_e_dias_e_exclui_so_ausentes_nao_atrasados(self):
        class Modelo:
            def predict(self,textos):
                self.textos=textos.tolist()
                return np.array(['atrasado','no prazo'])
        base=pd.DataFrame({'order_id':['conhecido','atraso','prazo','sem_texto'],
            'delay_status':[0,np.nan,np.nan,np.nan], 'delay_in_days':[-3,np.nan,np.nan,np.nan],
            'review_comment_title':[None,'["Não recebi"]',None,None],
            'review_comment_message':['nao recebi','["Passou do prazo"]','chegou no prazo',None]})
        modelo=Modelo();d,r=preencher_atrasos_pln(base,modelo)
        self.assertEqual(d.order_id.tolist(),['conhecido','atraso'])
        self.assertEqual(d.delay_status.tolist(),[0,1])
        self.assertTrue(pd.isna(d.iloc[1].delay_in_days))
        self.assertEqual(modelo.textos,['nao recebi passou do prazo','chegou no prazo'])
        self.assertEqual(r['descartados_sem_classificacao_atrasado'],2)
        self.assertEqual(rotular_texto('nao passou do prazo'),'no prazo')
        validar_tabela(d,[])
        d2,r2=preencher_atrasos_pln(d,None)
        pd.testing.assert_frame_equal(d,d2)
        self.assertEqual(r2['preenchidos_pln'],0)

    def test_merge_nao_multiplica_itens_pagamentos_ou_avaliacoes(self):
        f=fontes_fixture();m=construir_merge(f)
        self.assertEqual(len(m),1)  # um pedido, com três itens; sem vendedor não entra
        self.assertEqual(json.loads(m.loc[0,'product_id']),['p1','p1','p2'])
        d,_=engenharia(m,{},estatisticas_vendedores(f))
        d=d.set_index('order_id');o=d.loc['o1']
        self.assertEqual(o.qtd_items,3)
        self.assertEqual(o.total_weight,500)
        self.assertEqual(o.total_volume_cm3,108)
        self.assertEqual(o.price,50)
        self.assertEqual(o.payment_value,55)
        self.assertEqual(o.review_score,3)
        self.assertEqual(o.predominant_product_category_name,'livro')
        self.assertAlmostEqual(o.distance_customer_seller,111.195080233,places=6)
        self.assertEqual(o.delay_in_days,-2)
        self.assertEqual(o.delay_status,0)
        self.assertEqual(o.seller_sales_count,1)
        self.assertEqual(o.seller_reviews_count,2)
        self.assertEqual(o.seller_review_score_mean,3)
        self.assertEqual(set(d.index),{'o1'})
        for c in ['product_weight_g','product_id','customer_zip_code_prefix','order_purchase_timestamp']:
            self.assertNotIn(c,d)

    def test_nao_imputa_nem_descarta_ausencias(self):
        f=fontes_fixture();f['products'].loc[1,'product_weight_g']=np.nan
        f['sellers'].loc[0,'seller_zip_code_prefix']='SEM_CEP'
        f['orders'].loc[0,'order_delivered_customer_date']=None
        d,_=engenharia(construir_merge(f),{},estatisticas_vendedores(f))
        self.assertEqual(len(d),1)
        self.assertTrue(pd.isna(d.loc[0,'total_weight']))
        self.assertTrue(pd.isna(d.loc[0,'distance_customer_seller']))
        self.assertTrue(pd.isna(d.loc[0,'delay_status']))

    def test_delay_status_usa_exatamente_um_dia(self):
        f=fontes_fixture();f['orders'].loc[0,'order_delivered_customer_date']='2020-01-11'
        d,_=engenharia(construir_merge(f),{},estatisticas_vendedores(f))
        self.assertEqual(d.loc[0,'delay_in_days'],1)
        self.assertEqual(d.loc[0,'delay_status'],1)

    def test_diferencas_preservam_fracoes_sem_arredondamento_de_tratamento(self):
        f=fontes_fixture();f['orders'].loc[0,'order_approved_at']='2020-01-01 18:00:00'
        f['orders'].loc[0,'order_delivered_customer_date']='2020-01-10 12:00:00'
        d,_=engenharia(construir_merge(f),{},estatisticas_vendedores(f))
        self.assertEqual(d.loc[0,'approval_date_in_days'],.25)
        self.assertEqual(d.loc[0,'delay_in_days'],.5)
        self.assertEqual(d.loc[0,'delay_status'],0)

    def test_filtra_multivendedor_sem_perder_vendas_nas_estatisticas_globais(self):
        f=fontes_fixture()
        f['orders']=pd.concat([f['orders'],f['orders'].iloc[[0]].assign(order_id='o3')],ignore_index=True)
        novos=f['order_items'].iloc[:2].copy();novos['order_id']='o3';novos['seller_id']=['s1','s2']
        f['order_items']=pd.concat([f['order_items'],novos],ignore_index=True)
        m=construir_merge(f)
        self.assertEqual(m.order_id.tolist(),['o1'])
        stats=estatisticas_vendedores(f).set_index('seller_id')
        self.assertEqual(stats.loc['s1','seller_sales_count'],2)
        self.assertEqual(stats.loc['s1','seller_reviews_count'],2)


class TreinoTest(unittest.TestCase):
    def test_metricas_classificacao_com_dias_desconhecidos(self):
        m=avaliar([0,1,1],[.1,.9,.8],[-2,3,np.nan],[-1,5,7],.5,[1.])
        self.assertEqual(m['f1'],1.)
        self.assertEqual(m['mae_dias'],1.5)
        self.assertEqual(m['pedidos_avaliados_regressao'],2)
        self.assertEqual(m['dias_atraso_total'],3)
        self.assertEqual(m['fila_1_dias_ausentes'],1)
        vazio=avaliar([1],[.9],[np.nan],[np.nan],.5,[1.])
        self.assertTrue(np.isnan(vazio['mae_dias']))
        self.assertTrue(np.isnan(vazio['dias_atraso_total']))

    def test_ctgan_restaura_ausencia_dias_sem_inventar_duracao(self):
        class Gerador:
            def set_random_state(self,seed):pass
            def sample(self,n):return pd.DataFrame({'total_weight':[20.,30.],'delay_in_days':[0.,-2.],
                                                   '__dias_ausentes':['1','0']})
        d=amostrar({'gerador':Gerador(),'constantes':{},'atributos':['total_weight']},2,'teste',42)
        self.assertTrue(pd.isna(d.delay_in_days.iloc[0]))
        self.assertEqual(d.delay_status.tolist(),[1,0])

    def test_nenhuma_etapa_de_treino_roda_sem_revisao(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta=Path(tmp)/'nao_criar'
            with patch('src.ml.experimentos.preparar') as preparar, patch('src.ml.experimentos.treinar') as treino:
                with self.assertRaisesRegex(ValueError,'bloqueado'):
                    executar({'dados_validados':False},pasta)
                preparar.assert_not_called();treino.assert_not_called()
                self.assertFalse(pasta.exists())
        with self.assertRaises(ValueError):exigir_revisao({})

    def test_ausencias_exigem_tratamento_usuario(self):
        d=pd.DataFrame({'order_id':['a'],'delay_status':[0],'delay_in_days':[-2.], 'total_weight':[np.nan]})
        with self.assertRaisesRegex(ValueError,'nenhuma imputação'):validar_tabela(d,['total_weight'])

    def test_ctgan_nao_aceita_validacao_ou_nao_revisados(self):
        for p,ok in [('teste',True),('treino',False)]:
            with self.assertRaises(ValueError):
                ajustar(pd.DataFrame({'particao':[p],'origem_dado':['real_olist']}),{'dados_validados':ok},42,['total_weight'])

    def test_gerados_preservam_dias_negativos_e_derivam_classe(self):
        class Gerador:
            def set_random_state(self,seed):pass
            def sample(self,n):return pd.DataFrame({'total_weight':[20.,30.,40.],'delay_in_days':[-4.,.5,2.]})
        pacote={'gerador':Gerador(),'constantes':{},'atributos':['total_weight']}
        d=amostrar(pacote,3,'teste',42)
        self.assertEqual(d.delay_in_days.tolist(),[-4.,.5,2.])
        self.assertEqual(d.delay_status.tolist(),[0,0,1])

    def test_exportacao_em_todas_particoes_e_origens_com_fixture(self):
        base=pd.DataFrame({'order_id':[str(i) for i in range(20)],'total_weight':np.arange(20)+1.,
            'delay_status':[0,1]*10,'delay_in_days':[-2,3]*10,'origem_dado':['real_olist','sintetico_ctgan']*10})
        base['delay_status_source']='datas'
        base['delay_in_days']=base.delay_in_days.astype(float)
        base.loc[2,['delay_status','delay_in_days','delay_status_source']]=[1,np.nan,'pln']
        config={'dados_validados':True,'atributos':['total_weight'],'review_score_origem':'pedido_retrospectivo',
            'modelos':[{'nome':'dummy','tipo':'dummy'}],'cenarios':[{'nome':'misto'}],'limiar':.5}
        with tempfile.TemporaryDirectory() as tmp:
            pasta=Path(tmp);dados=pasta/'dados';(dados/'misto').mkdir(parents=True)
            config['saida_resultados']=str(pasta/'resultados_modelos')
            for p in ['treino','validacao','teste']:base.to_csv(dados/'misto'/f'{p}.csv',index=False)
            base[base.origem_dado.eq('real_olist')].to_csv(dados/'reais_teste.csv',index=False)
            prep={'atributos':['total_weight'],'pasta_dados':str(dados),
                'csv_sha256':{str(p.relative_to(dados)):sha256(p) for p in dados.rglob('*.csv')}}
            (pasta/'preparacao.json').write_text(json.dumps(prep),encoding='utf-8')
            treinar(config,pasta)
            m=pd.read_csv(pasta/'resultados_modelos'/f'{pasta.name}.csv')
            for p in ['treino','validacao','teste']:
                self.assertEqual(set(m.loc[m.particao.eq(p),'segmento']),{'todos','real_olist','sintetico_ctgan'})
            prev=pd.read_csv(pasta/'previsoes.csv')
            self.assertEqual(set(prev.delay_in_days.dropna()),{-2,3})
            total=m.loc[m.particao.eq('treino') & m.segmento.eq('todos')].iloc[0]
            self.assertEqual(total.pedidos_treino_regressao,19)
            self.assertEqual(total.pedidos_avaliados_regressao,19)
            self.assertEqual(total.rotulos_pln,1)
            self.assertEqual(total.tp+total.tn+total.fp+total.fn,20)
            self.assertEqual(len(list((pasta/'resultados_modelos').iterdir())),1)
            self.assertFalse((pasta/'resultados').exists())
            self.assertTrue({'tn','fp','fn','tp','melhor_classificador_validacao'}.issubset(m))
            self.assertTrue((pasta/'misto__dummy.joblib').is_file())

    def test_fluxo_completo_isolado_mantem_todos_cenarios_sem_treinar_gan_real(self):
        # Fixture técnica, não autorização para treinar os CSVs reais.
        with tempfile.TemporaryDirectory() as tmp:
            raiz=Path(tmp);entrada=raiz/'engineering.csv'
            linhas=[]
            for p,data in [('treino','2017-01-01'),('validacao','2018-02-01'),('teste','2018-06-01')]:
                for i in range(4):
                    linhas.append({'order_id':p+str(i),'order_approved_at':data,'total_weight':i+1.,
                        'delay_status':i%2,'delay_in_days':2 if i%2 else -8,
                        'order_delivered_customer_date_in_days':10,'approval_date_in_days':0})
            pd.DataFrame(linhas).to_csv(entrada,index=False)
            cenarios=[{'nome':modo,**{p:{'modo':modo,'n_reais':None,'n_sinteticos':0 if modo=='real' else 4}
                      for p in ['treino','validacao','teste']}} for modo in ['real','sintetico','misto']]
            config={'dados_validados':True,'entrada':str(entrada),'atributos':['total_weight'],
                'saida_resultados':str(raiz/'resultados_modelos'),
                'cortes':{'validacao':'2018-01-01','teste':'2018-05-01'},'cenarios':cenarios,
                'modelos':[{'nome':'dummy','tipo':'dummy'}],'limiar':.5}
            def amostra(pacote,n,parte,semente):
                return pd.DataFrame({'order_id':[f'S-{parte}-{i}' for i in range(n)],
                    'total_weight':np.arange(n)+semente,'delay_status':[i%2 for i in range(n)],
                    'delay_in_days':[2 if i%2 else -8 for i in range(n)],
                    'particao':parte,'origem_dado':'sintetico_ctgan','rotulo_observado':False})
            with patch('src.ml.experimentos.sinteticos.ajustar',return_value={'fixture':True}) as fit, \
                 patch('src.ml.experimentos.sinteticos.amostrar',side_effect=amostra):
                executar(config,raiz/'modelos',destino=raiz/'dados')
                self.assertTrue(fit.call_args.args[0].particao.eq('treino').all())
            self.assertEqual(json.loads((raiz/'modelos/manifesto.json').read_text(encoding='utf-8'))['status'],'concluida')
            for c in ['real','sintetico','misto']:
                for p in ['treino','validacao','teste']:
                    self.assertTrue((raiz/'dados'/c/f'{p}.csv').is_file())
            prev=pd.read_csv(raiz/'modelos/previsoes.csv')
            self.assertTrue(prev.previsao_delay_in_days.lt(0).all())


if __name__=='__main__':unittest.main()
