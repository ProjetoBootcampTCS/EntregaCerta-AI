"""Administração local. Não cria senhas padrão nem disponibiliza cadastro de analista pela web."""
import argparse
from getpass import getpass

from .acesso_web import criar_usuario, inicializar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("iniciar", help="Criar tabelas web sem alterar as tabelas Olist.")
    criar = sub.add_parser("criar-analista", help="Criar conta autorizada localmente.")
    criar.add_argument("--nome", required=True)
    criar.add_argument("--email", required=True)
    args = parser.parse_args()
    inicializar()
    if args.acao == "criar-analista":
        senha = getpass("Senha do analista (12 a 128 caracteres): ")
        if senha != getpass("Confirme a senha: "):
            raise SystemExit("As senhas não coincidem. Nenhuma conta criada.")
        criar_usuario(args.nome, args.email, senha, "analista")
        print("Conta de analista criada. Entre pela página /entrar.")
    else:
        print("Tabelas da área web prontas no PostgreSQL. Dados Olist preservados.")


if __name__ == "__main__":
    main()
