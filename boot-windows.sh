#! /bin/sh

OPT="-enable-kvm"
OPT="$OPT -name Windows"
OPT="$OPT -machine type=q35,accel=kvm"
OPT="$OPT -cpu host,kvm=off,-hypervisor,hv_relaxed,hv_spinlocks=0x1fff,hv_time,hv_vendor_id=0123456789ab"
OPT="$OPT -smp 6,sockets=1,cores=3,threads=2"
OPT="$OPT -m 8G"
OPT="$OPT -rtc clock=host,base=localtime"
## Bus
OPT="$OPT -device pci-bridge,addr=12.0,chassis_nr=2,id=head.2"
OPT="$OPT -usb"
## COM
OPT="$OPT -serial none"
OPT="$OPT -parallel none"
## UEFI
OPT="$OPT -drive if=pflash,format=raw,readonly=on,file=/usr/share/ovmf/x64/OVMF_CODE.fd"
OPT="$OPT -drive if=pflash,format=raw,file=resources/WIN_OVMF_VARS.fd"
## Storage
OPT="$OPT -drive file=/dev/mapper/LINUX-VM,format=raw,cache=none,if=virtio"
CDROM=1
OPT="$OPT -drive file=$HOME/img/Windows10_x64.iso,index=$((CDROM++)),media=cdrom"
OPT="$OPT -drive file=resources/virtio-win-0.1.141.iso,index=$((CDROM++)),media=cdrom"
OPT="$OPT -drive file=resources/win-drivers.iso,index=$((CDROM++)),media=cdrom"
if [ "$1" == "test" ]; then
OPT="$OPT -snapshot"
fi
if [ "$1" == "install" ]; then
## Boot
OPT="$OPT -boot once=d,menu=on"
## Input
OPT="$OPT -device virtio-keyboard-pci,bus=head.2,addr=03.0,display=video.2"
OPT="$OPT -device virtio-mouse-pci,bus=head.2,addr=04.0,display=video.2"
## Output
OPT="$OPT -device qxl,bus=pcie.0,addr=1c.4,id=video.2"
OPT="$OPT -spice port=5902,addr=127.0.0.1,disable-ticketing"
OPT="$OPT -vga qxl -nographic"
else
OPT="$OPT -vga none -nographic"
#OPT="$OPT -device ich9-intel-hda -device hda-output"
## GPU Passthrough
OPT="$OPT -device ioh3420,bus=pcie.0,addr=01.0,multifunction=on,chassis=1,id=root.1"
OPT="$OPT -device vfio-pci,host=01:00.0,bus=root.1,addr=00.0,multifunction=on,x-pci-sub-device-id=0x65a1,x-pci-sub-vendor-id=0x1558,romfile=roms/clevo-p650hp6/GP106-discrete.rom"
fi
## Network
OPT="$OPT -net nic,addr=0xa,model=virtio,macaddr=52:54:00:00:EE:03 -net vde"

taskset 0x77 qemu-system-x86_64 $OPT
