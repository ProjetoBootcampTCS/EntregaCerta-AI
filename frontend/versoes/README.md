# Versões da interface

Registro de 09/11/2026. A versão ativa após esta atualização é a **V2**.

| Pacote | Conteúdo |
| --- | --- |
| `V1.zip` | Cópia exata do HTML, CSS e JavaScript anteriores: painel grafite/verde-lima, fila, filtros, detalhes e CSV. |
| `V2.zip` | HTML, CSS, JavaScript e logo SVG: painel lateral da futura GenAI, botão flutuante, entrada dos blocos na rolagem e nova identidade visual. |

A GenAI da V2 ainda não está conectada. O painel permite preparar e copiar um rascunho e consultar um resumo determinístico da análise carregada. Nenhuma pergunta é enviada e nenhuma resposta de IA é simulada. O rascunho dura somente enquanto esta página permanece aberta.

## Voltar para uma versão

No PowerShell, a partir da raiz `EntregaCertaAI`, execute **um** dos comandos abaixo. Eles substituem somente os arquivos da interface contidos no pacote. Preserve suas edições posteriores antes de restaurar.

Voltar à V1:

```powershell
Expand-Archive -LiteralPath .\frontend\versoes\V1.zip -DestinationPath .\frontend -Force
```

Voltar à V2:

```powershell
Expand-Archive -LiteralPath .\frontend\versoes\V2.zip -DestinationPath .\frontend -Force
```

Com a API local em execução, abra `http://127.0.0.1:8000/` e pressione **Ctrl + F5**. A V1 não usa o arquivo `logo.svg` que pode permanecer na pasta após uma restauração; isso não altera sua aparência.

Os pacotes são retratos fixos destas versões. Backend, modelos, notebooks e dados não fazem parte deles. O arquivo independente `entregacerta_heatmap_novo.html` foi preservado.

## Conferências da V2

- JavaScript passou em `node --check`; IDs do HTML e referências do script conferidos; logo validado como SVG/XML.
- Navegador em desktop e largura de 390 px: abertura/fechamento, Escape, ciclo de foco com Tab, rascunho, cópia e envio desabilitado conferidos.
- Cards ocultos antes da entrada na tela e visíveis após rolagem; pausa de movimento mantém o conteúdo legível.
- Consulta real retornou 24.667 pedidos e fila de 2.466; o contexto do assistente acompanhou a conclusão da consulta. Nenhum erro ou aviso foi registrado no console dessa verificação.
- V1 comparada byte a byte com os três arquivos anteriores antes da edição. V2 comparada byte a byte com os quatro arquivos ativos; ambos os ZIPs passaram na verificação de integridade.
