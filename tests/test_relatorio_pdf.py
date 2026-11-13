"""Fixtures artificiais exclusivamente para testar PDF, cálculos e autorização."""
from io import BytesIO
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader
import pandas as pd
from src import api, acesso_web, relatorio_pdf as relatorio


def dados_teste():
    return {'contexto':'Demonstração histórica - validação Olist', 'pedidos_avaliados':20,
            'pedidos_na_fila':2,'fracao_fila':.1,'observacao':'Score não calibrado.',
            'fila':[{'order_id':'pedido-tecnico-a','score_atraso':0,'prioridade':1},
                    {'order_id':'pedido-tecnico-b','score_atraso':1,'prioridade':1}]}


class RelatorioPDFTest(unittest.TestCase):
    def setUp(self):
        relatorio._analises.clear()
        self.fatos=dados_teste()

    def test_indicadores_e_limites_histograma(self):
        resultado=relatorio.indicadores(self.fatos)
        self.assertEqual(resultado['fora_da_fila'],18)
        self.assertEqual(resultado['score_medio'],.5)
        self.assertEqual(resultado['score_mediano'],.5)
        self.assertEqual(resultado['histograma_fila'],[1,0,0,0,0,0,0,0,0,1])
        self.assertEqual(sum(resultado['histograma_fila']),2)
        for valor in [float('nan'),float('inf'),-1,1.1]:
            self.fatos['fila'][0]['score_atraso']=valor
            with self.assertRaises(ValueError):relatorio.indicadores(self.fatos)

    def test_pdf_resumo_genai_cache_e_snapshot_imutavel(self):
        registro=relatorio.registrar_analise(self.fatos,'analista-a')
        self.fatos['fila'][0]['score_atraso']=.9
        resposta={'disponivel':True,'motivo_termino':'STOP','resposta':'Texto de teste: a fila orienta revisão humana. <script>inócuo</script>.'}
        with patch.object(relatorio,'responder',return_value=resposta) as llm,patch.object(api,'prever_pedidos',side_effect=AssertionError('Não refazer inferência')):
            pdf,genai=relatorio.gerar_relatorio(registro['analise_id'],'analista-a')
            self.assertTrue(genai)
            self.assertEqual(relatorio.gerar_relatorio(registro['analise_id'],'analista-a')[0],pdf)
            llm.assert_called_once()
            contexto=llm.call_args.args[1]
            self.assertTrue(llm.call_args.kwargs['para_relatorio'])
            self.assertEqual(contexto['score_medio'],.5)
            self.assertNotIn('pedido-tecnico',str(contexto))
            self.assertNotIn('histograma_fila',contexto)
            self.assertNotIn('menor_score',contexto)
        leitor=PdfReader(BytesIO(pdf));self.assertEqual(len(leitor.pages),2)
        texto='\n'.join(p.extract_text() for p in leitor.pages)
        for esperado in ['Pedidos avaliados','0,5000','Resumo gerado pela GenAI','não é uma probabilidade','<script>inócuo</script>']:
            self.assertIn(esperado,texto)

    def test_pdf_contingencia_e_fila_vazia(self):
        self.fatos.update(pedidos_avaliados=0,pedidos_na_fila=0,fila=[])
        registro=relatorio.registrar_analise(self.fatos,'analista-a')
        with patch.object(relatorio,'responder',side_effect=TimeoutError()):
            pdf,genai=relatorio.gerar_relatorio(registro['analise_id'],'analista-a')
        self.assertFalse(genai)
        leitor=PdfReader(BytesIO(pdf));self.assertEqual(len(leitor.pages),2)
        texto=' '.join(p.extract_text() for p in leitor.pages)
        self.assertIn('GenAI indisponível',texto)
        self.assertIn('Não há pedidos na fila',texto)
        self.assertIn('Não disponível',texto)

    def test_resumo_longo_e_preservado_ate_o_fim(self):
        resumo=('Texto longo de teste <img> & fonte. '*60)+'Conclusão final preservada.'
        pdf=relatorio.montar_pdf(relatorio.indicadores(self.fatos),resumo,True,'id-tecnico','2026-11-13T12:00:00+00:00')
        leitor=PdfReader(BytesIO(pdf))
        self.assertGreaterEqual(len(leitor.pages),2)
        texto=' '.join(' '.join(p.extract_text() for p in leitor.pages).split())
        self.assertEqual(texto.count('Texto longo de teste <img> & fonte.'),60)
        self.assertIn('Conclusão final preservada.',texto)
        self.assertNotIn('Texto abreviado',texto)

    def test_resumo_interrompido_nao_e_apresentado_como_concluido(self):
        registro=relatorio.registrar_analise(self.fatos,'a')
        resposta={'disponivel':True,'motivo_termino':'STOP','resposta':'A fila selecionada contém pedidos para revisão humana, resultando em uma fração de (0,099'}
        with patch.object(relatorio,'responder',return_value=resposta):
            pdf,genai=relatorio.gerar_relatorio(registro['analise_id'],'a')
        self.assertFalse(genai)
        texto=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
        self.assertIn('chegou incompleto',texto)
        self.assertNotIn('(0,099',texto)

    def test_ponto_final_nao_disfarca_limite_de_tokens(self):
        resposta={'disponivel':True,'motivo_termino':'MAX_TOKENS','resposta':'A fila selecionada contém pedidos que precisam de revisão.'}
        self.assertFalse(relatorio.resumo_completo(resposta))
        resposta.pop('motivo_termino')
        self.assertFalse(relatorio.resumo_completo(resposta))

    def test_isolamento_expiracao_e_limite_cache(self):
        r=relatorio.registrar_analise(self.fatos,'a')
        with self.assertRaises(HTTPException) as erro:relatorio.gerar_relatorio(r['analise_id'],'b')
        self.assertEqual(erro.exception.status_code,404)
        relatorio._analises[r['analise_id']]['expira']=0
        with self.assertRaises(HTTPException) as erro:relatorio.gerar_relatorio(r['analise_id'],'a')
        self.assertEqual(erro.exception.status_code,410)
        for _ in range(relatorio.MAX_ANALISES+1):relatorio.registrar_analise(self.fatos,'a')
        self.assertEqual(len(relatorio._analises),relatorio.MAX_ANALISES)

    def test_consulta_registra_resultado_para_o_analista(self):
        # Resultados artificiais apenas para conferir o contrato HTTP e a sessão.
        resultado=pd.DataFrame({'order_id':[f'teste-{i}' for i in range(20)],
                                'score_atraso':[i/20 for i in range(20)],
                                'prioridade':[0]*18+[1]*2})
        usuario={'id':'a','perfil':'analista','csrf':'csrf-tecnico'}
        with TestClient(api.app) as cliente,patch.object(acesso_web,'obter_sessao',return_value=usuario),patch.object(api,'consultar_pedidos',return_value=resultado),patch.object(api,'obter_modelos',return_value=({'fracao_fila':.1},None)),patch.object(api,'prever_pedidos',return_value=resultado) as inferencia,patch.object(api,'priorizar_pedidos',return_value=resultado):
            resposta=cliente.get('/api/prioridades')
            self.assertEqual(resposta.status_code,200,resposta.text)
            dados=resposta.json()
            self.assertEqual(len(dados['analise_id']),32)
            self.assertIn('analisado_em',dados)
            registro=relatorio._analises[dados['analise_id']]
            self.assertEqual(registro['dono'],'a')
            self.assertEqual(registro['fatos']['pedidos_na_fila'],2)
            self.assertEqual(registro['fatos']['maior_score'],.95)
            inferencia.assert_called_once()

    def test_api_perfis_csrf_download_e_fatos_nao_injetaveis(self):
        registro=relatorio.registrar_analise(self.fatos,'a')
        url='/api/analista/relatorio-pdf';payload={'analise_id':registro['analise_id']}
        origem={'Origin':'http://127.0.0.1:8000','X-CSRF-Token':'csrf-tecnico'}
        with TestClient(api.app,headers=origem) as cliente,patch.object(acesso_web,'obter_sessao') as sessao,patch.object(relatorio,'responder',return_value={'disponivel':False,'resposta':'indisponível'}),patch.object(api,'prever_pedidos',side_effect=AssertionError('Não refazer inferência')):
            sessao.return_value=None
            self.assertEqual(cliente.post(url,json=payload).status_code,401)
            sessao.return_value={'id':'c','perfil':'cliente','csrf':'csrf-tecnico'}
            self.assertEqual(cliente.post(url,json=payload).status_code,403)
            sessao.return_value={'id':'b','perfil':'analista','csrf':'csrf-tecnico'}
            self.assertEqual(cliente.post(url,json=payload).status_code,404)
            sessao.return_value={'id':'a','perfil':'analista','csrf':'csrf-tecnico'}
            self.assertEqual(cliente.post(url,json=payload,headers={'X-CSRF-Token':''}).status_code,403)
            self.assertEqual(cliente.post(url,json=payload,headers={'Origin':'https://outro.test'}).status_code,403)
            self.assertEqual(cliente.post(url,json={**payload,'pedidos_na_fila':999}).status_code,422)
            r=cliente.post(url,json=payload)
            self.assertEqual(r.status_code,200,r.text[:100])
            self.assertEqual(r.headers['content-type'],'application/pdf')
            self.assertEqual(r.headers['cache-control'],'no-store')
            self.assertEqual(r.headers['x-resumo-genai'],'indisponivel')
            self.assertTrue(r.content.startswith(b'%PDF'))
            self.assertIn('attachment',r.headers['content-disposition'])
            self.assertEqual(cliente.get('/static/relatorio.pdf').status_code,404)


if __name__=='__main__':unittest.main()
