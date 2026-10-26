# Guia de backup e restauração — Vision Station

Para o Supervisor (NFR-USA-3): dá para fazer sem o Mantenedor.

## O que o backup guarda

Um arquivo `.vbak` com:

- **todos os jobs**, com todas as versões (ou só a última de cada, se configurado);
- **qual versão estava ativa**;
- **a configuração da instalação** (`system.yaml`): câmera, backup, gravação, rede.

**Não** guarda: os resultados e as imagens das inspeções (são registros, não configuração; exporte em **Resultados → Exportar CSV**) e **as senhas** (por segurança; defina de novo depois de restaurar).

## Backup automático

Em **Configurações → Backup** (Mantenedor): a pasta (de rede ou pen drive), a frequência (padrão: a cada 24 h) e quantos guardar (padrão: 30; os mais antigos são apagados). Se o backup automático falhar, **Configurações** mostra o aviso e a **Auditoria** registra *Backup falhou*.

## Fazer um backup agora

1. **Entrar** como Supervisor.
2. **Jobs → Fazer backup.** Aparece o nome e o tamanho do arquivo, ex.: `backup_2026-10-15_1432.vbak (2,4 MB)`.
3. Para copiar para outro lugar: **Jobs → Backups…** → **Baixar** ao lado do arquivo.

Guarde uma cópia fora do PC da estação (pen drive ou rede).

## Exportar um job só

**Jobs → ⋯ → Exportar .vjob** (a última versão), ou na página do job, **Exportar .vjob** na versão desejada. Serve para levar um job para outra estação.

## Restaurar num PC novo (ou depois de uma pane)

1. Instale o Vision Station (guia de instalação) e defina a senha do Mantenedor.
2. Ligue a câmera **na mesma posição** de antes.
3. **Entrar → Jobs → Importar arquivo** e escolha o `.vbak`.
   - O sistema confere o arquivo inteiro antes: se estiver danificado, recusa e não muda nada.
   - Aparece o que entrou: versões *adicionadas*, *já existiam*, ou *renumeradas* (quando uma versão com o mesmo número e conteúdo diferente já existia aqui).
   - **Importar nunca ativa nada sozinho.**
4. Abra o job que estava ativo (o aviso diz qual) e clique **Ativar** na versão.
   - O sistema exige uma **imagem de referência** legível e confere o job no **conjunto de referência** (imagens com o resultado esperado). Sem qualquer uma dessas referências, a ativação é recusada e a tela mostra o motivo. Se tudo bater, ele é ativado.
   - Ao ativar, a estação aplica os ajustes da câmera e compara a imagem ao vivo com a imagem de referência. Se a câmera estiver em outra posição ou fora de foco, a tela mostra *Falha na verificação — chamar manutenção*: ajuste a câmera e peça ao Mantenedor para entrar e tocar **Tentar de novo** na tela da estação.
5. A configuração da instalação que veio no backup **não é aplicada sozinha**: confira **Configurações** (câmera, pasta de backup) e salve.
6. Defina de novo as senhas em **Acessos**.
7. Passe algumas peças boas e ruins conhecidas para confirmar.

## Quando a verificação não passa

Na ativação, o sistema mostra o que não bateu (ex.: *caso ok2.png: resultado FAIL, esperado PASS*). Só o **Mantenedor** pode **Ativar mesmo assim**, escrevendo o motivo; isso fica na **Auditoria**.
