"""Verificacoes independentes do CSV gerado, usando somente os registros reais."""

from collections import Counter
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from statistics import mean, median
import unittest

import pandas as pd


RAIZ = Path(__file__).resolve().parents[1]
ORIGINAIS = RAIZ / "Dados" / "Brazilian Logistic"
DATAS = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
         "order_delivered_customer_date", "order_estimated_delivery_date"]


class TestConsolidacaoReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        entrada = RAIZ / "Dados" / "pedidos_consolidados.csv"
        if not entrada.is_file():
            entrada = RAIZ / "Dados" / "pedidos_consolidados_teste.csv"
        cls.base = pd.read_csv(entrada, parse_dates=DATAS)
        cls.pedidos = pd.read_csv(ORIGINAIS / "olist_orders_dataset.csv", parse_dates=DATAS)
        cls.itens = pd.read_csv(ORIGINAIS / "olist_order_items_dataset.csv")
        cls.pagamentos = pd.read_csv(ORIGINAIS / "olist_order_payments_dataset.csv")
        cls.por_id = cls.base.set_index("order_id")

    def test_pedidos_e_itens_preservados(self):
        self.assertTrue(self.base["order_id"].is_unique)
        self.assertEqual(set(self.base["order_id"]), set(self.pedidos["order_id"]))
        contagens = Counter(self.itens["order_id"])
        for pedido in self.base.itertuples():
            if pedido.order_id in contagens:
                self.assertEqual(pedido.quantidade_itens, contagens[pedido.order_id])
            else:
                self.assertTrue(pd.isna(pedido.quantidade_itens))

    def test_dinheiro_sem_multiplicacao(self):
        # Reconciliacao com Decimal, independente das somas NumPy/Pandas.
        for coluna_saida, tabela, coluna_original in [
            ("valor_itens", self.itens, "price"),
            ("valor_frete", self.itens, "freight_value"),
            ("valor_pago", self.pagamentos, "payment_value"),
        ]:
            total_original = sum(Decimal(str(x)) for x in tabela[coluna_original])
            total_consolidado = sum(Decimal(str(x)) for x in self.base[coluna_saida].dropna())
            self.assertLess(abs(total_original - total_consolidado), Decimal("0.005"))

    def test_datas_originais_e_rotulos(self):
        originais = self.pedidos.set_index("order_id").sort_index()
        saida = self.por_id.sort_index()
        for coluna in DATAS:
            pd.testing.assert_series_equal(originais[coluna], saida[coluna])
        sem_desfecho = (~originais["order_status"].eq("delivered")
                        | originais["order_delivered_customer_date"].isna()
                        | originais["order_estimated_delivery_date"].isna())
        self.assertTrue(saida.loc[sem_desfecho, ["atrasou", "dias_atraso"]].isna().all().all())
        for pedido in self.base.loc[self.base["rotulo_disponivel"].eq(1)].itertuples():
            # date() evita confundir horas no mesmo dia com atraso.
            dias = (pedido.order_delivered_customer_date.date()
                    - pedido.order_estimated_delivery_date.date()).days
            self.assertEqual(pedido.atrasou, int(dias > 0))
            self.assertEqual(pedido.dias_atraso, max(0, dias))
        antes = self.base["order_delivered_customer_date"] < self.base["order_approved_at"]
        self.assertTrue(self.base.loc[antes, "elegivel_modelagem"].eq(0).all())

    def test_peso_parcial_nao_vira_peso_total(self):
        produtos = pd.read_csv(ORIGINAIS / "olist_products_dataset.csv")
        itens = self.itens.merge(produtos[["product_id", "product_weight_g"]],
                                 on="product_id", validate="many_to_one")
        invalidos = itens["product_weight_g"].isna() | itens["product_weight_g"].le(0)
        pedidos_com_peso_ausente = itens.loc[invalidos, "order_id"].unique()
        self.assertTrue(self.por_id.loc[pedidos_com_peso_ausente, "peso_total_g"].isna().all())

    def test_distancia_por_vendedor_sem_ponderacao_acidental_por_itens(self):
        contagem = self.itens.groupby(["order_id", "seller_id"]).size()
        desiguais = contagem.groupby(level=0).agg(["min", "max"])
        candidatos = desiguais.index[desiguais["max"].gt(desiguais["min"])]
        disponiveis = self.por_id.loc[self.por_id.index.isin(candidatos)]
        disponiveis = disponiveis.loc[disponiveis["vendedores_sem_distancia"].eq(0)
                                     & disponiveis["distancia_max_vendedores_km"].gt(
                                         disponiveis["distancia_media_vendedores_km"] + 1)]
        self.assertFalse(disponiveis.empty, "Faltou caso real adequado para verificar a ponderacao.")
        order_id = disponiveis.index[0]
        cliente_id = self.por_id.loc[order_id, "customer_id"]
        clientes = pd.read_csv(ORIGINAIS / "olist_customers_dataset.csv",
                              dtype={"customer_zip_code_prefix": "string"})
        vendedores = pd.read_csv(ORIGINAIS / "olist_sellers_dataset.csv",
                                dtype={"seller_zip_code_prefix": "string"}).set_index("seller_id")
        cep_cliente = clientes.loc[clientes["customer_id"].eq(cliente_id), "customer_zip_code_prefix"].iloc[0].zfill(5)
        ids = self.itens.loc[self.itens["order_id"].eq(order_id), "seller_id"].unique()
        ceps_vendedores = vendedores.loc[ids, "seller_zip_code_prefix"].str.zfill(5)
        geo = pd.read_csv(ORIGINAIS / "olist_geolocation_dataset.csv",
                         dtype={"geolocation_zip_code_prefix": "string"})
        geo["geolocation_zip_code_prefix"] = geo["geolocation_zip_code_prefix"].str.zfill(5)
        pares = {}
        for cep in {cep_cliente, *ceps_vendedores}:
            pontos = geo.loc[geo["geolocation_zip_code_prefix"].eq(cep)]
            pares[cep] = (radians(median(pontos["geolocation_lat"])),
                          radians(median(pontos["geolocation_lng"])))
        lat1, lon1 = pares[cep_cliente]
        distancias = []
        for cep in ceps_vendedores:
            lat2, lon2 = pares[cep]
            a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
            distancias.append(6371.0088 * 2 * asin(sqrt(a)))
        self.assertAlmostEqual(self.por_id.loc[order_id, "distancia_media_vendedores_km"], mean(distancias), delta=0.001)
        self.assertAlmostEqual(self.por_id.loc[order_id, "distancia_max_vendedores_km"], max(distancias), delta=0.001)
        self.assertEqual(self.por_id.loc[order_id, "quantidade_vendedores"], len(ids))


if __name__ == "__main__":
    unittest.main()
