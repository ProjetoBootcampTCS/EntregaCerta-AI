"""Preservação dos resultados históricos ao reorganizar o código."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import joblib
import pandas as pd
from experimentos import testar_doses_ctgan as doses, testar_historicos_vendedores as historicos


class OrganizacaoTest(unittest.TestCase):
    def test_classe_serializada_antiga_aponta_para_mesma_classe(self):
        antigo = importlib.import_module('src.simulacao_logistica.cenario')
        atual = importlib.import_module('experimentos.simulacao_logistica.cenario')
        self.assertIs(antigo.Cenario, atual.Cenario)

    def test_protocolo_diferente_nao_sobrescreve_snapshot(self):
        # Registros reais; só o protocolo divergente é uma fixture técnica.
        base = pd.read_csv(doses.RAIZ / 'Dados/pedidos_ml.csv', nrows=50)
        base['origem_dado'] = 'real_olist'
        for modulo in (doses, historicos):
            with self.subTest(modulo=modulo.__name__), tempfile.TemporaryDirectory() as pasta:
                pasta = Path(pasta)
                snapshot = pasta / 'snapshot_postgresql.joblib'
                joblib.dump(base, snapshot)
                joblib.dump({'fixture': 'protocolo_anterior'}, pasta / 'protocolo.joblib')
                antes = snapshot.read_bytes()
                with patch.object(modulo, 'PASTA', pasta), patch.object(modulo, 'consultar_base', return_value=base):
                    with self.assertRaisesRegex(ValueError, 'Protocolo'):
                        modulo.executar()
                self.assertEqual(antes, snapshot.read_bytes())


if __name__ == '__main__':
    unittest.main()
