# Guia de Instalação Passo a Passo — Nox Archinstall (`v1.0.1` Estável)

Este guia explica, do começo ao fim e sem exigir experiência avançada com o `archinstall`, como instalar o **Nox Archinstall (Project Nox)** a partir da mídia oficial do Arch Linux mantendo verificação criptográfica de integridade em todos os estágios.

O fluxo completo resume-se a:

> **ISO oficial do Arch Linux → Conexão com a Internet → Comando Oficial Verificado (SHA-256) → `[1/4]` Seleção do Disco → `[2/4]` Confirmação do Disco → `[3/4]` Usuário → `[4/4]` Senha → Confirmação Destrutiva Final → Instalação Automática → Reinicialização.**

---

## 1. Antes da instalação (Pré-requisitos e Preparação)

### 1.1. Faça backup dos seus arquivos pessoais
A instalação do Project Nox **formatará integralmente o SSD escolhido**, recriando a tabela de partições GPT (`/boot` de 4 GiB em FAT32 + partição raiz em Btrfs). Copie qualquer documento, chave, foto ou projeto importante para um disco externo ou nuvem antes de iniciar.

### 1.2. Requisitos mínimos do computador
- **Processador (CPU):** compatível com **`x86-64-v4`** (AMD Ryzen séries 7000/9000 — Zen 4 / Zen 5). O instalador verifica esse requisito automaticamente na etapa `00-preflight` porque utiliza os repositórios otimizados `cachyos-znver4`.
- **Modo de inicialização da placa-mãe:** **UEFI 64 bits** (modo CSM / Legacy BIOS desativado).
- **Espaço livre no SSD de destino:** mínimo técnico de **20 GiB** (recomendado **64 GiB ou mais**; em máquinas físicas com `>= 24 GiB` de RAM e disco amplo, o instalador dimensiona o swapfile Btrfs de 32 GiB automaticamente).
- **Conexão ativa com a internet:** necessária durante toda a instalação para baixar os pacotes oficiais do Arch Linux, do CachyOS e o payload verificado da versão.

### 1.3. ISO oficial homologada e versão do `archinstall`
- O Project Nox **não** possui ISO própria: você deve usar a **ISO oficial do Arch Linux**.
- O instalador foi homologado na ISO oficial **`archlinux-2026.11.01-x86_64.iso`**, que traz o **`archinstall 4.5`**.
- Por segurança, o assistente `nox-install.py` verifica automaticamente se está rodando como `root` em modo UEFI dentro da ISO oficial (`/run/archiso`) e se a versão do `archinstall` pertence à série homologada **`4.5`** (`4.5` ou `4.5.*`), bloqueando qualquer execução acidental no sistema hospedeiro.

### 1.4. Por que o Secure Boot deve estar desativado para iniciar a ISO oficial
Em configurações padrão de fábrica, a ISO oficial do Arch Linux pode ser bloqueada caso o **Secure Boot** esteja ativo na placa-mãe.

- **Recomendação obrigatória para a instalação:** antes de dar boot pelo pendrive da ISO do Arch Linux, entre na BIOS/UEFI (tecla `Del` na MSI PRO B650M-P) e confirme que **Secure Boot** está como **`Disabled`**.
- **Não apague nem altere as chaves do firmware antes de instalar o sistema.** As etapas 1, 2 e 3 do Secure Boot (geração das chaves locais `sbctl`, assinatura dos binários EFI/kernel e inscrição do hash BLAKE2B em `/boot/limine.conf`) são preparadas automaticamente durante a instalação. As etapas 4 e 5 (inscrição das chaves na NVRAM e ativação do Secure Boot na BIOS) serão realizadas depois, com o sistema já instalado e funcionando, seguindo [`docs/SECURE-BOOT.md`](SECURE-BOOT.md) ou [`docs/SECURE-BOOT-MSI.md`](SECURE-BOOT-MSI.md).

### 1.5. Como confirmar que a ISO iniciou em modo UEFI
Assim que o pendrive carregar e você cair no prompt `root@archiso ~ #`, confirme que o sistema iniciou em modo UEFI executando:

```bash
ls /sys/firmware/efi/efivars
```

- **Resultado esperado:** uma lista de variáveis EFI é exibida na tela. (Se o diretório não existir, a placa-mãe iniciou o pendrive em modo Legacy/CSM; reinicie na BIOS e selecione a entrada `UEFI: <seu pendrive>`).

---

## 2. Conexão à Internet na ISO Oficial

### 2.1. Conexão via cabo de rede (Ethernet)
Se o computador estiver conectado por cabo Ethernet ao roteador, a ISO oficial do Arch Linux obtém endereço IP automaticamente via DHCP (`systemd-networkd`). Pule para a [Seção 2.3](#23-como-confirmar-a-conectividade).

### 2.2. Conexão via Wi-Fi (`iwctl`)
Se for instalar usando Wi-Fi (como a placa **Intel AX210**), utilize o utilitário nativo `iwctl` da ISO do Arch Linux:

1. Liste sua interface Wi-Fi (geralmente `wlan0`):
   ```bash
   iwctl device list
   ```
2. Faça a varredura e liste as redes disponíveis:
   ```bash
   iwctl station wlan0 scan
   iwctl station wlan0 get-networks
   ```
3. Conecte-se à sua rede Wi-Fi (substitua `NOME_DA_REDE` pelo SSID exato; a senha será solicitada a seguir):
   ```bash
   iwctl station wlan0 connect "NOME_DA_REDE"
   ```
4. Aguarde cerca de 5 segundos para a atribuição de IP.

### 2.3. Como confirmar a conectividade
Execute no terminal da ISO:

```bash
curl -I https://archlinux.org
```

- **Resultado esperado:** resposta contendo `HTTP/2 200` (ou `HTTP/1.1 200 OK`).
- **Se DNS ou HTTPS falhar:**
  - Verifique se o relógio do sistema na BIOS está com data coerente: `timedatectl status` (ative a sincronização com `timedatectl set-ntp true`).
  - Confira se a interface recebeu endereço IP: `ip addr show`.

---

## 3. Cadeia de Confiança e Comando Oficial de Instalação

> **Estado das versões no GitHub:**
> - **Release estável atual (`v1.0.1` — `Latest` e Imutável):** publicada em [`releases/tag/v1.0.1`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.1). **Este é o comando oficial vigente para execução imediata na ISO.**
> - **Próxima revisão preparada (`v1.0.2` — Em Revisão):** integração obrigatória do `discord-game-presence` e suporte AUR isolado a `checkdepends` + `validpgpkeys` em [`manifests/release.json`](../manifests/release.json) e [`RELEASE-NOTES-v1.0.2.md`](RELEASE-NOTES-v1.0.2.md) (aguardando aprovação humana para merge e publicação).
> - **Release anterior preservada (`v1.0.0`):** mantida intacta para referência histórica em [`releases/tag/v1.0.0`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.0).

### Comando Oficial Verificado — Release Estável Publicada `v1.0.1` (Vigente)

| Artefato (`v1.0.1` Publicada) | Origem Congelada | SHA-256 Verificado |
|---|---|---|
| `nox-install.py` | [`releases/download/v1.0.1/nox-install.py`](https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/nox-install.py) | `fa6c2a3b1ee86cd60976857555326bf6a63c341914e9c061f557a62a74e03b47` |
| `user_configuration.json` | [`releases/download/v1.0.1/user_configuration.json`](https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/user_configuration.json) | `9cb32121cb9a87b54b7c07749a92d3b8cb6cffcf6e4dadc502f3fa9a3da3a867` |
| `nox-archinstall-payload-v1.0.1.tar.gz` | [`releases/download/v1.0.1/nox-archinstall-payload-v1.0.1.tar.gz`](https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/nox-archinstall-payload-v1.0.1.tar.gz) | `52008f9c454c8b39c91d6e51b3546f6a76546f021c3c6a0850dc7a55d5bf92b2` |
| `nox-archinstall-payload-v1.0.1.tar.gz.sha256` | [`releases/download/v1.0.1/nox-archinstall-payload-v1.0.1.tar.gz.sha256`](https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/nox-archinstall-payload-v1.0.1.tar.gz.sha256) | `c6d52792ff1e1038663c633ea81a4f96d9db953ef54139a221b00ee46373ccf0` |

> **AVISO DESTRUTIVO:** O disco selecionado durante a instalação será **formatado integralmente** e **todos os dados existentes serão apagados permanentemente**.

Execute na ISO oficial do Arch Linux (**recomendado**, usando diretório temporário seguro via `mktemp -d`, limpeza automática via `trap` e `umask 022` antes do `python3`):

```bash
sh -c 'set -eu; d=$(umask 077; mktemp -d); trap "rm -rf \"$d\"" EXIT INT TERM; \
curl --proto "=https" --proto-redir "=https" --tlsv1.2 -fsSL https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/nox-install.py -o "$d/nox-install.py"; \
printf "%s  %s/nox-install.py\n" "fa6c2a3b1ee86cd60976857555326bf6a63c341914e9c061f557a62a74e03b47" "$d" | sha256sum -c -; \
curl --proto "=https" --proto-redir "=https" --tlsv1.2 -fsSL https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/user_configuration.json -o "$d/nox-cfg.json"; \
printf "%s  %s/nox-cfg.json\n" "9cb32121cb9a87b54b7c07749a92d3b8cb6cffcf6e4dadc502f3fa9a3da3a867" "$d" | sha256sum -c -; \
umask 022; python3 "$d/nox-install.py" --config "$d/nox-cfg.json"'
```

> **Nota sobre `umask` e modelo de confiança:** O download é feito em subshell com `umask 077` para manter os temporários restritos (`0600`), os dois arquivos passam por `sha256sum -c -` antes de executar código Python, e `umask 022` é garantido antes de invocar o `archinstall`. Sem chave pública offline pré-instalada na ISO do Arch Linux, a autenticidade apoia-se em HTTPS/TLSv1.2+ sem downgrade para HTTP e pinagem criptográfica SHA-256 explícita.

### Cadeias Acíclicas e Histórico (`v1.0.2` em Revisão, `v1.0.1` e `v1.0.0`)

A cadeia congelada completa da **`v1.0.2`** (preparada para revisão em [`manifests/release.json`](../manifests/release.json), ainda não publicada enquanto `v1.0.1` permanece `Latest`) utiliza (`i` `761725f7279fc11b086f76ab806bef204aec5eba` → `bootstrap/nox-install.py` `f9f6c46ba7461d5b6166d34706a5bd868ad628c6` → `user_configuration.json` `e50bab32d642dee85ede329100ba451d2f82f491` → `nox-archinstall-payload-v1.0.2.tar.gz`):
- `i`: `a517cb46a9a1079a1370234dd1be6c9b37a87782be055364932ed58571e7ba05`
- `nox-install.py`: `6d0bf5a220badb5c67d057d7ae81947ff90fca6011c4de4b7a2f442bf8042ddf`
- `user_configuration.json`: `c7c27cbb719d2dce415c68b2c1926fcafd4656045cfe966ebb3331fb2ffe8775`
- `nox-archinstall-payload-v1.0.2.tar.gz`: `723c46bb9d6ae2965988e99d25b3198340feb24bdf7a71b5f4b0c1179fe5a774` (`sha256` `.sha256`: `249dd2367c6b7bec1f7145b798a8577f8988f0c2c02ef8603c61f27d71969d1f`)

Para conferência histórica, os digests originais da release anterior [`v1.0.0`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.0) (preservada no repositório) permanecem:
- `nox-install.py`: `fce3f9a83e2b8c13666cf583f143096de37b8dd312e59dd8c6af4acbabb82f10`
- `user_configuration.json`: `6754aefcdfb659e1abdfb5036c158a609d1672f945186a1e692edeab2e104e4c`
- `nox-archinstall-payload-v1.0.0.tar.gz`: `08fbf62a2325b2a3a4b30a3d7ec4b986bc17f412970ba25f83839624444d6fd9`

### O que o assistente verifica automaticamente antes de tocar no disco
1. Confirma que você está em um terminal interativo dentro da ISO oficial do Arch Linux (`/run/archiso`) em modo UEFI com **`archinstall 4.5`**.
2. Carrega e valida via **SHA-256** a configuração base antes de interpretar o JSON.
3. Valida o formato, esquema HTTPS e hash **SHA-256** do payload da versão sem permitir downgrade para HTTP.
4. Lista os discos elegíveis (`>= 20 GiB`, excluindo a mídia da ISO) para que você escolha o SSD com segurança.

---

## 4. As 4 Etapas Numeradas e Confirmação Destrutiva Final

> **AVISO CRÍTICO:** O disco selecionado na etapa `[1/4]` terá **todas as suas partições e dados apagados permanentemente**. Nunca tente adivinhar qual disco escolher.

### 4.1. Como identificar o SSD correto na lista (`[1/4]`)
O assistente exibe cada disco elegível com quatro informações claras:
1. **Tipo e barramento:** `[INTERNO]` vs `[USB/REMOVIVEL]` e o protocolo (`[nvme]`, `[sata]`, `[usb]`). O pendrive da própria ISO do Arch Linux já é filtrado automaticamente para não aparecer como destino.
2. **Caminho do dispositivo:** por exemplo, `/dev/nvme0n1` ou `/dev/sda`.
3. **Capacidade total em GiB:** por exemplo, `(931.5 GiB)` para um SSD de 1 TB ou `(465.8 GiB)` para um SSD de 500 GB.
4. **Modelo físico e identificador persistente (`by-id`):** por exemplo, `Kingston KC3000`, `WD Black SN770`, `Samsung SSD 980`.

### 4.2. Dupla confirmação de segurança (`[1/4]`, `[2/4]` e confirmação final)
Para evitar qualquer formatação acidental por erro de digitação:
1. **Escolha do SSD (`[1/4]`):** digite o **número** correspondente ao SSD na lista (por exemplo, `1`) — nenhum disco é selecionado automaticamente se você apenas apertar `Enter`.
2. **Confirmação destrutiva do dispositivo (`[2/4]`):** o assistente mostra o resumo do disco escolhido e exige que você **digite exatamente o nome curto do dispositivo** (por exemplo, `nvme0n1` ou `vda`). Se o texto digitado não coincidir, a instalação é cancelada imediatamente sem alterar nada.
3. **Confirmação final antes de formatar:** após informar usuário e senha, o assistente apresenta o quadro **`RESUMO FINAL ANTES DE FORMATAR`** e pergunta `Confirmar e iniciar a instalacao agora? [s/N]:`. Nenhuma partição é tocada antes de você responder `s` nessa última confirmação.

---

## 5. Usuário, Senha e Privilégios (`sudo`)

Nas etapas `[3/4]` e `[4/4]`:

1. **Nome de usuário (`[3/4]`):**
   - Digite o nome do seu usuário principal em letras minúsculas (por exemplo, `awerkori`).
   - O nome deve começar com letra minúscula ou `_` e conter apenas letras minúsculas, números, `_` ou `-` (máximo de 32 caracteres). Contas reservadas como `root`, `greeter` ou `noxbuild` são recusadas.
2. **Definição e confirmação da senha (`[4/4]`):**
   - Digite sua senha e pressione `Enter`; em seguida, digite a mesma senha novamente para confirmar.
   - Por segurança, **nenhum caractere ou asterisco aparece na tela** enquanto você digita a senha, e a senha em texto puro é convertida imediatamente em hash SHA-512 (`$6$`) dentro de `tmpfs` em RAM (`/dev/shm`, permissão `0700`/`0600`), sendo removida dos diretórios de log ao final da execução.
3. **Como funcionam o `sudo` e a conta `root` no Project Nox:**
   - Seu usuário é adicionado automaticamente ao grupo `wheel`.
   - Sempre que precisar executar comandos administrativos (`sudo ...`), você utilizará **a sua própria senha de usuário** (sem regras `NOPASSWD`).
   - A conta `root` permanece **bloqueada para login direto** (`passwd -S root` → `L`).

Quando o processo terminar e voltar ao prompt da ISO, reinicie o computador e remova o pendrive:

```bash
reboot
```

---

## 6. Depois da instalação (Primeiro Boot e Primeiro Login)

Nenhuma configuração manual é necessária após reiniciar:

1. **Menu de Boot Limine:**
   - Você verá o menu do **Limine** com o tema escuro **Project Nox** e o emblema roxo/dourado no canto superior direito.
   - A entrada padrão **`Arch Linux → Project Nox`** (`linux-cachyos`) inicia automaticamente após **5 segundos** (ou imediatamente se você pressionar `Enter`).
2. **Tela de Login (Noctalia Greeter):**
   - O **Noctalia Greeter** será exibido com o relógio centralizado, seu nome de usuário já selecionado e a sessão **`Umbriel`** ativa.
   - Digite sua senha e pressione `Enter`.
3. **Primeiro Login no Desktop (Umbriel + Noctalia Shell):**
   - O compositor **Umbriel** (em layout `dwindle`) e a barra superior do **Noctalia Shell** carregam automaticamente.
   - O wallpaper animado entra em execução via `mpvpaper`.
   - Se os dois monitores de referência (Samsung Odyssey G5 em `DP-1` e AOC vertical em `HDMI-A-1`) estiverem conectados, o `nox-display-profile` aplica automaticamente as resoluções (`2560x1440@165Hz` e `1920x1080@100Hz` rotacionado a 90°) e sincroniza a animação entre ambos.
4. **Atalhos principais para começar a usar:**
   - `Super` ou `Super + R`: abre o **Launcher minimalista** do Noctalia (`Firefox`, `kitty`, `Luciole`, `ProtonPlus`, ou digite `/tools` para ferramentas técnicas).
   - `Super + Q`: abre o terminal **Kitty** (exibindo o painel `nox-fastfetch`).
   - `Super + E` ou `Ctrl + E`: abre o gerenciador de arquivos **Luciole**.
   - `Super + C`: fecha a janela focada.
   - `Super + L`: bloqueia a sessão com a **Noctalia Lock Screen**.
   - Consulte todos os atalhos em [`docs/KEYBINDS_MIGRATION.md`](KEYBINDS_MIGRATION.md).
5. **Verificação rápida pós-instalação:**
   Abra o terminal Kitty (`Super + Q`) e confirme o status da instalação, a integridade criptográfica do boot e a ausência de unidades com falha:
   ```bash
   cat /var/lib/nox-archinstall/status.json
   sudo nox-secureboot-verify
   systemctl --failed
   systemctl --user --failed
   ```
   Para verificações adicionais de hardware físico (GPU, áudio Fuxi H3, Wi-Fi AX210, Topgrade) e ativação futura do Secure Boot, consulte [`docs/POST_INSTALL_CHECKS.md`](POST_INSTALL_CHECKS.md) e [`docs/SECURE-BOOT-MSI.md`](SECURE-BOOT-MSI.md).
