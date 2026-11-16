"""Preservação dos resultados históricos ao reorganizar o código."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import joblib
import pandas as pd
from src.experimentos import testar_doses_ctgan as doses, testar_historicos_vendedores as historicos


class OrganizacaoTest(unittest.TestCase):
    def test_simulacao_tem_implementacao_real_no_src(self):
        atual = importlib.import_module('src.simulacao_logistica.cenario')
        raiz = Path(__file__).resolve().parents[2]
        self.assertEqual(Path(atual.__file__).resolve(), raiz / 'src/simulacao_logistica/cenario.py')
        self.assertFalse((raiz / 'experimentos').exists())

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
