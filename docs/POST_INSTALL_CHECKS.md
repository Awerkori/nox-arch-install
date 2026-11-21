# Verificações Pós-Instalação em Hardware Físico (PENDENTE-HARDWARE)

Os itens abaixo dependem de periféricos e GPU físicos (Tipo C) e não podem ser homologados integralmente em VM virtualizada (`virtio-gpu` / rede NAT):

1. **GPU AMD (`amdgpu`) e Mesa/RADV/Vulkan:**
   ```bash
   lspci -nnk | grep -A3 -E 'VGA|Display|3D'
   vulkaninfo --summary 2>/dev/null || glxinfo -B 2>/dev/null
   journalctl -k -b --no-pager | grep -Ei 'amdgpu|drm.*error'
   ```

2. **Monitores Samsung Odyssey G5 (`DP-1`, 1440p@165) e AOC (`HDMI-A-1`, 1080p@100 vertical):**
   ```bash
   umbriel outputs
   umbriel workspaces
   # Conferir posicionamento sem sobreposição nem buracos e XWayland primary:
   xrandr --query | grep -E ' connected( primary)? '
   ```

3. **Teclado Aula F75 (`us`/`intl` com dead keys):**
   - Testar no Kitty e no Luciole: `' + e -> é`, `' + c -> ç`, `~ + a -> ã`, `^ + e -> ê`, `" + space -> "`.
   - Diagnosticar duplicação apenas se ocorrer: `sudo libinput debug-events`.

4. **Headset HAVIT Fuxi H3 (`FuxiH3`):**
   ```bash
   pactl list cards | grep -A15 -i fuxi
   amixer -c FuxiH3 contents | grep -A2 "PCM Playback Volume"
   paplay /usr/share/sounds/alsa/Front_Left.wav
   paplay /usr/share/sounds/alsa/Front_Right.wav
   ```

5. **Microfone analógico P2 e infraestrutura de áudio (sem HushMic):**
   ```bash
   wpctl status
   pactl list sources short
   pactl get-default-source
   ```
   Confirmar que a fonte padrão selecionada pertence ao dispositivo físico de entrada (e NÃO a `Monitor of`, `HDMI` ou dispositivo virtual inexistente).

6. **Caixa de som Bluetooth:**
   ```bash
   systemctl status bluetooth --no-pager
   bluetoothctl
   # parear/conectar dispositivo e validar sink A2DP:
   pactl list sinks short
   ```

7. **Wi-Fi Intel AX210 (`iwlwifi` + `iwd` + regdomain BR):**
   ```bash
   nmtui   # ou nmcli device wifi connect "<SSID>" password "<SENHA>"
   iw reg get
   systemctl --failed
   ethtool -k wlan0 | grep -E 'tcp-segmentation-offload|generic-segmentation-offload|generic-receive-offload'
   ```
   (Se desejar desativar power save na conexão específica: `nmcli connection modify "<CONEXAO>" 802-11-wireless.powersave 2`.)

8. **Ajuste fino de alinhamento vertical do monitor AOC (opcional):**
   - Posição padrão configurada: `[2560, -350]` em `~/.config/umbriel/outputs.toml`.
   - Para ajustar manualmente sem perder na próxima atualização/login, edite `~/.config/umbriel/outputs.local.toml`:
     ```toml
     [output."HDMI-A-1"]
     position = [2560, -350]
     ```
     e aplique com `umbriel msg config-reload`.

9. **Ativação final do Secure Boot no hardware físico (etapa mínima na BIOS):**
   Durante a instalação, `sbctl`, chaves privadas únicas (`/var/lib/sbctl/keys/`), assinatura do Limine (`limine_x64.efi` e `BOOTX64.EFI`) e enrollment criptográfico do `limine.conf` (`ENABLE_ENROLL_LIMINE_CONFIG=yes`) já foram automatizados. Para ativar o enforcement na UEFI:
   1. Reinicie para o setup UEFI/BIOS (`systemctl reboot --firmware-setup`).
   2. Em **Security / Boot -> Secure Boot**, coloque em **Custom / Setup Mode** (limpando/deletando chaves PK/KEK/db existentes) e **salve**.
   3. Inicie o Arch Linux normalmente e execute (requer confirmação explícita; inclui certificados Microsoft por padrão para preservar Option ROM da GPU Radeon):
      ```bash
      sudo nox-secureboot-enroll
      ```
   4. Reinicie na BIOS, ative **Secure Boot = Enabled** e confirme após o boot:
      ```bash
      sudo sbctl status
      sudo nox-secureboot-verify --require-active
      sudo /usr/local/libexec/nox/nox-limine-integrity --verify
      ```

10. **Topgrade, ProtonPlus, GE-Proton e DWProton (`PENDENTE-HARDWARE` após instalar Steam/launcher):**
    - `Proton-CachyOS SLR` já vem pré-instalado em `/usr/share/steam/compatibilitytools.d/proton-cachyos-slr/` e é atualizado via `topgrade` (`paru`).
    - Sem `Steam`/`Heroic`/`Lutris`/`Bottles` instalados, o `ProtonPlus` não possui diretório-alvo ativo para baixar `GE-Proton` ou `DWProton` durante a instalação offline. Depois de instalar seu launcher de jogos:
      1. Abra o **ProtonPlus** pelo launcher do Noctalia (visível na listagem principal) ou execute `protonplus install steam ge-proton` e `protonplus install steam dwproton`.
      2. Execute `topgrade` como usuário normal no Kitty para validar atualização conjunta (`paru` + `protonplus update all`) e criação/consolidação automática de `Ponto de Segurança` e `Estado Atualizado`.

11. **Discord Game Presence após instalar Discord e um jogo (`PENDENTE-HARDWARE`):**
    - O daemon `discord-game-presence.service` já inicia ativo por padrão no login gráfico (`systemctl --user is-active discord-game-presence.service`).
    - Após instalar o cliente **Discord** e executar um jogo em execução real com áudio/GPU físicos, valide que `discord-game-presence --scan` detecta o processo do jogo e exibe o Rich Presence no perfil do Discord sem configuração manual.
