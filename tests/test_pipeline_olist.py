"""Casos técnicos pequenos: não representam medições de qualidade do gerador."""
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from src.contratos_olist import (CLEAN_COLUMNS, CTGAN_FEATURES, HISTORICOS, ML_DATASET_COLUMNS,
    ML_FEATURES, adicionar_razoes, montar_ml, validar_limpo, validar_ml)
from src.dados_vendedor_unico import historicos_asof, mapear_vendedor_unico
from src.ml_vendedor_unico import (avaliar_comparacao, criar_preprocessador, preparar_features_inferencia,
                                   prever_pedido_enriquecido, treinar_comparacao)
from src.preparar_dados import adicionar_tempos_e_alvos, coordenadas_por_cep, resumir_itens
from src.pipeline_olist import executar_eda
from src.simulacao_atrasos import SimuladorAtrasos
from src.sintese_olist import (ajustar_ctgan, atribuir_metadados, codificar_treino, decodificar_candidatos,
                              filtrar_candidatos, gerar_pedidos, hash_tabela, quotas_estratos)
from src.tratar_dados_ml import selecionar_coorte, separar_por_tempo


def base_tecnica(n=30):
    df = pd.DataFrame({
        "order_id": [f"real_{i}" for i in range(n)], "seller_id": [f"seller_{i % 3}" for i in range(n)],
        "particao": "treino", "order_approved_at": pd.date_range("2017-01-01", periods=n),
        "customer_state": "RJ", "seller_state": "SP", "categoria_principal": "livros",
        "quantidade_itens": 1, "quantidade_produtos": 1, "quantidade_categorias": 1,
        "valor_itens": np.linspace(10, 100, n), "valor_frete": np.linspace(1, 10, n),
        "peso_total_g": np.linspace(100, 1000, n), "volume_total_cm3": np.linspace(1000, 10000, n),
        "distancia_vendedor_cliente_km": np.linspace(10, 1000, n), "prazo_prometido_dias": np.linspace(5, 30, n),
        HISTORICOS[0]: 4., HISTORICOS[1]: 10, HISTORICOS[2]: .2,
        "atrasou": np.arange(n) % 4 == 0, "origem_dado": "real",
    })
    df.loc[0, HISTORICOS] = [np.nan, 0, np.nan]
    return adicionar_razoes(df)[CLEAN_COLUMNS]


def config_simulacao():
    return json.loads((Path(__file__).resolve().parents[1] / "config/olist_ctgan.json").read_text())["simulation"]


class TestFiltroHistorico(unittest.TestCase):
    def test_filtra_bruto_sem_perder_multiplos_itens(self):
        itens = pd.DataFrame({"order_id": ["a", "a", "b", "b", "c", "d", "d"],
                              "order_item_id": [1, 2, 1, 2, 1, 1, 2],
                              "seller_id": ["s", "s", "s", "t", None, "s", None]})
        mapa, n = mapear_vendedor_unico(itens)
        self.assertEqual(mapa.to_dict("records"), [{"order_id": "a", "seller_id": "s"}])
        self.assertEqual(n.to_dict(), {"a": 1, "b": 2, "c": 0, "d": 1})
        with self.assertRaises(ValueError):
            mapear_vendedor_unico(pd.concat([itens, itens.iloc[:1]]))

    def test_historia_estrita_deduplicada_sem_proprio_pedido(self):
        pedidos = pd.DataFrame({"order_id": ["a", "b", "c", "d", "outro"],
            "order_approved_at": pd.to_datetime(["2017-01-01", "2017-01-03", "2017-01-04", "2017-01-05", "2017-01-01"])})
        mapa = pedidos[["order_id"]].assign(seller_id=["s", "s", "s", "s", "t"])
        reviews = pd.DataFrame({
            "review_id": ["r1", "r1", "r2", "r3", "r4", "rt"],
            "order_id": ["a", "a", "b", "c", "d", "outro"],
            "review_score": [3, 3, 4, 1, 1, 1],
            "review_creation_date": ["2017-01-02", "2017-01-02", "2017-01-03", "2017-01-01", "2018-01-01", "2017-01-01"],
            "review_answer_timestamp": ["2017-01-03", "2017-01-03", "2017-01-04", "2017-01-02", "2018-01-02", "2017-01-02"],
        })
        alvos = pedidos.merge(mapa, on="order_id")
        resultado, report = historicos_asof(alvos, pedidos, mapa, reviews)
        self.assertEqual(resultado[HISTORICOS[1]].tolist(), [0, 0, 1, 2, 0])
        self.assertTrue(resultado.loc[:1, HISTORICOS[0]].isna().all())
        self.assertEqual(resultado.loc[2, HISTORICOS[0]], 3.)
        self.assertEqual(resultado.loc[2, HISTORICOS[2]], 1.)
        self.assertEqual(resultado.loc[3, HISTORICOS[0]], 3.5)
        self.assertEqual(resultado.loc[3, HISTORICOS[2]], .5)
        self.assertEqual(report["duplicatas_removidas"], 1)
        self.assertEqual(report["datas_ou_notas_invalidas"], 1)

    def test_review_id_ambiguo_e_timestamp_ausente_nao_entram(self):
        pedidos = pd.DataFrame({"order_id": ["a", "b", "c"], "order_approved_at": pd.to_datetime(["2017-01-01", "2017-01-02", "2017-02-01"])})
        mapa = pedidos[["order_id"]].assign(seller_id="s")
        reviews = pd.DataFrame({"review_id": ["r", "r", "n"], "order_id": ["a", "b", "a"], "review_score": [3, 3, 1],
                                "review_creation_date": "2017-01-03", "review_answer_timestamp": ["2017-01-04", "2017-01-04", None]})
        resultado, report = historicos_asof(pedidos.merge(mapa), pedidos, mapa, reviews)
        self.assertTrue(resultado[HISTORICOS[1]].eq(0).all())
        self.assertEqual(report["identidades_ambiguas_excluidas"], 1)

    def test_geografia_e_somas_de_um_seller(self):
        geo = coordenadas_por_cep(pd.DataFrame({"geolocation_zip_code_prefix": pd.Series(["00001", "00002"], dtype="string"),
                                              "geolocation_lat": [0., 0.], "geolocation_lng": [0., 1.]}))
        itens = pd.DataFrame({"order_id": ["a", "a"], "order_item_id": [1, 2], "product_id": ["p", "p"],
                              "seller_id": ["s", "s"], "price": [10., 10.], "freight_value": [2., 2.]})
        produtos = pd.DataFrame({"product_id": ["p"], "product_category_name": ["livros"], "product_weight_g": [10.],
                                 "product_length_cm": [2.], "product_height_cm": [3.], "product_width_cm": [4.]})
        vendedores = pd.DataFrame({"seller_id": ["s"], "seller_state": ["SP"], "seller_zip_code_prefix": ["00002"]})
        pedidos = pd.DataFrame({"order_id": ["a"], "customer_latitude": [0.], "customer_longitude": [0.]})
        r = resumir_itens(itens, produtos, vendedores, geo, pedidos).iloc[0]
        self.assertEqual((r.quantidade_itens, r.quantidade_produtos, r.quantidade_vendedores), (2, 1, 1))
        self.assertEqual((r.valor_itens, r.valor_frete, r.peso_total_g, r.volume_total_cm3), (20., 4., 20., 48.))
        self.assertAlmostEqual(r.distancia_max_vendedores_km, 111.19508, places=4)
        self.assertEqual(r.distancia_max_vendedores_km, r.distancia_media_vendedores_km)

    def test_rotulo_timestamp_e_defaults_legados(self):
        df = pd.DataFrame({"order_id": ["a", "b"], "order_status": ["delivered", "shipped"], "quantidade_itens": [1, 1],
            "order_purchase_timestamp": pd.to_datetime(["2017-01-01"] * 2), "order_approved_at": pd.to_datetime(["2017-01-01"] * 2),
            "order_delivered_carrier_date": pd.to_datetime(["2017-01-02"] * 2),
            "order_delivered_customer_date": pd.to_datetime(["2017-01-03 12:00:00", None]),
            "order_estimated_delivery_date": pd.to_datetime(["2017-01-03"] * 2)})
        antigo = adicionar_tempos_e_alvos(df)
        novo = adicionar_tempos_e_alvos(df, comparar_timestamp=True)
        self.assertEqual(antigo.atrasou.iloc[0], 0)
        self.assertEqual(novo.atrasou.iloc[0], 1)
        self.assertTrue(pd.isna(novo.atrasou.iloc[1]))
        self.assertEqual(len(selecionar_coorte(novo, [], comparar_timestamp=True)), 1)

    def test_purga_rotulos_futuros_preservada(self):
        df = pd.DataFrame({"order_approved_at": pd.to_datetime(["2017-12-31", "2018-01-02", "2018-05-02"]),
                           "rotulo_disponivel_em": pd.to_datetime(["2018-01-02", "2018-01-10", "2018-05-10"])})
        resultado, purgas = separar_por_tempo(df)
        self.assertEqual(resultado.particao.tolist(), ["validacao", "teste"])
        self.assertEqual(purgas["rotulo_futuro_treino"], 1)


class TestContratosSintese(unittest.TestCase):
    def test_contratos_e_mes_so_no_ml(self):
        real = base_tecnica()
        validar_limpo(real)
        ml = montar_ml(real)
        self.assertEqual((len(CLEAN_COLUMNS), len(CTGAN_FEATURES), len(ML_DATASET_COLUMNS), len(ML_FEATURES)), (23, 15, 23, 18))
        self.assertEqual(list(ml.columns), ML_DATASET_COLUMNS)
        self.assertTrue(ml.mes_aprovacao.eq(1).all())
        self.assertNotIn("mes_aprovacao", real)
        self.assertNotIn("order_approved_at", ml)
        self.assertFalse(set(["seller_id", "order_id", "atrasou", "particao", "origem_dado", "p_atraso_simulada"]) & set(ML_FEATURES))
        with self.assertRaises(ValueError):
            validar_limpo(real.assign(faltante_peso=0))
        with self.assertRaises(ValueError):
            validar_limpo(real[CLEAN_COLUMNS[::-1]])

    def test_razoes_zero_e_restricoes(self):
        real = base_tecnica()
        real.loc[1, "valor_itens"] = 0
        real = adicionar_razoes(real)
        self.assertTrue(pd.isna(real.loc[1, "proporcao_frete_valor"]))
        validar_limpo(real)
        real.loc[2, "preco_medio_item"] = 1000
        with self.assertRaises(ValueError):
            validar_limpo(real)

    def test_ctgan_apenas_15_colunas_sem_metadados_alvo(self):
        real = base_tecnica()
        b, logs, discretas = codificar_treino(real)
        self.assertEqual(list(b), CTGAN_FEATURES)
        self.assertEqual(b.loc[0, HISTORICOS[0]], 0)
        self.assertEqual(b.loc[0, HISTORICOS[2]], -1)
        restaurado = decodificar_candidatos(b, {"logs": logs})
        self.assertTrue(restaurado.loc[0, [HISTORICOS[0], HISTORICOS[2]]].isna().all())
        self.assertNotIn("preco_medio_item", b)
        for p in ["validacao", "teste"]:
            with self.assertRaises(ValueError):
                codificar_treino(real.assign(particao=p))
        with self.assertRaises(ValueError):
            codificar_treino(real.assign(origem_dado="sintetico_ctgan"))

    def test_ctgan_fit_recebe_contrato_exato(self):
        with patch("ctgan.CTGAN") as classe:
            pacote, b = ajustar_ctgan(base_tecnica(), {"seed": 7, "epochs": 1, "batch_size": 10})
        passado = classe.return_value.fit.call_args.args[0]
        self.assertEqual(list(passado), CTGAN_FEATURES)
        self.assertEqual(len(passado), 30)
        self.assertEqual(pacote["hash_treino"], hash_tabela(base_tecnica()))

    def test_rejeita_dominios_e_outliers_sem_clipping(self):
        real = base_tecnica()
        candidato = real[CTGAN_FEATURES].iloc[1:2].copy()
        for c, valor in [("quantidade_produtos", 2), ("valor_frete", -1), ("peso_total_g", np.inf),
                         ("seller_state", "XX"), (HISTORICOS[0], 6), (HISTORICOS[2], 1.2),
                         (HISTORICOS[1], -1), ("distancia_vendedor_cliente_km", 1001)]:
            teste = candidato.copy()
            teste[c] = valor
            self.assertTrue(filtrar_candidatos(teste, real).empty, c)

    def test_ids_sinteticos_perfis_datas_e_colisoes(self):
        real = base_tecnica()
        candidatos = real[CTGAN_FEATURES].copy()
        sint, report = atribuir_metadados(candidatos, real, "teste", 7)
        self.assertEqual(report["perfis_compativeis"], len(sint))
        sint["atrasou"] = 0
        sint = sint[CLEAN_COLUMNS]
        validar_limpo(sint, sintetico=True)
        self.assertTrue(set(sint.order_approved_at) <= set(real.order_approved_at))
        self.assertFalse(set(sint.seller_id) & set(real.seller_id))
        sint.loc[1, "seller_id"] = sint.loc[0, "seller_id"]
        with self.assertRaises(ValueError):
            validar_limpo(sint, sintetico=True)

    def test_quotas_preservam_simples_sem_inventar_percentual(self):
        real = base_tecnica(10)
        real.loc[7:8, "quantidade_itens"] = 2
        real.loc[9, "quantidade_itens"] = 5
        self.assertEqual(quotas_estratos(real, 20), {1: 14, 2: 4, 3: 2})

    def test_geracao_reprodutivel_recusa_copias_e_reporta_falha(self):
        real = base_tecnica()
        b, logs, _ = codificar_treino(real)
        gerador = Mock()
        # Componente financeira nova, mas dentro do suporte do treino.
        b["valor_itens"] = np.log1p(50.123)
        gerador.sample.return_value = b
        pacote = {"treino": real, "modelo": gerador, "logs": logs, "hash_treino": hash_tabela(real)}
        config = {"seed": 7, "max_resample_attempts": 2, "min_batch": 30}
        sint, report = gerar_pedidos(pacote, 10, "teste", config)
        self.assertEqual(len(sint), 10)
        self.assertEqual(report["aceitos"], 10)
        gerador.sample.return_value = codificar_treino(real)[0].assign(valor_frete=-10.)
        with self.assertRaisesRegex(RuntimeError, "Amostragem insuficiente") as erro:
            gerar_pedidos(pacote, 10, "teste", config)
        self.assertGreater(erro.exception.relatorio["invalidos"], 0)

    def test_copia_real_nao_escapa_por_ruido_de_log(self):
        real = base_tecnica()
        b, logs, _ = codificar_treino(real)
        gerador = Mock()
        gerador.sample.return_value = b
        pacote = {"treino": real, "modelo": gerador, "logs": logs, "hash_treino": hash_tabela(real)}
        with self.assertRaisesRegex(RuntimeError, "Amostragem insuficiente") as erro:
            gerar_pedidos(pacote, 2, "teste", {"seed": 7, "max_resample_attempts": 1})
        self.assertGreater(erro.exception.relatorio["copias_ou_duplicatas"], 0)


class TestSimulacaoML(unittest.TestCase):
    def test_eda_apenas_le_dados_ja_limpos(self):
        real = base_tecnica()
        anterior = real.copy(deep=True)
        with tempfile.TemporaryDirectory() as pasta:
            executar_eda(real, None, Path(pasta))
            self.assertTrue((Path(pasta) / "itens.csv").exists())
        pd.testing.assert_frame_equal(real, anterior)

    def test_simulacao_seed_taxa_direcoes_e_real_intacto(self):
        real = base_tecnica()
        copia = real.copy(deep=True)
        config = config_simulacao()
        sim = SimuladorAtrasos(config).fit(real)
        com = real.iloc[1:2].copy()
        referencia = sim.score(com)[0]
        for coluna, delta, sentido in [("distancia_vendedor_cliente_km", 20, 1), ("peso_total_g", 20, 1),
                                      ("volume_total_cm3", 20, 1), ("valor_itens", 20, 1),
                                      ("valor_frete", 2, -1), ("prazo_prometido_dias", 2, -1),
                                      (HISTORICOS[0], .5, -1), (HISTORICOS[2], .2, 1)]:
            alterado = com.copy()
            alterado[coluna] += delta
            self.assertGreater(sentido * (sim.score(alterado)[0] - referencia), 0, coluna)
        candidato, _ = atribuir_metadados(real[CTGAN_FEATURES], real, "teste", 2)
        a, p, report = sim.simular(candidato)
        b, q, _ = sim.simular(candidato)
        pd.testing.assert_frame_equal(a, b)
        pd.testing.assert_frame_equal(p, q)
        self.assertAlmostEqual(report["probabilidade_media"], config["target_delay_rate"], places=12)
        self.assertNotIn("p_atraso_simulada", a)
        pd.testing.assert_frame_equal(real, copia)
        with self.assertRaises(ValueError):
            sim.simular(real)
        config["exact_count"] = True
        a, _, _ = SimuladorAtrasos(config).fit(real).simular(candidato)
        self.assertEqual(a.atrasou.sum(), round(len(a) * config["target_delay_rate"]))

    def test_ml_isolamento_e_selecao_sem_teste(self):
        real = base_tecnica(60)
        real.loc[30:44, "particao"] = "validacao"
        real.loc[45:, "particao"] = "teste"
        treino = real.iloc[:30]
        candidatos, _ = atribuir_metadados(treino[CTGAN_FEATURES], treino, "teste", 2)
        sintetico, _, _ = SimuladorAtrasos(config_simulacao()).fit(treino).simular(candidatos)
        df = montar_ml(real, sintetico)
        config = {"seed": 7, "synthetic_to_real_ratios": [.5, 1.], "synthetic_weights": [.5, 1.]}
        pacote = treinar_comparacao(df, config)
        alterado = df.copy()
        alterado.loc[alterado.particao.eq("teste"), "atrasou"] = 1 - alterado.loc[alterado.particao.eq("teste"), "atrasou"]
        outro = treinar_comparacao(alterado, config)
        pd.testing.assert_frame_equal(pacote["validacao"], outro["validacao"])
        self.assertEqual(pacote["selecionado_aumentado"], outro["selecionado_aumentado"])
        self.assertEqual(len(avaliar_comparacao(df, pacote)), 2)
        with self.assertRaises(ValueError):
            avaliar_comparacao(alterado, pacote)
        sintetico.loc[0, "particao"] = "teste"
        with self.assertRaises(ValueError):
            montar_ml(real, sintetico)

    def test_preprocessador_nao_cria_flags_e_usa_so_treino(self):
        df = montar_ml(base_tecnica())
        pre = criar_preprocessador().fit(df[ML_FEATURES])
        self.assertFalse(any("missingindicator" in c for c in pre.get_feature_names_out()))
        imputer = pre.named_transformers_["numericas"].named_steps["imputador"]
        colunas = pre.transformers_[0][2]
        self.assertEqual(imputer.statistics_[colunas.index("valor_itens")], df.valor_itens.median())
        futuro = df.copy()
        futuro["customer_state"] = "AM"
        pre.transform(futuro[ML_FEATURES])
        self.assertEqual(pre.named_transformers_["categoricas"].categories_[0].tolist(), ["RJ"])

    def test_inferencia_nao_exige_alvo_entrega_ou_review_propria(self):
        real = base_tecnica()
        pedidos = real.drop(columns=["atrasou", *HISTORICOS])
        historicos = real[["order_id", "order_approved_at"]]
        mapa = real[["order_id", "seller_id"]]
        reviews = pd.DataFrame(columns=["review_id", "order_id", "review_score", "review_creation_date", "review_answer_timestamp"])
        preparado = preparar_features_inferencia(pedidos, historicos, mapa, reviews, {})
        self.assertTrue(preparado[HISTORICOS[1]].eq(0).all())
        pipe = Mock()
        pipe.predict_proba.return_value = np.tile([.7, .3], (len(real), 1))
        modelo = {"pipeline": pipe, "features": ML_FEATURES, "limiar": .5}
        resultado = prever_pedido_enriquecido(preparado, modelo)
        self.assertTrue(resultado.previsao_atraso.eq(0).all())
        self.assertEqual(list(pipe.predict_proba.call_args.args[0]), ML_FEATURES)


if __name__ == "__main__":
    unittest.main()
