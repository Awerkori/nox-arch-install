<p align="center">
  <img src="configs/icons/nox-emblem.png" alt="Nox Archinstall" width="132" />
</p>

<h1 align="center">Nox-Arch-Install</h1>

<p align="center">
  <em>Instalação pessoal automatizada de Arch Linux · Kernel CachyOS znver4, Limine, Btrfs Snapper, Secure Boot e Umbriel / Noctalia</em>
</p>

<p align="center">
  <a href="https://github.com/Awerkori/nox-arch-install/actions/workflows/ci.yml"><img src="https://github.com/Awerkori/nox-arch-install/actions/workflows/ci.yml/badge.svg?branch=main" alt="Nox Archinstall CI" /></a>
  <a href="https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.2"><img src="https://img.shields.io/badge/release-v1.0.2%20est%C3%A1vel-7c3aed?style=flat-square" alt="Release estável v1.0.2" /></a>
  <img src="https://img.shields.io/badge/arch-x86--64--v4%20%C2%B7%20linux--cachyos-5b21b6?style=flat-square" alt="Arquitetura x86-64-v4 e linux-cachyos" />
  <img src="https://img.shields.io/badge/boot-Limine%20%C2%B7%20BLAKE2B%20%C2%B7%20sbctl-a855f7?style=flat-square" alt="Limine BLAKE2B e sbctl" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/licen%C3%A7a-AGPL--3.0-1f1635?style=flat-square" alt="Licença AGPL-3.0" /></a>
</p>

<p align="center">
  <img src="docs/screenshots/03-desktop-showcase.png" alt="Nox Archinstall — Desktop Umbriel + Noctalia Shell + Kitty/Fastfetch (Obsidian Purple)" width="100%" />
</p>

**Nox Archinstall** (internamente *Project Nox*) é o instalador pessoal e reproduzível do meu próprio desktop Arch Linux — não uma distribuição genérica — projetado especificamente para plataforma **AMD Zen 4/5 (`x86-64-v4`)**, placa-mãe **MSI PRO B650M-P**, **Ryzen 5 7500F**, **Radeon RX 9060 XT** e **Intel AX210**.

Ele parte da **ISO oficial do Arch Linux** (`archinstall 4.5`) para garantir base limpa e auditável, automatizando em seguida todo o pós-instalação: repositório CachyOS `znver4`, kernel único **`linux-cachyos`**, compositor Wayland **`Umbriel`** com **`Noctalia Shell`** (`Obsidian Purple`), layout Btrfs resiliente com **snapshots PRE/POST automáticos** (`Snapper` + `snap-pac` + `limine-snapper-sync`) e **restauração assistida** (`Limine` / `limine-snapper-restore`), além de cadeia UEFI **`sbctl`** com verificação **BLAKE2B** do `limine.conf`.

---

## Galeria do Sistema

| Bootloader Limine (`Project Nox`) | Login Gráfico (`Noctalia Greeter`) |
| :---: | :---: |
| ![Boot Limine](docs/screenshots/01-limine-boot.png) | ![Noctalia Greeter](docs/screenshots/02-noctalia-greeter.png) |
| **Launcher Minimalista (`Obsidian Purple`)** | **Bloqueio de Sessão (`Noctalia Lock Screen`)** |
| ![Noctalia Launcher](docs/screenshots/04-noctalia-launcher.png) | ![Noctalia Lock Screen](docs/screenshots/05-noctalia-lockscreen.png) |

---

## Recursos Instalados

| Camada | Especificação Técnica |
|---|---|
| **Sistema Base** | Arch Linux oficial (`en_CA.UTF-8`, `America/Sao_Paulo`, `sudo` via `wheel`, `root` bloqueado) |
| **Kernel** | `linux-cachyos` único otimizado para `x86-64-v4` (`znver4`), sem kernels concorrentes após instalação |
| **Armazenamento** | GPT UEFI (`/boot` 4 GiB FAT32 + Btrfs `zstd:3`: `@`, `@home`, `@log`, `@pkg`, `@.snapshots`, `@swap` + `zram0`) |
| **Boot** | **Limine** com verificação **BLAKE2B** de kernel/initramfs/`limine.conf` (`nox-limine-integrity`) |
| **Segurança** | Chaves locais individuais via **`sbctl`**, `UMASK 022` isolado no alvo e verificações fail-closed |
| **Snapshots** | **Snapshots PRE/POST automáticos** (`Snapper` `root` máx. 2 + `snap-pac` + `limine-snapper-sync`) e **restauração assistida** (`Limine` / `limine-snapper-restore`) |
| **Desktop** | **Umbriel** (`dwindle`), **Noctalia Shell / Greeter / Lock Screen**, **Obsidian Purple** e `mpvpaper` |
| **Aplicativos** | **Kitty**, **Bash**, **Luciole**, **Firefox Pure** (`CachyOS`), **btop**, **fastfetch**, `nox-topgrade`, **ProtonPlus** e **`discord-game-presence`** (instalado automaticamente; serviço `--user` inicia na sessão do usuário) |

---

## Como Instalar (`v1.0.2` Estável Publicada)

> **Estado das versões:** a release estável atual, publicada e protegida por imutabilidade no GitHub é a **[`v1.0.2`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.2)** (`Latest`, cadeia verificada em [`manifests/release.json`](manifests/release.json) — inclui integração obrigatória do **`discord-game-presence`** iniciando automaticamente na sessão do usuário). As versões anteriores **[`v1.0.1`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.1)** e **[`v1.0.0`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.0)** permanecem preservadas integralmente no histórico de releases.

> **AVISO DESTRUTIVO:** O disco selecionado durante a instalação será **formatado integralmente** e **todos os dados existentes serão apagados permanentemente**. Faça backup antes de continuar.

Na **ISO oficial do Arch Linux** (`archlinux-2026.11.01-x86_64.iso`, modo UEFI 64 bits, Secure Boot temporariamente desativado na BIOS e conexão de rede ativa), execute este **único comando público oficial da release publicada `v1.0.2`**:

```bash
sh -c 'set -eu; d=$(umask 077; mktemp -d); trap "rm -rf \"$d\"" EXIT INT TERM; \
curl --proto "=https" --proto-redir "=https" --tlsv1.2 -fsSL https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.2/nox-install.py -o "$d/nox-install.py"; \
printf "%s  %s/nox-install.py\n" "6d0bf5a220badb5c67d057d7ae81947ff90fca6011c4de4b7a2f442bf8042ddf" "$d" | sha256sum -c -; \
curl --proto "=https" --proto-redir "=https" --tlsv1.2 -fsSL https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.2/user_configuration.json -o "$d/nox-cfg.json"; \
printf "%s  %s/nox-cfg.json\n" "c7c27cbb719d2dce415c68b2c1926fcafd4656045cfe966ebb3331fb2ffe8775" "$d" | sha256sum -c -; \
umask 022; python3 "$d/nox-install.py" --config "$d/nox-cfg.json"'
```

O assistente exibe **4 etapas numeradas** (`[1/4]` seleção do disco → `[2/4]` confirmação exata do dispositivo → `[3/4]` usuário → `[4/4]` senha e confirmação) seguidas pela **confirmação destrutiva final (`[s/N]`)** antes de alterar qualquer partição. Ao concluir, execute `reboot`, remova a mídia USB e consulte [`docs/INSTALLATION.md`](docs/INSTALLATION.md) para detalhes completos (Wi-Fi `iwctl`, primeiro boot e inspeção passo a passo).

---

## Documentação

| Guia | Assunto |
|---|---|
| [`docs/INSTALLATION.md`](docs/INSTALLATION.md) | Guia passo a passo na ISO, Wi-Fi `iwctl` e hashes congelados da `v1.0.2` (e histórico `v1.0.1`/`v1.0.0`) |
| [`docs/KEYBINDS_MIGRATION.md`](docs/KEYBINDS_MIGRATION.md) | Atalhos completos do compositor **Umbriel** e launcher **Noctalia** |
| [`docs/SECURE-BOOT-MSI.md`](docs/SECURE-BOOT-MSI.md) | Guia físico para **MSI PRO B650M-P** (`FQ0001`, `--microsoft`, `JBAT1`, Fases A–F) |
| [`docs/SECURE-BOOT.md`](docs/SECURE-BOOT.md) | Arquitetura geral de **Secure Boot**, `sbctl` e fluxo de 5 estágios |
| [`docs/RECOVERY.md`](docs/RECOVERY.md) | Manual de recuperação em 10 cenários (snapshots, `limine.conf`, `arch-chroot`) |
| [`docs/POST_INSTALL_CHECKS.md`](docs/POST_INSTALL_CHECKS.md) | Checklist físico pós-instalação (`RX 9060 XT`, monitores, `AX210`, `Fuxi H3`) |
| [`docs/INSTALLED-COMPONENTS.md`](docs/INSTALLED-COMPONENTS.md) | Inventário de pacotes ([`INSTALLED-PACKAGES.tsv`](docs/INSTALLED-PACKAGES.tsv)) e unidades `systemd` |
| [`docs/TOPGRADE-PROTON-INTEGRATION.md`](docs/TOPGRADE-PROTON-INTEGRATION.md) | Atualizações unificadas (`nox-topgrade` + `paru` + `ProtonPlus` + Proton-CachyOS) |
| [`docs/FINAL-AUDIT-REPORT.md`](docs/FINAL-AUDIT-REPORT.md) | Relatório técnico de auditoria, testes de contrato e homologação em VMs limpas |
| [`docs/CREDITS-AND-LICENSES.md`](docs/CREDITS-AND-LICENSES.md) | Autoria própria (`AGPL-3.0`) e créditos dos projetos upstream |
| [`docs/RELEASE-NOTES-v1.0.2.md`](docs/RELEASE-NOTES-v1.0.2.md) | Notas da release publicada `v1.0.2` (`discord-game-presence` + keyring PGP isolado AUR) |

---

## Limitações Conhecidas

- **Hardware-alvo específico:** exige CPU **`x86-64-v4`** (AMD Zen 4 / Zen 5) e **UEFI 64 bits**; perfis calibrados para **MSI PRO B650M-P (`MS-7E27`)**, **Ryzen 5 7500F**, **Radeon RX 9060 XT**, **Intel AX210** e monitores Samsung Odyssey G5 (`DP-1`) + AOC 24B35 (`HDMI-A-1`).
- **ISO homologada:** validado exclusivamente sobre a ISO oficial **`archlinux-2026.11.01-x86_64.iso`** com **`archinstall 4.5`**.
- **Validação física pendente:** toda a validação ponta a ponta (incluindo Secure Boot ativo e rollback durável PRE com preservação de `@home`) foi comprovada em VMs QEMU/KVM OVMF; testes presenciais em hardware real (`RX 9060 XT`, monitores DP/HDMI, Wi-Fi/Bluetooth `AX210`, headset `Fuxi H3`, teclado `AULA F75` e política `FQ0001` na BIOS MSI PRO B650M-P) permanecem pendentes em [`docs/POST_INSTALL_CHECKS.md`](docs/POST_INSTALL_CHECKS.md).
- **Modelo de confiança:** sem chave PGP offline pré-instalada na ISO do Arch Linux, a integridade baseia-se em HTTPS/TLSv1.2+ sem downgrade e verificação SHA-256 explícita antes da execução.

---

## Créditos e Licença

Scripts, hooks, assistente e identidade visual originais deste repositório são licenciados sob **[GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE)**. Créditos integrais dos componentes upstream pertencem aos projetos **Arch Linux**, **CachyOS**, **Limine**, **Umbriel**, **Noctalia Shell**, **sbctl**, **Snapper**, **snap-pac**, **limine-snapper-sync**, **Topgrade**, **ProtonPlus** e **discord-game-presence** ([`docs/CREDITS-AND-LICENSES.md`](docs/CREDITS-AND-LICENSES.md)).
