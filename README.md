# EntregaCerta AI

Projeto do Bootcamp TCS que combina dados reais da Olist, PostgreSQL, Machine Learning
e GenAI para apoiar a revisão humana de pedidos com risco de atraso. Interface em
HTML, CSS e JavaScript, com backend FastAPI e áreas de cliente e analista.

## Abrir o sistema

Abra o Docker Desktop. No terminal do VS Code, **na pasta deste README**, execute:

```powershell
.\.venv\Scripts\python.exe main.py iniciar
```

Acesse **http://127.0.0.1:8000**. Mantenha o terminal aberto; Ctrl+C encerra a API.
Esse comando inicia o PostgreSQL e a aplicação usando o modelo salvo. Não é preciso
executar notebooks, treinar modelos ou abrir arquivos de src individualmente.

**Do zero, incluindo dados e treinamento:** siga o [guia completo](Docs/instalacao_novo_pc.md).
Ele indica os scripts, a execução completa do notebook 02 com **Executar tudo**
e os passos de PostgreSQL, login e abertura da aplicação. Os estudos opcionais
ficam em `Notebooks/experimentos/03_experimentos_rede_neural.ipynb`.

## Comandos principais

Todos usam .\.venv\Scripts\python.exe main.py seguido da ação:

| Ação | Quando usar |
|---|---|
| iniciar | Abrir o sistema no dia a dia |
| preparar-banco | Primeira instalação ou atualização das tabelas web; preserva histórico já carregado |
| criar-analista --nome "Nome" --email "email@equipe.com" | Cadastrar analista; a senha é solicitada no terminal |
| verificar | Conferir conexão, consulta e inferência reais, sem alterar os dados |
| testar --postgres | Testar aplicação e integração com banco em schemas temporários |
| --help | Consultar a ajuda |

## Onde trabalhar

```text
main.py           Comandos para operar o projeto
src/              Backend, PostgreSQL, dados, inferência e GenAI
frontend/         Páginas, estilos, scripts e logo em uso
Dados/            CSVs originais e bases preparadas
Modelos/          Modelo da aplicação e evidências dos experimentos
Notebooks/        01: preparação; 02: treinamento principal
  experimentos/   CTGAN, históricos e comparações opcionais
  legado/         Estudos antigos preservados para consulta
experimentos/     Scripts, configurações e testes da pesquisa de ML
tests/            Testes da aplicação e da preparação de dados
Docs/             Guia, histórico técnico, proveniência, registros e BPMN
```

Para continuar a pesquisa, consulte o [índice dos experimentos](experimentos/README.md).
Os resultados, limitações e etapas realizadas estão no [registro técnico](Docs/desenvolvimento.md).
Os JSONs de experimentos/configuracoes controlam o cenário CTGAN; os arquivos
em Modelos registram modelos, parâmetros e resultados, por isso foram preservados.

## Limites atuais

- O dashboard faz reprodução histórica; o score é risco relativo, não probabilidade calibrada.
- A loja é demonstrativa, sem pagamento ou envio real. Seus novos pedidos ainda não recebem score de ML.
- O modelo web mantém a fila de 10% originalmente configurada. Os estudos de recall de 90%/95% são experimentos separados.
- O assistente exige configuração de API. Se ela falhar, consultas, ML e relatório com resumo automático continuam disponíveis.
- Métricas de cenários sintéticos não comprovam desempenho em atrasos reais.

## Pontos de restauração

**Ponto 0:** estado anterior à organização. **Ponto 1:** versão organizada.
As cópias locais ficam na pasta irmã EntregaCertaAI_Pontos, fora do repositório.
Veja a seção de restauração no [guia](Docs/instalacao_novo_pc.md). Dados e modelos
foram preservados; ambientes Python e volume PostgreSQL ficam fora dos ZIPs.

Fonte: Brazilian E-Commerce Public Dataset by Olist, registros anonimizados de
2016–2018. Proveniência e condições de uso em [recebimento_dataset.txt](Docs/recebimento_dataset.txt).
