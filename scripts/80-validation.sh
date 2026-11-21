#!/usr/bin/env bash
# Stage 80: Comprehensive offline/target validation before allowing success status.
set -Eeuo pipefail
source "${NOX_ROOT}/scripts/lib/common.sh"

nox_assert_target_context
if $NOX_DRY_RUN; then
  nox_info "[DRY-RUN] 80-validation: validaria todos os requisitos no alvo."
  exit 0
fi

BOOT_MP="/boot"
if ! findmnt /boot >/dev/null 2>&1 && findmnt /efi >/dev/null 2>&1; then
  BOOT_MP="/efi"
fi

FAILS=0
check() {
  local name="$1"
  shift
  if "$@"; then
    nox_info "[PASS] $name"
  else
    nox_error "[FAIL] $name"
    ((FAILS++)) || true
  fi
}

# 1. CachyOS repos priority order & single kernel + Limine + Secure Boot prep
check "repos cachyos configurados na ordem oficial antes de Arch" bash -c "
  repos=\"\$(pacman-conf --repo-list | tr '\n' ' ')\"
  grep -Eq '^cachyos-(znver4|v4) cachyos-core-(znver4|v4) cachyos-extra-(znver4|v4) cachyos core extra multilib' <<<\"\$repos\"
"
check "linux-cachyos e headers instalados" bash -c "pacman -Q linux-cachyos linux-cachyos-headers >/dev/null"
check "nenhum kernel concorrente instalado" bash -c "! pacman -Q linux linux-zen linux-lts linux-hardened >/dev/null 2>&1"
check "arquivos de boot limine e cachyos presentes" bash -c "test -s '${BOOT_MP}/EFI/limine/limine_x64.efi' && test -s '${BOOT_MP}/EFI/BOOT/BOOTX64.EFI' && test -s '${BOOT_MP}/limine.conf'"
check "limine-mkinitcpio-hook, limine-snapper-sync e sbctl instalados" bash -c "pacman -Q limine limine-mkinitcpio-hook limine-snapper-sync sbctl >/dev/null"
check "limine.conf contem Arch Linux -> Project Nox (kernel-id=linux-cachyos), tema e boot automatico 5s" bash -c "
  test -s '${BOOT_MP}/nox-limine-wallpaper.png' &&
  grep -q 'kernel-id=linux-cachyos' '${BOOT_MP}/limine.conf' &&
  grep -Eq '^[[:space:]]*//Project Nox\$' '${BOOT_MP}/limine.conf' &&
  ! grep -Eq '^[[:space:]]*/+\+Snapshots\b' '${BOOT_MP}/limine.conf' &&
  (! grep -qE '/@\.snapshots/[0-9]+' '${BOOT_MP}/limine.conf' || grep -Eq '^[[:space:]]*//Snapshots$' '${BOOT_MP}/limine.conf') &&
  grep -q '^wallpaper: boot():/nox-limine-wallpaper.png#' '${BOOT_MP}/limine.conf' &&
  grep -qx 'interface_branding: Project Nox' '${BOOT_MP}/limine.conf' &&
  grep -qx 'default_entry: Arch Linux/Project Nox' '${BOOT_MP}/limine.conf' &&
  grep -qx 'timeout: 5' '${BOOT_MP}/limine.conf' &&
  grep -qx 'remember_last_entry: no' '${BOOT_MP}/limine.conf' &&
  ! grep -q 'linux-zen' '${BOOT_MP}/limine.conf' &&
  test ! -d '${BOOT_MP}/EFI/arch-limine'
"
check "hook btrfs-overlayfs presente em /etc/mkinitcpio.conf" bash -c "grep -Eq '^HOOKS=.*(btrfs-overlayfs|sd-btrfs-overlayfs)' /etc/mkinitcpio.conf"
check "/.snapshots montado como subvolume Btrfs" bash -c "mountpoint -q /.snapshots && btrfs subvolume show /.snapshots >/dev/null"
check "cadeia criptografica Limine + sbctl validada (nox-secureboot-verify)" /usr/local/bin/nox-secureboot-verify
check "estado limpo e integro do Limine (nox-limine-integrity --verify)" /usr/local/libexec/nox/nox-limine-integrity --verify

# 1b. System language (en_CA.UTF-8 + en_US fallback), timezone (America/Sao_Paulo), keyboard + cedilla, performance configs
check "idioma padrao en_CA.UTF-8 com fallback en_US configurado e gerado" bash -c "grep -qx 'LANG=en_CA.UTF-8' /etc/locale.conf && grep -qx 'LANGUAGE=en_CA:en_US:en' /etc/locale.conf && locale -a | grep -qiE '^en_CA\.utf-?8\$' && locale -a | grep -qiE '^en_US\.utf-?8\$'"
check "fuso horario America/Sao_Paulo configurado" bash -c "readlink -f /etc/localtime | grep -q 'America/Sao_Paulo\$'"
check "teclado us/intl e cedilha (.XCompose) configurados" bash -c "grep -qx 'KEYMAP=us-acentos' /etc/vconsole.conf && grep -q 'ccedilla' /etc/skel/.XCompose"
check "sysctl de performance e gamemode.ini presentes" bash -c "test -s /etc/sysctl.d/99-nox-performance.conf && test -s /etc/gamemode.ini && test -s /etc/modprobe.d/iwlwifi-ax210.conf"
check "regras Fuxi H3 hotplug e BlueZ/WirePlumber presentes" bash -c "test -s /etc/udev/rules.d/85-nox-fuxi-h3.rules && test -s /etc/xdg/wireplumber/wireplumber.conf.d/52-fuxi-h3-profile.conf && test -s /etc/systemd/user/nox-fuxi-h3.path"
check "mesa e vulkan-radeon 64/32 bits instalados" bash -c "pacman -Q mesa lib32-mesa vulkan-radeon lib32-vulkan-radeon >/dev/null"

# 2. Pacman & Paru from CachyOS
check "pacman instalado do CachyOS" bash -c "pacman -Qi pacman | grep -qE '(Installed From[[:space:]]*:[[:space:]]*cachyos|Packager[[:space:]]*:[[:space:]]*CachyOS)'"
check "paru estavel instalado do CachyOS" bash -c "pacman -Qi paru | grep -qE 'Installed From[[:space:]]*:[[:space:]]*cachyos' && ! pacman -Q paru-git >/dev/null 2>&1"

# 3. Forbidden packages absent (including GRUB, grub-btrfs, HushMic, redundant monitors/fetchers)
for p in grub grub-btrfs os-prober hyprland sddm nemo plasma-desktop gnome-shell chromium steam discord yay paru-git hushmic-bin htop glances neofetch macchina; do
  check "pacote proibido ausente: $p" bash -c "! pacman -Q '$p' >/dev/null 2>&1"
done

# 4. Desktop, Greeter, Kitty, Bash, Luciole, Firefox Pure, Btop, Fastfetch, Minimalist Launcher & Obsidian Purple
check "umbriel, noctalia, noctalia-greeter, greetd, mpvpaper, socat, kitty instalados" bash -c "pacman -Q umbriel noctalia noctalia-greeter greetd mpvpaper socat kitty >/dev/null"
# shellcheck disable=SC2016
check "binarios graficos e mpvpaper sem bibliotecas ausentes (ldd)" bash -c '
  for b in /usr/bin/mpvpaper /usr/bin/mpv /usr/bin/ffmpeg /usr/bin/ffmpegthumbnailer /usr/bin/noctalia /usr/bin/noctalia-greeter /usr/bin/umbriel /usr/bin/kitty /usr/bin/firefox /usr/lib/glycin-loaders/2+/glycin-jxl /usr/lib/glycin-loaders/2+/glycin-svg /usr/lib/glycin-loaders/2+/glycin-image-rs; do
    test -x "$b" && ! ldd "$b" 2>/dev/null | grep -q "not found"
  done && mpvpaper --help >/dev/null 2>&1 && mpv --version >/dev/null 2>&1
'
check "vulkan-tools, mesa-utils e pilha grafica presentes (libva-utils ausente)" bash -c "pacman -Q vulkan-tools mesa-utils mesa lib32-mesa vulkan-radeon lib32-vulkan-radeon libva lib32-libva linux-firmware >/dev/null && ! pacman -Q libva-utils >/dev/null 2>&1"
check "luciole-git instalado e .desktop presente" bash -c "pacman -Q luciole-git >/dev/null && test -f /usr/share/applications/dev.noctalia.luciole.desktop"
check "firefox-pure (CachyOS) instalado como navegador padrao XDG e dark/Obsidian CSS" bash -c "pacman -Qi firefox-pure | grep -qE 'Installed From[[:space:]]*:[[:space:]]*(cachyos-znver4|cachyos)' && test -f /usr/share/applications/firefox.desktop && grep -q 'x-scheme-handler/https=firefox.desktop' /etc/skel/.config/mimeapps.list && test -s /usr/lib/firefox/browser/defaults/preferences/nox-theme.js && grep -q 'toolkit.legacyUserProfileCustomizations.stylesheets' /usr/lib/firefox/browser/defaults/preferences/nox-theme.js && test -s /usr/share/nox-archinstall/firefox/userChrome.css"
check "btop, rocm-smi-lib e fastfetch instalados com dashboard Obsidian Purple" bash -c "pacman -Q btop rocm-smi-lib fastfetch >/dev/null && test -s /etc/skel/.config/btop/btop.conf && grep -q 'color_theme = \"noctalia\"' /etc/skel/.config/btop/btop.conf && test -s /etc/skel/.config/btop/themes/noctalia.theme && test -s /etc/skel/.config/fastfetch/config.jsonc && test -s /etc/skel/.config/fastfetch/nox-logo.txt && grep -q 'nox-logo.txt' /etc/skel/.config/fastfetch/config.jsonc"
check "identidade visual Obsidian Purple aplicada em Noctalia, Lockscreen, Fontes, Plugins, GTK, Qt, Kitty, Umbriel e Greeter" bash -c "test -s /usr/share/nox-archinstall/wallpapers/obsidian-purple.png && test -s /usr/share/nox-archinstall/wallpapers/nox-g5-runtime.webm && test -s /usr/share/nox-archinstall/wallpapers/nox-aoc-runtime.webm && test -s /usr/share/nox-archinstall/wallpapers/nox-lockscreen.png && test -s /usr/share/nox-archinstall/wallpapers/nox-greeter.png && test -s /usr/share/nox-archinstall/icons/nox-emblem.png && test -s /usr/share/nox-archinstall/icons/nox-lockscreen-emblem.gif && test -s /usr/share/fonts/nox/outfit-latin.ttf && test -s /usr/share/fonts/nox/plus-jakarta-sans-latin.ttf && test -s /usr/share/nox-archinstall/greeter-assets/noctalia.svg && test -s /usr/share/nox-archinstall/noctalia-plugins/mpvpaper/plugin.toml && test -s /etc/skel/.config/noctalia/palettes/ObsidianPurple.json && test -s /etc/skel/.config/noctalia/nox-theme.toml && grep -q 'setup_wizard_enabled = false' /etc/skel/.config/noctalia/nox-theme.toml && test -s /etc/skel/.config/noctalia/nox-lockscreen-widgets.toml && test -s /etc/skel/.config/noctalia/nox-power.toml && noctalia config validate /etc/skel/.config/noctalia >/dev/null && test -s /etc/skel/.config/gtk-3.0/noctalia.css && test -s /etc/skel/.config/gtk-4.0/noctalia.css && test -s /etc/skel/.config/qt5ct/colors/noctalia.conf && test -s /etc/skel/.config/qt6ct/colors/noctalia.conf && test -s /etc/skel/.config/kitty/themes/noctalia.conf && grep -qx 'include themes/noctalia.conf' /etc/skel/.config/kitty/kitty.conf && test -s /etc/skel/.config/umbriel/noctalia.toml && grep -q 'nox-greeter.png' /var/lib/noctalia-greeter/greeter.toml"
check "monitores e sessao sem desligamento/suspensao automaticos por inatividade" bash -c "grep -q '^IdleAction=ignore' /etc/systemd/logind.conf.d/99-nox-no-idle.conf && grep -q '^IdleActionSec=0' /etc/systemd/logind.conf.d/99-nox-no-idle.conf && ! pacman -Q swayidle >/dev/null 2>&1 && ! pacman -Q hypridle >/dev/null 2>&1"
check "teclado us(intl), dead keys e cedilha .XCompose configurados" bash -c "grep -q 'layout = \"us\"' /etc/skel/.config/umbriel/config.toml && grep -q 'variant = \"intl\"' /etc/skel/.config/umbriel/config.toml && grep -q '<dead_acute> <c> : \"ç\"' /etc/skel/.XCompose"
check "launcher minimalista Noctalia e ferramenta de busca tecnica configurados" bash -c "test -s /etc/skel/.config/noctalia/nox-launcher.toml && grep -q 'global = false' /etc/skel/.config/noctalia/nox-launcher.toml && test -x /usr/local/libexec/nox/nox-system-tools-list && test -x /usr/local/libexec/nox/nox-system-tools-launch && test -s /etc/skel/.local/share/applications/dev.noctalia.Noctalia.desktop && grep -qx 'NoDisplay=true' /etc/skel/.local/share/applications/limine-snapper-restore.desktop && grep -qx 'NoDisplay=true' /etc/skel/.local/share/applications/btop.desktop && grep -qx 'NoDisplay=true' /etc/skel/.local/share/applications/qt6ct.desktop"
check "topgrade, protonplus e proton-cachyos-slr instalados e configurados" bash -c "pacman -Q topgrade-bin protonplus proton-cachyos-slr >/dev/null && test -x /usr/local/bin/topgrade && test -s /etc/skel/.config/topgrade.d/50-nox-arch.toml && test -s /etc/skel/.config/topgrade.d/98-disable-self-update.toml && test -s /etc/skel/.config/topgrade.d/99-disable-containers.toml && grep -q 'no_self_update = true' /etc/skel/.config/topgrade.d/98-disable-self-update.toml && grep -q 'containers' /etc/skel/.config/topgrade.d/99-disable-containers.toml && test -f /usr/share/applications/com.vysp3r.ProtonPlus.desktop && test ! -e /etc/skel/.local/share/applications/com.vysp3r.ProtonPlus.desktop"
check "discord-game-presence instalado e servico de usuario habilitado apenas por usuario" bash -c "pacman -Q discord-game-presence >/dev/null && test -x /usr/bin/discord-game-presence && /usr/bin/discord-game-presence --version >/dev/null && test -f /usr/lib/systemd/user/discord-game-presence.service && grep -qx 'WantedBy=default.target' /usr/lib/systemd/user/discord-game-presence.service && test \"\$(readlink -f /etc/skel/.config/systemd/user/default.target.wants/discord-game-presence.service)\" = '/usr/lib/systemd/user/discord-game-presence.service' && test ! -e /etc/systemd/user/default.target.wants/discord-game-presence.service"
check "greetd habilitado e apontando para nox-greeter-session" bash -c "systemctl is-enabled greetd.service >/dev/null && grep -q nox-greeter-session /etc/greetd/config.toml"
check "umbriel config validate OK" bash -c "umbriel config validate -c /etc/skel/.config/umbriel/config.toml"
check "umbriel layout padrao dwindle" bash -c "grep -Eq '^[[:space:]]*mode[[:space:]]*=[[:space:]]*\"dwindle\"' /etc/skel/.config/umbriel/config.toml && ! grep -Eq '^[[:space:]]*mode[[:space:]]*=[[:space:]]*\"(scrolling|master|stacking)\"' /etc/skel/.config/umbriel/config.toml"
check "visudo validado sem NOPASSWD" bash -c "visudo -cf /etc/sudoers >/dev/null && visudo -cf /etc/sudoers.d/10-wheel >/dev/null && ! grep -rqE '^[^#]*NOPASSWD' /etc/sudoers /etc/sudoers.d/"

# 5. Services enabled (and NetworkManager-wait-online disabled)
for s in NetworkManager.service scx_loader.service ananicy-cpp.service irqbalance.service bluetooth.service systemd-resolved.service systemd-oomd.service limine-snapper-sync.service; do
  check "servico habilitado: $s" systemctl is-enabled "$s" >/dev/null
done
check "NetworkManager-wait-online.service desabilitado" bash -c "! systemctl is-enabled NetworkManager-wait-online.service >/dev/null 2>&1"
check "snapper-timeline.timer desabilitado" bash -c "! systemctl is-enabled snapper-timeline.timer >/dev/null 2>&1"

# 6. Human user login shell = bash & wheel membership
while IFS=: read -r uname _uid _gid _home ushell; do
  [[ -n "$uname" ]] || continue
  check "shell bash para $uname" bash -c "test '$ushell' = '/bin/bash' -o '$ushell' = '/usr/bin/bash'"
  check "grupo wheel para $uname" bash -c "id -nG '$uname' | grep -qw wheel"
  check "permissoes .local, ProtonPlus visivel e overlays launcher para $uname" bash -c "test \"\$(stat -c '%U' '${_home}/.local')\" = '$uname' && test \"\$(stat -c '%U' '${_home}/.local/share')\" = '$uname' && grep -qx 'NoDisplay=true' '${_home}/.local/share/applications/limine-snapper-restore.desktop' && test ! -e '${_home}/.local/share/applications/com.vysp3r.ProtonPlus.desktop'"
  check "discord-game-presence habilitado e com dono correto para $uname" bash -c "test \"\$(readlink -f '${_home}/.config/systemd/user/default.target.wants/discord-game-presence.service')\" = '/usr/lib/systemd/user/discord-game-presence.service' && test \"\$(stat -c '%U' '${_home}/.config/systemd/user/default.target.wants/discord-game-presence.service')\" = '$uname' && test \"\$(stat -c '%U' '${_home}/.config/systemd')\" = '$uname'"
done < <(nox_list_human_users)

if ((FAILS > 0)); then
  nox_die "Validacao offline falhou com ${FAILS} erro(s)."
fi
nox_info "Todas as checagens offline de 80-validation passaram!"
