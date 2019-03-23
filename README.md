# GPU Passthrough on Clevo P650HP6

## Introduction

This is a detailed breakdown of the steps I took and decisions I made in an effort to achieve GPU passthrough in a Windows 10 guest on a Metabox Prime P650HP (no NVidia GSync), which is essentially a Clevo P650HP6.

I have successfully passed through the discrete GPU to a Windows 10 guest, but I have not yet been able eliminate the `Code 43` error after installation of the NVidia graphics driver.

I have tested the same virtual environment with a Manjaro Linux live guest, and have confirmed that 3D acceleration works when using the NVidia driver in this case. Tests with `__GL_SYNC_TO_VBLANK=0 glxgears` have yielded frame rates in excess of 9K consistently with this guest.

## Setup

### Host

* Operating system: Manjaro Linux
    * Manjaro because based on Arch Linux; maintains its own copy of the Arch repositories.
    * Tried installing Antergos Linux for its easy install on `zfs` option, but encountered bugs in the installer.
* Boot loader: `systemd-boot`
    * Tried `grub2`, but installation failed with Manjaro installer, causing boot failure; could have been my `lvm` setup or the Windows EFI partition.
* File systems: `ntfs`, `lvm` + `ext4`
    * Chose `ntfs` over `exfat` on HDD.
    * Seriously considered `zfs` on SSD for flexibility, but has limited support in the linux kernel.
    * Considered `xfs` on SSD for good performance with VM images.
* Partitioning scheme: 1TB media/downloads, 128GB linux, 128GB VMs, 128GB backups
* Desktop environment: `cinnamon` + `lightdm`
    * Considered `kde` and `gnome`, but they are bloated and their apps already integrate with `cinnamon` very well.
    * Considered `i3` but takes a lot of initial setup and configuration.
* Networking: `vde2`
* Utilities: `zsh`, `neovim`, `gauke`

### GPU Passthrough

* On first boot, encountered blank screen when `lightdm` tried to start with the laptop in `mshybrid` mode. Did a [reboot to runlevel][] 5 then applied a solution outlined in [Switchable / Optimus section of the Clevo P650RS][].
* [PCI passthrough via OVMF][]
    * [Enabling IOMMU][]
    * [Ensuring that the groups are valid][]
    * [Isolating the GPU with vfio-pci loaded as a module][]
* [Optimus laptop dGPU passthrough guide][]
    * [Bumblebee setup guide][] steps 1-2, 6-7, 9-11
    * [System and environment setup][] step 2
    * [Prepare your script][] step 1
* [Run Windows VM in user mode][]
* [Permissions for non-root gpu passthrough][]
* [Bringing up tap0 and vde2 at boot for use with virtual machines][]

[reboot to runlevel]: https://wiki.archlinux.org/index.php/SysVinit#Runlevel_invocation
[switchable / optimus section of the clevo p650rs]: https://wiki.archlinux.org/index.php/Clevo_P650RS#Switchable_/_Optimus
[pci passthrough via ovmf]: https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF
[enabling iommu]: https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF#Enabling_IOMMU
[ensuring that the groups are valid]: https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF#Ensuring_that_the_groups_are_valid
[isolating the gpu with vfio-pci loaded as a module]: https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF#With_vfio-pci_loaded_as_a_module
[optimus laptop dGPU passthrough guide]:
https://gist.github.com/Misairu-G/616f7b2756c488148b7309addc940b28
[bumblebee setup guide]: https://gist.github.com/Misairu-G/616f7b2756c488148b7309addc940b28#bumblebee-setup-guide
[system and environment setup]: https://gist.github.com/Misairu-G/616f7b2756c488148b7309addc940b28#system--environment-setup
[prepare your script]: https://gist.github.com/Misairu-G/616f7b2756c488148b7309addc940b28#prepare-your-script
[run windows vm in user mode]: heiko-sieger.info/running-windows-10-on-linux-using-kvm-with-vga-passthrough/#Part_13_Run_Windows_VM_in_user_mode_non-root
[permissions for non-root gpu passthrough]: www.evonide.com/non-root-gpu-passthrough-setup/#Permissions_for_non-root_GPU_passthrough
[bringing up tap0 and vde2 at boot for use with virtual machines]: bbs.archlinux.org/viewtopic.php?id=120739

## Installing a Windows 10 Guest

* Make sure all required `systemd` services and `udev` rules are enabled.
* Change directory to the project folder.
    ```text
    $ cd ~/virt
    ```
* Download the latest NVidia graphics driver for Windows into the `drivers/windows/` directory.
* Download the latest `virtio` drivers into the `resources/` directory.
* Copy the EFI vars file into the `resources/` directory.
    ```text
    $ cp /usr/share/ovmf/x64/OVMF_VARS.fd resources/
    ```
* Generate a disk image containing the NVidia graphics driver for the QEMU boot script to use.
    ```text
    $ ./gen-win-drivers-iso.sh
    ```
* Bind the discrete GPU to `vfio`.
    ```text
    $ #How to do this without `root` privileges? \
    > sudo ./bind-nvidia-gpu.sh
    ```
* Run the QEMU boot script.
    ```text
    $ ./boot-windows.sh install
    ```
  You should see the Windows installer screen in a `spice` window after waiting a few seconds. 
* Click through the installer prompt and install the `virtio` drivers from a CD-ROM drive attached to the guest.
* Continue the installation process and wait for the Windows desktop to load. Device Manager should show your graphics card passed through.
* Install the NVidia graphics drivers using the installer, which should be in a CD-ROM drive attached to the guest.
* The installer will always let you install the drivers, but it may error out after awhile before finishing the installation. Rebooting the system and trying again a few times usually results in a successful install.
* Reboot the Windows guest. Check Device Manager, and behold the error `Code 43`.

## What I've Tried

* Successfully passed through the GPU to a linux guest. Achieved similar results to a Reddit user who also got [Code 43 on Clevo P650RS][] in a Windows guest.
* Set `x-pci-sub-device-id=0x65a2` and reinstalled the graphics drivers. Installer installs the NVidia audio driver in addition to the other components.
* Used a script on the `mshybrid` rom to [update EFI GOP][] and booted with this rom. Had to set up RDP in the guest because HDMI output did not work.
* Used the [NVidia vBIOS VFIO patcher][] script to remove headers from rom. The rom has no headers so this didn't do anything.
* Attempted to [enable message signal-based interrupts][] in the guest. MSI turned out to be already enabled so nothing happened.
* Made sure to use the proper PCIE addresses in a post on the [current state of optimus muxless laptop GPU passthrough][].

[code 43 on clevo p650rs]: www.reddit.com/r/VFIO/comments/7lqz4c/clevo_p650rs_code_43_optimus_mux_gtx_1070/
[update efi gop]: www.win-raid.com/t892f16-AMD-and-Nvidia-GOP-update-No-requests-DIY.html
[nvidia vbios vfio patcher]: github.com/Matoking/NVIDIA-vBIOS-VFIO-Patcher
[enable message signal-based interrupts]: forums.guru3d.com/threads/windows-line-based-vs-message-signaled-based-interrupts.378044/
[current state of optimus muxless laptop gpu passthrough]: www.reddit.com/r/VFIO/comments/8gv60l/current_state_of_optimus_muxless_laptop_gpu/

## What I Haven't Tried

* Use roms from successful passthrough attempts on Clevo laptops.
* Build a custom `ovmf` package as detailed in this [hacky solution for Windows Guest on a muxless laptop][].
* [Pass through an NVidia GPU as primary or only gpu][].

[hacky solution for windows guest on a muxless laptop]: github.com/jscinoz/optimus-vfio-docs/issues/2
[pass through an NVIDIA GPU as primary or only gpu]: forums.unraid.net/topic/51230-video-guidehow-to-pass-through-an-nvidia-gpu-as-primary-or-only-gpu-in-unraid/

## System Configuration

### Hardware Specifications

* Processor: Intel i7-7700HQ
* Discrete Graphics: NVIDIA GeForce GTX1060 6GB Mobile
* Integrated Graphics: Intel HD Graphics 630
* RAM: 12GB DDR4 2400MHz (8GB + 4GB)
* SSD: Crucial MX300 525GB SATA3 M.2
* HDD: 1TB 7200RPM
* WiFi: Intel 8265 AC Dual Band Wireless/BT 4.2
* Display: 15.6" 1920x1080 60Hz
* Display output ports: 1x HDMI, 2x mini DisplayPort

### Drive Partitioning

```text
$ lsblk -o NAME,LABEL,SIZE,TYPE,FSTYPE,MOUNTPOINT
NAME            LABEL   SIZE TYPE FSTYPE      MOUNTPOINT
sda                   489.1G disk
├─sda1                  512M part vfat        /boot
└─sda2                488.6G part LVM2_member
  ├─LINUX-LINUX         128G lvm  ext4        /
  └─LINUX-VM            128G lvm
sdb                   931.5G disk
└─sdb1          Data  931.5G part ntfs
```

### Base System

* Bootloader: `systemd-boot` (`systemd 239.6-2.2`)
* Kernel: `linux 4.20.1-1-MANJARO x86_64`
* Operating system: `Manjaro 18.0.2 Illyria`
* Desktop manager: `lightdm 1:1.28.0-1`
* Desktop environment: `cinnamon 4.0.9-1.2`
* Shell: `zsh 5.6.2-1` + `manjaro-zsh-config 0.11-1`

### Virtual Environment

* VM monitor: `qemu 3.1.0-1` + `ovmf 1:r24601.6861765935-1`
* Networking: `vde2 2.3.2-11`
* Host graphics: `xf86-video-intel 1:2.99.917+855+g746ab3bb-1` + `bumblebee 3.2.1-22`
* Guest graphics: `linux420-nvidia 1:415.25-1`

### IOMMU Groups

```text
$ ./list-iommu-groups.sh
IOMMU Group 0 00:00.0 Host bridge [0600]: Intel Corporation Xeon E3-1200 v6/7th Gen Core Processor Host Bridge/DRAM Registers [8086:5910] (rev 05)
IOMMU Group 10 6e:00.0 Network controller [0280]: Intel Corporation Wireless 8265 / 8275 [8086:24fd] (rev 78)
IOMMU Group 1 00:01.0 PCI bridge [0604]: Intel Corporation Xeon E3-1200 v5/E3-1500 v5/6th Gen Core Processor PCIe Controller (x16) [8086:1901] (rev 05)
IOMMU Group 1 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GP106M [GeForce GTX 1060 Mobile] [10de:1c20] (rev ff)
IOMMU Group 2 00:14.0 USB controller [0c03]: Intel Corporation 100 Series/C230 Series Chipset Family USB 3.0 xHCI Controller [8086:a12f] (rev 31)
IOMMU Group 2 00:14.2 Signal processing controller [1180]: Intel Corporation 100 Series/C230 Series Chipset Family Thermal Subsystem [8086:a131] (rev 31)
IOMMU Group 3 00:16.0 Communication controller [0780]: Intel Corporation 100 Series/C230 Series Chipset Family MEI Controller #1 [8086:a13a] (rev 31)
IOMMU Group 4 00:17.0 SATA controller [0106]: Intel Corporation HM170/QM170 Chipset SATA Controller [AHCI Mode] [8086:a103] (rev 31)
IOMMU Group 5 00:1c.0 PCI bridge [0604]: Intel Corporation 100 Series/C230 Series Chipset Family PCI Express Root Port #1 [8086:a110] (rev f1)
IOMMU Group 6 00:1c.4 PCI bridge [0604]: Intel Corporation 100 Series/C230 Series Chipset Family PCI Express Root Port #5 [8086:a114] (rev f1)
IOMMU Group 7 00:1c.6 PCI bridge [0604]: Intel Corporation 100 Series/C230 Series Chipset Family PCI Express Root Port #7 [8086:a116] (rev f1)
IOMMU Group 8 00:1f.0 ISA bridge [0601]: Intel Corporation HM175 Chipset LPC/eSPI Controller [8086:a152] (rev 31)
IOMMU Group 8 00:1f.2 Memory controller [0580]: Intel Corporation 100 Series/C230 Series Chipset Family Power Management Controller [8086:a121] (rev 31)
IOMMU Group 8 00:1f.3 Audio device [0403]: Intel Corporation CM238 HD Audio Controller [8086:a171] (rev 31)
IOMMU Group 8 00:1f.4 SMBus [0c05]: Intel Corporation 100 Series/C230 Series Chipset Family SMBus [8086:a123] (rev 31)
IOMMU Group 9 6d:00.0 Unassigned class [ff00]: Realtek Semiconductor Co., Ltd. RTL8411B PCI Express Card Reader [10ec:5287] (rev 01)
IOMMU Group 9 6d:00.1 Ethernet controller [0200]: Realtek Semiconductor Co., Ltd. RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller [10ec:8168] (rev 12)
```

### Discrete GPU Info

`lspci` shows the following output when `mshybrid` mode is enabled in the BIOS. When it is switched to `discrete` mode, the GPU subsystem ID changes to `1558:65a2`.

```text
$ lspci -nnk -s 01:00.0
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GP106M [GeForce GTX 1060 Mobile] [10de:1c20] (rev a1)
  Subsystem: CLEVO/KAPOK Computer GP106M [GeForce GTX 1060 Mobile] [1558:65a1]
  Kernel driver in use: vfio-pci
  Kernel modules: nouveau, nvidia_drm, nvidia
```

2 vbios ROMs were saved using `TechPowerUp GPU-z v2.16.0` on a fully updated installation of Windows 10, prior to installation of linux. `GP106-mshybrid.rom` was saved with `mshybrid` mode enabled in the laptop's BIOS, and `GP106-discrete.rom` was saved in `discrete` mode. A third ROM `GP106-mshybrid_updGOP.rom` was generated using the GOPUpd python script to enable UEFI in the `mshybrid` vbios.

```text
$ ./rom-parser/rom-parser clevo-p650hp6/GP106-mshybrid.rom
Valid ROM signature found @0h, PCIR offset 1a0h
  PCIR: type 0 (x86 PC-AT), vendor: 10de, device: 1c20, class: 030000
  PCIR: revision 3, vendor revision: 1
  Last image
$ ./rom-parser/rom-parser clevo-p650hp6/GP106-discrete.rom
Valid ROM signature found @0h, PCIR offset 1a0h
  PCIR: type 0 (x86 PC-AT), vendor: 10de, device: 1c20, class: 030000
  PCIR: revision 3, vendor revision: 1
Valid ROM signature found @28200h, PCIR offset 1ch
  PCIR: type 3 (EFI), vendor: 10de, device: 1c20, class: 030000
  PCIR: revision 3, vendor revision: 0
    EFI: Signature Valid, Subsystem: Boot, Machine: X64
  Last image
$ ./rom-parser/rom-parser clevo-p650hp6/GP106-mshybrid_updGOP.rom
Valid ROM signature found @0h, PCIR offset 1a0h
  PCIR: type 0 (x86 PC-AT), vendor: 10de, device: 1c20, class: 030000
  PCIR: revision 3, vendor revision: 1
Valid ROM signature found @1a000h, PCIR offset 1ch
  PCIR: type 3 (EFI), vendor: 10de, device: 1c20, class: 030000
  PCIR: revision 3, vendor revision: 0
    EFI: Signature Valid, Subsystem: Boot, Machine: X64
  Last image
```

### Boot Entries

```text
$ cat /boot/loader/entries/manjaro-4.20-x86_64.conf
title	Manjaro Linux 4.20-x86_64
linux	/vmlinuz-4.20-x86_64
initrd	/intel-ucode.img
initrd	/initramfs-4.20-x86_64.img
options	root=/dev/mapper/LINUX-LINUX rw acpi_osi=! acpi_osi=Linux acpi_osi=\"Windows 2015\" pcie_port_pm=off i915.enable_gvt=1 intel_iommu=on,igfx_off iommu=pt kvm.ignore_msrs=1 isolcpus=1,5,2,6
```

### Kernel Modules

```text
$ cat /etc/mkinitcpio.conf | grep -E '^MODULES='
MODULES=(vfio vfio_iommu_type1 vfio_pci vfio_virqfd)
```

```text
$ cat /etc/modprobe.d/bbswitch.conf
options bbswitch load_state=0 unload_state=1
```

```text
$ cat /etc/modprobe.d/kvm.conf
options kvm report_ignored_msrs=0
```

### X11 Config

```text
$ cat /etc/X11/xorg.conf.d/20-intel-graphics.conf
Section "Device"
	Identifier	"GPU0"
	Driver		"intel"
	BusID		"PCI:0:2:0"
EndSection
```

### UDev Rules

```text
$ cat /etc/udev/rules.d/10-qemu-kvm.rules
SUBSYSTEM=="vfio", OWNER="root", GROUP="kvm"
ENV{DM_NAME}=="LINUX-VM", OWNER="root", GROUP="kvm"
```

### Systemd Services

```text
$ cat /etc/systemd/system/qemu-dhcp.service
[Unit]
Description=DHCP For QEMU Guests
After=qemu-vde.service

[Service]
Type=forking
ExecStart=/usr/bin/slirpvde --daemon --dhcp
Restart=on-abort

[Install]
WantedBy=multi-user.target
```

```text
$ cat /etc/systemd/system/qemu-lan.service
[Unit]
Description=LAN For QEMU Guests
After=qemu-vde.service

[Service]
Type=oneshot
ExecStart=/usr/bin/ip addr add 10.0.2.1/24 dev vmnet0
ExecStart=/usr/bin/ip link set dev vmnet0 up

[Install]
WantedBy=multi-user.target
```

```text
cat /etc/systemd/system/qemu-vde.service
[Unit]
Description=VDE For QEMU Guests
After=network.target

[Service]
Type=forking
ExecStart=/usr/bin/vde_switch -tap vmnet0 -daemon -mod 660 -group kvm
Restart=on-abort

[Install]
WantedBy=multi-user.target
```