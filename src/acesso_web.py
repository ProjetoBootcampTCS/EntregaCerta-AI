"""Contas, sessões opacas e autorização por perfil no PostgreSQL."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .carregar_postgresql import obter_conexao

ESQUEMA = "app_web"
COOKIE = "entregacerta_sessao"
HORAS_SESSAO = 8
os.environ.setdefault("PGCONNECT_TIMEOUT", "5")
router = APIRouter(prefix="/api/auth")


@contextmanager
def conexao_web():
    try:
        with obter_conexao() as conn:
            conn.row_factory = dict_row
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(ESQUEMA)))
            yield conn
    except psycopg.Error:
        raise HTTPException(503, "Serviço de contas indisponível. Confira o PostgreSQL e a inicialização da área web.") from None


def inicializar():
    with obter_conexao() as conn:
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(ESQUEMA)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(ESQUEMA)))
        conn.execute(Path(__file__).with_name("esquema_web.sql").read_text(encoding="utf-8"))


def gerar_hash(senha):
    if not 12 <= len(senha) <= 128:
        raise ValueError("Use uma senha de 12 a 128 caracteres.")
    salt = secrets.token_bytes(16)
    # scrypt conforme parâmetros mínimos OWASP, sem nova dependência.
    digest = hashlib.scrypt(senha.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256*1024*1024)
    return "scrypt$131072$8$1$" + salt.hex() + "$" + digest.hex()


def conferir_senha(senha, armazenado):
    try:
        metodo, n, r, p, salt, esperado = armazenado.split("$")
        if metodo != "scrypt" or (n, r, p) != ("131072", "8", "1"):
            return False
        atual = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=256*1024*1024)
        return hmac.compare_digest(atual, bytes.fromhex(esperado))
    except (ValueError, TypeError):
        return False


def resumo_usuario(usuario):
    return {k: str(usuario[k]) for k in ("id", "nome", "email", "perfil")}


def criar_usuario(nome, email, senha, perfil="cliente"):
    if perfil not in {"cliente", "analista"}:
        raise ValueError("Perfil inválido.")
    email = normalizar_email(email)
    digest = gerar_hash(senha)
    with conexao_web() as conn:
        usuario = conn.execute("""INSERT INTO usuarios(id,nome,email,senha_hash,perfil)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(email) DO NOTHING
            RETURNING id,nome,email,perfil""", (uuid.uuid4(), nome.strip(), email, digest, perfil)).fetchone()
    if usuario is None:
        raise HTTPException(409, "Não foi possível criar a conta com esse e-mail. Use outro endereço ou tente entrar.")
    return usuario


def normalizar_email(email):
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Informe um e-mail válido.")
    return email


class Credenciais(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    senha: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valido(cls, valor):
        return normalizar_email(valor)


class Cadastro(Credenciais):
    nome: str = Field(min_length=2, max_length=80)
    senha: str = Field(min_length=12, max_length=128)

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, valor):
        if len(valor.strip()) < 2:
            raise ValueError("Informe seu nome.")
        return valor.strip()


def limitar(chave, maximo):
    digest = hashlib.sha256(chave.encode()).hexdigest()
    with conexao_web() as conn:
        conn.execute("DELETE FROM limites_acesso WHERE reinicia_em < now() - interval '1 day'")
        registro = conn.execute("""INSERT INTO limites_acesso(chave, quantidade, reinicia_em)
            VALUES (%s, 1, now() + interval '15 minutes')
            ON CONFLICT(chave) DO UPDATE SET
              quantidade=CASE WHEN limites_acesso.reinicia_em <= now() THEN 1 ELSE limites_acesso.quantidade+1 END,
              reinicia_em=CASE WHEN limites_acesso.reinicia_em <= now() THEN now()+interval '15 minutes' ELSE limites_acesso.reinicia_em END
            RETURNING quantidade""", (digest,)).fetchone()
    if registro["quantidade"] > maximo:
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos para tentar novamente.", headers={"Retry-After": "900"})


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def obter_sessao(request):
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    with conexao_web() as conn:
        return conn.execute("""SELECT u.id,u.nome,u.email,u.perfil,s.csrf
            FROM sessoes s JOIN usuarios u ON u.id=s.usuario_id
            WHERE s.token_hash=%s AND s.expira_em>now() AND u.ativo""", (token_hash(token),)).fetchone()


def cookie_seguro():
    return os.getenv("ENTREGACERTA_COOKIE_SECURE", "false").lower() == "true"


def abrir_sessao(usuario, request, response):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(hours=HORAS_SESSAO)
    with conexao_web() as conn:
        conn.execute("DELETE FROM sessoes WHERE expira_em<=now() OR token_hash=%s", (token_hash(request.cookies.get(COOKIE, "")),))
        conn.execute("INSERT INTO sessoes(token_hash,usuario_id,csrf,expira_em) VALUES (%s,%s,%s,%s)",
                     (token_hash(token), usuario["id"], csrf, expira))
    response.set_cookie(COOKIE, token, httponly=True, secure=cookie_seguro(), samesite="strict", path="/", max_age=HORAS_SESSAO*3600)
    return {"autenticado": True, "usuario": resumo_usuario(usuario), "csrf": csrf}


def conferir_origem(request):
    permitidas = os.getenv("ENTREGACERTA_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if request.headers.get("origin", "") not in {x.strip().rstrip("/") for x in permitidas}:
        raise HTTPException(403, "Origem da requisição não autorizada.")


def politica_acesso(request: Request):
    """Política fechada por padrão: rotas novas exigem analista.

    Dependência global aplicada antes da execução dos endpoints da aplicação.
    Assets públicos são tratados separadamente, sem HTML ou arquivos de backup.
    """
    caminho, metodo = request.url.path, request.method
    escrita = metodo not in {"GET", "HEAD", "OPTIONS"}
    if escrita:
        conferir_origem(request)
    publicas = {("GET", "/"), ("GET", "/cliente"), ("GET", "/entrar"),
                ("GET", "/api/loja/catalogo"), ("GET", "/api/auth/sessao"),
                ("POST", "/api/auth/entrar"), ("POST", "/api/auth/cadastrar")}
    if (metodo, caminho) in publicas:
        return
    usuario = obter_sessao(request)
    if usuario is None:
        if caminho in {"/dashboard", "/pedidos"}:
            raise HTTPException(303, headers={"Location": "/entrar?destino=" + caminho.lstrip("/")})
        raise HTTPException(401, "Entre na sua conta para continuar.")
    request.state.usuario = usuario
    if caminho.startswith("/api/cliente/"):
        permitido = usuario["perfil"] == "cliente"
    elif caminho in {"/api/auth/sair", "/api/assistente"}:
        permitido = True
    else:
        permitido = usuario["perfil"] == "analista"
    if not permitido:
        raise HTTPException(403, "Este recurso não está disponível para o seu perfil.")
    if escrita and not hmac.compare_digest(request.headers.get("x-csrf-token", ""), usuario["csrf"]):
        raise HTTPException(403, "Sessão inválida para esta ação. Atualize a página.")


@router.get("/sessao")
def sessao_atual(request: Request):
    usuario = obter_sessao(request)
    return {"autenticado": False} if usuario is None else {"autenticado": True, "usuario": resumo_usuario(usuario), "csrf": usuario["csrf"]}


@router.post("/entrar")
def entrar(dados: Credenciais, request: Request, response: Response):
    limitar("login-ip:" + (request.client.host if request.client else "local"), 40)
    limitar("login-email:" + dados.email, 12)
    with conexao_web() as conn:
        usuario = conn.execute("SELECT * FROM usuarios WHERE email=%s", (dados.email,)).fetchone()
    # Executa a mesma derivação para e-mails desconhecidos, evitando resposta imediata.
    falso = "scrypt$131072$8$1$" + "00"*16 + "$" + "00"*64
    correto = conferir_senha(dados.senha, usuario["senha_hash"] if usuario else falso)
    if not correto or not usuario or not usuario["ativo"]:
        raise HTTPException(401, "E-mail ou senha inválidos.")
    return abrir_sessao(usuario, request, response)


@router.post("/cadastrar", status_code=201)
def cadastrar(dados: Cadastro, request: Request, response: Response):
    limitar("cadastro:" + (request.client.host if request.client else "local"), 10)
    # Perfil nunca vem do navegador; não existe cadastro público de analistas.
    usuario = criar_usuario(dados.nome, dados.email, dados.senha, "cliente")
    return abrir_sessao(usuario, request, response)


@router.post("/sair", status_code=204)
def sair(request: Request, response: Response):
    with conexao_web() as conn:
        conn.execute("DELETE FROM sessoes WHERE token_hash=%s", (token_hash(request.cookies.get(COOKIE, "")),))
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=cookie_seguro(), samesite="strict")
