"""Respostas simuladas para conferir limites, término e contingência, sem rede."""
import unittest
from unittest.mock import patch

from google.genai import types
from src import assistente_genai as assistente


def resposta_sdk(motivo='STOP', texto='Resumo completo de teste para a revisão humana da fila.'):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        finish_reason=motivo,
        content=types.Content(role='model', parts=[types.Part(text=texto)]),
    )])


class AssistenteGenAITest(unittest.TestCase):
    def setUp(self):
        self.ambiente=patch.dict(assistente.os.environ,{
            'GEMINI_API_KEY':'chave-ficticia-de-teste', 'GEMINI_MODEL':'gemini-3.6-flash',
        })
        self.ambiente.start();self.addCleanup(self.ambiente.stop)
        self.patch_cliente=patch.object(assistente.genai,'Client')
        self.cliente=self.patch_cliente.start();self.addCleanup(self.patch_cliente.stop)
        self.gerar=self.cliente.return_value.__enter__.return_value.models.generate_content

    def test_pdf_tem_orcamento_proprio_e_confirma_termino(self):
        self.gerar.return_value=resposta_sdk()
        resultado=assistente.responder('Resumo técnico',{'pedidos':20},para_relatorio=True)
        config=self.gerar.call_args.kwargs['config']
        self.assertEqual(config.max_output_tokens,4096)
        self.assertEqual(config.thinking_config.thinking_level.value,'MINIMAL')
        http=self.cliente.call_args.kwargs['http_options']
        self.assertEqual(http.timeout,45000)
        self.assertEqual(http.retry_options.attempts,1)
        self.assertTrue(resultado['disponivel'])
        self.assertEqual(resultado['motivo_termino'],'STOP')
        self.gerar.assert_called_once()

    def test_limite_de_tokens_refaz_uma_vez_sem_concatenar_fragmentos(self):
        self.gerar.side_effect=[resposta_sdk('MAX_TOKENS','Fragmento incompleto.'),resposta_sdk()]
        resultado=assistente.responder('Resumo técnico',{},para_relatorio=True)
        self.assertTrue(resultado['disponivel'])
        self.assertNotIn('Fragmento',resultado['resposta'])
        self.assertEqual([c.kwargs['config'].max_output_tokens for c in self.gerar.call_args_list],[4096,8192])

    def test_segundo_limite_interrompe_sem_retornar_texto_parcial(self):
        self.gerar.return_value=resposta_sdk('MAX_TOKENS','Fragmento incompleto.')
        resultado=assistente.responder('Resumo técnico',{},para_relatorio=True)
        self.assertFalse(resultado['disponivel'])
        self.assertEqual(resultado['motivo_termino'],'MAX_TOKENS')
        self.assertNotIn('Fragmento',resultado['resposta'])
        self.assertEqual(self.gerar.call_count,2)

    def test_bloqueios_e_falta_de_candidato_nao_sao_repetidos(self):
        for resposta in [resposta_sdk('SAFETY'),resposta_sdk('RECITATION'),types.GenerateContentResponse(candidates=[])]:
            with self.subTest(resposta=resposta):
                self.gerar.reset_mock();self.gerar.return_value=resposta
                resultado=assistente.responder('Resumo técnico',{},para_relatorio=True)
                self.assertFalse(resultado['disponivel'])
                self.gerar.assert_called_once()

    def test_resposta_vazia_e_erro_externo_mantem_contingencia(self):
        self.gerar.return_value=resposta_sdk(texto='')
        self.assertFalse(assistente.responder('Resumo técnico',{},para_relatorio=True)['disponivel'])
        self.gerar.side_effect=TimeoutError()
        self.assertFalse(assistente.responder('Resumo técnico',{},para_relatorio=True)['disponivel'])

    def test_chat_mantem_configuracao_existente(self):
        self.gerar.return_value=resposta_sdk()
        self.assertTrue(assistente.responder('Pergunta',{})['disponivel'])
        config=self.gerar.call_args.kwargs['config']
        self.assertEqual(config.max_output_tokens,1024)
        self.assertIsNone(config.thinking_config)
        http=self.cliente.call_args.kwargs['http_options']
        self.assertEqual(http.timeout,30000)
        self.assertEqual(http.retry_options.attempts,3)
        self.gerar.assert_called_once()

    def test_modelo_fora_da_familia_3_nao_recebe_thinking_level(self):
        self.gerar.return_value=resposta_sdk()
        with patch.dict(assistente.os.environ,{'GEMINI_MODEL':'gemini-2.5-flash'}):
            self.assertTrue(assistente.responder('Resumo técnico',{},para_relatorio=True)['disponivel'])
        self.assertIsNone(self.gerar.call_args.kwargs['config'].thinking_config)

    def test_outro_gemini_3_usa_low_em_vez_de_minimal(self):
        self.gerar.return_value=resposta_sdk()
        with patch.dict(assistente.os.environ,{'GEMINI_MODEL':'gemini-3.1-pro-preview'}):
            self.assertTrue(assistente.responder('Resumo técnico',{},para_relatorio=True)['disponivel'])
        self.assertEqual(self.gerar.call_args.kwargs['config'].thinking_config.thinking_level.value,'LOW')

    def test_sem_chave_nao_chama_provedor(self):
        with patch.dict(assistente.os.environ,{'GEMINI_API_KEY':''}):
            self.assertFalse(assistente.responder('Resumo técnico',{},para_relatorio=True)['disponivel'])
        self.cliente.assert_not_called()


if __name__=='__main__':unittest.main()
