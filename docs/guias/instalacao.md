# Guia de instalação — Vision Station

Para o Mantenedor. Leva cerca de 30 minutos num PC novo, sem contar a montagem da câmera e da luz.

## 1. O que é preciso

- **PC:** Windows 11 Pro 64 bits, Intel Core i5 de 12ª geração ou melhor, 16 GB de memória, SSD de 512 GB, monitor de 21" ou maior, nobreak. Especificação completa no documento 04, §3.
- **Câmera:** a C920 numa porta USB 3, ou a câmera IP na rede (driver Hikvision, depois da primeira entrega).
- **O instalador:** `VisionStation-<versão>-setup.exe` (gerado como explica o [guia para gerar o instalador](gerar-instalador.md), ou baixado do CI, artefato *installer*).
- **Microsoft Edge:** já vem no Windows 11; é a tela do operador.

## 2. Instalar

1. Entre no Windows com um usuário administrador e rode `VisionStation-<versão>-setup.exe`.
2. **Como o programa inicia:**
   - **Como serviço do Windows** (recomendado): inicia sozinho quando o PC liga, sem ninguém entrar, e reinicia se cair.
   - **Ao entrar no Windows:** use se a câmera USB não abrir pelo serviço (veja *Problemas*). O programa inicia quando o usuário da estação entra.
3. **Tela do operador:** marque *Abrir a tela do operador em tela cheia* para o Edge abrir a estação em modo quiosque sempre que alguém entrar no Windows.
4. No fim, marque **Definir agora a senha do Mantenedor**: abre uma janela que pede a senha duas vezes (pelo menos 8 caracteres).

Onde fica cada coisa:

| O quê | Onde |
|---|---|
| Programa | `C:\Program Files\VisionSystem\` |
| Dados (jobs, resultados, imagens, configuração, logs) | `C:\ProgramData\VisionSystem\` |
| Configuração da instalação | `C:\ProgramData\VisionSystem\system\system.yaml` |
| Registro do programa | `C:\ProgramData\VisionSystem\logs\` |

## 3. Primeira configuração

1. No PC da estação, abra **http://127.0.0.1:8765** (menu Iniciar → *Vision Station*). Na primeira vez a tela do operador mostra "Esta instalação ainda não foi configurada" e o botão **Configurar agora**; ele abre o **assistente de instalação** (`/setup`). Depois, ele fica em **Configurações → Assistente de instalação**.
2. **Senha do Mantenedor:** crie a senha (pelo menos 8 caracteres). Esta é a única etapa sem login, e só funciona no próprio PC da estação, uma vez. Anote a senha: não há como recuperá-la sem acesso ao PC.
3. **Câmera:** o assistente lista as câmeras USB ligadas. Cada uma aparece como *Validada* ou *Não validada* (modelo ainda sem ensaio de bancada). Escolha a câmera, **Testar câmera** e **Usar esta câmera**. A câmera só muda depois de reiniciar o programa: no Windows, *Serviços* → *Vision Station* → *Reiniciar* (ou reinicie o PC). O passo fica pronto quando a imagem chega.
4. **Senha do Supervisor:** defina a senha do Supervisor.
5. **Backup:** escolha a pasta (rede ou pen drive), **Testar pasta**, depois **Salvar a pasta de backup** e defina a frequência.
6. **Primeiro job:** o botão abre o editor no primeiro passo. Você também pode importar o job da estação (`.vjob`, ou o backup `.vbak` da instalação anterior) em **Jobs**. Depois **Ativar**: o sistema confere o job no conjunto de referência antes de usar.

Os passos *Desempenho do PC* e *Máquina* aparecem desligados, com o motivo: chegam em fases seguintes e não impedem a estação de trabalhar. Quando a senha, a câmera e o job estiverem prontos, o assistente mostra **Ir para a estação**.

Se outro programa da estação (por exemplo o da estação de embalagem) vai usar o Vision Station pela tela dele, ponha o endereço da página dele em **Configurações → Rede → Páginas de outros programas** (documento 06).

## 4. Atualizar

Rode o instalador da versão nova. Ele para o programa, troca os arquivos e inicia de novo. **Os dados ficam**: jobs, resultados, configuração e senhas. Jobs de formatos antigos são convertidos ao serem lidos.

Antes de atualizar, faça um backup (**Jobs → Fazer backup**).

## 5. Desinstalar

*Configurações do Windows → Aplicativos → Vision Station → Desinstalar.* O serviço e a tarefa são removidos. **A pasta de dados não é apagada**; apague `C:\ProgramData\VisionSystem\` à mão só se tiver certeza.

## 6. Problemas comuns

| O que aparece | O que fazer |
|---|---|
| A tela não abre (página não encontrada) | O programa não está rodando. *Serviços* → *Vision Station* → *Iniciar*. Veja o registro em `logs\` |
| "Câmera desconectada" o tempo todo com a C920 | Feche qualquer programa que use a câmera (app da Logitech, Teams, navegador). Se continuar e o programa roda como serviço, reinstale escolhendo **Ao entrar no Windows** (uma câmera USB às vezes não abre fora da sessão do usuário) |
| "A interface não foi compilada" | Instalador gerado sem a interface: gere de novo ([guia para gerar o instalador](gerar-instalador.md)) |
| "Nenhum job ativo" | Ative um job em **Jobs** |
| "Falha na verificação — chamar manutenção" | A câmera ou a imagem mudou desde que o job foi feito (câmera movida, foco, luz). O detalhe aparece na tela. Corrija a câmera e, como Mantenedor, toque **Tentar de novo** na tela da estação; se a cena mudou de vez, ajuste o job no editor e ative a versão nova |
| O programa não inicia e o registro fala do `system.yaml` | O arquivo foi editado com erro; o registro diz onde. Corrija ou apague o arquivo (volta aos padrões) |
| Esqueceu a senha | No PC, em um prompt de administrador: `"C:\Program Files\VisionSystem\vision-station.exe" --set-password maintainer --data C:\ProgramData\VisionSystem` |

Para suporte, junte a pasta `C:\ProgramData\VisionSystem\logs\` e o `system.yaml` (não tem senhas).
