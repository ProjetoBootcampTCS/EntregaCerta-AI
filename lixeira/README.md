# Arquivos fora do pipeline atual

Esta pasta preserva a organização anterior do pipeline de dados, CTGAN e treinamento,
incluindo estudos, configurações alternativas e seus testes. Não há exclusão definitiva.
`inventario.json` registra os hashes antes da reorganização; os arquivos de web,
assistente, banco, relatórios e EDA foram devolvidos aos seus caminhos originais.

O pipeline atual tem sete Python numerados na raiz de `src` e dois JSON em
`src/configuracoes`. Consulte `Docs/laboratorio_modelos.md` para executar.
O script de migração aqui arquivado é apenas registro; não deve ser executado novamente.

Os scripts arquivados podem depender dos caminhos e configurações anteriores.
O pré-processamento antigo ainda necessário à aplicação web permanece em
`src/experimentos/pipeline_anterior`, junto da inferência em `src/ml/inferencia.py`.
