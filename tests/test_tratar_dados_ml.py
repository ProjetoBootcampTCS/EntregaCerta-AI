"""Testa preparacao temporal e preprocessamento apenas com registros reais."""

from pathlib import Path
import unittest

import joblib
import numpy as np
import pandas as pd

from src.tratar_dados_ml import CATEGORICAS, NUMERICAS, localizar_entrada, limpar_atributos


RAIZ = Path(__file__).resolve().parents[1]


class TestDadosML(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pacote = joblib.load(RAIZ / "Modelos" / "dados_ml.joblib")
        cls.csv = pd.read_csv(RAIZ / "Dados" / "pedidos_ml.csv")
        cls.fonte = pd.read_csv(localizar_entrada()).set_index("order_id")

    def test_particoes_temporais_e_disponibilidade_dos_rotulos(self):
        meta = self.pacote["metadados"]
        corte_v = pd.Timestamp(self.pacote["cortes"]["validacao"])
        corte_t = pd.Timestamp(self.pacote["cortes"]["teste"])
        self.assertTrue(meta["treino"]["order_approved_at"].lt(corte_v).all())
        self.assertTrue(meta["treino"]["rotulo_disponivel_em"].lt(corte_v).all())
        self.assertTrue(meta["validacao"]["order_approved_at"].ge(corte_v).all())
        self.assertTrue(meta["validacao"]["order_approved_at"].lt(corte_t).all())
        self.assertTrue(meta["validacao"]["rotulo_disponivel_em"].lt(corte_t).all())
        self.assertTrue(meta["teste"]["order_approved_at"].ge(corte_t).all())
        conjuntos = [set(meta[n]["order_id"]) for n in ["treino", "validacao", "teste"]]
        for i in range(3):
            for j in range(i+1, 3):
                self.assertFalse(conjuntos[i] & conjuntos[j])
        self.assertEqual(set.union(*conjuntos), set(self.csv["order_id"]))

    def test_medianas_aprendidas_so_no_treino(self):
        ids = self.pacote["metadados"]["treino"]["order_id"]
        treino, _ = limpar_atributos(self.fonte.loc[ids])
        imputer = self.pacote["preprocessador"].named_transformers_["numericas"].named_steps["imputador"]
        # Verificacao independente em grandezas que nao dependem da revisao geografica.
        for coluna in ["peso_total_g", "volume_total_cm3", "valor_itens", "valor_frete", "prazo_prometido_dias"]:
            self.assertAlmostEqual(imputer.statistics_[NUMERICAS.index(coluna)], treino[coluna].median())
        peso_medio = imputer.statistics_[NUMERICAS.index("peso_total_g")]
        faltantes = self.csv["faltante_peso_total_g"].eq(1)
        self.assertTrue(self.csv.loc[faltantes, "peso_total_g"].eq(peso_medio).all())
        conhecidos = ~faltantes
        np.testing.assert_allclose(self.csv.loc[conhecidos, "peso_total_g"],
                                   self.fonte.loc[self.csv.loc[conhecidos, "order_id"], "peso_total_g"])

    def test_encoder_nao_aprendeu_categorias_do_futuro(self):
        ids = self.pacote["metadados"]["treino"]["order_id"]
        treino, _ = limpar_atributos(self.fonte.loc[ids])
        encoder = self.pacote["preprocessador"].named_transformers_["categoricas"].named_steps["encoder"]
        for coluna, categorias in zip(CATEGORICAS, encoder.categories_):
            esperadas = set(treino[coluna].fillna("NAO_INFORMADO"))
            self.assertEqual(set(categorias), esperadas)

    def test_matrizes_alvos_e_csv_prontos(self):
        proibidas = {"order_id", "customer_unique_id", "order_status", "atrasou", "dias_atraso",
                     "rotulo_disponivel_em", "elegivel_modelagem", "order_delivered_customer_date",
                     "order_delivered_carrier_date", "tempo_transporte_dias", "tempo_entrega_dias"}
        self.assertFalse(proibidas & set(self.pacote["colunas_entrada"]))
        self.assertFalse(self.csv.isna().any().any())
        self.assertTrue(self.csv["order_id"].is_unique)
        for nome in ["treino", "validacao", "teste"]:
            x, y = self.pacote["X"][nome], self.pacote["y"][nome]
            self.assertEqual(x.shape, (len(y), len(self.pacote["nomes_atributos"])))
            self.assertTrue(np.isfinite(x).all())
            self.assertEqual(set(y), {0, 1})
            linhas = self.csv.loc[self.csv["particao"].eq(nome)]
            np.testing.assert_array_equal(y, linhas["atrasou"].to_numpy())
            np.testing.assert_array_equal(self.pacote["y_dias_atraso"][nome], linhas["dias_atraso"].to_numpy())

    def test_geolocalizacoes_externas_nao_conservam_distancias_invalidas(self):
        # Existem coordenadas de clientes reais do arquivo localizadas na Europa.
        impossiveis = (self.fonte["customer_latitude"].gt(6)
                       | self.fonte["customer_latitude"].lt(-34)
                       | self.fonte["customer_longitude"].gt(-28)
                       | self.fonte["customer_longitude"].lt(-74))
        ids = self.fonte.index[impossiveis].intersection(self.csv["order_id"])
        self.assertGreater(len(ids), 0)
        tratadas = self.csv.set_index("order_id").loc[ids, "distancia_max_vendedores_km"]
        anteriores = self.fonte.loc[ids, "distancia_max_vendedores_km"]
        self.assertTrue((tratadas - anteriores).abs().gt(1).all())


if __name__ == "__main__":
    unittest.main()
