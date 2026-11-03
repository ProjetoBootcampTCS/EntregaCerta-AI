# Preparação e validação do ambiente

Etapa 2. Python **3.12**, ambiente virtual independente. No computador atual, o comando global `python` aponta para outra versão; indicar explicitamente um executável 3.12 no setup. Não usar o ambiente do protótipo CreditCare.

Na pasta do projeto, em PowerShell:

```powershell
.\scripts\setup.ps1 -PythonExecutable "CAMINHO_DO_PYTHON_3_12\python.exe"
.\.venv\Scripts\python.exe -m entregacerta.cli doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/validate_planning.py
```

O setup cria `.venv`, instala `requirements.lock` e o pacote local sem resolver dependências novamente, preserva `.env` existente e executa `pip check`/diagnóstico. Temporários e cache ficam em `.local/`, ignorado pelo Git. Não é preciso ativar o venv ao usar os caminhos acima. A política PowerShell deve permitir executar scripts locais; como alternativa, executar manualmente os comandos Python do script, sem alterar a política global.

`pyproject.toml` declara dependências diretas e limites; `requirements.lock` fixa as versões efetivamente instaladas, inclusive ferramentas de construção. Lock desta etapa verificado em Windows com Python 3.12.14. Não presumir reprodução em Linux antes da validação dos containers na etapa 7. O lock não usa hashes de pacotes e não constitui certificação de segurança das dependências.

## Configuração

Copiar `.env.example` para `.env` se o setup ainda não o tiver feito. Configurar `ENTREGACERTA_DATASET_ZIP` com o caminho do ZIP recebido. Neste computador, isso já foi preenchido localmente; esse caminho não entra no Git. Os outros caminhos são relativos à raiz do projeto. Campos da API de LLM permanecem vazios até a etapa 5. Não colar chaves na conversa nem em arquivos versionados.

Precedência: variáveis do processo sobre `.env`, depois os padrões. Backend e frontend devem usar portas distintas; timeout deve estar entre 0 (exclusivo) e 120 segundos. A chave não aparece no `repr` da configuração nem no diagnóstico, que informa somente sua presença.

Portas planejadas: API 8000; frontend 8502; prévia documental 8766. **Ainda não existem página de negócio, servidor FastAPI, modelo treinado ou comando de previsão nesta etapa.** O diagnóstico e os testes executam ferramentas de planejamento.

## Diagramas

```powershell
.\.venv\Scripts\python.exe scripts/build_diagrams.py
.\.venv\Scripts\python.exe scripts/preview_diagrams.py
```

Abrir `http://127.0.0.1:8766/` no navegador e conferir “Advertências: 0”. O visualizador é local e funciona com os assets já incluídos; não requer API. Ao abrir, salva exportações de validação. Encerrar o servidor com `Ctrl+C`. Os arquivos fonte e o SQL permanecem editáveis. Para apenas consultar, abrir os SVGs em `docs/diagramas/`.

O script `acquire_planning_assets.py` permite obter novamente os schemas OMG e os assets bpmn-js em suas fontes públicas, com manifesto SHA-256. Isso não adquire datasets e não implementa o sistema.

## Ferramentas externas e reprodução

Git foi verificado; versionamento do projeto é local. Docker client foi encontrado, mas o Engine não respondeu (pipe ausente). Terraform não foi encontrado no PATH. Nenhuma infraestrutura foi provisionada. Esses resultados são diagnósticos separados, registrados em `docs/validacao/ambiente.json`; não impedem concluir o planejamento, mas precisam ser resolvidos para a etapa 7.

Uma segunda instalação limpa foi usada para verificar o lock desta etapa; as evidências efetivas estão em `ETAPA_2_RESULTADOS.md`. Instalar dependências não comprova que modelos e interface futuros funcionam. Importações, testes técnicos e diagramas são a cobertura atual.
