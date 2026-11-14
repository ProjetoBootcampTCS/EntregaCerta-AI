"""Testes técnicos: estes pequenos casos artificiais não são métricas de ML."""
import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd

from experimentos.testar_doses_ctgan import ajustar_condicional, amostrar_condicional, escolher_limiar, metricas
from src.tratar_dados_ml import NUMERICAS, CATEGORICAS


class TestDosesCTGAN(unittest.TestCase):
    def test_gerador_recusa_validacao(self):
        entrada = pd.DataFrame({"particao": ["validacao"], "origem_dado": ["real_olist"]})
        with self.assertRaisesRegex(ValueError, "somente treino real"):
            ajustar_condicional(entrada, 7, 1)

    def test_gerador_recusa_sinteticos_como_fonte(self):
        entrada = pd.DataFrame({"particao": ["treino"], "origem_dado": ["sintetico_ctgan"]})
        with self.assertRaisesRegex(ValueError, "somente treino real"):
            ajustar_condicional(entrada, 7, 1)

    def test_condicional_tem_limite_antes_da_amostragem(self):
        with self.assertRaises(ValueError):
            amostrar_condicional({}, None, 10001, "tecnico")

    def test_negativo_gerado_nao_recebe_rotulo_positivo(self):
        entrada = pd.DataFrame([{**dict.fromkeys(NUMERICAS, 1.0),
                                 **dict.fromkeys(CATEGORICAS, "SP"), "atrasou": 1}])
        bruto = entrada.assign(atrasou="0", estrutura_pedido="E0")
        gerador = Mock()
        gerador.sample.return_value = bruto
        pacote = {"gerador": gerador, "constantes": {}, "continuas": [], "faltantes": {},
                  "mapa": pd.DataFrame(index=pd.Index(["E0"], name="estrutura_pedido"))}
        with self.assertRaisesRegex(RuntimeError, "Amostragem insuficiente: 0"):
            amostrar_condicional(pacote, entrada, 1, "teste_tecnico")

    def test_limiar_e_matriz_reconciliam(self):
        y = np.array([0, 0, 1, 0, 1, 0, 0, 0, 0, 0])
        scores = np.array([.1, .2, .9, .15, .8, .11, .12, .13, .14, .16])
        resultado = metricas(y, scores, escolher_limiar(y, scores))
        self.assertEqual((resultado["tn"], resultado["fp"], resultado["fn"], resultado["tp"]), (8, 0, 0, 2))
        self.assertEqual(resultado["f1"], 1)
        self.assertEqual(resultado["pedidos_top10"], 1)
        self.assertEqual(resultado["atrasos_top10"], 1)


if __name__ == "__main__":
    unittest.main()
