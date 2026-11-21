#!/usr/bin/env sh
# Iniciador curto oficial do Nox Archinstall (v1.0.2)
# Baixa o bootstrap oficial de referencia imutavel via HTTPS, valida o SHA-256 e executa com TTY interativo.
set -eu
umask 077

BOOTSTRAP_COMMIT="f9f6c46ba7461d5b6166d34706a5bd868ad628c6"
DEFAULT_BOOTSTRAP_URL="https://raw.githubusercontent.com/Awerkori/nox-arch-install/${BOOTSTRAP_COMMIT}/bootstrap/nox-install.py"
DEFAULT_BOOTSTRAP_SHA256="6d0bf5a220badb5c67d057d7ae81947ff90fca6011c4de4b7a2f442bf8042ddf"

BOOTSTRAP_URL="$DEFAULT_BOOTSTRAP_URL"
BOOTSTRAP_SHA256="$DEFAULT_BOOTSTRAP_SHA256"

if [ "${NOX_ALLOW_CUSTOM_BOOTSTRAP:-0}" = "1" ]; then
  BOOTSTRAP_URL="${NOX_BOOTSTRAP_URL:-$DEFAULT_BOOTSTRAP_URL}"
  BOOTSTRAP_SHA256="${NOX_BOOTSTRAP_SHA256:-$DEFAULT_BOOTSTRAP_SHA256}"
elif [ -n "${NOX_BOOTSTRAP_URL:-}" ] || [ -n "${NOX_BOOTSTRAP_SHA256:-}" ]; then
  echo "ERRO: override de bootstrap requer NOX_ALLOW_CUSTOM_BOOTSTRAP=1." >&2
  exit 2
fi

case "$BOOTSTRAP_URL" in
  https://*) ;;
  *)
    echo "ERRO: URL do bootstrap deve usar HTTPS estrito: $BOOTSTRAP_URL" >&2
    exit 2
    ;;
esac

case "$BOOTSTRAP_SHA256" in
  [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]) ;;
  *)
    echo "ERRO: formato SHA-256 do bootstrap invalido." >&2
    exit 2
    ;;
esac

TMP_DIR="$(mktemp -d /tmp/nox-boot.XXXXXX)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM HUP

chmod 700 "$TMP_DIR"
BOOTSTRAP_FILE="$TMP_DIR/nox-install.py"

curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL --retry 3 --max-time 30 "$BOOTSTRAP_URL" -o "$BOOTSTRAP_FILE"
if [ ! -s "$BOOTSTRAP_FILE" ]; then
  echo "ERRO: arquivo de bootstrap baixado esta vazio." >&2
  exit 1
fi

printf '%s  %s\n' "$BOOTSTRAP_SHA256" "$BOOTSTRAP_FILE" | sha256sum -c - >/dev/null 2>&1 || {
  echo "ERRO: falha na verificacao SHA-256 do bootstrap nox-install.py." >&2
  exit 1
}

# Restaura umask padrao antes do instalador para que /mnt/etc e arquivos do sistema alvo nao herdem 077.
umask 022

if (: </dev/tty) 2>/dev/null; then
  python3 "$BOOTSTRAP_FILE" "$@" </dev/tty
else
  python3 "$BOOTSTRAP_FILE" "$@"
fi
