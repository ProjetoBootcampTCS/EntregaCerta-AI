# Guia completo — dos CSVs originais à aplicação

Execute os comandos no **PowerShell, na raiz do projeto**: a pasta que contém
main.py, src, Notebooks e requirements.txt. No VS Code: **Terminal → Novo Terminal**.

- **Refazer o projeto do zero:** siga as etapas 1 a 10.
- **Abrir o sistema já preparado:** abra Docker Desktop e execute somente
  .\.venv\Scripts\python.exe main.py iniciar. Acesse http://127.0.0.1:8000.

A preparação e o treinamento gravam novas versões dos dados e modelos. Para uma
nova rodada, trabalhe em uma cópia de execução e preserve a versão anterior.
Os pontos 0/1 são cópias locais anteriores; não recebem alterações automaticamente.

## Ordem resumida

| Ordem | O que executar | Resultado |
|---|---|---|
| 1 | Instalar dependências na .venv | Ambiente Python |
| 2 | Colocar os nove CSVs Olist em Dados/Brazilian Logistic/ | Fonte original disponível |
| 3 | python -m src.preparar_dados | Consolidado: uma linha por pedido |
| 4 | python -m src.tratar_dados_ml --entrada Dados/pedidos_consolidados.csv | CSV tratado e matrizes |
| 4 — opcional | Notebooks/01_preparacao_dados.ipynb | Estudo e conferência didática |
| 5–6 | Notebook 02: reiniciar kernel e Executar tudo | Treino, avaliação, salvamento e conferência da inferência |
| 7 | Configurar .env e executar python main.py preparar-banco | PostgreSQL, view e tabelas web |
| 8 | python main.py criar-analista ... | Conta autorizada |
| 9 | python main.py verificar e testes | Integração conferida |
| 10 | python main.py iniciar | Aplicação aberta |

Na tabela, python significa o executável da .venv. Os comandos completos estão
abaixo. Não execute api.py, banco.py ou os módulos de acesso isoladamente pelo
botão “Run Python File”.

## 1. Preparar o ambiente

Tenha Git, VS Code, Python 3.12 e Docker Desktop. Use a versão organizada do
repositório, com main.py; alterações locais só aparecem no GitHub depois do envio
pela equipe.

Se .venv ainda não existir:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
~~~

Não recrie um ambiente que já funciona. Os comandos usam o Python da .venv
diretamente, sem precisar ativá-la.

No VS Code, selecione **Python: Select Interpreter → .venv**. Para os notebooks
01/02 e o experimento 03, escolha também **Selecionar Kernel → Python Environments → .venv**.
A .venv-ctgan é reservada aos experimentos: o pacote atual dados_ml.joblib foi
salvo com Pandas 3, enquanto o ambiente CTGAN usa Pandas 2.3.3.

## 2. Disponibilizar os CSVs originais

Extraia a base Olist recebida pela equipe. Os arquivos devem ficar diretamente
nesta pasta, sem outra pasta intermediária:

~~~text
Dados/Brazilian Logistic/
  olist_customers_dataset.csv
  olist_geolocation_dataset.csv
  olist_order_items_dataset.csv
  olist_order_payments_dataset.csv
  olist_order_reviews_dataset.csv
  olist_orders_dataset.csv
  olist_products_dataset.csv
  olist_sellers_dataset.csv
  product_category_name_translation.csv
~~~

Confira:

~~~powershell
Get-ChildItem -LiteralPath ".\Dados\Brazilian Logistic" -Filter *.csv
~~~

Fonte e condições de uso: [recebimento_dataset.txt](recebimento_dataset.txt).
Mantenha os originais sem alterações. Esta sequência usa dados reais, sem injeção
sintética. A consolidação usa sete tabelas; avaliações entram também na carga SQL,
e a tradução de categorias permanece como referência.

## 3. Consolidar os dados — primeiro script

~~~powershell
.\.venv\Scripts\python.exe -m src.preparar_dados
~~~

O script agrega itens e pagamentos antes das junções, calcula atributos logísticos
e alvos observados, confere chaves e totais e preserva os originais.

Produz:

- Dados/pedidos_consolidados.csv — consolidado, ainda com campos retrospectivos.
- Docs/validacao_dados.txt — contagens, verificações e hashes das fontes.

Referência atual: **99.441 pedidos, sem repetição de order_id**.
Não passe esse CSV inteiro ao modelo: ele contém datas do desfecho e alvos.

O notebook 02 encontra pedidos_consolidados.csv automaticamente. Se existir apenas
o nome antigo pedidos_consolidados_teste.csv, ele também é aceito; esse nome antigo
representa o consolidado completo, não a partição de teste. Não é necessário copiar
nem renomear o CSV. Use consolidado e matrizes da mesma rodada de preparação.

## 4. Limpar, dividir e transformar — segundo script

~~~powershell
.\.venv\Scripts\python.exe -m src.tratar_dados_ml --entrada ".\Dados\pedidos_consolidados.csv"
~~~

Seleciona pedidos com rótulos válidos, corrige distâncias, trata inconsistências,
separa os períodos e ajusta imputação, padronização e codificação **somente no
treino**. Este script prepara os dados; ainda não treina um classificador.

| Arquivo produzido | Uso |
|---|---|
| Dados/pedidos_ml.csv | Inspeção e carga PostgreSQL; categorias legíveis e metadados |
| Modelos/dados_ml.joblib | Matrizes X, alvos y, metadados e pré-processador |
| Docs/tratamento_ml.txt | Regras, exclusões, partições, versões e hashes |

Referência com os dados e regras atuais:

| Partição | Pedidos | Atrasos observados | Matriz X |
|---|---:|---:|---|
| Treino | 41.173 | 1.765 | 41.173 × 159 |
| Validação | 24.667 | 2.494 | 24.667 × 159 |
| Teste | 25.550 | 1.124 | 25.550 × 159 |
| Total | 91.390 | 5.383 | — |

A divisão usa aprovação e disponibilidade do rótulo: validação a partir de
01/01/2018, teste a partir de 01/05/2018. Investigue contagens diferentes; não
ajuste os dados apenas para forçar os números da tabela.

Confira os dados antes de treinar:

~~~powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_preparar_dados tests.test_tratar_dados_ml -v
~~~

### Onde entra o notebook 01?

Abra [01_preparacao_dados.ipynb](../Notebooks/01_preparacao_dados.ipynb) com kernel
.venv e execute de cima para baixo. Ele refaz a preparação didaticamente a partir
dos originais. Se pedidos_ml.csv e dados_ml.joblib existirem, compara e preserva
os arquivos; se houver divergência, interrompe. Se estiverem ausentes, pode criá-los.

**Não é uma terceira transformação obrigatória** depois dos scripts: serve para
estudar e conferir. Também pode substituir tratar_dados_ml na preparação didática,
mas a etapa 3 continua necessária para o consolidado usado no notebook 02.

## 5. Treinar e avaliar — notebook 02

Abra [02_treinamento_modelos.ipynb](../Notebooks/02_treinamento_modelos.ipynb) e:

1. Selecione o kernel **.venv**.
2. Clique em **Reiniciar kernel**.
3. Clique em **Executar tudo / Run All**.
4. Aguarde terminar e salve o notebook com suas saídas.

**Agora todas as células estão na ordem. Não pule células e não alterne com o
terminal.** A preparação das etapas 3 e 4 precisa estar concluída.

| Seção do notebook | O que acontece |
|---|---|
| 1 | Carrega matrizes, alvos e pré-processamento; confere tamanhos e identificadores |
| 2 | Treina o baseline que sempre escolhe a classe mais frequente |
| 3–4 | Treina e avalia regressão logística e HGB na validação |
| 5 | Treina a rede BCE, recupera a melhor época e mostra métricas/gráficos |
| 6 | Compara os três modelos na validação com filas de 5%, 10% e 20% |
| 7 | Aplica as configurações fixadas no teste e gera a tabela atual de comparação |
| 8–11 | Salva a rede, confere o tratamento e executa a inferência automaticamente |

A rede mantém camadas 128/64, dropout 0,1, semente 7 e AdamW com learning rate
0,0003. São até 150 épocas e paciência 50, monitorando **atrasos encontrados na
fila de 10% da validação**. A melhor época é recarregada ao terminar. A paciência
desse fluxo não monitora convergência da loss.

A configuração e a fila ficam definidas antes de consultar o teste. Não use o
teste para escolher novos hiperparâmetros. Ele já foi consultado em estudos
anteriores; a nova execução não o transforma em teste inédito. A tabela final é
calculada pelo código, sem precisar atualizar números manualmente em Markdown.

O backend continua usando a MLP. Comparar os modelos não troca automaticamente
o modelo da aplicação pelo vencedor. A fila de 10% deste fluxo não representa
a meta de recall 90%/95% dos estudos operacionais.

## 6. Salvamento e inferência — já incluídos em Executar tudo

As seções 8 a 11 do mesmo notebook produzem:

- Modelos/rede_neural.pt — pesos da rede.
- Modelos/preprocessador_rede.joblib — pré-processador e arquitetura correspondentes.
- Dados/pedidos_demo_validacao.csv — entrada da demonstração histórica.
- Dados/previsoes_demo_validacao.csv — scores e prioridades da rodada atual.

**Executar tudo substitui esse par de modelos e esses dois CSVs.** Preserve a
rodada anterior se quiser compará-la. O PostgreSQL não é alterado pelo notebook.
Reinicie a API após atualizar os modelos, pois ela mantém caches em memória.

A seção 11 chama src.inferencia em outro processo, usando o mesmo Python do kernel
e a raiz do projeto. Depois confere os mesmos pedidos, scores e prioridades.
O resultado esperado ao final é:

~~~text
Conferência final aprovada: mesmos pedidos, scores e prioridades!
~~~

Na base atual são 24.667 pedidos e 2.466 na fila. Essa mensagem comprova integração,
não qualidade preditiva; avalie Precision, Recall, F1, AP e as matrizes de confusão.
Se uma célula falhar, corrija a causa e reinicie a execução; não avance ignorando erros.

Não existe mais pausa obrigatória no terminal. Para repetir somente a inferência
depois que o par de modelos e a entrada de demonstração estiverem salvos, pode usar:

~~~powershell
.\.venv\Scripts\python.exe -m src.inferencia
~~~

### Experimentos separados

CrossEntropy, redução de atributos, PCA, coordenadas e diagnósticos estão em
[03_experimentos_rede_neural.ipynb](../Notebooks/experimentos/03_experimentos_rede_neural.ipynb).
Ele usa **.venv**, carrega os dados independentemente e também executa de cima para
baixo. São 16 treinos opcionais, por isso demora mais. Não é necessário executar
o 02 antes dele nem executar o 03 para abrir a aplicação. Seus resultados ficam
no notebook, sem sobrescrever os modelos, CSVs ou banco usados pelo site.

## 7. Configurar e carregar o PostgreSQL

### 7.1 Configurar o .env

Se ainda não existir, copie .env.example para .env e preencha:

- POSTGRES_USER, POSTGRES_PASSWORD e POSTGRES_DB.
- POSTGRES_HOST=localhost e POSTGRES_PORT=5433 para o Compose fornecido.
- ENTREGACERTA_DATABASE_URL: deixe vazio nesse caso; se preenchido, tem preferência.
- GEMINI_API_KEY e GEMINI_MODEL: para o assistente, com modelo disponível para sua
  chave. Sem GenAI, consultas, ML e relatório com resumo automático funcionam.

Preserve o .env existente se já configurado. Não publique esse arquivo nem os
ZIPs locais que o contêm.

### 7.2 Primeira carga

Abra Docker Desktop e aguarde iniciar:

~~~powershell
.\.venv\Scripts\python.exe main.py preparar-banco
~~~

O comando inicia PostgreSQL, chama a carga de src/banco.py quando o histórico
está vazio, cria a view de inferência e inicializa as tabelas web.

Lê **Dados/pedidos_ml.csv e o CSV original de avaliações**. Não carrega
dados_ml.joblib nem o CSV de previsões. Referência atual: 91.390 pedidos
distribuídos entre cinco tabelas e 99.224 avaliações.

Não execute banco.py, acesso_web.py ou arquivos SQL manualmente na instalação
normal: main.py preparar-banco coordena esses passos.

### 7.3 Se o banco já estava preenchido

preparar-banco **preserva o histórico existente**. Não substitui uma base antiga
apenas porque o CSV foi regenerado.

Se a intenção for explicitamente substituir o histórico por uma nova preparação,
preserve um backup do banco e, com PostgreSQL ligado, execute:

~~~powershell
.\.venv\Scripts\python.exe -c "from src.banco import carregar; print(carregar())"
.\.venv\Scripts\python.exe main.py preparar-banco
~~~

O primeiro comando substitui os dados históricos de pedidos, clientes, logistica,
pagamentos, qualidade_dados e avaliacoes. **Não é um comando diário.**
Loja e contas ficam no schema separado app_web.

Os pontos 0/1 são backups de arquivos, não do volume PostgreSQL.
Para PostgreSQL externo ou já iniciado fora do Compose, use
main.py preparar-banco --sem-docker.

## 8. Criar o analista

Com o banco preparado:

~~~powershell
.\.venv\Scripts\python.exe main.py criar-analista --nome "Nome do analista" --email "analista@equipe.com"
~~~

Digite uma senha de 12 a 128 caracteres e confirme. Ela não aparece no terminal.
Não existe conta/senha padrão. Crie uma conta por analista; se já existe,
utilize-a. O cadastro público na página cria clientes, não analistas.

## 9. Verificar a integração e executar testes

~~~powershell
.\.venv\Scripts\python.exe main.py verificar
.\.venv\Scripts\python.exe main.py testar --postgres
~~~

verificar consulta PostgreSQL e aplica o tratamento/modelo salvos. Na base atual:
91.390 pedidos na view, 24.667 na validação e 2.466 na fila.

testar --postgres inclui acesso, pedidos e integração em schemas temporários,
além da preparação de dados. Os testes de GenAI usam respostas controladas;
não confirmam disponibilidade da API externa.

Sem integração PostgreSQL, use main.py testar; os testes dependentes do banco
ficam explicitamente ignorados. Se uma conferência falhar, investigue a etapa
antes de continuar. Não remova assertions apenas para passar.

## 10. Abrir a aplicação

~~~powershell
.\.venv\Scripts\python.exe main.py iniciar
~~~

Acesse:

- **Página inicial:** http://127.0.0.1:8000
- **Loja/cliente:** http://127.0.0.1:8000/cliente
- **Entrar:** http://127.0.0.1:8000/entrar
- **Dashboard do analista:** http://127.0.0.1:8000/dashboard
- **Pedidos históricos do analista:** http://127.0.0.1:8000/pedidos

O comando inicia banco e API, que serve HTML/CSS/JS. Não abra o HTML direto,
não execute os JS individualmente e não rode api.py pelo botão do VS Code.

Mantenha o terminal aberto. **Ctrl+C** encerra a API; o banco continua ligado.
Para parar somente o banco: docker compose stop postgres.
Não use docker compose down -v para encerrar: a opção remove o volume.

Se modelo ou .env mudar, reinicie a API: ela mantém caches em memória.
Esta versão usa um processo; memória de conversas/PDFs é temporária, enquanto
contas e pedidos ficam no PostgreSQL.

**No próximo dia, basta Docker Desktop + main.py iniciar. Não repita os dez passos.**

## Pesquisa opcional

Consulte [experimentos/README.md](../experimentos/README.md) e
Notebooks/experimentos/. GAN, doses, históricos e previsão operacional usam
.venv-ctgan e não entram na sequência obrigatória. Notebooks/legado/ guarda
referências antigas.

Para conferir os testes da pesquisa, sem retreinar GANs:

~~~powershell
.\.venv-ctgan\Scripts\python.exe -B -m unittest discover -s experimentos/tests -v
~~~

Estudos de recall 90%/95% e despacho não substituem automaticamente o modelo web.
O fluxo acima mantém a MLP e a fila de 10%. A loja é demonstrativa: novos pedidos
ainda não recebem score; a análise de ML exibida usa reprodução histórica Olist.

## Problemas comuns

| Situação | Como resolver |
|---|---|
| No module named ... | Usar .venv/Scripts/python.exe e instalar requirements.txt nela |
| X_treino is not defined | Selecionar .venv, reiniciar kernel e usar Executar tudo no notebook 02 |
| attempted relative import | Usar python -m src.inferencia ou main.py na raiz |
| Consolidado ausente | Executar a etapa 3; pedidos_consolidados.csv é encontrado automaticamente |
| CSV de previsões ausente/divergente | Executar o notebook 02 inteiro; a seção 11 gera e confere a exportação |
| dados_ml.joblib não abre no kernel CTGAN | Usar .venv nos notebooks 01/02 e experimento 03; não misturar Pandas 3 e 2.3.3 |
| NameError após reiniciar kernel | As variáveis foram apagadas; retomar a sequência |
| Docker indisponível | Abrir Docker Desktop e conferir docker compose ps |
| Banco sem view/tabelas web | Executar main.py preparar-banco |
| CSV novo, banco antigo | Consultar a recarga explícita da etapa 7.3 |
| Porta 8000 ocupada | Encerrar a API antiga com Ctrl+C |
| Login recusado | Usar a conta de analista criada na etapa 8 |
| GenAI indisponível | Conferir chave/modelo no .env e reiniciar a API |

O notebook 02 confere unicidade diretamente, sem o parâmetro depreciado
verify_integrity. Uma exceção que interrompe a célula exige correção.

## Pontos de restauração

Na pasta irmã EntregaCertaAI_Pontos ficam ZIPs ponto 0/1 e manifestos SHA-256.
Incluem código, dados, modelos, .env, notebooks e estado local do Git.
Ambientes Python e volume PostgreSQL ficam fora dos ZIPs.

Para restaurar, encerre API e kernels, feche o projeto no VS Code e abra
PowerShell na pasta EntregaCertaAI_Pontos. Use o Python do sistema:

~~~powershell
py -3.12 restaurar_ponto.py ponto_0 --conferir
py -3.12 restaurar_ponto.py ponto_0 --aplicar
~~~

Troque ponto_0 por ponto_1 para a versão organizada. A pasta substituída fica
preservada com data/hora; ambientes locais são reaproveitados. Leia
COMO_RESTAURAR.txt junto aos backups. V1/V2 visuais estão no ponto 0.

## Escopo da conferência deste guia

A ordem foi confrontada com os scripts, os nomes dos arquivos e as células atuais.
O notebook 02 foi executado integralmente, com dados reais, em uma cópia isolada:
treino, avaliação, salvamento e conferência da inferência passaram sem erros.
As saídas dessa verificação foram mantidas no notebook. Os modelos e CSVs usados
pela aplicação foram preservados; ao executar o notebook no projeto, os arquivos
indicados na etapa 6 serão substituídos. A preparação completa e a carga do banco
não foram repetidas nesta organização.
