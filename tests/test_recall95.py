"""Fixtures artificiais apenas para verificar cortes e contagens, não desempenho."""
import unittest
import numpy as np
from src.comparar_recall95 import escolher_limiar_recall, medir


class Recall95Test(unittest.TestCase):
    def test_corte_minimiza_revisao_com_empates(self):
        y=np.array([1]*20+[0]*5)
        s=np.array(list(np.arange(20)/20)+[.05,.05,.5,.9,.99])
        corte=escolher_limiar_recall(y,s)
        self.assertEqual(corte,.05)
        resultado=medir(y,s,corte)
        self.assertEqual(resultado['fn'],1)
        self.assertEqual(resultado['recall'],.95)
        self.assertLess(medir(y,s,np.nextafter(corte,np.inf))['recall'],.95)
        for limite in np.unique(s):
            m=medir(y,s,limite)
            if m['recall']>=.95:
                self.assertGreaterEqual(m['revisoes'],resultado['revisoes'])

    def test_scores_constantes_exigem_revisar_todos(self):
        y=np.array([0,1,0,1]);s=np.full(4,.1)
        m=medir(y,s,escolher_limiar_recall(y,s))
        self.assertEqual(m['revisoes'],4)
        self.assertEqual(m['recall'],1)

    def test_poucos_positivos_exigem_todos_os_atrasos(self):
        corte=escolher_limiar_recall([0,1,1],[.1,.2,.8])
        self.assertEqual(corte,.2)
        self.assertEqual(medir([0,1,1],[.1,.2,.8],corte)['fn'],0)

    def test_entradas_invalidas(self):
        for y,s in [([],[]),([0,0],[.1,.2]),([1],[np.nan]),([1,0],[.1]),([2],[.1])]:
            with self.assertRaises(ValueError):escolher_limiar_recall(y,s)
        with self.assertRaises(ValueError):escolher_limiar_recall([1],[.1],1.1)

    def test_corte_congelado_pode_falhar_em_outro_periodo(self):
        corte=escolher_limiar_recall([0,1,1],[.1,.8,.9])
        m=medir([0,1,1],[.1,.2,.9],corte)
        self.assertEqual(m['recall'],.5)
        self.assertFalse(m['atingiu_meta'])


if __name__=='__main__':unittest.main()
