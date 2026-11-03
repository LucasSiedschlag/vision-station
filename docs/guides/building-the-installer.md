# Guia para gerar o instalador — Vision Station

Para quem mantém o programa. Gera o `VisionStation-<versão>-setup.exe` que o [guia de instalação](instalacao.md) usa. O build é feito **no Windows**: o driver da C920 (duvc-ctl) só existe lá.

## 1. O que é preciso (uma vez por PC)

| O quê | Para quê | Como instalar |
|---|---|---|
| Windows 10 ou 11, 64 bits | o programa e o instalador são para Windows | — |
| git | baixar o código e carimbar o commit na versão | `winget install Git.Git` |
| uv | Python 3.12 e as bibliotecas do programa | `winget install astral-sh.uv` |
| Node 24 | gerar a interface (React) | nvm-windows: `nvm install 24` e `nvm use 24` |
| Inno Setup 6 | montar o instalador | `winget install JRSoftware.InnoSetup` |
| Internet | na primeira vez: bibliotecas, pacotes da interface e o WinSW | — |

Para conferir, abra um terminal novo (cmd ou PowerShell):

```
git --version
uv --version
node -v          (deve mostrar v24.x)
npm -v
```

O Inno Setup não fica no PATH: o script procura o `ISCC.exe` em `C:\Program Files (x86)\Inno Setup 6\` e em `%LOCALAPPDATA%\Programs\Inno Setup 6\`.

## 2. Gerar

1. Atualize o código, na pasta do projeto: `git pull`.
2. Confira a versão em `pyproject.toml` (`version`) e em `src\vision_station\__init__.py` (`__version__`). As duas precisam ser iguais; o nome do instalador e a página *Sobre* usam esse número. Para uma entrega nova, aumente as duas antes do build.
3. Rode o build:
   - **com dois cliques** em `packaging\gerar-instalador.cmd`; ou
   - num terminal, na pasta do projeto: `packaging\gerar-instalador.cmd`.

   Só o programa, sem o instalador (não precisa do Inno Setup): `packaging\gerar-instalador.cmd -NoInstaller`.

O atalho chama o `packaging\build_windows.ps1`, que faz, em ordem:

1. instala o Python e as bibliotecas, com o driver da C920 (`uv sync --extra uvc --group build`);
2. gera a interface (`npm ci` e `npm run build` em `frontend\`);
3. grava a versão, o commit e a data do build (aparecem em *Sobre* e em `vision-station.exe --version`);
4. gera a lista de licenças `THIRD_PARTY_LICENSES.md` (**para** se aparecer uma licença copyleft, NFR-LIC-1);
5. monta o programa com o PyInstaller e confere que ele abre (`vision-station.exe --version`);
6. baixa o WinSW, o programa que roda o Vision Station como serviço, se ainda não estiver na pasta;
7. monta o instalador com o Inno Setup.

Medido no PC da bancada (16/10/2026), sem o instalador: uns **3 minutos** numa pasta nova e uns **2 minutos** nas vezes seguintes. Num PC que nunca baixou as bibliotecas, a primeira vez demora mais.

## 3. O que sai

| Arquivo | O que é |
|---|---|
| `dist\VisionStation-<versão>-setup.exe` | o instalador: é ele que vai para o PC da estação |
| `dist\vision-station\` | o programa montado (o instalador leva esta pasta) |
| `THIRD_PARTY_LICENSES.md` | as licenças de tudo o que vai junto; entregue junto com o instalador |
| `packaging\build_info.json` | versão, commit e data deste build |

Nenhum desses arquivos vai para o git.

## 4. Conferir antes de entregar

1. `dist\vision-station\vision-station.exe --version` mostra a versão e o commit certos (o script já roda isso; confira o commit).
2. Instale num PC de teste seguindo o [guia de instalação](instalacao.md) e abra a página *Sobre*: versão, commit e data do build.
3. Com a câmera ligada, a estação chega a *Aguardando…* e uma inspeção de teste dá resultado.

## 5. Sem montar no PC: baixar do CI

A cada envio para o GitHub, o CI monta o instalador no Windows com o mesmo script, inicia o programa e confere que a API e a interface respondem. Para baixar: GitHub → *Actions* → workflow *tests* → a execução do commit → artefato **installer** (um `.zip` com o instalador e a lista de licenças).

## 6. Problemas

| O que aparece | O que fazer |
|---|---|
| `node` não é reconhecido, ou *The path cannot be traversed because it contains an untrusted mount point* | O nvm-windows criou a pasta `.nodejs` sem ser administrador e o Windows não a segue. Num PowerShell **como administrador**, logado no seu usuário: `$n = "$env:LOCALAPPDATA\Author Software\nvm"`, depois `cmd /c rmdir "$n\.nodejs"` e `cmd /c mklink /J "$n\.nodejs" "$n\.shim"`. Abra um terminal novo. |
| *Inno Setup 6 not found* | Instale com `winget install JRSoftware.InnoSetup`, ou gere só o programa com `-NoInstaller`. |
| *a execução de scripts foi desabilitada neste sistema* | Use o `packaging\gerar-instalador.cmd`: ele já roda o script com a permissão necessária. |
| *duvc-ctl* não instala | O build precisa ser feito no Windows (no macOS e no Linux esse pacote não existe). |
| Falha ao baixar o WinSW | Sem internet: copie o `WinSW-x64.exe` da versão 2.12.0 para `packaging\winsw\VisionStation.exe` e rode de novo. |
| Não consegue apagar `dist\vision-station` | O programa montado está aberto (ou um terminal está dentro da pasta): feche e rode de novo. |
| *WARNING: Hidden import "tzdata" not found* | Pode ignorar: o programa não usa fusos horários pelo nome. |
| *copyleft* na lista de licenças | Uma biblioteca nova tem licença GPL/AGPL e não pode ir no produto (TD-18): troque a biblioteca. |
