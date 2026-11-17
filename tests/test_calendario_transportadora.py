"""Calendário logístico, atualização dos CSVs e representação no treino."""
import json
from importlib import import_module
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

preparacao = import_module("src.1_preparar_dados")
dados = import_module("src.2_dados_treino")
treino = import_module("src.2_treinar_modelos")
ctgan = import_module("src.2_ctgan")

DIFERENCA, SEMANA, FERIADO, FERIADOS, UTEIS, PROXIMO = dados.ATRIBUTOS_CALENDARIO


def calcular(despachos, estimativas):
    return preparacao.adicionar_features_calendario(pd.DataFrame({
        "order_id": [f"o{i}" for i in range(len(despachos))],
        "order_delivered_carrier_date": despachos,
        "order_estimated_delivery_date": estimativas,
    }))


class CalendarioTest(unittest.TestCase):
    def test_sexta_domingo_e_feriado_na_segunda_com_fracoes(self):
        d = calcular(["2017-04-07", "2017-04-28 12:00:00"], ["2017-04-09", "2017-05-02"])
        self.assertEqual(d[DIFERENCA].tolist(), [-2., -3.5])
        self.assertEqual(d[SEMANA].tolist(), ["sexta-feira", "sexta-feira"])
        self.assertEqual(d[UTEIS].tolist(), [0, 1])
        self.assertEqual(d[FERIADOS].tolist(), [0, 1])
        self.assertEqual(d[PROXIMO].tolist(), [3, 4])
        self.assertEqual(json.loads(d.loc[1, preparacao.FERIADOS_DETALHES]),
                         [{"data": "2017-05-01", "nome": "Dia do Trabalhador"}])

    def test_feriado_movel_no_despacho_e_exclusao_da_extremidade_inicial(self):
        d = calcular(["2017-04-14", "2018-03-29"], ["2017-04-17", "2018-03-30"])
        self.assertEqual(d[FERIADO].tolist(), [1, 0])
        self.assertEqual(d[FERIADOS].tolist(), [0, 1])
        self.assertEqual(d[UTEIS].tolist(), [1, 0])
        self.assertEqual(d[PROXIMO].tolist(), [3, 4])

    def test_feriado_no_domingo_nao_desconta_dia_util_duas_vezes(self):
        d = calcular(["2024-04-19"], ["2024-04-22"])
        self.assertEqual(d.loc[0, FERIADOS], 1)
        self.assertEqual(d.loc[0, UTEIS], 1)
        self.assertEqual(d.loc[0, PROXIMO], 3)

    def test_historico_20_novembro_sem_aplicar_lei_retroativamente(self):
        d = calcular(["2018-11-19", "2024-11-19"], ["2018-11-21", "2024-11-21"])
        self.assertEqual(d[FERIADOS].tolist(), [0, 1])
        self.assertEqual(d[UTEIS].tolist(), [2, 1])

    def test_sem_pontos_facultativos_ou_feriados_locais(self):
        d = calcular(["2018-02-12", "2018-05-30", "2018-01-24"],
                     ["2018-02-14", "2018-06-01", "2018-01-26"])
        self.assertEqual(d[FERIADOS].tolist(), [0, 0, 0])
        self.assertEqual(d[UTEIS].tolist(), [2, 2, 2])

    def test_virada_de_ano_e_proximo_dia_util_no_ano_seguinte(self):
        d = calcular(["2017-12-29", "2021-12-31"], ["2018-01-02", "2021-12-31"])
        self.assertEqual(d[FERIADOS].tolist(), [1, 0])
        self.assertEqual(d[UTEIS].tolist(), [1, 0])
        self.assertEqual(d[PROXIMO].tolist(), [4, 3])

    def test_prazo_vencido_e_mesmo_dia_tem_zero_dias_restantes(self):
        d = calcular(["2017-05-02", "2017-05-01", "2017-05-01 12:00:00"],
                     ["2017-05-01", "2017-05-01", "2017-05-01"])
        self.assertEqual(d[DIFERENCA].tolist(), [1., 0., .5])
        self.assertEqual(d[FERIADOS].tolist(), [0, 0, 0])
        self.assertEqual(d[UTEIS].tolist(), [0, 0, 0])
        self.assertEqual(d[preparacao.FERIADOS_DETALHES].tolist(), ["[]"] * 3)

    def test_ausencias_invalidos_e_tabela_vazia_sem_imputacao(self):
        d = calcular([None, "invalida", "2017-05-02"], ["2017-05-05", None, None])
        self.assertTrue(d.loc[:1, dados.ATRIBUTOS_CALENDARIO].isna().all().all())
        self.assertTrue(d.loc[2, [DIFERENCA, FERIADOS, UTEIS, preparacao.FERIADOS_DETALHES]].isna().all())
        self.assertEqual(d.loc[2, SEMANA], "terça-feira")
        self.assertEqual(d.loc[2, FERIADO], 0)
        self.assertEqual(d.loc[2, PROXIMO], 1)
        self.assertTrue(calcular([], []).empty)
        self.assertTrue(calcular([None], [None])[dados.ATRIBUTOS_CALENDARIO].isna().all().all())

    def test_dias_em_portugues_e_independencia_da_entrega_ao_cliente(self):
        datas = pd.date_range("2017-04-03", periods=7).astype(str).tolist()
        d = calcular(datas, ["2017-04-10"] * 7)
        self.assertEqual(d[SEMANA].tolist(), preparacao.DIAS_SEMANA)
        alterado = preparacao.adicionar_features_calendario(d.assign(order_delivered_customer_date="2099-12-31"))
        pd.testing.assert_frame_equal(d[dados.ATRIBUTOS_CALENDARIO], alterado[dados.ATRIBUTOS_CALENDARIO])

    def test_liga_datas_por_id_e_preserva_ordem_indice_e_tratamento(self):
        origem = calcular(["2017-04-03", "2017-04-07"], ["2017-04-10"] * 2)
        base = pd.DataFrame({"order_id": ["o1", "o0"], "valor_editado": [123.45, 987.65]}, index=[8, 3])
        d = preparacao.adicionar_features_calendario(base, origem)
        pd.testing.assert_frame_equal(base, d[base.columns])
        self.assertEqual(d[SEMANA].tolist(), ["sexta-feira", "segunda-feira"])
        with self.assertRaisesRegex(ValueError, "único"):
            preparacao.adicionar_features_calendario(base, pd.concat([origem, origem]))
        with self.assertRaisesRegex(ValueError, "correspondência"):
            preparacao.adicionar_features_calendario(base, origem.iloc[:1])

    def test_atualizacao_incremental_preserva_csvs_backup_e_idempotencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            fonte = raiz / "originais"
            fonte.mkdir()
            origem = calcular(["2017-04-03", None], ["2017-04-10"] * 2)
            origem[preparacao.DATAS_TRANSPORTADORA].to_csv(fonte / "olist_orders_dataset.csv", index=False)
            bases = {
                "datasets_engineering.csv": pd.DataFrame({"order_id": ["o1", "o0"], "editado": [10., 20.]}),
                "dataset_ml.csv": pd.DataFrame({"order_id": ["o0"], "editado": [999.]}),
            }
            for nome, base in bases.items():
                base.to_csv(raiz / nome, index=False)
            registro = raiz / "datasets_preparacao.json"
            registro.write_text(json.dumps({"pln": {"preservar": True}}), encoding="utf-8")
            config = {"saida": str(raiz), "originais": str(fonte)}
            preparacao.atualizar_somente_calendario(config)
            antes = {}
            for nome, base in bases.items():
                atualizada = pd.read_csv(raiz / nome)
                pd.testing.assert_frame_equal(base, atualizada[base.columns])
                self.assertTrue(set(dados.ATRIBUTOS_CALENDARIO).issubset(atualizada))
                backups = list((raiz / "experimentos").glob("antes_preparacao_*/" + nome))
                self.assertEqual(len(backups), 1)
                pd.testing.assert_frame_equal(base, pd.read_csv(backups[0]))
                antes[nome] = atualizada
            self.assertNotIn(preparacao.FERIADOS_DETALHES, antes["dataset_ml.csv"])
            meta = json.loads(registro.read_text(encoding="utf-8"))
            self.assertEqual(meta["pln"], {"preservar": True})
            self.assertEqual(meta["calendario_transportadora"]["sem_data_transportadora"], 1)
            self.assertEqual(meta["sha256"]["dataset_ml.csv"], dados.sha256(raiz / "dataset_ml.csv"))
            to_csv = pd.DataFrame.to_csv
            def falhar_no_segundo_csv(tabela, destino, **kwargs):
                if Path(destino).name == "dataset_ml.csv.novo":
                    raise OSError("falha de gravação simulada")
                return to_csv(tabela, destino, **kwargs)
            hashes = {nome: dados.sha256(raiz / nome) for nome in bases}
            with patch.object(pd.DataFrame, "to_csv", falhar_no_segundo_csv):
                with self.assertRaisesRegex(OSError, "simulada"):
                    preparacao.atualizar_somente_calendario(config)
            self.assertEqual(hashes, {nome: dados.sha256(raiz / nome) for nome in bases})
            preparacao.atualizar_somente_calendario(config)
            for nome, base in antes.items():
                pd.testing.assert_frame_equal(base, pd.read_csv(raiz / nome))

    def test_filtro_de_treino_e_explicito_e_nao_altera_fonte(self):
        base = calcular(["2017-04-03", None], ["2017-04-10"] * 2)
        base = base.assign(order_approved_at="2017-04-01", delay_status=[0, 1], delay_in_days=[-1., 2.])
        with tempfile.TemporaryDirectory() as tmp:
            entrada = Path(tmp) / "dataset_ml.csv"
            base.to_csv(entrada, index=False)
            config = {"entrada": str(entrada), "dados_validados": True, "atributos": dados.ATRIBUTOS_CALENDARIO,
                      "cortes": {"validacao": "2018-01-01", "teste": "2018-05-01"}}
            assinatura = dados.sha256(entrada)
            with self.assertRaisesRegex(ValueError, "nenhuma imputação"):
                dados.carregar(config)
            usadas, _, resumo = dados.carregar({**config, "excluir_sem_data_transportadora": True})
            self.assertEqual(usadas.order_id.tolist(), ["o0"])
            self.assertEqual(resumo["linhas_descartadas"], 1)
            self.assertEqual(resumo["pedidos_csv"], 2)
            self.assertEqual(resumo["pedidos_elegiveis"], 1)
            self.assertEqual(dados.sha256(entrada), assinatura)
            # Mesmo com a opção ligada, um estudo sem calendário mantém todos.
            base.assign(price=10).to_csv(entrada, index=False)
            todas, _, resumo = dados.carregar({**config, "atributos": ["price"], "excluir_sem_data_transportadora": True})
            self.assertEqual(len(todas), 2)
            self.assertEqual(resumo["linhas_descartadas"], 0)

    def test_one_hot_ajustado_so_no_treino_aceita_dia_desconhecido(self):
        p = treino.preprocessador([DIFERENCA, SEMANA])
        x = pd.DataFrame({DIFERENCA: [-2., -5.], SEMANA: ["segunda-feira", "sexta-feira"]})
        matriz = p.fit_transform(x)
        self.assertEqual(matriz.shape, (2, 3))
        self.assertEqual(p.named_transformers_["cat"].categories_[0].tolist(), ["segunda-feira", "sexta-feira"])
        nova = p.transform(pd.DataFrame({DIFERENCA: [-3.], SEMANA: ["domingo"]}))
        self.assertTrue(np.isfinite(nova).all())
        np.testing.assert_array_equal(nova[0, 1:], [0., 0.])

    def test_ctgan_recebe_semana_e_contagens_como_discretas(self):
        class Gerador:
            def __init__(self, **kwargs): pass
            def set_random_state(self, seed): pass
            def fit(self, tabela, discrete_columns):
                self.tabela = tabela
                self.discretas = discrete_columns
            def sample(self, n):
                return self.tabela.iloc[:n].copy().reset_index(drop=True)

        base = calcular(["2017-04-03", "2017-04-28"], ["2017-04-10", "2017-05-02"])
        base = base.assign(particao="treino", origem_dado="real_olist", delay_status=[0, 1], delay_in_days=[-1., 2.])
        with patch.dict("sys.modules", {"ctgan": SimpleNamespace(CTGAN=Gerador)}):
            pacote = ctgan.ajustar(base, {"dados_validados": True}, 42, dados.ATRIBUTOS_CALENDARIO)
        self.assertTrue({SEMANA, *dados.CONTAGENS_CALENDARIO}.issubset(pacote["colunas_discretas"]))
        geradas = ctgan.amostrar(pacote, 2, "teste", 42)
        self.assertEqual(geradas[SEMANA].tolist(), base[SEMANA].tolist())
        self.assertEqual(geradas[FERIADOS].tolist(), [0, 1])


if __name__ == "__main__":
    unittest.main()
