"""Fixtures artificiais apenas para testar filtros/HTTP, nunca desempenho de ML."""

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from src import api
from src.pedidos_web import montar_lote, filtrar_lote


class PedidosWebTest(unittest.TestCase):
    def setUp(self):
        self.pedidos = pd.DataFrame({
            "order_id": ["a", "b", "c", "d"],
            "customer_state": ["SP", "RJ", "SP", None],
            "uf_origem": ["SP", "SP", "PR", None],
            "categoria_principal": ["livros", "moveis", "livros", None],
            "order_approved_at": ["2018-01-01 10:00", "2018-01-02 23:59", "2018-01-03 01:00", None],
            "valor_pago": [10., 40., 30., None],
            "atrasou": [1, 0, 0, 1],  # Nunca deve ser exposto pela consulta.
        })
        self.previsoes = pd.DataFrame({
            "order_id": ["a", "b", "c", "d"],
            "score_atraso": [.8, .8, .4, .1], "prioridade": [1, 0, 0, 0],
        })
        self.lote = montar_lote(self.pedidos, self.previsoes)

    def test_filtros_combinados_e_prioridade_preservada(self):
        r = filtrar_lote(self.lote, uf="SP", categoria="livros", score_min=.3, score_max=.6)
        self.assertEqual([p["order_id"] for p in r["pedidos"]], ["c"])
        self.assertEqual(r["filtrados_na_fila"], 0)
        self.assertEqual(r["na_fila"], 1)
        self.assertEqual(r["total"], 4)
        self.assertNotIn("atrasou", r["pedidos"][0])

    def test_datas_inclusivas_e_nulos(self):
        r = filtrar_lote(self.lote, inicio=date(2018, 1, 2), fim=date(2018, 1, 2))
        self.assertEqual([p["order_id"] for p in r["pedidos"]], ["b"])
        nulo = filtrar_lote(self.lote, busca="d")["pedidos"][0]
        self.assertIsNone(nulo["order_approved_at"])
        self.assertIsNone(nulo["valor_pago"])

    def test_ordem_paginacao_e_busca_literal(self):
        r = filtrar_lote(self.lote, tamanho=2)
        self.assertEqual([p["order_id"] for p in r["pedidos"]], ["a", "b"])
        self.assertEqual(filtrar_lote(self.lote, tamanho=2, pagina=99)["pagina"], 2)
        self.assertEqual(filtrar_lote(self.lote, busca=".")["filtrados"], 0)
        self.assertEqual(filtrar_lote(self.lote, busca="A")["filtrados"], 1)
        self.assertEqual(filtrar_lote(self.lote, prioridade="0")["filtrados"], 3)
        self.assertEqual(filtrar_lote(self.lote, ordem="valor-desc")["pedidos"][0]["order_id"], "b")

    def test_chaves_incompativeis_rejeitadas(self):
        with self.assertRaises(ValueError):
            montar_lote(self.pedidos, self.previsoes.iloc[:3])
        with self.assertRaises(ValueError):
            montar_lote(pd.concat([self.pedidos, self.pedidos.iloc[:1]]), self.previsoes)

    def test_http_e_validacao(self):
        # A autorização real é testada separadamente em test_acesso_web.
        api.app.dependency_overrides[api.politica_acesso] = lambda: None
        self.addCleanup(api.app.dependency_overrides.clear)
        with patch.object(api, "obter_lote_pedidos", return_value=(self.lote, "2026-11-12T12:00:00+00:00", .25)), TestClient(api.app) as client:
            for rota in ["/", "/dashboard", "/pedidos", "/static/pedidos.js", "/static/pedidos.css"]:
                self.assertEqual(client.get(rota).status_code, 200, rota)
            r = client.get("/api/pedidos?tamanho=25&uf=sp&prioridade=0")
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["filtrados"], 1)
            for query in ["tamanho=30", "pagina=0", "score_min=0.9&score_max=0.1", "score_min=nan", "inicio=2018-02-01&fim=2018-01-01", "inicio=nao-data", "ordem=invalida", "prioridade=2"]:
                self.assertEqual(client.get("/api/pedidos?" + query).status_code, 422, query)


if __name__ == "__main__":
    unittest.main()
