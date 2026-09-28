# srv1: Resizable BAR + P2P-patched open module (operator runbook)

Goal: give srv1's two RTX 3060s peer access, then append a with-P2P
measurement to this envelope with step
`tools/runs/campaigns/srv1-multi-gpu/19-p2p.sh` (artifact `p2p.tsv`). The
step compares against `link.tsv`, `nccl.tsv`, `vknobs.tsv` and `lknobs.tsv`.

Every step marked **[APPROVAL An]** changes srv1 and waits for the owner's
explicit yes. Steps with no mark only read. XMP stays on the whole time:
never "Load UEFI Defaults" in the BIOS, because that drops XMP and
`ram_mt_s=3600` in hosts.json would then be wrong.

```
 BIOS: Above 4G + ReBAR, CSM off ──reboot 1──► BAR1 = 16 GiB, P2P still CNS
                                                   │  (optional: 1-link --suffix rebar)
 iommu=pt + patched open module ──reboot 2──► topo -p2p w = OK, peer = True
                                                   │
                                   19-p2p.sh (refuses unless P2P is live)
```

## 0. What srv1 is today (read 2026-09-27, read-only)

| item | value |
|---|---|
| OS / kernel | Ubuntu 26.04 LTS, `7.0.0-34-generic` (headers for -31 and -34 installed) |
| board / BIOS | ASRock Z390 Phantom Gaming 7, AMI `P1.30C` (01/04/2023), UEFI boot (`/sys/firmware/efi` exists) |
| Secure Boot | disabled ("Platform is in Setup Mode"), so an unsigned module loads |
| module | proprietary: `modinfo nvidia` license `NVIDIA`, `/lib/modules/7.0.0-34-generic/updates/dkms/nvidia.ko.zst`, 580.178.04 |
| DKMS | `nvidia/580.178.04` installed for 7.0.0-31 and 7.0.0-34 (package `nvidia-dkms-580`) |
| userspace | `nvidia-driver-580` / `libnvidia-compute-580` 580.178.04-0ubuntu0.26.04.1, GSP firmware `/lib/firmware/nvidia/580.178.04/gsp_ga10x.bin` present (the open module needs it) |
| modprobe.d | `nvidia NVreg_PreserveVideoMemoryAllocations=1 NVreg_TemporaryFilePath=/var`, `nvidia_drm modeset=1` |
| cmdline | `pcie_aspm=off crashkernel=...`: no iommu word |
| IOMMU | DMAR on, every group `DMA-FQ` (translated); root ports 00:01.0, 00:01.1 and both cards share group 1 |
| ACS | no ACS capability on 00:01.0 / 00:01.1 (Intel client PEG ports) |
| BARs | BAR1 256 MiB on both cards at 0xa0000000 / 0x80000000; bridge prefetch windows `[32-bit]`: Above 4G Decoding is off |
| ReBAR capability | both cards: `Physical Resizable BAR`, BAR 1 supported 64 MB .. 16 GB, current 256 MB |
| topology | `GPU0<->GPU1 = PHB`; both cards on CPU root ports, x8/x8 gen3, no switch |
| P2P | `topo -p2p r/w = CNS`, `can_device_access_peer = False` (link.tsv) |
| initramfs | read as "holds no nvidia module (`lsinitramfs` count 0)" — WRONG, read unprivileged; it held the DKMS nvidia modules. See §7 |

Does the root-port layout permit P2P? The two cards hang off two functions
of the CPU's PEG root complex with no switch and no ACS in the way, so a peer
TLP is routed inside the CPU. Intel client root complexes forward peer
WRITES; peer READS are reported broken or slow on some (tinygrad
open-gpu-kernel-modules issue #30, Z690). NCCL's P2P transport writes. vLLM's
custom all-reduce reads its peer's buffer, which is why 19-p2p runs vLLM's
own peer test (`VLLM_SKIP_P2P_CHECK=0`) before the cell that trusts the
driver. Plausible, unproven: the step's refusal decides.

## 1. The module source (exact version match)

The kernel module version must equal the userspace driver version, 580.178.04.
No published p2p branch is at 580.178.04 (tinygrad stops at 570.148.08-p2p;
aikitoria has 580.76.05 / 580.82.09 / 580.95.05 / 580.105.08-p2p, then
590+). The patch is small (9 files, +71 / -35) and forward-ports cleanly:

- base: `NVIDIA/open-gpu-kernel-modules` tag `580.178.04`
  (annotated tag object `96262fd76df2a096985ac1ca14a7519f9ea4df89`, commit
  `c8e699821c23e4335bf23330a54a23d15cfb95e9`)
- patch: the three code commits of `aikitoria/open-gpu-kernel-modules`
  branch `580.105.08-p2p`, pinned by SHA, README and install.sh excluded:
  - `782b594c13a393ca180dcc5bee7e3cfcfd8e8cfc` Simplified p2p mod based on the one by geohot
  - `616bdf332126285ec307bf3d46585a1f95ecfaa9` Enable p2p in the new settings in 575
  - `510a7720de1e7fa3ef374a721b48f700b23895b9` 5090 support by nimlgen
- checked 2026-09-27: `git apply --check` is clean on the 580.178.04 files
  (line offsets only, no fuzz), and the resulting diff hashes
  `git diff | grep -v '^index' | sha256sum` =
  `90f8a51ee8bacfbd1d1d6cbfeb1f7a8e02744c1a5719adb273a1392c328a6be6`.
  Not built yet: the build in section 4 is the first compile.

What the patch does: forces BAR1 P2P (`p2pOverride`, a BAR1 P2P mapping path
in `kern_bus_gp100.c`, the UVM/RM ops that go with it) and drops the
`NVreg_EnableResizableBar == 0` guard in `nv-pci.c`, so the driver may resize
BAR1 itself.

Fallback if the forward port fails to build: aikitoria `595.71.05-p2p` or
`610.57.04-p2p` with the matching userspace driver. That moves `driver=` in
hosts.json (gate 2 refuses until redeclared), changes the userspace every
earlier row ran on (the before/after is no longer driver-for-driver), and is
a new approval.

## 2. Preconditions (read-only)

1. The live measurement queue on srv1 has finished and nothing runs:
   `ssh srv1 'docker ps --format "{{.Names}}"'` prints nothing.
2. Record the current BIOS page values (photo): Above 4G Decoding, Re-Size BAR
   Support (if shown), CSM, XMP profile. Rollback puts these back.
3. Snapshot to srv1:`~/p2p-before/` (files in the operator's home only):

```bash
ssh srv1 'set -e; d=~/p2p-before; mkdir -p $d
  cp /etc/default/grub $d/grub
  cp -a /lib/modules/$(uname -r)/updates/dkms $d/dkms-ko
  modinfo nvidia > $d/modinfo.txt; dkms status > $d/dkms.txt
  cat /proc/cmdline > $d/cmdline.txt
  nvidia-smi -q > $d/nvidia-smi-q.txt; nvidia-smi topo -m > $d/topo.txt
  sudo lspci -vvv > $d/lspci-vvv.txt
  dpkg -l | grep -E "nvidia|linux-(image|headers)" > $d/dpkg.txt'
```

## 3. BIOS: Above 4G Decoding, Re-Size BAR, CSM off — **[APPROVAL A1]** (reboot 1)

ASRock UEFI (F2 / Del at POST, F6 toggles Advanced Mode):

1. `Advanced > Chipset Configuration > Above 4G Decoding` = **Enabled**
2. `Advanced > Chipset Configuration > Re-Size BAR Support` = **Enabled**
   (shown only after Above 4G is enabled, and only on a BIOS carrying
   Clever Access Memory; the `C` in `P1.30C` suggests this one does, not
   verified: ASRock's site refuses scripted reads)
3. `Boot > CSM (Compatibility Support Module) > CSM` = **Disabled**
   (srv1 already boots UEFI, so the OS entry survives this)
4. Leave `OC Tweaker > DRAM Configuration > Load XMP Setting` as it is. Do not
   load defaults. F10 save and exit.

If `Re-Size BAR Support` is not in the menu: stop here. Flashing another BIOS
is its own approval (it resets every setting, XMP included). A weaker route
exists with Above 4G on: the driver or the operator resizes BAR1 from Linux
(`resource1_resize`, bit 14 = 16 GB) with the card unbound, which needs a
free 64-bit window, possibly `pci=realloc`. That is **[APPROVAL A1b]**.

After boot, read-only checks with the stock proprietary module still loaded:

```bash
ssh srv1 'nvidia-smi -q | grep -A1 "BAR1 Memory Usage"'          # Total : 16384 MiB on both
ssh srv1 'sudo lspci -vvv -s 01:00.0 | grep -A3 "Resizable BAR"'  # BAR 1: current size: 16GB
ssh srv1 'sudo lspci -vvv -s 00:01.0 | grep "Prefetchable memory"' # a [64-bit] window above 4G
ssh srv1 'nvidia-smi topo -p2p w'                                  # still CNS: expected
```

Optional, isolates what ReBAR alone does (P2P still off):
`uv run python -m mcgyvr.serving.run --host srv1 --campaign srv1-multi-gpu --date 2026-09-27 --suffix rebar --step tools/runs/campaigns/srv1-multi-gpu/1-link.sh --model /models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf --ctx-per-slot 2048`
**[APPROVAL A2]** (a door run).

## 4. Build the patched module on srv1 — **[APPROVAL A3]** (CPU load only; nothing installed)

The compiler that built the running kernel is gcc 15.2.0; srv1 has it.

The build also needs `xz` (modeset shader blobs) and `g++` (nvidia-modeset's C++
DisplayPort library): `ssh srv1 'command -v xz g++ gcc-15'` before starting.
A compile check against `linux-headers-7.0.0-34-generic` 7.0.0-34.34 with
gcc 15.2.0-16ubuntu1 built all five modules clean (version 580.178.04,
Dual MIT/GPL); its objtool warnings match the unpatched tag's build.

```bash
ssh srv1 'set -e
  mkdir -p ~/src && cd ~/src
  git clone --depth 1 --branch 580.178.04 https://github.com/NVIDIA/open-gpu-kernel-modules.git ogkm-580.178.04-p2p
  cd ogkm-580.178.04-p2p
  test "$(git rev-parse 580.178.04)" = 96262fd76df2a096985ac1ca14a7519f9ea4df89   # the annotated tag object
  test "$(git rev-parse HEAD)" = c8e699821c23e4335bf23330a54a23d15cfb95e9         # the commit it points to
  for c in 782b594c13a393ca180dcc5bee7e3cfcfd8e8cfc 616bdf332126285ec307bf3d46585a1f95ecfaa9 510a7720de1e7fa3ef374a721b48f700b23895b9; do
    curl -fsSL "https://github.com/aikitoria/open-gpu-kernel-modules/commit/$c.patch" -o /tmp/$c.patch
    git apply --exclude=README.md --exclude=install.sh /tmp/$c.patch
  done
  git diff --stat                                   # 9 files, 71 insertions, 35 deletions
  git diff | grep -v "^index" | sha256sum           # 90f8a51ee8ba...a6be6
  make modules -j$(nproc) SYSSRC=/lib/modules/$(uname -r)/build
  ls kernel-open/*.ko'                              # nvidia nvidia-uvm nvidia-modeset nvidia-drm nvidia-peermem
```

## 5. IOMMU passthrough — **[APPROVAL A4]**

The patch writes to the peer's physical BAR address; a translated IOMMU
domain (`DMA-FQ`, today) drops those writes. Passthrough keeps DMAR but maps
the cards identity. Cost: devices are no longer isolated from each other's
DMA (the fork's README: "very dangerous if you run untrusted software or
devices").

```bash
ssh srv1 'sudo sed -i "s/^GRUB_CMDLINE_LINUX_DEFAULT=\"pcie_aspm=off\"$/GRUB_CMDLINE_LINUX_DEFAULT=\"pcie_aspm=off intel_iommu=on iommu=pt\"/" /etc/default/grub
  grep ^GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub && sudo update-grub'
```

## 6. Hold the kernel and driver packages — **[APPROVAL A5]**

A kernel or driver upgrade rebuilds the proprietary DKMS module for the new
kernel and the patched module is gone on the next boot (19-p2p then refuses).

```bash
ssh srv1 'sudo apt-mark hold linux-image-generic linux-headers-generic linux-generic \
  nvidia-driver-580 nvidia-dkms-580 nvidia-kernel-common-580 nvidia-kernel-source-580 \
  nvidia-utils-580 libnvidia-compute-580 nvidia-firmware-580-580.178.04'
```

## 7. Swap the module — **[APPROVAL A6]** (reboot 2)

depmod searches `updates` before `kernel` (`/etc/depmod.d/ubuntu.conf`), so the
DKMS module must leave the running kernel or it keeps winning. The other
kernel (7.0.0-31) keeps its DKMS build as a boot-menu fallback.

```bash
ssh srv1 'set -e; K=$(uname -r)
  sudo dkms remove -m nvidia -v 580.178.04 -k $K
  cd ~/src/ogkm-580.178.04-p2p
  sudo make modules_install -j$(nproc) SYSSRC=/lib/modules/$K/build   # -> /lib/modules/$K/kernel/drivers/video/
  sudo depmod -a $K
  modinfo -F license nvidia; modinfo -F filename nvidia'   # Dual MIT/GPL, .../kernel/drivers/video/nvidia.ko.zst
ssh srv1 'K=$(uname -r)
  sudo cp -a /boot/initrd.img-$K ~/p2p-before/initrd.img-$K.bak
  sudo update-initramfs -u -k $K
  sudo lsinitramfs /boot/initrd.img-$K | grep -E "nvidia[^/]*\.ko"'   # no nvidia.ko / updates/dkms
ssh srv1 'sudo reboot'
```

The initramfs step was missing on 2026-09-27 and cost a reboot: Ubuntu's
`framebuffer-nvidia` initramfs hook copies `updates/dkms/nvidia*` into the
boot image, which loads before the root disk, so the stock module from the
old initramfs came up (srcversion 647E1BB5…, license 'NVIDIA') although the
disk held only the patched one. `lsinitramfs` must run under sudo — the image
is mode 0600, and unprivileged it lists nothing, which read as "no nvidia".

## 8. Verify (read-only)

```bash
ssh srv1 'cat /proc/cmdline'                               # ... intel_iommu=on iommu=pt
ssh srv1 'cat /proc/driver/nvidia/version'                 # NVIDIA UNIX Open Kernel Module ... 580.178.04
ssh srv1 'nvidia-smi --query-gpu=driver_version --format=csv,noheader'   # 580.178.04 twice
ssh srv1 'nvidia-smi -q | grep -A1 "BAR1 Memory Usage"'    # Total : 16384 MiB
ssh srv1 'nvidia-smi topo -p2p r; nvidia-smi topo -p2p w'  # GPU0->GPU1 OK (w required; r filed)
ssh srv1 'cat /sys/bus/pci/devices/0000:01:00.0/iommu_group/type'   # identity
```

The transport and peer check are 19-p2p's own gate (it runs
`can_device_access_peer` both ways and a verified copy in the vLLM image, and
reads NCCL's `via P2P/...` with `NCCL_DEBUG=INFO`). An operator look outside
the door, not evidence:

```bash
ssh srv1 'docker run --rm --runtime=nvidia --gpus all --ipc=host -e NCCL_DEBUG=INFO \
  --entrypoint python3 vllm/vllm-openai:v0.26.0 -c "
import torch, torch.distributed as d, torch.multiprocessing as mp
def w(r):
    torch.cuda.set_device(r); d.init_process_group(\"nccl\", init_method=\"file:///tmp/rdzv\", rank=r, world_size=2)
    t = torch.ones(4096, device=r); d.all_reduce(t); torch.cuda.synchronize(); print(r, t[0].item())
print(torch.cuda.can_device_access_peer(0, 1), torch.cuda.can_device_access_peer(1, 0))
mp.spawn(w, nprocs=2)" 2>&1 | grep -E "True|False|via|^[01] "'
# expect: True True; "Channel 00/0 : 0[0] -> 1[1] via P2P/CUMEM..."; "0 2.0" and "1 2.0"
```

The door's gate 2 compares srv1 with hosts.json. `driver=` does not move; if
`gpu_reserve_mib` moves under the open module the door refuses and
`tools/runs/hosts.json[srv1].rig` is redeclared: **[APPROVAL A7]**.

## 9. Measure — **[APPROVAL A8]**

`--date 2026-09-27` files into this envelope (the door defaults to today, UTC):

```bash
uv run python -m mcgyvr.serving.run --host srv1 --campaign srv1-multi-gpu --date 2026-09-27 \
  --step tools/runs/campaigns/srv1-multi-gpu/19-p2p.sh \
  --model /models/dense/Qwen2.5-Coder-7B-Instruct-IQ4_XS.gguf --ctx-per-slot 2048
```

It exits 2 with no rows unless `topo -p2p w` is OK, peer access is True both
ways with a verified copy, and BAR1 is at least VRAM on both cards.

## 10. Rollback

Each step reverses on its own; do them in reverse order. Checked by reading
the commands against the state in section 0 and the snapshot in `~/p2p-before/`.

Module (undoes 7) — **[APPROVAL R1]**:

```bash
ssh srv1 'set -e; K=$(uname -r)
  sudo rm -f /lib/modules/$K/kernel/drivers/video/nvidia.ko* /lib/modules/$K/kernel/drivers/video/nvidia-uvm.ko* \
             /lib/modules/$K/kernel/drivers/video/nvidia-modeset.ko* /lib/modules/$K/kernel/drivers/video/nvidia-drm.ko* \
             /lib/modules/$K/kernel/drivers/video/nvidia-peermem.ko*
  sudo dkms install -m nvidia -v 580.178.04 -k $K      # rebuilds from /usr/src/nvidia-580.178.04
  sudo depmod -a $K
  modinfo -F license nvidia; dkms status'              # NVIDIA; installed for both kernels
ssh srv1 'K=$(uname -r); sudo update-initramfs -u -k $K'   # or restore ~/p2p-before/initrd.img-$K.bak
ssh srv1 'sudo reboot'
```

If `dkms install` fails, copy the saved build back instead:
`sudo mkdir -p /lib/modules/$K/updates/dkms && sudo cp -a ~/p2p-before/dkms-ko/. /lib/modules/$K/updates/dkms/ && sudo depmod -a $K`.
If the box does not come up with a display or `nvidia-smi` fails after
reboot 2, pick `7.0.0-31-generic` under "Advanced options" in GRUB: its
proprietary DKMS module is untouched.

IOMMU (undoes 5) — **[APPROVAL R2]**:
`ssh srv1 'sudo cp ~/p2p-before/grub /etc/default/grub && sudo update-grub'`, then reboot.

Packages (undoes 6) — **[APPROVAL R3]**: `ssh srv1 'sudo apt-mark unhold $(apt-mark showhold)'`
(today nothing is held, so this returns srv1 to that).

BIOS (undoes 3) — **[APPROVAL R4]**: Re-Size BAR Support Disabled, Above 4G
Decoding Disabled, CSM back to the recorded value, XMP untouched; verify
`nvidia-smi -q` BAR1 Total 256 MiB.

hosts.json (undoes A7): revert the redeclaration if one was made.

Check after rollback: `modinfo -F license nvidia` = `NVIDIA`, BAR1 256 MiB,
`/proc/cmdline` without `iommu=pt`, `nvidia-smi topo -p2p w` = CNS, and the
door's gate 2 green against hosts.json.
