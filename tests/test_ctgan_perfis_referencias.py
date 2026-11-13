"""Testes técnicos do cenário inteiramente artificial."""
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from src.ctgan_perfis_referencias import (validar_config, populacao_artificial,
    ajustar_perfil, finalizar, validar_candidatos, montar_ml_sintetico, amostrar_perfil,
    treinar_somente_sinteticos, avaliar_real)
from src.contratos_olist import CLEAN_COLUMNS, CTGAN_FEATURES, ML_FEATURES, HISTORICOS
from src.sintese_olist import hash_tabela


class TestPerfisReferencias(unittest.TestCase):
    def setUp(self):
        self.c = json.loads((Path(__file__).resolve().parents[1] / 'config/ctgan_perfis_referencias.json').read_text())
        self.c['seed_population_per_profile'] = 300

    def sinteticos(self):
        partes, nomes = [], []
        for i, perfil in enumerate(self.c['profiles']):
            partes.append(populacao_artificial(self.c, perfil, 42 + i))
            nomes.extend([perfil['name']] * len(partes[-1]))
        return finalizar(pd.concat(partes, ignore_index=True), nomes, self.c)

    def test_config_probabilidades_explicitas_ordenadas(self):
        validar_config(self.c)
        self.c['profiles'][0]['delay_probability'] = .9
        with self.assertRaises(ValueError):
            validar_config(self.c)

    def test_populacao_sem_ler_olist_e_reprodutivel(self):
        with patch('pandas.read_csv', side_effect=AssertionError('Não ler Olist')), patch('pandas.read_parquet', side_effect=AssertionError('Não ler Olist')):
            for p in self.c['profiles']:
                a = populacao_artificial(self.c, p, 42)
                pd.testing.assert_frame_equal(a, populacao_artificial(self.c, p, 42))
                self.assertEqual(list(a), CTGAN_FEATURES)
                self.assertEqual(len(validar_candidatos(a, self.c, p)), len(a))
                self.assertTrue(a.loc[a[HISTORICOS[1]].eq(0), [HISTORICOS[0], HISTORICOS[2]]].isna().all().all())

    def test_fit_recebe_apenas_15_sem_perfil_ou_alvo(self):
        base = populacao_artificial(self.c, self.c['profiles'][0], 42)
        with patch('ctgan.CTGAN') as classe:
            pacote, b = ajustar_perfil(base, self.c, 42)
        pd.testing.assert_frame_equal(classe.return_value.fit.call_args.args[0], b)
        self.assertEqual(list(b), CTGAN_FEATURES)
        self.assertEqual(pacote['source'], 'json_rules_only')

    def test_ids_datas_contrato_probabilidades_seed(self):
        a, auditoria = self.sinteticos()
        b, _ = self.sinteticos()
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(list(a), CLEAN_COLUMNS)
        self.assertEqual(set(a.order_approved_at.dt.year), {2016, 2017, 2018})
        self.assertTrue(a.seller_id.is_unique and a.order_id.is_unique)
        self.assertEqual(auditoria.groupby('perfil').p_atraso_simulada.first().to_dict(), {'baixo': .05, 'medio': .2, 'alto': .6})
        self.assertNotIn('perfil', a)
        self.assertNotIn('p_atraso_simulada', a)

    def test_rejeita_rota_e_faixa_incoerentes(self):
        p = self.c['profiles'][0]
        a = populacao_artificial(self.c, p, 42)
        a['customer_state'] = 'AC'
        self.assertTrue(validar_candidatos(a, self.c, p).empty)

    def test_amostragem_rejeita_sem_afrouxar_regras_e_registra_falha(self):
        p = self.c['profiles'][0]
        inicial = populacao_artificial(self.c, p, 42)
        modelo = Mock()
        pacote = {'source': 'json_rules_only', 'hash_seed': hash_tabela(inicial), 'modelo': modelo, 'logs': []}
        modelo.sample.return_value = populacao_artificial(self.c, p, 43)
        base, report = amostrar_perfil(pacote, inicial, self.c, p, 10, 100)
        self.assertEqual(len(base), 10)
        self.assertEqual(report['aceitos'], 10)
        self.c['max_resample_attempts'] = 1
        modelo.sample.return_value = inicial.assign(valor_frete=-1)
        with self.assertRaises(ValueError) as erro:
            amostrar_perfil(pacote, inicial, self.c, p, 10, 100)
        self.assertEqual(erro.exception.relatorio['aceitos'], 0)
        self.assertEqual(erro.exception.relatorio['invalidos'], len(inicial))
        a = populacao_artificial(self.c, p, 42)
        a['prazo_prometido_dias'] = 1
        self.assertTrue(validar_candidatos(a, self.c, p).empty)

    def test_ml_fit_somente_sintetico_avaliacao_nao_muda_modelo(self):
        a, _ = self.sinteticos()
        d = montar_ml_sintetico(a)
        with patch('pandas.read_parquet', side_effect=AssertionError('Não ler Olist durante fit')):
            modelo = treinar_somente_sinteticos(d, self.c)
        self.assertFalse(set(modelo['train_ids']) & set(modelo['holdout_ids']))
        self.assertEqual(len(modelo['train_ids']) + len(modelo['holdout_ids']), len(a))
        self.assertIn('atrasos_sinteticos', modelo['holdout_metrics'])
        self.assertNotIn('atrasos_reais', modelo['holdout_metrics'])
        coef = modelo['pipeline'].named_steps['modelo'].coef_.copy()
        limiar = modelo['limiar']
        real = a.assign(origem_dado='real', particao='teste')
        tabela, previsoes = avaliar_real(real, modelo)
        self.assertEqual(len(previsoes), len(a))
        np.testing.assert_array_equal(coef, modelo['pipeline'].named_steps['modelo'].coef_)
        self.assertEqual(limiar, modelo['limiar'])
        self.assertEqual(modelo['features'], ML_FEATURES)
        with self.assertRaises(ValueError):
            treinar_somente_sinteticos(d.assign(origem_dado='real'), self.c)


if __name__ == '__main__':
    unittest.main()
