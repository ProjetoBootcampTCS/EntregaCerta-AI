"""Verificações de isolamento; os poucos casos alterados aqui não medem desempenho."""
import unittest

import pandas as pd

from src.experimento_ctgan import RAIZ, gerar_atrasos, validar_injecao, filtrar_candidatos
from src.tratar_dados_ml import limpar_atributos


class TestExperimentoCTGAN(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = pd.read_csv(RAIZ / 'Dados/pedidos_ml.csv', nrows=50)
        cls.x, _ = limpar_atributos(cls.base)

    def lote_tecnico(self):
        lote = self.x.iloc[:2].copy()
        lote['order_id'] = ['ctgan_teste_0', 'ctgan_teste_1']
        lote['particao'] = 'treino'
        lote['atrasou'] = 1
        lote['origem_dado'] = 'sintetico_ctgan'
        lote['rotulo_observado'] = False
        lote['experimento_id'] = 'teste_tecnico'
        return lote

    def test_recusa_injetar_em_validacao_ou_teste(self):
        for particao in ['validacao', 'teste']:
            lote = self.lote_tecnico()
            lote.loc[lote.index[0], 'particao'] = particao
            with self.assertRaises(ValueError):
                validar_injecao(self.base, lote)

    def test_recusa_disfarcar_sinteticos_como_observados(self):
        lote = self.lote_tecnico()
        lote['rotulo_observado'] = True
        with self.assertRaises(ValueError):
            validar_injecao(self.base, lote)

    def test_recusa_id_real(self):
        lote = self.lote_tecnico()
        lote.loc[lote.index[0], 'order_id'] = self.base.order_id.iloc[0]
        with self.assertRaises(ValueError):
            validar_injecao(self.base, lote)

    def test_limite_verificado_antes_de_acessar_gerador(self):
        for quantidade in [0, -1, 10001, 10.5]:
            with self.assertRaises(ValueError):
                gerar_atrasos({}, quantidade, 'teste')

    def test_rejeita_frete_negativo_mesmo_com_um_vendedor(self):
        lote = self.x.iloc[:1].copy()
        lote['quantidade_vendedores'] = 1
        lote['valor_frete'] = -1
        lote['distancia_media_vendedores_km'] = 10
        lote['distancia_max_vendedores_km'] = 20
        self.assertTrue(filtrar_candidatos(lote, self.x).empty)

    def test_recusa_lote_duplicado(self):
        lote = self.lote_tecnico()
        lote = pd.concat([lote, lote], ignore_index=True)
        with self.assertRaises(ValueError):
            validar_injecao(self.base, lote)


if __name__ == '__main__':
    unittest.main()
