"""Unit and contract tests for Nox Archinstall."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class TestUserConfigurationContract(unittest.TestCase):
    def test_public_config_has_no_disk_or_credentials(self) -> None:
        cfg = json.loads((REPO / "user_configuration.json").read_text(encoding="utf-8"))
        self.assertNotIn("disk_config", cfg)
        self.assertNotIn("auth_config", cfg)
        self.assertNotIn("users", cfg)
        self.assertNotIn("root_enc_password", cfg)
        self.assertNotIn("encryption_password", cfg)
        self.assertEqual(cfg["bootloader_config"]["bootloader"], "Limine")
        self.assertEqual(cfg["archinstall_language"], "English")
        self.assertNotIn("grub-btrfs", cfg["packages"])
        self.assertNotIn("grub", cfg["packages"])
        self.assertEqual(cfg["network_config"]["type"], "nm_iwd")
        self.assertEqual(cfg["locale_config"]["kb_layout"], "us-acentos")
        self.assertEqual(cfg["locale_config"]["sys_lang"], "en_CA.UTF-8")
        self.assertEqual(cfg["timezone"], "America/Sao_Paulo")
        self.assertEqual(cfg["swap"]["enabled"], False)
        self.assertEqual(cfg["kernels"], ["linux-zen"])

    def test_umbriel_default_layout_is_dwindle(self) -> None:
        toml_text = (REPO / "configs/umbriel/config.toml").read_text(encoding="utf-8")
        import tomllib
        parsed = tomllib.loads(toml_text)
        self.assertEqual(parsed["layout"]["mode"], "dwindle")
        self.assertIn("dwindle", parsed["layout"])
        self.assertNotIn("scrolling", parsed["layout"])
        self.assertEqual(parsed["environment"]["LANG"], "en_CA.UTF-8")
        self.assertEqual(parsed["environment"]["LANGUAGE"], "en_CA:en_US:en")
        self.assertEqual(parsed["environment"]["AMD_VULKAN_ICD"], "RADV")
        kb = parsed["keybinds"]
        self.assertIn("kitty", str(kb["Mod+Q"]))
        self.assertIn("luciole", str(kb["Mod+E"]))
        self.assertIn("luciole", str(kb["Ctrl+E"]))
        self.assertIn("window-close", str(kb["Mod+C"]))
        self.assertIn("layout-toggle-split", str(kb["Mod+J"]))
        self.assertNotIn("Mod+Return", kb)
        self.assertNotIn("Mod+K", kb)
        self.assertNotIn("Mod+MouseLeft", kb)
        self.assertNotIn("Mod+MouseRight", kb)
        self.assertTrue((REPO / "configs/sysctl/99-nox-performance.conf").is_file())
        self.assertTrue((REPO / "configs/gamemode/gamemode.ini").is_file())
        self.assertTrue((REPO / "configs/boot-hooks/95-nox-sbctl-fallback").is_file())
        self.assertTrue((REPO / "configs/bin/nox-secureboot-enroll").is_file())
        self.assertTrue((REPO / "configs/bin/nox-secureboot-verify").is_file())
        self.assertTrue((REPO / "docs/KEYBINDS_MIGRATION.md").is_file())

    def test_secureboot_enroll_refuses_non_root_without_confirm(self) -> None:
        if os.geteuid() == 0:
            return
        res = subprocess.run(
            ["bash", str(REPO / "configs/bin/nox-secureboot-enroll")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(res.returncode, 0)


class TestHostSafetyGuard(unittest.TestCase):
    def test_install_blocks_unarmed_non_chroot_execution(self) -> None:
        env = os.environ.copy()
        env.pop("NOX_ALLOW_TARGET_EXEC", None)
        res = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--check-only"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(res.returncode, 0)

    def test_install_dry_run_succeeds_safely(self) -> None:
        res = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr)


class TestDisplayProfile(unittest.TestCase):
    def run_profile(self, outputs: list[dict]) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(outputs, tf)
            tpath = Path(tf.name)
        try:
            res = subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-display-profile"),
                    "--profile",
                    str(REPO / "profiles/hardware.json"),
                    "--input-json",
                    str(tpath),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout
        finally:
            tpath.unlink(missing_ok=True)

    def test_physical_dual_monitors(self) -> None:
        # List AOC first to verify EDID model matching beats enumeration order and sets G5 (DP-1) as primary
        out = self.run_profile(
            [
                {"name": "HDMI-A-1", "make": "AOC", "model": "24B35", "modes": ["1920x1080@100", "1920x1080@60"]},
                {"name": "DP-1", "make": "Samsung", "model": "Odyssey G5", "modes": ["2560x1440@165", "2560x1440@60"]},
            ]
        )
        self.assertIn('xwayland_primary_output = "DP-1"', out)
        self.assertIn('mode = "2560x1440@165"', out)
        self.assertIn('position = [0, 0]', out)
        self.assertIn('position = [2560, -350]', out)
        self.assertIn('transform = "90"', out)

    def test_sysfs_edid_identification_matches_g5_and_aoc(self) -> None:
        loader = importlib.machinery.SourceFileLoader(
            "nox_display_profile", str(REPO / "configs/bin/nox-display-profile")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def make_edid(name_txt: str) -> bytes:
            buf = bytearray(128)
            blk = b"\x00\x00\x00\xfc\x00" + name_txt.encode("ascii")[:13].ljust(13, b"\n")
            buf[54:72] = blk
            return bytes(buf)

        with tempfile.TemporaryDirectory() as td:
            drm = Path(td)
            for card_conn, mode, title in [
                ("card0-HDMI-A-1", "1920x1080", "24B35HM2"),
                ("card0-DP-1", "2560x1440", "Odyssey G5"),
            ]:
                d = drm / card_conn
                d.mkdir(parents=True)
                (d / "status").write_text("connected\n", encoding="utf-8")
                (d / "modes").write_text(mode + "\n", encoding="utf-8")
                (d / "edid").write_bytes(make_edid(title))
            outs = mod.load_outputs_from_sysfs(drm)
            cfg = json.loads((REPO / "profiles/hardware.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["displays"]["primary"]["preferred_connectors"][0], "DP-1")
            rendered = mod.render_outputs_toml(outs, cfg)
            self.assertIn('xwayland_primary_output = "DP-1"', rendered)
            self.assertIn('[output."HDMI-A-1"]', rendered)
            self.assertIn('transform = "90"', rendered)

    def test_secondary_disconnected_or_swapped_order(self) -> None:
        out = self.run_profile(
            [
                {"name": "DP-2", "model": "Samsung Odyssey G5", "modes": ["2560x1440@164.83"]},
            ]
        )
        self.assertIn('xwayland_primary_output = "DP-2"', out)
        self.assertIn('mode = "2560x1440@164.83"', out)
        self.assertNotIn("HDMI-A-1", out)

    def test_vm_virtual_output_fallback(self) -> None:
        out = self.run_profile(
            [
                {"name": "Virtual-1", "model": "QEMU Monitor", "modes": ["1920x1080@60"]},
            ]
        )
        self.assertIn('[output."Virtual-1"]', out)
        self.assertNotIn("DP-1", out)
        self.assertNotIn("DP-2", out)


class TestFuxiH3Fix(unittest.TestCase):
    def test_dynamic_suffix_and_numid_and_capture(self) -> None:
        cards_txt = (
            "Card #42\n"
            "  Name: alsa_card.usb-XiiSound_Technology_Corporation_Fuxi-H3-01\n"
            "  Profiles:\n"
            "    output:iec958-stereo+input:mono-fallback: Digital\n"
            "  Active Profile: output:analog-stereo+input:mono-fallback\n"
        )
        sources_txt = (
            "Source #1\n"
            "  Name: alsa_input.pci-0000_00_1f.3.analog-stereo\n"
            "  Mute: yes\n"
            "Source #9\n"
            "  Name: alsa_input.usb-XiiSound_Technology_Corporation_Fuxi-H3-01.mono-fallback\n"
            "  Mute: yes\n"
        )
        amixer_txt = (
            "numid=3,iface=MIXER,name='Mic Capture Switch'\n"
            "numid=4,iface=MIXER,name='Mic Capture Switch',index=1\n"
            "numid=14,iface=MIXER,name='PCM Playback Volume',index=1\n"
        )
        with (
            tempfile.NamedTemporaryFile("w", delete=False) as cf,
            tempfile.NamedTemporaryFile("w", delete=False) as sf,
            tempfile.NamedTemporaryFile("w", delete=False) as af,
            tempfile.NamedTemporaryFile("w", delete=False) as stf,
        ):
            cf.write(cards_txt)
            sf.write(sources_txt)
            af.write(amixer_txt)
            cpath, spath, apath, stpath = Path(cf.name), Path(sf.name), Path(af.name), Path(stf.name)
        stpath.unlink(missing_ok=True)
        try:
            res = subprocess.run(
                [
                    "bash",
                    str(REPO / "configs/bin/nox-fuxi-h3-fix"),
                    "--pactl-cards",
                    str(cpath),
                    "--pactl-sources",
                    str(spath),
                    "--amixer-contents",
                    str(apath),
                    "--alsa-cards",
                    "/dev/null",
                    "--state-file",
                    str(stpath),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Fuxi-H3-01", res.stdout)
            self.assertIn("CHOSEN_PROFILE=output:iec958-stereo+input:mono-fallback", res.stdout)
            self.assertIn("NUMID=14", res.stdout)
            self.assertIn("MIC_SWITCH_NUMIDS=3,4", res.stdout)
            self.assertIn("SOURCE_NAME=alsa_input.usb-XiiSound_Technology_Corporation_Fuxi-H3-01.mono-fallback", res.stdout)
            self.assertIn("SHOULD_UNMUTE_CAPTURE=true", res.stdout)
        finally:
            cpath.unlink(missing_ok=True)
            spath.unlink(missing_ok=True)
            apath.unlink(missing_ok=True)
            stpath.unlink(missing_ok=True)

    def test_preserves_user_intentional_mute_across_hotplug(self) -> None:
        cards_txt = (
            "Card #42\n"
            "  Name: alsa_card.usb-XiiSound_Technology_Corporation_Fuxi-H3-01\n"
            "  Profiles:\n"
            "    output:iec958-stereo+input:mono-fallback: Digital\n"
            "  Active Profile: output:iec958-stereo+input:mono-fallback\n"
        )
        with (
            tempfile.NamedTemporaryFile("w", delete=False) as cf,
            tempfile.NamedTemporaryFile("w", delete=False) as stf,
        ):
            cf.write(cards_txt)
            stf.write("PRESENT=0\nSOURCE=\nUSER_MUTED=1\n")
            cpath, stpath = Path(cf.name), Path(stf.name)
        try:
            res = subprocess.run(
                [
                    "bash",
                    str(REPO / "configs/bin/nox-fuxi-h3-fix"),
                    "--pactl-cards",
                    str(cpath),
                    "--pactl-sources",
                    "/dev/null",
                    "--amixer-contents",
                    "/dev/null",
                    "--alsa-cards",
                    "/dev/null",
                    "--state-file",
                    str(stpath),
                    "--hotplug",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("SHOULD_UNMUTE_CAPTURE=false", res.stdout)
        finally:
            cpath.unlink(missing_ok=True)
            stpath.unlink(missing_ok=True)

    def test_absent_headset_skips_cleanly(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as cf:
            cf.write("Card #1\n  Name: alsa_card.pci-0000_00_1b.0\n")
            cpath = Path(cf.name)
        try:
            res = subprocess.run(
                [
                    "bash",
                    str(REPO / "configs/bin/nox-fuxi-h3-fix"),
                    "--pactl-cards",
                    str(cpath),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("SKIP-HARDWARE", res.stdout)
        finally:
            cpath.unlink(missing_ok=True)


class TestLimineNormalize(unittest.TestCase):
    @staticmethod
    def _load_mod():
        loader = importlib.machinery.SourceFileLoader(
            "nox_limine_normalize", str(REPO / "configs/bin/nox-limine-normalize")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_roundtrip_pre_and_post_normalizes_theme_and_snapshots(self) -> None:
        sample = """timeout: 5
default_entry: 2
remember_last_entry: yes
/+Arch Linux
comment: Arch Linux
comment: machine-id=abc123 order-priority=50
  //linux-cachyos
  comment: Kernel version: 7.3.5-1-cachyos
  comment: kernel-id=linux-cachyos
  protocol: linux
  path: boot():/abc123/linux-cachyos/vmlinuz#deadbeef

  //+Snapshots
  comment: 2 snapshots
  ///2 │ 2026-11-19 14:53:22
  comment: pacman -S foo bar
  ////linux-cachyos
  comment: kernel-id=linux-cachyos
  protocol: linux
  path: boot():/abc123/limine_history/vmlinuz#222
  cmdline: rootflags=subvol=/@.snapshots/2/snapshot
  ///1 │ 2026-11-19 14:53:22
  comment: pre update
  ////linux-cachyos
  comment: kernel-id=linux-cachyos
  protocol: linux
  path: boot():/abc123/limine_history/vmlinuz#111
  cmdline: rootflags=subvol=/@.snapshots/1/snapshot
"""
        mod = self._load_mod()
        with tempfile.TemporaryDirectory() as td:
            esp = Path(td)
            (esp / "nox-limine-wallpaper.png").write_bytes(b"fake-limine-wp")
            meta = {
                1: {"type": "pre", "pre_number": None},
                2: {"type": "post", "pre_number": 1},
            }
            post = mod.transform(sample, "post", esp_dir=esp, snapper_meta=meta)
            self.assertIn("timeout: 5\ndefault_entry: Arch Linux/Project Nox\nremember_last_entry: no\n", post)
            self.assertIn("wallpaper: boot():/nox-limine-wallpaper.png#", post)
            self.assertIn("interface_branding: Project Nox\n", post)
            self.assertIn("  //Project Nox\n", post)
            self.assertNotIn("  //linux-cachyos\n", post)
            self.assertIn("  //Snapshots\n", post)
            self.assertNotIn("//+Snapshots", post)
            self.assertIn("  ///Ponto de Segurança\n", post)
            self.assertIn("  ///Estado Atualizado\n", post)
            self.assertLess(post.index("///Ponto de Segurança"), post.index("///Estado Atualizado"))
            self.assertNotIn("pacman -S", post)
            self.assertNotIn("2026-11-19", post)
            self.assertNotIn("////linux-cachyos", post)

            pre = mod.transform(post, "pre", esp_dir=esp, snapper_meta=meta)
            self.assertIn("  //linux-cachyos\n", pre)
            self.assertNotIn("  //Project Nox\n", pre)
            self.assertIn("  ////linux-cachyos\n", pre)

    def test_snapshot_edge_cases_unpaired_and_empty(self) -> None:
        mod = self._load_mod()
        base_header = "/+Arch Linux\n  //linux-cachyos\n  comment: kernel-id=linux-cachyos\n  //Snapshots\n"
        out_empty = mod.transform(base_header, "post", snapper_meta={})
        self.assertIn("  //Snapshots\n", out_empty)
        self.assertNotIn("Ponto de Segurança", out_empty)

        only_pre = (
            base_header
            + "  ///5 │ 2026-11-19\n  ////linux-cachyos\n  protocol: linux\n  cmdline: rootflags=subvol=/@.snapshots/5/snapshot\n"
        )
        out_pre = mod.transform(only_pre, "post", snapper_meta={5: {"type": "pre", "pre_number": None}})
        self.assertIn("///Ponto de Segurança\n", out_pre)
        self.assertNotIn("Estado Atualizado", out_pre)


class TestSystemToolsLauncher(unittest.TestCase):
    def test_lists_and_resolves_only_hidden_overrides_without_touching_usr_share(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sys_dir = root / "sys"
            usr_dir = root / "usr"
            sys_dir.mkdir()
            usr_dir.mkdir()

            (sys_dir / "kitty.desktop").write_text("[Desktop Entry]\nName=kitty\nExec=kitty\n", encoding="utf-8")
            (sys_dir / "qt6ct.desktop").write_text(
                "[Desktop Entry]\nName=Qt6 Settings\nComment=Qt6 Configuration Tool\nExec=qt6ct\nTerminal=false\n",
                encoding="utf-8",
            )
            (sys_dir / "btop.desktop").write_text(
                "[Desktop Entry]\nName=btop++\nComment=Resource monitor\nExec=btop\nTerminal=true\n",
                encoding="utf-8",
            )
            (usr_dir / "qt6ct.desktop").write_text("[Desktop Entry]\nType=Application\nName=Qt6 Settings\nNoDisplay=true\n", encoding="utf-8")
            (usr_dir / "btop.desktop").write_text("[Desktop Entry]\nType=Application\nName=btop++\nNoDisplay=true\n", encoding="utf-8")

            res = subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-system-tools-list"),
                    "--user-dir",
                    str(usr_dir),
                    "--sys-dir",
                    str(sys_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(
                res.stdout.splitlines(),
                ["btop++\tSystem resource monitor", "Qt6 Settings\tQt6 configuration utility"],
            )
            self.assertFalse(any("gtk" in line.lower() for line in res.stdout.splitlines() if "btop++" in line))

            launch = subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-system-tools-launch"),
                    "--user-dir",
                    str(usr_dir),
                    "--sys-dir",
                    str(sys_dir),
                    "--dry-run",
                    "Qt6 Settings\tQt6 configuration utility",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(launch.stdout.strip(), "qt6ct")

    def test_snapshots_stage_resyncs_limine_restore_overlay_and_ownership(self) -> None:
        common_sh = (REPO / "scripts/lib/common.sh").read_text(encoding="utf-8")
        appearance_sh = (REPO / "scripts/53-appearance.sh").read_text(encoding="utf-8")
        snapshots_sh = (REPO / "scripts/60-snapshots.sh").read_text(encoding="utf-8")
        val_sh = (REPO / "scripts/80-validation.sh").read_text(encoding="utf-8")
        self.assertIn("nox_sync_hidden_tech_desktops()", common_sh)
        self.assertIn('install -d -m 0755 -o "$uid" -g "$gid"', common_sh)
        self.assertIn('"${uhome}/.local" "${uhome}/.local/share"', common_sh)
        self.assertIn("nox_sync_hidden_tech_desktops", appearance_sh)
        self.assertIn("nox_sync_hidden_tech_desktops", snapshots_sh)
        self.assertIn("limine-snapper-restore.desktop", val_sh)


class TestObsidianPurplePolish(unittest.TestCase):
    def test_obsidian_purple_assets_and_palette_contract(self) -> None:
        import tomllib

        palette = json.loads((REPO / "configs/noctalia/palettes/ObsidianPurple.json").read_text(encoding="utf-8"))
        self.assertEqual(palette["version"], 2)
        dark = palette["dark"]
        self.assertEqual(dark["surface"], "#090610")
        self.assertEqual(dark["primary"], "#9333ea")
        for mode in ("dark", "light"):
            term = palette[mode]["terminal"]
            for req in ("foreground", "background", "selection_fg", "selection_bg", "cursor", "cursor_text", "normal", "bright"):
                self.assertIn(req, term)
        session_init = (REPO / "configs/bin/nox-session-init").read_text(encoding="utf-8")
        self.assertNotIn(") >/dev/null 2>&1 &", session_init)
        self.assertIn("noctalia msg wallpaper-get", session_init)
        self.assertTrue((REPO / "configs/wallpapers/obsidian-purple.png").is_file())
        self.assertTrue((REPO / "configs/firefox/nox-theme.js").is_file())
        self.assertTrue((REPO / "configs/gtk/gtk.css").is_file())

        theme_toml = tomllib.loads((REPO / "configs/noctalia/nox-theme.toml").read_text(encoding="utf-8"))
        self.assertEqual(theme_toml["theme"]["source"], "custom")
        self.assertEqual(theme_toml["theme"]["custom_palette"], "ObsidianPurple")
        self.assertIn("umbriel", theme_toml["theme"]["templates"]["builtin_ids"])

        launcher_toml = tomllib.loads((REPO / "configs/noctalia/nox-launcher.toml").read_text(encoding="utf-8"))
        self.assertEqual(launcher_toml["shell"]["launcher"]["providers"]["calculator"]["global"], False)
        self.assertEqual(launcher_toml["shell"]["launcher"]["providers"]["calculator"]["prefix"], "calc")

        power_toml = tomllib.loads((REPO / "configs/noctalia/nox-power.toml").read_text(encoding="utf-8"))
        for key in ("lock", "screen-off", "lock-and-suspend"):
            self.assertEqual(power_toml["idle"]["behavior"][key]["enabled"], False)
            self.assertEqual(power_toml["idle"]["behavior"][key]["timeout"], 0.0)

        logind_idle = (REPO / "configs/systemd/99-nox-no-idle.conf").read_text(encoding="utf-8")
        self.assertIn("IdleAction=ignore", logind_idle)
        self.assertIn("IdleActionSec=0", logind_idle)

        umbriel_toml = tomllib.loads((REPO / "configs/umbriel/config.toml").read_text(encoding="utf-8"))
        kb_cfg = umbriel_toml["input"]["keyboard"]
        self.assertEqual(kb_cfg["layout"], "us")
        self.assertEqual(kb_cfg["variant"], "intl")
        self.assertEqual(kb_cfg["repeat_rate"], 25)
        self.assertEqual(kb_cfg["repeat_delay"], 600)

        gtk_ini = (REPO / "configs/gtk/settings.ini").read_text(encoding="utf-8")
        self.assertIn("gtk-theme-name=adw-gtk3-dark", gtk_ini)
        self.assertIn("gtk-application-prefer-dark-theme=1", gtk_ini)

        desktop_sh = (REPO / "scripts/50-desktop.sh").read_text(encoding="utf-8")
        self.assertNotIn("  libva-utils\n", desktop_sh)
        for kept in ("mesa", "vulkan-radeon", "vulkan-tools", "mesa-utils", "mpvpaper", "socat", "libva"):
            self.assertIn(f"  {kept}\n", desktop_sh)

        for asset in (
            REPO / "configs/fastfetch/nox-logo.txt",
            REPO / "configs/firefox/userChrome.css",
            REPO / "configs/firefox/userContent.css",
            REPO / "configs/greeter/assets/noctalia.svg",
            REPO / "configs/fonts/outfit-latin.ttf",
            REPO / "configs/fonts/plus-jakarta-sans-latin.ttf",
            REPO / "configs/icons/nox-emblem.png",
            REPO / "configs/icons/nox-lockscreen-emblem.gif",
            REPO / "configs/wallpapers/nox-g5-runtime.webm",
            REPO / "configs/wallpapers/nox-aoc-runtime.webm",
            REPO / "configs/wallpapers/nox-lockscreen.png",
            REPO / "configs/wallpapers/nox-greeter.png",
            REPO / "configs/wallpapers/nox-limine.png",
            REPO / "configs/noctalia/plugins/mpvpaper/plugin.toml",
        ):
            self.assertTrue(asset.is_file(), f"Missing asset: {asset}")


class TestNoctaliaLayout(unittest.TestCase):
    def test_landscape_and_portrait_layout_and_mpvpaper_assignment(self) -> None:
        loader = importlib.machinery.SourceFileLoader(
            "nox_noctalia_layout", str(REPO / "configs/bin/nox-noctalia-layout")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        outputs = [
            {"name": "HDMI-A-1", "make": "AOC", "model": "24B35", "width": 1920, "height": 1080},
            {"name": "DP-1", "make": "Samsung", "model": "Odyssey G5", "width": 2560, "height": 1440},
        ]
        assigns = mod.build_mpvpaper_assignments(outputs)["assignments"]
        self.assertTrue(assigns["DP-1"].endswith("nox-g5-runtime.webm"))
        self.assertTrue(assigns["HDMI-A-1"].endswith("nox-aoc-runtime.webm"))

        import tomllib
        ls = tomllib.loads(mod.build_lockscreen_widgets_toml(outputs))
        self.assertTrue(ls["lockscreen_widgets"]["enabled"])
        self.assertIn("lockscreen-login-box@DP-1", ls["lockscreen_widgets"]["widget"])
        self.assertIn("lockscreen-login-box@HDMI-A-1", ls["lockscreen_widgets"]["widget"])
        self.assertEqual(ls["lockscreen_widgets"]["widget"]["lockscreen-widget-emblem-HDMI-A-1"]["cx"], 540.0)


class TestSnapperCleanup(unittest.TestCase):
    def run_cleanup(self, entries: list[dict]) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump({"root": entries}, tf)
            tpath = Path(tf.name)
        try:
            res = subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-snapper-cleanup"),
                    "--input-json",
                    str(tpath),
                    "--session-id",
                    "",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(res.stdout)
        finally:
            tpath.unlink(missing_ok=True)

    def test_keeps_latest_pre_post_and_manual(self) -> None:
        entries = [
            {"number": 0, "type": "single", "cleanup": "", "active": True, "default": True},
            {"number": 1, "type": "pre", "cleanup": "number"},
            {"number": 2, "type": "post", "pre-number": 1, "cleanup": "number"},
            {"number": 3, "type": "single", "cleanup": ""},  # manual snapshot preserved
            {"number": 4, "type": "pre", "cleanup": "number"},
            {"number": 5, "type": "post", "pre-number": 4, "cleanup": "number"},
        ]
        out = self.run_cleanup(entries)
        self.assertEqual(out["delete"], [1, 2])

    def test_aborted_unpaired_pre_preserves_previous_pair(self) -> None:
        entries = [
            {"number": 0, "type": "single", "cleanup": ""},
            {"number": 1, "type": "pre", "cleanup": "number"},
            {"number": 2, "type": "post", "pre-number": 1, "cleanup": "number"},
            {"number": 3, "type": "pre", "cleanup": "number"},
        ]
        out = self.run_cleanup(entries)
        self.assertEqual(out["delete"], [])
        self.assertEqual(out["reason"], "unpaired-newer-pre-preserved")


class TestTopgradeAndSnapperSession(unittest.TestCase):
    def test_topgrade_configs_and_proton_visibility_contracts(self) -> None:
        import tomllib

        arch_cfg = tomllib.loads((REPO / "configs/topgrade/50-nox-arch.toml").read_text(encoding="utf-8"))
        self.assertEqual(arch_cfg["linux"]["arch_package_manager"], "paru")

        self_cfg = tomllib.loads((REPO / "configs/topgrade/98-disable-self-update.toml").read_text(encoding="utf-8"))
        self.assertEqual(self_cfg["misc"]["no_self_update"], True)

        ctr_cfg = tomllib.loads((REPO / "configs/topgrade/99-disable-containers.toml").read_text(encoding="utf-8"))
        self.assertIn("containers", ctr_cfg["misc"]["disable"])

        desktop_sh = (REPO / "scripts/50-desktop.sh").read_text(encoding="utf-8")
        self.assertIn("  protonplus\n", desktop_sh)
        self.assertIn("  proton-cachyos-slr\n", desktop_sh)
        self.assertIn('nox_aur_install_pkg "topgrade-bin"', desktop_sh)
        self.assertNotIn("  steam\n", desktop_sh)
        self.assertNotIn("  proton-cachyos\n", desktop_sh)

        common_sh = (REPO / "scripts/lib/common.sh").read_text(encoding="utf-8")
        self.assertNotIn("ProtonPlus", common_sh)
        self.assertTrue((REPO / "configs/bin/nox-topgrade").is_file())

    def test_multi_transaction_session_consolidates_onto_anchor_pre(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "session.json"
            log_file = root / "snapper.log"
            entries_t1 = [
                {"number": 0, "type": "single", "cleanup": ""},
                {"number": 5, "type": "pre", "cleanup": "number"},
                {"number": 6, "type": "post", "pre-number": 5, "cleanup": "number"},
                {"number": 7, "type": "pre", "cleanup": "number"},
                {"number": 8, "type": "post", "pre-number": 7, "cleanup": "number"},
            ]
            t1_json = root / "t1.json"
            t1_json.write_text(json.dumps({"root": entries_t1}), encoding="utf-8")

            mock_snapper = root / "mock-snapper"
            mock_snapper.write_text(
                "#!/usr/bin/env bash\n"
                f"echo \"$*\" >> '{log_file}'\n"
                "if [[ \"$*\" == *\"create\"* && \"$*\" == *\"--print-number\"* ]]; then\n"
                "  echo 11\n"
                "fi\n",
                encoding="utf-8",
            )
            mock_snapper.chmod(0o755)

            # Txn 1 inside topgrade session: initializes anchor_pre=7 and deletes prior 5,6
            subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-snapper-cleanup"),
                    "--input-json",
                    str(t1_json),
                    "--session-id",
                    "topgrade:4242:100",
                    "--state-file",
                    str(state_file),
                    "--snapper-bin",
                    str(mock_snapper),
                ],
                check=True,
            )
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["anchor_pre"], 7)
            self.assertEqual(saved["latest_post"], 8)

            # Txn 2 inside SAME topgrade session: deletes old post 8, creates post 11 -> pre 7, deletes 9,10
            entries_t2 = [
                {"number": 0, "type": "single", "cleanup": ""},
                {"number": 7, "type": "pre", "cleanup": "number"},
                {"number": 8, "type": "post", "pre-number": 7, "cleanup": "number"},
                {"number": 9, "type": "pre", "cleanup": "number"},
                {"number": 10, "type": "post", "pre-number": 9, "cleanup": "number"},
            ]
            t2_json = root / "t2.json"
            t2_json.write_text(json.dumps({"root": entries_t2}), encoding="utf-8")
            subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-snapper-cleanup"),
                    "--input-json",
                    str(t2_json),
                    "--session-id",
                    "topgrade:4242:100",
                    "--state-file",
                    str(state_file),
                    "--snapper-bin",
                    str(mock_snapper),
                ],
                check=True,
            )
            saved2 = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved2["anchor_pre"], 7)
            self.assertEqual(saved2["latest_post"], 11)
            ops = log_file.read_text(encoding="utf-8").splitlines()
            self.assertIn("--no-dbus -c root delete --sync 5 6", ops[0])
            self.assertIn("--no-dbus -c root delete --sync 8", ops[1])
            self.assertIn("--no-dbus -c root create --type post --pre-number 7 --cleanup-algorithm number", ops[2])
            self.assertIn("--no-dbus -c root delete --sync 9 10", ops[3])

            # Interrupted Txn 3 with unpaired PRE 12 preserves everything cleanly
            entries_t3 = entries_t2 + [{"number": 12, "type": "pre", "cleanup": "number"}]
            t3_json = root / "t3.json"
            t3_json.write_text(json.dumps({"root": entries_t3}), encoding="utf-8")
            res_dry = subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-snapper-cleanup"),
                    "--input-json",
                    str(t3_json),
                    "--session-id",
                    "topgrade:4242:100",
                    "--state-file",
                    str(state_file),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(res_dry.stdout)["action"], "noop")


class TestBootstrapVerification(unittest.TestCase):
    def test_rejects_mismatched_sha256(self) -> None:
        res = subprocess.run(
            [
                "bash",
                str(REPO / "bootstrap/nox-bootstrap.sh"),
                "https://example.invalid/payload.tar.gz",
                "0" * 64,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(res.returncode, 0)


class TestVisualPolishDefinitiva(unittest.TestCase):
    def test_greeter_and_lockscreen_unification_contracts(self) -> None:
        import tomllib

        greeter = tomllib.loads((REPO / "configs/greeter/greeter.toml").read_text(encoding="utf-8"))
        sync_cfg = tomllib.loads((REPO / "configs/greeter/sync.toml").read_text(encoding="utf-8"))
        theme_cfg = tomllib.loads((REPO / "configs/noctalia/nox-theme.toml").read_text(encoding="utf-8"))
        self.assertTrue(greeter["appearance"]["hide_logo"])
        self.assertEqual(greeter["appearance"]["corner_radius_scale"], 1.05)
        self.assertEqual(sync_cfg["appearance"]["corner_radius_scale"], 1.05)
        self.assertEqual(greeter["appearance"]["palette"]["outline"], "#5b21b6")
        self.assertEqual(sync_cfg["appearance"]["palette"]["outline"], "#5b21b6")
        self.assertIn("shadow", greeter["appearance"]["palette"])
        self.assertIn("shadow", sync_cfg["appearance"]["palette"])
        self.assertEqual(sync_cfg["appearance"]["scheme"], "Synced")
        self.assertEqual(greeter["appearance"]["wallpaper"]["tint"], 0.0)
        self.assertEqual(greeter["appearance"]["wallpaper"]["blur"], 0.0)
        self.assertEqual(theme_cfg["lockscreen"]["blur_intensity"], 0.0)
        self.assertEqual(theme_cfg["lockscreen"]["tint_intensity"], 0.0)
        self.assertNotIn("avatar_path", theme_cfg["shell"])
        self.assertTrue(theme_cfg["plugin_settings"]["noctalia/mpvpaper"]["dual_sync"])
        actions = {a["action"]: a for a in theme_cfg["shell"]["session"]["actions"]}
        self.assertEqual(actions["shutdown"]["variant"], "outline")
        self.assertEqual(actions["lock_and_suspend"]["variant"], "outline")
        self.assertTrue(greeter["appearance"]["wallpaper"]["path"].endswith("nox-greeter.png"))

        loader = importlib.machinery.SourceFileLoader(
            "nox_noctalia_layout", str(REPO / "configs/bin/nox-noctalia-layout")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ls = tomllib.loads(
            mod.build_lockscreen_widgets_toml(
                [{"name": "DP-1", "model": "Odyssey G5", "width": 2560, "height": 1440}]
            )
        )
        emblem = ls["lockscreen_widgets"]["widget"]["lockscreen-widget-emblem-DP-1"]
        date_w = ls["lockscreen_widgets"]["widget"]["lockscreen-widget-date-DP-1"]
        login_w = ls["lockscreen_widgets"]["widget"]["lockscreen-login-box@DP-1"]
        self.assertEqual(emblem["box_width"], 160.0)
        self.assertEqual(emblem["box_height"], 160.0)
        self.assertTrue(emblem["settings"]["image_path"].endswith("nox-lockscreen-emblem.gif"))
        self.assertEqual(date_w["type"], "clock")
        self.assertFalse(login_w["settings"]["show_unlock_hint"])
        self.assertTrue(login_w["settings"]["show_session_buttons"])
        self.assertNotIn("background_padding", login_w["settings"])

    def test_dual_monitor_shared_trajectory_and_ipc_sync_contracts(self) -> None:
        import math
        import tomllib

        loader = importlib.machinery.SourceFileLoader(
            "generate_nox_visuals", str(REPO / "tools/generate_nox_visuals.py")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        gen_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen_mod)

        self.assertIsNone(gen_mod._compute_dual_sweep_global(0.02))
        self.assertIsNone(gen_mod._compute_dual_sweep_global(0.85))
        xs = [gen_mod._compute_dual_sweep_global(p)[0] for p in [i / 40.0 for i in range(4, 30)]]
        self.assertTrue(all(xs[i] < xs[i + 1] for i in range(len(xs) - 1)), "Dual sweep must move forward monotonically")
        self.assertLess(xs[0], 0.0)
        self.assertGreater(xs[-1], 3640.0)

        # Verify bezel continuity formula at x_global = 2560 across y in [0, 1440]
        tilt = math.tan(math.radians(-20.0))
        bx_g5 = 2560.0 + (0.0 * tilt) - 0.0
        bx_aoc = 2560.0 + (-350.0 * tilt) - 2560.0
        # At y_virtual = 720 -> y_g5 = 720, y_aoc = 720 - (-350) = 1070
        x_g5_at_y720 = bx_g5 + 720.0 * tilt
        x_aoc_at_y720 = bx_aoc + 1070.0 * tilt
        self.assertAlmostEqual(x_g5_at_y720 - 2560.0, x_aoc_at_y720, places=6)

        plug = tomllib.loads((REPO / "configs/noctalia/plugins/mpvpaper/plugin.toml").read_text(encoding="utf-8"))
        dual_settings = [s for s in plug["setting"] if s["key"] == "dual_sync"]
        self.assertEqual(len(dual_settings), 1)
        self.assertTrue(dual_settings[0]["default"])

        lua = (REPO / "configs/noctalia/plugins/mpvpaper/mpvpaper_service.luau").read_text(encoding="utf-8")
        for needle in ("dualSyncEnabled", "orderedDualConnectors", "syncPairPhase", "resetDualPairZero", "DUAL_CYCLE_SECONDS = 14.0"):
            self.assertIn(needle, lua)

    def test_nox_fastfetch_panel_alignment_and_sections(self) -> None:
        loader = importlib.machinery.SourceFileLoader(
            "nox_fastfetch", str(REPO / "configs/bin/nox-fastfetch")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        sample_raw = [
            "\x1b[m\x1b[?7lawerkori@nox-arch",
            "-----------------",
            "✦ SYSTEM",
            "\x1b[1m├─ OS        \x1b[38;2;168;85;247m│ \x1b[m\x1b[13G\x1b[38;2;245;242;255mArch Linux x86_64",
            "├─ Host      │ \x1b[13GKVM/QEMU Standard PC",
            "├─ Kernel    │ \x1b[13G6.14.0-cachyos",
            "└─ Packages  │ \x1b[13G742 (pacman)",
            "✦ SESSION",
            "├─ DE/WM     │ \x1b[13GUmbriel (Wayland)",
            "└─ Terminal  │ \x1b[13Gkitty 0.41.0",
            "✦ HARDWARE",
            "├─ CPU       │ \x1b[13GAMD Ryzen 9 7950X",
            "└─ Memory    │ \x1b[13G1.24 GiB / 7.75 GiB (\x1b[32m16%\x1b[m)",
            "✦ DISPLAY & STORAGE",
            "├─ Display   │ \x1b[13G1280x800 in 14\" [External]",
            "└─ Disk (/)  │ \x1b[13G8.4 GiB / 60.0 GiB (\x1b[32m14%\x1b[m) - btrfs",
            "● ● ● ● ● ● ● ●",
            "\x1b[?7h",
        ]
        parsed = mod.parse_fastfetch_lines(sample_raw)
        self.assertEqual([s["title"] for s in parsed["sections"]], list(mod.EXPECTED_SECTIONS))
        logo_lines = (REPO / "configs/fastfetch/nox-logo.txt").read_text(encoding="utf-8").splitlines()
        for cols in (120, 90, 62):
            rendered = mod.render_dashboard(parsed, logo_lines, cols)
            self.assertNotIn("\x1b[13G", rendered)
            self.assertNotIn("\x1b[?7l", rendered)
            plain_lines = [mod.strip_ansi(l) for l in rendered.splitlines()]
            sep_cols = {l.find("│") for l in plain_lines if "├─" in l or "└─" in l}
            self.assertEqual(len(sep_cols), 1, f"Misaligned │ separators at cols={cols}: {sep_cols}")
            border_widths = {
                mod.vis_len(l[l.find("╭") :]) for l in plain_lines if "╭─ ✦ " in l
            } | {
                mod.vis_len(l[l.find("╰") :]) for l in plain_lines if "╰─" in l
            }
            self.assertEqual(len(border_widths), 1, f"Mismatched border widths at cols={cols}: {border_widths}")


class TestCorrectiveAuditAdditions(unittest.TestCase):
    def test_nox_install_builds_btrfs_and_locked_root_equivalently(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("nox_install", REPO / "bootstrap/nox-install.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        self.assertFalse(mod.validate_username("root")[0])
        self.assertFalse(mod.validate_username("BadUser")[0])
        self.assertTrue(mod.validate_username("awerkori")[0])

        base_cfg = json.loads((REPO / "user_configuration.json").read_text(encoding="utf-8"))
        disk = {"name": "nvme0n1", "path": "/dev/nvme0n1", "size_bytes": 1000 * 1024**3}
        cfg, creds = mod.build_final_configs(base_cfg, disk, "awerkori", "$6$salt$hash", sector_size=512)

        self.assertNotIn("auth_config", cfg)
        self.assertIsNone(creds["root_enc_password"])
        self.assertEqual(len(creds["users"]), 1)
        self.assertEqual(creds["users"][0]["username"], "awerkori")
        self.assertTrue(creds["users"][0]["sudo"])
        self.assertEqual(creds["users"][0]["groups"], ["wheel"])

        dc = cfg["disk_config"]
        self.assertEqual(dc["btrfs_options"]["snapshot_config"]["type"], "Snapper")
        parts = dc["device_modifications"][0]["partitions"]
        self.assertEqual(parts[0]["fs_type"], "fat32")
        self.assertEqual(parts[0]["size"]["value"], 4096)
        self.assertEqual(parts[1]["fs_type"], "btrfs")
        self.assertEqual(parts[1]["mount_options"], ["compress=zstd"])
        subvols = [(s["name"], s["mountpoint"]) for s in parts[1]["btrfs"]]
        self.assertEqual(
            subvols,
            [
                ("@", "/"),
                ("@home", "/home"),
                ("@log", "/var/log"),
                ("@pkg", "/var/cache/pacman/pkg"),
                ("@.snapshots", "/.snapshots"),
            ],
        )

    def test_limine_interrupted_restore_guards_present(self) -> None:
        for rel in (
            "configs/bin/nox-limine-integrity",
            "configs/bin/nox-limine-snapper-restore",
            "configs/systemd/nox-limine-integrity-shutdown.service",
        ):
            self.assertTrue((REPO / rel).is_file(), f"Missing {rel}")
        pre_hook = (REPO / "configs/boot-hooks/05-nox-limine-naming-pre").read_text(encoding="utf-8")
        fb_hook = (REPO / "configs/boot-hooks/95-nox-sbctl-fallback").read_text(encoding="utf-8")
        k_script = (REPO / "scripts/20-cachyos-kernel.sh").read_text(encoding="utf-8")
        self.assertIn("/run/nox-limine-tx.dirty", pre_hook)
        self.assertIn("/run/nox-limine-tx.dirty", fb_hook)
        self.assertIn("nox-limine-integrity-shutdown.service", k_script)
        self.assertIn("/usr/local/bin/limine-snapper-restore", k_script)

        # Ensure P1/P2/P4/P5 corrective invariants remain intact
        nox_inst = (REPO / "bootstrap/nox-install.py").read_text(encoding="utf-8")
        self.assertIn("ensure_interactive_tty", nox_inst)
        self.assertIn("verify_disk_safe_to_wipe", nox_inst)
        self.assertIn("validate_payload_spec", nox_inst)
        self.assertIn('HOMOLOGATED_ARCHINSTALL_SERIES = "4.5"', nox_inst)
        self.assertIn("select_tmpfs_dir", nox_inst)
        self.assertIn("scrub_persisted_archinstall_credentials", nox_inst)
        repo_stage = (REPO / "scripts/10-cachyos-repos.sh").read_text(encoding="utf-8")
        self.assertNotIn("pacman -Sy --noconfirm", repo_stage)
        desktop_stage = (REPO / "scripts/50-desktop.sh").read_text(encoding="utf-8")
        self.assertIn("nox_log_missing_lib_diagnostics", desktop_stage)
        self.assertIn("pacman -Syyu --noconfirm", desktop_stage)
        self.assertNotIn("_nox_lagging", desktop_stage)
        limine_integ = (REPO / "configs/bin/nox-limine-integrity").read_text(encoding="utf-8")
        self.assertIn('conf_b2="$(b2sum "$CONF"', limine_integ)
        self.assertIn('grep -qaiF "$conf_b2" "$LIMINE_EFI"', limine_integ)
        mem_stage = (REPO / "scripts/70-memory.sh").read_text(encoding="utf-8")
        self.assertNotIn("nodatacow", mem_stage)
        wrap = (REPO / "configs/bin/nox-limine-snapper-restore").read_text(encoding="utf-8")
        self.assertIn("/usr/bin/limine-snapper-list", wrap)


class TestTrustChainHardening(unittest.TestCase):
    @staticmethod
    def _load_nox_install():
        spec = importlib.util.spec_from_file_location("nox_install", REPO / "bootstrap/nox-install.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_stage1_launcher_rejects_tampered_bootstrap_and_http(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake_boot = tmp / "nox-install.py"
            fake_boot.write_text("import sys\nprint('EXECUTED_UNVERIFIED')\nsys.exit(0)\n", encoding="utf-8")
            wrong_sha = "a" * 64

            # 1. Override without NOX_ALLOW_CUSTOM_BOOTSTRAP=1 must fail
            env_no_flag = os.environ.copy()
            env_no_flag["NOX_BOOTSTRAP_URL"] = "https://example.invalid/nox-install.py"
            res_no_flag = subprocess.run(
                ["sh", str(REPO / "i")],
                env=env_no_flag,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_no_flag.returncode, 2)
            self.assertIn("NOX_ALLOW_CUSTOM_BOOTSTRAP=1", res_no_flag.stderr)

            # 2. HTTP URL must be rejected even with NOX_ALLOW_CUSTOM_BOOTSTRAP=1
            env_http = os.environ.copy()
            env_http["NOX_ALLOW_CUSTOM_BOOTSTRAP"] = "1"
            env_http["NOX_BOOTSTRAP_URL"] = "http://127.0.0.1:9999/nox-install.py"
            env_http["NOX_BOOTSTRAP_SHA256"] = wrong_sha
            res_http = subprocess.run(
                ["sh", str(REPO / "i")],
                env=env_http,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_http.returncode, 2)
            self.assertIn("HTTPS estrito", res_http.stderr)

            # 3. Invalid SHA-256 format must be rejected
            env_bad_sha = os.environ.copy()
            env_bad_sha["NOX_ALLOW_CUSTOM_BOOTSTRAP"] = "1"
            env_bad_sha["NOX_BOOTSTRAP_URL"] = "https://example.invalid/nox-install.py"
            env_bad_sha["NOX_BOOTSTRAP_SHA256"] = "not-a-sha256"
            res_bad_sha = subprocess.run(
                ["sh", str(REPO / "i")],
                env=env_bad_sha,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_bad_sha.returncode, 2)
            self.assertIn("formato SHA-256", res_bad_sha.stderr)

            # 4. Tampered bootstrap content must fail SHA-256 verification before python3 executes
            mock_bin = tmp / "bin"
            mock_bin.mkdir()
            mock_curl = mock_bin / "curl"
            mock_curl.write_text(
                "#!/usr/bin/env sh\n"
                "while [ $# -gt 0 ]; do\n"
                "  if [ \"$1\" = \"-o\" ]; then cp '" + str(fake_boot) + "' \"$2\"; exit 0; fi\n"
                "  shift\n"
                "done\n"
                "exit 1\n",
                encoding="utf-8",
            )
            mock_curl.chmod(0o755)

            env_tamper = os.environ.copy()
            env_tamper["PATH"] = f"{mock_bin}:{env_tamper.get('PATH', '')}"
            env_tamper["NOX_ALLOW_CUSTOM_BOOTSTRAP"] = "1"
            env_tamper["NOX_BOOTSTRAP_URL"] = "https://raw.githubusercontent.com/Awerkori/nox-arch-install/0000000/bootstrap/nox-install.py"
            env_tamper["NOX_BOOTSTRAP_SHA256"] = wrong_sha
            res_tamper = subprocess.run(
                ["sh", str(REPO / "i")],
                env=env_tamper,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res_tamper.returncode, 0)
            self.assertIn("falha na verificacao SHA-256", res_tamper.stderr)
            self.assertNotIn("EXECUTED_UNVERIFIED", res_tamper.stdout)

            # 5. Matching SHA-256 executes cleanly
            good_sha = hashlib.sha256(fake_boot.read_bytes()).hexdigest()
            env_good = env_tamper.copy()
            env_good["NOX_BOOTSTRAP_SHA256"] = good_sha
            res_good = subprocess.run(
                ["sh", str(REPO / "i")],
                env=env_good,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_good.returncode, 0)
            self.assertIn("EXECUTED_UNVERIFIED", res_good.stdout)

    def test_config_integrity_verified_before_json_parse_and_http_rejected(self) -> None:
        import hashlib

        mod = self._load_nox_install()
        raw_cfg = (REPO / "user_configuration.json").read_bytes()
        real_sha = hashlib.sha256(raw_cfg).hexdigest()

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cfg_file = tmp / "user_configuration.json"
            cfg_file.write_bytes(raw_cfg)

            # Valid hash succeeds
            loaded = mod.load_base_config(str(cfg_file), expected_sha256=real_sha)
            self.assertEqual(loaded["bootloader_config"]["bootloader"], "Limine")

            # Tampered config with mismatched SHA-256 fails before JSON interpretation
            tampered = tmp / "tampered.json"
            tampered.write_text("NOT EVEN JSON", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                mod.load_base_config(str(tampered), expected_sha256=real_sha)
            self.assertIn("Falha na verificacao SHA-256", str(ctx.exception))

            # Invalid SHA-256 format is rejected
            with self.assertRaises(ValueError) as ctx2:
                mod.load_base_config(str(cfg_file), expected_sha256="12345")
            self.assertIn("Formato de SHA-256", str(ctx2.exception))

            # HTTP URL rejected without allow_insecure_http
            with self.assertRaises(ValueError) as ctx3:
                mod.load_base_config("http://127.0.0.1:8080/user_configuration.json", allow_insecure_http=False)
            self.assertIn("URL insegura recusada", str(ctx3.exception))

            # Mutable branch URL rejected without explicit expected_sha256
            with self.assertRaises(ValueError) as ctx4:
                mod.load_base_config(
                    "https://raw.githubusercontent.com/Awerkori/nox-arch-install/main/user_configuration.json",
                    allow_insecure_http=False,
                    expected_sha256=None,
                )
            self.assertIn("branch mutavel", str(ctx4.exception))

    def test_redirect_downgrade_and_incomplete_download_rejected(self) -> None:
        import http.server
        import threading

        mod = self._load_nox_install()

        class TestHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A002
                pass

            def do_GET(self) -> None:
                if self.path == "/redirect-http":
                    self.send_response(302)
                    self.send_header("Location", "http://example.com/user_configuration.json")
                    self.end_headers()
                elif self.path == "/truncated":
                    self.send_response(200)
                    self.send_header("Content-Length", "500")
                    self.end_headers()
                    self.wfile.write(b'{"partial": true}')
                elif self.path == "/empty":
                    self.send_response(200)
                    self.send_header("Content-Length", "0")
                    self.end_headers()

        server = http.server.HTTPServer(("127.0.0.1", 0), TestHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # 1. SafeHTTPSRedirectHandler refuses redirect to http:// when allow_insecure_http=False
            handler = mod.SafeHTTPSRedirectHandler(allow_insecure_http=False)
            req = mod.urllib.request.Request("https://github.com/Awerkori/nox-arch-install/raw/v1.0.2/user_configuration.json")
            with self.assertRaises(ValueError) as r_ctx:
                handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example.com/cfg.json")
            self.assertIn("downgrade HTTPS->HTTP", str(r_ctx.exception))

            # 2. Truncated download (Content-Length mismatch) raises RuntimeError
            with self.assertRaises(RuntimeError) as t_ctx:
                mod._fetch_url_bytes(f"http://127.0.0.1:{port}/truncated", allow_insecure_http=True)
            self.assertIn("incompleto", str(t_ctx.exception).lower())

            # 3. Empty response raises ValueError
            with self.assertRaises(ValueError) as e_ctx:
                mod._fetch_url_bytes(f"http://127.0.0.1:{port}/empty", allow_insecure_http=True)
            self.assertIn("Resposta vazia", str(e_ctx.exception))
        finally:
            server.shutdown()
            server.server_close()

    def test_payload_validation_rejects_other_version_and_tampered_tarball(self) -> None:
        import http.server
        import tarfile
        import threading

        mod = self._load_nox_install()
        base_cfg = json.loads((REPO / "user_configuration.json").read_text(encoding="utf-8"))

        # 1. Config pointing to another version or wrong payload hash fails when enforce_official_payload=True
        wrong_ver_cfg = json.loads(json.dumps(base_cfg))
        mod.override_payload_cmd(
            wrong_ver_cfg,
            "https://github.com/Awerkori/nox-arch-install/releases/download/v0.9.0/nox-archinstall-payload-v0.9.0.tar.gz",
            "b" * 64,
        )
        with self.assertRaises(ValueError) as v_ctx:
            mod.validate_payload_spec(wrong_ver_cfg, enforce_official_payload=True)
        self.assertIn("incompativel com esta versao do bootstrap", str(v_ctx.exception))

        # 2. Legacy RC payload URL rejected by default
        rc_cfg = json.loads(json.dumps(base_cfg))
        mod.override_payload_cmd(
            rc_cfg,
            "https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.0-rc10/nox-archinstall-payload-v1.0.0-rc10.tar.gz",
            "c" * 64,
        )
        with self.assertRaises(ValueError) as rc_ctx:
            mod.validate_payload_spec(rc_cfg, allow_legacy_rc=False)
        self.assertIn("RC legado", str(rc_ctx.exception))

        # 3. Tampered payload tarball is rejected by nox-bootstrap.sh before extraction
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            pkg_dir = tmp / "pkg"
            pkg_dir.mkdir()
            (pkg_dir / "install.sh").write_text("#!/usr/bin/env bash\necho PWNED\n", encoding="utf-8")
            tar_file = tmp / "payload.tar.gz"
            with tarfile.open(tar_file, "w:gz") as tf:
                tf.add(pkg_dir / "install.sh", arcname="root/install.sh")

            class TarHandler(http.server.BaseHTTPRequestHandler):
                def log_message(self, format: str, *args) -> None:  # noqa: A002
                    pass

                def do_GET(self) -> None:
                    data = tar_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

            srv = http.server.HTTPServer(("127.0.0.1", 0), TarHandler)
            port = srv.server_port
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            try:
                dest_dir = tmp / "dest"
                env = os.environ.copy()
                env["NOX_ALLOW_INSECURE_HTTP"] = "1"
                env["NOX_ALLOW_TARGET_EXEC"] = "1"
                env["NOX_PAYLOAD_DEST_DIR"] = str(dest_dir)
                res = subprocess.run(
                    [
                        "bash",
                        str(REPO / "bootstrap/nox-bootstrap.sh"),
                        f"http://127.0.0.1:{port}/payload.tar.gz",
                        "d" * 64,
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("Checksum SHA-256 divergente", res.stderr)
                self.assertFalse(dest_dir.exists(), "Tampered payload must never be extracted")
            finally:
                srv.shutdown()
                srv.server_close()


class TestBootstrapAndHostSafetyHardening(unittest.TestCase):
    @staticmethod
    def _load_nox_install():
        spec = importlib.util.spec_from_file_location("nox_install", REPO / "bootstrap/nox-install.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_host_safety_guards_reject_execution_outside_iso_and_chroot(self) -> None:
        mod = self._load_nox_install()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            efi_dir = tmp / "efi"
            efi_dir.mkdir()
            missing_archiso = tmp / "no-archiso"

            # 1. Non-root rejected
            with self.assertRaises(RuntimeError) as e1:
                mod.ensure_arch_iso_environment(euid=1000, efi_dir=efi_dir, archiso_dir=efi_dir)
            self.assertIn("root", str(e1.exception))

            # 2. Non-UEFI rejected
            with self.assertRaises(RuntimeError) as e2:
                mod.ensure_arch_iso_environment(euid=0, efi_dir=missing_archiso, archiso_dir=efi_dir)
            self.assertIn("UEFI", str(e2.exception))

            # 3. Missing /run/archiso rejected
            with self.assertRaises(RuntimeError) as e3:
                mod.ensure_arch_iso_environment(euid=0, efi_dir=efi_dir, archiso_dir=missing_archiso)
            self.assertIn("/run/archiso", str(e3.exception))

            # 4. nox-bootstrap.sh refuses execution on host when NOX_ALLOW_TARGET_EXEC is not set
            env = os.environ.copy()
            env.pop("NOX_ALLOW_TARGET_EXEC", None)
            res = subprocess.run(
                [
                    "bash",
                    str(REPO / "bootstrap/nox-bootstrap.sh"),
                    "https://example.com/payload.tar.gz",
                    "e" * 64,
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("BLOQUEIO DE SEGURANCA", res.stderr)

    def test_tmpfs_selection_and_credential_scrubbing(self) -> None:
        mod = self._load_nox_install()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            no_tmpfs_mounts = tmp / "mounts_no_tmpfs"
            no_tmpfs_mounts.write_text("/dev/sda1 / ext4 rw 0 0\n", encoding="utf-8")
            with self.assertRaises(RuntimeError) as ctx:
                mod.select_tmpfs_dir(mounts_file=no_tmpfs_mounts)
            self.assertIn("tmpfs", str(ctx.exception))

            log1 = tmp / "var_log_archinstall"
            log2 = tmp / "mnt_var_log_archinstall"
            log1.mkdir(mode=0o755)
            log2.mkdir(mode=0o755)
            for d in (log1, log2):
                (d / "user_credentials.json").write_text('{"secret": 1}', encoding="utf-8")
                (d / "nox_creds.json").write_text('{"secret": 2}', encoding="utf-8")
                (d / "creds.json").write_text('{"secret": 3}', encoding="utf-8")
                (d / "install.log").write_text("normal log\n", encoding="utf-8")

            mod.scrub_persisted_archinstall_credentials(log_dirs=(log1, log2))
            for d in (log1, log2):
                self.assertFalse((d / "user_credentials.json").exists())
                self.assertFalse((d / "nox_creds.json").exists())
                self.assertFalse((d / "creds.json").exists())
                self.assertTrue((d / "install.log").exists())
                self.assertEqual( d.stat().st_mode & 0o777, 0o700)

    def test_verify_disk_safe_to_wipe_fail_closed_matrix(self) -> None:
        from unittest import mock

        mod = self._load_nox_install()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake_disk = tmp / "nvme0n1"
            fake_disk.write_text("", encoding="utf-8")
            fake_part = tmp / "nvme0n1p1"
            fake_part.write_text("", encoding="utf-8")
            other_disk = tmp / "sda"
            other_disk.write_text("", encoding="utf-8")
            bad_symlink = tmp / "by-id-nvme"
            bad_symlink.symlink_to(other_disk)
            good_symlink = tmp / "by-id-nvme-ok"
            good_symlink.symlink_to(fake_disk)

            base_disk = {
                "name": "nvme0n1",
                "path": str(fake_disk),
                "size_bytes": 100 * (1024**3),
                "model": "TestNVMe",
                "serial": "SER123",
                "tran": "nvme",
                "by_id": str(good_symlink),
            }

            def make_lsblk_json(
                path: str | None = None,
                name: str = "nvme0n1",
                size: int = 100 * (1024**3),
                model: str = "TestNVMe",
                serial: str = "SER123",
                tran: str = "nvme",
                children: list[dict] | None = None,
            ) -> str:
                return json.dumps(
                    {
                        "blockdevices": [
                            {
                                "name": name,
                                "path": path or str(fake_disk),
                                "size": size,
                                "model": model,
                                "serial": serial,
                                "tran": tran,
                                "type": "disk",
                                "rm": False,
                                "mountpoints": [],
                                "children": children or [],
                            }
                        ]
                    }
                )

            def make_runner(
                lsblk_j_rc: int = 0,
                lsblk_j_out: str | None = None,
                lsblk_m_rc: int = 0,
                lsblk_m_out: str = "",
                findmnt_rc: int = 0,
                findmnt_out: str = "/dev/sda1 /\n",
                swapon_rc: int = 0,
                swapon_out: str = "/dev/zram0\n",
            ):
                payload_j = make_lsblk_json() if lsblk_j_out is None else lsblk_j_out

                def _runner(cmd, capture_output=True, text=True, check=False):
                    if cmd[:2] == ["lsblk", "-b"]:
                        return subprocess.CompletedProcess(cmd, lsblk_j_rc, stdout=payload_j, stderr="lsblk-j err")
                    if cmd[:2] == ["lsblk", "-nr"]:
                        return subprocess.CompletedProcess(cmd, lsblk_m_rc, stdout=lsblk_m_out, stderr="lsblk-m err")
                    if cmd[0] == "findmnt":
                        return subprocess.CompletedProcess(cmd, findmnt_rc, stdout=findmnt_out, stderr="findmnt err")
                    if cmd[0] == "swapon":
                        return subprocess.CompletedProcess(cmd, swapon_rc, stdout=swapon_out, stderr="swapon err")
                    raise AssertionError(f"Unexpected cmd: {cmd}")

                return _runner

            # 1. Missing disk rejected
            with self.assertRaises(RuntimeError) as m_ctx:
                mod.verify_disk_safe_to_wipe({"path": str(tmp / "nonexistent"), "by_id": ""})
            self.assertIn("nao esta mais presente", str(m_ctx.exception))

            # 2. Broken/redirected by-id symlink rejected
            with self.assertRaises(RuntimeError) as id_ctx:
                mod.verify_disk_safe_to_wipe({**base_disk, "by_id": str(bad_symlink)})
            self.assertIn("Identificador persistente", str(id_ctx.exception))

            # 3. lsblk -J returning non-zero fails closed
            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(lsblk_j_rc=32)):
                with self.assertRaises(RuntimeError) as e3:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("Falha ao reidentificar", str(e3.exception))

            # 4. Invalid/malformed or incomplete lsblk JSON fails closed
            for bad_json in ("NOT-JSON", "{}", '{"blockdevices": []}'):
                with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(lsblk_j_out=bad_json)):
                    with self.assertRaises(RuntimeError):
                        mod.verify_disk_safe_to_wipe(base_disk)

            # 5. lsblk mountpoints query failure fails closed (never treated as empty mounts)
            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(lsblk_m_rc=1)):
                with self.assertRaises(RuntimeError) as e5:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("Falha ao consultar lsblk", str(e5.exception))

            # 6. Active mount on disk/partition rejected
            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(lsblk_m_out="/mnt\n")):
                with self.assertRaises(RuntimeError) as e6:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("pontos montados", str(e6.exception))

            # 7. Active swap on partition of selected disk rejected & swapon failure fails closed
            children_tree = make_lsblk_json(
                children=[{"name": "nvme0n1p1", "path": str(fake_part), "mountpoints": []}]
            )
            with mock.patch.object(
                mod.subprocess, "run", side_effect=make_runner(lsblk_j_out=children_tree, swapon_out=f"{fake_part}\n")
            ):
                with self.assertRaises(RuntimeError) as e7:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("Swap ativo detectado", str(e7.exception))

            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(swapon_rc=1)):
                with self.assertRaises(RuntimeError) as e7b:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("swapon", str(e7b.exception))

            # 8. findmnt failure or mounted partition via findmnt fails closed
            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(findmnt_rc=1)):
                with self.assertRaises(RuntimeError) as e8:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("findmnt", str(e8.exception))

            with mock.patch.object(
                mod.subprocess,
                "run",
                side_effect=make_runner(lsblk_j_out=children_tree, findmnt_out=f"{fake_part}[/@] /mnt\n"),
            ):
                with self.assertRaises(RuntimeError) as e8b:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("findmnt", str(e8b.exception))

            # 9. Device identity drift (size/serial/model/name) between selection and wipe rejected
            drifted_json = make_lsblk_json(serial="DIFFERENT_DISK")
            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner(lsblk_j_out=drifted_json)):
                with self.assertRaises(RuntimeError) as e9:
                    mod.verify_disk_safe_to_wipe(base_disk)
                self.assertIn("Serial do disco", str(e9.exception))

            # 10. Clean safe disk with matching identity and no mounts/swap passes
            with mock.patch.object(mod.subprocess, "run", side_effect=make_runner()):
                mod.verify_disk_safe_to_wipe(base_disk)

    def test_interactive_tty_and_accidental_wipe_abort_guards(self) -> None:
        from unittest import mock

        mod = self._load_nox_install()

        # 1. ensure_interactive_tty fails cleanly when stdin is not a TTY and /dev/tty is unavailable
        with (
            mock.patch.object(mod.sys.stdin, "isatty", return_value=False),
            mock.patch("builtins.open", side_effect=OSError("no controlling tty")),
        ):
            with self.assertRaises(RuntimeError) as tty_ctx:
                mod.ensure_interactive_tty()
            self.assertIn("/dev/tty", str(tty_ctx.exception))

        # 2. Mismatched disk name in [2/4] aborts with rc=130 without hashing password or running archinstall
        fake_disks = [
            {
                "name": "nvme0n1",
                "path": "/dev/nvme0n1",
                "size_bytes": 100 * (1024**3),
                "size_gib": 100.0,
                "model": "Test NVMe",
                "serial": "SN123",
                "tran": "nvme",
                "removable": False,
                "mounts": [],
                "by_id": "",
            }
        ]
        args = mod.parse_args(["--config", str(REPO / "user_configuration.json"), "--dry-run", "--skip-net-check"])
        with (
            mock.patch.object(mod, "ensure_interactive_tty"),
            mock.patch.object(mod, "list_candidate_disks", return_value=fake_disks),
            mock.patch("builtins.input", side_effect=["1", "wrongdisk"]),
            mock.patch.object(mod.subprocess, "run") as mock_run,
        ):
            rc = mod.interactive_main(args)
            self.assertEqual(rc, 130)
            mock_run.assert_not_called()

        # 3. Declining final confirmation [s/N] aborts with rc=130 without calling archinstall
        with (
            mock.patch.object(mod, "ensure_interactive_tty"),
            mock.patch.object(mod, "list_candidate_disks", return_value=fake_disks),
            mock.patch("builtins.input", side_effect=["1", "nvme0n1", "awerkori", "n"]),
            mock.patch.object(mod.getpass, "getpass", side_effect=["SecretPass123!", "SecretPass123!"]),
            mock.patch.object(mod.subprocess, "run") as mock_run2,
        ):
            rc2 = mod.interactive_main(args)
            self.assertEqual(rc2, 130)
            mock_run2.assert_not_called()


class TestSnapperConcurrencyAndEdgeCases(unittest.TestCase):
    def test_concurrent_cleanup_invocations_are_serialized_by_flock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock_file = root / "cleanup.lock"
            state_file = root / "state.json"
            trace_file = root / "trace.log"
            entries = [
                {"number": 0, "type": "single", "cleanup": ""},
                {"number": 1, "type": "pre", "cleanup": "number"},
                {"number": 2, "type": "post", "pre-number": 1, "cleanup": "number"},
                {"number": 3, "type": "pre", "cleanup": "number"},
                {"number": 4, "type": "post", "pre-number": 3, "cleanup": "number"},
            ]
            in_json = root / "entries.json"
            in_json.write_text(json.dumps({"root": entries}), encoding="utf-8")

            mock_snapper = root / "mock-snapper"
            mock_snapper.write_text(
                "#!/usr/bin/env bash\n"
                f"echo \"START $$ $(date +%s%N)\" >> '{trace_file}'\n"
                "sleep 0.35\n"
                f"echo \"END $$ $(date +%s%N)\" >> '{trace_file}'\n",
                encoding="utf-8",
            )
            mock_snapper.chmod(0o755)

            cmd = [
                "python3",
                str(REPO / "configs/bin/nox-snapper-cleanup"),
                "--input-json",
                str(in_json),
                "--session-id",
                "",
                "--state-file",
                str(state_file),
                "--lock-file",
                str(lock_file),
                "--snapper-bin",
                str(mock_snapper),
            ]
            p1 = subprocess.Popen(cmd)
            p2 = subprocess.Popen(cmd)
            self.assertEqual(p1.wait(timeout=10), 0)
            self.assertEqual(p2.wait(timeout=10), 0)

            events = [line.split()[0] for line in trace_file.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events, ["START", "END", "START", "END"])

    def test_failed_consolidate_create_preserves_intermediate_pair_and_important_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "session.json"
            state_file.write_text(
                json.dumps({"session_id": "topgrade:99:1", "anchor_pre": 7, "latest_post": 8}),
                encoding="utf-8",
            )
            log_file = root / "snapper.log"
            entries = [
                {"number": 0, "type": "single", "cleanup": ""},
                {"number": 4, "type": "single", "cleanup": "number", "userdata": {"important": "yes"}},
                {"number": 7, "type": "pre", "cleanup": "number"},
                {"number": 8, "type": "post", "pre-number": 7, "cleanup": "number"},
                {"number": 9, "type": "pre", "cleanup": "number"},
                {"number": 10, "type": "post", "pre-number": 9, "cleanup": "number"},
            ]
            in_json = root / "in.json"
            in_json.write_text(json.dumps({"root": entries}), encoding="utf-8")

            # Mock snapper that succeeds on deleting old post 8, but FAILS on creating consolidated post
            mock_snapper = root / "mock-snapper"
            mock_snapper.write_text(
                "#!/usr/bin/env bash\n"
                f"echo \"$*\" >> '{log_file}'\n"
                "if [[ \"$*\" == *\"create\"* ]]; then\n"
                "  echo 'simulated create failure' >&2\n"
                "  exit 1\n"
                "fi\n",
                encoding="utf-8",
            )
            mock_snapper.chmod(0o755)

            subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-snapper-cleanup"),
                    "--input-json",
                    str(in_json),
                    "--session-id",
                    "topgrade:99:1",
                    "--state-file",
                    str(state_file),
                    "--snapper-bin",
                    str(mock_snapper),
                ],
                check=True,
            )
            ops = log_file.read_text(encoding="utf-8").splitlines()
            # Must NOT delete 9 and 10 when create fails, and must never touch important=yes snapshot #4
            self.assertEqual(len(ops), 2)
            self.assertFalse(any("9 10" in op for op in ops))
            self.assertFalse(any(" 4" in op for op in ops))
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual((saved["anchor_pre"], saved["latest_post"]), (9, 10))

    def test_snapper_lock_acquisition_fails_closed_without_mutating_state(self) -> None:
        from unittest import mock

        loader = importlib.machinery.SourceFileLoader(
            "nox_snapper_cleanup", str(REPO / "configs/bin/nox-snapper-cleanup")
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_file = root / "state.json"
            initial_state = json.dumps({"session_id": "topgrade:1:1", "anchor_pre": 5, "latest_post": 6})
            state_file.write_text(initial_state, encoding="utf-8")
            snap_log = root / "snapper.log"
            mock_snapper = root / "mock-snapper"
            mock_snapper.write_text(
                f"#!/usr/bin/env bash\necho \"$*\" >> '{snap_log}'\n",
                encoding="utf-8",
            )
            mock_snapper.chmod(0o755)
            in_json = root / "entries.json"
            in_json.write_text(
                json.dumps(
                    {
                        "root": [
                            {"number": 1, "type": "pre", "cleanup": "number"},
                            {"number": 2, "type": "post", "pre-number": 1, "cleanup": "number"},
                            {"number": 5, "type": "pre", "cleanup": "number"},
                            {"number": 6, "type": "post", "pre-number": 5, "cleanup": "number"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            # 1. os.open failure prevents any snapper command or state modification
            bad_lock = root / "nonwritable" / "sub" / "lock"
            with mock.patch("os.open", side_effect=PermissionError("EACCES simulated")):
                with mock.patch("sys.argv", [
                    "nox-snapper-cleanup",
                    "--input-json", str(in_json),
                    "--session-id", "",
                    "--state-file", str(state_file),
                    "--lock-file", str(bad_lock),
                    "--snapper-bin", str(mock_snapper),
                ]):
                    rc = mod.main()
            self.assertEqual(rc, 1)
            self.assertFalse(snap_log.exists(), "No snapper command may execute when lock open fails")
            self.assertEqual(state_file.read_text(encoding="utf-8"), initial_state)

            # 2. fcntl.flock failure closes fd cleanly and prevents snapper execution
            ok_lock = root / "real.lock"
            with (
                mock.patch.object(mod.fcntl, "flock", side_effect=OSError("EWOULDBLOCK simulated")),
                mock.patch("os.close", wraps=os.close) as close_spy,
                mock.patch("sys.argv", [
                    "nox-snapper-cleanup",
                    "--input-json", str(in_json),
                    "--session-id", "",
                    "--state-file", str(state_file),
                    "--lock-file", str(ok_lock),
                    "--snapper-bin", str(mock_snapper),
                ]),
            ):
                rc2 = mod.main()
            self.assertEqual(rc2, 1)
            close_spy.assert_called()
            self.assertFalse(snap_log.exists(), "No snapper command may execute when flock fails")
            self.assertEqual(state_file.read_text(encoding="utf-8"), initial_state)

            # 3. Lock is released cleanly after exception inside critical section
            with self.assertRaises(RuntimeError):
                with mod._cleanup_lock(ok_lock):
                    raise RuntimeError("boom inside locked section")
            # Re-acquiring non-blocking flock proves previous lock was released cleanly
            import fcntl as _fcntl
            fd_check = os.open(str(ok_lock), os.O_CREAT | os.O_RDWR, 0o600)
            try:
                _fcntl.flock(fd_check, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                _fcntl.flock(fd_check, _fcntl.LOCK_UN)
            finally:
                os.close(fd_check)

            # 4. --dry-run remains safe and read-only without needing lock mutation
            dry_res = subprocess.run(
                [
                    "python3",
                    str(REPO / "configs/bin/nox-snapper-cleanup"),
                    "--input-json", str(in_json),
                    "--session-id", "",
                    "--state-file", str(state_file),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(dry_res.stdout)["delete"], [1, 2])
            self.assertEqual(state_file.read_text(encoding="utf-8"), initial_state)


class TestLimineAndSecureBootHardening(unittest.TestCase):
    def test_secureboot_verify_and_limine_integrity_detect_and_repair_failures(self) -> None:
        import hashlib

        def b2(data: bytes) -> str:
            return hashlib.blake2b(data, digest_size=64).hexdigest()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            esp = root / "boot"
            (esp / "EFI/limine").mkdir(parents=True)
            (esp / "EFI/BOOT").mkdir(parents=True)
            (esp / "abc123/linux-cachyos").mkdir(parents=True)

            wp_bytes = b"nox-wallpaper-bytes"
            kern_bytes = b"nox-kernel-vmlinuz-bytes"
            init_bytes = b"nox-initramfs-bytes"
            (esp / "nox-limine-wallpaper.png").write_bytes(wp_bytes)
            (esp / "abc123/linux-cachyos/vmlinuz").write_bytes(kern_bytes)
            (esp / "abc123/linux-cachyos/initramfs-linux-cachyos.img").write_bytes(init_bytes)

            conf_path = esp / "limine.conf"
            conf_text = (
                "timeout: 5\n"
                "default_entry: Arch Linux/Project Nox\n"
                "remember_last_entry: no\n"
                f"wallpaper: boot():/nox-limine-wallpaper.png#{b2(wp_bytes)}\n"
                "wallpaper_style: stretched\n"
                "/+Arch Linux\n"
                "  //Project Nox\n"
                "  comment: kernel-id=linux-cachyos\n"
                "  protocol: linux\n"
                f"  path: boot():/abc123/linux-cachyos/vmlinuz#{b2(kern_bytes)}\n"
                f"  module_path: boot():/abc123/linux-cachyos/initramfs-linux-cachyos.img#{b2(init_bytes)}\n"
            )
            conf_path.write_text(conf_text, encoding="utf-8")
            conf_hash = b2(conf_path.read_bytes())

            limine_efi = esp / "EFI/limine/limine_x64.efi"
            fallback_efi = esp / "EFI/BOOT/BOOTX64.EFI"
            src_efi = root / "BOOTX64.EFI.src"
            src_efi.write_bytes(b"MZ-FAKE-EFI-BINARY-" + (b"0" * 128))
            limine_efi.write_bytes(b"MZ-FAKE-EFI-" + conf_hash.encode("ascii") + b"-SIGNED\n")
            fallback_efi.write_bytes(b"MZ-FAKE-EFI-" + conf_hash.encode("ascii") + b"-SIGNED\n")
            (esp / "abc123/linux-cachyos/vmlinuz").write_bytes(kern_bytes)

            limine_default = root / "default-limine"
            limine_default.write_text(
                "ENABLE_VERIFICATION=yes\nENABLE_ENROLL_LIMINE_CONFIG=yes\n",
                encoding="utf-8",
            )
            dirty_marker = root / "nox-limine-tx.dirty"
            unsigned_list = root / "unsigned.txt"
            unsigned_list.write_text("", encoding="utf-8")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            mock_sbctl = bin_dir / "sbctl"
            mock_sbctl.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$1\" in\n"
                "  setup) echo '{\"installed\": true}' ;;\n"
                "  status) echo '{\"installed\": true, \"setup_mode\": false, \"secure_boot\": false}' ;;\n"
                "  verify)\n"
                f"    if grep -qxF \"$2\" '{unsigned_list}' 2>/dev/null; then\n"
                "      echo \"✗ $2 is not signed\"\n"
                "      exit 1\n"
                "    fi\n"
                "    echo \"✓ $2 is signed\"\n"
                "    ;;\n"
                "  sign)\n"
                "    target=\"${@: -1}\"\n"
                "    real_target=\"$(printf '%s' \"$target\" | sed -E 's|/\\.nox-sbctl-fb\\.[^/]+/|/|; s|\\.nox\\.tmp$||')\"\n"
                f"    sed -i \"\\|^${{real_target}}$|d\" '{unsigned_list}' 2>/dev/null || true\n"
                "    echo \"✓ Signed $target\"\n"
                "    ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            mock_sbctl.chmod(0o755)

            mock_limine = bin_dir / "limine"
            mock_limine.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"enroll-config\" ]]; then\n"
                "  printf 'MZ-FAKE-EFI-%s-SIGNED\\n' \"$3\" > \"$2\"\n"
                "fi\n",
                encoding="utf-8",
            )
            mock_limine.chmod(0o755)

            mock_enroll_cfg = bin_dir / "limine-enroll-config"
            mock_enroll_cfg.write_text(
                "#!/usr/bin/env bash\n"
                f"h=\"$(b2sum '{conf_path}' | awk '{{print $1}}')\"\n"
                f"printf 'MZ-FAKE-EFI-%s-SIGNED\\n' \"$h\" > '{limine_efi}'\n"
                f"'{mock_sbctl}' sign '{limine_efi}' >/dev/null\n",
                encoding="utf-8",
            )
            mock_enroll_cfg.chmod(0o755)

            def run_verify(*extra: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        "bash",
                        str(REPO / "configs/bin/nox-secureboot-verify"),
                        "--esp-path",
                        str(esp),
                        "--limine-default",
                        str(limine_default),
                        "--dirty-marker",
                        str(dirty_marker),
                        "--sbctl-bin",
                        str(mock_sbctl),
                        *extra,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

            # 1. Clean state passes all offline checks
            ok_res = run_verify()
            self.assertEqual(ok_res.returncode, 0, ok_res.stderr + ok_res.stdout)
            self.assertIn("[NOX SECUREBOOT] OK", ok_res.stdout)

            # 2. --require-active fails when UEFI Secure Boot is disabled in firmware
            req_res = run_verify("--require-active")
            self.assertNotEqual(req_res.returncode, 0)
            self.assertIn("UEFI Secure Boot is Disabled (--require-active)", req_res.stderr)

            # 3. Partially updated config (dirty marker present) fails verification
            dirty_marker.write_text("", encoding="utf-8")
            dirty_res = run_verify()
            self.assertNotEqual(dirty_res.returncode, 0)
            self.assertIn("partially updated/interrupted", dirty_res.stderr)
            dirty_marker.unlink()

            # 4. Unsigned EFI binary fails verification
            unsigned_list.write_text(f"{limine_efi}\n", encoding="utf-8")
            unsig_res = run_verify()
            self.assertNotEqual(unsig_res.returncode, 0)
            self.assertIn("unsigned or missing EFI binary", unsig_res.stderr)
            unsigned_list.write_text("", encoding="utf-8")

            # 5. Missing EFI binary fails verification
            fallback_efi.unlink()
            miss_res = run_verify()
            self.assertNotEqual(miss_res.returncode, 0)
            self.assertIn("unsigned or missing EFI binary", miss_res.stderr)

            # 6. Incorrect asset BLAKE2B hash in limine.conf fails verification
            fallback_efi.write_bytes(b"MZ-FAKE-EFI-" + conf_hash.encode("ascii") + b"-SIGNED\n")
            (esp / "abc123/linux-cachyos/vmlinuz").write_bytes(b"TAMPERED-KERNEL-BYTES")
            bad_k_res = run_verify()
            self.assertNotEqual(bad_k_res.returncode, 0)
            self.assertIn("BLAKE2B mismatch", bad_k_res.stderr)
            (esp / "abc123/linux-cachyos/vmlinuz").write_bytes(kern_bytes)

            # 7. Adulterated limine.conf (mismatched config BLAKE2B in EFI + unnormalized //linux-cachyos)
            #    fails nox-secureboot-verify, and is automatically repaired by nox-limine-integrity!
            adulterated = conf_text.replace("  //Project Nox\n", "  //linux-cachyos\n")
            conf_path.write_text(adulterated, encoding="utf-8")
            dirty_marker.write_text("", encoding="utf-8")
            unsigned_list.write_text(f"{limine_efi}\n{fallback_efi}\n", encoding="utf-8")

            adult_res = run_verify()
            self.assertNotEqual(adult_res.returncode, 0)
            self.assertIn("NOT enrolled or mismatched", adult_res.stderr)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            env["ESP_PATH"] = str(esp)
            env["NOX_DIRTY_MARKER"] = str(dirty_marker)
            env["NOX_LIMINE_DEFAULT"] = str(limine_default)
            env["NOX_NORMALIZE_BIN"] = str(REPO / "configs/bin/nox-limine-normalize")
            env["NOX_FALLBACK_HOOK"] = str(REPO / "configs/boot-hooks/95-nox-sbctl-fallback")
            env["NOX_VERIFY_BIN"] = str(REPO / "configs/bin/nox-secureboot-verify")
            env["NOX_LIMINE_SRC_EFI"] = str(src_efi)
            env["NOX_SBCTL_BIN"] = str(mock_sbctl)
            env["NOX_ALLOW_NONROOT_TEST"] = "1"
            env["NOX_FORCE_EFI_HOOK"] = "1"

            # 7a. Missing mandatory dependencies must fail and PRESERVE dirty_marker
            bad_env_norm = env.copy()
            bad_env_norm["NOX_NORMALIZE_BIN"] = str(root / "missing-normalize")
            r_no_norm = subprocess.run(
                ["bash", str(REPO / "configs/bin/nox-limine-integrity"), "--repair-if-dirty"],
                env=bad_env_norm, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(r_no_norm.returncode, 0)
            self.assertTrue(dirty_marker.exists(), "Dirty marker must stay when normalizer is missing")

            bad_env_hook = env.copy()
            bad_env_hook["NOX_FALLBACK_HOOK"] = str(root / "missing-hook")
            r_no_hook = subprocess.run(
                ["bash", str(REPO / "configs/bin/nox-limine-integrity"), "--repair-if-dirty"],
                env=bad_env_hook, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(r_no_hook.returncode, 0)
            self.assertTrue(dirty_marker.exists(), "Dirty marker must stay when fallback hook is missing")

            bad_env_enroll = env.copy()
            bad_env_enroll["NOX_LIMINE_ENROLL_BIN"] = str(root / "missing-enroll")
            r_no_enroll = subprocess.run(
                ["bash", str(REPO / "configs/bin/nox-limine-integrity"), "--repair-if-dirty"],
                env=bad_env_enroll, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(r_no_enroll.returncode, 0)
            self.assertTrue(dirty_marker.exists(), "Dirty marker must stay when limine-enroll-config is missing")

            # 7b. Failing step (normalizer error / enroll error / signing failure) preserves dirty_marker
            fail_script = root / "fail-step"
            fail_script.write_text("#!/usr/bin/env bash\nexit 42\n", encoding="utf-8")
            fail_script.chmod(0o755)
            for override_var in ("NOX_NORMALIZE_BIN", "NOX_LIMINE_ENROLL_BIN", "NOX_FALLBACK_HOOK"):
                f_env = env.copy()
                f_env[override_var] = str(fail_script)
                r_fail = subprocess.run(
                    ["bash", str(REPO / "configs/bin/nox-limine-integrity"), "--repair-if-dirty"],
                    env=f_env, capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(r_fail.returncode, 0, f"Expected failure when {override_var} exits 42")
                self.assertTrue(dirty_marker.exists(), f"Dirty marker must stay when {override_var} fails")

            # 7c. Successful transactional recovery clears dirty_marker ONLY at the end
            rep_res = subprocess.run(
                ["bash", str(REPO / "configs/bin/nox-limine-integrity"), "--repair-if-dirty"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(rep_res.returncode, 0, rep_res.stderr + rep_res.stdout)
            self.assertFalse(dirty_marker.exists())
            self.assertIn("  //Project Nox\n", conf_path.read_text(encoding="utf-8"))

            post_rep_verify = run_verify()
            self.assertEqual(post_rep_verify.returncode, 0, post_rep_verify.stderr + post_rep_verify.stdout)

    def test_secureboot_verify_firmware_json_matrix_and_enroll_fail_closed(self) -> None:
        import hashlib

        def b2(data: bytes) -> str:
            return hashlib.blake2b(data, digest_size=64).hexdigest()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            esp = root / "boot"
            (esp / "EFI/limine").mkdir(parents=True)
            (esp / "EFI/BOOT").mkdir(parents=True)
            (esp / "abc/linux-cachyos").mkdir(parents=True)
            (esp / "efi_sys").mkdir()
            kern = b"kernel"
            (esp / "abc/linux-cachyos/vmlinuz").write_bytes(kern)
            conf = esp / "limine.conf"
            conf.write_text(
                "timeout: 5\n/+Arch Linux\n  //Project Nox\n  comment: kernel-id=linux-cachyos\n"
                f"  path: boot():/abc/linux-cachyos/vmlinuz#{b2(kern)}\n",
                encoding="utf-8",
            )
            conf_h = b2(conf.read_bytes())
            lim_efi = esp / "EFI/limine/limine_x64.efi"
            fb_efi = esp / "EFI/BOOT/BOOTX64.EFI"
            src_efi = root / "BOOTX64.EFI.src"
            src_efi.write_bytes(b"SRC-EFI")
            lim_efi.write_bytes(b"EFI-" + conf_h.encode())
            fb_efi.write_bytes(b"EFI-" + conf_h.encode())
            lim_def = root / "default-limine"
            lim_def.write_text("ENABLE_VERIFICATION=yes\nENABLE_ENROLL_LIMINE_CONFIG=yes\n", encoding="utf-8")
            dirty = root / "dirty"
            status_file = root / "status.json"
            status_rc_file = root / "status.rc"
            status_rc_file.write_text("0", encoding="utf-8")
            enroll_effect = root / "enrolled.flag"

            bin_dir = root / "bin"
            bin_dir.mkdir()
            mock_sbctl = bin_dir / "sbctl"
            mock_sbctl.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$1\" in\n"
                "  setup) echo '{\"installed\": true}' ;;\n"
                "  verify) echo \"✓ $2 is signed\" ;;\n"
                "  sign) echo \"✓ Signed ${@: -1}\" ;;\n"
                "  enroll-keys)\n"
                f"    : > '{enroll_effect}'\n"
                "    echo '{\"setup_mode\": false, \"secure_boot\": false}' > '" + str(status_file) + "'\n"
                "    ;;\n"
                "  status)\n"
                f"    rc=$(cat '{status_rc_file}')\n"
                "    if [[ \"$rc\" -ne 0 ]]; then exit \"$rc\"; fi\n"
                f"    cat '{status_file}'\n"
                "    ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            mock_sbctl.chmod(0o755)

            mock_lim_inst = bin_dir / "limine-install"
            mock_lim_inst.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            mock_lim_inst.chmod(0o755)
            mock_lim_enr = bin_dir / "limine-enroll-config"
            mock_lim_enr.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            mock_lim_enr.chmod(0o755)
            mock_limine = bin_dir / "limine"
            mock_limine.write_text(
                f"#!/usr/bin/env bash\nprintf 'EFI-%s' \"$3\" > \"$2\"\n", encoding="utf-8"
            )
            mock_limine.chmod(0o755)

            def verify_status(json_payload: str, rc: int = 0, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
                status_file.write_text(json_payload, encoding="utf-8")
                status_rc_file.write_text(str(rc), encoding="utf-8")
                return subprocess.run(
                    [
                        "bash", str(REPO / "configs/bin/nox-secureboot-verify"),
                        "--esp-path", str(esp),
                        "--limine-default", str(lim_def),
                        "--dirty-marker", str(dirty),
                        "--sbctl-bin", str(mock_sbctl),
                        *extra,
                    ],
                    capture_output=True, text=True, check=False,
                )

            # A. Verify all 10 firmware JSON scenarios
            r_setup = verify_status('{"setup_mode": true, "secure_boot": false}')
            self.assertEqual(r_setup.returncode, 0, r_setup.stderr)
            self.assertIn("Setup Mode", r_setup.stdout)

            r_user = verify_status('{"setup_mode": false, "secure_boot": false}')
            self.assertEqual(r_user.returncode, 0, r_user.stderr)
            self.assertIn("User Mode", r_user.stdout)

            r_active = verify_status('{"setup_mode": false, "secure_boot": true}', extra=("--require-active",))
            self.assertEqual(r_active.returncode, 0, r_active.stderr)
            self.assertIn("actively enforced", r_active.stdout)

            r_req_off = verify_status('{"setup_mode": false, "secure_boot": false}', extra=("--require-active",))
            self.assertNotEqual(r_req_off.returncode, 0)

            # Empty, malformed, missing fields, wrong types, non-zero exit must ALL FAIL (UNKNOWN)
            for bad_json, bad_rc in (
                ("", 0),
                ("{bad-json", 0),
                ('{"setup_mode": false}', 0),
                ('{"secure_boot": false}', 0),
                ('{"setup_mode": "false", "secure_boot": false}', 0),
                ('{"setup_mode": false, "secure_boot": 1}', 0),
                ('{"setup_mode": false, "secure_boot": false}', 1),
            ):
                for extra in ((), ("--require-active",)):
                    r_bad = verify_status(bad_json, rc=bad_rc, extra=extra)
                    self.assertNotEqual(
                        r_bad.returncode, 0,
                        f"Expected FAIL for bad status payload={bad_json!r} rc={bad_rc} extra={extra}",
                    )
                    self.assertIn("UNKNOWN", r_bad.stderr)

            # B. Enroll fails preflight cleanly if mandatory tools are absent (before calling sbctl enroll-keys)
            status_file.write_text('{"setup_mode": true, "secure_boot": false}', encoding="utf-8")
            status_rc_file.write_text("0", encoding="utf-8")
            enroll_env = os.environ.copy()
            enroll_env["PATH"] = f"{bin_dir}:{enroll_env.get('PATH', '')}"
            enroll_env["ESP_PATH"] = str(esp)
            enroll_env["NOX_EFI_SYS_DIR"] = str(esp / "efi_sys")
            enroll_env["NOX_LIMINE_DEFAULT"] = str(lim_def)
            enroll_env["NOX_DIRTY_MARKER"] = str(dirty)
            enroll_env["NOX_LIMINE_SRC_EFI"] = str(src_efi)
            enroll_env["NOX_FALLBACK_HOOK"] = str(REPO / "configs/boot-hooks/95-nox-sbctl-fallback")
            enroll_env["NOX_VERIFY_BIN"] = str(REPO / "configs/bin/nox-secureboot-verify")
            enroll_env["NOX_SBCTL_BIN"] = str(mock_sbctl)
            enroll_env["NOX_ALLOW_NONROOT_TEST"] = "1"
            enroll_env["NOX_FORCE_EFI_HOOK"] = "1"

            bad_enroll_env = enroll_env.copy()
            bad_enroll_env["NOX_LIMINE_ENROLL_BIN"] = str(root / "missing-limine-enroll")
            re_miss = subprocess.run(
                ["bash", str(REPO / "configs/bin/nox-secureboot-enroll"), "--yes-enroll-uefi-keys"],
                env=bad_enroll_env, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(re_miss.returncode, 0)
            self.assertFalse(enroll_effect.exists(), "Must NOT enroll keys if mandatory tool missing")

            # C. Successful enroll executes all steps, verifies chain, distinguishes Enrolled vs Active
            re_ok = subprocess.run(
                ["bash", str(REPO / "configs/bin/nox-secureboot-enroll"), "--yes-enroll-uefi-keys"],
                env=enroll_env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(re_ok.returncode, 0, re_ok.stderr + re_ok.stdout)
            self.assertIn("Stage 1-4 OK", re_ok.stdout)
            self.assertIn("Stage 5 PENDING", re_ok.stdout)
            self.assertTrue(enroll_effect.exists())


class TestDocumentationAndManifestIntegrity(unittest.TestCase):
    def test_all_markdown_relative_links_exist(self) -> None:
        import re
        import urllib.parse

        link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
        md_files = [REPO / "README.md", *sorted((REPO / "docs").rglob("*.md"))]
        for md in md_files:
            text = md.read_text(encoding="utf-8")
            for raw_target in link_re.findall(text):
                target = raw_target.strip().split()[0]
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                rel_path = urllib.parse.unquote(target.split("#", 1)[0])
                if not rel_path:
                    continue
                resolved = (md.parent / rel_path).resolve()
                self.assertTrue(
                    resolved.exists(),
                    f"Broken link in {md.relative_to(REPO)}: {raw_target!r} -> {resolved} does not exist",
                )

    def test_release_manifest_and_config_payload_consistency(self) -> None:
        manifest = json.loads((REPO / "manifests/release.json").read_text(encoding="utf-8"))
        cfg = json.loads((REPO / "user_configuration.json").read_text(encoding="utf-8"))
        for req in ("version", "payload_commit", "payload_url", "payload_sha256"):
            self.assertIn(req, manifest)
            self.assertTrue(manifest[req])
        joined_cmd = "\n".join(cfg.get("custom_commands") or [])
        self.assertIn(manifest["payload_url"], joined_cmd)
        self.assertIn(manifest["payload_sha256"], joined_cmd)

    def test_documentation_has_no_unverified_mutable_install_commands(self) -> None:
        import hashlib

        launcher_sha = hashlib.sha256((REPO / "i").read_bytes()).hexdigest()
        boot_sha = hashlib.sha256((REPO / "bootstrap/nox-install.py").read_bytes()).hexdigest()
        cfg_sha = hashlib.sha256((REPO / "user_configuration.json").read_bytes()).hexdigest()

        i_text = (REPO / "i").read_text(encoding="utf-8")
        self.assertIn(f'DEFAULT_BOOTSTRAP_SHA256="{boot_sha}"', i_text)
        self.assertNotIn("/main/", i_text)

        boot_text = (REPO / "bootstrap/nox-install.py").read_text(encoding="utf-8")
        self.assertIn(f'OFFICIAL_CONFIG_SHA256 = "{cfg_sha}"', boot_text)
        self.assertNotIn("raw.githubusercontent.com/Awerkori/arch-install/main/", boot_text)
        self.assertNotIn("raw.githubusercontent.com/Awerkori/nox-arch-install/main/", boot_text)

        for doc_rel in ("README.md", "docs/INSTALLATION.md"):
            doc_text = (REPO / doc_rel).read_text(encoding="utf-8")
            self.assertNotIn("/raw/main/i", doc_text)
            self.assertNotIn("raw.githubusercontent.com/Awerkori/arch-install/main/", doc_text)
            self.assertNotIn("raw.githubusercontent.com/Awerkori/nox-arch-install/main/", doc_text)
            self.assertIn("sha256sum -c -", doc_text)

        audit_text = (REPO / "docs/FINAL-AUDIT-REPORT.md").read_text(encoding="utf-8")
        self.assertIn(launcher_sha, audit_text)
        manifest_text = (REPO / "manifests/release.json").read_text(encoding="utf-8")
        self.assertIn(launcher_sha, manifest_text)

    def test_release_manifest_schema_v2_and_verify_only_chain(self) -> None:
        manifest = json.loads((REPO / "manifests/release.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("schema_version"), 2)
        for req in (
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
        ):
            self.assertIn(req, manifest, f"Missing schema v2 key: {req}")
            self.assertTrue(manifest[req], f"Empty schema v2 key: {req}")

        for art_key in ("launcher", "bootstrap", "config"):
            art = manifest["artifacts"][art_key]
            for fkey in ("name", "path", "commit", "url", "sha256"):
                self.assertIn(fkey, art, f"Missing artifacts.{art_key}.{fkey}")
                self.assertTrue(art[fkey])

        # Verify CI secret scan covers .github workflows and detects a runtime canary secret
        ci_yml = (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("--exclude-dir=.github", ci_yml)
        scan_line = ""
        for line in ci_yml.splitlines():
            if "grep -rnE" in line:
                scan_line = line.strip()
                break
        self.assertTrue(scan_line, "Secret scan grep command missing from .github/workflows/ci.yml")
        grep_args = scan_line.lstrip("! ").replace(" \\", "").strip() + " --exclude-dir=.git --exclude-dir=dist --exclude-dir=reports --exclude-dir=__pycache__ ."
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wf = root / ".github/workflows"
            wf.mkdir(parents=True)
            canary = ("gh" + "p_") + ("Z9x8C7v6B5n4M3k2J1h0" * 2)[:36]
            (wf / "canary.yml").write_text(f"env:\n  TOKEN: {canary}\n", encoding="utf-8")
            scan_res = subprocess.run(
                ["bash", "-c", grep_args],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(scan_res.returncode, 0, "Secret scan failed to detect canary inside .github/workflows/")
            self.assertIn(".github/workflows/canary.yml", scan_res.stdout)

    def test_build_release_verify_only_detects_stale_manifest_and_validates_chain(self) -> None:
        # 1. Running --verify-only on the live repository must pass once chain commits are synchronized
        res = subprocess.run(
            ["bash", str(REPO / "scripts/build-release.sh"), "--verify-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
        self.assertIn("VERIFY_RELEASE_CHAIN=PASS", res.stdout)

        # 2. Verify build-release.sh --verify-only FAILS when payload_sha256 is stale in a temp repo copy
        with tempfile.TemporaryDirectory() as td:
            tmp_repo = Path(td) / "repo"
            subprocess.run(["git", "clone", "--quiet", str(REPO), str(tmp_repo)], check=True)
            mpath = tmp_repo / "manifests/release.json"
            mdata = json.loads(mpath.read_text(encoding="utf-8"))
            mdata["payload_sha256"] = "f" * 64
            mpath.write_text(json.dumps(mdata, indent=2) + "\n", encoding="utf-8")
            bad_res = subprocess.run(
                ["bash", str(tmp_repo / "scripts/build-release.sh"), "--verify-only", "--skip-git-match"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad_res.returncode, 0)
            self.assertIn("ERRO payload", bad_res.stderr)

    def test_nox_install_restores_umask_022_before_invoking_archinstall(self) -> None:
        import hashlib
        from unittest import mock

        mod = TestTrustChainHardening._load_nox_install()
        observed: dict[str, object] = {}

        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "user_configuration.json"
            cfg_path.write_text((REPO / "user_configuration.json").read_text(encoding="utf-8"), encoding="utf-8")
            cfg_sha = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
            manifest = json.loads((REPO / "manifests/release.json").read_text(encoding="utf-8"))
            payload_tar = REPO / f"dist/nox-archinstall-payload-{manifest['version']}.tar.gz"
            if not payload_tar.is_file():
                subprocess.run(["bash", str(REPO / "scripts/build-release.sh"), "--skip-git-match"], cwd=REPO, check=True)
            payload_sha = manifest["payload_sha256"]

            fake_disk = {
                "name": "vda",
                "path": "/dev/vda",
                "by_id": "/dev/disk/by-id/virtio-test",
                "size_bytes": 60 * 1024**3,
                "size_gib": 60.0,
                "model": "QEMU",
                "serial": "clean",
                "tran": "virtio",
                "removable": False,
                "mounts": [],
            }
            answers = iter(["1", "vda", "noxdev", "s"])

            def fake_run(cmd, *args, **kwargs):
                cur_umask = os.umask(0o022)
                os.umask(cur_umask)
                observed["cmd"] = cmd
                observed["child_umask"] = cur_umask
                cfg_arg = Path(cmd[cmd.index("--config") + 1])
                creds_arg = Path(cmd[cmd.index("--creds") + 1])
                observed["tmp_dir_mode"] = cfg_arg.parent.stat().st_mode & 0o777
                observed["cfg_mode"] = cfg_arg.stat().st_mode & 0o777
                observed["creds_mode"] = creds_arg.stat().st_mode & 0o777
                return subprocess.CompletedProcess(cmd, 0, "", "")

            old_umask = os.umask(0o077)
            try:
                ns = mod.parse_args(
                    [
                        "--config",
                        str(cfg_path),
                        "--config-sha256",
                        cfg_sha,
                        "--payload-url",
                        f"https://example.invalid/{payload_tar.name}",
                        "--payload-sha256",
                        payload_sha,
                        "--skip-net-check",
                    ]
                )
                with (
                    mock.patch.object(mod, "ensure_interactive_tty"),
                    mock.patch.object(mod, "ensure_arch_iso_environment"),
                    mock.patch.object(mod, "detect_archinstall_version", return_value="4.5"),
                    mock.patch.object(mod, "list_candidate_disks", return_value=[fake_disk]),
                    mock.patch.object(mod, "verify_disk_safe_to_wipe"),
                    mock.patch.object(mod, "_read_disk_sector_size", return_value=512),
                    mock.patch.object(mod, "hash_password_sha512", return_value="$6$test$hash"),
                    mock.patch.object(mod, "select_tmpfs_dir", return_value=td),
                    mock.patch.object(mod, "scrub_persisted_archinstall_credentials"),
                    mock.patch("builtins.input", side_effect=lambda _prompt="": next(answers)),
                    mock.patch("getpass.getpass", return_value="noxdev123"),
                    mock.patch.object(mod.subprocess, "run", side_effect=fake_run),
                ):
                    rc = mod.interactive_main(ns)
                post_umask = os.umask(0o077)
                os.umask(post_umask)
            finally:
                os.umask(old_umask)

            self.assertEqual(rc, 0)
            self.assertEqual(observed["child_umask"], 0o022)
            self.assertEqual(observed["tmp_dir_mode"], 0o700)
            self.assertEqual(observed["cfg_mode"], 0o600)
            self.assertEqual(observed["creds_mode"], 0o600)
            self.assertEqual(post_umask, 0o077)


class TestLimineIntegrityAndSnapPacRegression(unittest.TestCase):
    def test_a3_snap_pac_deferred_out_of_pacstrap_to_stage_60(self) -> None:
        cfg = json.loads((REPO / "user_configuration.json").read_text(encoding="utf-8"))
        self.assertNotIn("snap-pac", cfg["packages"])
        self.assertNotIn("snapper", cfg["packages"])
        stage60 = (REPO / "scripts/60-snapshots.sh").read_text(encoding="utf-8")
        self.assertIn("SNAP_PAC_SKIP=y pacman -S --needed --noconfirm snapper snap-pac", stage60)

    def test_no_silent_boot_integrity_suppression_in_stages_and_restore_wrapper(self) -> None:
        for rel in (
            "scripts/20-cachyos-kernel.sh",
            "scripts/60-snapshots.sh",
            "configs/bin/nox-first-boot",
        ):
            txt = (REPO / rel).read_text(encoding="utf-8")
            self.assertNotIn("limine-enroll-config || true", txt, rel)
            self.assertNotIn("limine-enroll-config >/dev/null 2>&1 || true", txt, rel)
            self.assertNotIn("95-nox-sbctl-fallback || true", txt, rel)
            self.assertNotIn("95-nox-sbctl-fallback >/dev/null 2>&1 || true", txt, rel)
            self.assertRegex(txt, r'nox-limine-integrity"?\s+--force', rel)

        stage80 = (REPO / "scripts/80-validation.sh").read_text(encoding="utf-8")
        self.assertIn("nox-limine-integrity --verify", stage80)

        # Verify restore wrapper propagates repair failure (non-zero) and preserves .dirty
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real_sync = root / "limine-snapper-sync"
            real_sync.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            real_sync.chmod(0o755)
            bad_integ = root / "bad-integ"
            bad_integ.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
            bad_integ.chmod(0o755)
            dirty = root / "dirty"
            dirty.write_text("pending\n", encoding="utf-8")
            wrap_dir = root / "wrap"
            wrap_dir.mkdir()
            wrapper = wrap_dir / "limine-snapper-sync"
            # Point wrapper script at fake real binary by copying helper with swapped /usr/bin lookup
            src_wrap = (REPO / "configs/bin/nox-limine-snapper-restore").read_text(encoding="utf-8")
            wrapper.write_text(src_wrap.replace("/usr/bin/limine-snapper-sync", str(real_sync)), encoding="utf-8")
            wrapper.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "NOX_INTEGRITY_HELPER": str(bad_integ),
                    "NOX_DIRTY_MARKER": str(dirty),
                    "NOX_ALLOW_NONROOT_TEST": "1",
                }
            )
            res = subprocess.run(["bash", str(wrapper), "--list"], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 7)
            self.assertIn("repair_rc=7", res.stderr)
            self.assertTrue(dirty.exists())

    def test_limine_snapper_sync_skips_repair_when_restore_lock_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real_sync = root / "real-sync"
            real_sync.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
            real_sync.chmod(0o755)
            marker = root / "repair-called"
            fake_integ = root / "fake-integ"
            fake_integ.write_text(f"#!/usr/bin/env bash\ntouch '{marker}'\nexit 0\n", encoding="utf-8")
            fake_integ.chmod(0o755)
            restore_lock = root / "limine-snapper-restore.lock"
            restore_lock.write_text("", encoding="utf-8")
            dirty = root / "dirty"
            dirty.write_text("active-restore\n", encoding="utf-8")
            wrapper = root / "limine-snapper-sync"
            wrapper.write_text((REPO / "configs/bin/nox-limine-snapper-restore").read_text(encoding="utf-8"), encoding="utf-8")
            wrapper.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "NOX_SYNC_BIN": str(real_sync),
                    "NOX_INTEGRITY_HELPER": str(fake_integ),
                    "NOX_RESTORE_LOCKFILE": str(restore_lock),
                    "NOX_DIRTY_MARKER": str(dirty),
                    "NOX_ALLOW_NONROOT_TEST": "1",
                }
            )
            res = subprocess.run(["bash", str(wrapper)], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 1)
            self.assertFalse(marker.exists(), "Watcher/sync wrapper must NOT repair while foreground restore lock is active")

    def test_limine_snapper_restore_forwards_live_tty_input_through_reboot_prompt(self) -> None:
        import pty as pty_mod
        import select as select_mod
        import time as time_mod

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snap_list = root / "limine-snapper-list"
            snap_list.write_text(
                "#!/usr/bin/env bash\n"
                "echo ' 8 │ 2026-11-20 17:41:58 │ nox-final-pre'\n",
                encoding="utf-8",
            )
            snap_list.chmod(0o755)

            received_log = root / "received.txt"
            fake_restore = root / "real-restore"
            fake_restore.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.write('Choice: '); sys.stdout.flush()\n"
                "c = sys.stdin.readline().strip()\n"
                "sys.stdout.write('Description for backup subvolume: '); sys.stdout.flush()\n"
                "d = sys.stdin.readline().strip()\n"
                "sys.stdout.write('Restore complete. Reboot now? [Y/n]: '); sys.stdout.flush()\n"
                "a = sys.stdin.readline().strip()\n"
                f"open('{received_log}', 'w').write(f'{{c}}|{{d}}|{{a}}')\n"
                "raise SystemExit(0 if (c == '8' and d == 'bkp' and a == 'n') else 9)\n",
                encoding="utf-8",
            )
            fake_restore.chmod(0o755)

            fake_integ = root / "integ"
            fake_integ.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_integ.chmod(0o755)

            wrapper = root / "limine-snapper-restore"
            wrapper.write_text((REPO / "configs/bin/nox-limine-snapper-restore").read_text(encoding="utf-8"), encoding="utf-8")
            wrapper.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "NOX_LIST_BIN": str(snap_list),
                    "NOX_RESTORE_BIN": str(fake_restore),
                    "NOX_INTEGRITY_HELPER": str(fake_integ),
                    "NOX_DIRTY_MARKER": str(root / "dirty"),
                    "NOX_ALLOW_NONROOT_TEST": "1",
                }
            )

            master_fd, slave_fd = pty_mod.openpty()
            proc = subprocess.Popen(
                ["bash", str(wrapper)],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
            os.close(slave_fd)
            buf = b""
            step = 0
            deadline = time_mod.monotonic() + 15
            try:
                while time_mod.monotonic() < deadline:
                    r, _, _ = select_mod.select([master_fd], [], [], 0.2)
                    if master_fd in r:
                        try:
                            chunk = os.read(master_fd, 4096)
                        except OSError:
                            break
                        if not chunk:
                            break
                        buf = (buf + chunk)[-2048:]
                        if step == 0 and b"Informe o ID do snapshot para restaurar" in buf:
                            os.write(master_fd, b"8\n")
                            step = 1
                            buf = b""
                        elif step == 1 and b"Descricao opcional do backup" in buf:
                            os.write(master_fd, b"bkp\n")
                            step = 2
                            buf = b""
                        elif step == 2 and b"Confirmar restauracao do snapshot ID" in buf:
                            os.write(master_fd, b"s\n")
                            step = 3
                            buf = b""
                        elif step == 3 and b"Reboot now? [Y/n]:" in buf:
                            os.write(master_fd, b"n\r")
                            step = 4
                            buf = b""
                    if proc.poll() is not None and step == 4:
                        break
            finally:
                os.close(master_fd)
            self.assertEqual(proc.wait(timeout=5), 0)
            self.assertEqual(received_log.read_text(encoding="utf-8"), "8|bkp|n")

    def test_fallback_hook_serializes_concurrent_runs_with_isolated_tempdir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            esp = root / "boot"
            (esp / "EFI/BOOT").mkdir(parents=True)
            (esp / "EFI/limine").mkdir(parents=True)
            conf = esp / "limine.conf"
            conf.write_text("timeout: 5\n", encoding="utf-8")
            src = root / "SRC_BOOTX64.EFI"
            src.write_bytes(b"VALID-PE-BINARY")
            lim_def = root / "default-limine"
            lim_def.write_text("ENABLE_ENROLL_LIMINE_CONFIG=yes\n", encoding="utf-8")
            lock_f = root / "fb.lock"

            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "limine").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (bin_dir / "limine").chmod(0o755)
            mock_sbctl = bin_dir / "sbctl"
            mock_sbctl.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$1\" in\n"
                "  setup) echo '{\"installed\": true}' ;;\n"
                "  sign) sleep 0.1; test -s \"$2\" ;;\n"
                "  verify) echo \"✓ $2 is signed\" ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            mock_sbctl.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "ESP_PATH": str(esp),
                    "NOX_LIMINE_SRC_EFI": str(src),
                    "NOX_LIMINE_DEFAULT": str(lim_def),
                    "NOX_FALLBACK_LOCK": str(lock_f),
                    "NOX_SBCTL_BIN": str(mock_sbctl),
                    "NOX_FORCE_EFI_HOOK": "1",
                    "NOX_PRESERVE_DIRTY_MARKER": "1",
                }
            )
            p1 = subprocess.Popen(["bash", str(REPO / "configs/boot-hooks/95-nox-sbctl-fallback")], env=env)
            p2 = subprocess.Popen(["bash", str(REPO / "configs/boot-hooks/95-nox-sbctl-fallback")], env=env)
            self.assertEqual(p1.wait(timeout=15), 0)
            self.assertEqual(p2.wait(timeout=15), 0)
            self.assertTrue((esp / "EFI/BOOT/BOOTX64.EFI").is_file())
            self.assertEqual(list((esp / "EFI/BOOT").glob(".nox-sbctl-fb.*")), [])

    def test_list_candidate_disks_fails_closed_on_lsblk_errors_and_bad_json(self) -> None:
        from unittest import mock

        mod = TestTrustChainHardening._load_nox_install()
        with mock.patch.object(mod.subprocess, "run", return_value=subprocess.CompletedProcess(["lsblk"], 1, "", "io error")):
            with self.assertRaises(RuntimeError):
                mod.list_candidate_disks()
        with mock.patch.object(mod.subprocess, "run", return_value=subprocess.CompletedProcess(["lsblk"], 0, "{bad-json", "")):
            with self.assertRaises(RuntimeError):
                mod.list_candidate_disks()

    def test_a4_nox_limine_integrity_state_matrix_and_verify_mode(self) -> None:
        import hashlib

        def b2(data: bytes) -> str:
            return hashlib.blake2b(data, digest_size=64).hexdigest()

        script = REPO / "configs/bin/nox-limine-integrity"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            esp = root / "boot"
            (esp / "EFI/limine").mkdir(parents=True)
            (esp / "EFI/BOOT").mkdir(parents=True)
            conf = esp / "limine.conf"
            lim_efi = esp / "EFI/limine/limine_x64.efi"
            fb_efi = esp / "EFI/BOOT/BOOTX64.EFI"
            dirty = root / "dirty.marker"
            lim_def = root / "default-limine"
            state_signed = root / "signed.flag"

            bin_dir = root / "bin"
            bin_dir.mkdir()
            mock_norm = bin_dir / "norm"
            mock_norm.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "from pathlib import Path\n"
                "f = Path(sys.argv[sys.argv.index('--file') + 1])\n"
                "f.write_text('/+Arch Linux\\n  //Project Nox\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            mock_norm.chmod(0o755)

            mock_enr = bin_dir / "limine-enroll-config"
            mock_enr.write_text(
                "#!/usr/bin/env python3\n"
                "import hashlib, os\n"
                "from pathlib import Path\n"
                "esp = Path(os.environ['ESP_PATH'])\n"
                "h = hashlib.blake2b((esp / 'limine.conf').read_bytes(), digest_size=64).hexdigest()\n"
                "(esp / 'EFI/limine/limine_x64.efi').write_bytes(b'EFI-' + h.encode())\n",
                encoding="utf-8",
            )
            mock_enr.chmod(0o755)

            mock_fb = bin_dir / "fallback"
            mock_fb.write_text(
                "#!/usr/bin/env python3\n"
                "import hashlib, os\n"
                "from pathlib import Path\n"
                "esp = Path(os.environ['ESP_PATH'])\n"
                "h = hashlib.blake2b((esp / 'limine.conf').read_bytes(), digest_size=64).hexdigest()\n"
                "(esp / 'EFI/BOOT/BOOTX64.EFI').write_bytes(b'FB-' + h.encode())\n",
                encoding="utf-8",
            )
            mock_fb.chmod(0o755)

            mock_sbctl = bin_dir / "sbctl"
            mock_sbctl.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$1\" in\n"
                "  setup) echo '{\"installed\": true}' ;;\n"
                f"  verify) [[ -f '{state_signed}' ]] && echo \"✓ $2 is signed\" || exit 1 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            mock_sbctl.chmod(0o755)

            mock_verify = bin_dir / "verify"
            mock_verify.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            mock_verify.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "ESP_PATH": str(esp),
                    "NOX_DIRTY_MARKER": str(dirty),
                    "NOX_LIMINE_DEFAULT": str(lim_def),
                    "NOX_NORMALIZE_BIN": str(mock_norm),
                    "NOX_LIMINE_ENROLL_BIN": "limine-enroll-config",
                    "NOX_FALLBACK_HOOK": str(mock_fb),
                    "NOX_VERIFY_BIN": str(mock_verify),
                    "NOX_SBCTL_BIN": str(mock_sbctl),
                    "NOX_ALLOW_NONROOT_TEST": "1",
                }
            )

            def run_integ(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["bash", str(script), *args],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            # 1. Unknown flag must exit 2
            self.assertEqual(run_integ("--bogus-flag").returncode, 2)

            # 2. Clean pre-boot uninitialized state (no limine.conf, no .dirty, no Limine artifacts) -> 0
            self.assertEqual(run_integ("--repair-if-dirty").returncode, 0)

            # 3. Missing limine.conf WITH .dirty marker -> fail closed AND preserve .dirty marker!
            dirty.write_text("dirty\n", encoding="utf-8")
            r_dirty_missing = run_integ("--repair-if-dirty")
            self.assertNotEqual(r_dirty_missing.returncode, 0)
            self.assertTrue(dirty.exists(), ".dirty marker must be preserved when limine.conf is missing")

            # 4. Missing limine.conf under explicit --force/--repair/--verify/--check -> fail closed
            dirty.unlink()
            for flag in ("--force", "--repair", "--verify", "--check"):
                res_m = run_integ(flag)
                self.assertNotEqual(res_m.returncode, 0, f"{flag} must fail when {conf} missing")

            # 5. Missing limine.conf when Limine artifacts already exist -> fail closed even under --repair-if-dirty
            lim_def.write_text("ENABLE_ENROLL_LIMINE_CONFIG=yes\n", encoding="utf-8")
            self.assertNotEqual(run_integ("--repair-if-dirty").returncode, 0)

            # 6. Converged config + --verify / --check matrix (including dirty marker preservation)
            conf.write_text("/+Arch Linux\n  //Project Nox\n", encoding="utf-8")
            h_ok = b2(conf.read_bytes())
            lim_efi.write_bytes(b"EFI-" + h_ok.encode())
            fb_efi.write_bytes(b"FB-" + h_ok.encode())
            state_signed.write_text("1", encoding="utf-8")

            self.assertEqual(run_integ("--verify").returncode, 0)
            self.assertEqual(run_integ("--check").returncode, 0)

            dirty.write_text("pending\n", encoding="utf-8")
            r_v_dirty = run_integ("--verify")
            self.assertNotEqual(r_v_dirty.returncode, 0)
            self.assertTrue(dirty.exists(), "--verify must not delete .dirty marker")

            # Cleanup via --repair-if-dirty succeeds and clears .dirty
            r_fix = run_integ("--repair-if-dirty")
            self.assertEqual(r_fix.returncode, 0, r_fix.stderr)
            self.assertFalse(dirty.exists())
            self.assertEqual(run_integ("--verify").returncode, 0)


class TestDocumentationAndPublicationContracts(unittest.TestCase):
    V100_FROZEN = {
        "nox-install.py": "fce3f9a83e2b8c13666cf583f143096de37b8dd312e59dd8c6af4acbabb82f10",
        "user_configuration.json": "6754aefcdfb659e1abdfb5036c158a609d1672f945186a1e692edeab2e104e4c",
        "payload": "08fbf62a2325b2a3a4b30a3d7ec4b986bc17f412970ba25f83839624444d6fd9",
    }
    V101_FROZEN = {
        "nox-install.py": "fa6c2a3b1ee86cd60976857555326bf6a63c341914e9c061f557a62a74e03b47",
        "user_configuration.json": "9cb32121cb9a87b54b7c07749a92d3b8cb6cffcf6e4dadc502f3fa9a3da3a867",
        "payload": "52008f9c454c8b39c91d6e51b3546f6a76546f021c3c6a0850dc7a55d5bf92b2",
    }

    def test_relative_markdown_links_and_images_resolve(self) -> None:
        import re

        md_files = [REPO / "README.md", *sorted((REPO / "docs").glob("*.md"))]
        link_re = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
        img_re = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']')
        for md in md_files:
            text = md.read_text(encoding="utf-8")
            targets = link_re.findall(text) + img_re.findall(text)
            for raw in targets:
                if raw.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                rel = raw.split("#", 1)[0]
                if not rel:
                    continue
                target_path = (md.parent / rel).resolve()
                self.assertTrue(
                    target_path.exists(),
                    f"Broken relative link {raw!r} in {md.relative_to(REPO)} -> {target_path}",
                )

    def test_evidence_manifest_complete_tracked_and_valid(self) -> None:
        import hashlib

        ev_dir = REPO / "docs/evidence/v1.0.1"
        manifest = ev_dir / "MANIFEST.sha256"
        lines = [line.strip() for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 22)
        listed_paths: set[str] = set()
        for line in lines:
            digest, rel = line.split(None, 1)
            rel = rel.lstrip("*./")
            fpath = ev_dir / rel
            self.assertTrue(fpath.is_file(), f"Missing manifest file: {fpath}")
            actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
            self.assertEqual(actual, digest, f"SHA-256 mismatch for {fpath}")
            listed_paths.add(f"docs/evidence/v1.0.1/{rel}")

            ign = subprocess.run(
                ["git", "-C", str(REPO), "check-ignore", f"docs/evidence/v1.0.1/{rel}"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(ign.returncode, 0, f"Evidence file is gitignored: docs/evidence/v1.0.1/{rel}")

        # Verify all evidence references inside FINAL-AUDIT-REPORT.md exist
        report = (REPO / "docs/FINAL-AUDIT-REPORT.md").read_text(encoding="utf-8")
        for expected in (
            "evidence/v1.0.1/MANIFEST.sha256",
            "acceptB-clean-durable-rollback.log",
            "acceptA-clean-verify.log",
            "acceptB-clean-verify.log",
            "acceptB-clean-secureboot-enroll.log",
            "acceptB-clean-secureboot-active-and-snapper.log",
            "acceptB-clean-snap-pac-and-cleanup.log",
            "acceptA-v101-final-verify.log",
            "acceptB-v101-final-stage5-and-restore.log",
            "acceptB-v101-final-reboot1.log",
            "acceptB-v101-final-reboot2.log",
        ):
            self.assertIn(expected, report)

    def test_readme_and_docs_install_commands_use_published_v100_and_verified_hashes(self) -> None:
        import re

        readme = (REPO / "README.md").read_text(encoding="utf-8")
        install_doc = (REPO / "docs/INSTALLATION.md").read_text(encoding="utf-8")
        audit_doc = (REPO / "docs/FINAL-AUDIT-REPORT.md").read_text(encoding="utf-8")
        comp_doc = (REPO / "docs/INSTALLED-COMPONENTS.md").read_text(encoding="utf-8")
        rel_manifest = json.loads((REPO / "manifests/release.json").read_text(encoding="utf-8"))

        # README must expose only ONE bash install block, targeting published Latest (v1.0.1 until v1.0.2 is published) on Awerkori/nox-arch-install
        bash_blocks = re.findall(r"```bash\n(.*?)```", readme, flags=re.S)
        self.assertEqual(len(bash_blocks), 1, "README.md must contain exactly ONE primary live bash install block")
        cmd = bash_blocks[0]
        self.assertIn("https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/nox-install.py", cmd)
        self.assertIn(self.V101_FROZEN["nox-install.py"], cmd)
        self.assertIn("https://github.com/Awerkori/nox-arch-install/releases/download/v1.0.1/user_configuration.json", cmd)
        self.assertIn(self.V101_FROZEN["user_configuration.json"], cmd)
        self.assertIn("mktemp -d", cmd)
        self.assertIn("trap ", cmd)
        self.assertIn("umask 022", cmd)
        self.assertNotIn("/tmp/nox-install.py", cmd)
        self.assertNotIn("/tmp/nox-cfg.json", cmd)
        self.assertNotIn("releases/download/v1.0.0", cmd)
        self.assertNotIn("Awerkori/arch-install", cmd)
        self.assertNotIn("/refs/heads/main", cmd)
        self.assertNotIn("/main/", cmd)

        # Destructive warning before command, dynamic CI badge, and accurate interactive steps (4 numbered + final confirmation)
        self.assertLess(readme.index("AVISO DESTRUTIVO"), readme.index("```bash"))
        self.assertIn("actions/workflows/ci.yml/badge.svg", readme)
        self.assertIn("Awerkori/nox-arch-install/actions/workflows/ci.yml", readme)
        self.assertNotIn("5 etapas", readme.lower())
        self.assertNotIn("5 confirmações", readme.lower())
        self.assertNotIn("5 etapas", install_doc.lower())
        self.assertNotIn("rollback automático", readme.lower())
        self.assertIn("mktemp -d", install_doc)

        # Must advertise published v1.0.1 as Latest while preserving v1.0.0 history and documenting v1.0.2
        self.assertIn("v1.0.1", readme)
        self.assertIn("v1.0.0", readme)
        self.assertIn("v1.0.2", readme)
        self.assertIn("discord-game-presence", readme)
        self.assertNotIn("Awerkori/arch-install", install_doc)
        self.assertNotIn("Awerkori/arch-install", comp_doc)

        # INSTALLATION.md must carry v1.0.1 active hashes + v1.0.0 frozen reference
        self.assertIn(self.V101_FROZEN["nox-install.py"], install_doc)
        self.assertIn(self.V101_FROZEN["user_configuration.json"], install_doc)
        self.assertIn(self.V101_FROZEN["payload"], install_doc)
        self.assertIn(self.V100_FROZEN["nox-install.py"], install_doc)
        self.assertIn(self.V100_FROZEN["user_configuration.json"], install_doc)
        self.assertIn(self.V100_FROZEN["payload"], install_doc)
        self.assertNotIn("32c074ca3819d261a774b92ee4c7359411b963d5", install_doc)
        self.assertNotIn("daeea6fb99a7c76b071036c97d041e95783b54c5f46bfa2360ac4c1c173688e0", install_doc)
        self.assertNotIn("raw.githubusercontent.com/Awerkori/arch-install/main/", install_doc)
        self.assertNotIn("raw.githubusercontent.com/Awerkori/nox-arch-install/main/", install_doc)

        # FINAL-AUDIT-REPORT.md and INSTALLED-COMPONENTS.md must stay synchronized with current manifests/release.json and preserve v1.0.0/v1.0.1
        self.assertIn(rel_manifest["payload_sha256"], audit_doc)
        self.assertIn(rel_manifest["config_commit"], audit_doc)
        self.assertIn(rel_manifest["bootstrap_commit"], audit_doc)
        self.assertIn(rel_manifest["launcher_commit"], audit_doc)
        self.assertIn(rel_manifest["launcher_sha256"], audit_doc)
        self.assertIn(rel_manifest["bootstrap_sha256"], audit_doc)
        self.assertIn(rel_manifest["config_sha256"], audit_doc)
        self.assertIn(self.V100_FROZEN["payload"], comp_doc)
        self.assertIn(self.V101_FROZEN["payload"], comp_doc)
        self.assertIn("discord-game-presence", comp_doc)

    def test_docs_and_evidence_have_no_secrets_private_paths_or_unverified_user_anecdotes(self) -> None:
        import re

        secret_re = re.compile(
            r"noxdev123|[g]hp_|[g]ho_|[g]ithub_pat_|AKIA[0-9A-Z]{16}|BEGIN (?:OPENSSH|RSA|EC|DSA|PGP)? ?PRIVATE KEY|/home/awerkori|52:54:00"
        )
        paths_to_check = [
            REPO / "README.md",
            *sorted((REPO / "docs").glob("*.md")),
            *sorted((REPO / "docs/evidence/v1.0.1/logs").glob("*")),
        ]
        ev102_logs = REPO / "docs/evidence/v1.0.2/logs"
        if ev102_logs.is_dir():
            paths_to_check.extend(sorted(ev102_logs.glob("*")))
        for p in paths_to_check:
            txt = p.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(secret_re.search(txt), f"Sensitive or private string found in {p.relative_to(REPO)}")

        msi_doc = (REPO / "docs/SECURE-BOOT-MSI.md").read_text(encoding="utf-8")
        self.assertNotIn("Relatos reais de usuários", msi_doc)
        self.assertNotIn("--custom-only", msi_doc)
        self.assertIn("--no-microsoft", msi_doc)
        self.assertIn("Cenários técnicos documentados", msi_doc)


class TestAurAndDiscordGamePresenceContracts(unittest.TestCase):
    def test_aur_helper_parses_checkdepends_and_imports_validpgpkeys_fail_closed(self) -> None:
        aur_sh = (REPO / "scripts/lib/aur.sh").read_text(encoding="utf-8")
        self.assertIn("${checkdepends[@]}", aur_sh)
        self.assertIn("${validpgpkeys[@]}", aur_sh)
        self.assertNotIn("--nocheck", aur_sh)
        self.assertIn("--skipchecksums|--skippgpcheck", aur_sh)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkgdir = root / "pkg"
            pkgdir.mkdir()
            (pkgdir / "PKGBUILD").write_text(
                "pkgname=discord-game-presence\n"
                "pkgver=0.2\n"
                "pkgrel=1\n"
                "depends=('python')\n"
                "makedepends=('git>=2.40')\n"
                "checkdepends=('python-pytest')\n"
                "validpgpkeys=('7E12BC1FF3B6EDB2CD8053EB981A2B2A3BBF5514')\n",
                encoding="utf-8",
            )
            deps_out = subprocess.run(
                [
                    "python3",
                    "-c",
                    "import subprocess, re\n"
                    "out = subprocess.check_output(['bash', '-c', 'source PKGBUILD; printf \"%s\\n\" \"${depends[@]}\" \"${makedepends[@]}\" \"${checkdepends[@]}\"'], text=True)\n"
                    "print(','.join(re.split(r'[<>=:]', l.strip())[0] for l in out.splitlines() if l.strip()))\n",
                ],
                cwd=pkgdir,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(deps_out.stdout.strip(), "python,git,python-pytest")

            mock_bin = root / "bin"
            mock_bin.mkdir()
            gpg_log = root / "gpg.log"
            mock_gpg = mock_bin / "gpg"
            mock_gpg.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"echo \"GNUPGHOME=${{GNUPGHOME:-}} $*\" >> '{gpg_log}'\n"
                "if [[ \"$*\" == *'--list-keys'* ]]; then\n"
                "  [[ -f \"${GNUPGHOME}/imported\" ]] && exit 0\n"
                "  exit 2\n"
                "fi\n"
                "if [[ \"$*\" == *'--recv-keys'* ]]; then\n"
                "  if [[ \"${MOCK_GPG_FAIL:-0}\" == '1' ]]; then\n"
                "    exit 2\n"
                "  fi\n"
                "  touch \"${GNUPGHOME}/imported\"\n"
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            mock_gpg.chmod(0o755)

            gnupghome_ok = root / "aur-home/.gnupg"
            env_ok = os.environ.copy()
            env_ok["PATH"] = f"{mock_bin}:{env_ok.get('PATH', '')}"
            res_ok = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"set -euo pipefail; source '{REPO}/scripts/lib/common.sh'; source '{REPO}/scripts/lib/aur.sh'; "
                    f"nox_aur_import_pgp_keys '{gnupghome_ok}' '7E12BC1FF3B6EDB2CD8053EB981A2B2A3BBF5514'",
                ],
                env=env_ok,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_ok.returncode, 0, res_ok.stderr)
            self.assertEqual(gnupghome_ok.stat().st_mode & 0o777, 0o700)
            self.assertIn("--recv-keys 7E12BC1FF3B6EDB2CD8053EB981A2B2A3BBF5514", gpg_log.read_text(encoding="utf-8"))

            gnupghome_fail = root / "aur-home-fail/.gnupg"
            env_fail = env_ok.copy()
            env_fail["MOCK_GPG_FAIL"] = "1"
            res_fail = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"set -euo pipefail; source '{REPO}/scripts/lib/common.sh'; source '{REPO}/scripts/lib/aur.sh'; "
                    f"nox_aur_import_pgp_keys '{gnupghome_fail}' '7E12BC1FF3B6EDB2CD8053EB981A2B2A3BBF5514'",
                ],
                env=env_fail,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res_fail.returncode, 0)
            self.assertIn("Falha ao importar chave PGP", res_fail.stderr)

    def test_discord_game_presence_desktop_and_validation_contracts(self) -> None:
        desktop_sh = (REPO / "scripts/50-desktop.sh").read_text(encoding="utf-8")
        val_sh = (REPO / "scripts/80-validation.sh").read_text(encoding="utf-8")

        self.assertIn('nox_aur_install_pkg "discord-game-presence"', desktop_sh)
        self.assertIn("nox_enable_user_systemd_unit /usr/lib/systemd/user/discord-game-presence.service", desktop_sh)
        self.assertIn(" steam discord ", desktop_sh)
        self.assertNotIn("systemctl --global", desktop_sh)
        self.assertNotIn("enable-linger", desktop_sh)
        self.assertNotIn("systemctl --user", desktop_sh)

        self.assertIn("pacman -Q discord-game-presence", val_sh)
        self.assertIn("/usr/bin/discord-game-presence --version", val_sh)
        self.assertIn("/etc/skel/.config/systemd/user/default.target.wants/discord-game-presence.service", val_sh)
        self.assertIn("test ! -e /etc/systemd/user/default.target.wants/discord-game-presence.service", val_sh)
        self.assertIn(" steam discord ", val_sh)

    def test_nox_enable_user_systemd_unit_per_user_isolation_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            unit_src = root / "discord-game-presence.service"
            unit_src.write_text(
                "[Unit]\nDescription=Discord Game Presence\n\n[Service]\nExecStart=/usr/bin/discord-game-presence\n\n[Install]\nWantedBy=default.target\n",
                encoding="utf-8",
            )
            skel = root / "skel"
            alice_home = root / "home/alice"
            bob_home = root / "home/bob"
            skel.mkdir()
            alice_home.mkdir(parents=True)
            bob_home.mkdir(parents=True)

            script = (
                "set -euo pipefail\n"
                f"source '{REPO}/scripts/lib/common.sh'\n"
                "nox_list_human_users() {\n"
                f"  printf 'alice:%s:%s:%s:/usr/bin/bash\\n' \"$(id -u)\" \"$(id -g)\" '{alice_home}'\n"
                f"  printf 'bob:%s:%s:%s:/usr/bin/bash\\n' \"$(id -u)\" \"$(id -g)\" '{bob_home}'\n"
                "}\n"
                f"nox_enable_user_systemd_unit '{unit_src}' '{skel}'\n"
                f"nox_enable_user_systemd_unit '{unit_src}' '{skel}'\n"
            )
            res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0, res.stderr)

            for base in (skel, alice_home, bob_home):
                link = base / ".config/systemd/user/default.target.wants/discord-game-presence.service"
                self.assertTrue(link.is_symlink(), f"Missing symlink: {link}")
                self.assertEqual(Path(os.readlink(link)), unit_src)

            bad_unit = root / "bad.service"
            bad_unit.write_text("[Unit]\nDescription=Bad\n[Install]\nWantedBy=../evil.target\n", encoding="utf-8")
            bad_res = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"set -euo pipefail; source '{REPO}/scripts/lib/common.sh'; nox_enable_user_systemd_unit '{bad_unit}' '{skel}'",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad_res.returncode, 0)
            self.assertIn("WantedBy invalido", bad_res.stderr)





