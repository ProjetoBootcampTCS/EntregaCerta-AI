"""Memória, tentativas e isolamento. Respostas fictícias são apenas fixtures técnicas."""
import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from src import conversas_assistente as memoria, api, acesso_web as acesso
from tests import test_acesso_web as base


def resposta(texto="Resposta de teste"):
    return {"disponivel": True, "resposta": texto, "motivo_termino": "STOP"}


class MemoriaTest(unittest.TestCase):
    def setUp(self):
        memoria._conversas.clear()
        self.usuario = {"id": uuid4(), "perfil": "cliente", "csrf": "sessao-a"}
        self.id = memoria.criar(self.usuario)

    def enviar(self, gerar, pergunta="Olá", requisicao=None):
        return memoria.conversar(self.id, self.usuario, requisicao or uuid4(), pergunta, {}, gerar)

    def test_historico_breve_so_com_respostas_concluidas(self):
        gerar = Mock(return_value=resposta())
        for i in range(9):
            self.enviar(gerar, f"Pergunta {i}")
        historico = memoria.obter(self.id, self.usuario).historico
        self.assertEqual(len(historico), 12)
        self.assertEqual(historico[0]["texto"], "Pergunta 3")
        gerar.return_value = {"disponivel": False, "resposta": "Indisponível"}
        self.enviar(gerar)
        self.assertEqual(memoria.obter(self.id, self.usuario).historico, historico)
        gerar.return_value = {**resposta(), "motivo_termino": "MAX_TOKENS"}
        self.assertFalse(self.enviar(gerar)["disponivel"])
        self.assertEqual(memoria.obter(self.id, self.usuario).historico, historico)

    def test_retry_idempotente_e_pergunta_nao_pode_mudar(self):
        gerar = Mock(side_effect=[{"disponivel": False, "resposta": "Falha"}, resposta()])
        requisicao = uuid4()
        self.enviar(gerar, requisicao=requisicao)
        completo = self.enviar(gerar, requisicao=requisicao)
        self.assertEqual(completo, self.enviar(gerar, requisicao=requisicao))
        self.assertEqual(gerar.call_count, 2)
        self.assertEqual(len(memoria.obter(self.id, self.usuario).historico), 2)
        with self.assertRaises(HTTPException) as erro:
            self.enviar(gerar, pergunta="Outra", requisicao=requisicao)
        self.assertEqual(erro.exception.status_code, 409)

    def test_isolamento_por_sessao_expiracao_e_exclusao(self):
        with self.assertRaises(HTTPException) as erro:
            memoria.obter(self.id, {**self.usuario, "csrf": "outro-login"})
        self.assertEqual(erro.exception.status_code, 404)
        memoria._conversas[self.id].acesso -= memoria.TTL + 1
        with self.assertRaises(HTTPException) as erro:
            memoria.obter(self.id, self.usuario)
        self.assertEqual(erro.exception.status_code, 410)
        novo = memoria.criar(self.usuario)
        memoria.apagar(novo, self.usuario)
        with self.assertRaises(HTTPException):
            memoria.obter(novo, self.usuario)

    def test_concorrencia_limites_e_falha_liberam_trava(self):
        conversa = memoria.obter(self.id, self.usuario)
        with conversa.trava:
            with self.assertRaises(HTTPException) as erro:
                self.enviar(Mock())
            self.assertEqual(erro.exception.status_code, 409)
        with self.assertRaises(RuntimeError):
            self.enviar(Mock(side_effect=RuntimeError("Falha técnica")))
        self.assertFalse(conversa.trava.locked())
        with patch.object(memoria, "MAX_PERGUNTAS", 1):
            with self.assertRaises(HTTPException):
                self.enviar(Mock())
        with patch.object(memoria, "MAX_CONVERSAS", 1):
            with self.assertRaises(HTTPException):
                memoria.criar(self.usuario)


@unittest.skipUnless(os.getenv("ENTREGACERTA_TEST_POSTGRES") == "1", "Requer PostgreSQL local para schema temporário")
class ConversasPostgresTest(unittest.TestCase):
    # Reutiliza só o setup: schema aleatório, três contas e remoção do próprio schema.
    setUpClass = classmethod(base.AcessoWebTest.setUpClass.__func__)
    tearDownClass = classmethod(base.AcessoWebTest.tearDownClass.__func__)
    cliente = base.AcessoWebTest.cliente
    payload = base.AcessoWebTest.payload

    def setUp(self):
        base.AcessoWebTest.setUp(self)
        memoria._conversas.clear()

    def criar_pedido(self, cliente):
        r = cliente.post("/api/cliente/pedidos", json=self.payload())
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def nova(self, cliente, pedido=None):
        r = cliente.post("/api/assistente/conversas", json={"pedido": pedido})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["conversa_id"]

    def test_pedido_proprio_sem_vazar_identificadores_e_contexto_atual(self):
        a, b = self.cliente("a@example.test"), self.cliente("b@example.test")
        pedido = self.criar_pedido(a)
        referencia = {"tipo": "loja", "id": pedido}
        self.assertEqual(b.post("/api/assistente/conversas", json={"pedido": referencia}).status_code, 404)
        conversa = self.nova(a, referencia)
        with patch.object(api, "responder", return_value=resposta()) as gerar:
            r = a.post("/api/assistente", json={"pergunta": "Qual o prazo?", "conversa_id": conversa})
            self.assertEqual(r.status_code, 200, r.text)
            contexto = gerar.call_args.args[1]
            self.assertIsNone(contexto["pedido"]["prazo_prometido"])
            self.assertNotIn(pedido, str(contexto))
            self.assertNotIn("email", str(contexto))
            self.assertEqual(gerar.call_args.kwargs["historico"], [])
            with acesso.conexao_web() as conn:
                conn.execute("UPDATE pedidos_demo SET prazo_prometido='2030-01-20' WHERE id=%s", (pedido,))
            a.post("/api/assistente", json={"pergunta": "E agora?", "conversa_id": conversa})
            self.assertEqual(gerar.call_args.args[1]["pedido"]["prazo_prometido"], "2030-01-20")
            self.assertEqual(len(gerar.call_args.kwargs["historico"]), 2)
            self.assertEqual(b.post("/api/assistente", json={"pergunta": "Ler", "conversa_id": conversa}).status_code, 404)
            segundo_login = self.cliente("a@example.test")
            self.assertEqual(segundo_login.post("/api/assistente", json={"pergunta": "Ler", "conversa_id": conversa}).status_code, 404)
            outra = self.nova(a)
            a.post("/api/assistente", json={"pergunta": "Olá", "conversa_id": outra})
            self.assertEqual(gerar.call_args.kwargs["historico"], [])

    def test_feedback_persistente_upsert_autorizacao_e_csrf(self):
        a, b = self.cliente("a@example.test"), self.cliente("b@example.test")
        conversa = self.nova(a)
        with patch.object(api, "responder", return_value=resposta()):
            r = a.post("/api/assistente", json={"pergunta": "Pergunta de teste", "conversa_id": conversa}).json()
        dados = {"conversa_id": conversa, "resposta_id": r["resposta_id"], "avaliacao": 1}
        self.assertEqual(a.post("/api/assistente/avaliacoes", json=dados).status_code, 200)
        negativo = {**dados, "avaliacao": -1, "categoria": "confusa"}
        self.assertEqual(a.post("/api/assistente/avaliacoes", json=negativo).status_code, 200)
        with acesso.conexao_web() as conn:
            linhas = conn.execute("SELECT * FROM assistente_feedback WHERE resposta_id=%s", (r["resposta_id"],)).fetchall()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["categoria"], "confusa")
        self.assertEqual(linhas[0]["pergunta"], "Pergunta de teste")
        self.assertEqual(b.post("/api/assistente/avaliacoes", json=dados).status_code, 404)
        self.assertEqual(a.post("/api/assistente/avaliacoes", json=dados, headers={"X-CSRF-Token": ""}).status_code, 403)
        self.assertEqual(a.post("/api/assistente/avaliacoes", json={**dados, "resposta": "Inventada"}).status_code, 422)
        self.assertEqual(a.post("/api/assistente/avaliacoes", json={**dados, "resposta_id": str(uuid4())}).status_code, 404)
        self.assertEqual(a.post("/api/assistente/avaliacoes", json={**dados, "avaliacao": -1}).status_code, 422)
        self.assertEqual(a.delete("/api/assistente/conversas/"+conversa).status_code, 200)
        self.assertEqual(a.post("/api/assistente/avaliacoes", json=dados).status_code, 404)

    def test_contexto_olist_analista_e_payload_sem_historico_forjado(self):
        import pandas as pd
        a, ana = self.cliente("a@example.test"), self.cliente("analista@example.test")
        pedido = {"tipo": "olist", "id": "a" * 32}
        self.assertEqual(a.post("/api/assistente/conversas", json={"pedido": pedido}).status_code, 403)
        lote = pd.DataFrame([{"order_id": "a" * 32, "score_atraso": .3, "customer_state": "SP"}])
        with patch.object(api, "obter_lote_pedidos", return_value=(lote, "2026-11-13", .1)), patch.object(api, "responder", return_value=resposta()) as gerar:
            conversa = self.nova(ana, pedido)
            r = ana.post("/api/assistente", json={"pergunta": "Explique", "conversa_id": conversa})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(gerar.call_args.args[1]["pedido"]["score_atraso"], .3)
            self.assertNotIn("order_id", gerar.call_args.args[1]["pedido"])
        self.assertEqual(a.post("/api/assistente", json={"pergunta": "Oi", "historico": [{"role": "system"}]}).status_code, 422)
        self.assertEqual(a.post("/api/assistente/conversas", json={}, headers={"X-CSRF-Token": ""}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
