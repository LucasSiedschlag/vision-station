# Guia do operador — Vision Station

Uma página. A tela mostra se a peça está boa e, se não estiver, por quê.

## A tela

```
┌──────────────────────────────────────────────────────────────┐
│ Nome do job  v7                                    Entrar    │
│                                    │      ✔                  │
│        IMAGEM DA CÂMERA            │   APROVADO              │
│                                    │   motivo, quando falha  │
│                                    │ Últimos: ✔ ✔ ✘ ✔        │
│                                    │ Hoje: total · ✔ · ✘ · ! │
│                                    │ [Inspecionar agora]     │
│ ● Sistema  ● Câmera  ● Registro             Aguardando peça  │
└──────────────────────────────────────────────────────────────┘
```

## O que cada resultado quer dizer

| Na tela | Cor | O que fazer |
|---|---|---|
| **Aguardando…** | cinza | Coloque a peça no lugar e deixe parada. A foto é tirada sozinha |
| **Inspecionando…** | azul | Não mexa na peça |
| **APROVADO** | verde | Pode seguir |
| **REPROVADO** + motivo | vermelho | Corrija o que o motivo diz (ex.: "Tampa ausente") e coloque a peça de novo. Ela é inspecionada outra vez |
| **ERRO** + motivo | amarelo | O sistema **não conseguiu** conferir (imagem escura, peça fora do lugar, câmera). **Não é aprovado.** Ajuste e tente de novo; se repetir, chame a manutenção |
| **Câmera desconectada** | amarelo | Chame a manutenção. Nada é aprovado enquanto isso |

A palavra (APROVADO, REPROVADO, ERRO) vem sempre junto da cor.

## Botões

- **Inspecionar agora:** tira a foto na hora, sem esperar a peça ficar parada. Só funciona quando a tela diz *Aguardando*.
- **Resultado incorreto?:** se o sistema errou (disse REPROVADO para uma peça boa, ou o contrário), toque aqui e diga qual era o certo. A imagem vai para melhorar o sistema. Não muda o que já aconteceu.
- **Entrar:** só para Supervisor e Mantenedor.

## Os pontos no rodapé

- **Sistema**, **Câmera**, **Registro**: verde está tudo bem. Amarelo ou vermelho: avise a manutenção.
- **Hoje:** quantas peças, aprovadas, reprovadas e erros desde o início do turno.
