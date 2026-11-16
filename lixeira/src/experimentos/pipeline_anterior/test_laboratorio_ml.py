"""Contratos do laboratório: tempo, isolamento, métricas e exportação."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
import joblib

from src.experimentos.pipeline_anterior.avaliacoes import adicionar_avaliacoes
from src.ml.metricas import avaliar, escolher_limiar
from src.experimentos.pipeline_anterior.comparador import montar_particao, validar_config, treinar, assinaturas
from src.experimentos.pipeline_anterior.tratar_dados_ml import sha256
from src.experimentos.pipeline_anterior.preparar_dados import COLUNAS_PREVISAO
from src.experimentos.pipeline_anterior.geracao import ajustar


class LaboratorioTest(unittest.TestCase):
    def test_implementacoes_organizadas_sem_atalhos_na_raiz(self):
        for antigo, novo in [('preparar_dados', 'dados.preparar_dados'),
                             ('tratar_dados_ml', 'ml.tratar_dados_ml'), ('banco', 'postgresql.banco')]:
            modulo = importlib.import_module('src.' + novo)
            raiz = Path(__file__).resolve().parents[1]
            self.assertEqual(Path(modulo.__file__).resolve(), raiz / 'src' / Path(*novo.split('.')).with_suffix('.py'))
            self.assertFalse((raiz / 'src' / (antigo + '.py')).exists())

    def test_notas_nao_consultam_futuro_mesmo_instante_ou_proprio_pedido(self):
        pedidos = pd.DataFrame({'order_id': ['a', 'b', 'c', 'd'],
            'order_approved_at': pd.to_datetime(['2020-01-01', '2020-01-03', '2020-01-04', '2020-01-05'])})
        itens = pd.DataFrame({'order_id': ['a', 'a', 'b', 'c', 'd'], 'seller_id': ['s']*5})
        reviews = pd.DataFrame({'order_id': ['a', 'b', 'c'], 'review_id': ['r1', 'r2', 'r3'],
            'review_score': [1, 5, 2], 'review_answer_timestamp': ['2020-01-02', '2020-01-04', '2020-01-20']})
        h = adicionar_avaliacoes(pedidos, reviews, itens, pedidos).set_index('order_id')
        self.assertEqual(h.loc['a', 'hist_avaliacoes_vendedor_media'], 0)
        self.assertEqual(h.loc['c', 'hist_avaliacoes_vendedor_media'], 1)
        self.assertAlmostEqual(h.loc['c', 'hist_nota_vendedor_media'], 7/3)
        self.assertEqual(h.loc['d', 'hist_avaliacoes_vendedor_media'], 2)
        # Mudar uma avaliação futura só pode mudar metadados retrospectivos.
        reviews.loc[2, 'review_score'] = 5
        outro = adicionar_avaliacoes(pedidos, reviews, itens, pedidos).set_index('order_id')
        pd.testing.assert_frame_equal(h.filter(like='hist_'), outro.filter(like='hist_'))

    def test_metricas_e_fila_conhecidas(self):
        m = avaliar([0, 1, 1, 0], [.1, .9, .4, .8], [0, 4, 2, 0], [0, 3, 1, 1], .5, [.5])
        self.assertEqual((m['tn'], m['fp'], m['fn'], m['tp']), (1, 1, 1, 1))
        self.assertEqual(m['f1'], .5)
        self.assertEqual(m['mae_dias'], .75)
        self.assertEqual(m['fila_0.5_dias_capturados'], 4)
        self.assertEqual(escolher_limiar([0, 1], [.2, .8]), .8)

    def test_composicao_e_limite_sem_reposicao(self):
        reais = pd.DataFrame({'order_id': ['r1', 'r2'], 'origem_dado': ['real_olist']*2})
        sint = pd.DataFrame({'order_id': ['s1'], 'origem_dado': ['sintetico_ctgan']})
        d = montar_particao(reais, sint, {'modo': 'misto', 'n_reais': 1, 'n_sinteticos': 1}, 7)
        self.assertEqual(set(d.origem_dado), {'real_olist', 'sintetico_ctgan'})
        with self.assertRaises(ValueError):
            montar_particao(reais, sint, {'modo': 'real', 'n_reais': 3}, 7)

    def test_config_recusa_caminho_com_traversal(self):
        config = {'modelos': [{'nome': '../fora', 'tipo': 'dummy'}], 'cenarios': []}
        with self.assertRaises(ValueError):
            validar_config(config)

    def test_assinatura_detecta_copia_com_tipos_numericos_diferentes(self):
        inteiro = pd.DataFrame({'quantidade_itens': [1], 'atrasou': [1], 'dias_atraso': [2]})
        decimal = inteiro.astype(float)
        self.assertEqual(assinaturas(inteiro, ['quantidade_itens']).iloc[0],
                         assinaturas(decimal, ['quantidade_itens']).iloc[0])

    def test_gerador_recusa_validacao_teste_e_sinteticos(self):
        for p, origem in [('validacao', 'real_olist'), ('teste', 'real_olist'), ('treino', 'sintetico_ctgan')]:
            with self.subTest(particao=p, origem=origem), self.assertRaises(ValueError):
                ajustar(pd.DataFrame({'particao': [p], 'origem_dado': [origem]}), {}, 42)

    def test_treino_exporta_previsoes_recarregaveis_e_nao_usa_nota_propria(self):
        base = pd.DataFrame({c: [1.0]*20 for c in COLUNAS_PREVISAO})
        for c in ['customer_state', 'uf_origem', 'categoria_principal', 'tipo_pagamento_principal']:
            base[c] = 'X'
        base['atrasou'] = [0, 1]*10
        base['dias_atraso'] = [0, 3]*10
        base['nota_proprio_pedido_eda'] = base.atrasou * 5
        base['origem_dado'] = 'real_olist'
        config = {'modelos': [{'nome': 'dummy', 'tipo': 'dummy'}], 'cenarios': [{'nome': 'real'}], 'limiar': .5}
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            dados = pasta / 'dados/real'
            dados.mkdir(parents=True)
            for p in ('treino', 'validacao', 'teste'):
                base['order_id'] = [p + str(i) for i in range(len(base))]
                base.to_csv(dados / f'{p}.csv', index=False)
            base.to_csv(pasta / 'dados/reais_teste.csv', index=False)
            preparo = {'atributos': COLUNAS_PREVISAO, 'pasta_dados': str(pasta/'dados'),
                'csv_sha256': {str(p.relative_to(pasta/'dados')): sha256(p) for p in (pasta/'dados').rglob('*.csv')}}
            (pasta/'preparacao.json').write_text(json.dumps(preparo), encoding='utf-8')
            treinar(config, pasta)
            local = pasta/'resultados/real/dummy'
            pacote = joblib.load(local/'modelo.joblib')
            self.assertNotIn('nota_proprio_pedido_eda', pacote['atributos'])
            prev = pd.read_csv(local/'previsoes_teste.csv')
            np.testing.assert_allclose(pacote['regressor'].predict(base[COLUNAS_PREVISAO]), prev.previsao_dias_atraso)
            metricas = pd.read_csv(pasta/'resultados/metricas.csv')
            self.assertIn('teste_real_referencia', set(metricas.particao))
            self.assertTrue((pasta/'resultados/matrizes_confusao.csv').is_file())


if __name__ == '__main__':
    unittest.main()
