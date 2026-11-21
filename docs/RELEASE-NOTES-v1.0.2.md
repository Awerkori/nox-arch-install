# Release Notes — Nox Archinstall `v1.0.2` (Em Revisão)

> **Estado:** Preparada para revisão em PR; **`v1.0.1`** permanece como release estável `Latest` publicada até aprovação e publicação oficial da **`v1.0.2`** pelo proprietário.  
> **Repositório oficial atualizado:** [`Awerkori/nox-arch-install`](https://github.com/Awerkori/nox-arch-install). As releases imutáveis anteriores [`v1.0.0`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.0) e [`v1.0.1`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.1) permanecem integralmente preservadas.

## 1. Novidades da Revisão `v1.0.2`

1. **Integração obrigatória do `discord-game-presence` (`0.2-1`, AUR):**
   - Instalado automaticamente no estágio [`scripts/50-desktop.sh`](../scripts/50-desktop.sh) em sandbox não privilegiado (`noxbuild`), sem instalar os clientes `discord` ou `steam` (que continuam proibidos na imagem base) e sem adicionar entradas visuais no launcher do Noctalia.
   - Serviço de usuário `discord-game-presence.service` (`WantedBy=default.target`) habilitado estritamente por usuário humano e em `/etc/skel` via [`nox_enable_user_systemd_unit`](../scripts/lib/common.sh) (`~/.config/systemd/user/default.target.wants/discord-game-presence.service`), sem uso de `systemctl --global`, sem `enable-linger` e sem afetar `root` ou `greeter`.
   - Validação adicionada em [`scripts/80-validation.sh`](../scripts/80-validation.sh) cobrindo presença do pacote, executável `/usr/bin/discord-game-presence --version`, unidade systemd, links por usuário e ausência de habilitação global.

2. **Suporte seguro AUR a `checkdepends` e `validpgpkeys` ([`scripts/lib/aur.sh`](../scripts/lib/aur.sh)):**
   - Extração automática de `checkdepends` (como `python-pytest`) sem root antes da compilação, mantendo a suíte `check()` ativa (`makepkg` sem `--nocheck`).
   - Leitura de `validpgpkeys` sem root e importação fail-closed para keyring isolado (`$NOX_AUR_HOME/.gnupg`, modo `0700`, sem tocar `/etc/pacman.d/gnupg` e sem `--skippgpcheck`/`--skipchecksums`), encerrando processos `gpg-agent`/`dirmngr` com `gpgconf --kill all` na limpeza.

3. **Atualização dos links ativos para `Awerkori/nox-arch-install`:**
   - Scripts de build/bootstrap/iniciador, documentação ativa e suíte de testes unitários atualizados para refletir a renomeação oficial do repositório no GitHub (`https://github.com/Awerkori/nox-arch-install`).

## 2. Cadeia Congelada Verificada (`manifests/release.json`)

| Artefato | Commit Imutável | SHA-256 |
|---|---|---|
| [`i`](../i) | `761725f7279fc11b086f76ab806bef204aec5eba` | `a517cb46a9a1079a1370234dd1be6c9b37a87782be055364932ed58571e7ba05` |
| [`bootstrap/nox-install.py`](../bootstrap/nox-install.py) | `f9f6c46ba7461d5b6166d34706a5bd868ad628c6` | `6d0bf5a220badb5c67d057d7ae81947ff90fca6011c4de4b7a2f442bf8042ddf` |
| [`user_configuration.json`](../user_configuration.json) | `e50bab32d642dee85ede329100ba451d2f82f491` | `c7c27cbb719d2dce415c68b2c1926fcafd4656045cfe966ebb3331fb2ffe8775` |
| `nox-archinstall-payload-v1.0.2.tar.gz` | `e50bab32d642dee85ede329100ba451d2f82f491` | `723c46bb9d6ae2965988e99d25b3198340feb24bdf7a71b5f4b0c1179fe5a774` |
| `nox-archinstall-payload-v1.0.2.tar.gz.sha256` | `—` | `249dd2367c6b7bec1f7145b798a8577f8988f0c2c02ef8603c61f27d71969d1f` |

## 3. Validação Ponta a Ponta (`dev1-v102`)

- **Instalação limpa na ISO `archlinux-2026.11.01-x86_64.iso`:** `EXIT_CODE=0`, zero ocorrências de `lookup self` no `pacman.log`, `80-validation` 100% `PASS`, chave PGP `7E12BC1FF3B6EDB2CD8053EB981A2B2A3BBF5514` importada em `$NOX_AUR_HOME/.gnupg` sem `--skippgpcheck`/`--nocheck`.
- **Login gráfico (`Umbriel` + `Noctalia Greeter`) e reboot consecutivo (`boot1` + `boot2`):**
  - `systemctl --user is-enabled discord-game-presence.service` = `enabled` (symlink exclusivo em `~/.config/systemd/user/default.target.wants/` e `/etc/skel/`, ausente de `/etc/systemd/user/default.target.wants/`).
  - `systemctl --user is-active discord-game-presence.service` = `active` (`Loaded 25388 games`, zero falhas em `system` e `user`).
  - `discord-game-presence --version` = `discord-game-presence 0.2`, `steam`/`discord` ausentes, zero entradas `.desktop` extras.
  - Evidências sanitizadas registradas em [`docs/evidence/v1.0.2/`](evidence/v1.0.2/MANIFEST.sha256).
