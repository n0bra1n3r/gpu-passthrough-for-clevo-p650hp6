#! /bin/sh

OPT="-enable-kvm"
OPT="$OPT -name Linux"
OPT="$OPT -machine type=q35,accel=kvm"
OPT="$OPT -cpu host,kvm=off,hv_vapic,hv_relaxed,hv_spinlocks=0x1fff,hv_time,hv_vendor_id=0123456789ab"
OPT="$OPT -smp 4,sockets=1,cores=2,threads=2"
OPT="$OPT -m 8G"
OPT="$OPT -rtc clock=host,base=localtime"
## COM
OPT="$OPT -serial none"
OPT="$OPT -parallel none"
## UEFI
OPT="$OPT -drive if=pflash,format=raw,readonly=on,file=/usr/share/ovmf/x64/OVMF_CODE.fd"
OPT="$OPT -drive if=pflash,format=raw,file=resources/OVMF_VARS.fd"
## CDROM
OPT="$OPT -drive file=$HOME/img/archlinux-2019.01.01-x86_64.iso,index=1,media=cdrom"
OPT="$OPT -drive file=$HOME/img/manjaro-cinnamon-18.0-stable-x86_64.iso,index=2,media=cdrom"
## Output
OPT="$OPT -device qxl,bus=pcie.0,addr=1c.4,id=video.2"
OPT="$OPT -spice port=5902,addr=127.0.0.1,disable-ticketing"
OPT="$OPT -vga qxl -nographic"
## Input
OPT="$OPT -usb"
OPT="$OPT -device usb-tablet"
## Network
OPT="$OPT -net nic,macaddr=52:54:00:00:EE:03 -net vde"
## GPU Passthrough
OPT="$OPT -device ioh3420,bus=pcie.0,addr=1c.0,multifunction=on,port=1,chassis=1,id=root.1"
OPT="$OPT -device vfio-pci,host=01:00.0,bus=root.1,addr=00.0,multifunction=on,x-pci-sub-device-id=0x65a2,x-pci-sub-vendor-id=0x1558,romfile=roms/clevo-p650hp6/GP106-discrete.rom"

taskset 0xCC qemu-system-x86_64 $OPT
