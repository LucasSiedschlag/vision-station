import { plural, t } from '@lingui/core/macro'
import { formatNumber } from '@/lib/number'

/**
 * Every user-facing string of the interface, written in Portuguese, the source language (TD-30). Each one is a
 * Lingui message read when a screen draws it (a getter or a function), never when a module loads, so it comes
 * in the language on screen; the English texts are in src/locales/en/messages.po (`npm run i18n:extract`).
 */
export const text = {
  nav: {
    get station() {
      return t`Estação`
    },
    get about() {
      return t`Sobre`
    },
    get jobs() {
      return t`Jobs`
    },
    get results() {
      return t`Resultados`
    },
    get dataset() {
      return t`Dataset`
    },
    get settings() {
      return t`Configurações`
    },
    get access() {
      return t`Acessos`
    },
    get audit() {
      return t`Auditoria`
    },
  },
  roles: {
    get operator() {
      return t`Operador`
    },
    get supervisor() {
      return t`Supervisor`
    },
    get maintainer() {
      return t`Mantenedor`
    },
  },
  login: {
    get language() {
      return t`Idioma depois de entrar`
    },
    get open() {
      return t`Entrar`
    },
    get title() {
      return t`Entrar`
    },
    get role() {
      return t`Perfil`
    },
    get password() {
      return t`Senha`
    },
    get submit() {
      return t`Entrar`
    },
    get cancel() {
      return t`Cancelar`
    },
    get wrong() {
      return t`Perfil ou senha incorretos.`
    },
    get locked() {
      return t`Muitas tentativas. Aguarde um pouco e tente de novo.`
    },
    get expired() {
      return t`Sua sessão terminou. Entre de novo para continuar.`
    },
    welcome: (role: string) => t`Entrou como ${role}.`,
    get logout() {
      return t`Sair`
    },
    get idleLogout() {
      return t`Sessão encerrada por inatividade.`
    },
  },
  status: {
    get system() {
      return t`Sistema`
    },
    get camera() {
      return t`Câmera`
    },
    get log() {
      return t`Registro`
    },
    get machine() {
      return t`Máquina`
    },
    get machineConnected() {
      return t`conectada`
    },
    get noSignal() {
      return t`sem sinal`
    },
    get awaitingHeartbeat() {
      return t`aguardando sinal de vida`
    },
    heartbeat: (seconds: number) => {
      const age = formatNumber(seconds, 1)
      return t`sinal de vida há ${age} s`
    },
    get connecting() {
      return t`conectando`
    },
    get connected() {
      return t`conectado`
    },
    get offline() {
      return t`sem conexão`
    },
    get ok() {
      return t`ok`
    },
    get disconnected() {
      return t`desconectada`
    },
    get failing() {
      return t`com falhas`
    },
    get unknown() {
      return t`desconhecido`
    },
    lastFrame: (seconds: number) => {
      const age = formatNumber(seconds, 1)
      return t`último quadro há ${age} s`
    },
    failures: (n: number) =>
      plural(n, {
        0: 'Nenhum resultado deixou de ser gravado',
        one: '# resultado não gravado',
        other: '# resultados não gravados',
      }),
  },
  operator: {
    get trigger() {
      return t`Inspecionar agora`
    },
    get retry() {
      return t`Tentar de novo`
    },
    get resume() {
      return t`Retomar a estação`
    },
    get wrong() {
      return t`Resultado incorreto?`
    },
    get wrongTitle() {
      return t`Este resultado estava errado?`
    },
    wrongBody: (said: string) => t`O sistema disse ${said}. Qual era o resultado certo?`,
    get wasOk() {
      return t`Estava OK`
    },
    get wasNotOk() {
      return t`Estava NÃO OK`
    },
    get wrongDone() {
      return t`Marcado como incorreto. A imagem vai para o treinamento.`
    },
    get noImage() {
      return t`Sem imagem da câmera`
    },
    get tools() {
      return t`Ferramentas`
    },
    moreTools: (n: number) => plural(n, { one: '+ # outra', other: '+ # outras' }),
    get markings() {
      return t`Marcações`
    },
    get backToLive() {
      return t`Voltar ao vivo`
    },
    resultOf: (time: string) => t`Resultado das ${time}`,
    get noSavedImage() {
      return t`Esse resultado não tem imagem guardada`
    },
    resultAt: (outcome: string, time: string, reason: string) =>
      time
        ? reason
          ? t`${outcome} às ${time}: ${reason}`
          : t`${outcome} às ${time}`
        : reason
          ? t`${outcome}: ${reason}`
          : outcome,
    regionLabel: (id: string, passed: boolean) =>
      passed ? t`Região de ${id}: passou` : t`Região de ${id}: reprovou`,
    get today() {
      return t`Hoje`
    },
    get recent() {
      return t`Últimos resultados`
    },
    get total() {
      return t`Total`
    },
    get pass() {
      return t`Aprovadas`
    },
    get fail() {
      return t`Reprovadas`
    },
    get error() {
      return t`Erros`
    },
    outcome: {
      get PASS() {
        return t`Aprovado`
      },
      get FAIL() {
        return t`Reprovado`
      },
      get ERROR() {
        return t`Erro`
      },
    },
  },
  errors: {
    get forbiddenTitle() {
      return t`Sem permissão`
    },
    get forbiddenBody() {
      return t`Este perfil não pode abrir esta tela.`
    },
    get notFoundBody() {
      return t`Esse endereço não existe.`
    },
    get backToStation() {
      return t`Voltar para a estação`
    },
    get routeTitle() {
      return t`Esta tela falhou`
    },
    get routeBody() {
      return t`Algo deu errado ao montar esta tela.`
    },
    get retry() {
      return t`Tentar de novo`
    },
    get expiredTitle() {
      return t`Sua sessão terminou`
    },
  },
  about: {
    get title() {
      return t`Sobre`
    },
    get version() {
      return t`Versão do programa`
    },
    get build() {
      return t`Compilação`
    },
    get jobFormat() {
      return t`Formato dos arquivos de job`
    },
    get tools() {
      return t`Ferramentas que este programa executa`
    },
    get loadError() {
      return t`Não foi possível ler as informações do programa.`
    },
  },
  jobs: {
    get title() {
      return t`Jobs`
    },
    get import() {
      return t`Importar arquivo`
    },
    get backup() {
      return t`Fazer backup`
    },
    get backups() {
      return t`Backups…`
    },
    get name() {
      return t`Nome`
    },
    get active() {
      return t`Ativo`
    },
    get versions() {
      return t`Versões`
    },
    get updated() {
      return t`Última alteração`
    },
    get author() {
      return t`Autor`
    },
    get actions() {
      return t`Ações`
    },
    actionsOf: (name: string) => t`Ações de ${name}`,
    get open() {
      return t`Abrir`
    },
    get export() {
      return t`Exportar .vjob`
    },
    get duplicate() {
      return t`Duplicar`
    },
    get edit() {
      return t`Editar`
    },
    get newJob() {
      return t`Novo job`
    },
    get empty() {
      return t`Nenhum job ainda`
    },
    get emptyBody() {
      return t`Importe um arquivo .vjob ou .vbak, ou crie um job no editor.`
    },
    get loadError() {
      return t`Não foi possível ler a lista de jobs.`
    },
    get back() {
      return t`Voltar para Jobs`
    },
    version: (v: number) => t`v${v}`,
    activeVersion: (v: number) => t`ativo: v${v}`,
    parent: (v: number) => t`a partir da v${v}`,
    get noNotes() {
      return t`sem nota`
    },
    get activate() {
      return t`Ativar`
    },
    get compare() {
      return t`Comparar com…`
    },
    get openInEditor() {
      return t`Abrir no editor`
    },
    activateTitle: (v: number, name: string) => t`Ativar versão ${v} de ${name}?`,
    get activateBody() {
      return t`O sistema confere o job no conjunto de referência antes de ativar. A estação passa a usar esta versão e confere a câmera e a imagem de referência ao trocar.`
    },
    get activateConfirm() {
      return t`Verificar e ativar`
    },
    activated: (v: number, name: string) => t`Versão ${v} de ${name} ativada.`,
    get activatedWithWarnings() {
      return t`Ativado, com avisos:`
    },
    get verificationFailed() {
      return t`O job não passou na verificação:`
    },
    get overrideTitle() {
      return t`Ativar mesmo assim`
    },
    get overrideHint() {
      return t`Só o Mantenedor. O motivo fica registrado na auditoria.`
    },
    get overrideReason() {
      return t`Motivo`
    },
    get overrideConfirm() {
      return t`Ativar mesmo assim`
    },
    get importTitle() {
      return t`Importar arquivo`
    },
    get importBody() {
      return t`Um job (.vjob) ou um backup (.vbak). Importar guarda as versões; ativar é um passo à parte, com verificação.`
    },
    get importDrop() {
      return t`Solte o arquivo aqui ou escolha um`
    },
    get importDone() {
      return t`Arquivo importado`
    },
    importStatus: {
      get added() {
        return t`adicionada`
      },
      get already_present() {
        return t`já existia`
      },
      get renumbered() {
        return t`renumerada`
      },
    },
    importItem: (v: number, status: string, original: number) =>
      original !== v ? t`v${v} (era v${original}) · ${status}` : t`v${v} · ${status}`,
    get importBackupNote() {
      return t`O backup trouxe a configuração do sistema; ela não é aplicada sozinha.`
    },
    importActiveWas: (v: number) =>
      t`No backup, a versão ativa era a v${v}: ative-a aqui depois de conferir.`,
    backupDone: (name: string, size: string) => t`Backup ${name} (${size}) gravado.`,
    get backupsTitle() {
      return t`Backups`
    },
    backupsFolder: (folder: string) => t`Pasta: ${folder}`,
    get backupsNone() {
      return t`Nenhum backup na pasta.`
    },
    get backupsNoFolder() {
      return t`Nenhuma pasta de backup configurada.`
    },
    get download() {
      return t`Baixar`
    },
    downloadOf: (name: string) => t`Baixar ${name}`,
    diffTitle: (v: number) => t`Comparar a versão ${v}`,
    get diffAgainst() {
      return t`Comparar com`
    },
    get diffSame() {
      return t`As duas versões têm a mesma definição.`
    },
    get duplicateTitle() {
      return t`Duplicar job`
    },
    duplicateBody: (v: number) =>
      t`Cria um job novo a partir da versão ${v}, com todos os arquivos.`,
    get duplicateName() {
      return t`Nome do job novo`
    },
    duplicateDone: (name: string) => t`Job ${name} criado.`,
    copyOf: (name: string) => t`${name} (cópia)`,
  },
  editor: {
    steps: {
      get image() {
        return t`Imagem e disparo`
      },
      get samples() {
        return t`Amostras`
      },
      get anchor() {
        return t`Âncora`
      },
      get tools() {
        return t`Ferramentas`
      },
      get quality() {
        return t`Qualidade`
      },
      get outputs() {
        return t`Resultado e saídas`
      },
      get validate() {
        return t`Validar`
      },
      get save() {
        return t`Salvar`
      },
    },
    /** Why a step is blocked or needs attention (docs/frontend.md §4.3). */
    sequence: {
      get needReference() {
        return t`Capture a imagem de referência primeiro`
      },
      get needReferenceHere() {
        return t`Capture a imagem de referência`
      },
      get needTool() {
        return t`Adicione ao menos uma ferramenta`
      },
      get noSamples() {
        return t`Ainda sem amostras Boas e Ruins`
      },
      get serverProblem() {
        return t`O servidor recusou algo neste passo`
      },
      get imageChanged() {
        return t`A imagem mudou depois da última validação; rode Validar`
      },
      get changedSinceValidation() {
        return t`O job mudou depois da validação; rode Validar de novo`
      },
      samplesFailed: (failed: number, total: number) =>
        t`${failed} de ${total} amostras não saíram como esperado`,
      get notValidated() {
        return t`Ainda não validado`
      },
      get next() {
        return t`Próximo passo`
      },
      get blockedBanner() {
        return t`Este passo está bloqueado: dá para ler, não para editar.`
      },
    },
    sampleKind: {
      get PASS() {
        return t`Boa`
      },
      get FAIL() {
        return t`Ruim`
      },
      get ERROR() {
        return t`Com erro`
      },
    },
    get triggerBar() {
      return t`Disparo`
    },
    get triggerTitle() {
      return t`Disparo`
    },
    get interval() {
      return t`Intervalo mínimo entre inspeções`
    },
    get intervalHint() {
      return t`0 inspeciona o mais rápido que o computador deixar. Uma imagem tirada com a cena em movimento nunca é inspecionada.`
    },
    // Resultado e saídas
    get outputsIntro() {
      return t`Quais ferramentas decidem o resultado e o que a tela do operador diz enquanto espera.`
    },
    get decides() {
      return t`Decide o resultado`
    },
    get decidesHint() {
      return t`Desligada, a ferramenta é medida e gravada, mas nunca reprova a peça.`
    },
    get machineOutputs() {
      return t`As saídas para a máquina vêm com a interface da máquina (fase B).`
    },
    // Validar
    get validateIntro() {
      return t`Roda o job em todas as amostras e confere com o esperado. É a mesma conferência que a ativação faz.`
    },
    get validateAll() {
      return t`Validar tudo`
    },
    get validateEmpty() {
      return t`Sem amostras. Capture amostras Boas e Ruins no passo Amostras.`
    },
    get validateOk() {
      return t`Todas as amostras saíram como esperado`
    },
    validateSome: (failed: number, total: number) =>
      t`${failed} de ${total} amostras não saíram como esperado`,
    get colSample() {
      return t`Amostra`
    },
    get colExpected() {
      return t`Esperado`
    },
    get colGot() {
      return t`Resultado`
    },
    slowest: (ms: number) => t`Mais lenta: ${ms} ms`,
    get notRun() {
      return t`não rodou`
    },
    // Salvar
    get saveIntro() {
      return t`Confira o nome e o que mudou, e salve como uma nova versão. Ativar é feito na página do job.`
    },
    get changes() {
      return t`Mudanças desta versão`
    },
    get noChanges() {
      return t`Nada mudou em relação à versão de origem.`
    },
    get checkFields() {
      return t`Conferir campos`
    },
    change: {
      get nothing() {
        return t`nenhum`
      },
      get on() {
        return t`ligado`
      },
      get off() {
        return t`desligado`
      },
      newJob: (name: string, tools: number) => {
        const count = plural(tools, { one: '# ferramenta', other: '# ferramentas' })
        return t`Job novo ${name}: ${count}`
      },
      name: (from: string, to: string) => t`Nome: ${from} → ${to}`,
      get description() {
        return t`A descrição mudou`
      },
      camera: (setting: string, from: string, to: string) => t`Câmera, ${setting}: ${from} → ${to}`,
      // the names of the camera settings in the summary; a setting not listed keeps its key
      settings: {
        get resolution() {
          return t`resolução`
        },
        get pixel_format() {
          return t`formato do pixel`
        },
        get exposure() {
          return t`exposição`
        },
        get gain() {
          return t`ganho`
        },
        get white_balance() {
          return t`balanço de branco`
        },
        get focus() {
          return t`foco`
        },
        get zoom() {
          return t`zoom`
        },
        get power_line_hz() {
          return t`rede elétrica`
        },
        get low_light_compensation() {
          return t`compensação de pouca luz`
        },
        get orientation() {
          return t`orientação`
        },
      } as Record<string, string>,
      get reference() {
        return t`Nova imagem de referência`
      },
      samplesAdded: (good: number, bad: number) => t`Amostras novas: ${good} Boas e ${bad} Ruins`,
      samplesRemoved: (n: number) =>
        plural(n, { one: '# amostra removida', other: '# amostras removidas' }),
      anchorAdded: (type: string) => t`Âncora nova (${type})`,
      get anchorRemoved() {
        return t`Âncora removida`
      },
      anchorChanged: (type: string) => t`Âncora alterada (${type})`,
      regionAdded: (name: string) => t`Região nova: ${name}`,
      regionChanged: (name: string) => t`Região alterada: ${name}`,
      regionRemoved: (name: string) => t`Região removida: ${name}`,
      toolAdded: (id: string, type: string) => t`Ferramenta nova: ${id} (${type})`,
      toolRemoved: (id: string) => t`Ferramenta removida: ${id}`,
      param: (id: string, title: string, from: string, to: string) =>
        t`${id}: ${title}, ${from} → ${to}`,
      toolRegion: (id: string, from: string, to: string) => t`${id}: região ${from} → ${to}`,
      toolInformative: (id: string) => t`${id} passou a só informar, sem reprovar`,
      toolDecides: (id: string) => t`${id} passou a decidir o resultado`,
      toolReason: (id: string) => t`${id}: o texto de reprovação mudou`,
      get trigger() {
        return t`O disparo mudou`
      },
      get quality() {
        return t`A qualidade da imagem mudou`
      },
      get texts() {
        return t`Os textos do operador mudaram`
      },
      get decision() {
        return t`A regra de decisão mudou`
      },
    },
    get stepsLabel() {
      return t`Passos do job`
    },
    get imageLabel() {
      return t`Imagem`
    },
    get imageSource() {
      return t`Imagem mostrada`
    },
    get sourceReference() {
      return t`Referência`
    },
    get sourceLive() {
      return t`Ao vivo`
    },
    get refreshImage() {
      return t`Atualizar imagem`
    },
    get loadingImage() {
      return t`Carregando a imagem…`
    },
    get drawingHint() {
      return t`Arraste sobre a imagem para desenhar`
    },
    get drawingNow() {
      return t`Desenhando… (arraste na imagem)`
    },
    get noAnchor() {
      return t`Sem âncora: rode Testar para localizar o objeto e ver as regiões relativas a ele.`
    },
    get newJob() {
      return t`novo job`
    },
    draftOf: (v: number) => t`rascunho a partir da v${v}`,
    get unsaved() {
      return t`não salvo`
    },
    get undo() {
      return t`Desfazer`
    },
    get redo() {
      return t`Refazer`
    },
    get discard() {
      return t`Descartar`
    },
    get test() {
      return t`Testar`
    },
    get save() {
      return t`Salvar…`
    },
    get recovered() {
      return t`Rascunho recuperado deste navegador.`
    },
    get discardRecovered() {
      return t`Descartar o rascunho`
    },
    get stationPaused() {
      return t`A estação está pausada (ajuste de câmera).`
    },
    get stationPausedBySession() {
      return t`A estação está pausada enquanto o editor mede ao vivo; volta sozinha quando você sair.`
    },
    get resume() {
      return t`Retomar a estação`
    },
    get testNote() {
      return t`Testado na imagem mais nova da câmera, em tamanho cheio, como a estação faz.`
    },
    outcome: {
      get PASS() {
        return t`Aprovado`
      },
      get FAIL() {
        return t`Reprovado`
      },
      get ERROR() {
        return t`Erro`
      },
    },
    saveTitle: (v: number) => t`Salvar como versão ${v}`,
    get saveNewTitle() {
      return t`Salvar o job novo`
    },
    get saveBody() {
      return t`A versão salva nunca muda. Para usar na estação, ative-a na tela Jobs (com verificação).`
    },
    get notes() {
      return t`O que mudou`
    },
    get notesHint() {
      return t`Fica no histórico de versões.`
    },
    saved: (v: number) => t`Versão ${v} salva.`,
    get discardTitle() {
      return t`Descartar o rascunho?`
    },
    get discardBody() {
      return t`As mudanças não salvas são perdidas. A versão salva continua como estava.`
    },
    get leaveTitle() {
      return t`Sair do editor?`
    },
    get leaveBody() {
      return t`O rascunho fica guardado neste navegador e volta quando você abrir o editor de novo.`
    },
    get leave() {
      return t({ message: 'Sair', context: 'leave the editor' }) // not the logout "Sair"
    },
    get presenceArea() {
      return t`presença`
    },
    get anchorLabel() {
      return t`âncora`
    },
    get cropLabel() {
      return t`recorte`
    },
    // camera
    get cameraIntro() {
      return t`Os ajustes vão no job e são gravados na câmera a cada abertura. Aplicar pausa a estação até você retomá-la.`
    },
    get width() {
      return t`Largura`
    },
    get height() {
      return t`Altura`
    },
    get exposure() {
      return t`Exposição`
    },
    get exposureValue() {
      return t`Tempo de exposição`
    },
    get gain() {
      return t`Ganho`
    },
    get whiteBalance() {
      return t`Balanço de branco`
    },
    get kelvin() {
      return t`Temperatura`
    },
    get focus() {
      return t`Foco`
    },
    get value() {
      return t`Valor`
    },
    get manual() {
      return t`Manual`
    },
    get auto() {
      return t`Automático: a câmera decide (evite na estação)`
    },
    get powerLine() {
      return t`Rede elétrica`
    },
    /** The strip of samples under the image (docs/frontend.md §10.1). */
    strip: {
      get label() {
        return t`Amostras`
      },
      get reference() {
        return t`Referência`
      },
      get live() {
        return t`Ao vivo`
      },
      get addGood() {
        return t`Boa`
      },
      get addBad() {
        return t`Ruim`
      },
      get addGoodLong() {
        return t`Capturar como Boa`
      },
      get addBadLong() {
        return t`Capturar como Ruim`
      },
      get none() {
        return t`Nenhuma amostra ainda. Para propor limites: 3 Boas e 1 Ruim; o recomendado é 10 Boas e 1 Ruim de cada defeito.`
      },
      sample: (name: string, kind: string, agrees: string) => t`${name}: ${kind}, ${agrees}`,
      get good() {
        return t`Boa`
      },
      get bad() {
        return t`Ruim`
      },
      get agrees() {
        return t`o job concorda`
      },
      get disagrees() {
        return t`o job discorda`
      },
      get untested() {
        return t`ainda não medida`
      },
      get hide() {
        return t`Ocultar as amostras`
      },
      get show() {
        return t`Mostrar as amostras`
      },
    },
    get railWidth() {
      return t`Largura da lista de passos`
    },
    get inspectorWidth() {
      return t`Largura do inspetor`
    },
    get resultBarLabel() {
      return t`Resultado do rascunho`
    },
    /** The bar under the workbench: the last verdict, a chip per tool, the time and the rate (docs/frontend.md §10.1). */
    bar: {
      get none() {
        return t`Sem resultado ainda: o rascunho é medido na imagem ao vivo ou ao pedir Testar.`
      },
      get notRun() {
        return t`não rodou`
      },
      toolChip: (id: string, state: string) => t`${id}: ${state}`,
      get passed() {
        return t`passou`
      },
      get failed() {
        return t`reprovou`
      },
      rate: (rate: string) => t`Captura ${rate}/s`,
    },
    /** What the image area says when it cannot show the usual (docs/frontend.md §19.1). */
    states: {
      anchorNotFound: (code: string) => t`Âncora não encontrada (${code})`,
      get anchorHint() {
        return t`As ferramentas não rodaram. As amostras e a referência continuam abertas.`
      },
      get openAnchor() {
        return t`Abrir o passo Âncora`
      },
      get cameraLost() {
        return t`Câmera desconectada`
      },
      lastImage: (age: string) => t`Última imagem há ${age}.`,
      get adjustOnReference() {
        return t`Ajustar na referência`
      },
      seconds: (n: number) => t`${n} s`,
      minutes: (n: number) => t`${n} min`,
    },
    /** Zoom, pan and the layers of the image (docs/frontend.md §10.2, §18). */
    view: {
      get zoomIn() {
        return t`Aproximar`
      },
      get zoomOut() {
        return t`Afastar`
      },
      get fit() {
        return t`Ajustar à janela`
      },
      get actual() {
        return t`Tamanho real (100 %)`
      },
      zoom: (percent: string) => t`Zoom ${percent} %`,
      get minimap() {
        return t`Mapa da imagem: clique para ir a outra parte`
      },
      get hint() {
        return t`Roda do mouse: zoom. Espaço e arrastar: mover. Ctrl+0 ajusta; 1 mostra no tamanho real.`
      },
      markings: (on: number, all: number) => t`Marcações · ${on}/${all}`,
      get markingsMenu() {
        return t`Escolher as marcações`
      },
      get allMarkings() {
        return t`Todas as marcações`
      },
      layers: {
        get regions() {
          return t`Regiões`
        },
        get anchors() {
          return t`Âncoras`
        },
        get labels() {
          return t`Rótulos`
        },
        get mask() {
          return t`Máscara`
        },
        get presence() {
          return t`Área de presença`
        },
        get grid() {
          return t`Grade de pixels`
        },
      },
      layerHints: {
        get regions() {
          return t`a região de cada ferramenta e o resultado dela`
        },
        get anchors() {
          return t`onde a âncora foi achada`
        },
        get labels() {
          return t`o nome ao lado de cada região`
        },
        get mask() {
          return t`os pixels que a faixa de cor pega`
        },
        get presence() {
          return t`a área que dispara pela imagem`
        },
        get grid() {
          return t`só com zoom acima de 800 %`
        },
      },
    },
    /** The tolerance gauge (docs/frontend.md §19.3). */
    gauge: {
      get good() {
        return t`Boas`
      },
      get bad() {
        return t`Ruins`
      },
      get reference() {
        return t`Referência`
      },
      get current() {
        return t`atual`
      },
      get notMeasured() {
        return t`não medido`
      },
      get limitMin() {
        return t`Limite mínimo`
      },
      get limitMax() {
        return t`Limite máximo`
      },
      get useMin() {
        return t`Usar o limite mínimo`
      },
      get useMax() {
        return t`Usar o limite máximo`
      },
      points: (n: string) => t`${n} pontos percentuais`,
      margin: (parts: string) => t`Margem: ${parts}.`,
      worstGood: (side: 'min' | 'max', value: string, distance: string, inside: boolean) =>
        side === 'min'
          ? inside
            ? t`a pior boa (${value}) está ${distance} acima do limite`
            : t`a pior boa (${value}) está ${distance} abaixo do limite, e reprova`
          : inside
            ? t`a pior boa (${value}) está ${distance} abaixo do limite`
            : t`a pior boa (${value}) está ${distance} acima do limite, e reprova`,
      nearestBad: (side: 'min' | 'max', distance: string) =>
        side === 'min'
          ? t`a ruim mais alta, ${distance} abaixo`
          : t`a ruim mais baixa, ${distance} acima`,
      tally: (goodIn: number, goodN: number, badOut: number, badN: number) =>
        t`${goodIn} de ${goodN} boas dentro · ${badOut} de ${badN} ruins fora`,
      get onlyReference() {
        return t`Só a referência foi medida: o limite não pode ser conferido nem proposto. Capture amostras Boas e Ruins.`
      },
      get adjust() {
        return t`Ajustar pelas amostras`
      },
      get adjusting() {
        return t`Calculando…`
      },
      get apply() {
        return t`Aplicar`
      },
      get discard() {
        return t`Descartar`
      },
      valueText: (limit: string, current: string, goodIn: number, goodN: number) =>
        t`${limit}; valor atual ${current}; ${goodIn} de ${goodN} boas dentro`,
      proposal: (
        side: 'min' | 'max',
        value: string,
        goodMargin: string,
        badMargin: string | null,
      ) =>
        badMargin === null
          ? side === 'min'
            ? t`Proposta: limite mínimo ${value}, ${goodMargin} abaixo da pior boa.`
            : t`Proposta: limite máximo ${value}, ${goodMargin} acima da pior boa.`
          : side === 'min'
            ? t`Proposta: limite mínimo ${value}, no meio entre as ruins e as boas (${goodMargin} abaixo da pior boa, ${badMargin} acima da ruim mais alta).`
            : t`Proposta: limite máximo ${value}, no meio entre as boas e as ruins (${goodMargin} acima da pior boa, ${badMargin} abaixo da ruim mais baixa).`,
      get overlap() {
        return t`As amostras se sobrepõem; a medição não separa boas de ruins.`
      },
      fewGood: (n: number) => t`São precisas pelo menos ${n} amostras Boas para propor um limite.`,
      get bounds() {
        return t`Nenhum valor aceito por este parâmetro separa as amostras.`
      },
      get stale() {
        return t`Medindo as amostras de novo…`
      },
    },
    /** The fine-tune of tolerances (docs/frontend.md §7.12). */
    tune: {
      title: (name: string, version: number) => t`Ajuste fino — ${name} v${version}`,
      get intro() {
        return t`Aqui só mudam os limites de tolerância e as amostras. Regiões, câmera e ferramentas são do Mantenedor.`
      },
      get noTools() {
        return t`Este job não tem ferramenta com tolerância para ajustar.`
      },
      get toolPasses() {
        return t`passa`
      },
      get toolFails() {
        return t`reprova`
      },
      get captureGood() {
        return t`Capturar como Boa`
      },
      get captureBad() {
        return t`Capturar como Ruim`
      },
      get noCamera() {
        return t`Sem imagem da câmera: dá para ajustar pelas amostras que o job já tem.`
      },
      added: (good: number, bad: number) =>
        t`Amostras novas: ${good} boas e ${bad} ruins (entram na versão ao salvar).`,
      saveAs: (version: number) => t`Salvar como v${version}…`,
      get discardAll() {
        return t`Descartar ajustes`
      },
      saveTitle: (version: number) => t`Salvar o ajuste como versão ${version}`,
      saveBody: (version: number) =>
        t`Cria a versão ${version}, marcada como ajuste fino, e a verifica nas amostras. Ela só passa a valer quando você ativar.`,
      get note() {
        return t`O que você ajustou e por quê`
      },
      get noteHint() {
        return t`Obrigatório: fica no registro de auditoria. Ex.: lote novo de tampas, luz do turno da noite.`
      },
      verified: (version: number) => t`Versão ${version} salva e verificada: pode ser ativada.`,
      notVerified: (version: number) =>
        t`Versão ${version} salva, mas não passou na verificação. Só o Mantenedor pode liberar uma versão assim.`,
      activate: (version: number) => t`Ativar a versão ${version}`,
      activated: (version: number) => t`Versão ${version} ativada.`,
      get close() {
        return t`Fechar`
      },
      get tuned() {
        return t`ajuste fino`
      },
      get open() {
        return t`Ajuste fino`
      },
    },
    /** The camera controls: histogram, focus meter, exposure (docs/frontend.md §19.5). */
    camera: {
      get histogramLabel() {
        return t`Histograma de brilho da imagem ao vivo`
      },
      clippedLow: (share: string) => t`${share} % da imagem preta`,
      clippedHigh: (share: string) => t`${share} % da imagem saturada`,
      get sharpness() {
        return t`Nitidez`
      },
      get noValue() {
        return t`sem imagem`
      },
      best: (peak: string) => t`melhor: ${peak}`,
      get atPeak() {
        return t`No ponto mais nítido`
      },
      get turnFocus() {
        return t`Gire o foco até a barra ficar verde`
      },
      get resetPeak() {
        return t`Reiniciar o melhor`
      },
      get exposureSlider() {
        return t`Exposição (escala logarítmica)`
      },
      get noLive() {
        return t`Sem imagem ao vivo: a câmera não está entregando quadros.`
      },
    },
    /** The colour picker (docs/frontend.md §19.4). */
    colour: {
      get title() {
        return t`Cor`
      },
      get sampleLabel() {
        return t`Amostra`
      },
      get include() {
        return t`Incluir cor`
      },
      get exclude() {
        return t`Excluir cor`
      },
      clear: (included: number, excluded: number) =>
        t`Limpar amostras (${included} incluídas, ${excluded} excluídas)`,
      get dragInclude() {
        return t`Arraste sobre a cor na imagem`
      },
      get dragExclude() {
        return t`Arraste sobre o que deve ficar de fora`
      },
      get markColourFirst() {
        return t`Marque primeiro a cor com Incluir cor.`
      },
      get noProposal() {
        return t`Não foi possível propor uma faixa com essas amostras.`
      },
      proposed: (summary: string) => t`Faixa proposta: ${summary}.`,
      keeps: (share: string) => t`Mantém ${share} % da cor amostrada.`,
      leaves: (share: string) => t`Deixa ${share} % do que você excluiu dentro da faixa.`,
      get apply() {
        return t`Aplicar`
      },
      get discard() {
        return t`Descartar`
      },
      get anyHue() {
        return t`Qualquer matiz`
      },
      get anyHueHint() {
        return t`Para preto, branco e cinzas, que não têm matiz: contam só a saturação e o brilho.`
      },
      get hue() {
        return t`Matiz`
      },
      get hueFrom() {
        return t`Matiz inicial`
      },
      get hueTo() {
        return t`Matiz final`
      },
      get saturation() {
        return t`Saturação`
      },
      get saturationMin() {
        return t`Saturação mínima`
      },
      get saturationMax() {
        return t`Saturação máxima`
      },
      get brightness() {
        return t`Brilho`
      },
      get brightnessMin() {
        return t`Brilho mínimo`
      },
      get brightnessMax() {
        return t`Brilho máximo`
      },
      get margin() {
        return t`Folga`
      },
      get marginHint() {
        return t`Alarga ou estreita a faixa toda de uma vez, a partir da última que você ajustou.`
      },
      get mask() {
        return t`Máscara na imagem`
      },
    },
    liveOn: (rate: string) => t`Ao vivo ● ${rate}/s`,
    liveState: {
      get connecting() {
        return t`Conectando à câmera…`
      },
      get busy() {
        return t`Outro editor está usando a câmera`
      },
      get refused() {
        return t`Entre como Supervisor ou Mantenedor para medir ao vivo`
      },
      get ended() {
        return t`Medição ao vivo encerrada`
      },
    },
    liveDraftRefused: (why: string) => t`O rascunho não pôde ser medido: ${why}`,
    get liveNote() {
      return t`Medido agora, na imagem ao vivo, com a estação pausada.`
    },
    sampleShown: (name: string) => t`Amostra: ${name}`,
    get sampleBack() {
      return t`Voltar à imagem`
    },
    get autoOnce() {
      return t`Auto uma vez`
    },
    get autoOnceHint() {
      return t`Mede a exposição agora, com a câmera pausada, e deixa o valor fixo no job. Leva alguns segundos.`
    },
    autoOnceDone: (value: number, saturated: number) => {
      const share = formatNumber(saturated, 1)
      return t`Exposição ajustada para ${value} µs (${share} % de pixels saturados).`
    },
    autoOnceLimit: (limit: string, value: number, saturated: number, target: number) => {
      const share = formatNumber(saturated, 1)
      const goal = formatNumber(target, 1)
      if (limit === 'max')
        return t`Mesmo com a exposição máxima (${value} µs) só ${share} % dos pixels saturam; o alvo era ${goal} %. Ficou no máximo.`
      if (limit === 'min')
        return t`Mesmo com a exposição mínima (${value} µs) ${share} % dos pixels saturam; o alvo era ${goal} %. Ficou no mínimo.`
      return t`Melhor aproximação: ${value} µs com ${share} % de pixels saturados; o alvo era ${goal} %.`
    },
    get autoTarget() {
      return t`Brilho-alvo do Auto uma vez`
    },
    get autoTargetHint() {
      return t`Percentual de pixels saturados que a exposição deve alcançar na região medida`
    },
    get autoMax() {
      return t`Exposição máxima do Auto uma vez`
    },
    get autoRegion() {
      return t`Medir só numa região`
    },
    get autoRegionAll() {
      return t`Mede a imagem toda`
    },
    get drawAutoRegion() {
      return t`Desenhar a região de medição`
    },
    get autoRegionLabel() {
      return t`Região de medição da exposição`
    },
    get orientation() {
      return t`Orientação da imagem`
    },
    get orientationHint() {
      return t`O programa vira cada imagem; as regiões e os resultados já usam a imagem virada. Mudar depois de capturar a referência e as amostras pede capturá-las de novo.`
    },
    orientations: {
      get normal() {
        return t`Normal`
      },
      get mirror() {
        return t`Espelhada`
      },
      get flip() {
        return t`De cabeça para baixo`
      },
      get rotate180() {
        return t`Girada 180°`
      },
    },
    get applyCamera() {
      return t`Aplicar na câmera`
    },
    get applied() {
      return t`Ajustes gravados e lidos de volta.`
    },
    get notApplied() {
      return t`Nem todos os ajustes foram gravados:`
    },
    setting: {
      get applied() {
        return t`aplicado`
      },
      get not_supported() {
        return t`não suportado`
      },
      get out_of_range() {
        return t`fora da faixa`
      },
      get failed() {
        return t`falhou`
      },
      get rejected() {
        return t`recusado`
      },
    },
    // trigger
    get triggerMode() {
      return t`Modo de disparo`
    },
    triggerModes: {
      get image_presence() {
        return [
          t`Objeto parado na área`,
          t`Inspeciona quando um objeto entra na área e fica parado`,
        ] as const
      },
      get manual() {
        return [t`Manual`, t`Pelo botão Inspecionar agora ou por outro programa`] as const
      },
      get external() {
        return [t`Sinal externo`, t`Um sinal de outro equipamento dispara a inspeção`] as const
      },
      get continuous() {
        return [t`Contínuo`, t`Inspeciona uma imagem atrás da outra`] as const
      },
    },
    get drawPresence() {
      return t`Desenhar a área de presença`
    },
    get stillMs() {
      return t`Tempo parado`
    },
    get stillHint() {
      return t`Quanto tempo o objeto precisa ficar parado antes da foto.`
    },
    get diffThreshold() {
      return t`Diferença de cinza`
    },
    get diffHint() {
      return t`Quanto um pixel muda para contar como objeto (1 a 255).`
    },
    get minArea() {
      return t`Área mínima com objeto`
    },
    get minAreaHint() {
      return t`Fração da área de presença (0 a 1).`
    },
    get waiting() {
      return t`Texto de espera`
    },
    get waitingHint() {
      return t`O que a tela do operador mostra enquanto espera, ex.: Aguardando peça.`
    },
    // quality
    get qualityIntro() {
      return t`Imagens fora destes limites viram ERRO com o motivo, nunca APROVADO.`
    },
    get brightnessMin() {
      return t`Brilho mínimo`
    },
    get brightnessMax() {
      return t`Brilho máximo`
    },
    get sharpness() {
      return t`Nitidez mínima`
    },
    get sharpnessHint() {
      return t`Fração da nitidez da imagem de referência (0,5 = metade).`
    },
    get similarity() {
      return t`Semelhança mínima com a referência`
    },
    get similarityHint() {
      return t`Na verificação ao ativar: câmera movida ou cena diferente.`
    },
    get measure() {
      return t`Medir a imagem atual`
    },
    measured: (b: string, s: string) => t`Imagem atual: brilho ${b}, nitidez ${s}.`,
    get useMeasured() {
      return t`Usar o brilho atual ±20%`
    },
    // regions
    get locator() {
      return t`Localizador`
    },
    get locatorHint() {
      return t`Acha o objeto na imagem, para as regiões acompanharem quando ele muda de lugar.`
    },
    get noLocator() {
      return t`Nenhum (regiões fixas na imagem)`
    },
    locatorNames: {
      get fixed() {
        return t`Posição fixa`
      },
      get template() {
        return t`Gabarito`
      },
      get blob() {
        return t`Cor ou contraste`
      },
    },
    get drawLocator() {
      return t`Desenhar a posição do objeto`
    },
    get cropHint() {
      return t`Desenhe um recorte em volta do objeto na imagem de referência e use-o como gabarito.`
    },
    get patternCropHint() {
      return t`Para a ferramenta de padrão: desenhe um recorte do logo ou marca na imagem de referência.`
    },
    get cropNeedsReference() {
      return t`Capture a imagem de referência (passo Referência) para recortar um gabarito.`
    },
    get drawCrop() {
      return t`Desenhar recorte`
    },
    get useCrop() {
      return t`Usar como gabarito`
    },
    usePatternFor: (id: string) => t`Usar como padrão de ${id}`,
    get templateSaved() {
      return t`Gabarito guardado no job.`
    },
    get regions() {
      return t`Regiões`
    },
    get noRegions() {
      return t`Nenhuma região. Uma ferramenta pode olhar a imagem toda.`
    },
    relativeTo: (name: string) => t`${name}: relativa a`,
    get relFrame() {
      return t`à imagem`
    },
    get relAnchor() {
      return t`ao objeto (âncora)`
    },
    get redraw() {
      return t`Redesenhar`
    },
    removeRegion: (name: string) => t`Remover a região ${name}`,
    get newRegion() {
      return t`Nova região`
    },
    get newRegionHint() {
      return t`Letras, números, - e _.`
    },
    get badName() {
      return t`Nome inválido ou já usado.`
    },
    get addRegion() {
      return t`Adicionar`
    },
    // tools
    get noTools() {
      return t`Nenhuma ferramenta ainda. Um job precisa de pelo menos uma.`
    },
    get passed() {
      return t`passou`
    },
    get failed() {
      return t`falhou`
    },
    moveUp: (id: string) => t`Subir ${id}`,
    moveDown: (id: string) => t`Descer ${id}`,
    removeTool: (id: string) => t`Remover ${id}`,
    get toolId() {
      return t`Nome`
    },
    get toolIdHint() {
      return t`Aparece nas pontuações e no registro.`
    },
    get toolRoi() {
      return t`Região`
    },
    get wholeFrame() {
      return t`imagem toda`
    },
    get wholeAnchor() {
      return t`o objeto (âncora)`
    },
    get modelDrop() {
      return t`Solte aqui o modelo (.onnx) e o cartão (.card.yaml)`
    },
    get modelHint() {
      return t`O modelo é treinado fora da estação (docs/models.md) e vai dentro do job.`
    },
    modelAdded: (paths: string) => t`Adicionado ao job: ${paths}`,
    get unknownType() {
      return t`Tipo de ferramenta que este programa não conhece.`
    },
    get reasonFail() {
      return t`Motivo da reprovação`
    },
    get reasonHint() {
      const example = '{fraction:.0%}' // a placeholder of the job's text, shown as is (not a message placeholder)
      return t`Em português, para o operador. Pode usar valores da ferramenta, ex.: ${example}.`
    },
    get defaultReason() {
      return t`Falhou`
    },
    get addTool() {
      return t`Adicionar ferramenta`
    },
    get chooseType() {
      return t`Escolha o tipo`
    },
    toolNames: {
      get code() {
        return t`Código de barras ou 2D`
      },
      get color() {
        return t`Cor`
      },
      get pattern() {
        return t`Padrão (logo, marca)`
      },
      get detect() {
        return t`Detecção por modelo`
      },
    },
    get add() {
      return t`Adicionar`
    },
    // reference
    get referenceIntro() {
      return t`A imagem de referência é a vista de um objeto bom. Ela serve para comparar nitidez e a vista da câmera ao ativar.`
    },
    get captureReference() {
      return t`Capturar a imagem de referência`
    },
    get recaptureReference() {
      return t`Capturar de novo`
    },
    referenceSaved: (w: number, h: number) => t`Imagem de referência capturada (${w} × ${h}).`,
    get referenceSet() {
      return t`Amostras`
    },
    get referenceSetIntro() {
      return t`Fotos de peças boas e de defeitos conhecidos, cada uma com o resultado esperado. Ao validar e ao ativar, o job precisa acertar todas.`
    },
    get noCases() {
      return t`Nenhuma amostra ainda.`
    },
    get caseImage() {
      return t`Imagem`
    },
    get caseExpected() {
      return t`Tipo`
    },
    expectedFor: (image: string) => t`Tipo da amostra ${image}`,
    get remove() {
      return t`Remover`
    },
    removeCase: (image: string) => t`Remover ${image}`,
    get caseName() {
      return t`Nome da amostra`
    },
    get badCaseName() {
      return t`Use letras, números, - e _, sem repetir.`
    },
    get addCase() {
      return t`Capturar amostra`
    },
    caseAdded: (name: string, now: string, expected: string) =>
      t`Amostra ${name}: o rascunho diz ${now}; esperado ${expected}.`,
    // review
    get jobName() {
      return t`Nome do job`
    },
    get description() {
      return t`Descrição`
    },
    get validate() {
      return t`Conferir o rascunho`
    },
    get valid() {
      return t`O rascunho pode ser salvo.`
    },
    get invalid() {
      return t`O rascunho tem problemas.`
    },
    get fieldErrors() {
      return t`Campos com problema`
    },
    files: (n: number) =>
      plural(n, {
        // in Portuguese 0 takes the singular form: "0 arquivo" would be wrong
        0: 'Nenhum arquivo no job (referência, gabaritos, conjunto de referência).',
        one: '# arquivo no job (referência, gabaritos, conjunto de referência).',
        other: '# arquivos no job (referência, gabaritos, conjunto de referência).',
      }),
  },
  results: {
    /** The values of a result against the limits it had, frozen at that result (docs/frontend.md §7.4). */
    gauge: {
      get tools() {
        return t`Ferramentas`
      },
      get informative() {
        return t`informativa`
      },
      min: (value: string) => t`mínimo ${value}`,
      max: (value: string) => t`máximo ${value}`,
      inside: (distance: string) => t`dentro, ${distance} da borda`,
      outside: (distance: string) => t`fora, ${distance} além da borda`,
      get codes() {
        return t`Motivos`
      },
      get frozen() {
        return t`Os limites são os que valiam neste resultado.`
      },
    },
    get reasonCode() {
      return t`Motivo`
    },
    get allReasons() {
      return t`Todos os motivos`
    },
    reasonOption: (label: string, count: number) => t`${label} (${count})`,
    get belowMin() {
      return t`abaixo do mínimo`
    },
    get aboveMax() {
      return t`acima do máximo`
    },
    get title() {
      return t`Resultados`
    },
    get period() {
      return t`Período`
    },
    periods: {
      get today() {
        return t`Hoje`
      },
      get d7() {
        return t`7 dias`
      },
      get d30() {
        return t`30 dias`
      },
      get all() {
        return t`Tudo`
      },
    },
    get job() {
      return t`Job`
    },
    get allJobs() {
      return t`Todos os jobs`
    },
    get outcome() {
      return t`Resultado`
    },
    outcomes: {
      get all() {
        return t`Todos`
      },
      get PASS() {
        return t`Aprovadas`
      },
      get FAIL() {
        return t`Reprovadas`
      },
      get ERROR() {
        return t`Erros`
      },
    },
    get incorrectOnly() {
      return t`Só os marcados como incorretos`
    },
    get exportCsv() {
      return t`Exportar CSV`
    },
    get when() {
      return t`Quando`
    },
    get reason() {
      return t`Motivo`
    },
    get duration() {
      return t`Duração`
    },
    get empty() {
      return t`Nenhum resultado neste período`
    },
    get emptyBody() {
      return t`Mude os filtros ou o período.`
    },
    get loadError() {
      return t`Não foi possível ler os resultados.`
    },
    open: (when: string) => t`Abrir o resultado de ${when}`,
    get detail() {
      return t`Resultado`
    },
    get imageOriginal() {
      return t`Original`
    },
    get imageMarked() {
      return t`Marcado`
    },
    get imageView() {
      return t`Imagem mostrada`
    },
    get noImage() {
      return t`A imagem deste resultado não foi guardada (amostragem de aprovados ou limpeza do disco).`
    },
    get scores() {
      return t`Pontuações`
    },
    get timings() {
      return t`Tempos`
    },
    get toolTimings() {
      return t`Tempo de cada ferramenta`
    },
    jobVersion: (name: string, v: number) => t`${name} · v${v}`,
    get markIncorrect() {
      return t`Marcar como incorreto`
    },
    get markHint() {
      return t`A imagem vai para o treinamento com o resultado certo.`
    },
    shouldBe: (o: string) => t`Estava ${o}`,
    corrected: (o: string, by: string) =>
      by ? t`Corrigido: o certo era ${o} (por ${by}).` : t`Corrigido: o certo era ${o}.`,
    get marked() {
      return t`Resultado marcado como incorreto. A imagem vai para o treinamento.`
    },
    get downloadImage() {
      return t`Baixar imagem`
    },
    get sampledNote() {
      return t`Imagem guardada por amostragem.`
    },
  },
  dataset: {
    get viewImages() {
      return t`Ver imagens`
    },
    get hideImages() {
      return t`Ocultar imagens`
    },
    imagesOf: (name: string) => t`Imagens de ${name}`,
    get collected() {
      return t`coletada`
    },
    corrected: (label: string) => t`corrigida: ${label}`,
    get imagesEmpty() {
      return t`Nenhuma imagem ainda.`
    },
    imageAlt: (id: string, what: string) => t`${id}: ${what}`,
    get title() {
      return t`Dataset e coleta`
    },
    get intro() {
      return t`Imagens para treinar modelos. Ficam neste PC; o treinamento é feito fora da estação.`
    },
    get collecting() {
      return t`Modo de coleta`
    },
    get collectingHint() {
      return t`Toda imagem inspecionada também vai para o dataset.`
    },
    collectingOf: (name: string) => t`Modo de coleta de ${name}`,
    get images() {
      return t`Imagens`
    },
    get export() {
      return t`Exportar`
    },
    get exportAll() {
      return t`Exportar tudo`
    },
    exportOf: (name: string) => t`Exportar o dataset de ${name}`,
    exported: (id: string, count: number, folder: string) =>
      t`Dataset ${id}: ${count} imagens em ${folder}`,
    get empty() {
      return t`Nenhum job ainda`
    },
    total: (n: number) =>
      plural(n, {
        0: 'Nenhuma imagem no dataset',
        one: '# imagem no dataset',
        other: '# imagens no dataset',
      }),
    get loadError() {
      return t`Não foi possível ler o dataset.`
    },
  },
  settings: {
    get language() {
      return t`Idioma da estação`
    },
    get languageHint() {
      return t`A tela do operador fala este idioma. As outras telas também, até alguém escolher outro no menu da conta.`
    },
    get title() {
      return t`Configurações`
    },
    get intro() {
      return t`Configuração desta instalação (system.yaml). Não vai nos jobs; vai nos backups.`
    },
    dataRoot: (path: string) => t`Pasta de dados: ${path}`,
    get station() {
      return t`Estação`
    },
    get name() {
      return t`Nome da estação`
    },
    get shifts() {
      return t`Inícios de turno`
    },
    get shiftsHint() {
      return t`HH:MM separados por vírgula; os contadores recomeçam em cada um.`
    },
    get idle() {
      return t`Sair por inatividade após`
    },
    get resultMin() {
      return t`Mostrar o resultado por pelo menos`
    },
    get resultMinHint() {
      return t`Mesmo quando a estação já está pronta para a próxima peça.`
    },
    get markings() {
      return t`Marcações na imagem do operador`
    },
    get markingsHint() {
      return t`Quando a tela do operador desenha as regiões das ferramentas sobre a imagem.`
    },
    markingsOptions: {
      get always() {
        return t`Sempre`
      },
      get on_fail() {
        return t`Só em reprovação`
      },
      get never() {
        return t`Nunca`
      },
    },
    get operatorMarkings() {
      return t`O operador pode ligar e desligar as marcações`
    },
    get failSound() {
      return t`Som na reprovação`
    },
    get camera() {
      return t`Câmera`
    },
    get driver() {
      return t`Tipo de câmera`
    },
    drivers: {
      get uvc() {
        return t`USB (UVC, ex. C920)`
      },
      get file() {
        return t`Pasta de imagens (testes)`
      },
      get hikvision() {
        return t`Hikvision (IP)`
      },
    } as Record<string, string>,
    get deviceName() {
      return t`Nome do dispositivo`
    },
    get deviceNameHint() {
      return t`Ex.: C920. Ou use o caminho ou o índice.`
    },
    get devicePath() {
      return t`Caminho do dispositivo`
    },
    get deviceIndex() {
      return t`Índice do dispositivo`
    },
    get folder() {
      return t`Pasta das imagens`
    },
    get loop() {
      return t`Repetir as imagens`
    },
    get fps() {
      return t`Imagens por segundo`
    },
    get host() {
      return t`Endereço`
    },
    get port() {
      return t`Porta`
    },
    get user() {
      return t`Usuário`
    },
    get keyring() {
      return t`Senha da câmera (entrada no cofre do Windows)`
    },
    get keyringHint() {
      return t`O nome da entrada, nunca a senha.`
    },
    get testCamera() {
      return t`Testar câmera`
    },
    get recording() {
      return t`Gravação`
    },
    get sample() {
      return t`Guardar a imagem de 1 aprovado a cada`
    },
    get sampleHint() {
      return t`Reprovados e erros sempre guardam a imagem.`
    },
    get retention() {
      return t`Apagar registros com mais de`
    },
    get retentionHint() {
      return t`Vazio: guardar tudo.`
    },
    get minFree() {
      return t`Manter livre no disco pelo menos`
    },
    get backup() {
      return t`Backup`
    },
    get backupFolder() {
      return t`Pasta de backup`
    },
    get backupFolderHint() {
      return t`Pasta de rede ou pen drive. Vazio: dentro da pasta de dados.`
    },
    get testFolder() {
      return t`Testar pasta`
    },
    get every() {
      return t`Backup automático a cada`
    },
    get everyHint() {
      return t`Vazio: só quando pedido.`
    },
    get keep() {
      return t`Quantos guardar`
    },
    get include() {
      return t`O que incluir`
    },
    get includeAll() {
      return t`Todas as versões`
    },
    get includeLatest() {
      return t`Só a última versão de cada job`
    },
    get network() {
      return t`Rede`
    },
    get listen() {
      return t`Endereço de escuta`
    },
    get listenHint() {
      return t`127.0.0.1: só este PC. Outro valor abre para a rede (precisa de senha).`
    },
    get allowedHosts() {
      return t`Nomes aceitos na rede`
    },
    get allowedOrigins() {
      return t`Páginas de outros programas`
    },
    get allowedOriginsHint() {
      return t`Ex.: http://localhost:8800, separadas por vírgula.`
    },
    get save() {
      return t`Salvar configurações`
    },
    saved: (sections: string) => t`Configurações salvas: ${sections}.`,
    get nothingChanged() {
      return t`Nada mudou.`
    },
    get restart() {
      return t`Algumas mudanças só valem depois de reiniciar o programa:`
    },
    sections: {
      get station() {
        return t`estação`
      },
      get camera() {
        return t`câmera`
      },
      get recording() {
        return t`gravação`
      },
      get backup() {
        return t`backup`
      },
      get network() {
        return t`rede`
      },
    } as Record<string, string>,
    backupError: (e: string) => t`O último backup automático falhou: ${e}`,
    get loadError() {
      return t`Não foi possível ler as configurações.`
    },
    get hours() {
      return t`h`
    },
    get days() {
      return t`dias`
    },
    get minutes() {
      return t`min`
    },
    get seconds() {
      return t`s`
    },
    get gb() {
      return t`GB`
    },
    get images() {
      return t`imagens`
    },
  },
  access: {
    get title() {
      return t`Acessos`
    },
    get intro() {
      return t`O operador não usa senha. Supervisor e Mantenedor entram com a senha do perfil.`
    },
    get role() {
      return t`Perfil`
    },
    get password() {
      return t`Senha`
    },
    get changedAt() {
      return t`Última troca`
    },
    get set() {
      return t`Definida`
    },
    get notSet() {
      return t`Não definida`
    },
    change: (role: string) => t`Trocar a senha do ${role}`,
    define: (role: string) => t`Definir a senha do ${role}`,
    get newPassword() {
      return t`Senha nova`
    },
    get again() {
      return t`Repita a senha nova`
    },
    get current() {
      return t`Senha atual`
    },
    get rule() {
      return t`Pelo menos 8 caracteres. Ela não é mostrada de novo.`
    },
    get mismatch() {
      return t`As duas senhas não são iguais.`
    },
    get tooShort() {
      return t`Use pelo menos 8 caracteres.`
    },
    done: (role: string) => t`Senha do ${role} definida. As sessões dele foram encerradas.`,
    get revoke() {
      return t`Encerrar todas as sessões`
    },
    get revokeTitle() {
      return t`Encerrar todas as sessões?`
    },
    get revokeBody() {
      return t`Todos saem, inclusive você, e precisam entrar de novo.`
    },
    revoked: (n: number) =>
      plural(n, {
        0: 'Nenhuma sessão encerrada.',
        one: '# sessão encerrada.',
        other: '# sessões encerradas.',
      }),
  },
  audit: {
    get title() {
      return t`Auditoria`
    },
    get intro() {
      return t`O que mudou na estação, quando e por quem. Não se apaga.`
    },
    get kind() {
      return t`Evento`
    },
    get allKinds() {
      return t`Todos os eventos`
    },
    get when() {
      return t`Quando`
    },
    get details() {
      return t`Detalhes`
    },
    get exportCsv() {
      return t`Exportar CSV`
    },
    get empty() {
      return t`Nenhum evento`
    },
    get loadError() {
      return t`Não foi possível ler a auditoria.`
    },
    tuneHead: (by: string, from: number, to: number) => t`${by}: v${from} → v${to}`,
    get tuneVerified() {
      return t`verificada`
    },
    get tuneNotVerified() {
      return t`não passou na verificação`
    },
    kinds: {
      get activate() {
        return t`Job ativado`
      },
      get activate_override() {
        return t`Job ativado sem passar na verificação`
      },
      get import() {
        return t`Importação`
      },
      get restore() {
        return t`Restauração de backup`
      },
      get backup() {
        return t`Backup`
      },
      get backup_failed() {
        return t`Backup falhou`
      },
      get job_create() {
        return t`Job criado`
      },
      get job_save() {
        return t`Versão salva`
      },
      get job_duplicate() {
        return t`Job duplicado`
      },
      get job_tune() {
        return t`Ajuste fino`
      },
      get settings() {
        return t`Configurações alteradas`
      },
      get password_set() {
        return t`Senha definida`
      },
      get sessions_revoked() {
        return t`Sessões encerradas`
      },
      get camera_apply() {
        return t`Ajuste de câmera`
      },
      get dataset_export() {
        return t`Dataset exportado`
      },
    } as Record<string, string>,
  },
  shell: {
    get language() {
      return t`Idioma`
    },
    get languageNote() {
      return t`Vale só para você, neste navegador. A tela do operador usa o idioma da estação.`
    },
    get menu() {
      return t`Menu`
    },
    get collapse() {
      return t`Recolher menu`
    },
    get expand() {
      return t`Expandir menu`
    },
    get user() {
      return t`Conta`
    },
    get theme() {
      return t`Tema`
    },
    get themeSystem() {
      return t`Sistema`
    },
    get themeDark() {
      return t`Escuro`
    },
    get themeLight() {
      return t`Claro`
    },
    get noJob() {
      return t`Nenhum job`
    },
    get palette() {
      return t`Ir para…`
    },
    get palettePlaceholder() {
      return t`Nome da tela`
    },
    get paletteEmpty() {
      return t`Nada encontrado.`
    },
    get paletteScreens() {
      return t`Telas`
    },
  },
  live: {
    get connecting() {
      return t`Conectando…`
    },
    get offline() {
      return t`Sem conexão`
    },
    get reconnecting() {
      return t`Reconectando automaticamente.`
    },
    get pass() {
      return t`APROVADO`
    },
    get fail() {
      return t`REPROVADO`
    },
    get error() {
      return t`ERRO`
    },
    get couldNotInspect() {
      return t`Não foi possível inspecionar.`
    },
    get inspecting() {
      return t`Inspecionando…`
    },
    get cameraLost() {
      return t`Câmera desconectada`
    },
    get fault() {
      return t`Falha na verificação`
    },
    get callMaintenance() {
      return t`Chamar a manutenção.`
    },
    get maintenance() {
      return t`Em manutenção`
    },
    get preparing() {
      return t`Preparando…`
    },
    get waiting() {
      return t`Aguardando objeto`
    },
    get offlineBanner() {
      return t`Sem conexão com o programa da estação. O que aparece nesta tela pode estar desatualizado.`
    },
    get imageLabel() {
      return t`Imagem ao vivo da câmera`
    },
    get verdictLabel() {
      return t`Resultado`
    },
    get statusLabel() {
      return t`Estado do sistema`
    },
    get systemConnected() {
      return t`Esta tela está ligada ao programa da estação.`
    },
    get systemConnecting() {
      return t`Ligando esta tela ao programa da estação.`
    },
    get systemOffline() {
      return t`Esta tela perdeu a ligação com o programa e tenta de novo sozinha.`
    },
    get machineUnknown() {
      return t`Sem ligação com o sistema, o estado da máquina não é conhecido.`
    },
    get cameraUnknown() {
      return t`Sem ligação com o sistema, o estado da câmera não é conhecido.`
    },
    get logUnknown() {
      return t`Sem ligação com o sistema, não se sabe se os resultados estão sendo gravados.`
    },
    get logOk() {
      return t`Os resultados estão sendo gravados.`
    },
    get machineAwaiting() {
      return t`Ligada, mas a máquina ainda não deu sinal de vida.`
    },
    get machineSilent() {
      return t`A máquina não responde; nenhum disparo é aceito.`
    },
    lastResult: (word: string) => t`Último resultado: ${word}. Pode estar desatualizado.`,
  },
  ui: {
    get close() {
      return t`Fechar`
    },
    get cancel() {
      return t`Cancelar`
    },
    get somethingWrong() {
      return t`Algo deu errado`
    },
    get retry() {
      return t`Tentar de novo`
    },
    get details() {
      return t`Detalhes`
    },
    get hideDetails() {
      return t`Ocultar detalhes`
    },
    get skipToContent() {
      return t`Pular para o conteúdo`
    },
    get current() {
      return t`(atual)`
    },
    get suggestions() {
      return t`Sugestões`
    },
    get showTable() {
      return t`Ver como tabela`
    },
    get pages() {
      return t`Páginas`
    },
    get previousPage() {
      return t`Página anterior`
    },
    get nextPage() {
      return t`Próxima página`
    },
    get stepDone() {
      return t`concluído`
    },
    get stepCurrent() {
      return t`passo atual`
    },
    get stepTodo() {
      return t`pendente`
    },
    get stepAttention() {
      return t`precisa de atenção`
    },
    get stepBlocked() {
      return t`bloqueado`
    },
    get movable() {
      return t`item que pode ser movido`
    },
    get dragHelp() {
      return t`Para mover, pressione Espaço ou Enter; use as setas para cima e para baixo; Espaço ou Enter de novo para soltar, Esc para cancelar.`
    },
    get notFoundTitle() {
      return t`Página não encontrada`
    },
    get noServer() {
      return t`Não foi possível falar com o programa da estação.`
    },
    get filters() {
      return t`Filtros`
    },
    get importing() {
      return t`Importando…`
    },
    get differences() {
      return t`Diferenças`
    },
    get versionColumn() {
      return t`Versão`
    },
    get commaSeparated() {
      return t`Separados por vírgula`
    },
    get invalidJson() {
      return t`JSON inválido`
    },
    get notUsed() {
      return t`Não usado`
    },
    get regionsLabel() {
      return t`Regiões sobre a imagem`
    },
    get referenceImage() {
      return t`imagem de referência`
    },
    get toolColumn() {
      return t`Ferramenta`
    },
    get fileColumn() {
      return t`Arquivo`
    },
    get dateColumn() {
      return t`Data`
    },
    get liveImageReduced() {
      return t`imagem ao vivo (reduzida)`
    },
    exactValue: (name: string) => t`${name} (valor exato)`,
    pageRange: (from: number, to: number, total: number) => t`${from}–${to} de ${total}`,
    move: (name: string) => t`Mover ${name}`,
    place: (position: number, total: number) => t`posição ${position} de ${total}`,
    dragStart: (name: string, place: string) => t`${name} pego para mover, na ${place}.`,
    dragOver: (name: string, place: string) => t`${name} na ${place}.`,
    dragOut: (name: string) => t`${name} fora da lista.`,
    dragEnd: (name: string, place: string) => t`${name} solto na ${place}.`,
    dropped: (name: string) => t`${name} solto.`,
    dragCancel: (name: string) => t`Movimento cancelado. ${name} voltou ao lugar.`,
    badFileType: (files: string, accept: string) =>
      t`Tipo de arquivo não aceito: ${files}. Use ${accept}.`,
    commaSeparatedHint: (hint: string) => t`${hint} · separados por vírgula`,
    notUsedHint: (hint: string) => t`${hint} (não usado)`,
    defaultValue: (value: string) => t`padrão: ${value}`,
    // the parameter forms and the settings levels (docs/frontend.md §17, §19.2)
    get groupMeasure() {
      return t`O que medir`
    },
    get groupCriteria() {
      return t`Critérios`
    },
    get levelLabel() {
      return t`Nível dos ajustes`
    },
    levels: {
      get 1() {
        return t`Essencial`
      },
      get 2() {
        return t`Avançado`
      },
      get 3() {
        return t`Especialista`
      },
    },
    hiddenChanged: (n: number) =>
      plural(n, {
        one: '# ajuste oculto foi alterado',
        other: '# ajustes ocultos foram alterados',
      }),
    sectionChanged: (n: number) => plural(n, { one: '# alterado', other: '# alterados' }),
    get hiddenChangedHide() {
      return t`Esconder os ajustes alterados`
    },
    get hiddenChangedHint() {
      return t`Mostrar só os ajustes alterados que o nível atual esconde`
    },
    imageSize: (width: number, height: number, source: string) =>
      t`${width} × ${height} px · ${source}`,
  },
} as const

/** Who saved a version: a profile is shown by its name ("Mantenedor"), any other author as written. */
export function authorName(author: string): string {
  return author in text.roles ? text.roles[author as keyof typeof text.roles] : author
}
