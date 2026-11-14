"""A inicialização não pode apagar uma carga já existente ou incompleta."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import main


class InicializacaoTest(unittest.TestCase):
    def test_primeira_carga_apenas_em_tabelas_vazias(self):
        self.assertTrue(main.precisa_carga(dict.fromkeys(main.TABELAS, None)))
        self.assertTrue(main.precisa_carga(dict.fromkeys(main.TABELAS, 0)))

    def test_preserva_carga_completa(self):
        contagens = dict.fromkeys(main.TABELAS, 91390)
        contagens['avaliacoes'] = 99224
        self.assertFalse(main.precisa_carga(contagens))

    def test_recusa_recarga_sobre_estado_incompleto(self):
        for tabela in main.TABELAS:
            contagens = dict.fromkeys(main.TABELAS, 10)
            contagens[tabela] = None
            with self.subTest(tabela=tabela), self.assertRaises(ValueError):
                main.precisa_carga(contagens)

    def test_iniciar_nao_executa_carga_nem_migracao(self):
        with patch.object(main, 'conferir_arquivos'), patch.object(main, 'ligar_banco'), \
             patch.object(main, 'conferir_banco'), patch('uvicorn.run') as servidor, \
             patch('src.banco.carregar') as carga, patch('src.acesso_web.inicializar') as migracao:
            main.iniciar(SimpleNamespace(sem_docker=True))
        carga.assert_not_called()
        migracao.assert_not_called()
        self.assertEqual(servidor.call_args.kwargs['workers'], 1)


if __name__ == '__main__':
    unittest.main()
