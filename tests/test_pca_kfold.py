"""PCA dentro dos folds, exclusão do teste e exportação da validação cruzada."""
from importlib import import_module
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

treino = import_module("src.2_treinar_modelos")

ATRIBUTOS = ["price", "freight_value", "customer_state"]


def base_fixture():
    base = pd.DataFrame({
        "order_id": [f"o{i}" for i in range(24)],
        "price": np.arange(24, dtype=float) + 1,
        "freight_value": (np.arange(24, dtype=float) + 1) * 2,
        "customer_state": [f"uf{i}" for i in range(24)],
        "delay_status": [0, 1] * 12,
        "delay_in_days": [-2., 3.] * 12,
        "delay_status_source": "datas",
        "particao": "treino", "origem_dado": "real_olist",
        "order_approved_at": "2017-01-01",
    })
    base.loc[1, ["delay_in_days", "delay_status_source"]] = [np.nan, "pln"]
    return base


def config_fixture():
    return {"dados_validados": True, "atributos": ATRIBUTOS, "semente": 42, "threads": 1,
            "pca": {"ativado": True, "variancia": .95},
            "kfold": {"ativado": True, "n_splits": 3, "limiar": .4},
            "modelos": [{"nome": "linear", "tipo": "linear"}],
            "cortes": {"validacao": "2018-01-01", "teste": "2018-05-01"},
            "cenarios": [{"nome": "real", **{p: {"modo": "real", "n_sinteticos": 0} for p in treino.PARTICOES}}]}


class PcaKfoldTest(unittest.TestCase):
    def test_encoder_scaler_pca_so_enxergam_treino_de_cada_fold(self):
        base = base_fixture()
        original_fit = Pipeline.fit
        ajustes = []

        def fit(pipeline, x, y, **kwargs):
            resultado = original_fit(pipeline, x, y, **kwargs)
            ajustes.append((pipeline, x.copy(), y.copy()))
            return resultado

        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            with patch.object(Pipeline, "fit", fit), patch.object(treino, "escolher_limiar", side_effect=AssertionError("limiar não deve usar o fold avaliado")):
                met, resumo = treino.validar_cruzado(config_fixture(), pasta, base, ATRIBUTOS)
            folds = pd.read_csv(pasta / "kfold_particoes.csv")
            self.assertEqual(set(folds.order_id), set(base.order_id))
            self.assertFalse(folds.order_id.duplicated().any())
            self.assertEqual(folds.fold_validacao.value_counts().to_dict(), {1: 8, 2: 8, 3: 8})
            self.assertEqual(len(ajustes), 6)
            for fold in range(1, 4):
                fora = set(folds.loc[folds.fold_validacao.eq(fold), "order_id"])
                for pipeline, x, y in ajustes[(fold - 1) * 2:fold * 2]:
                    self.assertTrue(set(base.loc[x.index, "order_id"]).isdisjoint(fora))
                    self.assertFalse(y.isna().any())
                    prep = pipeline.named_steps["preprocessador"]
                    self.assertEqual(set(prep.named_transformers_["cat"].categories_[0]), set(x.customer_state))
                    np.testing.assert_allclose(prep.named_transformers_["num"].mean_, x[["price", "freight_value"]].mean())
                    pca = pipeline.named_steps["pca"]
                    self.assertEqual(pca.n_samples_, len(x))
                    self.assertGreaterEqual(pca.explained_variance_ratio_.sum(), .95)
                    self.assertLess(pca.n_components_, pca.n_features_in_)
            self.assertTrue(met.limiar.eq(.4).all())
            self.assertEqual(met.pedidos.sum(), len(base))
            self.assertEqual(met.pedidos_avaliados_regressao.sum(), 23)
            self.assertAlmostEqual(resumo.loc[0, "f1_media"], met.f1.mean())
            self.assertAlmostEqual(resumo.loc[0, "f1_desvio"], met.f1.std())
            self.assertNotIn("f1_macro", met)
            self.assertNotIn("f1_micro", met)
            self.assertTrue((pasta / "kfold_metricas.csv").is_file())
            self.assertTrue((pasta / "kfold_resumo.csv").is_file())

    def test_rejeita_sinteticos_particoes_externas_e_classes_insuficientes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for base in [base_fixture().assign(particao="teste"),
                         base_fixture().assign(origem_dado="sintetico_ctgan"), base_fixture().iloc[:4]]:
                with self.subTest(), self.assertRaises(ValueError):
                    treino.validar_cruzado(config_fixture(), Path(tmp), base, ATRIBUTOS)

    def test_configuracoes_invalidas_e_pca_opcional(self):
        for campo, valores in [("pca", {"ativado": True, "variancia": 1}),
                               ("pca", {"ativado": True, "variancia": True}),
                               ("kfold", {"ativado": True, "n_splits": 1}),
                               ("kfold", {"ativado": True, "n_splits": 3, "limiar": 2})]:
            with self.subTest(), self.assertRaises(ValueError):
                treino.validar_config({**config_fixture(), campo: valores})
        cls, _ = treino.criar_modelos({"tipo": "linear"}, 42)
        self.assertNotIn("pca", treino.pipeline_modelo(ATRIBUTOS, cls, {}).named_steps)

    def test_fluxo_completo_salva_pca_e_kfold_sem_usar_validacao_ou_teste(self):
        base = base_fixture()
        partes = [base]
        for particao, data in [("validacao", "2018-02-01"), ("teste", "2018-06-01")]:
            partes.append(base.assign(order_id=base.order_id + "_" + particao,
                                     particao=particao, order_approved_at=data))
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            entrada = raiz / "entrada.csv"
            pd.concat(partes, ignore_index=True).to_csv(entrada, index=False)
            config = {**config_fixture(), "entrada": str(entrada), "saida_resultados": str(raiz / "resultados")}
            pasta = raiz / "modelos"
            treino.executar(config, pasta, destino=raiz / "dados")
            self.assertEqual(json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))["status"], "concluida")
            folds = pd.read_csv(pasta / "kfold_particoes.csv")
            self.assertEqual(set(folds.order_id), set(base.order_id))
            pacote = joblib.load(pasta / "real__linear.joblib")
            for chave in ["classificador", "regressor"]:
                self.assertIn("pca", pacote[chave].named_steps)
                self.assertEqual(len(pacote[chave].predict(base[ATRIBUTOS])), len(base))
            met = pd.read_csv(raiz / "resultados/modelos.csv")
            self.assertIn("f1", met)
            self.assertNotIn("f1_macro", met)
            self.assertNotIn("f1_micro", met)
            self.assertTrue(met.criterio_selecao.eq("f1_validacao").all())
            self.assertTrue(met.pca_ativado.all())
            self.assertTrue(met.pca_variancia_classificacao.ge(.95).all())
            self.assertTrue(met.pca_componentes_regressao.notna().all())


if __name__ == "__main__":
    unittest.main()
