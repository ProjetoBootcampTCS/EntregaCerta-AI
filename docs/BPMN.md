# Processo operacional em BPMN 2.0

Modelo documental (`isExecutable=false`): [processo.bpmn](diagramas/processo.bpmn), com elementos semânticos e posicionamento BPMN DI. Pode ser aberto em modelador compatível e editado na prévia local. Não representa um motor de workflow implementado.

O evento inicial é a aprovação. A aplicação consulta dados disponíveis, verifica qualidade, calcula escore e registra versão. Dados insuficientes seguem para registro de pendência humana, sem inventar previsão. Pedidos na fila prioritária passam por revisão do analista e registro da decisão; os demais recebem acompanhamento padrão. A capacidade é um parâmetro da fila diária, não uma certeza de atraso.

O analista escolhe se quer relatório. A API produz o texto fundamentado; um evento de erro anexado à tarefa representa chave ausente, timeout, indisponibilidade ou saída inválida. Nesse caminho, o sistema prepara um resumo factual com aviso. Ambos passam por conferência humana antes de salvar. Sem relatório solicitado, o caso termina com os registros anteriores.

Duas raias: **EntregaCerta AI** e **Analista de operações**, dentro de um único processo. Condições das decisões são documentação das regras da aplicação, não expressões vinculadas a um motor. As decisões binárias possuem fluxo padrão explícito. O diagrama não inclui a etapa offline de treinamento, mostrada na arquitetura.

Para abrir a prévia:

```powershell
.\.venv\Scripts\python.exe scripts/preview_diagrams.py
```

Abrir `http://127.0.0.1:8766/`. A página usa bpmn-js local, sem enviar o diagrama a um serviço externo. Ao importar, exporta SVG e XML de retorno para validar compatibilidade. O botão de download salva a edição no navegador; substituir o arquivo fonte exige revisão/versionamento. A exportação automática serve à validação e não substitui o modelo fonte.

Verificações: XSD oficial OMG local, referências de fluxos, cobertura nas raias, alcance de finais, BPMN DI e importação/exportação no bpmn-js. XSD válido não prova que o processo operacional já funciona; os testes de negócio pertencem às etapas posteriores. A evidência da execução está em `docs/validacao/`.

Referências: [OMG BPMN 2.0.2](https://www.omg.org/spec/BPMN/2.0.2/), [schemas oficiais](https://www.omg.org/spec/BPMN/20100501/BPMN20.xsd), [bpmn.io](https://bpmn.io/toolkit/bpmn-js/).
