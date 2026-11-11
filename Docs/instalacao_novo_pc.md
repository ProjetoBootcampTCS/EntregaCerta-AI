# EntregaCerta AI — instalação em um novo computador

Guia para executar a aplicação no Windows, com o frontend, PostgreSQL, modelo de ML e assistente Gemini. Referência: branch `rnn-train`, em 11/11/2026.

Não é necessário treinar o modelo novamente: a aplicação carrega os arquivos salvos na pasta `Modelos`.

## 1. Instalar os programas

- [Git para Windows](https://git-scm.com/install/windows).
- [Visual Studio Code](https://code.visualstudio.com/docs/setup/windows).
- [Python Install Manager](https://www.python.org/downloads/windows/).
- [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), seguindo os requisitos de WSL 2 do instalador.

Reinicie o computador se algum instalador solicitar. Depois, abra um novo PowerShell e instale o Python 3.12:

```powershell
py install 3.12
py -3.12 --version
git --version
docker compose version
```

O comando `py install` é do Python Install Manager. Se já houver Python 3.12 instalado e `py -3.12 --version` funcionar, não é necessário instalá-lo novamente.

Não é necessário instalar PostgreSQL separadamente: ele será executado pelo Docker.

## 2. Clonar a branch correta

No PowerShell, entre na pasta em que deseja guardar o projeto e execute:

```powershell
git clone --branch rnn-train https://github.com/ProjetoBoocampTCS/EntregaCerta-AI.git
cd EntregaCerta-AI
code .
git branch --show-current
```

O último comando deve mostrar `rnn-train`. As atualizações usadas neste guia estão nessa branch.

Se `code .` não funcionar, abra o VS Code manualmente e use **Arquivo → Abrir Pasta** para selecionar `EntregaCerta-AI`.

**Execute todos os comandos seguintes na raiz do projeto**, a pasta que contém `requirements.txt`, `compose.yaml`, `src` e `frontend`. No VS Code, abra **Terminal → Novo Terminal** e use PowerShell.

## 3. Criar o ambiente Python e instalar as dependências

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

A instalação pode demorar, principalmente por causa do PyTorch. Aguarde terminar antes de continuar.

O resultado esperado do último comando é `No broken requirements found.`. Isso confere as dependências instaladas; o funcionamento da aplicação será verificado nos próximos passos.

No VS Code:

1. Instale a extensão **Python**, da Microsoft.
2. Pressione `Ctrl + Shift + P`.
3. Procure **Python: Select Interpreter**.
4. Selecione o Python da pasta `.venv` do projeto.

Os comandos deste guia usam diretamente o Python da `.venv`, dispensando sua ativação pelo PowerShell. Para somente abrir a aplicação, não é necessário executar notebooks nem instalar as dependências experimentais de CTGAN.

## 4. Conferir os arquivos necessários

Confirme que estes arquivos vieram no clone:

```text
Dados/
  pedidos_ml.csv
  Brazilian Logistic/
    olist_order_reviews_dataset.csv
Modelos/
  preprocessador_rede.joblib
  rede_neural.pt
src/
  view_pedidos_inferencia.sql
```

Se algum estiver ausente, confira a branch e peça à equipe para disponibilizar a versão correspondente. Não substitua os modelos por arquivos de outro experimento.

## 5. Criar o arquivo de configuração

Na raiz do projeto, crie um arquivo chamado **`.env`**, sem a extensão `.txt`, e coloque:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=admin
POSTGRES_PASSWORD=SUBSTITUA_POR_UMA_SENHA_LOCAL
POSTGRES_DB=meu_banco

ENTREGACERTA_DATABASE_URL=

GEMINI_API_KEY=COLE_SUA_CHAVE_AQUI
GEMINI_MODEL=gemini-3.6-flash
```

- Troque `SUBSTITUA_POR_UMA_SENHA_LOCAL` por uma senha para o banco desse computador, antes de iniciar o contêiner pela primeira vez.
- Troque `COLE_SUA_CHAVE_AQUI` pela sua chave criada no [Google AI Studio](https://aistudio.google.com/apikey).
- `gemini-3.6-flash` é o identificador usado na configuração da equipe ao preparar este guia. Se não estiver disponível para sua chave, confirme um modelo disponível no AI Studio e ajuste `GEMINI_MODEL`.
- Deixe `ENTREGACERTA_DATABASE_URL` vazio neste procedimento: quando preenchido, ele tem preferência sobre as configurações `POSTGRES_*`.
- Não envie o `.env` ao GitHub nem compartilhe sua chave em prints. Cada colaborador configura seu próprio ambiente.

Sem uma chave válida, a aplicação deve informar a indisponibilidade do assistente. As consultas e previsões de ML não dependem dessa chave.

## 6. Iniciar o PostgreSQL

Abra o Docker Desktop e espere o mecanismo do Docker iniciar. Depois, no terminal do projeto:

```powershell
docker compose up -d postgres
docker compose ps
docker compose exec -T postgres pg_isready -U admin -d meu_banco
```

O contêiner deve aparecer como `Up` e a última verificação deve informar `accepting connections`. Se ainda estiver iniciando, aguarde alguns segundos e repita a verificação.

A aplicação usa a porta **5433** do computador, ligada à porta **5432** dentro do contêiner.

## 7. Carregar os dados no banco

**Faça esta etapa na instalação inicial. O script substitui os dados das tabelas que carrega; não o execute a cada abertura do site.**

```powershell
.\.venv\Scripts\python.exe -m src.carregar_postgresql
```

Aguarde a mensagem `Carga concluída`, com as quantidades carregadas. O script cria e preenche as tabelas de pedidos, clientes, logística, pagamentos, qualidade dos dados e avaliações.

Clonar o GitHub não copia o banco de dados existente no Docker de outro computador. Por isso, esta carga é necessária no novo ambiente.

## 8. Criar a view usada pela aplicação

Uma view é uma consulta salva no banco. Neste projeto, ela reúne e converte os campos necessários à inferência.

```powershell
Get-Content -Raw .\src\view_pedidos_inferencia.sql | docker compose exec -T postgres psql -U admin -d meu_banco -v ON_ERROR_STOP=1
```

O resultado esperado é `CREATE VIEW`. Essa etapa é necessária porque o script de carga não cria a view `public.vw_pedidos_inferencia`.

## 9. Testar o banco junto com o modelo

```powershell
.\.venv\Scripts\python.exe -m src.consultar_postgresql
```

O comando consulta os pedidos de validação, carrega o modelo salvo e gera os scores e a fila. O resultado esperado é:

```text
Consulta e previsao pelo PostgreSQL executadas!
Pedidos avaliados: ...
Pedidos na fila: ...
```

Confira as quantidades exibidas. Se ocorrer um erro, resolva-o antes de iniciar o site. Execute como módulo, usando `-m`, para que os imports relativos de `src` funcionem.

## 10. Abrir a aplicação

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

Deixe esse terminal aberto. No navegador, acesse:

- [Aplicação EntregaCerta AI](http://127.0.0.1:8000/).
- [Documentação da API](http://127.0.0.1:8000/docs), caso precise investigar uma requisição.

Confira se a página carrega, execute a análise de pedidos e envie uma pergunta no chat. O frontend é servido pelo próprio backend; abra pelo endereço acima.

O chat consulta o banco e executa a inferência antes de chamar o Gemini. Portanto, ele depende do banco e dos modelos funcionando, além da API generativa. A resposta pode demorar conforme a máquina, a rede e a disponibilidade do provedor.

Para encerrar o servidor, pressione `Ctrl + C` no terminal.

## 11. Como abrir nas próximas vezes

Depois da instalação inicial:

1. Abra o Docker Desktop e aguarde iniciar.
2. Abra a pasta do projeto no VS Code.
3. No terminal da raiz, execute:

```powershell
docker compose up -d postgres
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

4. Acesse [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

Não é necessário recriar a `.venv`, recarregar os dados nem treinar o modelo em cada abertura.

## Como receber atualizações da equipe

Antes de atualizar, salve seu trabalho e confira `git status`. Se houver alterações locais, preserve-as com a equipe antes de trocar de branch ou atualizar.

Com o servidor parado e na branch `rnn-train`:

```powershell
git branch --show-current
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Reinicie o servidor e atualize a página com `Ctrl + F5`. Se o Git informar conflito ou divergência, não use comandos de descarte: peça orientação à equipe.

## Problemas mais comuns

| Problema | O que conferir |
| --- | --- |
| `No module named google`, `psycopg` ou outra biblioteca | Instale `requirements.txt` da branch correta e execute pelo Python da `.venv`. |
| Docker não conecta | Abra o Docker Desktop, aguarde iniciar e execute `docker compose ps`. |
| Erro de conexão ou autenticação no PostgreSQL | Confira host, porta, usuário, senha, banco e se `ENTREGACERTA_DATABASE_URL` está vazio. Alterar a senha no `.env` não altera automaticamente a senha de um banco já criado. |
| `vw_pedidos_inferencia` não existe | Execute a etapa 8, depois de concluir a carga. |
| Erro ao consultar pedidos ou gerar inferência | Execute a etapa 9 e compartilhe o traceback completo, sem credenciais. |
| HTTP 500 em `/api/assistente` | Consulte o erro no terminal do Uvicorn. Pode ocorrer antes da chamada ao Gemini, durante consulta ou inferência. |
| Gemini retorna 503 ou 504 | Registre a mensagem do provedor e confira a configuração do modelo. Não significa, por si só, que o banco local esteja com problema. |
| Página continua na versão antiga | Confira a branch, atualize o código, reinicie o servidor e use `Ctrl + F5`. |

## Limites desta conferência

Os comandos e caminhos foram conferidos com o código atual do projeto. Este guia não foi executado como uma instalação limpa em outro computador.

O `requirements.txt` permite intervalos de versões. Assim, uma instalação nova pode receber versões diferentes das da máquina da equipe; isso exige atenção especial ao carregar modelos salvos. Se houver incompatibilidade, compare as versões com as usadas no treinamento antes de substituir os artefatos.
