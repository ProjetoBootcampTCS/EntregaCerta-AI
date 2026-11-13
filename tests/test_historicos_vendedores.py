"""Fixtures artificiais só para verificar lógica temporal, não desempenho de ML."""
import unittest
from pathlib import Path

import joblib
from threadpoolctl import threadpool_limits

import numpy as np
import pandas as pd

from src.testar_historicos_vendedores import (
    COLUNAS_HISTORICO, PASTA, RAIZ, acumulados_anteriores, criar_historicos, disponibilidade_revisada,
)


class TestHistoricos(unittest.TestCase):
    def fontes(self):
        pedidos = pd.DataFrame({
            "order_id": ["antigo", "atual", "futuro"],
            "order_status": ["delivered"] * 3,
            "order_purchase_timestamp": ["2017-01-01", "2017-02-01", "2017-03-01"],
            "order_approved_at": ["2017-01-01", "2017-02-01", "2017-03-01"],
            "order_delivered_carrier_date": ["2017-01-03", "2017-02-02", "2017-03-02"],
            "order_delivered_customer_date": ["2017-01-12", "2017-02-10", "2017-03-10"],
            "order_estimated_delivery_date": ["2017-01-10", "2017-02-12", "2017-03-12"],
        })
        itens = pd.DataFrame({"order_id": ["antigo", "antigo", "atual", "futuro"], "seller_id": ["A"] * 4})
        consultas = pd.DataFrame({"order_id": ["atual"], "order_approved_at": pd.to_datetime(["2017-02-01"]), "prazo_prometido_dias": [11]})
        return pedidos, itens, consultas

    def test_prazo_inclui_todo_o_dia(self):
        b = pd.DataFrame({"atrasou": [0, 1], "order_estimated_delivery_date": pd.to_datetime(["2017-01-10"]*2),
                          "order_delivered_customer_date": pd.to_datetime(["2017-01-10 23:59:59", "2017-01-14 10:00:00"])})
        self.assertEqual(list(disponibilidade_revisada(b)), list(pd.to_datetime(["2017-01-10 23:59:59", "2017-01-11 00:00:00"])))

    def test_evento_no_mesmo_instante_nao_entra(self):
        e = pd.DataFrame({"seller_id": ["A"]*3, "quando": pd.to_datetime(["2017-01-01", "2017-02-01", "2017-02-02"]), "n": [1, 2, 8]})
        q = pd.DataFrame({"seller_id": ["A"], "order_approved_at": pd.to_datetime(["2017-02-01"])})
        soma, ultimo = acumulados_anteriores(e, q, "quando", ["n"])
        self.assertEqual(soma.n.iloc[0], 1)
        self.assertLess(ultimo.iloc[0], q.order_approved_at.iloc[0])

    def test_janela_30_dias_e_limites(self):
        e = pd.DataFrame({"seller_id": ["A"]*4, "quando": pd.to_datetime(["2017-01-01", "2017-01-02", "2017-01-31", "2017-02-01"]), "n": [100, 1, 2, 8]})
        q = pd.DataFrame({"seller_id": ["A"], "order_approved_at": pd.to_datetime(["2017-02-01"])})
        soma, _ = acumulados_anteriores(e, q, "quando", ["n"], 30)
        self.assertEqual(soma.n.iloc[0], 3)

    def test_sem_futuro_sem_proprio_alvo_sem_duplicar_itens(self):
        p, i, q = self.fontes()
        h, _ = criar_historicos(p, i, q)
        self.assertEqual(h.hist_observados_media.iloc[0], 1)
        self.assertEqual(h.hist_entrega_dias_media.iloc[0], 11)
        self.assertEqual(h.hist_postagem_dias_media.iloc[0], 2)
        alterado = p.copy()
        alterado.loc[alterado.order_id.ne("antigo"), "order_delivered_customer_date"] = "2017-05-10"
        alterado.loc[alterado.order_id.ne("antigo"), "order_estimated_delivery_date"] = "2017-05-11"
        h2, _ = criar_historicos(alterado, i, q)
        pd.testing.assert_frame_equal(h[COLUNAS_HISTORICO], h2[COLUNAS_HISTORICO])

    def test_vendedor_novo_nao_herda_media_futura(self):
        p, i, q = self.fontes()
        i.loc[i.order_id.eq("atual"), "seller_id"] = "NOVO"
        h, _ = criar_historicos(p, i, q)
        self.assertEqual(h.hist_sem_desfecho_fracao.iloc[0], 1)
        self.assertTrue(np.isnan(h.hist_entrega_dias_media.iloc[0]))
        self.assertEqual(h.hist_taxa_atraso_media.iloc[0], 1)  # prior passado: 1/1

    def test_varios_vendedores_uma_linha_por_pedido(self):
        p, i, q = self.fontes()
        i = pd.concat([i, pd.DataFrame({"order_id": ["atual"], "seller_id": ["NOVO"]})], ignore_index=True)
        h, _ = criar_historicos(p, i, q)
        self.assertEqual(len(h), 1)
        self.assertEqual(h.vendedores.iloc[0], 2)
        self.assertEqual(h.hist_sem_desfecho_fracao.iloc[0], .5)


@unittest.skipUnless((PASTA / "comparacao.joblib").exists(), "Executar experimento para conferir artefatos reais.")
class TestArtefatosReais(unittest.TestCase):
    def test_scores_persistidos_e_baseline_original(self):
        base = joblib.load(PASTA / "base_experimento.joblib")
        modelos = joblib.load(PASTA / "comparacao.joblib")["modelos"]
        val = base.loc[base.particao.eq("validacao") & ~base.recuperado]
        ampliada = base.loc[base.particao.eq("validacao")]
        with threadpool_limits(limits=4):
            for pacote in modelos.values():
                np.testing.assert_array_equal(pacote["ids_validacao"], val.order_id)
                for tabela, nome in [(val, "scores_validacao"), (ampliada, "scores_ampliada")]:
                    matriz = pacote["preprocessador"].transform(tabela[pacote["colunas"]]).astype(np.float32)
                    scores = pacote["modelo"].predict_proba(matriz)[:, 1]
                    np.testing.assert_allclose(scores, pacote[nome], atol=1e-12, rtol=0)
        anterior = RAIZ / "Modelos/experimento_ctgan/doses_20261111/comparacao.joblib"
        if anterior.exists():
            real = joblib.load(anterior)["modelos"]["Real_0_42"]
            np.testing.assert_allclose(modelos["original_atuais_Logistica"]["scores_validacao"], real["scores_validacao"], atol=1e-12, rtol=0)

    def test_rotulos_origem_e_eventos_reais(self):
        base = joblib.load(PASTA / "base_experimento.joblib")
        self.assertTrue(base.order_id.is_unique)
        for parte, corte in [("treino", "2018-01-01"), ("validacao", "2018-05-01")]:
            self.assertTrue(base.loc[base.particao.eq(parte), "rotulo_disponivel_em"].lt(pd.Timestamp(corte)).all())
        esperado = (base.order_delivered_customer_date.dt.normalize() > base.order_estimated_delivery_date.dt.normalize()).astype(int)
        np.testing.assert_array_equal(base.atrasou, esperado)
        self.assertTrue((base.ultimo_evento_historico.isna() | base.ultimo_evento_historico.lt(base.order_approved_at)).all())
        original = pd.read_csv(RAIZ / 'Dados/Brazilian Logistic/olist_orders_dataset.csv').set_index('order_id')
        consolidado = pd.read_csv(RAIZ / 'Dados/pedidos_consolidados_teste.csv').set_index('order_id')
        for c in ['order_status', 'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date',
                  'order_delivered_customer_date', 'order_estimated_delivery_date']:
            pd.testing.assert_series_equal(original[c].sort_index(), consolidado[c].sort_index())

    def test_amostra_real_contra_filtro_direto(self):
        # Cálculo independente sem usar a função de acumulados do experimento.
        pedidos = pd.read_csv(RAIZ / 'Dados/Brazilian Logistic/olist_orders_dataset.csv')
        for c in [x for x in pedidos if x.endswith(('_timestamp', '_at', '_date'))]:
            pedidos[c] = pd.to_datetime(pedidos[c], errors='coerce')
        itens = pd.read_csv(RAIZ / 'Dados/Brazilian Logistic/olist_order_items_dataset.csv', usecols=['order_id', 'seller_id']).drop_duplicates()
        r = pedidos.merge(itens, on='order_id', validate='one_to_many')
        r = r.loc[r.order_approved_at.ge(r.order_purchase_timestamp)]
        q = pd.read_csv(PASTA / 'auditoria_eventos_vendedores.csv', parse_dates=['order_approved_at']).sample(100, random_state=42)
        for row in q.itertuples():
            vendedor = r.loc[r.seller_id.eq(row.seller_id)]
            passado = vendedor.loc[vendedor.order_status.eq('delivered')
                & vendedor.order_delivered_customer_date.ge(vendedor.order_approved_at)
                & vendedor.order_estimated_delivery_date.dt.normalize().ge(vendedor.order_approved_at.dt.normalize())
                & vendedor.order_delivered_customer_date.lt(row.order_approved_at)]
            self.assertEqual(len(passado), row.observados)
            if len(passado):
                dias = (passado.order_delivered_customer_date - passado.order_approved_at).dt.total_seconds().mean() / 86400
                self.assertAlmostEqual(dias, row.entrega_dias, places=7)
            recentes = vendedor.loc[vendedor.order_approved_at.ge(row.order_approved_at-pd.Timedelta(days=30)) & vendedor.order_approved_at.lt(row.order_approved_at)]
            self.assertEqual(len(recentes), row.pedidos_30d)


if __name__ == "__main__":
    unittest.main()
