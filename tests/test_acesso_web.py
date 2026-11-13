"""Integração de segurança em schema PostgreSQL temporário; nenhum dado de ML."""
import os
from datetime import datetime, timedelta, timezone
import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import sql

from src import acesso_web as acesso, api, loja_web


@unittest.skipUnless(os.getenv("ENTREGACERTA_TEST_POSTGRES") == "1", "Ative ENTREGACERTA_TEST_POSTGRES=1 com PostgreSQL local disponível")
class AcessoWebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.esquema = "test_web_" + uuid4().hex
        cls.patch_schema = patch.object(acesso, "ESQUEMA", cls.esquema)
        cls.patch_schema.start()
        cls.origens = patch.dict(os.environ, {"ENTREGACERTA_ORIGINS": "http://testserver", "ENTREGACERTA_COOKIE_SECURE": "false"})
        cls.origens.start()
        acesso.inicializar()
        cls.senha = "Teste-isolado-" + uuid4().hex
        cls.ana = acesso.criar_usuario("Analista de teste", "analista@example.test", cls.senha, "analista")
        cls.a = acesso.criar_usuario("Cliente A", "a@example.test", cls.senha)
        cls.b = acesso.criar_usuario("Cliente B", "b@example.test", cls.senha)

    @classmethod
    def tearDownClass(cls):
        # Remover somente o namespace aleatório criado por esta classe.
        assert cls.esquema.startswith("test_web_") and len(cls.esquema) == 41
        with acesso.obter_conexao() as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.esquema)))
        cls.patch_schema.stop()
        cls.origens.stop()

    def setUp(self):
        with acesso.conexao_web() as conn:
            conn.execute("DELETE FROM limites_acesso")
            conn.execute("UPDATE usuarios SET ativo=true")

    def cliente(self, email=None):
        c = TestClient(api.app, headers={"Origin": "http://testserver"})
        self.addCleanup(c.close)
        if email:
            r = c.post("/api/auth/entrar", json={"email": email, "senha": self.senha})
            self.assertEqual(r.status_code, 200, r.text)
            c.headers["X-CSRF-Token"] = r.json()["csrf"]
        return c

    def payload(self):
        p = loja_web.catalogo()[0]
        return {"itens": [{"produto_id": p["id"], "quantidade": 2}], "uf": "SP", "chave_requisicao": str(uuid4())}

    def test_anonimo_paginas_api_e_assets_privados(self):
        c = self.cliente()
        for rota in ["/", "/cliente", "/entrar", "/api/loja/catalogo", "/static/auth.js"]:
            self.assertEqual(c.get(rota).status_code, 200, rota)
        for rota in ["/dashboard", "/pedidos"]:
            r = c.get(rota, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].startswith("/entrar?destino="))
        for rota in ["/api/prioridades", "/api/pedidos", "/api/cliente/pedidos", "/api/analista/pedidos-loja"]:
            self.assertEqual(c.get(rota).status_code, 401, rota)
        self.assertEqual(c.post("/api/assistente", json={"pergunta":"teste"}).status_code, 401)
        for rota in ["/static/dashboard.html", "/static/pedidos.html", "/static/versoes/V1.zip", "/docs", "/openapi.json"]:
            self.assertEqual(c.get(rota).status_code, 404, rota)

    def test_cadastro_cliente_sem_escalada_de_privilegios(self):
        c = self.cliente()
        dados = {"nome":"Novo cliente", "email": uuid4().hex+"@example.test", "senha":self.senha}
        r = c.post("/api/auth/cadastrar", json={**dados, "perfil":"analista"})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn(self.senha, r.text)
        r = c.post("/api/auth/cadastrar", json=dados)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["usuario"]["perfil"], "cliente")
        self.assertNotIn("senha", r.text)
        self.assertEqual(c.get("/api/prioridades").status_code, 403)

    def test_cliente_assistente_sem_acesso_ao_painel_ou_ml(self):
        c = self.cliente("a@example.test")
        with patch.object(api, "consultar_pedidos", side_effect=AssertionError("Não deve consultar ML")):
            for rota in ["/dashboard", "/pedidos", "/api/prioridades", "/api/pedidos", "/api/analista/pedidos-loja"]:
                self.assertEqual(c.get(rota, follow_redirects=False).status_code, 403, rota)
            with patch.object(api, "responder", return_value={"disponivel":True,"resposta":"Resposta técnica de teste"}) as responder:
                self.assertEqual(c.post("/api/assistente", json={"pergunta":"teste"}).status_code, 200)
                contexto=responder.call_args.args[1]
                self.assertIn("Área do cliente",contexto["contexto"])
                self.assertNotIn("pedidos_avaliados",contexto)
                self.assertNotIn("email",str(contexto))
                self.assertEqual(c.post("/api/assistente",json={"pergunta":"teste"},headers={"X-CSRF-Token":""}).status_code,403)
            self.assertEqual(c.patch("/api/analista/pedidos-loja/"+str(uuid4()), json={"status":"entregue"}).status_code, 403)

    def test_senha_hash_cookie_token_e_resposta(self):
        c = self.cliente()
        r = c.post("/api/auth/entrar", json={"email":"a@example.test", "senha":self.senha})
        cookie = r.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertIn("max-age=28800", cookie)
        token = c.cookies[acesso.COOKIE]
        self.assertNotIn(token, r.text)
        with acesso.conexao_web() as conn:
            usuario = conn.execute("SELECT senha_hash FROM usuarios WHERE email=%s", ("a@example.test",)).fetchone()
            sessao = conn.execute("SELECT * FROM sessoes WHERE token_hash=%s", (acesso.token_hash(token),)).fetchone()
        self.assertNotEqual(usuario["senha_hash"], self.senha)
        self.assertTrue(acesso.conferir_senha(self.senha, usuario["senha_hash"]))
        self.assertIsNotNone(sessao)
        self.assertNotEqual(sessao["token_hash"], token)
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertEqual(r.headers["x-content-type-options"], "nosniff")
        self.assertEqual(c.post("/api/auth/entrar",json={"email":"a@example.test", "senha":"errada"}).status_code,401)
        with patch.dict(os.environ,{"ENTREGACERTA_COOKIE_SECURE":"true"}):
            r=c.post("/api/auth/entrar",json={"email":"a@example.test", "senha":self.senha})
            self.assertIn("; Secure",r.headers["set-cookie"])

    def test_origem_e_csrf_obrigatorios(self):
        c = self.cliente("a@example.test")
        for headers in [{"Origin":"https://outro.example"}, {"X-CSRF-Token":"incorreto"}, {"Origin":""}, {"X-CSRF-Token":""}]:
            self.assertEqual(c.post("/api/cliente/pedidos",json=self.payload(),headers=headers).status_code,403)
        anonimo=self.cliente()
        self.assertEqual(anonimo.post("/api/auth/entrar",json={"email":"a@example.test","senha":self.senha},headers={"Origin":"https://outro.example"}).status_code,403)

    def test_pedido_idempotente_precos_servidor_e_ownership(self):
        a,b=self.cliente("a@example.test"),self.cliente("b@example.test")
        dados=self.payload()
        r=a.post("/api/cliente/pedidos",json=dados)
        self.assertEqual(r.status_code,201,r.text)
        p=r.json()
        self.assertEqual(p["total_centavos"],loja_web.catalogo()[0]["preco_centavos"]*2)
        self.assertEqual(p["origem"],"demonstracao_loja")
        self.assertEqual(a.post("/api/cliente/pedidos",json=dados).json()["id"],p["id"])
        self.assertEqual(a.post("/api/cliente/pedidos",json={**dados,"uf":"RJ"}).status_code,409)
        self.assertEqual(a.post("/api/cliente/pedidos",json={**dados,"cliente_id":str(self.b["id"])}).status_code,422)
        self.assertEqual(a.post("/api/cliente/pedidos",json={**dados,"total_centavos":1}).status_code,422)
        self.assertEqual(b.get("/api/cliente/pedidos/"+p["id"]).status_code,404)
        self.assertNotIn(p["id"],[p["id"] for p in b.get("/api/cliente/pedidos").json()["pedidos"]])
        self.assertEqual(a.get("/api/cliente/pedidos/"+p["id"]).status_code,200)

    def test_fluxo_analista_e_acompanhamento_cliente(self):
        c=self.cliente("a@example.test");a=self.cliente("analista@example.test")
        p=c.post("/api/cliente/pedidos",json=self.payload()).json()
        for rota in ["/dashboard","/pedidos","/api/analista/pedidos-loja"]:
            self.assertEqual(a.get(rota).status_code,200,rota)
        self.assertEqual(a.get("/api/cliente/pedidos").status_code,403)
        url="/api/analista/pedidos-loja/"+p["id"]
        self.assertEqual(a.patch(url,json={"status":"entregue","versao":1}).status_code,409)
        for versao,status in enumerate(["em_preparacao","despachado","entregue"],start=1):
            r=a.patch(url,json={"status":status,"versao":versao})
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(c.get("/api/cliente/pedidos/"+p["id"]).json()["status"],status)
        self.assertEqual(len(r.json()["eventos"]),4)

    def test_logout_expiracao_e_desativacao_invalidam_sessao(self):
        c=self.cliente("a@example.test");token=c.cookies[acesso.COOKIE]
        self.assertEqual(c.post("/api/auth/sair").status_code,204)
        c.cookies.set(acesso.COOKIE,token)
        self.assertEqual(c.get("/api/cliente/pedidos").status_code,401)
        c=self.cliente("a@example.test");token=c.cookies[acesso.COOKIE]
        with acesso.conexao_web() as conn:
            conn.execute("UPDATE sessoes SET expira_em=now()-interval '1 second' WHERE token_hash=%s",(acesso.token_hash(token),))
        self.assertEqual(c.get("/api/cliente/pedidos").status_code,401)
        c=self.cliente("a@example.test")
        with acesso.conexao_web() as conn:
            conn.execute("UPDATE usuarios SET ativo=false WHERE email=%s",("a@example.test",))
        self.assertEqual(c.get("/api/cliente/pedidos").status_code,401)

    def test_limite_tentativas_persistente(self):
        c=self.cliente()
        for _ in range(12):
            r=c.post("/api/auth/entrar",json={"email":"inexistente@example.test","senha":"invalida"})
            self.assertEqual(r.status_code,401)
        r=c.post("/api/auth/entrar",json={"email":"inexistente@example.test","senha":"invalida"})
        self.assertEqual(r.status_code,429)
        self.assertEqual(r.headers["retry-after"],"900")


    def test_prazo_responsavel_historico_e_privacidade(self):
        c=self.cliente("a@example.test");a=self.cliente("analista@example.test")
        p=c.post("/api/cliente/pedidos",json=self.payload()).json()
        self.assertIsNone(p["prazo_prometido"])
        url="/api/analista/pedidos-loja/"+p["id"]
        prazo=(datetime.now(timezone.utc)+timedelta(days=7)).date().isoformat()
        responsavel=str(self.ana["id"])
        equipe=a.get("/api/analista/responsaveis").json()["responsaveis"]
        self.assertIn(responsavel,[x["id"] for x in equipe])
        self.assertNotIn(str(self.a["id"]),[x["id"] for x in equipe])
        r=a.patch(url,json={"versao":1,"prazo_prometido":prazo,"responsavel_id":responsavel,"status":"em_preparacao"})
        self.assertEqual(r.status_code,200,r.text)
        novo=r.json()
        self.assertEqual(novo["versao"],2)
        self.assertEqual(novo["prazo_original"],prazo)
        self.assertEqual(novo["responsavel_id"],responsavel)
        self.assertEqual(len(novo["eventos"][-1]["alteracoes"]),3)
        self.assertEqual(novo["eventos"][-1]["autor"]["id"],responsavel)
        adiado=(datetime.now(timezone.utc)+timedelta(days=10)).date().isoformat()
        self.assertEqual(a.patch(url,json={"versao":2,"prazo_prometido":adiado}).status_code,422)
        r=a.patch(url,json={"versao":2,"prazo_prometido":adiado,"motivo":"Nota interna para teste"})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["prazo_original"],prazo)
        self.assertEqual(r.json()["prazo_prometido"],adiado)
        # Recarga do cliente usa dados persistidos; não recebe o autor ou notas internas.
        publico=c.get("/api/cliente/pedidos/"+p["id"]).json()
        self.assertEqual(publico["prazo_prometido"],adiado)
        self.assertEqual(publico["prazo_original"],prazo)
        self.assertNotIn("Nota interna",str(publico))
        self.assertNotIn(responsavel,str(publico))
        self.assertNotIn("responsavel",publico)
        self.assertEqual(len(publico["eventos"]),3)
        self.assertEqual(c.get("/api/analista/responsaveis").status_code,403)
        self.assertEqual(self.cliente("b@example.test").get("/api/cliente/pedidos/"+p["id"]).status_code,404)
        # Migração pode ser repetida sem apagar o pedido e seu histórico.
        acesso.inicializar()
        self.assertEqual(c.get("/api/cliente/pedidos/"+p["id"]).json(),publico)

    def test_conflitos_validacao_e_sem_alteracoes(self):
        c=self.cliente("a@example.test");a=self.cliente("analista@example.test")
        p=c.post("/api/cliente/pedidos",json=self.payload()).json()
        url="/api/analista/pedidos-loja/"+p["id"]
        for mudanca in [{"responsavel_id":str(self.a["id"])},{"responsavel_id":str(uuid4())},
                        {"prazo_prometido":"2000-01-01"},{"prazo_prometido":None},
                        {"prazo_prometido":"sem data"},{"autor":"falso"}]:
            self.assertEqual(a.patch(url,json={"versao":1,**mudanca}).status_code,422)
        r=a.patch(url,json={"versao":1,"responsavel_id":str(self.ana["id"])})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(a.patch(url,json={"versao":1,"status":"em_preparacao"}).status_code,409)
        r=a.patch(url,json={"versao":2,"responsavel_id":str(self.ana["id"])})
        self.assertEqual(r.json()["versao"],2)
        self.assertEqual(len(r.json()["eventos"]),2)
        r=a.patch(url,json={"versao":2,"responsavel_id":None})
        self.assertEqual(r.json()["versao"],3)
        self.assertIsNone(r.json()["responsavel_id"])

    def test_pedido_legado_sem_autor_e_sem_prazo(self):
        c=self.cliente("a@example.test");a=self.cliente("analista@example.test")
        p=c.post("/api/cliente/pedidos",json=self.payload()).json()
        with acesso.conexao_web() as conn:
            conn.execute("UPDATE pedidos_demo SET eventos=jsonb_build_array(jsonb_build_object('status','recebido','em',criado_em)) WHERE id=%s",(p["id"],))
        acesso.inicializar()
        registro=next(x for x in a.get("/api/analista/pedidos-loja").json()["pedidos"] if x["id"]==p["id"])
        self.assertIsNone(registro["prazo_prometido"])
        self.assertIsNone(registro["responsavel_id"])
        self.assertNotIn("autor",registro["eventos"][0])


if __name__ == "__main__":
    unittest.main()
