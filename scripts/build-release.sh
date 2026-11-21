#!/usr/bin/env bash
# Deterministic release builder & schema-v2 trust-chain generator/verifier for Nox Archinstall.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"

VERSION="v1.0.2"
BASE_URL=""
VERIFY_ONLY=false
PIN_BOOTSTRAP_COMMIT=""
PIN_LAUNCHER_COMMIT=""
CONFIG_COMMIT=""
BOOTSTRAP_COMMIT=""
LAUNCHER_COMMIT=""
PAYLOAD_COMMIT=""
SKIP_GIT_MATCH=false

usage() {
  cat <<'USAGE'
Uso: build-release.sh [opcoes] [VERSION] [BASE_URL]
  --verify-only                   Valida payload deterministico, schema v2, commits e cadeia i->bootstrap->config->payload sem alterar arquivos
  --pin-bootstrap <CONFIG_COMMIT> Atualiza bootstrap/nox-install.py com commit/SHA-256 oficiais de user_configuration.json e payload
  --pin-launcher <BOOT_COMMIT>    Atualiza iniciador i com commit/SHA-256 oficiais de bootstrap/nox-install.py
  --config-commit <SHA>           Sobrescreve config_commit esperado ao gerar/validar manifesto
  --bootstrap-commit <SHA>        Sobrescreve bootstrap_commit esperado ao gerar/validar manifesto
  --launcher-commit <SHA>         Sobrescreve launcher_commit esperado ao gerar/validar manifesto
  --payload-commit <SHA>          Sobrescreve payload_commit esperado ao gerar/validar manifesto
  --skip-git-match                Permite gerar manifesto antes dos commits finais (apenas para staging local; falha em --verify-only)
USAGE
}

POS_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify-only)
      VERIFY_ONLY=true
      shift
      ;;
    --pin-bootstrap)
      PIN_BOOTSTRAP_COMMIT="${2:-}"
      shift 2
      ;;
    --pin-launcher)
      PIN_LAUNCHER_COMMIT="${2:-}"
      shift 2
      ;;
    --config-commit)
      CONFIG_COMMIT="${2:-}"
      shift 2
      ;;
    --bootstrap-commit)
      BOOTSTRAP_COMMIT="${2:-}"
      shift 2
      ;;
    --launcher-commit)
      LAUNCHER_COMMIT="${2:-}"
      shift 2
      ;;
    --payload-commit)
      PAYLOAD_COMMIT="${2:-}"
      shift 2
      ;;
    --skip-git-match)
      SKIP_GIT_MATCH=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      echo "Opcao desconhecida: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      POS_ARGS+=("$1")
      shift
      ;;
  esac
done

if ((${#POS_ARGS[@]} >= 1)); then
  VERSION="${POS_ARGS[0]}"
fi
if ((${#POS_ARGS[@]} >= 2)); then
  BASE_URL="${POS_ARGS[1]}"
fi

mkdir -p "$DIST_DIR"
TAR_NAME="nox-archinstall-payload-${VERSION}.tar.gz"
TAR_PATH="${DIST_DIR}/${TAR_NAME}"

build_deterministic_payload() {
  local out_tar="$1"
  local file_list
  file_list="$(mktemp "${DIST_DIR}/.payload-files.XXXXXX")"
  # Build strictly from git-tracked runtime payload paths with normalized mode, owner, mtime, and GNU tar format
  # so builds are bit-for-bit identical across Arch, Ubuntu CI, and any umask.
  git -C "$REPO_ROOT" ls-files -- \
    LICENSE \
    install.sh \
    bootstrap/nox-bootstrap.sh \
    configs \
    profiles \
    scripts \
    tools | LC_ALL=C sort >"$file_list"
  GZIP=-n tar --format=gnu --sort=name --mtime='UTC 2026-01-01' \
    --owner=0 --group=0 --numeric-owner \
    --mode='a+rX,u+w,go-w' \
    --transform='s|^|nox-archinstall/|' \
    -czf "$out_tar" -C "$REPO_ROOT" -T "$file_list"
  rm -f "$file_list"
  sha256sum "$out_tar" | awk '{print $1}'
}

resolve_commit_for_path() {
  local rel_path="$1"
  local file_sha
  file_sha="$(sha256sum "${REPO_ROOT}/${rel_path}" | awk '{print $1}')"
  local cand blob_sha
  while IFS= read -r cand; do
    [[ -n "$cand" ]] || continue
    blob_sha="$(git -C "$REPO_ROOT" cat-file -p "${cand}:${rel_path}" 2>/dev/null | sha256sum | awk '{print $1}' || true)"
    if [[ "$blob_sha" == "$file_sha" ]]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done < <(git -C "$REPO_ROOT" log -n 25 --format='%H' -- "$rel_path" 2>/dev/null || true)
  return 1
}

if [[ -n "$PIN_BOOTSTRAP_COMMIT" ]]; then
  PAYLOAD_SHA256="$(build_deterministic_payload "$TAR_PATH")"
  printf '%s  %s\n' "$PAYLOAD_SHA256" "$TAR_NAME" >"${TAR_PATH}.sha256"
  PAYLOAD_URL="${BASE_URL:-https://github.com/Awerkori/nox-arch-install/releases/download/${VERSION}}/${TAR_NAME}"
  git -C "$REPO_ROOT" rev-parse --verify "${PIN_BOOTSTRAP_COMMIT}^{commit}" >/dev/null 2>&1 || {
    echo "ERRO: commit de configuracao invalido: $PIN_BOOTSTRAP_COMMIT" >&2
    exit 1
  }
  CFG_BLOB_SHA="$(git -C "$REPO_ROOT" cat-file -p "${PIN_BOOTSTRAP_COMMIT}:user_configuration.json" | sha256sum | awk '{print $1}')"
  CFG_WT_SHA="$(sha256sum "${REPO_ROOT}/user_configuration.json" | awk '{print $1}')"
  [[ "$CFG_BLOB_SHA" == "$CFG_WT_SHA" ]] || {
    echo "ERRO: user_configuration.json local (${CFG_WT_SHA}) difere do commit ${PIN_BOOTSTRAP_COMMIT} (${CFG_BLOB_SHA})." >&2
    exit 1
  }
  python3 - "${REPO_ROOT}/bootstrap/nox-install.py" "$VERSION" "$PIN_BOOTSTRAP_COMMIT" "$CFG_WT_SHA" "$PAYLOAD_URL" "$PAYLOAD_SHA256" <<'PY'
import re, sys
path, ver, cfg_commit, cfg_sha, pay_url, pay_sha = sys.argv[1:]
txt = open(path, "r", encoding="utf-8").read()
txt = re.sub(r'^NOX_RELEASE_VERSION = ".*"$', f'NOX_RELEASE_VERSION = "{ver}"', txt, flags=re.M)
txt = re.sub(r'^OFFICIAL_CONFIG_COMMIT = ".*"$', f'OFFICIAL_CONFIG_COMMIT = "{cfg_commit}"', txt, flags=re.M)
txt = re.sub(r'^OFFICIAL_CONFIG_SHA256 = ".*"$', f'OFFICIAL_CONFIG_SHA256 = "{cfg_sha}"', txt, flags=re.M)
txt = re.sub(r'^OFFICIAL_PAYLOAD_URL = \(\n    ".*"\n\)$', f'OFFICIAL_PAYLOAD_URL = (\n    "{pay_url}"\n)', txt, flags=re.M)
txt = re.sub(r'^OFFICIAL_PAYLOAD_SHA256 = ".*"$', f'OFFICIAL_PAYLOAD_SHA256 = "{pay_sha}"', txt, flags=re.M)
open(path, "w", encoding="utf-8").write(txt)
PY
  echo "Pinned bootstrap/nox-install.py -> config_commit=${PIN_BOOTSTRAP_COMMIT}, payload_sha=${PAYLOAD_SHA256}"
  exit 0
fi

if [[ -n "$PIN_LAUNCHER_COMMIT" ]]; then
  git -C "$REPO_ROOT" rev-parse --verify "${PIN_LAUNCHER_COMMIT}^{commit}" >/dev/null 2>&1 || {
    echo "ERRO: commit de bootstrap invalido: $PIN_LAUNCHER_COMMIT" >&2
    exit 1
  }
  BOOT_BLOB_SHA="$(git -C "$REPO_ROOT" cat-file -p "${PIN_LAUNCHER_COMMIT}:bootstrap/nox-install.py" | sha256sum | awk '{print $1}')"
  BOOT_WT_SHA="$(sha256sum "${REPO_ROOT}/bootstrap/nox-install.py" | awk '{print $1}')"
  [[ "$BOOT_BLOB_SHA" == "$BOOT_WT_SHA" ]] || {
    echo "ERRO: bootstrap/nox-install.py local (${BOOT_WT_SHA}) difere do commit ${PIN_LAUNCHER_COMMIT} (${BOOT_BLOB_SHA})." >&2
    exit 1
  }
  python3 - "${REPO_ROOT}/i" "$PIN_LAUNCHER_COMMIT" "$BOOT_WT_SHA" "$VERSION" <<'PY'
import re, sys
path, boot_commit, boot_sha, ver = sys.argv[1:]
txt = open(path, "r", encoding="utf-8").read()
txt = re.sub(r'^# Iniciador curto oficial do Nox Archinstall \(.*\)$', f'# Iniciador curto oficial do Nox Archinstall ({ver})', txt, flags=re.M)
txt = re.sub(r'^BOOTSTRAP_COMMIT=".*"$', f'BOOTSTRAP_COMMIT="{boot_commit}"', txt, flags=re.M)
txt = re.sub(r'^DEFAULT_BOOTSTRAP_SHA256=".*"$', f'DEFAULT_BOOTSTRAP_SHA256="{boot_sha}"', txt, flags=re.M)
open(path, "w", encoding="utf-8").write(txt)
PY
  echo "Pinned launcher i -> bootstrap_commit=${PIN_LAUNCHER_COMMIT}, bootstrap_sha=${BOOT_WT_SHA}"
  exit 0
fi

if $VERIFY_ONLY; then
  TMP_TAR="$(mktemp "${DIST_DIR}/.verify-${VERSION}.XXXXXX.tar.gz")"
  trap 'rm -f "$TMP_TAR"' EXIT
  PAYLOAD_SHA256="$(build_deterministic_payload "$TMP_TAR")"
  python3 - "$REPO_ROOT" "$PAYLOAD_SHA256" "$SKIP_GIT_MATCH" <<'PY'
import hashlib, json, re, subprocess, sys
from pathlib import Path

repo = Path(sys.argv[1])
actual_payload_sha = sys.argv[2]
skip_git_match = sys.argv[3] == "true"

manifest = json.loads((repo / "manifests/release.json").read_text(encoding="utf-8"))
required_top = (
    "schema_version",
    "version",
    "payload_commit",
    "source_commit",
    "config_commit",
    "bootstrap_commit",
    "launcher_commit",
    "generated_at_utc",
    "trust_model",
    "payload_url",
    "payload_sha256",
    "config_sha256",
    "bootstrap_sha256",
    "launcher_sha256",
    "artifacts",
    "reproducibility",
)
for k in required_top:
    if k not in manifest or manifest[k] in (None, ""):
        raise SystemExit(f"ERRO manifesto schema v2: campo obrigatorio ausente '{k}'")

if manifest["schema_version"] != 2:
    raise SystemExit(f"ERRO manifesto: schema_version esperado=2, obtido={manifest['schema_version']}")

ts = str(manifest["generated_at_utc"])
if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts):
    raise SystemExit(f"ERRO manifesto: generated_at_utc invalido: {ts}")

if manifest["payload_sha256"] != actual_payload_sha:
    raise SystemExit(f"ERRO payload: tarball deterministico ({actual_payload_sha}) difere de release.json ({manifest['payload_sha256']})")

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

cfg_sha = sha256_file(repo / "user_configuration.json")
boot_sha = sha256_file(repo / "bootstrap/nox-install.py")
i_sha = sha256_file(repo / "i")

checks = [
    ("config_sha256", cfg_sha, "config"),
    ("bootstrap_sha256", boot_sha, "bootstrap"),
    ("launcher_sha256", i_sha, "launcher"),
]
for top_key, wt_sha, art_key in checks:
    if manifest[top_key] != wt_sha:
        raise SystemExit(f"ERRO hash '{top_key}': manifesto={manifest[top_key]}, arquivo={wt_sha}")
    art = manifest["artifacts"].get(art_key, {})
    if art.get("sha256") != wt_sha:
        raise SystemExit(f"ERRO artifacts.{art_key}.sha256: manifesto={art.get('sha256')}, arquivo={wt_sha}")
    for req_art_field in ("name", "path", "commit", "url", "sha256"):
        if not art.get(req_art_field):
            raise SystemExit(f"ERRO artifacts.{art_key}: campo obrigatorio ausente '{req_art_field}'")
    if not str(art["url"]).startswith("https://") or "/main/" in str(art["url"]) or "/master/" in str(art["url"]):
        raise SystemExit(f"ERRO artifacts.{art_key}.url insegura ou mutavel: {art['url']}")
    if art["commit"] not in art["url"]:
        raise SystemExit(f"ERRO artifacts.{art_key}.url nao contem commit '{art['commit']}': {art['url']}")

# Verify internal pins across i -> bootstrap/nox-install.py -> user_configuration.json -> payload
i_txt = (repo / "i").read_text(encoding="utf-8")
m_i_c = re.search(r'^BOOTSTRAP_COMMIT="([0-9a-f]{40})"$', i_txt, re.M)
m_i_s = re.search(r'^DEFAULT_BOOTSTRAP_SHA256="([0-9a-f]{64})"$', i_txt, re.M)
if not m_i_c or not m_i_s:
    raise SystemExit("ERRO iniciador 'i': BOOTSTRAP_COMMIT ou DEFAULT_BOOTSTRAP_SHA256 ausente")
if m_i_c.group(1) != manifest["bootstrap_commit"] or m_i_s.group(1) != boot_sha:
    raise SystemExit(f"ERRO cadeia i->bootstrap: 'i' aponta para {m_i_c.group(1)}/{m_i_s.group(1)}, esperado {manifest['bootstrap_commit']}/{boot_sha}")

boot_txt = (repo / "bootstrap/nox-install.py").read_text(encoding="utf-8")
m_b_c = re.search(r'^OFFICIAL_CONFIG_COMMIT = "([0-9a-f]{40})"$', boot_txt, re.M)
m_b_s = re.search(r'^OFFICIAL_CONFIG_SHA256 = "([0-9a-f]{64})"$', boot_txt, re.M)
m_b_ps = re.search(r'^OFFICIAL_PAYLOAD_SHA256 = "([0-9a-f]{64})"$', boot_txt, re.M)
if not m_b_c or not m_b_s or not m_b_ps:
    raise SystemExit("ERRO bootstrap: constantes oficiais ausentes em nox-install.py")
if m_b_c.group(1) != manifest["config_commit"] or m_b_s.group(1) != cfg_sha or m_b_ps.group(1) != actual_payload_sha:
    raise SystemExit("ERRO cadeia bootstrap->config/payload: pinagem divergente em bootstrap/nox-install.py")
if manifest["payload_url"] not in boot_txt:
    raise SystemExit(f"ERRO cadeia bootstrap->payload_url: URL '{manifest['payload_url']}' ausente em nox-install.py")

cfg_txt = (repo / "user_configuration.json").read_text(encoding="utf-8")
if manifest["payload_url"] not in cfg_txt or actual_payload_sha not in cfg_txt:
    raise SystemExit("ERRO cadeia config->payload: user_configuration.json nao referencia URL/SHA-256 exatos do manifesto")

if not skip_git_match:
    for art_key, commit_key, rel_path, expected_sha in (
        ("launcher", "launcher_commit", "i", i_sha),
        ("bootstrap", "bootstrap_commit", "bootstrap/nox-install.py", boot_sha),
        ("config", "config_commit", "user_configuration.json", cfg_sha),
    ):
        csha = manifest[commit_key]
        res = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-p", f"{csha}:{rel_path}"],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            raise SystemExit(f"ERRO git: nao foi possivel ler {csha}:{rel_path}")
        blob_sha = hashlib.sha256(res.stdout).hexdigest()
        if blob_sha != expected_sha:
            raise SystemExit(
                f"ERRO git blob mismatch para '{rel_path}' no commit {csha}: blob={blob_sha}, working_tree={expected_sha}"
            )

print("VERIFY_RELEASE_CHAIN=PASS")
PY
  exit 0
fi

# Standard build + schema-v2 manifest generation
SHA256="$(build_deterministic_payload "$TAR_PATH")"
printf '%s  %s\n' "$SHA256" "$TAR_NAME" >"${TAR_PATH}.sha256"

if [[ -z "$BASE_URL" ]]; then
  BASE_URL="https://github.com/Awerkori/nox-arch-install/releases/download/${VERSION}"
fi
PAYLOAD_URL="${BASE_URL}/${TAR_NAME}"

# Update user_configuration.json payload pointer
python3 - "${REPO_ROOT}/user_configuration.json" "$PAYLOAD_URL" "$SHA256" <<'PY'
import json, sys
cfg_path, url, sha = sys.argv[1:]
with open(cfg_path, "r", encoding="utf-8") as f:
    data = json.load(f)
cmd = (
    "bash -c 'set -Eeuo pipefail; "
    f"URL=\"{url}\"; SHA=\"{sha}\"; "
    "TMP=$(mktemp -d); trap \"rm -rf $TMP\" EXIT; "
    "curl --proto \"=https\" --proto-redir \"=https\" --tlsv1.2 -fsSL --retry 3 --max-time 60 \"$URL\" -o \"$TMP/p.tar.gz\"; "
    "printf \"%s  %s\\n\" \"$SHA\" \"$TMP/p.tar.gz\" | sha256sum -c -; "
    "rm -rf /var/lib/nox-archinstall/payload; mkdir -p /var/lib/nox-archinstall/payload; "
    "tar --no-same-owner --no-same-permissions -xzf \"$TMP/p.tar.gz\" --strip-components=1 -C /var/lib/nox-archinstall/payload; "
    "chmod +x /var/lib/nox-archinstall/payload/install.sh; "
    "exec /var/lib/nox-archinstall/payload/install.sh --stage target-offline'"
)
data["custom_commands"] = [cmd]
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

if ! $SKIP_GIT_MATCH; then
  [[ -n "$CONFIG_COMMIT" ]] || CONFIG_COMMIT="$(resolve_commit_for_path user_configuration.json)" || {
    echo "ERRO: user_configuration.json nao coincide com nenhum commit recente. Faca commit antes ou use --skip-git-match para staging." >&2
    exit 1
  }
  [[ -n "$BOOTSTRAP_COMMIT" ]] || BOOTSTRAP_COMMIT="$(resolve_commit_for_path bootstrap/nox-install.py)" || {
    echo "ERRO: bootstrap/nox-install.py nao coincide com nenhum commit recente. Use --pin-bootstrap e faca commit antes." >&2
    exit 1
  }
  [[ -n "$LAUNCHER_COMMIT" ]] || LAUNCHER_COMMIT="$(resolve_commit_for_path i)" || {
    echo "ERRO: 'i' nao coincide com nenhum commit recente. Use --pin-launcher e faca commit antes." >&2
    exit 1
  }
fi

HEAD_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ -n "$CONFIG_COMMIT" ]] || CONFIG_COMMIT="$HEAD_SHA"
[[ -n "$BOOTSTRAP_COMMIT" ]] || BOOTSTRAP_COMMIT="$HEAD_SHA"
[[ -n "$LAUNCHER_COMMIT" ]] || LAUNCHER_COMMIT="$HEAD_SHA"
[[ -n "$PAYLOAD_COMMIT" ]] || PAYLOAD_COMMIT="$CONFIG_COMMIT"

CONFIG_SHA256="$(sha256sum "${REPO_ROOT}/user_configuration.json" | awk '{print $1}')"
BOOTSTRAP_SHA256="$(sha256sum "${REPO_ROOT}/bootstrap/nox-install.py" | awk '{print $1}')"
LAUNCHER_SHA256="$(sha256sum "${REPO_ROOT}/i" | awk '{print $1}')"
PAYLOAD_SHA_FILE_SHA256="$(sha256sum "${TAR_PATH}.sha256" | awk '{print $1}')"
GENERATED_AT_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

python3 - "${REPO_ROOT}/manifests/release.json" "$VERSION" "$PAYLOAD_COMMIT" "$CONFIG_COMMIT" "$BOOTSTRAP_COMMIT" "$LAUNCHER_COMMIT" "$GENERATED_AT_UTC" "$PAYLOAD_URL" "$SHA256" "$CONFIG_SHA256" "$BOOTSTRAP_SHA256" "$LAUNCHER_SHA256" "$TAR_NAME" "$PAYLOAD_SHA_FILE_SHA256" <<'PY'
import json, sys
(
    out,
    ver,
    payload_commit,
    cfg_commit,
    boot_commit,
    launcher_commit,
    generated_at_utc,
    url,
    payload_sha,
    cfg_sha,
    boot_sha,
    launcher_sha,
    tar_name,
    sha_file_sha,
) = sys.argv[1:]

raw_base = "https://raw.githubusercontent.com/Awerkori/nox-arch-install"
manifest = {
    "schema_version": 2,
    "version": ver,
    "payload_commit": payload_commit,
    "source_commit": payload_commit,
    "config_commit": cfg_commit,
    "bootstrap_commit": boot_commit,
    "launcher_commit": launcher_commit,
    "generated_at_utc": generated_at_utc,
    "trust_model": "immutable-commit-and-sha256-pinning",
    "payload_url": url,
    "payload_sha256": payload_sha,
    "config_sha256": cfg_sha,
    "bootstrap_sha256": boot_sha,
    "launcher_sha256": launcher_sha,
    "artifacts": {
        "launcher": {
            "name": "i",
            "path": "i",
            "commit": launcher_commit,
            "url": f"{raw_base}/{launcher_commit}/i",
            "sha256": launcher_sha,
        },
        "bootstrap": {
            "name": "nox-install.py",
            "path": "bootstrap/nox-install.py",
            "commit": boot_commit,
            "url": f"{raw_base}/{boot_commit}/bootstrap/nox-install.py",
            "sha256": boot_sha,
        },
        "config": {
            "name": "user_configuration.json",
            "path": "user_configuration.json",
            "commit": cfg_commit,
            "url": f"{raw_base}/{cfg_commit}/user_configuration.json",
            "sha256": cfg_sha,
        },
        "payload": {
            "name": tar_name,
            "url": url,
            "sha256": payload_sha,
        },
        "payload_checksum_file": {
            "name": f"{tar_name}.sha256",
            "sha256": sha_file_sha,
        },
    },
    "reproducibility": {
        "build_script": "scripts/build-release.sh",
        "tar_flags": "GZIP=-n tar --format=gnu --sort=name --mtime='UTC 2026-01-01' --owner=0 --group=0 --numeric-owner --mode='a+rX,u+w,go-w'",
        "included_paths": [
            "LICENSE",
            "install.sh",
            "bootstrap/nox-bootstrap.sh",
            "configs",
            "profiles",
            "scripts",
            "tools",
        ],
    },
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
PY

echo "Built: ${TAR_PATH}"
echo "Generated At (UTC): ${GENERATED_AT_UTC}"
echo "Payload SHA256: ${SHA256}"

if ! $SKIP_GIT_MATCH; then
  "${BASH_SOURCE[0]}" --verify-only "$VERSION" "$BASE_URL"
fi
