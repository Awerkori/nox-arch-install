# Créditos, Atribuições e Licenças — Nox Archinstall (`v1.0.0` / `v1.0.1`)

O **Nox Archinstall (Project Nox)** é um projeto pessoal de automação e configuração que integra diversos softwares livres e projetos de código aberto da comunidade Linux. Este documento distingue claramente o que faz parte da automação própria deste repositório e o que pertence aos respectivos projetos upstream.

---

## 1. Código e Configurações Próprias deste Repositório

Os scripts de instalação, assistente de bootstrap, hooks de integridade, wrappers de recuperação, geradores de identidade visual e arquivos de configuração próprios deste repositório são licenciados sob a **[GNU Affero General Public License v3.0 (AGPL-3.0)](../LICENSE)**:

- **Assistente e Bootstrap:** `bootstrap/nox-install.py`, `bootstrap/nox-bootstrap.sh`, `install.sh` e `scripts/build-release.sh`.
- **Pipeline de Instalação (`00..90`):** `scripts/00-preflight.sh` a `scripts/90-first-boot.sh` e biblioteca `scripts/lib/common.sh`.
- **Helpers e Serviços do Sistema:**
  - `configs/bin/nox-display-profile` (detecção automática de topologia de monitores via sysfs/EDID e fallback VM).
  - `configs/bin/nox-noctalia-layout` (sincronização de layout e IPC do `mpvpaper`).
  - `configs/bin/nox-limine-normalize`, `configs/bin/nox-limine-integrity` e `configs/bin/nox-limine-snapper-restore` (normalização de entradas do Limine, verificação BLAKE2B e restauração assistida de snapshots).
  - `configs/bin/nox-secureboot-enroll` e `configs/bin/nox-secureboot-verify` (wrappers auditáveis para `sbctl`).
  - `configs/bin/nox-fuxi-h3-fix` (ajuste dinâmico de volume PCM ALSA/PipeWire para o receptor USB do Havit Fuxi H3).
  - `configs/bin/nox-snapper-cleanup` e `configs/bin/nox-topgrade` (consolidação de snapshots `PRE`/`POST` por sessão de atualização).
  - `configs/bin/nox-fastfetch`, `configs/bin/nox-system-tools-list` e `configs/bin/nox-system-tools-launch`.
- **Assets Visuais Personalizados (`Obsidian Purple`):**
  - Wallpapers estáticos e animados gerados programaticamente por `tools/generate_nox_visuals.py` e `tools/generate_braille_logo.py` (`configs/wallpapers/nox-g5-runtime.webm`, `nox-aoc-runtime.webm`, `nox-g5.png`, `nox-aoc.png`, `nox-greeter.png`, `nox-lockscreen.png`, `nox-limine.png`, `obsidian-purple.png`, `configs/icons/nox-lockscreen-emblem.gif`, `nox-emblem.png` e `emblema-mestre-1254.png`).

---

## 2. Projetos Upstream e Componentes de Terceiros

O Project Nox não reivindica autoria sobre nenhum dos sistemas, kernels, compositores, aplicativos ou bibliotecas instalados a partir dos repositórios oficiais do Arch Linux, CachyOS ou AUR. Todos os créditos pertencem aos seus respectivos autores e mantenedores:

| Projeto / Componente | Papel no Project Nox | Fonte / Referência Oficial | Licença Upstream |
|---|---|---|---|
| **Arch Linux** & **`archinstall`** | Sistema-base oficial, ISO de instalação e instalador base automatizado | [archlinux.org](https://archlinux.org/) · [github.com/archlinux/archinstall](https://github.com/archlinux/archinstall) | GPL-3.0 (archinstall) / Várias |
| **CachyOS** (`linux-cachyos`, `cachyos-settings`, `scx_loader`, `firefox-pure`, repos `znver4`) | Kernel otimizado, configurações de sistema, escalonador BPF `scx_lavd` e pacotes compilados para AMD Zen 4 | [cachyos.org](https://cachyos.org/) · [github.com/CachyOS](https://github.com/CachyOS) | GPL-2.0 / GPL-3.0 / MPL-2.0 |
| **Limine** (`limine`, `limine-mkinitcpio-hook`, `limine-snapper-sync`) | Bootloader UEFI moderno com verificação BLAKE2B de configuração e integração de snapshots Btrfs | [limine-bootloader.org](https://limine-bootloader.org/) · [github.com/Limine-Bootloader/Limine](https://github.com/Limine-Bootloader/Limine) · [gitlab.com/Zesko/limine-snapper-sync](https://gitlab.com/Zesko/limine-snapper-sync) | BSD-2-Clause / GPL-3.0 |
| **`sbctl`** (Morten Linderud / Foxboron) | Gerenciador de chaves UEFI Secure Boot, assinatura PE/EFI e banco de quirks de firmware (`FQ0001`) | [github.com/Foxboron/sbctl](https://github.com/Foxboron/sbctl) | MIT |
| **Umbriel** | Compositor Wayland dinâmico com suporte ao layout `dwindle` | Repositório oficial CachyOS (`cachyos/umbriel`) | GPL-3.0 / MIT |
| **Noctalia Shell & Noctalia Greeter** | Barra de status, launcher, lock screen, notificações e greeter Wayland para `greetd` | Repositório oficial CachyOS (`noctalia`, `noctalia-greeter`) | GPL-3.0 |
| **Luciole** (`luciole-git`) | Gerenciador de arquivos moderno compilado via AUR | [aur.archlinux.org/packages/luciole-git](https://aur.archlinux.org/packages/luciole-git) | Licença do projeto upstream |
| **`mpvpaper`** & **`mpv`** & **FFmpeg** | Reprodução de wallpapers animados em Wayland com controle via socket IPC | [github.com/GhostNaN/mpvpaper](https://github.com/GhostNaN/mpvpaper) · [mpv.io](https://mpv.io/) | GPL-3.0 / LGPL-2.1+ |
| **Snapper** & **`snap-pac`** & **`btrfs-progs`** | Gerenciamento de snapshots Btrfs e hooks automáticos de transações Pacman | [snapper.io](http://snapper.io/) · [github.com/wesbarnett/snap-pac](https://github.com/wesbarnett/snap-pac) | GPL-2.0 |
| **Kitty** | Emulador de terminal acelerado por GPU | [sw.kovidgoyal.net/kitty](https://sw.kovidgoyal.net/kitty/) | GPL-3.0 |
| **Topgrade** (`topgrade-bin`) | Orquestrador de atualizações do sistema | [github.com/topgrade-rs/topgrade](https://github.com/topgrade-rs/topgrade) | GPL-3.0 |
| **discord-game-presence** | Serviço de usuário em Python para detecção de jogos e envio de Rich Presence local para cliente Discord quando presente | [git.shouldnt.work/fuxino/discord-game-presence](https://git.shouldnt.work/fuxino/discord-game-presence) · [AUR](https://aur.archlinux.org/packages/discord-game-presence) | GPL-3.0-or-later |
| **ProtonPlus** & **Proton-CachyOS SLR** | Gerenciador de ferramentas de compatibilidade e camada Proton otimizada | [github.com/Vysp3r/ProtonPlus](https://github.com/Vysp3r/ProtonPlus) · [github.com/CachyOS/proton-cachyos](https://github.com/CachyOS/proton-cachyos) | GPL-3.0 / BSD / Várias |
| **btop++** & **Fastfetch** | Monitor de recursos do sistema e painel de informações de hardware/sistema | [github.com/aristocratos/btop](https://github.com/aristocratos/btop) · [github.com/fastfetch-cli/fastfetch](https://github.com/fastfetch-cli/fastfetch) | Apache-2.0 / MIT |
| **Fontes Outfit & Plus Jakarta Sans** | Tipografia da interface do Greeter, Lock Screen e Noctalia Shell (`configs/fonts/`) | [github.com/Outfitio/Outfit-Fonts](https://github.com/Outfitio/Outfit-Fonts) · [github.com/tokotype/PlusJakartaSans](https://github.com/tokotype/PlusJakartaSans) | SIL Open Font License 1.1 (OFL-1.1, redistribuição permitida) |
| **Bibata Cursor & Papirus Icons** | Tema de cursor e ícones instalados via pacotes oficiais durante o provisionamento | [github.com/ful1e5/Bibata_Cursor](https://github.com/ful1e5/Bibata_Cursor) · [github.com/PapirusDevelopmentTeam/papirus-icon-theme](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme) | GPL-3.0 |

---

## 3. Auditoria de Redistribuição dos Arquivos Presentes no Repositório

Todos os arquivos armazenados diretamente na árvore Git deste repositório foram verificados quanto à ausência de dados privados e à permissão legal de redistribuição:

1. **Chaves criptográficas e segredos:** nenhuma chave privada de Secure Boot (`/var/lib/sbctl/keys/`), certificado pessoal, senha, hash de usuário ou token está incluído no repositório. Cada instalação gera suas próprias chaves localmente via `sbctl create-keys`.
2. **Fontes em `configs/fonts/`:** `outfit-latin.ttf` e `plus-jakarta-sans-latin.ttf` são distribuídas sob a **SIL Open Font License 1.1 (OFL-1.1)**, que permite livre redistribuição e empacotamento junto a softwares.
3. **Wallpapers e emblemas em `configs/wallpapers/` e `configs/icons/`:** gerados por scripts próprios do projeto (`tools/generate_nox_visuals.py`), sem uso de imagens proprietárias de terceiros.
4. **Pacotes binários e ISO do Arch Linux:** não são armazenados no repositório; são baixados sob demanda durante a instalação diretamente dos espelhos oficiais do Arch Linux, CachyOS e AUR.
