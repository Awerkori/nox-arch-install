#!/usr/bin/env bash
# Shared logging, state tracking, context guards, and atomic file helpers.

NOX_VERSION="1.0.2"
NOX_STATE_DIR="${NOX_STATE_DIR:-/var/lib/nox-archinstall}"
NOX_LOG_DIR="${NOX_LOG_DIR:-/var/log/nox-archinstall}"
NOX_CFG_DIR="${NOX_CFG_DIR:-/etc/nox-archinstall}"
export NOX_LIBEXEC_DIR="/usr/local/libexec/nox"
NOX_DRY_RUN="${NOX_DRY_RUN:-false}"
NOX_PROFILE="${NOX_PROFILE:-zen4}"

nox_ts() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

nox_log() {
  local level="$1"
  shift
  local msg="$*"
  local line
  line="[$(nox_ts)] [$level] $msg"
  printf '%s\n' "$line" >&2
  if [[ -d "$NOX_LOG_DIR" && -w "$NOX_LOG_DIR" ]]; then
    printf '%s\n' "$line" >>"${NOX_LOG_DIR}/install.log" 2>/dev/null || true
  fi
}

nox_info() { nox_log "INFO" "$*"; }
nox_warn() { nox_log "WARN" "$*"; }
nox_error() { nox_log "ERROR" "$*"; }

nox_die() {
  nox_error "$*"
  exit 1
}

nox_init_dirs() {
  mkdir -p "$NOX_STATE_DIR/stages" "$NOX_LOG_DIR" "$NOX_CFG_DIR"
  chmod 755 "$NOX_STATE_DIR" "$NOX_STATE_DIR/stages" "$NOX_LOG_DIR" "$NOX_CFG_DIR"
}

nox_is_chroot() {
  if [[ -r /proc/1/root/. && -r /. ]]; then
    local root_dev init_dev
    root_dev="$(stat -Lc '%d:%i' / 2>/dev/null || true)"
    init_dev="$(stat -Lc '%d:%i' /proc/1/root 2>/dev/null || true)"
    if [[ -n "$root_dev" && -n "$init_dev" && "$root_dev" != "$init_dev" ]]; then
      return 0
    fi
  fi
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    if systemd-detect-virt -r >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

nox_assert_target_context() {
  if $NOX_DRY_RUN; then
    nox_info "DRY-RUN ativo: ignorando alteracoes no sistema."
    return 0
  fi
  if [[ "$EUID" -ne 0 ]]; then
    nox_die "Este estagio precisa executar como root dentro do sistema alvo."
  fi
  # Guard against accidental execution on the user's live desktop host.
  if [[ "${NOX_ALLOW_TARGET_EXEC:-}" != "1" ]]; then
    if ! nox_is_chroot && [[ ! -f "${NOX_STATE_DIR}/target-armed" ]]; then
      nox_die "BLOQUEIO DE SEGURANCA: contexto nao reconhecido como chroot/alvo autorizado (defina NOX_ALLOW_TARGET_EXEC=1 apenas dentro de VM/alvo)."
    fi
  fi
}

nox_stage_done() {
  local stage="$1"
  [[ -f "${NOX_STATE_DIR}/stages/${stage}.done" ]]
}

nox_mark_stage_done() {
  local stage="$1"
  local checksum="${2:-}"
  printf '{"stage":"%s","status":"ok","timestamp":"%s","version":"%s","checksum":"%s"}\n' \
    "$stage" "$(nox_ts)" "$NOX_VERSION" "$checksum" >"${NOX_STATE_DIR}/stages/${stage}.done"
}

nox_write_status() {
  local status="$1"
  local failed_stage="${2:-}"
  local detail="${3:-}"
  mkdir -p "$NOX_STATE_DIR"
  python3 - "$NOX_STATE_DIR/status.json" "$status" "$failed_stage" "$detail" "$NOX_VERSION" "$(nox_ts)" <<'PY'
import json, sys, os
out, status, stage, detail, ver, ts = sys.argv[1:]
data = {
    "status": status,
    "failed_stage": stage or None,
    "detail": detail or None,
    "version": ver,
    "timestamp": ts,
}
tmp = out + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
os.replace(tmp, out)
PY
}

nox_atomic_install() {
  local mode="$1"
  local src="$2"
  local dest="$3"
  local dir
  dir="$(dirname "$dest")"
  mkdir -p "$dir"
  local tmp="${dest}.nox.tmp.$$"
  install -m "$mode" "$src" "$tmp"
  mv -f "$tmp" "$dest"
}

nox_wait_pacman_lock() {
  local lock="/var/lib/pacman/db.lck"
  local tries=0
  while [[ -e "$lock" ]]; do
    if pgrep -x pacman >/dev/null 2>&1 || pgrep -x paru >/dev/null 2>&1; then
      if ((tries >= 30)); then
        nox_die "Transacao pacman/paru ainda ativa apos espera; /var/lib/pacman/db.lck ocupado. Nao removendo lock."
      fi
      nox_warn "Aguardando termino de transacao pacman ativa..."
      sleep 2
      ((tries++))
    else
      nox_die "Encontrado /var/lib/pacman/db.lck sem processo ativo. Investigue manualmente antes de remover o lock."
    fi
  done
}

nox_list_human_users() {
  # Lists non-system local accounts with valid interactive shells (UID >= 1000, < 65000)
  awk -F: '$3 >= 1000 && $3 < 65000 && $7 !~ /(nologin|false|sync)$/ { print $1 ":" $3 ":" $4 ":" $6 ":" $7 }' /etc/passwd
}

nox_check_isa_v4() {
  if [[ -x /lib/ld-linux-x86-64.so.2 ]]; then
    if /lib/ld-linux-x86-64.so.2 --help 2>/dev/null | grep -q 'x86-64-v4 (supported, searched)'; then
      return 0
    fi
  fi
  return 1
}

nox_check_zen4_or_5() {
  # Detects AMD Zen 4 (family 25, model >= 0x60) or Zen 5 (family 26) from /proc/cpuinfo
  awk '
    /^vendor_id/ { v=$3 }
    /^cpu family/ { f=$4 }
    /^model[[:space:]]*:/ { m=$3 }
    END {
      if (v == "AuthenticAMD" && (f == 26 || (f == 25 && m >= 96))) exit 0;
      exit 1;
    }
  ' /proc/cpuinfo
}

nox_sync_hidden_tech_desktops() {
  # Hide technical/maintenance tools from Noctalia initial view via XDG user overlays
  # without editing pacman-owned /usr/share/applications/*.desktop; searchable via nox-launcher.toml.
  local -a hidden_tech_desktops=(
    dev.noctalia.Noctalia.desktop
    nwg-look.desktop
    qt5ct.desktop
    qt6ct.desktop
    qv4l2.desktop
    qvidcap.desktop
    lstopo.desktop
    mpv.desktop
    limine-snapper-restore.desktop
    org.pulseaudio.pavucontrol.desktop
    btop.desktop
  )
  install -d -m 0755 /etc/skel/.local /etc/skel/.local/share /etc/skel/.local/share/applications
  local dfile src dname ov base uname uid gid uhome _shell
  for dfile in "${hidden_tech_desktops[@]}"; do
    src="/usr/share/applications/${dfile}"
    [[ -f "$src" ]] || continue
    dname="$(grep -m1 '^Name=' "$src" | cut -d= -f2- || true)"
    [[ -n "$dname" ]] || dname="${dfile%.desktop}"
    cat >"/etc/skel/.local/share/applications/${dfile}" <<EOF
[Desktop Entry]
Type=Application
Name=${dname}
NoDisplay=true
EOF
    chmod 0644 "/etc/skel/.local/share/applications/${dfile}"
  done

  while IFS=: read -r uname uid gid uhome _shell; do
    [[ -n "$uname" && -d "$uhome" ]] || continue
    install -d -m 0755 -o "$uid" -g "$gid" \
      "${uhome}/.local" "${uhome}/.local/share" "${uhome}/.local/share/applications"
    for ov in /etc/skel/.local/share/applications/*.desktop; do
      [[ -f "$ov" ]] || continue
      base="$(basename "$ov")"
      nox_atomic_install 0644 "$ov" "${uhome}/.local/share/applications/${base}"
      chown "${uid}:${gid}" "${uhome}/.local/share/applications/${base}"
    done
  done < <(nox_list_human_users)
}

nox_enable_user_systemd_unit() {
  local unit_src="$1"
  local skel_dir="${2:-/etc/skel}"
  local unit_name
  unit_name="$(basename "$unit_src")"
  [[ -f "$unit_src" ]] || nox_die "Unidade systemd ausente: $unit_src"

  local wanted_raw target
  wanted_raw="$(grep -E '^WantedBy=' "$unit_src" | cut -d= -f2- | tr ' ' '\n' | sed '/^[[:space:]]*$/d' || true)"
  [[ -n "$wanted_raw" ]] || nox_die "Unidade $unit_src nao declara WantedBy valido."

  local current_uid
  current_uid="$(id -u)"

  while IFS= read -r target; do
    [[ "$target" =~ ^[A-Za-z0-9@._-]+\.target$ ]] || nox_die "Alvo WantedBy invalido em $unit_src: '$target'"
    install -d -m 0755 \
      "${skel_dir}/.config" \
      "${skel_dir}/.config/systemd" \
      "${skel_dir}/.config/systemd/user" \
      "${skel_dir}/.config/systemd/user/${target}.wants"
    ln -sfn "$unit_src" "${skel_dir}/.config/systemd/user/${target}.wants/${unit_name}"

    local uname uid gid uhome _shell
    while IFS=: read -r uname uid gid uhome _shell; do
      [[ -n "$uname" && -d "$uhome" ]] || continue
      if [[ "$current_uid" == "0" ]]; then
        install -d -m 0755 -o "$uid" -g "$gid" \
          "${uhome}/.config" \
          "${uhome}/.config/systemd" \
          "${uhome}/.config/systemd/user" \
          "${uhome}/.config/systemd/user/${target}.wants"
        ln -sfn "$unit_src" "${uhome}/.config/systemd/user/${target}.wants/${unit_name}"
        chown -h "${uid}:${gid}" "${uhome}/.config/systemd/user/${target}.wants/${unit_name}"
      else
        install -d -m 0755 \
          "${uhome}/.config" \
          "${uhome}/.config/systemd" \
          "${uhome}/.config/systemd/user" \
          "${uhome}/.config/systemd/user/${target}.wants"
        ln -sfn "$unit_src" "${uhome}/.config/systemd/user/${target}.wants/${unit_name}"
      fi
    done < <(nox_list_human_users)
  done <<<"$wanted_raw"
}
