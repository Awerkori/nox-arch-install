#!/usr/bin/env python3
"""Interactive simplified installer wrapper for Project Nox on the official Arch Linux ISO.

Collects strictly the personal inputs required from the owner (target SSD,
explicit wipe confirmation, username, and password) and generates the exact
Archinstall silent JSON configuration matching the validated Project Nox layout
(GPT + 4 GiB FAT32 /boot + Btrfs compress=zstd with @, @home, @log, @pkg,
@.snapshots; @swap + ZRAM + CachyOS + Limine + Umbriel + Noctalia via target-offline).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import http.client
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

NOX_RELEASE_VERSION = "v1.0.2"
OFFICIAL_CONFIG_COMMIT = "e50bab32d642dee85ede329100ba451d2f82f491"
DEFAULT_CONFIG_URL = (
    f"https://raw.githubusercontent.com/Awerkori/nox-arch-install/{OFFICIAL_CONFIG_COMMIT}/user_configuration.json"
)
OFFICIAL_CONFIG_SHA256 = "c7c27cbb719d2dce415c68b2c1926fcafd4656045cfe966ebb3331fb2ffe8775"
OFFICIAL_PAYLOAD_URL = (
    "https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.2/nox-archinstall-payload-v1.0.2.tar.gz"
)
OFFICIAL_PAYLOAD_SHA256 = "723c46bb9d6ae2965988e99d25b3198340feb24bdf7a71b5f4b0c1179fe5a774"

LEGACY_RC_TAG = "v1.0.0-rc10"
LEGACY_RC_PREFIX = "v1.0.0-rc"
HOMOLOGATED_ARCHINSTALL_SERIES = "4.5"
REQUIRED_ARCHINSTALL_FLAGS = ("--silent", "--config", "--creds", "--skip-version-check", "--skip-wifi-check")
MIN_DISK_BYTES = 20 * 1024 * 1024 * 1024  # 20 GiB safety floor
ESP_SIZE_MIB = 4096
ESP_START_MIB = 1
BTRFS_START_MIB = ESP_START_MIB + ESP_SIZE_MIB

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
UNSAFE_URL_CHARS_RE = re.compile(r'[\s"\';|&$`<>\\\x00-\x1f]')
MUTABLE_BRANCH_URL_RE = re.compile(
    r"^https?://(?:raw\.githubusercontent\.com/[^/]+/[^/]+/(?:refs/heads/)?(?:main|master)/|"
    r"github\.com/[^/]+/[^/]+/(?:raw|blob)/(?:refs/heads/)?(?:main|master)/)",
    re.IGNORECASE,
)

RESERVED_USERS = {
    "root",
    "daemon",
    "bin",
    "sys",
    "sync",
    "games",
    "man",
    "lp",
    "mail",
    "news",
    "uucp",
    "proxy",
    "www-data",
    "backup",
    "list",
    "irc",
    "gnats",
    "nobody",
    "systemd-network",
    "systemd-resolve",
    "systemd-timesync",
    "systemd-oom",
    "messagebus",
    "dbus",
    "greeter",
    "noxbuild",
}
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


class SafeHTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject any HTTP redirect downgrade or unsupported scheme."""

    def __init__(self, allow_insecure_http: bool = False) -> None:
        super().__init__()
        self.allow_insecure_http = allow_insecure_http

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        parsed = urllib.parse.urlparse(newurl)
        scheme = (parsed.scheme or "").lower()
        if scheme == "http" and not self.allow_insecure_http:
            raise ValueError(f"Redirecionamento inseguro recusado (downgrade HTTPS->HTTP): {newurl}")
        if scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError(f"Alvo de redirecionamento invalido ou esquema nao suportado: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_sha256_bytes(data: bytes, expected_sha256: str, label: str = "artefato") -> str:
    """Verify SHA-256 of raw bytes before parsing or executing content."""
    if not SHA256_RE.fullmatch(expected_sha256 or ""):
        raise ValueError(f"Formato de SHA-256 esperado invalido para {label}: {expected_sha256!r}")
    actual = hashlib.sha256(data).hexdigest()
    if not hmac.compare_digest(actual.lower(), expected_sha256.lower()):
        raise ValueError(
            f"Falha na verificacao SHA-256 de {label}: esperado={expected_sha256.lower()}, obtido={actual.lower()}"
        )
    return actual


def _fetch_url_bytes(url: str, allow_insecure_http: bool = False, timeout: int = 30) -> tuple[bytes, str]:
    """Download URL bytes over validated HTTPS with redirect protection and truncation detection."""
    if UNSAFE_URL_CHARS_RE.search(url or ""):
        raise ValueError(f"URL contem caracteres invalidos ou inseguros: {url!r}")
    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme == "http" and not allow_insecure_http:
        raise ValueError(f"URL insegura recusada (use https://): {url}")
    if scheme not in ("https", "http") or not parsed.netloc:
        raise ValueError(f"URL invalida ou esquema nao suportado: {url}")

    opener = urllib.request.build_opener(SafeHTTPSRedirectHandler(allow_insecure_http=allow_insecure_http))
    req = urllib.request.Request(url, headers={"User-Agent": f"nox-install/{NOX_RELEASE_VERSION}"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            final_url = resp.geturl() or url
            final_scheme = (urllib.parse.urlparse(final_url).scheme or "").lower()
            if final_scheme == "http" and not allow_insecure_http:
                raise ValueError(f"URL final apos redirecionamento usa HTTP inseguro: {final_url}")
            expected_len_hdr = resp.headers.get("Content-Length") if resp.headers else None
            raw_bytes = resp.read()
    except ValueError:
        raise
    except http.client.IncompleteRead as exc:
        raise RuntimeError(f"Download incompleto de {url}: {exc}") from exc
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Erro HTTP {exc.code} ao baixar {url}") from exc
    except ssl.SSLError as exc:
        raise RuntimeError(f"Erro TLS/SSL ao acessar {url}: {exc}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"Falha de rede/DNS/timeout ao acessar {url}: {exc}") from exc

    if expected_len_hdr is not None:
        try:
            exp_len = int(expected_len_hdr.strip())
        except ValueError as exc:
            raise RuntimeError(f"Cabecalho Content-Length invalido em {url}: {expected_len_hdr!r}") from exc
        if len(raw_bytes) != exp_len:
            raise RuntimeError(
                f"Download truncado/incompleto de {url}: esperado={exp_len} bytes, recebido={len(raw_bytes)} bytes."
            )

    if not raw_bytes or not raw_bytes.strip():
        raise ValueError(f"Resposta vazia recebida de {url}.")
    return raw_bytes, final_url


def ensure_interactive_tty() -> None:
    """Ensure stdin reads from the interactive controlling TTY even if invoked via pipe."""
    if sys.stdin.isatty():
        return
    try:
        tty_file = open("/dev/tty", "r", encoding="utf-8")
        sys.stdin = tty_file
    except OSError as exc:
        raise RuntimeError(
            "stdin nao e um terminal interativo e /dev/tty nao esta disponivel. "
            "Baixe o instalador para um arquivo temporario antes de executar com python3."
        ) from exc


def ensure_arch_iso_environment(
    euid: int | None = None,
    efi_dir: Path = Path("/sys/firmware/efi"),
    archiso_dir: Path = Path("/run/archiso"),
) -> None:
    """Refuse execution outside the official UEFI Arch Linux live ISO environment."""
    actual_euid = os.geteuid() if euid is None else euid
    if actual_euid != 0:
        raise RuntimeError("execute o instalador como root na ISO oficial do Arch Linux.")
    if not efi_dir.is_dir():
        raise RuntimeError("sistema nao inicializado em modo UEFI.")
    if not archiso_dir.is_dir():
        raise RuntimeError(
            "este instalador deve ser executado na ISO live oficial do Arch Linux (/run/archiso)."
        )


def _lsblk_mounts_for_device(path: str) -> list[str]:
    """Query mountpoints for a block device and its partitions (fail-closed on error)."""
    res = subprocess.run(
        ["lsblk", "-nr", "-o", "MOUNTPOINT", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"Falha ao consultar lsblk MOUNTPOINT para '{path}' (exit={res.returncode}): {res.stderr.strip()}"
        )
    return sorted({m.strip() for m in res.stdout.splitlines() if m.strip()})


def list_candidate_disks() -> list[dict[str, Any]]:
    """Query lsblk and return eligible disks (>= 20 GiB), excluding live archiso media (fail-closed)."""
    res = subprocess.run(
        ["lsblk", "-d", "-b", "-J", "-o", "NAME,PATH,SIZE,MODEL,SERIAL,TRAN,TYPE,RM,MOUNTPOINTS"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Falha ao listar discos via lsblk (exit={res.returncode}): {res.stderr.strip()}")
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Saida JSON invalida de lsblk ao listar discos: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("blockdevices"), list):
        raise RuntimeError("Saida JSON invalida de lsblk ao listar discos.")
    disks: list[dict[str, Any]] = []
    by_id_map: dict[str, str] = {}
    by_id_dir = Path("/dev/disk/by-id")
    if by_id_dir.is_dir():
        for entry in sorted(by_id_dir.iterdir()):
            if entry.name.startswith(("dm-", "wwn-", "nvme-eui.")) or "-part" in entry.name:
                continue
            try:
                resolved = str(entry.resolve())
                by_id_map.setdefault(resolved, str(entry))
            except OSError:
                continue

    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        path = str(dev.get("path") or "")
        size = int(dev.get("size") or 0)
        if not path or size < MIN_DISK_BYTES:
            continue
        mounts = _lsblk_mounts_for_device(path)
        if any(m.startswith("/run/archiso") for m in mounts):
            continue
        rm_raw = dev.get("rm")
        is_removable = bool(rm_raw) and str(rm_raw).lower() not in {"0", "false"}
        tran = (dev.get("tran") or "disk").strip().lower()
        disks.append(
            {
                "name": str(dev.get("name") or Path(path).name),
                "path": path,
                "size_bytes": size,
                "size_gib": size / (1024**3),
                "model": (dev.get("model") or "Desconhecido").strip(),
                "serial": (dev.get("serial") or "").strip(),
                "tran": tran,
                "removable": is_removable or tran == "usb",
                "mounts": mounts,
                "by_id": by_id_map.get(path, ""),
            }
        )
    return disks


def _collect_lsblk_tree(nodes: list[dict[str, Any]]) -> tuple[set[str], list[str]]:
    """Collect all device paths and mountpoints recursively from lsblk JSON blockdevices."""
    dev_paths: set[str] = set()
    mounts: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            raise RuntimeError("Estrutura JSON invalida em lsblk blockdevices (no nao e objeto).")
        npath = node.get("path")
        nname = node.get("name")
        if isinstance(npath, str) and npath.strip():
            p = npath.strip()
            dev_paths.add(p)
            dev_paths.add(os.path.realpath(p))
        elif isinstance(nname, str) and nname.strip():
            p = f"/dev/{nname.strip()}"
            dev_paths.add(p)
            dev_paths.add(os.path.realpath(p))
        else:
            raise RuntimeError("Estrutura JSON incompleta em lsblk (ausente path/name).")
        mps = node.get("mountpoints")
        if mps is not None:
            if not isinstance(mps, list):
                raise RuntimeError("Campo mountpoints invalido no JSON do lsblk.")
            for mp in mps:
                if isinstance(mp, str) and mp.strip():
                    mounts.append(mp.strip())
        children = node.get("children")
        if children is not None:
            if not isinstance(children, list):
                raise RuntimeError("Campo children invalido no JSON do lsblk.")
            c_paths, c_mounts = _collect_lsblk_tree(children)
            dev_paths.update(c_paths)
            mounts.extend(c_mounts)
    return dev_paths, mounts


def verify_disk_safe_to_wipe(disk: dict[str, Any]) -> None:
    """Fail-closed safety validation of target disk identity, mounts, and active swap before wipe."""
    raw_path = str(disk.get("path") or "").strip()
    if not raw_path:
        raise RuntimeError("Caminho do disco selecionado vazio.")
    disk_path = Path(raw_path)
    if not disk_path.exists():
        raise RuntimeError(f"Disco selecionado '{raw_path}' nao esta mais presente.")

    canonical_disk = os.path.realpath(raw_path)
    if disk.get("by_id"):
        by_id_path = Path(str(disk["by_id"]))
        if not by_id_path.exists() or os.path.realpath(str(by_id_path)) != canonical_disk:
            raise RuntimeError(
                f"Identificador persistente '{disk['by_id']}' nao aponta mais para '{raw_path}' ({canonical_disk}). Abortando."
            )

    # 1. Re-identify selected device via lsblk -b -J (mandatory exit=0 and valid schema)
    lsblk_json_proc = subprocess.run(
        ["lsblk", "-b", "-J", "-o", "NAME,PATH,SIZE,MODEL,SERIAL,TRAN,TYPE,RM,MOUNTPOINTS", raw_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if lsblk_json_proc.returncode != 0:
        raise RuntimeError(
            f"Falha ao reidentificar '{raw_path}' via lsblk (exit={lsblk_json_proc.returncode}): "
            f"{lsblk_json_proc.stderr.strip()}"
        )
    try:
        lsblk_data = json.loads(lsblk_json_proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Saida JSON invalida de lsblk para '{raw_path}': {exc}") from exc

    if not isinstance(lsblk_data, dict) or not isinstance(lsblk_data.get("blockdevices"), list) or not lsblk_data["blockdevices"]:
        raise RuntimeError(f"Estrutura JSON incompleta de lsblk ao verificar '{raw_path}'.")

    top_dev = lsblk_data["blockdevices"][0]
    if not isinstance(top_dev, dict) or top_dev.get("type") != "disk":
        raise RuntimeError(f"Dispositivo '{raw_path}' nao e reconhecido como disco ('type=disk').")

    actual_path = str(top_dev.get("path") or "")
    actual_name = str(top_dev.get("name") or "")
    try:
        actual_size = int(top_dev.get("size"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Tamanho invalido retornado pelo lsblk para '{raw_path}'.") from exc

    if not actual_path or os.path.realpath(actual_path) != canonical_disk:
        raise RuntimeError(f"Caminho canonico divergente para '{raw_path}': obtido '{actual_path}'.")
    if disk.get("name") and actual_name != disk["name"]:
        raise RuntimeError(f"Nome do disco mudou entre selecao e formatacao: '{disk['name']}' -> '{actual_name}'.")
    if disk.get("size_bytes") is not None and int(disk["size_bytes"]) != actual_size:
        raise RuntimeError(
            f"Tamanho do disco '{raw_path}' mudou entre selecao e formatacao ({disk['size_bytes']} -> {actual_size})."
        )
    actual_model = str(top_dev.get("model") or "Desconhecido").strip()
    if disk.get("model") and actual_model != str(disk["model"]).strip():
        raise RuntimeError(
            f"Modelo do disco '{raw_path}' mudou entre selecao e formatacao ('{disk['model']}' -> '{actual_model}')."
        )
    actual_serial = str(top_dev.get("serial") or "").strip()
    if disk.get("serial") is not None and actual_serial != str(disk["serial"]).strip():
        raise RuntimeError(
            f"Serial do disco '{raw_path}' mudou entre selecao e formatacao ('{disk['serial']}' -> '{actual_serial}')."
        )
    actual_tran = str(top_dev.get("tran") or "disk").strip().lower()
    if disk.get("tran") and actual_tran != str(disk["tran"]).strip().lower():
        raise RuntimeError(
            f"Transporte do disco '{raw_path}' mudou entre selecao e formatacao ('{disk['tran']}' -> '{actual_tran}')."
        )

    dev_paths, json_mounts = _collect_lsblk_tree(lsblk_data["blockdevices"])

    # 2. Cross-check lsblk flat mount list (mandatory exit=0)
    flat_mounts = _lsblk_mounts_for_device(raw_path)
    all_mounts = sorted({*json_mounts, *flat_mounts})
    if any(m.startswith("/run/archiso") for m in all_mounts):
        raise RuntimeError(f"BLOQUEIO: '{raw_path}' contem ponto de montagem da midia Arch ISO (/run/archiso).")
    if all_mounts:
        raise RuntimeError(
            f"O disco '{raw_path}' possui pontos montados ou alvos ativos ({', '.join(all_mounts)}). "
            "Desmonte-os manualmente antes de prosseguir."
        )

    # 3. Cross-check findmnt (fail-closed if findmnt fails or finds any mount sourced from disk or partitions)
    findmnt_proc = subprocess.run(
        ["findmnt", "-rn", "-o", "SOURCE,TARGET"],
        capture_output=True,
        text=True,
        check=False,
    )
    if findmnt_proc.returncode != 0:
        raise RuntimeError(
            f"Falha ao consultar findmnt antes de formatar '{raw_path}' (exit={findmnt_proc.returncode}): "
            f"{findmnt_proc.stderr.strip()}"
        )
    for line in findmnt_proc.stdout.splitlines():
        parts = line.split(None, 1)
        if not parts:
            continue
        src = parts[0].split("[", 1)[0].strip()
        target = parts[1].strip() if len(parts) > 1 else "?"
        if src in dev_paths or (src.startswith("/dev/") and os.path.realpath(src) in dev_paths):
            raise RuntimeError(
                f"Particao ou dispositivo '{src}' pertencente a '{raw_path}' esta montado em '{target}' via findmnt."
            )

    # 4. Verify no active swap resides on the selected disk or any descendant partition (fail-closed)
    swapon_proc = subprocess.run(
        ["swapon", "--noheadings", "--raw", "--show=NAME"],
        capture_output=True,
        text=True,
        check=False,
    )
    if swapon_proc.returncode != 0:
        raise RuntimeError(
            f"Falha ao consultar swap ativo via swapon (exit={swapon_proc.returncode}): "
            f"{swapon_proc.stderr.strip()}"
        )
    for line in swapon_proc.stdout.splitlines():
        sw_dev = line.strip()
        if not sw_dev:
            continue
        if sw_dev in dev_paths or (sw_dev.startswith("/dev/") and os.path.realpath(sw_dev) in dev_paths):
            raise RuntimeError(
                f"Swap ativo detectado no disco/particao '{sw_dev}' (pertencente a '{raw_path}'). "
                "Execute 'swapoff' antes de continuar."
            )


def validate_username(name: str) -> tuple[bool, str]:
    cleaned = name.strip()
    if not cleaned:
        return False, "O nome de usuario nao pode ficar vazio."
    if cleaned in RESERVED_USERS:
        return False, f"O nome '{cleaned}' e reservado pelo sistema."
    if not USERNAME_RE.match(cleaned):
        return (
            False,
            "Use apenas letras minusculas, digitos, '_' ou '-', comecando por letra ou '_' (max. 32 caracteres).",
        )
    return True, cleaned


def build_disk_config(disk_path: str, size_bytes: int, sector_size: int = 512) -> dict[str, Any]:
    """Build deterministic GPT + 4GiB ESP + Btrfs compress=zstd disk_config for the chosen disk."""
    total_mib = size_bytes // (1024 * 1024)
    # Reserve 2 MiB at end for GPT backup header alignment
    btrfs_mib = total_mib - BTRFS_START_MIB - 2
    if btrfs_mib < 16384:
        raise ValueError(f"Disco '{disk_path}' menor que o minimo necessario apos /boot de 4 GiB.")
    return {
        "config_type": "default_layout",
        "btrfs_options": {
            "snapshot_config": {
                "type": "Snapper",
            }
        },
        "device_modifications": [
            {
                "device": disk_path,
                "wipe": True,
                "partitions": [
                    {
                        "btrfs": [],
                        "dev_path": None,
                        "flags": ["boot", "esp"],
                        "fs_type": "fat32",
                        "mount_options": [],
                        "mountpoint": "/boot",
                        "obj_id": "11111111-1111-4111-8111-111111111101",
                        "size": {
                            "sector_size": {"unit": "B", "value": sector_size},
                            "unit": "MiB",
                            "value": ESP_SIZE_MIB,
                        },
                        "start": {
                            "sector_size": {"unit": "B", "value": sector_size},
                            "unit": "MiB",
                            "value": ESP_START_MIB,
                        },
                        "status": "create",
                        "type": "primary",
                    },
                    {
                        "btrfs": [
                            {"mountpoint": "/", "name": "@"},
                            {"mountpoint": "/home", "name": "@home"},
                            {"mountpoint": "/var/log", "name": "@log"},
                            {"mountpoint": "/var/cache/pacman/pkg", "name": "@pkg"},
                            {"mountpoint": "/.snapshots", "name": "@.snapshots"},
                        ],
                        "dev_path": None,
                        "flags": [],
                        "fs_type": "btrfs",
                        "mount_options": ["compress=zstd"],
                        "mountpoint": None,
                        "obj_id": "11111111-1111-4111-8111-111111111102",
                        "size": {
                            "sector_size": {"unit": "B", "value": sector_size},
                            "unit": "MiB",
                            "value": btrfs_mib,
                        },
                        "start": {
                            "sector_size": {"unit": "B", "value": sector_size},
                            "unit": "MiB",
                            "value": BTRFS_START_MIB,
                        },
                        "status": "create",
                        "type": "primary",
                    },
                ],
            }
        ],
    }


def hash_password_sha512(password: str) -> str:
    return subprocess.check_output(
        ["openssl", "passwd", "-6", "-stdin"],
        input=password + "\n",
        text=True,
    ).strip()


def load_base_config(
    source: str,
    allow_insecure_http: bool = False,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Load and authenticate user_configuration.json before parsing JSON."""
    if not source or not source.strip():
        raise ValueError("Fonte de configuracao vazia.")

    is_official_source = source == DEFAULT_CONFIG_URL
    if is_official_source and MUTABLE_BRANCH_URL_RE.match(source):
        raise ValueError(f"Configuracao oficial nao pode apontar para branch mutavel: {source}")

    effective_sha256 = expected_sha256
    if is_official_source and effective_sha256 is None:
        effective_sha256 = OFFICIAL_CONFIG_SHA256

    if source.startswith(("http://", "https://")):
        if MUTABLE_BRANCH_URL_RE.match(source) and not effective_sha256 and not allow_insecure_http:
            raise ValueError(
                f"Configuracao remota em branch mutavel recusada sem --config-sha256: {source}"
            )
        raw_bytes, _final_url = _fetch_url_bytes(source, allow_insecure_http=allow_insecure_http, timeout=30)
    else:
        cfg_path = Path(source)
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {source}")
        raw_bytes = cfg_path.read_bytes()
        if not raw_bytes or not raw_bytes.strip():
            raise ValueError(f"Arquivo de configuracao vazio: {source}")

    if effective_sha256 is not None:
        verify_sha256_bytes(raw_bytes, effective_sha256, label="user_configuration.json")

    try:
        raw_text = raw_bytes.decode("utf-8")
        data = json.loads(raw_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"user_configuration.json malformado ou JSON invalido: {exc}") from exc

    if not isinstance(data, dict) or not data.get("custom_commands"):
        raise ValueError("user_configuration.json invalido ou sem 'custom_commands'.")
    for req_key in ("bootloader_config", "locale_config", "network_config"):
        if req_key not in data:
            raise ValueError(f"user_configuration.json incompleto (ausente: '{req_key}').")
    for forbidden_key in ("disk_config", "auth_config", "users", "root_enc_password", "encryption_password"):
        if forbidden_key in data:
            raise ValueError(f"user_configuration.json contem chave proibida na base publica: '{forbidden_key}'.")
    return data


def override_payload_cmd(
    cfg: dict[str, Any],
    payload_url: str | None,
    payload_sha: str | None,
    allow_insecure_http: bool = False,
) -> None:
    if payload_url:
        if UNSAFE_URL_CHARS_RE.search(payload_url):
            raise ValueError(f"Payload URL contem caracteres invalidos: {payload_url!r}")
        if payload_url.startswith("http://") and not allow_insecure_http:
            raise ValueError(f"Payload URL HTTP recusada sem --allow-insecure-http: {payload_url}")
    if payload_sha and not SHA256_RE.fullmatch(payload_sha):
        raise ValueError(f"SHA-256 de payload invalido: {payload_sha}")
    if not payload_url and not payload_sha:
        return
    cmds = list(cfg.get("custom_commands") or [])
    new_cmds: list[str] = []
    for cmd in cmds:
        updated = cmd
        if payload_url:
            updated = re.sub(r'URL=\\?"[^"]+\\?"', f'URL="{payload_url}"', updated)
            if payload_url.startswith("http://") and allow_insecure_http:
                updated = updated.replace('--proto "=https" ', "").replace('--proto-redir "=https" ', "")
        if payload_sha:
            updated = re.sub(r'SHA=\\?"[0-9a-fA-F]{64}\\?"', f'SHA="{payload_sha}"', updated)
        new_cmds.append(updated)
    cfg["custom_commands"] = new_cmds


def extract_payload_spec(cfg: dict[str, Any]) -> tuple[str, str]:
    joined = "\n".join(cfg.get("custom_commands") or [])
    m_url = re.search(r'URL="([^"]*)"', joined)
    m_sha = re.search(r'SHA="([^"]*)"', joined)
    return (m_url.group(1) if m_url else "", m_sha.group(1) if m_sha else "")


def validate_payload_spec(
    cfg: dict[str, Any],
    allow_insecure_http: bool = False,
    allow_legacy_rc: bool = False,
    enforce_official_payload: bool = False,
) -> tuple[str, str]:
    url, sha = extract_payload_spec(cfg)
    if not url or not sha:
        raise ValueError("Nao foi possivel extrair URL/SHA-256 validos do payload em custom_commands.")
    if UNSAFE_URL_CHARS_RE.search(url):
        raise ValueError(f"URL do payload contem caracteres invalidos: {url!r}")
    if not SHA256_RE.fullmatch(sha):
        raise ValueError(f"Formato de SHA-256 do payload invalido em custom_commands: {sha!r}")

    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme == "http" and not allow_insecure_http:
        raise ValueError(f"Payload deve usar HTTPS: {url}")
    if scheme not in ("https", "http") or not parsed.netloc:
        raise ValueError(f"URL do payload invalida: {url}")
    if MUTABLE_BRANCH_URL_RE.match(url) and not allow_insecure_http:
        raise ValueError(f"Payload oficial nao pode apontar para branch mutavel: {url}")
    if (LEGACY_RC_TAG in url or LEGACY_RC_PREFIX in url) and not allow_legacy_rc:
        raise ValueError(
            f"Configuracao base aponta para payload RC legado ({url}). "
            "Utilize a configuracao vinculada a release oficial ou passe --payload-url/--payload-sha256."
        )
    if enforce_official_payload:
        if url != OFFICIAL_PAYLOAD_URL or not hmac.compare_digest(sha.lower(), OFFICIAL_PAYLOAD_SHA256.lower()):
            raise ValueError(
                "Configuracao incompativel com esta versao do bootstrap: URL ou SHA-256 do payload "
                f"diverge do manifesto oficial ({NOX_RELEASE_VERSION})."
            )
    return url, sha


def detect_archinstall_version(allow_untested: bool = False) -> str:
    res = subprocess.run(["archinstall", "--version"], capture_output=True, text=True, check=False)
    combined = (res.stdout + "\n" + res.stderr).strip()
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", combined)
    if res.returncode != 0 or not m:
        raise RuntimeError(f"archinstall ausente ou versao ilegivel: {combined or res.returncode}")
    ver = m.group(1)
    if not (ver == HOMOLOGATED_ARCHINSTALL_SERIES or ver.startswith(HOMOLOGATED_ARCHINSTALL_SERIES + ".")):
        if not allow_untested:
            raise RuntimeError(
                f"Versao de archinstall '{ver}' nao homologada (homologado especificamente na serie {HOMOLOGATED_ARCHINSTALL_SERIES})."
            )
    help_res = subprocess.run(["archinstall", "--help"], capture_output=True, text=True, check=False)
    help_txt = (help_res.stdout or "") + "\n" + (help_res.stderr or "")
    for flag in REQUIRED_ARCHINSTALL_FLAGS:
        if flag not in help_txt:
            raise RuntimeError(f"Interface CLI do archinstall '{ver}' nao suporta a flag obrigatoria '{flag}'.")
    return ver


def select_tmpfs_dir(mounts_file: Path = Path("/proc/mounts")) -> str:
    """Return a verified in-memory tmpfs directory (/dev/shm, /run, or /tmp) for temporary credentials."""
    mounts: dict[str, str] = {}
    try:
        for line in mounts_file.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 3:
                mounts[parts[1]] = parts[2]
    except OSError:
        pass
    for candidate in ("/dev/shm", "/tmp", "/run"):
        if mounts.get(candidate) == "tmpfs" and os.path.isdir(candidate) and os.access(candidate, os.W_OK | os.X_OK):
            return candidate
    raise RuntimeError("Nenhum filesystem temporario em RAM (tmpfs) disponivel para armazenar credenciais temporarias.")


def scrub_persisted_archinstall_credentials(
    log_dirs: tuple[Path, ...] = (Path("/var/log/archinstall"), Path("/mnt/var/log/archinstall")),
) -> None:
    """Ensure archinstall log directories never retain user_credentials.json or world-readable logs."""
    for log_dir in log_dirs:
        if not log_dir.is_dir():
            continue
        try:
            os.chmod(log_dir, 0o700)
        except OSError:
            pass
        for cred_name in ("user_credentials.json", "nox_creds.json", "creds.json"):
            cand = log_dir / cred_name
            if cand.exists():
                try:
                    cand.unlink()
                except OSError:
                    pass


def verify_network_preflight(payload_url: str, allow_insecure_http: bool = False) -> None:
    opener = urllib.request.build_opener(SafeHTTPSRedirectHandler(allow_insecure_http=allow_insecure_http))
    for test_url in (payload_url, "https://archlinux.org"):
        req = urllib.request.Request(
            test_url,
            method="HEAD",
            headers={"User-Agent": f"nox-install/{NOX_RELEASE_VERSION}"},
        )
        try:
            with opener.open(req, timeout=12) as resp:
                final_url = resp.geturl() or test_url
                final_scheme = (urllib.parse.urlparse(final_url).scheme or "").lower()
                if final_scheme == "http" and not allow_insecure_http:
                    raise RuntimeError(f"Redirecionamento inseguro para HTTP detectado em {test_url} -> {final_url}")
                if resp.status >= 400:
                    raise RuntimeError(f"Falha HTTP {resp.status} ao verificar {test_url}")
        except urllib.error.HTTPError as exc:
            if exc.code == 405:
                continue
            raise RuntimeError(f"Falha de rede/repositorio em {test_url}: HTTP {exc.code}") from exc
        except Exception as exc:
            raise RuntimeError(f"Sem conectividade ou falha HTTPS ao acessar {test_url}: {exc}") from exc


def build_final_configs(
    base_cfg: dict[str, Any],
    disk: dict[str, Any],
    username: str,
    enc_password: str,
    sector_size: int = 512,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = json.loads(json.dumps(base_cfg))
    cfg.pop("auth_config", None)
    cfg["disk_config"] = build_disk_config(disk["path"], int(disk["size_bytes"]), sector_size=sector_size)
    # Policy: root locked (null), single wheel user whose password also authorizes sudo.
    creds: dict[str, Any] = {
        "root_enc_password": None,
        "users": [
            {
                "enc_password": enc_password,
                "groups": ["wheel"],
                "sudo": True,
                "username": username,
            }
        ],
    }
    return cfg, creds


def _read_disk_sector_size(path: str) -> int:
    try:
        out = subprocess.check_output(["blockdev", "--getss", path], text=True).strip()
        val = int(out)
        return val if val in (512, 4096) else 512
    except Exception:
        return 512


def interactive_main(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 11):
        print("ERRO: Python 3.11+ necessario.", file=sys.stderr)
        return 1

    try:
        ensure_interactive_tty()
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    archinstall_ver = "dry-run"
    if not args.dry_run:
        try:
            ensure_arch_iso_environment()
            archinstall_ver = detect_archinstall_version()
        except RuntimeError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 1

    is_official_config = (
        args.config == DEFAULT_CONFIG_URL
        and args.config_sha256 is None
        and not args.payload_url
        and not args.payload_sha256
    )
    config_mode_label = (
        f"OFICIAL AUTENTICADA ({NOX_RELEASE_VERSION}, SHA-256 verificado)"
        if is_official_config
        else "PERSONALIZADA PELO OPERADOR (--config / override)"
    )

    try:
        base_cfg = load_base_config(
            args.config,
            allow_insecure_http=args.allow_insecure_http,
            expected_sha256=args.config_sha256,
        )
        override_payload_cmd(
            base_cfg,
            args.payload_url,
            args.payload_sha256,
            allow_insecure_http=args.allow_insecure_http,
        )
        payload_url, payload_sha = validate_payload_spec(
            base_cfg,
            allow_insecure_http=args.allow_insecure_http,
            allow_legacy_rc=args.allow_legacy_rc,
            enforce_official_payload=is_official_config,
        )
        if not args.dry_run and not args.skip_net_check:
            verify_network_preflight(payload_url, allow_insecure_http=args.allow_insecure_http)
    except Exception as exc:
        print(f"ERRO DE PRE-VALIDACAO: {exc}", file=sys.stderr)
        return 1

    print("=" * 68)
    print("  PROJECT NOX ARCHINSTALL — Instalacao Guiada Simplificada")
    print("=" * 68)
    if not is_official_config:
        print("  [AVISO] Utilizando configuracao ou payload personalizado pelo operador.")
    print("Configuracoes aplicadas automaticamente:")
    print(f"  * Configuracao    : {config_mode_label}")
    print("  * Particionamento : GPT | /boot 4 GiB FAT32 + Btrfs compress=zstd")
    print("  * Subvolumes      : @ (/), @home, @log, @pkg, @.snapshots, @swap")
    print("  * Kernel & Boot   : linux-cachyos + Limine (Project Nox + sbctl)")
    print("  * Desktop         : Umbriel (dwindle) + Noctalia + Obsidian Purple")
    print("  * Privilegios     : sudo via senha do proprio usuario (root bloqueado)")
    print(f"  * Payload         : {payload_url}")
    print(f"  * Payload SHA-256 : {payload_sha[:16]}...")
    print(f"  * Archinstall     : {archinstall_ver}")
    print("-" * 68)

    disks = list_candidate_disks()
    if not disks:
        print("ERRO: nenhum disco elegivel (>= 20 GiB) encontrado.", file=sys.stderr)
        return 1

    print("\n[1/4] Discos disponiveis:")
    for idx, d in enumerate(disks, 1):
        kind_tag = "USB/REMOVIVEL" if d["removable"] else "INTERNO"
        id_str = f" | ID: {d['by_id']}" if d["by_id"] else ""
        ser_str = f" | Serial: {d['serial']}" if d["serial"] else ""
        mnt_str = f" | MONTADO: {','.join(d['mounts'])}" if d["mounts"] else ""
        print(
            f"  [{idx}] [{kind_tag}] {d['path']} ({d['size_gib']:.1f} GiB) | "
            f"{d['model']} [{d['tran']}]{ser_str}{id_str}{mnt_str}"
        )

    chosen: dict[str, Any] | None = None
    while chosen is None:
        raw_choice = input("\nEscolha o numero do SSD de destino (ou 'q' para cancelar): ").strip()
        if raw_choice.lower() in {"q", "quit", "sair", "exit"}:
            print("Instalacao cancelada pelo usuario antes de modificar qualquer disco.")
            return 130
        if not raw_choice:
            print("Selecao obrigatoria. Nenhum disco e selecionado automaticamente.")
            continue
        if not raw_choice.isdigit():
            print("Selecao invalida. Informe o numero correspondente ao disco desejado.")
            continue
        num = int(raw_choice)
        if not (1 <= num <= len(disks)):
            print(f"Numero fora do intervalo (1..{len(disks)}).")
            continue
        chosen = disks[num - 1]
        if chosen["mounts"]:
            print(
                f"AVISO: '{chosen['path']}' possui particoes montadas ({', '.join(chosen['mounts'])}). "
                "Desmonte antes ou escolha outro disco."
            )
            chosen = None

    print("\n[2/4] CONFIRMACAO DE APAGAMENTO DESTRUTIVO:")
    print(f"  Disco selecionado : {chosen['path']} ({chosen['size_gib']:.1f} GiB)")
    print(f"  Tipo / Barra      : {'USB/REMOVIVEL' if chosen['removable'] else 'INTERNO'} | {chosen['model']} [{chosen['tran']}]")
    if chosen["by_id"]:
        print(f"  Identificador     : {chosen['by_id']}")
    print("  AVISO: TODAS as particoes e dados deste disco serao APAGADOS permanentemente!")
    confirm_name = input(
        f"Digite exatamente '{chosen['name']}' para confirmar a formatacao deste disco: "
    ).strip()
    if confirm_name != chosen["name"]:
        print("Confirmacao nao corresponde ao disco selecionado. Abortando sem modificacoes.")
        return 130

    username = ""
    while not username:
        raw_user = input("\n[3/4] Nome de usuario (minusculas, ex: awerkori): ")
        ok, res = validate_username(raw_user)
        if not ok:
            print(f"Nome invalido: {res}")
            continue
        username = res

    password = ""
    while not password:
        pw1 = getpass.getpass(f"\n[4/4] Senha para '{username}' (tambem usada pelo sudo): ")
        if not pw1:
            print("A senha nao pode ficar vazia.")
            continue
        pw2 = getpass.getpass("Confirme a senha: ")
        if pw1 != pw2:
            print("As senhas nao coincidem. Tente novamente.")
            continue
        password = pw1

    print("\n" + "=" * 68)
    print("  RESUMO FINAL ANTES DE FORMATAR")
    print("=" * 68)
    print(f"  Disco alvo        : {chosen['path']} ({chosen['model']}, {chosen['size_gib']:.1f} GiB)")
    print("  Acao no disco     : APAGAR TUDO e criar GPT (/boot 4 GiB + Btrfs)")
    print("  Compressao Btrfs  : zstd (compress=zstd, @/@home/@log/@pkg/@.snapshots)")
    print(f"  Usuario           : {username} (grupo wheel + sudo)")
    print(f"  Hostname          : {base_cfg.get('hostname', 'Nox-Device-PC')}")
    print("  Senha             : [definida - nao exibida]")
    print("  Conta root        : bloqueada (administracao via sudo)")
    print("=" * 68)
    final_ans = input("Confirmar e iniciar a instalacao agora? [s/N]: ").strip().lower()
    if final_ans not in {"s", "sim", "y", "yes"}:
        del password
        print("Instalacao cancelada pelo usuario antes da formatacao.")
        return 130

    enc_pw = hash_password_sha512(password)
    del password

    try:
        verify_disk_safe_to_wipe(chosen)
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    sector_sz = _read_disk_sector_size(chosen["path"])
    cfg, creds = build_final_configs(base_cfg, chosen, username, enc_pw, sector_size=sector_sz)

    tmp_root = select_tmpfs_dir()
    with tempfile.TemporaryDirectory(prefix="nox-install-", dir=tmp_root) as tmp_dir:
        os.chmod(tmp_dir, 0o700)
        tmp_path = Path(tmp_dir)
        cfg_file = tmp_path / "nox_cfg.json"
        creds_file = tmp_path / "nox_creds.json"
        cfg_file.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        creds_file.write_text(json.dumps(creds, indent=2) + "\n", encoding="utf-8")
        os.chmod(cfg_file, 0o600)
        os.chmod(creds_file, 0o600)

        cmd = [
            "archinstall",
            "--silent",
            "--config",
            str(cfg_file),
            "--creds",
            str(creds_file),
            "--skip-version-check",
            "--skip-wifi-check",
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        try:
            verify_disk_safe_to_wipe(chosen)
        except RuntimeError as exc:
            print(f"ERRO CRITICO (revalidacao final antes de archinstall): {exc}", file=sys.stderr)
            return 1
        print("\nIniciando archinstall com configuracao Project Nox automatica...")
        # Restore standard 0022 umask before spawning archinstall so target /etc, pacstrap, and systemd-nspawn get 0755/0644 instead of inheriting caller 0077.
        prev_umask = os.umask(0o022)
        try:
            proc = subprocess.run(cmd, check=False)
            return proc.returncode
        finally:
            os.umask(prev_umask)
            scrub_persisted_archinstall_credentials()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project Nox simplified Arch ISO installer")
    parser.add_argument("--config", default=DEFAULT_CONFIG_URL, help="Path or URL to user_configuration.json")
    parser.add_argument(
        "--config-sha256",
        default=None,
        help="Expected SHA-256 for custom --config (defaults to pinned OFFICIAL_CONFIG_SHA256 for official config)",
    )
    parser.add_argument("--payload-url", default=None, help="Optional override payload URL for lab testing")
    parser.add_argument("--payload-sha256", default=None, help="Optional override payload SHA-256")
    parser.add_argument("--allow-insecure-http", action="store_true", help="Allow http:// URLs for local lab HTTP servers")
    parser.add_argument("--allow-legacy-rc", action="store_true", help="Allow legacy v1.0.0-rc10 payload URL if unchanged")
    parser.add_argument("--skip-net-check", action="store_true", help="Skip preflight HEAD check")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to archinstall")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(interactive_main(parse_args()))
