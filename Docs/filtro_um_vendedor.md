# Filtro de exatamente um vendedor

Pedidos brutos: 99441; duplicados: 0.

| Sellers | Pedidos | % bruto | No prazo | Atrasados | Sem rótulo |
|---|---:|---:|---:|---:|---:|
| 0 | 775 | 0.7794% | 0 | 0 | 775 |
| 1 | 97388 | 97.9355% | 87387 | 7808 | 2193 |
| >=2 | 1278 | 1.2852% | 1257 | 18 | 3 |

| Split | Situação | Pedidos | % split original | No prazo | Atrasados | Prevalência |
|---|---|---:|---:|---:|---:|---:|
| treino | antes | 41173 | 100.0000% | 39022 | 2151 | 5.2243% |
| treino | mantidos | 40710 | 98.8755% | 38565 | 2145 | 5.2690% |
| treino | excluidos | 463 | 1.1245% | 457 | 6 | 1.2959% |
| validacao | antes | 24667 | 100.0000% | 21802 | 2865 | 11.6147% |
| validacao | mantidos | 24337 | 98.6622% | 21479 | 2858 | 11.7434% |
| validacao | excluidos | 330 | 1.3378% | 323 | 7 | 2.1212% |
| teste | antes | 25550 | 100.0000% | 23967 | 1583 | 6.1957% |
| teste | mantidos | 25120 | 98.3170% | 23539 | 1581 | 6.2938% |
| teste | excluidos | 430 | 1.6830% | 428 | 2 | 0.4651% |

Pedidos multi-item com um seller na fonte: 8525.
Entregas no mesmo dia cuja definição difere do legado: 1292.
Rótulo deste relatório: entrega ao cliente > promessa, comparando timestamps; nenhum rótulo simulado.
Cortes temporais preservados, com purga por disponibilidade do rótulo. Ver auditoria.json para exclusões sequenciais, hashes e comparação com legado.
A base é retrospectiva de entregues; a purga pode reduzir representação de entregas demoradas.
