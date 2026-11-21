#!/usr/bin/env bash
# Stage 50: Umbriel, Noctalia Shell, Noctalia Greeter, Kitty, Bash, Mesa/RADV, Noto fonts, Luciole.
set -Eeuo pipefail
source "${NOX_ROOT}/scripts/lib/common.sh"
source "${NOX_ROOT}/scripts/lib/aur.sh"

nox_assert_target_context
if $NOX_DRY_RUN; then
  nox_info "[DRY-RUN] 50-desktop: instalaria Umbriel, Noctalia, Greeter, Kitty, Mesa, fontes e Luciole."
  exit 0
fi

nox_wait_pacman_lock

# Ensure forbidden environments are never requested
PKGS=(
  # Graphics & Mesa/RADV/Vulkan/VA-API (64 + 32-bit) & XWayland (+ Vulkan/GL diagnostics)
  mesa
  lib32-mesa
  vulkan-radeon
  lib32-vulkan-radeon
  vulkan-icd-loader
  lib32-vulkan-icd-loader
  vulkan-mesa-layers
  lib32-vulkan-mesa-layers
  vulkan-tools
  mesa-utils
  libva
  lib32-libva
  xorg-xwayland
  # Umbriel + Portals + Polkit + DBus
  umbriel
  xdg-desktop-portal
  xdg-desktop-portal-umbriel
  xdg-desktop-portal-gtk
  polkit
  polkit-gnome
  # Noctalia Shell + Greeter + Terminal + Fonts + File helpers + Video wallpaper
  noctalia
  noctalia-greeter
  greetd
  mpvpaper
  socat
  kitty
  bash
  bash-completion
  xdg-utils
  xdg-user-dirs
  gvfs
  ffmpegthumbnailer
  poppler
  7zip
  # Dark mode & theming tools
  adw-gtk-theme
  gnome-themes-extra
  nwg-look
  qt5ct
  qt6ct
  # Fonts (Latin, CJK, Emoji + monospace for Kitty)
  noto-fonts
  noto-fonts-cjk
  noto-fonts-emoji
  ttf-jetbrains-mono-nerd
  # Clipboard, Wayland, browser & standard CLI tools
  wl-clipboard
  jq
  firefox-pure
  btop
  rocm-smi-lib
  fastfetch
  protonplus
  proton-cachyos-slr
)

nox_info "Instalando stack desktop oficial (Umbriel + Noctalia + Greeter + Kitty + Firefox Pure + Btop + Fastfetch + ProtonPlus + Proton-CachyOS SLR + Mesa)..."
pacman -S --needed --noconfirm "${PKGS[@]}"

# Guard against CachyOS vs Arch rebuild skew without performing partial/selective package promotions.
NOX_AUDITED_DESKTOP_BINS=(
  /usr/bin/mpvpaper
  /usr/bin/mpv
  /usr/bin/ffmpeg
  /usr/bin/ffmpegthumbnailer
  /usr/bin/noctalia
  /usr/bin/noctalia-greeter
  /usr/bin/umbriel
  /usr/bin/kitty
  /usr/bin/firefox
  /usr/lib/glycin-loaders/2+/glycin-jxl
  /usr/lib/glycin-loaders/2+/glycin-svg
  /usr/lib/glycin-loaders/2+/glycin-image-rs
)

nox_core_bins_missing_libs() {
  local b
  for b in "${NOX_AUDITED_DESKTOP_BINS[@]}"; do
    [[ -x "$b" ]] || continue
    if ldd "$b" 2>/dev/null | grep -q "not found"; then
      return 0
    fi
  done
  return 1
}

nox_log_missing_lib_diagnostics() {
  local b missing_lines owner_pkg
  for b in "${NOX_AUDITED_DESKTOP_BINS[@]}"; do
    [[ -x "$b" ]] || continue
    missing_lines="$(ldd "$b" 2>/dev/null | grep "not found" || true)"
    [[ -n "$missing_lines" ]] || continue
    owner_pkg="$(pacman -Qoq "$b" 2>/dev/null || echo "desconhecido")"
    nox_error "Binario com SONAME ausente: $b (pacote: $owner_pkg)"
    while IFS= read -r line; do
      [[ -n "$line" ]] && nox_error "  ldd: $line"
    done <<<"$missing_lines"
    if [[ "$owner_pkg" != "desconhecido" ]]; then
      pacman -Qi "$owner_pkg" 2>/dev/null | grep -E '^(Name|Version|Repository|Installed From|Depends On)' | while IFS= read -r qi; do
        nox_error "  pacman -Qi: $qi"
      done || true
      pacman -Si "$owner_pkg" 2>/dev/null | grep -E '^(Repository|Name|Version|Depends On)' | while IFS= read -r si; do
        nox_error "  pacman -Si: $si"
      done || true
    fi
  done
}

if nox_core_bins_missing_libs; then
  nox_warn "Detectada dessincronizacao de SONAME/ABI apos instalacao do desktop; registrando diagnostico e executando apenas atualizacao completa coerente (pacman -Syyu)..."
  nox_log_missing_lib_diagnostics
  pacman -Syyu --noconfirm
  if nox_core_bins_missing_libs; then
    nox_log_missing_lib_diagnostics
    nox_die "Incompatibilidade de SONAME/ABI persiste apos pacman -Syyu completo. Abortando sem aplicar promocao seletiva/parcial de pacotes."
  fi
fi

# Functional execution verification of critical multimedia/wallpaper components
mpvpaper --help >/dev/null 2>&1 || nox_die "Falha funcional ao carregar mpvpaper."
mpv --version >/dev/null 2>&1 || nox_die "Falha funcional ao carregar mpv."
ffmpeg -version >/dev/null 2>&1 || nox_die "Falha funcional ao carregar ffmpeg."

# Build & install Luciole, Topgrade, and Discord Game Presence from AUR as unprivileged user (noxbuild)
nox_aur_install_pkg "luciole-git"
nox_aur_install_pkg "topgrade-bin"
nox_aur_install_pkg "discord-game-presence"
nox_aur_cleanup_user

# Verify discord-game-presence & enable user systemd service per human user (never --global or root/greeter)
pacman -Qq discord-game-presence >/dev/null 2>&1 || nox_die "discord-game-presence nao foi instalado!"
[[ -x /usr/bin/discord-game-presence ]] || nox_die "Binario /usr/bin/discord-game-presence ausente!"
nox_enable_user_systemd_unit /usr/lib/systemd/user/discord-game-presence.service

# Verify bash is login shell for all human accounts and valid in /etc/shells
grep -qxF '/bin/bash' /etc/shells || printf '/bin/bash\n' >>/etc/shells
grep -qxF '/usr/bin/bash' /etc/shells || printf '/usr/bin/bash\n' >>/etc/shells
while IFS=: read -r uname _uid _gid _home ushell; do
  [[ -n "$uname" ]] || continue
  if [[ "$ushell" != "/bin/bash" && "$ushell" != "/usr/bin/bash" ]]; then
    nox_info "Ajustando shell de login de '$uname' para /usr/bin/bash..."
    chsh -s /usr/bin/bash "$uname"
  fi
done < <(nox_list_human_users)

# Verify firefox-pure is installed as sole browser and no forbidden desktops/tools crept in
pacman -Qq firefox-pure >/dev/null 2>&1 || nox_die "firefox-pure nao foi instalado!"
for forbidden in hyprland sddm nemo plasma-desktop gnome-shell chromium steam discord htop glances neofetch macchina hushmic-bin; do
  if pacman -Qq "$forbidden" >/dev/null 2>&1; then
    nox_die "Pacote proibido detectado no alvo: $forbidden"
  fi
done

nox_info "Stack desktop base instalado e auditado com sucesso."
