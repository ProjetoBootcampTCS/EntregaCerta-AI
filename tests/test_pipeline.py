"""Contratos novos; somente fixtures para treinos de teste, nunca a base real."""
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from importlib import import_module
preparacao_mod = import_module("src.1_preparar_dados")
pln_mod = import_module("src.1_pln")
dados_mod = import_module("src.2_dados_treino")
treino_mod = import_module("src.2_treinar_modelos")
ctgan_mod = import_module("src.2_ctgan")
metricas_mod = import_module("src.3_avaliar_modelos")
construir_merge, engenharia = preparacao_mod.construir_merge, preparacao_mod.engenharia
estatisticas_vendedores = preparacao_mod.estatisticas_vendedores
atribuir_transportadoras = preparacao_mod.atribuir_transportadoras
confiabilidade_vendedor = preparacao_mod.confiabilidade_vendedor
preencher_atrasos_pln = preparacao_mod.preencher_atrasos_pln
comentarios, rotular_texto = pln_mod.comentarios, pln_mod.rotular_texto
avaliar = metricas_mod.avaliar
ATRIBUTOS, sha256 = dados_mod.ATRIBUTOS, dados_mod.sha256
exigir_revisao, validar_tabela, carregar = dados_mod.exigir_revisao, dados_mod.validar_tabela, dados_mod.carregar
executar, treinar = treino_mod.executar, treino_mod.treinar
montar_particao, assinaturas = treino_mod.montar_particao, treino_mod.assinaturas
ajustar, amostrar = ctgan_mod.ajustar, ctgan_mod.amostrar



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
    def test_cortes_temporais_nos_limites_sem_excluir_pedidos(self):
        base=pd.DataFrame({'order_id':list('abcdefg'),
            'order_approved_at':['2017-12-01','2017-12-31','2018-01-01','2018-04-30','2018-05-01','2017-12-01',None],
            'label_available_at':['2017-12-20','2018-01-01','2018-01-02','2018-05-01','2018-06-01','2018-06-01',None]})
        config={'cortes':{'validacao':'2018-01-01','teste':'2018-05-01'}}
        d,resumo=dados_mod.atribuir_particoes(base,config)
        self.assertEqual(len(d),len(base))
        self.assertEqual(d.particao.iloc[:6].tolist(),['treino','treino','validacao','validacao','teste','treino'])
        self.assertTrue(pd.isna(d.particao.iloc[6]))
        self.assertNotIn('elegivel_particao',d)
        self.assertEqual(resumo['por_particao'],{'treino':3,'validacao':2,'teste':1})
        with self.assertRaisesRegex(ValueError,'Corte de validação'):
            dados_mod.atribuir_particoes(base.iloc[:1],{'cortes':{'validacao':'2018-05-01','teste':'2018-05-01'}})

    def test_carregar_preserva_todos_pedidos_inclusive_pln_e_rotulos_posteriores(self):
        base=pd.DataFrame({'order_id':['a','b','c','d'], 'total_weight':[1.,2.,3.,4.],
            'delay_status':[0,1,1,0], 'delay_in_days':[-1.,np.nan,2.,-2.],
            'delay_status_source':['datas','pln','datas','datas'],
            'order_approved_at':['2017-12-01','2017-12-20','2018-03-01','2018-05-01'],
            'label_available_at':['2017-12-10','2018-01-02','2018-03-15','2018-05-20']})
        config={'dados_validados':True,'atributos':['total_weight'],
            'cortes':{'validacao':'2018-01-01','teste':'2018-05-01'}}
        with tempfile.TemporaryDirectory() as tmp:
            entrada=Path(tmp)/'dataset_ml.csv';config['entrada']=str(entrada)
            d,_=dados_mod.atribuir_particoes(base,config)
            d['elegivel_particao']=False  # Marcação antiga não interfere no novo fluxo.
            d.to_csv(entrada,index=False);antes=sha256(entrada)
            usados,_,resumo=carregar(config)
            self.assertEqual(usados.order_id.tolist(),['a','b','c','d'])
            self.assertEqual(resumo['linhas_descartadas'],0)
            self.assertTrue(pd.isna(usados.loc[1,'delay_in_days']))
            self.assertEqual(sha256(entrada),antes)
            d.loc[0,'order_approved_at']=None;d.to_csv(entrada,index=False)
            with self.assertRaisesRegex(ValueError,'order_approved_at ausente'):carregar(config)

    def test_atualizar_so_particoes_preserva_tratamento_e_cria_backup(self):
        base=pd.DataFrame({'order_id':['a','b'],'order_approved_at':['2017-12-01','2018-03-01'],
            'label_available_at':['2018-01-02','2018-03-10'],'valor_editado_pelo_usuario':[123.456,987.654]})
        with tempfile.TemporaryDirectory() as tmp:
            raiz=Path(tmp);saida=raiz/'Dados';saida.mkdir()
            config_treino=raiz/'treino.json';config_treino.write_text(json.dumps(
                {'cortes':{'validacao':'2018-01-01','teste':'2018-05-01'}}),encoding='utf-8')
            for nome in ['dataset_ml.csv','datasets_engineering.csv']:base.to_csv(saida/nome,index=False)
            preparacao_mod.atualizar_somente_particoes({'saida':str(saida),'configuracao_treino':str(config_treino)})
            for nome in ['dataset_ml.csv','datasets_engineering.csv']:
                depois=pd.read_csv(saida/nome)
                pd.testing.assert_frame_equal(base,depois[base.columns])
                self.assertEqual(depois.particao.tolist(),['treino','validacao'])
                self.assertNotIn('elegivel_particao',depois)
                self.assertEqual(len(list((saida/'experimentos').glob('antes_particoes_*/'+nome))),1)

    def test_tres_scripts_por_cli_em_pasta_isolada(self):
        # Exercita os arquivos numerados e os caminhos reais, sem usar dados do usuário.
        with tempfile.TemporaryDirectory() as tmp:
            raiz=Path(tmp);src=raiz/'src';src.mkdir();(src/'configuracoes').mkdir()
            for p in Path(treino_mod.__file__).parent.glob('[123]_*.py'):
                shutil.copy2(p,src/p.name)
            fontes=fontes_fixture()
            ordens=[];itens=[];pagamentos=[];reviews=[]
            for data in ['2017-01-01','2018-02-01','2018-06-01']:
                for i in range(4):
                    pedido=f'{data}_{i}';compra=pd.Timestamp(data)+pd.Timedelta(days=i)
                    o=fontes['orders'].iloc[[0]].copy()
                    o['order_id']=pedido;o['order_purchase_timestamp']=str(compra)
                    for c,dias in [('order_approved_at',1),('order_delivered_carrier_date',2),
                                   ('order_delivered_customer_date',12 if i%2 else 8),
                                   ('order_estimated_delivery_date',10)]:
                        o[c]=str(compra+pd.Timedelta(days=dias))
                    ordens.append(o)
                    itens.append(fontes['order_items'].assign(order_id=pedido,price=10.+i))
                    pagamentos.append(fontes['order_payments'].assign(order_id=pedido))
                    reviews.append(fontes['order_reviews'].assign(order_id=pedido,review_answer_timestamp=str(compra+pd.Timedelta(days=13))))
            fontes.update(orders=pd.concat(ordens),order_items=pd.concat(itens),
                          order_payments=pd.concat(pagamentos),order_reviews=pd.concat(reviews))
            originais=raiz/'Dados/originais';originais.mkdir(parents=True)
            for nome,d in fontes.items():d.to_csv(originais/f'olist_{nome}_dataset.csv',index=False)
            (src/'configuracoes/1_dados.json').write_text(json.dumps({'originais':'Dados/originais','saida':'Dados',
                'transportadoras':{'quantidade':3,'semente':42}}),encoding='utf-8')
            config={'dados_validados':True,'entrada':'Dados/dataset_ml.csv','atributos':ATRIBUTOS,
                'review_score_origem':'media_global_vendedor',
                'cortes':{'validacao':'2018-01-01','teste':'2018-05-01'},
                'modelos':[{'nome':'linear','tipo':'linear'},{'nome':'arvore','tipo':'arvore'}],
                'cenarios':[{'nome':'real',**{p:{'modo':'real','n_sinteticos':0} for p in treino_mod.PARTICOES}}]}
            (src/'configuracoes/2_treinamento.json').write_text(json.dumps(config),encoding='utf-8')
            externo=raiz/'fora';externo.mkdir()
            for arquivo,args in [('1_preparar_dados.py',[]),('2_treinar_modelos.py',['--nome','fixture']),
                                 ('3_avaliar_modelos.py',['--nome','fixture'])]:
                p=subprocess.run([sys.executable,'-B',str(src/arquivo),*args],cwd=externo,
                    capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            resultado=raiz/'Dados/resultados_modelos/fixture.csv'
            ml=pd.read_csv(raiz/'Dados/dataset_ml.csv')
            self.assertEqual(set(ml.particao),{'treino','validacao','teste'})
            self.assertNotIn('elegivel_particao',ml)
            m=pd.read_csv(resultado)
            self.assertEqual(set(m.modelo),{'linear','arvore'})
            self.assertEqual(set(m.particao),{'treino','validacao','teste','teste_real_referencia'})
            self.assertEqual(len(list(resultado.parent.iterdir())),1)
            manifesto=json.loads((raiz/'Modelos/comparacao_modelos/fixture/manifesto.json').read_text(encoding='utf-8'))
            self.assertEqual(len(manifesto['codigo_sha256']),7)
            self.assertEqual(len(list(src.rglob('*.py'))),7)

    def test_metricas_classificacao_com_dias_desconhecidos(self):
        m=avaliar([0,1,1],[.1,.9,.8],[-2,3,np.nan],[-1,5,7],.5,[1.])
        self.assertEqual(m['f1'],1.)
        self.assertEqual(m['mae_dias'],1.5)
        self.assertEqual(m['pedidos_avaliados_regressao'],2)
        self.assertEqual(m['pedidos_dias_ausentes'],1)
        self.assertEqual(m['mae_dias_atrasados'],2.)
        self.assertNotIn('f1_macro',m)
        self.assertNotIn('f1_micro',m)
        self.assertNotIn('roc_auc',m)
        self.assertFalse(any(c.startswith('fila_') for c in m))
        esperadas={'mae_dias','rmse_dias','r2_dias','mae_dias_atrasados','tn','fn','tp','fp',
                   'recall','precision','accuracy','limiar','f1'}
        informacoes={'pedidos','pedidos_dias_conhecidos','pedidos_dias_ausentes','pedidos_avaliados_regressao'}
        self.assertEqual(set(m),esperadas|informacoes)
        vazio=avaliar([1],[.9],[np.nan],[np.nan],.5,[1.])
        self.assertTrue(np.isnan(vazio['mae_dias']))
        self.assertTrue(np.isnan(vazio['mae_dias_atrasados']))

    def test_f1_da_classe_atrasado_e_limiar_otimo_na_validacao(self):
        y=np.array([0,0,0,1]);scores=np.array([.1,.2,.3,.25])
        m=avaliar(y,scores,[-1,-1,-1,2],[-1,-1,-1,2],.5)
        self.assertEqual(m['accuracy'],.75)
        self.assertEqual(m['f1'],0.)
        limiar=metricas_mod.escolher_limiar(y,scores)
        candidatos=np.r_[scores,np.nextafter(scores.max(),np.inf)]
        observado=avaliar(y,scores,[-1]*4,[-1]*4,limiar)['f1']
        esperado=max(avaliar(y,scores,[-1]*4,[-1]*4,t)['f1'] for t in candidatos)
        self.assertAlmostEqual(observado,esperado)
        self.assertAlmostEqual(observado,2/3)

    def test_selecao_usa_f1_positivo_da_validacao_e_nao_o_teste(self):
        base=pd.DataFrame({'cenario':['real']*4,'segmento':['todos']*4,
            'particao':['validacao','validacao','teste','teste'],'modelo':['a','b','a','b'],
            'tp':[4,8,10,0],'fp':[0,9,0,0],'fn':[6,2,0,10],'tn':[90,81,90,90],
            'precision':[1.,8/17,1.,0.],'mae_dias':[1.,2.,0.,50.]})
        resultado=metricas_mod.marcar_selecionados(base)
        self.assertEqual(set(resultado.loc[resultado.melhor_classificador_validacao,'modelo']),{'b'})
        self.assertEqual(set(resultado.loc[resultado.melhor_regressor_validacao,'modelo']),{'a'})
        self.assertAlmostEqual(resultado.loc[1,'f1'],16/27)

    def test_resultados_antigos_recalculam_f1_sem_renomear_macro_ou_micro(self):
        antigo=pd.DataFrame({'tp':[4,0],'fp':[0,0],'fn':[6,0],'tn':[90,10],
                             'f1_macro':[.77,1.],'f1_micro':[.94,1.]})
        atual=metricas_mod.metricas_f1(antigo)
        self.assertAlmostEqual(atual.loc[0,'f1'],4/7)
        self.assertEqual(atual.loc[1,'f1'],0.)
        self.assertNotIn('f1_macro',atual)
        self.assertNotIn('f1_micro',atual)
        self.assertIn('f1_macro',antigo)

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
            with patch.object(treino_mod, 'preparar') as preparar, patch.object(treino_mod, 'treinar') as treino:
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
            with patch.object(ctgan_mod, 'ajustar',return_value={'fixture':True}) as fit, \
                 patch.object(ctgan_mod, 'amostrar',side_effect=amostra):
                executar(config,raiz/'modelos',destino=raiz/'dados')
                self.assertTrue(fit.call_args.args[0].particao.eq('treino').all())
            self.assertEqual(json.loads((raiz/'modelos/manifesto.json').read_text(encoding='utf-8'))['status'],'concluida')
            for c in ['real','sintetico','misto']:
                for p in ['treino','validacao','teste']:
                    self.assertTrue((raiz/'dados'/c/f'{p}.csv').is_file())
            prev=pd.read_csv(raiz/'modelos/previsoes.csv')
            self.assertTrue(prev.previsao_delay_in_days.lt(0).all())


if __name__=='__main__':unittest.main()
