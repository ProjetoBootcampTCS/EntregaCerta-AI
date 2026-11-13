# Laboratório CTGAN: cenário logístico simulado

Este experimento reproduz a **proposta** da conversa compartilhada: atributos Olist,
transportadoras fictícias, regras de risco configuráveis e aumento do treino com
CTGAN. O código completo e resultados reproduzíveis da referência não estavam
disponíveis; portanto, não se trata de replicação numérica de um resultado dela.

**Um bom resultado para `atrasou_simulado` mostra aprendizado das regras que nós
criamos. Não demonstra que o modelo prevê os atrasos reais da Olist com a mesma
qualidade.** `atrasou_observado` permanece separado e preservado.

## 1. Abrir e executar

Na raiz do projeto, use o ambiente separado `.venv-ctgan`. Ele evita mudar as
dependências da aplicação web. PostgreSQL deve estar acessível pelo `.env`; os
CSV originais devem estar em `Dados/Brazilian Logistic/`, e a consolidação em
`Dados/pedidos_consolidados_teste.csv`. O banco é consultado em modo somente leitura.
Nenhuma tabela de produção ou modelo da aplicação é substituído.

Se esse ambiente ainda não existir em outro computador:

```powershell
py -3.12 -m venv .venv-ctgan
.\.venv-ctgan\Scripts\python.exe -m pip install -r requirements-ctgan.txt
```

Para gerar os dados, treinar os classificadores e produzir as avaliações:

```powershell
.\.venv-ctgan\Scripts\python.exe -m src.simulacao_logistica --etapa tudo
```

O treinamento da CTGAN em CPU pode demorar. O gerador fica em cache e é reutilizado
quando os atributos de treino, a implementação da geração e seus parâmetros não
mudam. Alterar apenas a quantidade de amostras não exige treinar a GAN novamente.
Reprodutibilidade exige também os mesmos dados, versões e sementes; não se promete
igualdade bit a bit entre hardwares ou versões diferentes.

No VS Code, abra `Notebooks/06_cenario_logistico_ctgan.ipynb` e selecione o kernel
`.venv-ctgan`. Ele carrega os resultados, confere previsões salvas e mostra gráficos.
Por padrão, não repete um treinamento caro. Há uma opção explícita para executar
o pipeline inteiro pelo notebook.

## 2. O que é configurável

| Arquivo | O que controla |
|---|---|
| `configuracoes/cenario_logistico.json` | Regras, transportadoras, intensidade do sinal, ruído, sementes e taxa-alvo |
| `configuracoes/geracao_ctgan.json` | Quantidade por partição, épocas, tamanho do lote e semente da CTGAN |

A configuração inicial gera **30.000 pedidos sintéticos no treino**, zero na
validação e zero no teste. São pedidos de ambas as classes, não 30 mil atrasos.
O limite é 30 mil por partição neste laboratório. Ele é independente do experimento
anterior que aumentava apenas os atrasos e tinha limite de 10 mil.

As sementes são números que controlam a aleatoriedade. Não significam risco baixo,
médio ou alto. Os coeficientes em `influencias` definem hipóteses: positivos aumentam
o risco e negativos reduzem, após transformações ajustadas no treino. Não são
coeficientes descobertos causalmente nos dados reais. `intensidade_sinal` amplia
essas diferenças; aumentá-la torna a regra mais previsível, sem melhorar por si só
a previsão dos atrasos observados.

`taxa_atraso_alvo` é aproximadamente 1/6 no treino. Não se marca automaticamente
cada sexto pedido. Ajusta-se o intercepto de uma função logística e sorteia-se o
desfecho conforme sua probabilidade. O mesmo intercepto é aplicado à validação e
ao teste: suas taxas podem mudar. Existe ruído e incerteza mesmo no cenário.

Transportadoras são `SIM_A`, `SIM_B` e `SIM_C`. A configuração padrão associa uma
transportadora a cada vendedor; `vinculo_transportadora: "pedido"` permite variar
por pedido. O filtro implementado aceita somente pedidos com **um vendedor**,
podendo conter vários itens. Outros filtros requerem implementação adicional.

Para usar uma cópia de configuração:

```powershell
.\.venv-ctgan\Scripts\python.exe -m src.simulacao_logistica --etapa tudo --cenario configuracoes/meu_cenario.json --geracao configuracoes/minha_geracao.json
```

## 3. Dados, rótulos e prevenção de vazamento

1. Consulta o snapshot PostgreSQL já dividido temporalmente. Treino anterior a
   janeiro/2018, validação anterior a maio/2018 e teste posterior, mantendo os
   filtros de disponibilidade de rótulos da preparação original.
2. Confere o atraso observado contra as datas de entrega e promessa da base
   consolidada, comparadas por dia. Exclui pedidos com mais de um vendedor.
3. Acrescenta coordenadas medianas por prefixo de CEP, distância geodésica,
   características dos itens e histórico de avaliações do vendedor disponível
   estritamente antes da aprovação de cada pedido. A avaliação do próprio pedido
   não pode entrar em sua previsão. A nota inicial neutra é 3, com peso de duas
   avaliações fictícias apenas como suavização matemática.
4. Atribui transportadoras e avaliações **simuladas** de qualidade. A nota de cada
   evento é sorteada em torno da média configurada da transportadora; sua
   disponibilidade é simulada após o prazo prometido mais um dia. Esses eventos
   não são avaliações reais de transportadoras nem resultados logísticos medidos.
5. Aprende no treino um valor esperado de frete a partir de distância, peso,
   volume e quantidade de itens. O desvio logarítmico do frete em relação ao
   esperado é uma entrada da regra e dos classificadores.
6. Ajusta a CTGAN exclusivamente nos atributos do treino e gera novas linhas.
   Os alvos não entram na GAN. O alvo simulado é calculado depois pelas mesmas
   regras congeladas. IDs sintéticos começam por `SIM-`; seu alvo observado fica
   vazio. Datas reais, vendedor real e trajetória temporal não são inventados
   para esses pedidos.
7. Compara Dummy, regressão logística e HGB em três experimentos: atraso observado
   sem injeção; alvo simulado sem CTGAN; alvo simulado com CTGAN. O limiar maximiza
   F1 na validação; o modelo é escolhido pelo F1 de validação, com AP como desempate.
   O teste não escolhe limiar, modelo ou regras.

As entradas permitidas estão em `ATRIBUTOS`, no arquivo `dados.py`. IDs, rótulos,
origem, `probabilidade_regra` e faixas de risco não são atributos preditivos.
Transportadora e sua reputação simulada também são excluídas do experimento com
alvo observado. Imputação, escala e categorias são aprendidas somente no treino
Olist e compartilhadas pelos dois braços simulados.

Históricos dos pedidos Olist podem se atualizar ao longo da validação/teste com
eventos que já estavam disponíveis na aprovação de cada novo pedido. Isso simula
consulta operacional do passado; não permite consultar eventos futuros. O histórico
de reputação dos pedidos gerados pela GAN é apenas um atributo sintético.

## 4. Onde encontrar os resultados

`Modelos/experimento_simulacao/ultima_execucao.txt` indica o identificador da
preparação mais recente. As pastas recebem um hash de dados, configurações e código.
Uma preparação interrompida pode existir sem métricas: confira a conclusão do comando.

- `Dados/simulacao_ctgan/<id>/pedidos_cenario_e_injetados.csv`: dados legíveis,
  separados pelas colunas `particao`, `origem_dado` e pelos dois alvos.
- `Modelos/experimento_simulacao/<id>/manifesto.json`: parâmetros, fontes, versões
  e hashes da execução.
- `metricas.csv`, `previsoes.csv` e `selecionados_na_validacao.csv`: evidência das
  avaliações, previsões individuais e critério de seleção.
- `qualidade_sinteticos.csv`: distâncias KS numéricas e TVD categóricas, médias e
  proporções de nulos. Valores maiores de KS/TVD indicam maior diferença marginal.
- `duplicatas_sinteticas.txt`: duplicações exatas, sem equivaler a garantia de
  privacidade ou ausência de memorização aproximada.
- `perdas_ctgan.csv`: histórico da GAN. Perdas do gerador/discriminador não medem
  diretamente realismo dos dados nem qualidade do classificador.
- `modelo_*.joblib` e gráficos PNG: pipelines completos e figuras para inspeção.

Os arquivos volumosos são locais e ignorados pelo Git. Carregue somente arquivos
Joblib que vocês próprios geraram ou cuja origem seja confiável.

Validação e teste sintéticos opcionais aparecem como
`CTGAN_DIAGNOSTICO_NAO_INDEPENDENTE`: derivam do mesmo gerador/regra e não constituem
evidência independente. O notebook padrão usa exclusivamente pedidos Olist
reservados para avaliar os dois braços simulados, com seus **alvos simulados**.

## 5. Como interpretar sem exagerar os resultados

F1 combina precisão e recall; acurácia isolada é insuficiente. AP avalia a ordenação
dos scores e depende da frequência da classe. A fila de 10% mede uma política
operacional diferente do limiar escolhido por F1. Brier e curvas de calibração
avaliam a correspondência entre scores e frequência do respectivo alvo.

O ganho atribuível à CTGAN é a diferença **com versus sem CTGAN para o mesmo alvo
simulado, mesmas partições e algoritmo**. Comparar seu F1 ao F1 do atraso observado
não mede ganho da GAN: são problemas diferentes. Uma execução com uma semente é
exploratória e não comprova estabilidade estatística.

As limitações incluem registros antigos e apenas pedidos elegíveis/entregues,
exclusão de pedidos com múltiplos vendedores, CEP aproximado, histórico de avaliação
do pedido como proxy da qualidade do vendedor e ausência de eventos reais de
transportadora. Os campos monetários e de pagamento são tratados como informações
disponíveis na aprovação, hipótese que requer validação em um sistema operacional.

Nos sintéticos, quantidades e limites físicos recebem correções, e coordenadas são
associadas a localizações observadas no treino dentro da UF gerada. A distância é
um atributo gerado: sem endereço de origem sintético, ela não comprova uma rota
física consistente. `valor_pago = valor_itens + valor_frete` assume ausência de
descontos. Plausibilidade dessas regras não torna os registros observações reais.

O conjunto de teste Olist já foi consultado em experimentos anteriores da equipe;
esta avaliação retrospectiva não é um novo teste intocado. Não ajustar novamente
as regras para perseguir seu resultado. Para avaliar melhoria real, retornar ao
alvo observado e a um protocolo independente predefinido.

## 6. Conferências e referências

```powershell
.\.venv-ctgan\Scripts\python.exe -m unittest tests.test_simulacao_logistica -v
```

Os testes usam fixtures artificiais apenas para verificar regras, datas, atributos
proibidos, limites, coerência e métricas de grupos pequenos. O notebook também
recarrega os pipelines e confere os scores contra o CSV da execução.

- [Proposta compartilhada](https://chatgpt.com/s/cx_6af5e63747a48191915d29e4c1cdad3c)
- [Implementação oficial CTGAN](https://github.com/sdv-dev/CTGAN)
- [Documentação CTGAN/SDV](https://docs.sdv.dev/sdv/single-table-data/modeling/synthesizers/ctgansynthesizer)
- [Prevenção de vazamento — Scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html)

## Resultado executado em 13/11/2026

Execução `7ca2a1faf2c49a6b`: 90.167 pedidos Olist com um vendedor, sendo 40.710
de treino, 24.337 de validação e 25.120 de teste; mais 30.000 pedidos CTGAN no
treino. A CTGAN foi treinada por 100 épocas, semente 42; cenário semente 123;
classificadores semente 7. Nenhuma amostra sintética entrou na validação/teste.

Modelos selecionados na validação, avaliados no teste:

| Alvo e experimento | Modelo | Precision | Recall | F1 | AP |
|---|---|---:|---:|---:|---:|
| Atraso observado, sem injeção | Regressão logística | 7,19% | 76,67% | 13,15% | 0,0966 |
| Alvo simulado, sem CTGAN | HGB | 80,42% | 70,89% | 75,35% | 0,8554 |
| Alvo simulado, com CTGAN | HGB | 80,30% | 76,91% | 78,57% | 0,8795 |

No HGB simulado, o F1 aumentou 3,22 pontos percentuais. Foram encontrados 2.491
dos 3.239 atrasos simulados do teste, com 611 falsos positivos. Sem CTGAN, eram
2.296 encontrados e 559 falsos positivos. O ganho concentrou-se em recall; a
precisão ficou praticamente igual. Na regressão logística simulada, o F1 de teste
caiu de 71,36% para 71,16%: o aumento de dados não ajudou todos os algoritmos.

Os sintéticos tiveram 8.222 atrasos simulados em 30.000 pedidos (27,41%), enquanto
o treino Olist antes da injeção teve 6.786 em 40.710 (16,67%). O treino aumentado
ficou com 21,22%. As regras não foram recalibradas para forçar a taxa nos sintéticos.
Essa mudança da distribuição faz parte do experimento e deve ser considerada:
comparar também a reponderação das classes seria necessário para isolar melhor o
efeito do aumento de amostras.

A maior distância KS marginal foi 0,219 no prazo prometido; a nota histórica do
vendedor teve KS 0,210. A TVD das categorias de produto foi 0,110 e a das UFs,
0,094. Não foram detectadas duplicatas exatas entre os sintéticos nem em relação
ao treino. Isso não prova realismo conjunto ou privacidade.

O CSV possui 120.167 linhas, com origem/partição identificadas. As métricas completas,
limiares, matrizes e qualidade estão na pasta dessa execução. A previsão real
continua fraca: a simulação **não resolveu** o problema original dos atrasos Olist.
