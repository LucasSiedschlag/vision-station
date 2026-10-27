# Lista de conferência da bancada — saída da Fase 1

Para o Mantenedor (VIA-0117, que cumpre a VIA-0016). Serve para **mostrar** que a Fase 1 está pronta, e não para supor. Critério de saída (documento 01 §7): *um job feito na tela, exportado, restaurado em outro PC e verificado; PASS/FAIL ao vivo na bancada*, com a C920.

Marque cada item, anote a data, o PC e o que viu. Um item sem marca não foi conferido.

## O que já é conferido sozinho

O cenário `frontend/e2e/exit-scenario.spec.ts` (`npm run e2e`) faz, numa estação simulada, a parte que **não precisa de um segundo PC**: cria um job no editor (referência, ferramenta, amostra boa, validação), salva, exporta o `.vjob`, importa numa instalação limpa, ativa (com a verificação da regra 4) e vê **APROVADO** e **REPROVADO** na tela do operador, cada objeto contado uma vez.

Ele **não** prova a visão nem a câmera: o resultado vem de uma inspeção simulada que o teste controla. Tudo que depende do PC real, da C920 e do tempo está abaixo.

## 0. Antes de começar

- [ ] PC da estação com o instalador da versão a conferir (`docs/guias/instalacao.md`); anote a versão em **Sobre**.
- [ ] Segundo PC (ou uma pasta de dados vazia no mesmo PC, em outra porta) para a restauração.
- [ ] C920 ligada, iluminação da bancada ligada, a peça de teste à mão.
- [ ] **Configurações → Desempenho → Rodar teste de desempenho** (ou `vision-station --benchmark`): anote o nível (M ou R) e se o disparo ocioso ficou dentro do limite.

## 1. Um job feito na tela (FR-JOB, UC-01)

- [ ] **Jobs → Novo job**: câmera aplicada, disparo escolhido, **imagem de referência** capturada, ao menos uma ferramenta, **amostra Boa** e **amostra Ruim** capturadas.
- [ ] **Validar tudo**: todas as amostras com o resultado esperado.
- [ ] **Salvar**: a versão 1 aparece em **Jobs**.
- [ ] **Ativar**: a verificação passa. *Sem imagem de referência ou sem conjunto de referência a ativação é recusada* (regra 4): confira que a recusa mostra o motivo.

## 2. PASS e FAIL ao vivo na bancada (UC-02, UC-03)

- [ ] Peça boa na área: **APROVADO**, contada **uma vez** (não uma por imagem).
- [ ] Tire a peça: a tela volta a aguardar sozinha.
- [ ] Peça com defeito conhecido: **REPROVADO** com o motivo e as marcações sobre a imagem.
- [ ] Cubra a câmera ou tire a luz: **ERRO**, nunca aprovado.
- [ ] Anote o tempo por inspeção (coluna **Duração** em **Resultados**): mediana e pior caso.

## 3. Exportar e restaurar em outro PC (UC-05, NFR-REL-4, NFR-REL-5)

- [ ] No PC da estação: **Jobs → ⋯ → Exportar .vjob** e **Fazer backup** (`docs/guias/backup-e-restauracao.md`); copie os arquivos para fora do PC.
- [ ] No outro PC (instalação nova): importe o `.vjob` e restaure o `.vbak`; defina as senhas de novo (o backup não as guarda).
- [ ] **Ativar** o job lá: a verificação passa **sem ajuste manual**, com a mesma imagem de referência e o mesmo conjunto de referência.
- [ ] Os resultados nas imagens do conjunto de referência são **os mesmos** do PC original (NFR-REL-5).
- [ ] Cronometre: da instalação nova até o job ativo e verificado, **no máximo 1 hora** (NFR-REL-4). Tempo: ______

## 4. Câmera desligada e religada (UC-09, NFR-REL-3)

- [ ] Com a estação inspecionando, **tire o cabo USB**: aparece *Câmera desconectada*, e nenhuma inspeção é dada como boa.
- [ ] Religue: a estação volta a inspecionar **sozinha em até 30 s** (NFR-REL-3). Tempo: ______
- [ ] Ao abrir a estação com a câmera já ligada, a tela mostra **Preparando…** (e não *câmera perdida*) até a câmera abrir.

## 5. Reiniciar o PC com o serviço (UC-10, NFR-REL-2)

- [ ] Com um job ativo, reinicie o PC (ou tire a energia) **sem entrar no Windows**.
- [ ] A estação volta a inspecionar com o **último job ativo**, sem ninguém tocar, **em até 2 min** (NFR-REL-2). Tempo: ______
- [ ] A tela mostra o job certo e os contadores do dia continuam.

## 6. Um turno sem parar (NFR-REL-1)

- [ ] Deixe a estação inspecionando por **um turno inteiro (proposta: 10 h)**, com peças reais ou repetindo a mesma.
- [ ] Sem reiniciar, sem erro de gravação, sem travar a tela; a pasta de dados não encheu o disco.
- [ ] Os resultados do turno estão em **Resultados**; o tempo por inspeção no fim é parecido com o do começo.
- [ ] Nenhum PASS contado para uma peça que não estava lá.

## Quando terminar

Guarde esta lista preenchida com o relatório do teste de desempenho (`system/benchmark.json`) e o resultado do `npm run e2e`. Cada item **não** marcado vira uma tarefa, com o motivo.
