# Relatório Final de Auditoria de Engenharia, Hardening de Segurança e Homologação — Nox Archinstall (`v1.0.1` + Preparação `v1.0.2`)

> **Histórico e versões:**
> - Pré-release [`v1.0.0-rc10`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.0-rc10): preservada integralmente em [`docs/history/FINAL-AUDIT-REPORT-v1.0.0-rc10.md`](history/FINAL-AUDIT-REPORT-v1.0.0-rc10.md).
> - Release estável publicada [`v1.0.0`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.0): documentada em [`docs/history/FINAL-AUDIT-REPORT-v1.0.0.md`](history/FINAL-AUDIT-REPORT-v1.0.0.md) (artefatos, tag e commit `73c21a171e4c672662feb35756dd7c46e54036c2` preservados sem alteração retroativa).
> - Release estável publicada vigente (`Latest` / Imutável): [`v1.0.1`](https://github.com/Awerkori/nox-arch-install/releases/tag/v1.0.1) ([PR #1](https://github.com/Awerkori/nox-arch-install/pull/1), commit `efc8e9018a2c4bf15ff3493af1f36d0b7eddc84a`, payload SHA-256 `52008f9c454c8b39c91d6e51b3546f6a76546f021c3c6a0850dc7a55d5bf92b2`).
> - Revisão em preparação (`v1.0.2` — Em Revisão): adiciona `discord-game-presence` (`0.2-1`, AUR), serviço `--user` por usuário humano e suporte AUR a `checkdepends` + `validpgpkeys` isolados, com evidências em [`docs/evidence/v1.0.2/`](evidence/v1.0.2/MANIFEST.sha256) e [`docs/RELEASE-NOTES-v1.0.2.md`](RELEASE-NOTES-v1.0.2.md).

---

## 1. Identificação da Revisão Congelada Atual (`v1.0.2` em Revisão; `v1.0.1` segue `Latest`)

- **Projeto:** Nox Archinstall / Project Nox (`https://github.com/Awerkori/nox-arch-install`)
- **Versão vigente publicada (`Latest`):** `v1.0.1` (`immutable: true`)
- **Versão preparada em `manifests/release.json`:** `v1.0.2` (aguardando aprovação para merge e publicação)
- **ISO oficial homologada:** `archlinux-2026.11.01-x86_64.iso` (`SHA-256: 01bcdcf01af2f7d58f2794899c834770d25c9bfc945bd092b32bb66672a4a216`, `archinstall 4.5`)
- **Manifesto de integridade:** [`manifests/release.json`](../manifests/release.json) (schema v2)
- **Evidências públicas sanitizadas:** [`docs/evidence/v1.0.1/`](evidence/v1.0.1/MANIFEST.sha256) e [`docs/evidence/v1.0.2/`](evidence/v1.0.2/MANIFEST.sha256)

### Cadeia Acíclica de Commits Imutáveis e Hashes SHA-256 (`v1.0.2` Congelada em `manifests/release.json`)

| Estágio | Artefato | Commit de Origem Imutável | SHA-256 |
|---|---|---|---|
| **Estágio 1 (Iniciador)** | [`i`](../i) | `761725f7279fc11b086f76ab806bef204aec5eba` | `a517cb46a9a1079a1370234dd1be6c9b37a87782be055364932ed58571e7ba05` |
| **Estágio 2 (Bootstrap)** | [`bootstrap/nox-install.py`](../bootstrap/nox-install.py) | `f9f6c46ba7461d5b6166d34706a5bd868ad628c6` | `6d0bf5a220badb5c67d057d7ae81947ff90fca6011c4de4b7a2f442bf8042ddf` |
| **Estágio 3 (Configuração)** | [`user_configuration.json`](../user_configuration.json) | `e50bab32d642dee85ede329100ba451d2f82f491` | `c7c27cbb719d2dce415c68b2c1926fcafd4656045cfe966ebb3331fb2ffe8775` |
| **Estágio 4 (Payload)** | `nox-archinstall-payload-v1.0.2.tar.gz` | `e50bab32d642dee85ede329100ba451d2f82f491` | `723c46bb9d6ae2965988e99d25b3198340feb24bdf7a71b5f4b0c1179fe5a774` |
| **Arquivo `.sha256`** | `nox-archinstall-payload-v1.0.2.tar.gz.sha256` | `—` | `249dd2367c6b7bec1f7145b798a8577f8988f0c2c02ef8603c61f27d71969d1f` |

*(Cadeia publicada e imutável da `v1.0.1` preservada: `i` `978c1f1892d19a42d3b1eb3bc0c2a9f1e9b093db` (`ebd6a651...`) → `bootstrap/nox-install.py` `46d3835b05ab43252454ce1648dd054f110857d5` (`fa6c2a3b...`) → `user_configuration.json` `83624813f3f32fd8608ee881b21b7ab6ec92cf3e` (`9cb32121...`) → `nox-archinstall-payload-v1.0.1.tar.gz` (`52008f9c...`), `.sha256` `c6d52792...`.)*

### Validação Limpa da Revisão `v1.0.2` (`dev1-v102`)
- **Instalação limpa (`ISO → vda`):** `EXIT_CODE=0`, `717` pacotes medidos (`102` explícitos, `615` dependências, `3` AUR via `pacman -Qm`: `luciole-git`, `topgrade-bin`, `discord-game-presence`), `0` ocorrências de `lookup self`.
- **Login gráfico e reboot consecutivo (`boot1` + `boot2`):** `discord-game-presence.service` `enabled` por usuário (`~/.config/systemd/user/default.target.wants/` e `/etc/skel/`, ausente de `/etc/systemd/user/default.target.wants/`), `active` (`Loaded 25388 games`), `steam` e `discord` ausentes, `0` falhas (`system` e `user`), `nox-limine-integrity --verify` e `nox-secureboot-verify` `PASS`.

---

## 2. Correções de Hardening e Confiabilidade Aplicadas em `v1.0.1`

### 2.1. Cadeia de Confiança, Reprodutibilidade e Escopo de CI
1. **Estágio 1 (`i`), Estágio 2 (`bootstrap/nox-install.py`) e `bootstrap/nox-bootstrap.sh` — Isolamento de `umask 077`:**
   - **Problema detectado durante a homologação limpa na ISO:** executar o iniciador sob `umask 077` propagava `0077` para o `archinstall`, `pacstrap` e `systemd-nspawn`, fazendo `/mnt/etc` nascer com modo `0700` e derrubando o `dbus-broker-launch` dentro do container temporário de instalação (`Permission denied`).
   - **Correção:** arquivos temporários continuam protegidos em `0700`/`0600` explicitamente (`chmod 700`/`0o600`), mas `i`, `bootstrap/nox-install.py` (imediatamente antes de chamar `archinstall`, restaurando no `finally`) e `bootstrap/nox-bootstrap.sh` (antes da extração e execução de `install.sh`) garantem `umask 022` para o sistema-alvo.
2. **Construção determinística e verificação de cadeia (`scripts/build-release.sh` e `manifests/release.json`):**
   - `build-release.sh` gera `generated_at_utc` real em UTC (`date -u`), reproduz integralmente o manifesto **schema v2**, empacota estritamente arquivos rastreados do runtime via `git ls-files` com `--format=gnu --sort=name --mtime='UTC 2026-01-01' --owner=0 --group=0 --numeric-owner --mode='a+rX,u+w,go-w'` e `GZIP=-n` (garantindo hash idêntico entre Arch Linux local e `ubuntu-latest` no GitHub Actions).
   - Adicionadas as flags `--pin-bootstrap`, `--pin-launcher` e `--verify-only` (esta última valida `payload_sha256`, schema v2, hashes de trabalho e blobs em `git cat-file -p` para toda a cadeia `i → nox-install.py → user_configuration.json → payload`).
3. **CI e detecção de segredos (`.github/workflows/ci.yml`):**
   - Removido `--exclude-dir=.github` do scan de segredos (mantendo apenas `.git`, `dist`, `reports` e `__pycache__`), configurado `fetch-depth: 0` no `actions/checkout` (`v7.0.1`) e adicionado `./scripts/build-release.sh --verify-only` como portão obrigatório.

### 2.2. Correções Fail-Closed de Disco, Snapper, Limine e Secure Boot
1. **`bootstrap/nox-install.py` (`list_candidate_disks` e `verify_disk_safe_to_wipe`):**
   - Verificação fail-closed dos códigos de saída de `lsblk -b -J`, `lsblk -nr -o MOUNTPOINT`, `findmnt -rn -o SOURCE,TARGET` e `swapon --noheadings --raw --show=NAME`.
   - Travessia recursiva da árvore de partições descendentes (`_collect_lsblk_tree`), bloqueio contra alvos `/run/archiso*`, pontos montados ou swap ativo, e reidentificação de `path`/`realpath`/nome/tamanho/modelo/serial/transporte imediatamente antes de invocar o `archinstall`.
2. **`configs/bin/nox-snapper-cleanup` (`_cleanup_lock`):**
   - Falha na abertura/criação do arquivo de lock (`os.open`) ou na aquisição de `fcntl.flock(..., LOCK_EX)` agora aborta **fail-closed** com saída não zero antes de qualquer consulta ou mutação no Snapper (garantindo fechamento do descritor e remoção de lock no `finally`). Modo `--dry-run` sem `--lock-file` permanece somente leitura.
3. **`configs/bin/nox-limine-integrity` e `configs/boot-hooks/95-nox-sbctl-fallback`:**
   - Pré-checagem de todos os binários obrigatórios antes de iniciar mutações, remoção de mascaramento de erros, pós-checagem de `/boot/limine.conf`, inscrição BLAKE2B em ambos os EFIs, assinatura UEFI e `nox-secureboot-verify --ignore-dirty-marker`, preservando `/run/nox-limine-tx.dirty` em qualquer falha (`NOX_PRESERVE_DIRTY_MARKER=1`).
   - Adicionados modos explícitos `--verify`/`--check` (verificação somente leitura) e separação fail-closed quando `/boot/limine.conf` está ausente: preserva `.dirty` e retorna erro sob transação interrompida, modos `--force`/`--repair`/`--verify`/`--check`, ou presença de artefatos Limine instalados; aceita ausência apenas em pré-inicialização limpa antes do `limine-install`.
4. **`configs/bin/nox-secureboot-verify` e `configs/bin/nox-secureboot-enroll`:**
   - Captura real do código de saída de `sbctl status --json` e validação estrita de schema/tipos booleanos em Python (`UNKNOWN` / falha imediata em saída inválida, vazia ou erro).
   - `nox-secureboot-enroll` exige `Setup Mode` válido antes de tocar a NVRAM, valida retorno de todas as etapas sem pular erros e confirma transição pós-enrollment para `User Mode` (`setup_mode == false`), diferenciando `Estágio 4 PASS` (inscrito) de `Estágio 5 PASS` (`--require-active`).
5. **Eliminação de `fatal library error, lookup self` no `pacstrap` (`user_configuration.json` + `scripts/60-snapshots.sh`):**
   - Causa raiz identificada no `/var/log/pacman.log`: `user_configuration.json` pré-instalava `"snapper"` e `"snap-pac"` já no `pacstrap` inicial do `archinstall`, acionando `zz-snap-pac-post.hook` (`ps -p <ppid>` via `libproc2`) em ambiente chroot antes da configuração do Snapper.
   - Removidos `"snapper"` e `"snap-pac"` da lista base de `pacstrap` em `user_configuration.json` (mantendo ambos instalados explicitamente via `SNAP_PAC_SKIP=y pacman -S` no estágio `60-snapshots.sh`, após montagem e configuração completas do sistema-alvo).
6. **Eliminação de colisão em hooks pós-boot e encaminhamento interativo real de TTY no restore (`configs/boot-hooks/95-nox-sbctl-fallback`, `configs/bin/nox-limine-integrity` e `configs/bin/nox-limine-snapper-restore`):**
   - Serialização exclusiva por `flock` e diretório temporário isolado (`mktemp -d`) por execução em `95-nox-sbctl-fallback` e lock dedicado (`202`) em `nox-limine-integrity`, eliminando a colisão `BOOTX64.EFI.nox.tmp` / `unrecognized PE machine` durante transações simultâneas.
   - Correção do código de retorno (`repair_rc`) em `nox-limine-snapper-restore`, supressão de reparo concorrente disparado pelo `limine-snapper-watcher` enquanto `/run/lock/limine-snapper-restore.lock` está ativo, e encaminhamento real do descritor TTY (`3<&0`) no helper PTY até o prompt final `Reboot now? [Y/n]:` (sem ser capturado pelo pipe do heredoc `<<'PY'`).
7. **Integridade de documentação, hashes `v1.0.0` e logs de evidência em `.gitignore`/CI:**
   - Corrigidos URL e hashes congelados da release estável `v1.0.0` em [`docs/INSTALLATION.md`](INSTALLATION.md), unificada a apresentação visual do [`README.md`](../README.md) com captura real do desktop e único comando ativo da release publicada `v1.0.0`, e adicionada exceção `!docs/evidence/**/*.log` em `.gitignore` com checagem `sha256sum -c MANIFEST.sha256` no CI.

---

## 3. Evidência em Testes Unitários, Contratos e Estáticos (Escopo: Local + GitHub Actions)

- **Workflow remoto (`.github/workflows/ci.yml`):**
  - Verificação estática e sintática em **todos os 31 scripts shell** (`bash -n`, `sh -n` para POSIX, `shellcheck -x -P .` e `shfmt -i 2 -ci -d`): **PASS (31/31)**.
  - Validação sintática JSON (`jq empty`) em `user_configuration.json`, `manifests/release.json`, `profiles/hardware.json` e `configs/noctalia/palettes/ObsidianPurple.json`: **PASS (4/4)**.
  - Verificação da cadeia criptográfica (`./scripts/build-release.sh --verify-only`): **`VERIFY_RELEASE_CHAIN=PASS`** (tarball determinístico idêntico localmente e no runner Ubuntu).
  - Scan de segredos incluindo `.github/`: **PASS** (validado em teste unitário com canário injetado em `.github/workflows/canary.yml`).
  - Suite unitária e de contrato (`python3 -B -m unittest discover -s tests/unit -p 'test_*.py' -v`): **PASS (`58/58` testes aprovados, `0` falhas, `0` ignorados)** — incluindo matrizes fail-closed de lock/concorrência Snapper, disco/wipe, JSON do `sbctl`, estados e modo `--verify` do `nox-limine-integrity`, teste PTY interativo completo de `nox-limine-snapper-restore` até `Reboot now? [Y/n]:`, inibição de colisão com `limine-snapper-restore.lock`, diferimento do `snap-pac` fora do `pacstrap`, propagação de `umask 022`, consistência do manifesto schema v2 e checagem documental (`README.md`, `docs/`, `MANIFEST.sha256`). *(Nota: os testes unitários cobrem lógica, contratos, documentos e wrappers com mocks de comandos de sistema onde aplicável; o fluxo real ponta a ponta foi validado separadamente nas VMs limpas abaixo.)*
  - Verificação de integridade das evidências públicas (`cd docs/evidence/v1.0.1 && sha256sum -c MANIFEST.sha256`): **PASS (`41/41` arquivos `OK`)**.

---

## 4. Homologação Real Ponta a Ponta em Duas Instalações Limpas (`ACCEPT-A-CLEAN` e `ACCEPT-B-CLEAN`)

Para eliminar qualquer resíduo de VMs reaproveitadas, foram criadas **duas novas VMs QEMU/KVM do zero** (`nox-archinstall-lab-acceptA-clean` e `nox-archinstall-lab-acceptB-clean`, 6 vCPUs `host-passthrough`, 8 GiB RAM, discos QCOW2 novos de 60 GiB, NVRAM OVMF independente sem chaves pré-inscritas), inicializadas diretamente pela ISO oficial `archlinux-2026.11.01-x86_64.iso` preservando intactas todas as VMs e evidências anteriores (`acceptA`, `acceptB`, `dev1`, `finalA`, `finalB` e `evidence/v1.0.1/`).

> **Transparência de laboratório (`--payload-url`):** Como a tag e os assets da release `v1.0.1` ainda não estão publicados no GitHub (aguardando aprovação humana deste PR), o fluxo real interativo `i` → `bootstrap/nox-install.py` → `user_configuration.json` baixou `i` e `bootstrap/nox-install.py` + `user_configuration.json` diretamente dos commits imutáveis no GitHub com validação SHA-256 completa e utilizou `--payload-url http://192.168.122.1:18443/nox-archinstall-payload-v1.0.1.tar.gz --payload-sha256 5db77939a83f50ceb30b812dfb0d669867c1a0f21ee05fb253dc3137bd0764b4 --allow-insecure-http` apenas para entregar o tarball determinístico gerado pelo próprio `build-release.sh` sobre a rede NAT local do laboratório.

### 4.1. Matriz de Critérios Validados após Boot Real em Disco Instalado

| Critério Verificado | `ACCEPT-A-CLEAN` (Setup Mode) | `ACCEPT-B-CLEAN` (Secure Boot Ativo) | Resultado |
|---|---|---|---|
| **Instalação limpa ISO → `vda`** | `EXIT_CODE=0` em `470s` | `EXIT_CODE=0` em `640s` | **PASS** |
| **Boot Limine direto do disco (`hd`)** | `Project Nox`, `7.3.5-1-cachyos`, `01-limine-boot.png` | `Project Nox`, `7.3.5-2-cachyos`, entrada `Arch-Linux.Project-Nox` | **PASS** |
| **Noctalia Greeter (`greetd`) & Login** | Login gráfico completo (`02-noctalia-greeter.png`) | Login gráfico + lockscreen (`04-lockscreen-clean.png`) | **PASS** |
| **Umbriel (`dwindle`) + Noctalia + Obsidian Purple** | `umbriel`, `noctalia`, `mpvpaper`, `03-desktop-clean.png` | `umbriel`, `noctalia`, `mpvpaper`, `Mod+L` lockscreen | **PASS** |
| **Firefox Pure & Luciole & Kitty/Fastfetch** | `/etc/firefox/policies/policies.json`, `user.js`, `/usr/bin/luciole`, `/usr/bin/kitty`, `/usr/local/bin/fastfetch` | Idênticos (`0` diferenças de pacotes/config) | **PASS** |
| **Kernel único e sistema base** | Apenas `linux-cachyos 7.3.5-1` (`kernel_count=1`) | Apenas `linux-cachyos 7.3.5-2` (`kernel_count=1`) | **PASS** |
| **Btrfs + ZRAM + Swapfile NOCOW** | `@`, `@home`, `@log`, `@pkg`, `@.snapshots`, `@swap` (`compress=zstd:3`), `zram0` `7.7G` (`prio 100`), `/nox-swap/swapfile` `2G` `+C` (`prio 10`) | Idêntico (`zram0` + `/nox-swap/swapfile` `+C`) | **PASS** |
| **Systemd health & root segurança** | `0` falhas (`system` e `user`), `passwd -S root` = `L` (locked) | `0` falhas (`system` e `user`), `passwd -S root` = `L` (locked) | **PASS** |
| **Locale, Fuso & Teclado** | `en_CA.UTF-8`, `America/Sao_Paulo` (`NTP active`), `us-acentos` + `us(intl)` + `.XCompose` | Idênticos | **PASS** |
| **Audio PipeWire + WirePlumber** | `pipewire`, `pipewire-pulse`, `wireplumber` ativos com sink/source | Idênticos | **PASS** |
| **Secure Boot (`Setup Mode` vs `User Mode` / `--require-active`)** | `Setup Mode: Enabled`: Estágios 1–3 `PASS` (`EXIT=0`); `--require-active` falha (`EXIT=1`, esperado antes do enroll) | Após `nox-secureboot-enroll --yes-enroll-uefi-keys --ignore-immutable` + reboot OVMF: `Secure Boot: enabled (user)`, Estágios 1–5 **`PASS` (`EXIT=0`)** | **PASS** |
| **Snapper PRE/POST + Hook `pacman` + Limine Sync** | Config `root` pronta (`current`) | Pares `1-2`, `3-4` e transação real `pacman -S --noconfirm ethtool` (`#5`/`#6`): hook `zzz-99-nox-snapper-cleanup.hook` podou antigos mantendo estritamente **2** snapshots (`#5`+`#6`), normalizou `/boot/limine.conf` (`///Ponto de Segurança` / `///Estado Atualizado`) e revalidou `--require-active` com **`EXIT=0`** | **PASS** |
| **Rollback durável PRE via Limine com Secure Boot ativo** | N/A | Snapshot `PRE #7` restaurado com backup `#10` (`nox-a5-backup`) após mutações descartáveis (`/etc/nox-disposable-rollback-test`, `/usr/local/share/nox-disposable-dir`) e reboot real pelo Limine: mutações ausentes (`PASS_ABSENT`), `/home` sentinel (`147365d8...`) preservado em `@home`, `nox-limine-integrity --verify` **`EXIT=0`**, `nox-secureboot-verify --require-active` **Estágio 5 `PASS` (`EXIT=0`)**, `pacman -Qk linux-cachyos` (`0` ausentes) e `systemd` `0` falhas | **PASS** |

### 4.2. Comparação de Pacotes e Unidades (`ACCEPT-A-CLEAN` vs `ACCEPT-B-CLEAN` vs Inventário)

- **`pacman -Qq` (todos os pacotes):** **`711` vs `711`** — `diff -u` = **0 diferenças** (e **0 diferenças** contra [`INSTALLED-PACKAGES.tsv`](INSTALLED-PACKAGES.tsv)).
- **`pacman -Qqe` (explícitos):** **`100` vs `100`** — `diff -u` = **0 diferenças**.
- **`pacman -Qqm` (AUR):** **`2` vs `2`** (`luciole-git`, `topgrade-bin`) — **0 diferenças**.
- **`systemctl list-unit-files --state=enabled` (sistema):** **`22` vs `22`** — **0 diferenças**.
- **`systemctl --user list-unit-files --state=enabled` (usuário):** **`7` vs `7`** — **0 diferenças**.

*(Registro histórico separado: as evidências anteriores à limpeza permanecem isoladas no laboratório local. A bateria intermediária `ACCEPT-A-CLEAN` / `ACCEPT-B-CLEAN` validou o payload `5db77939...` e os respectivos artefatos seguem preservados em `docs/evidence/v1.0.1/logs/accept*-clean-*`. Após os ajustes finais de boot/restore, o payload definitivo congelado **`52008f9c454c8b39c91d6e51b3546f6a76546f021c3c6a0850dc7a55d5bf92b2`** (`I_URL` no commit `978c1f1892d19a42d3b1eb3bc0c2a9f1e9b093db`, `I_SHA256` `ebd6a6515dad718530486bb8a14d7ce4e3f45d25bd0c7b364ba5b16996f5ce31`) foi integralmente rehomologado do zero em **duas novas instalações limpas independentes (`ACCEPT-A-V101-FINAL` e `ACCEPT-B-V101-FINAL`)**.)*

### 4.3. Homologação Definitiva sobre o Payload Congelado Final (`ACCEPT-A-V101-FINAL` e `ACCEPT-B-V101-FINAL`)

| Critério Verificado | `ACCEPT-A-V101-FINAL` (Setup Mode) | `ACCEPT-B-V101-FINAL` (Secure Boot Ativo) | Resultado |
|---|---|---|---|
| **Instalação limpa ISO → `vda`** | `EXIT_CODE=0`, zero erros `lookup self` (`pacman.log=0`, `install.log=0`, `tty.log=0`) | `EXIT_CODE=0`, zero erros `lookup self` (`pacman.log=0`, `install.log=0`, `tty.log=0`) | **PASS** |
| **Boot em disco (`hd`) + Greeter + Umbriel + Noctalia + mpvpaper** | `7.3.5-2-cachyos`, `SYS_FAILED=0`, `USR_FAILED=0`, `FIRST_BOOT_DONE` | Idêntico, `SYS_FAILED=0`, `USR_FAILED=0`, `FIRST_BOOT_DONE` | **PASS** |
| **Paridade exata A × B** | `711` pacotes / `100` explícitos / `2` AUR / `22` sys units / `7` user units | `diff -u` = **`0` diferenças** entre A e B | **PASS** |
| **Secure Boot (`Setup Mode` → `User Mode` → `--require-active`)** | Estágios 1–3 `PASS`, `nox-limine-integrity --verify` `PASS` | `nox-secureboot-enroll` (`Stage 4`) + reboot OVMF → **Estágio 5 `PASS`** | **PASS** |
| **Snapshot manual + `pacman -S/-Rns tree` + `journalctl`** | N/A | Snapshot `1` (`nox-manual-keep`) preservado após install+remove de `tree`; `0` erros de `95-nox-sbctl-fallback`, `repair_rc` ou colisão no `journalctl` | **PASS** |
| **Rollback durável PRE via `/usr/local/bin/limine-snapper-restore` + 2 reboots** | N/A | `PRE #6` restaurado via PTY interativo até `Reboot now? [Y/n]: n` (`RESTORE_PTY_EXIT=0`, `JOURNAL_FALLBACK_ERRORS_POST_RESTORE=0`); após Reboot 1: mutações descartáveis ausentes, `/home` sentinel (`ab53c5a359bd...`) íntegro, `Stage 5 PASS`; após Reboot 2 consecutivo: `linux-cachyos: 7843 total files, 0 missing files`, GUI ativa, `nox-limine-integrity --verify` `EXIT=0`, **Estágio 5 `PASS`**, `SYS_FAILED=0`, `USR_FAILED=0` | **PASS** |

---

## 5. Evidências Públicas Sanitizadas (`docs/evidence/v1.0.1/`)

Todas as evidências abaixo foram verificadas quanto à ausência de senhas, tokens, chaves privadas, seriais de hardware, endereços MAC e SSIDs Wi-Fi, acompanhadas de [`evidence/v1.0.1/MANIFEST.sha256`](evidence/v1.0.1/MANIFEST.sha256) (`41/41 OK`):

- **Capturas reais das VMs limpas (`docs/evidence/v1.0.1/screenshots/`):**
  1. [`01-limine-boot.png`](evidence/v1.0.1/screenshots/01-limine-boot.png) — Boot pelo Limine (`Project Nox`, kernel `linux-cachyos`, timeout `5s`).
  2. [`02-noctalia-greeter.png`](evidence/v1.0.1/screenshots/02-noctalia-greeter.png) — Noctalia Greeter (`greetd`, sessão `Umbriel`, tema Obsidian Purple).
  3. [`03-desktop-clean.png`](evidence/v1.0.1/screenshots/03-desktop-clean.png) — Desktop limpo inicial com Umbriel, Noctalia Shell e wallpaper animado `mpvpaper`.
  4. [`04-lockscreen-clean.png`](evidence/v1.0.1/screenshots/04-lockscreen-clean.png) — Noctalia Lock Screen na instalação limpa (`Mod+L`).
- **Logs e paridade da rodada intermediária (`docs/evidence/v1.0.1/logs/`):**
  - Resultados de instalação limpa (`acceptA-clean-install-result.txt`, `acceptB-clean-install-result.txt`), pós-boot (`acceptA-clean-verify.log`, `acceptB-clean-verify.log`), listas `pkg-*`/`units-*`, Secure Boot + Snapper + rollback (`acceptB-clean-secureboot-enroll.log`, `acceptB-clean-secureboot-active-and-snapper.log`, `acceptB-clean-snap-pac-and-cleanup.log`, `acceptB-clean-durable-rollback.log`).
- **Logs e paridade da rodada definitiva sobre o payload congelado `52008f9c...` (`docs/evidence/v1.0.1/logs/`):**
  - Resultados de instalação limpa e auditoria zero `lookup self` (`acceptA-v101-final-install-result.txt`, `acceptB-v101-final-install-result.txt`, `accept-v101-final-lookup-self-summary.txt`).
  - Pós-boot e paridade completa A × B (`acceptA-v101-final-verify.log`, `acceptB-v101-final-verify.log`, `accept*-v101-final-pkg-*`, `accept*-v101-final-units-*`).
  - Enrollment UEFI, Stage 5 ativo + `pacman -S/-Rns tree` + rollback durável PRE via PTY interativo e dois reboots consecutivos (`acceptB-v101-final-secureboot-enroll.log`, `acceptB-v101-final-stage5-and-restore.log`, `acceptB-v101-final-reboot1.log`, `acceptB-v101-final-reboot2.log`).

---

## 6. Limitações Conhecidas e Itens Pendentes de Validação Física (`PENDENTE-HARDWARE`)

### 6.1. Limitações Arquiteturais Documentadas
1. **Pinagem de hashes SHA-256 sem chave pública offline pré-instalada na ISO:** A ISO oficial do Arch Linux não inclui chaves públicas do proprietário do Project Nox. A cadeia de confiança utiliza commits imutáveis no GitHub sobre HTTPS/TLSv1.2+ e verificação SHA-256 explícita em cada estágio a partir do comando inicial copiado da documentação.
2. **Releases imutáveis no GitHub (`immutable_releases`):** Proteção da branch `main`, ruleset de tags `refs/tags/v*` (`active`) e **Immutable Releases** (`enabled: true`) habilitados na publicação da `v1.0.1`.

### 6.2. Checklist de Validação Física (`PENDENTE-HARDWARE`)
Os itens abaixo dependem exclusivamente do hardware físico de destino (`PENDENTE-HARDWARE`, procedimento detalhado em [`docs/POST_INSTALL_CHECKS.md`](POST_INSTALL_CHECKS.md)):

- [ ] **GPU ASRock AMD Radeon RX 9060 XT:** aceleração Vulkan/RADV real (`vulkaninfo`, `rocm-smi-lib`, `btop` GPU meter) e vídeo GOP no POST com Secure Boot ativo.
- [ ] **Monitores Samsung Odyssey G5 (`DP-1`, `2560x1440@165Hz`) + AOC 24B35 (`HDMI-A-1`, `1920x1080@100Hz` vertical `90°`):** alinhamento `[2560, -350]` e travessia contínua do cursor.
- [ ] **Placa Wi-Fi / Bluetooth Intel AX210 (`iwlwifi` + `iwd`):** conexão Wi-Fi real, `regdomain BR` e pareamento Bluetooth A2DP.
- [ ] **Headset HAVIT Fuxi H3:** ciclo real de conexão USB/2.4GHz validando `nox-fuxi-h3-fix` (`PCM Playback Volume` = 100 e unmute de captura).
- [ ] **Microfone analógico P2:** detecção e seleção padrão no WirePlumber sem dispositivo virtual residual.
- [ ] **Teclado AULA F75:** layout `us(intl)` e cedilha (`' + c → ç`) sem chattering.
- [ ] **Secure Boot efetivamente ativo na UEFI da MSI PRO B650M-P (`MS-7E27`, BIOS `1.I2`):** execução presencial das Fases A–E de [`docs/SECURE-BOOT-MSI.md`](SECURE-BOOT-MSI.md), política `FQ0001` (`Deny Execute`) e rejeição física de mídia não assinada.
