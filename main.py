"""Comandos do EntregaCerta AI. Comece com: python main.py --help."""
import argparse
from getpass import getpass
import os
from pathlib import Path
import subprocess
import sys
import time

RAIZ = Path(__file__).resolve().parent
TABELAS = ('pedidos', 'clientes', 'logistica', 'pagamentos', 'qualidade_dados', 'avaliacoes')
ARQUIVOS = (
    '.env', 'Modelos/preprocessador_rede.joblib', 'Modelos/rede_neural.pt',
    'Dados/Brazilian Logistic/olist_products_dataset.csv',
    'Dados/Brazilian Logistic/olist_order_items_dataset.csv',
)


def conferir_arquivos():
    faltantes = [nome for nome in ARQUIVOS if not (RAIZ / nome).is_file()]
    if faltantes:
        raise ValueError('Arquivos ausentes: ' + ', '.join(faltantes) + '. Consulte Docs/instalacao_novo_pc.md.')


def ligar_banco(sem_docker=False):
    """Sobe o contêiner existente e espera até 30 s. Não carrega nem apaga dados."""
    if not (RAIZ / '.env').is_file():
        raise ValueError('Crie o .env conforme Docs/instalacao_novo_pc.md.')
    if not sem_docker:
        subprocess.run(['docker', 'compose', 'up', '-d', 'postgres'], cwd=RAIZ, check=True)
    from src.banco import obter_conexao
    import psycopg
    for tentativa in range(10):
        try:
            with obter_conexao() as conn:
                conn.execute('SELECT 1')
            return
        except psycopg.Error:
            if tentativa == 9:
                raise ValueError('PostgreSQL indisponível. Confira Docker Desktop e POSTGRES_* no .env.') from None
            time.sleep(1)


def contar_historico():
    from src.banco import obter_conexao
    from psycopg import sql
    with obter_conexao() as conn:
        contagens = {}
        for tabela in TABELAS:
            existe = conn.execute('SELECT to_regclass(%s)', ('public.' + tabela,)).fetchone()[0]
            contagens[tabela] = (
                conn.execute(sql.SQL('SELECT COUNT(*) FROM public.{}').format(sql.Identifier(tabela))).fetchone()[0]
                if existe else None
            )
    return contagens


def precisa_carga(contagens):
    """Só autoriza a primeira carga se nenhuma tabela histórica contiver dados."""
    if all(contagens[t] in (None, 0) for t in TABELAS):
        return True
    pedidos = contagens['pedidos'] or 0
    completo = pedidos > 0 and (contagens['avaliacoes'] or 0) > 0
    completo = completo and all(contagens[t] == pedidos for t in TABELAS[1:5])
    if not completo:
        raise ValueError('Carga histórica incompleta. Dados preservados; confira as tabelas antes de recarregar.')
    return False


def preparar_banco(args):
    ligar_banco(args.sem_docker)
    from src.banco import carregar, obter_conexao
    from src.acesso_web import inicializar
    if precisa_carga(contar_historico()):
        print('Primeira carga: lendo pedidos_ml.csv e avaliações. Aguarde...', flush=True)
        pedidos, avaliacoes = carregar()
        print(f'Carregados: {pedidos} pedidos e {avaliacoes} avaliações.')
    else:
        print('Histórico já carregado; pedidos e avaliações preservados.')
    with obter_conexao() as conn:
        conn.execute((RAIZ / 'src/view_pedidos_inferencia.sql').read_text(encoding='utf-8'))
    inicializar()
    print('View e tabelas web prontas. Contas, pedidos da loja e histórico preservados.')


def conferir_banco():
    from src.banco import obter_conexao
    with obter_conexao() as conn:
        for tabela in ['public.vw_pedidos_inferencia', 'app_web.usuarios', 'app_web.assistente_feedback']:
            if conn.execute('SELECT to_regclass(%s)', (tabela,)).fetchone()[0] is None:
                raise ValueError('Banco ainda não preparado. Execute: python main.py preparar-banco')
        total = conn.execute('SELECT COUNT(*) FROM public.vw_pedidos_inferencia').fetchone()[0]
        if total == 0:
            raise ValueError('Base histórica vazia. Execute: python main.py preparar-banco')
    return total


def iniciar(args):
    conferir_arquivos()
    ligar_banco(args.sem_docker)
    conferir_banco()
    import uvicorn
    print('Abra http://127.0.0.1:8000 — Ctrl+C encerra o servidor.', flush=True)
    # Memória das conversas e PDFs pertence a este processo.
    uvicorn.run('src.api:app', host='127.0.0.1', port=8000, workers=1)


def criar_analista(args):
    from src.acesso_web import criar_usuario
    conferir_banco()
    senha = getpass('Senha do analista (12 a 128 caracteres): ')
    if senha != getpass('Confirme a senha: '):
        raise ValueError('Senhas diferentes. Nenhuma conta criada.')
    criar_usuario(args.nome, args.email, senha, 'analista')
    print('Analista criado. Entre em http://127.0.0.1:8000/entrar.')


def verificar(_args):
    """Diagnóstico real, somente leitura; não chama a API de GenAI."""
    conferir_arquivos()
    total = conferir_banco()
    from src.banco import consultar_pedidos
    from src.inferencia import carregar_modelos, prever_pedidos, priorizar_pedidos
    pedidos = consultar_pedidos('validacao')
    pacote, modelo = carregar_modelos()
    resultado = priorizar_pedidos(prever_pedidos(pedidos, pacote, modelo), pacote['fracao_fila'])
    print(f'Banco: {total} pedidos. Validação: {len(resultado)}. Fila: {int(resultado.prioridade.sum())}.')
    print('PostgreSQL, pré-processamento e modelo carregado funcionando. GenAI não consultada.')


def testar(args):
    if args.postgres:
        os.environ['ENTREGACERTA_TEST_POSTGRES'] = '1'
    else:
        os.environ.pop('ENTREGACERTA_TEST_POSTGRES', None)
    comando = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v']
    raise SystemExit(subprocess.call(comando, cwd=RAIZ))


def main():
    os.chdir(RAIZ)
    os.environ.setdefault('PGCONNECT_TIMEOUT', '2')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='comando', required=True)
    for nome, funcao, ajuda in [
        ('iniciar', iniciar, 'Abrir o sistema com o modelo salvo; uso diário.'),
        ('preparar-banco', preparar_banco, 'Primeira carga e atualização segura do esquema web.'),
    ]:
        comando = sub.add_parser(nome, help=ajuda)
        comando.add_argument('--sem-docker', action='store_true', help='Usar PostgreSQL já iniciado ou externo.')
        comando.set_defaults(funcao=funcao)
    comando = sub.add_parser('criar-analista', help='Cadastrar analista; senha solicitada no terminal.')
    comando.add_argument('--nome', required=True)
    comando.add_argument('--email', required=True)
    comando.set_defaults(funcao=criar_analista)
    sub.add_parser('verificar', help='Conferir banco e inferência reais, sem alterar dados.').set_defaults(funcao=verificar)
    comando = sub.add_parser('testar', help='Executar testes da aplicação e preparação de dados.')
    comando.add_argument('--postgres', action='store_true', help='Incluir integração em schemas temporários do banco.')
    comando.set_defaults(funcao=testar)
    args = parser.parse_args()
    try:
        args.funcao(args)
    except KeyboardInterrupt:
        print('\nEncerrado.')
    except (ValueError, FileNotFoundError) as erro:
        parser.exit(1, f'{erro}\n')
    except Exception as erro:
        # Não imprimir DSN, senha ou chave eventualmente incluídos em exceções.
        parser.exit(1, f'Falha ({type(erro).__name__}). Confira o ambiente e o guia Docs/instalacao_novo_pc.md.\n')


if __name__ == '__main__':
    main()
