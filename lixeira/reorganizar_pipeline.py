"""Registro da migração para sete Python e dois JSON; não integra o fluxo ativo."""
from pathlib import Path
import ast

RAIZ = Path(__file__).resolve().parents[1]
ANTERIOR = RAIZ / "lixeira/src"
SRC = RAIZ / "src"
SRC.mkdir(exist_ok=False)
(SRC / "configuracoes").mkdir()


def ler(nome):
    return (ANTERIOR / nome).read_text(encoding="utf-8-sig")


def trocar(texto, antigo, novo):
    assert antigo in texto, antigo
    return texto.replace(antigo, novo)


def funcao(texto, nome):
    arvore = ast.parse(texto)
    no = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == nome)
    return "\n".join(texto.splitlines()[no.lineno - 1:no.end_lineno])


BOOTSTRAP = '''import sys
from pathlib import Path
from importlib import import_module

# Os scripts numerados funcionam também quando executados fora da raiz do projeto.
sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
'''


def salvar(nome, texto):
    ast.parse(texto)
    (SRC / nome).write_text(texto.rstrip() + "\n", encoding="utf-8")


esquema = ler("dados/esquema.py")
esquema = trocar(esquema, 'Path(__file__).resolve().parents[2]', 'Path(__file__).resolve().parents[1]')
leitura = ler("ml/dados_treino.py")
leitura = leitura[leitura.index("def exigir_revisao"):]
leitura = trocar(leitura, 'em treinamento.json', 'em configuracoes/2_treinamento.json')
salvar("2_dados_treino.py", esquema + '\nimport numpy as np\nimport pandas as pd\n\n' + leitura + '''

if __name__ == "__main__":
    print("Auxiliar chamado automaticamente por 1_preparar_dados.py e 2_treinar_modelos.py.")
''')

preparacao = ler("dados/preparar_dados.py")
preparacao = trocar(preparacao, 'from .esquema import RAIZ, ATRIBUTOS, sha256', BOOTSTRAP + '''
_dados = import_module("src.2_dados_treino")
ATRIBUTOS, sha256 = _dados.ATRIBUTOS, _dados.sha256
''')
preparacao = trocar(preparacao, 'from src.experimentos.legado.pln_status_entrega import comentarios',
                    'comentarios = import_module("src.1_pln").comentarios')
preparacao = trocar(preparacao, 'from src.experimentos.legado.pln_status_entrega import treinar_pln',
                    'treinar_pln = import_module("src.1_pln").treinar_pln')
preparacao = trocar(preparacao, 'src/configuracoes/dados.json', 'src/configuracoes/1_dados.json')
salvar("1_preparar_dados.py", preparacao)

pln = ler("experimentos/legado/pln_status_entrega.py")
pln = pln[:pln.index('if __name__ == "__main__":')]
pln += '''if __name__ == "__main__":
    print("Auxiliar da preparação: execute 1_preparar_dados.py para aplicar a PLN.")
'''
salvar("1_pln.py", pln)

ctgan = ler("ctgan/geracao.py")
ctgan = trocar(ctgan, '''from src.dados.esquema import CATEGORICAS, ALVO_CLASSE, ALVO_DIAS
from src.ml.dados_treino import validar_tabela, exigir_revisao''', BOOTSTRAP + '''
_dados = import_module("src.2_dados_treino")
CATEGORICAS, ALVO_CLASSE, ALVO_DIAS = _dados.CATEGORICAS, _dados.ALVO_CLASSE, _dados.ALVO_DIAS
validar_tabela, exigir_revisao = _dados.validar_tabela, _dados.exigir_revisao
''')
ctgan += '''

if __name__ == "__main__":
    print("Auxiliar do treino: execute 2_treinar_modelos.py; para gerar apenas dados, use --etapa preparar.")
'''
salvar("2_ctgan.py", ctgan)

catalogo = ler("ml/modelos.py") + '''

if __name__ == "__main__":
    print("Auxiliar do treino. Modelos disponíveis:", ", ".join(CATALOGO))
'''
salvar("2_catalogo_modelos.py", catalogo)

experimentos = ler("ml/experimentos.py")
avaliacao = ler("ml/metricas.py")
avaliacao += '\n\nimport argparse\nimport json\nimport re\nimport pandas as pd\n' + BOOTSTRAP
avaliacao += '\n\n' + funcao(experimentos, 'caminho')
for nome in ['arquivo_resultados', 'marcar_selecionados', 'mostrar_resultados']:
    corpo = funcao(experimentos, nome)
    avaliacao += '\n\n' + corpo
    experimentos = trocar(experimentos, corpo + '\n\n', '')
avaliacao += '''


def main():
    parser = argparse.ArgumentParser(description="Consultar o CSV de desempenho de uma execução concluída.")
    parser.add_argument("--nome", help="Nome da execução; omitido usa a última execução.")
    args = parser.parse_args()
    mostrar_resultados(args.nome)


if __name__ == "__main__":
    main()
'''
salvar("3_avaliar_modelos.py", avaliacao)

experimentos = trocar(experimentos, '"""Laboratório configurável: python -m src.ml.experimentos --config ..."""',
    '"""Etapa 2: CTGAN, cenários, treino automatizado e CSV único de avaliação."""')
experimentos = trocar(experimentos, '''from src.dados.esquema import RAIZ, ATRIBUTOS, CATEGORICAS, sha256
from src.ml.dados_treino import carregar, exigir_revisao, atributos_configurados
from src.ml.modelos import CATALOGO, criar_modelos
from src.ml.metricas import avaliar, escolher_limiar
from src.ctgan import geracao as sinteticos''', BOOTSTRAP + '''
_dados = import_module("src.2_dados_treino")
ATRIBUTOS, CATEGORICAS, sha256 = _dados.ATRIBUTOS, _dados.CATEGORICAS, _dados.sha256
carregar, exigir_revisao, atributos_configurados = _dados.carregar, _dados.exigir_revisao, _dados.atributos_configurados
_modelos = import_module("src.2_catalogo_modelos")
CATALOGO, criar_modelos = _modelos.CATALOGO, _modelos.criar_modelos
_metricas = import_module("src.3_avaliar_modelos")
avaliar, escolher_limiar = _metricas.avaliar, _metricas.escolher_limiar
arquivo_resultados, marcar_selecionados = _metricas.arquivo_resultados, _metricas.marcar_selecionados
sinteticos = import_module("src.2_ctgan")
''')
experimentos = trocar(experimentos, 'src/configuracoes/treinamento.json', 'src/configuracoes/2_treinamento.json')
experimentos = trocar(experimentos,
    'for pasta_codigo in [RAIZ / "src/ml", RAIZ / "src/dados", RAIZ / "src/ctgan"] for p in pasta_codigo.glob("*.py")',
    'for p in (RAIZ / "src").glob("*.py")')
salvar("2_treinar_modelos.py", experimentos)

for antigo, novo in [('dados.json', '1_dados.json'), ('treinamento.json', '2_treinamento.json')]:
    (SRC / 'configuracoes' / novo).write_text(ler('configuracoes/' + antigo), encoding='utf-8')

teste = (RAIZ / 'lixeira/tests/test_novo_pipeline.py').read_text(encoding='utf-8')
comeco = teste.index('from src.dados.preparar_dados')
fim = teste.index('\n\n\ndef fontes_fixture')
teste = teste[:comeco] + '''from importlib import import_module
preparacao_mod = import_module("src.1_preparar_dados")
pln_mod = import_module("src.1_pln")
dados_mod = import_module("src.2_dados_treino")
treino_mod = import_module("src.2_treinar_modelos")
ctgan_mod = import_module("src.2_ctgan")
metricas_mod = import_module("src.3_avaliar_modelos")
construir_merge, engenharia = preparacao_mod.construir_merge, preparacao_mod.engenharia
estatisticas_vendedores = preparacao_mod.estatisticas_vendedores
atribuir_transportadoras = preparacao_mod.atribuir_transportadoras
confiabilidade_vendedor = preparacao_mod.confiabilidade_vendedor
preencher_atrasos_pln = preparacao_mod.preencher_atrasos_pln
comentarios, rotular_texto = pln_mod.comentarios, pln_mod.rotular_texto
avaliar = metricas_mod.avaliar
ATRIBUTOS, sha256 = dados_mod.ATRIBUTOS, dados_mod.sha256
exigir_revisao, validar_tabela, carregar = dados_mod.exigir_revisao, dados_mod.validar_tabela, dados_mod.carregar
executar, treinar = treino_mod.executar, treino_mod.treinar
montar_particao, assinaturas = treino_mod.montar_particao, treino_mod.assinaturas
ajustar, amostrar = ctgan_mod.ajustar, ctgan_mod.amostrar
''' + teste[fim:]
teste = trocar(teste, "patch('src.ml.experimentos.preparar')", "patch.object(treino_mod, 'preparar')")
teste = trocar(teste, "patch('src.ml.experimentos.treinar')", "patch.object(treino_mod, 'treinar')")
teste = trocar(teste, "patch('src.ml.experimentos.sinteticos.ajustar',", "patch.object(ctgan_mod, 'ajustar',")
teste = trocar(teste, "patch('src.ml.experimentos.sinteticos.amostrar',", "patch.object(ctgan_mod, 'amostrar',")
(RAIZ / 'tests').mkdir(exist_ok=False)
(RAIZ / 'tests/test_pipeline.py').write_text(teste, encoding='utf-8')
print('Criados:', *(str(p.relative_to(SRC)) for p in sorted(SRC.rglob('*')) if p.is_file()), sep='\n')
