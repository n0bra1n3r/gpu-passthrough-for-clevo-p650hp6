#!/usr/bin/env python3

import binascii
import ctypes
import datetime
import os
import re
import struct
import subprocess
import sys

char     = ctypes.c_char
uint8_t  = ctypes.c_ubyte
uint16_t = ctypes.c_ushort
uint32_t = ctypes.c_uint
uint64_t = ctypes.c_uint64
#uint128_t = ctypes.c_uint128
void     = ctypes.c_void_p

try :
	#import colorama
	from colorama import Fore, Back, Style, init

except :
	print("Colorama is not installed! Use \"pip install colorama\" from your Python\Scripts folder.\n")
	sys.exit()

#colorama.init()
init()

class ROM_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                 uint16_t),     # 00 55AA <- AA55, 564E <- 4E56
		("InitializationSize",        uint8_t),      # 02
		("InitEntryPoint",            uint8_t * 3),  # 03
		("Reserved",                  uint8_t * 18), # 06
		("PcirOffset",                uint16_t),     # 18
		("PnpOffset",                 uint16_t),     # 1A
		# 1C
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def rom_print(self, offset):
		
		init_size = self.InitializationSize * 0x200
		
		jmp_cmd  = self.InitEntryPoint[0]
		jmp_off  = self.InitEntryPoint[2] * 0x100 + self.InitEntryPoint[1]
		jmp_len  = 3
		
		if jmp_cmd == 0xEB :
			init_jmp = "Jump short"
			jmp_off  = self.InitEntryPoint[1]
			jmp_len  = 2
		elif jmp_cmd == 0xE9 :
			init_jmp = "Jump near"
		elif jmp_cmd == 0xEA :
			init_jmp = "Jump far"
		elif jmp_cmd == 0xE8 :
			init_jmp = "Call"
		else :
			init_jmp = "Jumpy McJumpFace"
		
		init_hex   = "%0.2X %-4.2X" % (jmp_cmd, jmp_off)
		init_asm   = "%s 0x%0.2X"  % (init_jmp, jmp_off)
		
		reserv_str  = "".join("%02X" % val for val in self.Reserved)
		#reserv_bin = "".join(val.to_bytes(1, 'big').decode('utf-8', 'ignore') for val in self.Reserved)
		init_abs    = jmp_off + jmp_len + offset + 3 if jmp_cmd else 0
		pci_off_abs = self.PcirOffset + offset if self.PcirOffset else 0
		pnp_off_abs = self.PnpOffset + offset if self.PnpOffset else 0
		
		print("-------------ROM_HEADER-------------\n")
		print("Signature:                          %0.4X"                   % self.Signature)
		print("Initialization Size:                0x%-4.2X  (0x%0.2X)"     % (self.InitializationSize, init_size))
		print("Init Entry Point:                   %s (%s, abs 0x%0.2X)"    % (init_hex, init_asm, init_abs))
		print("Reserved:                           %s"                      % reserv_str) # %s (%s)" % (reserv_str, reserv_bin))
		print("PCIR Offset:                        0x%-4.2X  (abs 0x%0.2X)" % (self.PcirOffset, pci_off_abs))
		print("PnP Offset:                         0x%-4.2X  (abs 0x%0.2X)" % (self.PnpOffset, pnp_off_abs))
		print("\n------------------------------------\n")
	
	def nv_rom_print(self, offset): # For 564E <- 4E56
		
		# Init size is uint16_t
		nv_InitializationSize = self.InitEntryPoint[0] * 0x100 + self.InitializationSize
		init_size             = nv_InitializationSize * 0x200
		
		reserv_str  = "%0.2X%0.2X" % (self.InitEntryPoint[1], self.InitEntryPoint[2])
		reserv_str  += "".join("%02X" % val for val in self.Reserved)
		#reserv_bin = "".join(val.to_bytes(1, 'big').decode('utf-8', 'ignore') for val in self.Reserved)
		pci_off_abs = self.PcirOffset + offset if self.PcirOffset else 0
		
		print("-----------NV_ROM_HEADER------------\n")
		print("Signature:                          %0.4X"                   % self.Signature)
		print("Initialization Size:                0x%-4.2X  (0x%0.2X)"     % (nv_InitializationSize, init_size))
		print("Reserved:                           %s"                      % reserv_str) # %s (%s)" % (reserv_str, reserv_bin))
		print("PCIR Offset:                        0x%-4.2X  (abs 0x%0.2X)" % (self.PcirOffset, pci_off_abs))
		print("\n------------------------------------\n")

class EFI_ROM_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                 uint16_t),     # 00 55AA <- AA55, 77BB <- BB77
		("InitializationSize",        uint16_t),     # 02
		("EfiSignature",              uint32_t),     # 04 0x0EF1
		("EfiSubsystem",              uint16_t),     # 08
		("EfiMachineType",            uint16_t),     # 0A
		("CompressionType",           uint16_t),     # 0C
		("Reserved",                  uint8_t * 8),  # 0E
		("EfiImageHeaderOffset",      uint16_t),     # 16
		("PcirOffset",                uint16_t),     # 18
		("Reserved2",                 uint16_t),     # 1A
		# 1C
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def rom_print(self, offset):
		
		init_size  = self.InitializationSize * 0x200
		
		if self.EfiSubsystem == 10 :
			subsys_str = "EFI application"
		elif self.EfiSubsystem == 11 :
			subsys_str = "EFI Boot Service Driver"
		elif self.EfiSubsystem == 12 :
			subsys_str = "EFI Runtime Driver"
		else :
			subsys_str = "Unknown"
		
		if self.EfiMachineType == 0x8664 :
			code_type = "x64"
		
		elif self.EfiMachineType == 0x014C :
			code_type = "x86" # IA32
		
		elif self.EfiMachineType == 0x0200 :
			code_type = "IA64"
		
		elif self.EfiMachineType == 0x0EBC :
			code_type = "EBC" # EFI Byte Code
		
		elif self.EfiMachineType == 0x01C0 :
			code_type = "ARM"
		
		elif self.EfiMachineType == 0x01C2 :
			code_type = "THUMB" # ARM-THUMB-MIXED
		
		elif self.EfiMachineType == 0x01C4 :
			code_type = "ARMv7"
		
		elif EfiMachineType == 0xAA64 :
			code_type = "ARMv8_x64"
		
		else : # There are many more in the specification, but use only the most common ones.
			code_type = "Unknown"
		
		if self.CompressionType == 1 :
			compress_type = "Compressed"
		elif self.CompressionType == 0 :
			compress_type = "Uncompressed"
		else :
			compress_type = "Unknown"
		
		reserv_str  = "".join("%02X" % val for val in self.Reserved)
		efi_off_abs = self.EfiImageHeaderOffset + offset if self.EfiImageHeaderOffset else 0
		pci_off_abs = self.PcirOffset + offset if self.PcirOffset else 0
		
		print("-----------EFI_ROM_HEADER-----------\n")
		print("Signature:                          %0.4X"               % self.Signature)
		print("Initialization Size:                0x%-4.2X (0x%0.2X)"  % (self.InitializationSize, init_size))
		print("EFI Signature:                      %0.2X"               % self.EfiSignature)
		print("EFI Subsystem:                      0x%-4.2X (%s)"       % (self.EfiSubsystem, subsys_str))
		print("EFI Machine Type:                   0x%-4.4X (%s)"       % (self.EfiMachineType, code_type))
		print("Compression Type:                   0x%-4.2X (%s)"       % (self.CompressionType, compress_type))
		print("Reserved:                           %s"                  % reserv_str)
		print("EFI Image offset:                   0x%-4.2X (abs 0x%0.2X)" % (self.EfiImageHeaderOffset, efi_off_abs))
		print("PCIR Offset:                        0x%-4.2X (abs 0x%0.2X)" % (self.PcirOffset, pci_off_abs))
		print("Reserved:                           %0.2X"               % self.Reserved2)
		print("\n------------------------------------\n")
	
	def nv_rom_print(self, offset): # For 77BB <- BB77
		
		#init_size = self.InitializationSize * 0x200
		
		reserv_str  = "%0.4X%0.8X%0.4X" % (self.InitializationSize, self.EfiSignature, self.EfiSubsystem)
		reserv_str  += "%0.4X%0.4X" % (self.EfiMachineType, self.CompressionType)
		reserv_str  += "".join("%02X" % val for val in self.Reserved)
		reserv_str  += "%0.4X" % self.EfiImageHeaderOffset
		#reserv_bin = "".join(val.to_bytes(1, 'big').decode('utf-8', 'ignore') for val in self.Reserved)
		pci_off_abs = self.PcirOffset + offset if self.PcirOffset else 0
		
		print("----------NV_EFI_ROM_HEADER---------\n")
		print("Signature:                          %0.4X"                   % self.Signature)
		print("Reserved:                           %s"                      % reserv_str) # %s (%s)" % (reserv_str, reserv_bin))
		print("PCIR Offset:                        0x%-4.2X  (abs 0x%0.2X)" % (self.PcirOffset, pci_off_abs))
		print("Reserved:                           %0.2X"                   % self.Reserved2)
		print("\n------------------------------------\n")

class NV_ROM_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                 uint16_t),     # 00 564E <- 4E56
		("InitializationSize",        uint16_t),     # 02
		("Reserved",                  uint8_t * 20), # 04
		("PcirOffset",                uint16_t),     # 18
		# 1A
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def nv_rom_print(self, offset):
		
		init_size = self.InitializationSize * 0x200
		
		reserv_str  = "".join("%02X" % val for val in self.Reserved)
		#reserv_bin = "".join(val.to_bytes(1, 'big').decode('utf-8', 'ignore') for val in self.Reserved)
		pci_off_abs = self.PcirOffset + offset if self.PcirOffset else 0
		
		print("------------NV_ROM_HEADER-----------\n")
		print("Signature:                          %0.4X"                   % self.Signature)
		print("Initialization Size:                0x%-4.2X  (0x%0.2X)"     % (self.InitializationSize, init_size))
		print("Reserved:                           %s"                      % reserv_str) # %s (%s)" % (reserv_str, reserv_bin))
		print("PCIR Offset:                        0x%-4.2X  (abs 0x%0.2X)" % (self.PcirOffset, pci_off_abs))
		print("\n------------------------------------\n")

class NV_EFI_ROM_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                 uint16_t),     # 00 77BB <- BB77
		("Reserved",                  uint8_t * 22), # 02
		("PcirOffset",                uint16_t),     # 18
		("Reserved2",                 uint16_t),     # 1A
		# 1C
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def nv_rom_print(self, offset):
		
		#init_size = self.InitializationSize * 0x200
		
		reserv_str  = "".join("%02X" % val for val in self.Reserved)
		#reserv_bin = "".join(val.to_bytes(1, 'big').decode('utf-8', 'ignore') for val in self.Reserved)
		pci_off_abs = self.PcirOffset + offset if self.PcirOffset else 0
		
		print("----------NV_EFI_ROM_HEADER---------\n")
		print("Signature:                          %0.4X"                   % self.Signature)
		print("Reserved:                           %s"                      % reserv_str) # %s (%s)" % (reserv_str, reserv_bin))
		print("PCIR Offset:                        0x%-4.2X  (abs 0x%0.2X)" % (self.PcirOffset, pci_off_abs))
		print("Reserved:                           %0.2X"                   % self.Reserved2)
		print("\n------------------------------------\n")

class PCIR_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                      char * 4),    # 00 PCIR, NPDS, RGIS
		("VendorId",                       uint16_t),    # 04
		("DeviceId",                       uint16_t),    # 06
		("DeviceListOffset",               uint16_t),    # 08 Reserved in PCI 2.3 and bellow
		("Length",                         uint16_t),    # 0A
		("Revision",                       uint8_t),     # 0C
		("ClassCode",                      uint8_t * 3), # 0D
		("ImageLength",                    uint16_t),    # 10
		("CodeRevision",                   uint16_t),    # 12
		("CodeType",                       uint8_t),     # 14
		("Indicator",                      uint8_t),     # 15
		("MaxRuntimeImageLength",          uint16_t),    # 16 Reserved in PCI 2.3 and bellow
		("ConfigUtilityCodeHeaderOffset",  uint16_t),    # 18 Missing in PCI 2.3 and bellow
		("DMTFCLPEntryPointOffset",        uint16_t),    # 1A Missing in PCI 2.3 and bellow
		# 1C
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def pcir_print(self, offset):
		
		dev_list = ""
		
		if 0 < self.DeviceListOffset < 0xFFFF :
			dev_list += "\n\n" + " " * 36
			dev_bgn  = self.DeviceListOffset + offset
			dev_nr   = 0
			ven_ID   = "%0.4X" % self.VendorId
			
			step = dev_bgn
			
			while True :
				dev_ID = binascii.hexlify(reading[step:step + 2][::-1]).decode('utf-8').upper()
				
				if dev_ID == "0000" or (ven_ID == "1B4B" and dev_ID == "614D" and reading[step:step + 7] == b'Marvell') :
					# The second test is for another Marvell flop.
					break
				
				dev_nr   += 1
				dev_list += ven_ID + "-" + dev_ID + "  "
				
				if (dev_nr % 4) == 0 :
					dev_list += "\n\n" + " " * 36
				
				step += 2
			
			if (dev_nr % 4) != 0 :
				dev_list += "\n"
		
		if self.Revision == 0 :
			pci_struct_rev = "PCI 2.3"
		elif self.Revision == 3 :
			pci_struct_rev = "PCI 3.0"
		else :
			pci_struct_rev = "Unknown"
		
		class_code1 = "-".join("%02X" % val for val in self.ClassCode[::-1])
		class_code2 = "-".join("%02X" % val for val in self.ClassCode)
		img_size    = self.ImageLength * 0x200
		
		if self.CodeType == 0 :
			code_type = "Intel x86, PC-AT compatible"
		elif self.CodeType == 1 :
			code_type = "Open Firmware standard for PCI"
		elif self.CodeType == 2 :
			code_type = "Hewlett-Packard PA RISC"
		elif self.CodeType == 3 :
			code_type = "EFI - Extensible Firmware Interface"
		elif self.CodeType == 0x70 :
			code_type = "Nvidia NBSI - Signature"
		elif self.CodeType == 0x85 :
			code_type = "Nvidia HDCP"
		elif self.CodeType == 0xE0 :
			code_type = "Nvidia x86 Extension"
		else :
			code_type = "Unknown"
		
		if self.Indicator & 0x80 :
			last_img = "Last image"
		else :
			last_img = "Not last image"
		
		max_len      = self.MaxRuntimeImageLength * 0x200
		dev_list_abs = self.DeviceListOffset + offset if self.DeviceListOffset else 0
		conf_hdr_abs = self.ConfigUtilityCodeHeaderOffset + offset if self.ConfigUtilityCodeHeaderOffset else 0
		dmtf_off_abs = self.DMTFCLPEntryPointOffset + offset if self.DMTFCLPEntryPointOffset else 0
		
		print("-------------PCIR_HEADER------------\n")
		print("Signature:                          %s"           % self.Signature.decode('utf-8'))
		print("Vendor ID:                          %0.4X"        % self.VendorId)
		print("Device ID:                          %0.4X"        % self.DeviceId)
		
		if self.Revision < 3 and self.DeviceListOffset == 0 :
			print("Reserved:                           %0.2X"    % self.DeviceListOffset)
		else :
			print("Device List Offset:                 0x%-4.2X   (abs 0x%0.2X)%s"  % (self.DeviceListOffset, dev_list_abs, dev_list))
		
		print("Length:                             0x%0.2X"      % self.Length)
		print("Revision:                           %-6.2X   (%s)"         % (self.Revision, pci_struct_rev))
		print("ClassCode:                          %s (or %s)"            % (class_code1, class_code2))
		print("Image Length:                       0x%-4.2X   (0x%0.2X)"  % (self.ImageLength, img_size))
		print("Code Revision:                      0x%0.2X"               % self.CodeRevision)
		print("Code Type:                          0x%-4.2X   (%s)"       % (self.CodeType, code_type))
		print("Indicator:                          0x%-4.2X   (%s)"       % (self.Indicator, last_img))
		
		if self.Revision < 3 :
			print("Reserved:                           %0.2X"    % self.MaxRuntimeImageLength)
		else :
			print("Max Runtime Image Length:           0x%-4.2X   (0x%0.2X)"      % (self.MaxRuntimeImageLength, max_len))
		
		if self.Length > 0x18 :
			print("Config Utility Code Header Offset:  0x%-4.2X   (abs 0x%0.2X)"  % (self.ConfigUtilityCodeHeaderOffset, conf_hdr_abs))
			print("DMTF CLP Entry Point Offset:        0x%-4.2X   (abs 0x%0.2X)"  % (self.DMTFCLPEntryPointOffset, dmtf_off_abs))
		
		print("\n------------------------------------\n")
	
	def rgis_print(self, offset):
		
		if self.Revision == 0 :
			pci_struct_rev = "PCI 2.3"
		elif self.Revision == 3 :
			pci_struct_rev = "PCI 3.0"
		else :
			pci_struct_rev = "Unknown"
		
		class_code1 = "-".join("%02X" % val for val in self.ClassCode[::-1])
		class_code2 = "-".join("%02X" % val for val in self.ClassCode)
		img_size    = self.ImageLength * 0x200
		
		if self.CodeType == 0 :
			code_type = "Intel x86, PC-AT compatible"
		elif self.CodeType == 1 :
			code_type = "Open Firmware standard for PCI"
		elif self.CodeType == 2 :
			code_type = "Hewlett-Packard PA RISC"
		elif self.CodeType == 3 :
			code_type = "EFI - Extensible Firmware Interface"
		elif self.CodeType == 0x70 :
			code_type = "Nvidia NBSI - Signature"
		elif self.CodeType == 0x85 :
			code_type = "Nvidia HDCP"
		elif self.CodeType == 0xE0 :
			code_type = "Nvidia x86 Extension"
		else :
			code_type = "Unknown"
		
		if self.Indicator & 0x80 :
			last_img = "Last image"
		else :
			last_img = "Not last image"
		
		print("-------------RGIS_HEADER------------\n")
		print("Signature:                          %s"           % self.Signature.decode('utf-8'))
		print("Vendor ID:                          %0.4X"        % self.VendorId)
		print("Device ID:                          %0.4X"        % self.DeviceId)
		print("Reserved:                           %0.2X"        % self.DeviceListOffset)
		print("Length:                             0x%0.2X"      % self.Length)
		print("Revision:                           %-6.2X   (%s)"         % (self.Revision, pci_struct_rev))
		print("ClassCode:                          %s (or %s)"            % (class_code1, class_code2))
		print("Image Length:                       0x%-4.2X   (0x%0.2X)"  % (self.ImageLength, img_size))
		print("Reserved:                           %0.2X"                 % self.CodeRevision)
		print("Code Type:                          0x%-4.2X   (%s)"       % (self.CodeType, code_type))
		print("Indicator:                          0x%-4.2X   (%s)"       % (self.Indicator, last_img))
		print("Reserved:                           %0.2X"        % self.MaxRuntimeImageLength)
		print("Reserved:                           %0.2X"        % self.ConfigUtilityCodeHeaderOffset)
		print("Reserved:                           %0.2X"        % self.DMTFCLPEntryPointOffset)
		print("\n------------------------------------\n")

class RGIS_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                      char * 4),    # 00 RGIS
		("VendorId",                       uint16_t),    # 04
		("DeviceId",                       uint16_t),    # 06
		("Reserved",                       uint16_t),    # 08
		("Length",                         uint16_t),    # 0A
		("Revision",                       uint8_t),     # 0C
		("ClassCode",                      uint8_t * 3), # 0D
		("ImageLength",                    uint16_t),    # 10
		("Reserved2",                      uint16_t),    # 12
		("CodeType",                       uint8_t),     # 14
		("Indicator",                      uint8_t),     # 15
		("Reserved3",                      uint16_t),    # 16
		("Reserved4",                      uint16_t),    # 18
		("Reserved5",                      uint16_t),    # 1A
		# 1C
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def rgis_print(self, offset):
		
		if self.Revision == 0 :
			pci_struct_rev = "PCI 2.3"
		elif self.Revision == 3 :
			pci_struct_rev = "PCI 3.0"
		else :
			pci_struct_rev = "Unknown"
		
		class_code1 = "-".join("%02X" % val for val in self.ClassCode[::-1])
		class_code2 = "-".join("%02X" % val for val in self.ClassCode)
		img_size    = self.ImageLength * 0x200
		
		if self.CodeType == 0 :
			code_type = "Intel x86, PC-AT compatible"
		elif self.CodeType == 1 :
			code_type = "Open Firmware standard for PCI"
		elif self.CodeType == 2 :
			code_type = "Hewlett-Packard PA RISC"
		elif self.CodeType == 3 :
			code_type = "EFI - Extensible Firmware Interface"
		elif self.CodeType == 0x70 :
			code_type = "Nvidia NBSI - Signature"
		elif self.CodeType == 0x85 :
			code_type = "Nvidia HDCP"
		elif self.CodeType == 0xE0 :
			code_type = "Nvidia x86 Extension"
		else :
			code_type = "Unknown"
		
		if self.Indicator & 0x80 :
			last_img = "Last image"
		else :
			last_img = "Not last image"
		
		print("-------------RGIS_HEADER------------\n")
		print("Signature:                          %s"           % self.Signature.decode('utf-8'))
		print("Vendor ID:                          %0.4X"        % self.VendorId)
		print("Device ID:                          %0.4X"        % self.DeviceId)
		print("Reserved:                           %0.2X"        % self.Reserved)
		print("Length:                             0x%0.2X"      % self.Length)
		print("Revision:                           %-6.2X   (%s)"         % (self.Revision, pci_struct_rev))
		print("ClassCode:                          %s (or %s)"            % (class_code1, class_code2))
		print("Image Length:                       0x%-4.2X   (0x%0.2X)"  % (self.ImageLength, img_size))
		print("Reserved:                           %0.2X"                 % self.Reserved2)
		print("Code Type:                          0x%-4.2X   (%s)"       % (self.CodeType, code_type))
		print("Indicator:                          0x%-4.2X   (%s)"       % (self.Indicator, last_img))
		print("Reserved:                           %0.2X"        % self.Reserved3)
		print("Reserved:                           %0.2X"        % self.Reserved4)
		print("Reserved:                           %0.2X"        % self.Reserved5)
		print("\n------------------------------------\n")

class NPDE_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                 char * 4),     # 00 NPDE
		("PciDataExtensionRev",       uint16_t),     # 04
		("Length",                    uint16_t),     # 06
		("ImageLength",               uint16_t),     # 08
		("Indicator",                 uint8_t),      # 0A
		("Unknown",                   uint8_t),      # 0B
		("GopVersion",                uint32_t),     # 0C
		("SubsystemID",               uint32_t),     # 10
		# 14
    ]
    
	def pack(self):
		return bytearray(self)[:]
	
	def npde_print(self, offset):
		
		img_size    = self.ImageLength * 0x200
		
		if self.Indicator & 0x80 :
			last_img = "Last image"
		else :
			last_img = "Not last image"
		
		subsys_id = id_from_bin(self.SubsystemID.to_bytes(4, 'little'), 'string')
		
		print("-------------NPDE_HEADER------------\n")
		print("Signature:                          %s"      % self.Signature.decode('utf-8'))
		print("PCI data extension revision         %0.2X"   % self.PciDataExtensionRev)
		print("NPDE Length                         0x%0.2X" % self.Length)
		print("Image Length                        0x%-4.2X   (0x%0.2X)"  % (self.ImageLength, img_size))
		print("Indicator                           0x%-4.2X   (%s)"       % (self.Indicator, last_img))
		print("Unknown                             0x%0.2X"    % self.Unknown)
		
		if self.Length > 0xC :
			print("Nvidia GOP version                  0x%0.2X"    % self.GopVersion)
		
		if self.Length > 0x10 :
			print("Subsystem ID                        %s"         % subsys_id)
		
		print("\n------------------------------------\n")

class PnP_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Signature",                       char * 4),    # 00 $PnP
		("StructureRevision",               uint8_t),     # 04
		("Length",                          uint8_t),     # 05
		("OffsetOfNextHdr",                 uint16_t),    # 06 0000h if none
		("Reserved",                        uint8_t),     # 08
		("Checksum",                        uint8_t),     # 09
		("DeviceIdentifier",                uint32_t),    # 0A
		("PointerToManufacturerString",     uint16_t),    # 0E Optional
		("PointerToProductNameString",      uint16_t),    # 10 Optional
		("DeviceTypeCode",                  uint8_t * 3), # 12
		("DeviceIndicators",                uint8_t),     # 15
		("BootConnectionVector",            uint16_t),    # 16 0000h if none
		("DisconnectVector",                uint16_t),    # 18 0000h if none
		("BootstrapEntryPoint",             uint16_t),    # 1A 0000h if none
		("Reserved",                        uint16_t),    # 1C
		("StaticResourceInformationVector", uint16_t),    # 1E 0000h if none
		# 20
    ]
	
	def pack(self):
		return bytearray(self)[:]
    
	def pnp_print(self, offset):
		
		next_hdr_abs = self.OffsetOfNextHdr + offset if self.OffsetOfNextHdr else 0
		
		checksum = sum(bytearray(bytearray(self)[:])) & 0xFF
		checksum = (0x100 - checksum) & 0xFF
		
		if checksum > 0 :
			chk_byte = (sum(bytearray(bytearray(self)[:])) - self.Checksum) & 0xFF
			chk_byte = (0x100 - chk_byte) & 0xFF
			pnp_chk_str = "    (Should be 0x%0.2X !!!)" % chk_byte
		else :
			pnp_chk_str = ""
		
		device_ident = id_from_bin(self.DeviceIdentifier.to_bytes(4, 'little'), "string")
		manuf_abs    = self.PointerToManufacturerString + offset if self.PointerToManufacturerString else 0
		manuf_str    = "\n\n" + " " * 36 + get_name(reading, manuf_abs, 'utf-8') + "\n" if manuf_abs else ""
		prod_abs     = self.PointerToProductNameString + offset if self.PointerToProductNameString else 0
		prod_str     = "\n\n" + " " * 36 + get_name(reading, prod_abs, 'utf-8') + "\n" if prod_abs else ""
		device_code1 = "-".join("%02X" % val for val in self.DeviceTypeCode[::-1])
		device_code2 = "-".join("%02X" % val for val in self.DeviceTypeCode)
		
		device_indic = "\n"
		
		if self.DeviceIndicators & 1 :
			device_indic += "\n" + " " * 36 + "Display device"
		
		if self.DeviceIndicators & 2 :
			device_indic += "\n" + " " * 36 + "Input device"
		
		if self.DeviceIndicators & 4 :
			device_indic += "\n" + " " * 36 + "Initial Program Load (IPL) device"
		
		if self.DeviceIndicators & 0x10 :
			device_indic += "\n" + " " * 36 + "OROM required only if this device is selected as a boot device."
		
		if self.DeviceIndicators & 0x20 :
			device_indic += "\n" + " " * 36 + "OROM is Read Cacheable"
		
		if self.DeviceIndicators & 0x40 :
			device_indic += "\n" + " " * 36 + "OROM may be Shadowed in RAM"
		
		if self.DeviceIndicators & 0x80 :
			device_indic += "\n" + " " * 36 + "OROM supports the Device Driver Initialization Model"
		
		device_indic += "\n"
		
		boot_cv_abs = self.BootConnectionVector + offset if self.BootConnectionVector else 0
		disc_vc_abs = self.DisconnectVector + offset if self.DisconnectVector else 0
		boot_ep_abs = self.BootstrapEntryPoint + offset if self.BootstrapEntryPoint else 0
		stat_iv_abs = self.StaticResourceInformationVector + offset if self.StaticResourceInformationVector else 0
				
		print("-------------PnP_HEADER-------------\n")
		print("Signature:                          %s"          % self.Signature.decode('utf-8'))
		print("Structure Revision:                 %0.2X"       % self.StructureRevision)
		print("Length:                             0x%-6.2X  (0x%0.2X)"     % (self.Length, self.Length * 0x10))
		print("Offset Of Next Header:              0x%-6.2X  (abs 0x%0.2X)" % (self.OffsetOfNextHdr, next_hdr_abs))
		print("Reserved:                           %0.2X"       % self.Reserved)
		print("Checksum:                           0x%-4.2X%s"  % (self.Checksum, pnp_chk_str))
		print("Device Identifier:                  %s"          % device_ident)
		print("Pointer To Manufacturer String:     0x%-6.2X  (abs 0x%0.2X)%s" % (self.PointerToManufacturerString, manuf_abs, manuf_str))
		print("Pointer To Product Name String:     0x%-6.2X  (abs 0x%0.2X)%s" % (self.PointerToProductNameString, prod_abs, prod_str))
		print("Device Type Code:                   %s  (or %s)" % (device_code1, device_code2))
		print("Device Indicators:                  0x%0.2X%s"   % (self.DeviceIndicators, device_indic))
		print("Boot Connection Vector:             0x%-6.2X  (abs 0x%0.2X)" % (self.BootConnectionVector, boot_cv_abs))
		print("Disconnect Vector:                  0x%-6.2X  (abs 0x%0.2X)" % (self.DisconnectVector, disc_vc_abs))
		print("Bootstrap Entry Point:              0x%-6.2X  (abs 0x%0.2X)" % (self.BootstrapEntryPoint, boot_ep_abs))
		print("Reserved:                           %0.2X"       % self.Reserved)
		print("Static Resource Information Vector: 0x%-6.2X  (abs 0x%0.2X)" % (self.StaticResourceInformationVector, stat_iv_abs))
		
		print("\n------------------------------------\n")

class DOS_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("e_magic",     char*2),      # 00 MZ
		("e_cblp",      uint16_t),    # 02
		("e_cp",        uint16_t),    # 04
		("e_crlc",      uint16_t),    # 06
		("e_cparhdr",   uint16_t),    # 08
		("e_minalloc",  uint16_t),    # 0A
		("e_maxalloc",  uint16_t),    # 0C
		("e_ss",        uint16_t),    # 0E
		("e_sp",        uint16_t),    # 10
		("e_csum",      uint16_t),    # 12
		("e_ip",        uint16_t),    # 14
		("e_cs",        uint16_t),    # 16
		("e_lfarlc",    uint16_t),    # 18
		("e_ovno",      uint16_t),    # 1A
		("e_res",       uint16_t*4),  # 1C
		("e_oemid",     uint16_t),    # 24
		("e_oeminfo",   uint16_t),    # 26
		("e_res2",      uint16_t*10), # 28
		("e_lfanew",    uint32_t),    # 3C
		# 3E
    ]
    
	def dos_print(self):
		print("----------DOS_HEADER----------\n")
		print("e_magic:                       %s"      % self.e_magic.decode('utf-8'))
		print("e_cblp:                        0x%0.2X" % self.e_cblp)
		print("e_cp:                          0x%0.2X" % self.e_cp)
		print("e_crlc:                        0x%0.2X" % self.e_crlc)
		print("e_cparhdr:                     0x%0.2X" % self.e_cparhdr)
		print("e_minalloc:                    0x%0.2X" % self.e_minalloc)
		print("e_maxalloc:                    0x%0.2X" % self.e_maxalloc)
		print("e_ss:                          0x%0.2X" % self.e_ss)
		print("e_sp:                          0x%0.2X" % self.e_sp)
		print("e_csum:                        0x%0.2X" % self.e_csum)
		print("e_ip:                          0x%0.2X" % self.e_ip)
		print("e_cs:                          0x%0.2X" % self.e_cs)
		print("e_lfarlc:                      0x%0.2X" % self.e_lfarlc)
		print("e_ovno:                        0x%0.2X" % self.e_ovno)
		print("e_res:                         %s"      % hexdump(self.e_res))
		print("e_oemid:                       0x%0.2X" % self.e_oemid)
		print("e_oeminfo:                     0x%0.2X" % self.e_oeminfo)
		print("e_res2:                        %s"      % hexdump(self.e_res2))
		print("e_lfanew:                      0x%0.2X" % self.e_lfanew)
		print("\n------------------------------\n")

class PE_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("signature",   char*4),      # 00 PE\x00\x00
		# 04
	]
	
	def pe_print(self):
		print("----------PE_HEADER-----------\n")
		print("Signature:                     %s" % self.signature.rstrip(b'\x00').decode('utf-8'))
		print("\n------------------------------\n")

class COFF_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Machine",              uint16_t), # 00
		("NumberOfSections",     uint16_t), # 02
		("TimeDateStamp",        uint32_t), # 04
		("PointerToSymbolTable", uint32_t), # 08
		("NumberOfSymbols",      uint32_t), # 0C
		("SizeOfOptionalHeader", uint16_t), # 10
		("Characteristics",      uint16_t), # 12
		# 14
	]
	
	def coff_print(self):
		print("---------COFF_HEADER----------\n")
		print("Machine:                       0x%0.4X" % self.Machine)
		print("NumberOfSections:              0x%0.2X" % self.NumberOfSections)
		print("TimeDateStamp:                 0x%0.2X" % self.TimeDateStamp)
		print("PointerToSymbolTable:          0x%0.2X" % self.PointerToSymbolTable)
		print("NumberOfSymbols:               0x%0.2X" % self.NumberOfSymbols)
		print("SizeOfOptionalHeader:          0x%0.2X" % self.SizeOfOptionalHeader)
		print("Characteristics:               0x%0.4X" % self.Characteristics)
		print("\n------------------------------\n")

class Optional_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Magic",                        uint16_t), # 00 0x010B - PE32, 0x020B - PE32+ (64 bit)
		("MajorLinkerVersion",           uint8_t),  # 02
		("MinorLinkerVersion",           uint8_t),  # 03
		("SizeOfCode",                   uint32_t), # 04
		("SizeOfInitializedData",        uint32_t), # 08
		("SizeOfUninitializedData",      uint32_t), # 0C
		("AddressOfEntryPoint",          uint32_t), # 10
		("BaseOfCode",                   uint32_t), # 14
		("BaseOfData",                   uint32_t), # 18
		("ImageBase",                    uint32_t), # 1C
		("SectionAlignment",             uint32_t), # 20
		("FileAlignment",                uint32_t), # 24
		("MajorOperatingSystemVersion",  uint16_t), # 28
		("MinorOperatingSystemVersion",  uint16_t), # 2A
		("MajorImageVersion",            uint16_t), # 2C
		("MinorImageVersion",            uint16_t), # 2E
		("MajorSubsystemVersion",        uint16_t), # 30
		("MinorSubsystemVersion",        uint16_t), # 32
		("Win32VersionValue",            uint32_t), # 34
		("SizeOfImage",                  uint32_t), # 38
		("SizeOfHeaders",                uint32_t), # 3C
		("CheckSum",                     uint32_t), # 40
		("Subsystem",                    uint16_t), # 44
		("DllCharacteristics",           uint16_t), # 46
		("SizeOfStackReserve",           uint32_t), # 48
		("SizeOfStackCommit",            uint32_t), # 4C
		("SizeOfHeapReserve",            uint32_t), # 50
		("SizeOfHeapCommit",             uint32_t), # 54
		("LoaderFlags",                  uint32_t), # 58
		("NumberOfRvaAndSizes",          uint32_t), # 5C
		# 60
	]
	
	def opt_print(self):
		print("-------Optional_HEADER--------\n")
		print("Magic:                         0x%0.4X" % self.Magic)
		print("MajorLinkerVersion:            0x%0.2X" % self.MajorLinkerVersion)
		print("MinorLinkerVersion:            0x%0.2X" % self.MinorLinkerVersion)
		print("SizeOfCode:                    0x%0.2X" % self.SizeOfCode)
		print("SizeOfInitializedData:         0x%0.2X" % self.SizeOfInitializedData)
		print("SizeOfUninitializedData:       0x%0.2X" % self.SizeOfUninitializedData)
		print("AddressOfEntryPoint:           0x%0.2X" % self.AddressOfEntryPoint)
		print("BaseOfCode:                    0x%0.2X" % self.BaseOfCode)
		print("BaseOfData:                    0x%0.2X" % self.BaseOfData)
		print("ImageBase:                     0x%0.2X" % self.ImageBase)
		print("SectionAlignment:              0x%0.2X" % self.SectionAlignment)
		print("FileAlignment:                 0x%0.2X" % self.FileAlignment)
		print("MajorOperatingSystemVersion:   0x%0.2X" % self.MajorOperatingSystemVersion)
		print("MinorOperatingSystemVersion:   0x%0.2X" % self.MinorOperatingSystemVersion)
		print("MajorImageVersion:             0x%0.2X" % self.MajorImageVersion)
		print("MinorImageVersion:             0x%0.2X" % self.MinorImageVersion)
		print("MajorSubsystemVersion:         0x%0.2X" % self.MajorSubsystemVersion)
		print("MinorSubsystemVersion:         0x%0.2X" % self.MinorSubsystemVersion)
		print("Win32VersionValue:             0x%0.2X" % self.Win32VersionValue)
		print("SizeOfImage:                   0x%0.2X" % self.SizeOfImage)
		print("SizeOfHeaders:                 0x%0.2X" % self.SizeOfHeaders)
		print("CheckSum:                      0x%0.2X" % self.CheckSum)
		print("Subsystem:                     0x%0.4X" % self.Subsystem)
		print("DllCharacteristics:            0x%0.4X" % self.DllCharacteristics)
		print("SizeOfStackReserve:            0x%0.2X" % self.SizeOfStackReserve)
		print("SizeOfStackCommit:             0x%0.2X" % self.SizeOfStackCommit)
		print("SizeOfHeapReserve:             0x%0.2X" % self.SizeOfHeapReserve)
		print("SizeOfHeapCommit:              0x%0.2X" % self.SizeOfHeapCommit)
		print("LoaderFlags:                   0x%0.2X" % self.LoaderFlags)
		print("NumberOfRvaAndSizes:           0x%0.2X" % self.NumberOfRvaAndSizes)
		print("\n------------------------------\n")

class Optional_Header64(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Magic",                        uint16_t), # 00 0x010B - PE32, 0x020B - PE32+ (64 bit)
		("MajorLinkerVersion",           uint8_t),  # 02
		("MinorLinkerVersion",           uint8_t),  # 03
		("SizeOfCode",                   uint32_t), # 04
		("SizeOfInitializedData",        uint32_t), # 08
		("SizeOfUninitializedData",      uint32_t), # 0C
		("AddressOfEntryPoint",          uint32_t), # 10
		("BaseOfCode",                   uint32_t), # 14
		("ImageBase",                    uint64_t), # 18
		("SectionAlignment",             uint32_t), # 20
		("FileAlignment",                uint32_t), # 24
		("MajorOperatingSystemVersion",  uint16_t), # 28
		("MinorOperatingSystemVersion",  uint16_t), # 2A
		("MajorImageVersion",            uint16_t), # 2C
		("MinorImageVersion",            uint16_t), # 2E
		("MajorSubsystemVersion",        uint16_t), # 30
		("MinorSubsystemVersion",        uint16_t), # 32
		("Win32VersionValue",            uint32_t), # 34
		("SizeOfImage",                  uint32_t), # 38
		("SizeOfHeaders",                uint32_t), # 3C
		("CheckSum",                     uint32_t), # 40
		("Subsystem",                    uint16_t), # 44
		("DllCharacteristics",           uint16_t), # 46
		("SizeOfStackReserve",           uint64_t), # 48
		("SizeOfStackCommit",            uint64_t), # 50
		("SizeOfHeapReserve",            uint64_t), # 58
		("SizeOfHeapCommit",             uint64_t), # 60
		("LoaderFlags",                  uint32_t), # 68
		("NumberOfRvaAndSizes",          uint32_t), # 6C
		# 70
	]
	
	def opt_print(self):
		print("-------Optional_HEADER64------\n")
		print("Magic:                         0x%0.4X" % self.Magic)
		print("MajorLinkerVersion:            0x%0.2X" % self.MajorLinkerVersion)
		print("MinorLinkerVersion:            0x%0.2X" % self.MinorLinkerVersion)
		print("SizeOfCode:                    0x%0.2X" % self.SizeOfCode)
		print("SizeOfInitializedData:         0x%0.2X" % self.SizeOfInitializedData)
		print("SizeOfUninitializedData:       0x%0.2X" % self.SizeOfUninitializedData)
		print("AddressOfEntryPoint:           0x%0.2X" % self.AddressOfEntryPoint)
		print("BaseOfCode:                    0x%0.2X" % self.BaseOfCode)
		print("ImageBase:                     0x%0.2X" % self.ImageBase)
		print("SectionAlignment:              0x%0.2X" % self.SectionAlignment)
		print("FileAlignment:                 0x%0.2X" % self.FileAlignment)
		print("MajorOperatingSystemVersion:   0x%0.2X" % self.MajorOperatingSystemVersion)
		print("MinorOperatingSystemVersion:   0x%0.2X" % self.MinorOperatingSystemVersion)
		print("MajorImageVersion:             0x%0.2X" % self.MajorImageVersion)
		print("MinorImageVersion:             0x%0.2X" % self.MinorImageVersion)
		print("MajorSubsystemVersion:         0x%0.2X" % self.MajorSubsystemVersion)
		print("MinorSubsystemVersion:         0x%0.2X" % self.MinorSubsystemVersion)
		print("Win32VersionValue:             0x%0.2X" % self.Win32VersionValue)
		print("SizeOfImage:                   0x%0.2X" % self.SizeOfImage)
		print("SizeOfHeaders:                 0x%0.2X" % self.SizeOfHeaders)
		print("CheckSum:                      0x%0.2X" % self.CheckSum)
		print("Subsystem:                     0x%0.4X" % self.Subsystem)
		print("DllCharacteristics:            0x%0.4X" % self.DllCharacteristics)
		print("SizeOfStackReserve:            0x%0.2X" % self.SizeOfStackReserve)
		print("SizeOfStackCommit:             0x%0.2X" % self.SizeOfStackCommit)
		print("SizeOfHeapReserve:             0x%0.2X" % self.SizeOfHeapReserve)
		print("SizeOfHeapCommit:              0x%0.2X" % self.SizeOfHeapCommit)
		print("LoaderFlags:                   0x%0.2X" % self.LoaderFlags)
		print("NumberOfRvaAndSizes:           0x%0.2X" % self.NumberOfRvaAndSizes)

class Data_Directory(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("VirtualAddress",   uint32_t), # 00
		("Size",             uint32_t), # 04
		# 08
	]
	
	def datadir_print(self, index):
		print("--------Data_Directory--------\n")
		print("Index:                         %d\n"    % index)
		
		print("VirtualAddress:                0x%0.2X" % self.VirtualAddress)
		print("Size:                          0x%0.2X" % self.Size)
		print("\n------------------------------\n")

class Section_Header(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Name",                  char*8),   # 00
		("VirtualSize",           uint32_t), # 08
		("VirtualAddress",        uint32_t), # 0C
		("SizeOfRawData",         uint32_t), # 10
		("PointerToRawData",      uint32_t), # 14
		("PointerToRealocations", uint32_t), # 18
		("PointerToLinenumbers",  uint32_t), # 1C
		("NumberOfRealocations",  uint16_t), # 20
		("NumberOfLinenumbers",   uint16_t), # 22
		("Characteristics",       uint32_t), # 24
		# 28
	]
	
	def sec_print(self):
		print("--------Section_HEADER--------\n")
		print("Name:                          %s"      % self.Name.rstrip(b'\x00').decode('utf-8'))
		print("VirtualSize:                   0x%0.2X" % self.VirtualSize)
		print("VirtualAddress:                0x%0.2X" % self.VirtualAddress)
		print("SizeOfRawData:                 0x%0.2X" % self.SizeOfRawData)
		print("PointerToRawData:              0x%0.2X" % self.PointerToRawData)
		print("PointerToRealocations:         0x%0.2X" % self.PointerToRealocations)
		print("PointerToLinenumbers:          0x%0.2X" % self.PointerToLinenumbers)
		print("NumberOfRealocations:          0x%0.2X" % self.NumberOfRealocations)
		print("NumberOfLinenumbers:           0x%0.2X" % self.NumberOfLinenumbers)
		print("Characteristics:               0x%0.4X" % self.Characteristics)
		print("\n------------------------------\n")

class Resource_Directory(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Characteristics",      uint32_t), # 00
		("TimeDateStamp",        uint32_t), # 04
		("MajorVersion",         uint16_t), # 08
		("MinorVersion",         uint16_t), # 0A
		("NumberOfNamedEntries", uint16_t), # 0C
		("NumberOfIdEntries",    uint16_t), # 0E
		# 10
	]
	
	def rsrc_print(self):
		print("------Resource_Directory------\n")
		print("Characteristics:               0x%0.8X" % self.Characteristics)
		print("TimeDateStamp:                 0x%0.2X" % self.TimeDateStamp)
		print("MajorVersion:                  0x%0.2X" % self.MajorVersion)
		print("MinorVersion:                  0x%0.2X" % self.MinorVersion)
		print("NumberOfNamedEntries:          0x%0.2X" % self.NumberOfNamedEntries)
		print("NumberOfIdEntries:             0x%0.2X" % self.NumberOfIdEntries)
		print("\n------------------------------\n")

class Resource_Directory_Entry(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("NameId",      uint32_t), # 00
		("Data",        uint32_t), # 04
		# 08
	]
	
	def resdirentry_print(self, name_rsrc, index):
		print("------Resource_DIR_Entry------\n")
		
		if index :
			print("Index:                         %d"      % index)
			print("Name or ID:                    %s\n"    % name_rsrc)
		else:
			print("Name or ID:                    %s\n"    % name_rsrc)
		
		print("NameId:                        0x%0.8X" % self.NameId)
		print("Data:                          0x%0.2X" % self.Data)
		print("\n------------------------------\n")

class Resource_Data_Entry(ctypes.LittleEndianStructure):
	_pack_   = 1
	_fields_ = [
		("Data",        uint32_t), # 00
		("Size",        uint32_t), # 04
		("CodePage",    uint32_t), # 08
		("Reserved",    uint32_t), # 0C
		# 10
	]
	
	def resdatentry_print(self):
		print("-----Resource_Data_Entry------\n")
		print("Data:                          0x%0.2X" % self.Data)
		print("Size:                          0x%0.2X" % self.Size)
		print("CodePage:                      0x%0.2X" % self.CodePage)
		print("Reserved:                      0x%0.2X" % self.Reserved)
		print("\n------------------------------\n")

def get_struct (str_, off, struct):
	my_struct  = struct()
	struct_len = ctypes.sizeof(my_struct)
	str_data   = str_[off:off + struct_len]
	fit_len    = min(len(str_data), struct_len)
	
	if fit_len < struct_len:
		raise Exception("can't read struct: %d bytes available but %d required" % (fit_len, struct_len))
	
	ctypes.memmove(ctypes.addressof(my_struct), str_data, fit_len)
	
	return my_struct

def get_name (data, offset, type) :
	
	if type == 'utf-16' :
		null_byte = b'\x00\x00'
		dec_type  = 'utf-16'
		len_byte  = 2
	else :
		null_byte = b'\x00'
		dec_type  = 'utf-8'
		len_byte  = 1
	
	name_str  = ""
	name_step = offset
	name_char = data[name_step:name_step + 1]
	
	while name_char != null_byte :
		name_str  += name_char.decode(dec_type, 'ignore')
		name_step += len_byte
		name_char = data[name_step:name_step + len_byte]
	
	return name_str

def hexdump (data):
	
	if isinstance(data, str):
		data = map(ord, data)
	
	return " ".join("%02X" % v for v in data)

def id_from_bin (id_data, output) :
	
	hex_bin  = binascii.hexlify(id_data).decode('utf-8').upper()
	id_hex   = binascii.hexlify(id_data[::-1]).decode('utf-8').upper()
	#id_hex   = id_hex[4:] + id_hex[:4]
	pci_ven  = id_hex[4:]
	pci_dev  = id_hex[:4]
	ven_dev  = pci_ven + "-" + pci_dev
	
	if output == "hexbin" :
		return hex_bin
	elif output == "hexrev" :
		return id_hex
	elif output == "id_list" :
		return pci_ven, pci_dev
	elif output == "all_list" :
		return ven_dev, pci_ven, pci_dev
	elif output == "hex" :
		return pci_ven + pci_dev
	else :
		return ven_dev

def mz_off (pe_data, offset) :
	
	pat_mz    = re.compile(br'\x4D\x5A')
	match_mz  = pat_mz.search(pe_data, offset)
	mz_found  = False
	mz_start  = 0xFFFFFFFF
	
	if match_mz is None :
		return mz_found, mz_start # False, 0xFFFFFFFF
	
	while match_mz is not None :
		
		(mz_start, mz_end) = match_mz.span()
		pe_off = int.from_bytes(pe_data[mz_start + 0x3C:mz_start + 0x40], 'little') + int(mz_start)
		
		if pe_data[pe_off:pe_off + 4] in [b'\x50\x45\x00\x00', b'\x4C\x45\x00\x00'] : # PE and LE
			
			mz_found = True
			break
		
		match_mz  = pat_mz.search(pe_data, mz_end)
	
	else :
		mz_found  = False
		mz_start  = 0xFFFFFFFF
	
	return mz_found, mz_start

def pe_machine (pe_data) :
	
	code_type = ""
	
	mz_found, mz_start = mz_off(pe_data, 0)
	
	if not mz_found :
		mz_start   = 0xFFFFFFFF
		code_type  = "notMZ"
		print_type = " notMZ"
		return mz_start, code_type, print_type
	
	pe_off = int.from_bytes(pe_data[mz_start + 0x3C:mz_start + 0x40], 'little') + int(mz_start)
		
	if pe_data[pe_off:pe_off + 4] == b'\x50\x45\x00\x00' :
		
		code_sig = pe_data[pe_off + 4:pe_off + 6][::-1]
		
		if code_sig == b'\x86\x64' :
			code_type = "x64"
		
		elif code_sig == b'\x01\x4C' :
			code_type = "x86" # IA32
		
		elif code_sig == b'\x02\x00' :
			code_type = "IA64"
		
		elif code_sig == b'\x0E\xBC' :
			code_type = "EBC" # EFI Byte Code
		
		elif code_sig == b'\x01\xC0' :
			code_type = "ARM"
		
		elif code_sig == b'\x01\xC2' :
			code_type = "THUMB" # ARM-THUMB-MIXED
		
		elif code_sig == b'\x01\xC4' :
			code_type = "ARMv7"
		
		elif code_sig == b'\xAA\x64' :
			code_type = "ARMv8_x64"
		
		else : # There are many more in the specification, but use only the most common ones.
			code_type = "unkSIG"
	
	else :
		code_type = "LE"
	
	if code_type == "x64" :
		print_type = ""
	else :
		print_type = " " + code_type
	
	return mz_start, code_type, print_type

def image_size (image_data, result_type) :
	
	imag_size  = 0
	sig_size   = 0
	sig_off    = 0
	all_content  = True
	sig_included = True
	
	if result_type == "naked" :
		all_content  = False
		sig_included = False
	elif result_type == "stub" :
		all_content  = False
	
	mz_found, mz_start = mz_off(image_data, 0)
	
	if not mz_found :
		#print("No MZ found!\n")
		return 2
	
	dos_hdr  = get_struct(image_data, mz_start, DOS_Header)
	#dos_hdr.dos_print()
	
	pe_off   = dos_hdr.e_lfanew
	pe_hdr   = get_struct(image_data, pe_off, PE_Header)
	#pe_hdr.pe_print()
	
	coff_off = pe_off + 4 # pe_off + ctypes.sizeof(pe_hdr)
	coff_hdr = get_struct(image_data, coff_off, COFF_Header)
	#coff_hdr.coff_print()
	
	if coff_hdr.SizeOfOptionalHeader :
		opt_off = coff_off + ctypes.sizeof(coff_hdr)
		
		if image_data[opt_off:opt_off + 2] == b'\x0B\x02' : # 0x010B - PE32, 0x020B - PE32+ (64 bit)
			opt_hdr = get_struct(image_data, opt_off, Optional_Header64)
		else :
			opt_hdr = get_struct(image_data, opt_off, Optional_Header)
			
		#opt_hdr.opt_print()
		
		imag_size   += opt_hdr.SizeOfHeaders
		
		data_dir_off = opt_off + ctypes.sizeof(opt_hdr)
		
		for ix in range(opt_hdr.NumberOfRvaAndSizes) :
			datadir_hdr = get_struct(image_data, data_dir_off, Data_Directory)
			#datadir_hdr.datadir_print(ix + 1)
			
			if ix == 4 : # Security Directory is the 5th
				sig_off  = datadir_hdr.VirtualAddress
				sig_size = datadir_hdr.Size
			
			data_dir_off += 8 # ctypes.sizeof(datadir_hdr)
		
		sect_off = opt_off + coff_hdr.SizeOfOptionalHeader
	
	else :
		sect_off = coff_off + ctypes.sizeof(coff_hdr)
	
	for ix in range(coff_hdr.NumberOfSections) :
		sect_hdr = get_struct(image_data, sect_off, Section_Header)
		#sect_hdr.sec_print()
		sect_off += 0x28 # ctypes.sizeof(sect_hdr)
		
		imag_size += sect_hdr.SizeOfRawData
	
	if all_content and sig_off :
		imag_size = sig_off + sig_size
	elif sig_included and sig_off and sig_off == imag_size : # Add signing block only when part of this image.
		imag_size += sig_size
	
	if imag_size :
		return imag_size
	else :
		return 2

def pe_checksum (image_data) :
	
	# From pefile
	
	checksum = 0
	top_val  = 2**32
	old_checksum    = 0
	checksum_offset = 0xFFFFFFFF
	
	mz_found, mz_start = mz_off(image_data, 0)
	
	if not mz_found :
		return "Not a PE file!\n"
	
	img_size = image_size(image_data, "full")
	#img_data = image_data[mz_start:]
	img_data = image_data[mz_start:mz_start + img_size]
	
	dos_hdr  = get_struct(image_data, mz_start, DOS_Header)
	#dos_hdr.dos_print()
	
	pe_off   = dos_hdr.e_lfanew
	pe_hdr   = get_struct(image_data, pe_off, PE_Header)
	#pe_hdr.pe_print()
	
	coff_off = pe_off + 4 # pe_off + ctypes.sizeof(pe_hdr)
	coff_hdr = get_struct(image_data, coff_off, COFF_Header)
	#coff_hdr.coff_print()
	
	if coff_hdr.SizeOfOptionalHeader :
		opt_off = coff_off + ctypes.sizeof(coff_hdr)
		
		if image_data[opt_off:opt_off + 2] == b'\x0B\x02' : # 0x010B - PE32, 0x020B - PE32+ (64 bit)
			opt_hdr = get_struct(image_data, opt_off, Optional_Header64)
		else :
			opt_hdr = get_struct(image_data, opt_off, Optional_Header)
		
		checksum_offset = opt_off + 0x40
		#print("%0.2X" % checksum_offset)
		old_checksum    = int.from_bytes(img_data[checksum_offset:checksum_offset + 4], 'little')
	
	# Verify the data is dword-aligned. Add padding if needed
	#
	file_size = len(img_data)
	remainder = int(file_size % 4)
	data      = img_data + ( b'\x00' * ((4-remainder) * ( remainder != 0 )) )
	len_data  = len(data)
	
	#print("%0.2X - %0.2X - %0.2X" % (img_size, file_size, len_data))
	
	for idx in range(0, len_data, 4) : # int(len_data / 4)
		
		# Skip the checksum field
		#
		if idx == checksum_offset : # int(checksum_offset / 4)
			continue
		
		dword    = struct.unpack('I', data[idx:idx + 4])[0] # idx*4
		checksum = (checksum & 0xFFFFFFFF) + dword + (checksum>>32)
		
		if checksum > top_val :
			checksum = (checksum & 0xFFFFFFFF) + (checksum >> 32)
	
	checksum = (checksum & 0xFFFF) + (checksum >> 16)
	checksum = (checksum) + (checksum >> 16)
	checksum = checksum & 0xFFFF
	
	# The length is the one of the original data, not the padded one
	#
	checksum += file_size
	
	return old_checksum, checksum

def base_in_image (image_data, offset) :
	
	image_base = 0x400000 # This is the usual size
	
	mz_found, mz_start = mz_off(image_data, 0)
	
	if not mz_found :
		return image_base
		
	dos_hdr  = get_struct(image_data, mz_start, DOS_Header)
	#dos_hdr.dos_print()
	
	pe_off   = dos_hdr.e_lfanew
	pe_hdr   = get_struct(image_data, pe_off, PE_Header)
	#pe_hdr.pe_print()
	
	coff_off = pe_off + 4 # pe_off + ctypes.sizeof(pe_hdr)
	coff_hdr = get_struct(image_data, coff_off, COFF_Header)
	#coff_hdr.coff_print()
	
	if coff_hdr.SizeOfOptionalHeader :
		opt_off = coff_off + ctypes.sizeof(coff_hdr)
		
		if image_data[opt_off:opt_off + 2] == b'\x0B\x02' : # 0x010B - PE32, 0x020B - PE32+ (64 bit)
			opt_hdr = get_struct(image_data, opt_off, Optional_Header64)
		else :
			opt_hdr = get_struct(image_data, opt_off, Optional_Header)
		
		#print("%0.2X" % opt_hdr.ImageBase)
		image_base   = opt_hdr.ImageBase
		data_dir_off = opt_off + ctypes.sizeof(opt_hdr)
		
		for ix in range(opt_hdr.NumberOfRvaAndSizes) :
			datadir_hdr = get_struct(image_data, data_dir_off, Data_Directory)
			#datadir_hdr.datadir_print(ix + 1)
			data_dir_off += 8 # ctypes.sizeof(datadir_hdr)
		
		sect_off = opt_off + coff_hdr.SizeOfOptionalHeader
	
	else :
		sect_off = coff_off + ctypes.sizeof(coff_hdr)
	
	rsrc_off = 0 # Initialized for later use
	
	for ix in range(coff_hdr.NumberOfSections) :
		sect_hdr = get_struct(image_data, sect_off, Section_Header)
		#sect_hdr.sec_print()
		sect_off += 0x28 # ctypes.sizeof(sect_hdr)
		
		sect_raw_off  = sect_hdr.PointerToRawData
		sect_raw_size = sect_hdr.SizeOfRawData
		
		if sect_raw_off <= offset < (sect_raw_off + sect_raw_size) :
			image_base += sect_hdr.VirtualAddress - sect_hdr.PointerToRawData
	
	return image_base

def rom_info_scan (rom_data, rom_offset) :
	
	rom_found  = False
	t_rom_pat  = re.compile(br'((\x55\xAA|\x56\x4E)|\x77\xBB)') # 55AA for regular ROMs, 564E and 77BB for Nvidia special ROMs
	
	while not rom_found :
		t_rom_match = t_rom_pat.search(rom_data, rom_offset)
		
		if t_rom_match is None :
			#print("No ROM found!\n")
			#exit()
			return (False, 0, 0, b'', "", 0, 0)
		
		(rom_sig_start, rom_sig_end) = t_rom_match.span()
		rom_pcir_start = int.from_bytes(rom_data[rom_sig_start + 0x18:rom_sig_start + 0x1A], 'little')
		#print("0x%0.2X - 0x%0.2X" % (rom_sig_start, rom_pcir_start))
		
		if rom_pcir_start == 0 :
			
			if rom_data[rom_sig_start + 0x20:rom_sig_start + 0x24] == b'PCIR' :
				rom_pcir_start = 0x20
			
			else :
				rom_pnp_start = int.from_bytes(rom_data[rom_sig_start + 0x1A:rom_sig_start + 0x1C], 'little')
				rom_pnp_off   = rom_sig_start + rom_pnp_start
				rom_pnp_str   = rom_data[rom_pnp_off:rom_pnp_off + 4]
				
				# Dont' add rom_pnp_start, it will produce false results
				if rom_pnp_str != b'$PnP' :
					#print("No PnP\n")
					rom_offset = rom_sig_start + 2
					continue
		
		rom_pcir_off = rom_sig_start + rom_pcir_start
		rom_pcir_str = rom_data[rom_pcir_off:rom_pcir_off + 4]
		#print (rom_pcir_str)
		
		if rom_pcir_start and rom_pcir_str not in [b'PCIR', b'NPDS', b'RGIS'] : # Last two for Nvidia
			#print("No PCIR\n")
			rom_offset = rom_sig_start + 2
			continue
		
		## Only first image needed
		rom_found = True
	
	#print("Found ROM at offset 0x%0.2X \n" % rom_sig_start)
	if rom_pcir_start :
		rom_id_bin   = rom_data[rom_pcir_off + 4:rom_pcir_off + 8]
		rom_id_hex   = id_from_bin(rom_id_bin, "hex")
		rom_last_img = ord(rom_data[rom_pcir_off + 0x15:rom_pcir_off + 0x16]) & 0x80
	
	else :
		rom_pcir_off = rom_sig_start + 0x20
		rom_id_bin   = b'\x00\x00\x00\x00'
		rom_id_hex   = "00000000"
		rom_last_img = 0x80
	
	rom_sig  = rom_data[rom_sig_start:rom_sig_start + 2]
	efi_test = rom_data[rom_sig_start + 4:rom_sig_start + 8]
	
	if rom_sig == b'\x77\xBB' :
		rom_size = 0 # The size is stored in RGIS struct
	elif rom_sig == b'\x56\x4E' or efi_test == b'\xF1\x0E\x00\x00' :
		rom_size = int.from_bytes(rom_data[rom_sig_start + 2:rom_sig_start + 4], 'little') * 0x200
	else :
		rom_size = ord(rom_data[rom_sig_start + 2:rom_sig_start + 3]) * 0x200
	
	npde_test1 = rom_data[rom_pcir_off + 0x20:rom_pcir_off + 0x24]
	npde_test2 = rom_data[rom_pcir_off + 0x24:rom_pcir_off + 0x28]
	npde_found = False
	
	if npde_test1 == b'NPDE' :
		#print("NPDE is present.")
		npde_found   = True
		npde_off     = rom_pcir_off + 0x20
		rom_last_img = ord(rom_data[npde_off + 0xA:npde_off + 0xB]) & 0x80
		npde_size    = int.from_bytes(rom_data[npde_off + 8:npde_off + 0xA], 'little') * 0x200
	
	elif npde_test2 == b'NPDE' :
		#print("NPDE is present.")
		npde_found   = True
		npde_off     = rom_pcir_off + 0x24
		rom_last_img = ord(rom_data[npde_off + 0xA:npde_off + 0xB]) & 0x80
		npde_size    = int.from_bytes(rom_data[npde_off + 8:npde_off + 0xA], 'little') * 0x200
	
	if not rom_pcir_start :
		return (rom_found, rom_sig_start, rom_pcir_off, rom_id_bin, rom_id_hex, rom_last_img, rom_size)
	
	rom_size_ds = int.from_bytes(rom_data[rom_pcir_off + 0x10:rom_pcir_off + 0x12], 'little') * 0x200
	
	if rom_size_ds and rom_size != rom_size_ds :
		#print("\nDifferent sizes in ROM header!\n")
		size_test = rom_sig_start + rom_size_ds
		rom_test  = rom_data[size_test:size_test + 2]
		rom_probe = rom_data[size_test - 1:size_test]
		
		if rom_size == 0 or rom_test in [b'\x55\xAA', b'\x56\x4E', b'\x77\xBB'] or (rom_test == b'' and rom_probe != b'') :
			rom_size = rom_size_ds
	
	#print("%0.2X" % rom_size)
	
	if npde_found and npde_size and rom_size != npde_size :
		#print("  Different sizes in PCI structure and NPDE structure of Legacy ROM!\n")
		#print("%0.2X\n" % npde_size)
		
		rom_end_npde  = rom_sig_start + npde_size
		rom_test_npde = rom_data[rom_end_npde:rom_end_npde + 2]
		
		## If NPDE size is the right one, there is one container for all ROMs.
		if rom_test_npde in [b'\x55\AA', b'\x56\x4E', b'\x77\xBB'] :
			#print("  The Legacy ROM appears to be a container for all images.\n")
			rom_size = npde_size
	
	# Fix Marvell crap, again and again.
	if rom_id_hex[:4] == "1B4B" :
		rom_end_test = rom_sig_start + rom_size
		rom_end_prob = rom_sig_start + rom_size - 0x200
		
		chk_test = sum(bytearray(rom_data[rom_sig_start:rom_end_test])) & 0xFF
		
		#print(chk_test)
		
		if chk_test != 0 or rom_data[rom_end_test - 0x30:rom_end_test - 1] != b'\x00' * 0x2F :
			#print("Marvell faulty?")
			
			chk_prob = sum(bytearray(rom_data[rom_sig_start:rom_end_prob])) & 0xFF
			
			#print(chk_prob)
			
			if chk_prob == 0 and rom_data[rom_end_prob - 0x30:rom_end_prob - 1] == b'\x00' * 0x2F :
				#print("\n Wrong size in header. Must be 0x200 smaller. Bad Marvell! \n")
				rom_size -= 0x200
	
	if rom_size == 0 : # For dummy ROM images that have empty size
		rom_size = 0x200
	
	rom_end   = rom_sig_start + rom_size
	
	return (rom_found, rom_sig_start, rom_pcir_off, rom_id_bin, rom_id_hex, rom_last_img, rom_size)

def rom_info(rom_data, offset, get_info) :
	t_position = offset
	ifr_header = False
	rom_found  = False
	t_old_type = False
	t_rom_pat  = re.compile(br'\x55\xAA')
	mini_me    = True if get_info == "mini" else False
	basic_me   = True if get_info == "basic" else False
	#55AA for regular ROMs, 564E and 77BB for Nvidia special ROMs
	#NVGI for IFR, 40RB for X, NVLS for Y, NVLB for Z
	#4D5A or 565A for PE
	
	## Checking for Nvidia IFR header
	nv_ifr_test = rom_data[t_position:t_position + 4]
	
	if nv_ifr_test == b'NVGI' :
		ifr_header = True
		ifr_size   = int.from_bytes(rom_data[t_position + 0x14:t_position + 0x16], 'little')
		
		if ifr_size < 0x100 and rom_data[t_position + 0x4000:t_position + 0x4004] == b'RFRD' :
			ifr_size = int.from_bytes(rom_data[t_position + 0x4008:t_position + 0x400C], 'little')
		
		t_position += ifr_size
		
		if mini_me :
			print(Fore.GREEN + "Found Nvidia IFR header before ROM start, size 0x%X\n" % ifr_size + Fore.RESET)
			ifr_id = id_from_bin(rom_data[t_position + 0xC:t_position + 0x10], "string")
			print(Fore.GREEN + "ID of IFR header  = %s\n" % ifr_id + Fore.RESET)
	
	## Not really needed, but it is safe. The ROM should start at 00 or at ifr_size.
	while not rom_found :
		
		t_rom_match = t_rom_pat.search(rom_data, t_position)
		
		if t_rom_match is None :
			
			if basic_me :
				return False
			
			print(Fore.RED + "No ROM found!\n" + Fore.RESET)
			file_dec = "%s_decompr.bin" % file_rom
			
			if not os.path.isfile(file_dec) and fileExtension not in ['.efi', '.ffs'] :
				print(Fore.RED + "Trying direct decompression...\n" + Fore.RESET)
				decomp = subprocess.call(["UEFIRomExtract", file_dir, file_dec], shell=True)
				print("")
				
				if os.path.isfile(file_dec) :
					print(Fore.YELLOW + "File " + file_dec + " was written! \n" + Fore.RESET)
			
			sys.exit()
		
		(t_start_match, t_end_match) = t_rom_match.span()
		t_start_pcir = int.from_bytes(rom_data[t_start_match + 0x18:t_start_match + 0x1A], 'little')
		#print("0x%0.2X - 0x%0.2X" % (t_start_match, t_start_pcir))
		
		if t_start_pcir == 0 :
			t_start_pnp = int.from_bytes(rom_data[t_start_match + 0x1A:t_start_match + 0x1C], 'little')
			t_pnp_off   = t_start_match + t_start_pnp
			t_pnp_str   = rom_data[t_pnp_off:t_pnp_off + 4]
			
			if t_pnp_str != b'$PnP' :
				#print("No PnP\n")
				t_position = t_start_match + 2
				continue
			
			t_start_pcir = 0x20
		
		t_pcir_off = t_start_match + t_start_pcir
		t_pcir_str = rom_data[t_pcir_off:t_pcir_off + 4]
		#print (t_pcir_str)
		
		if t_pcir_str != b'PCIR' :
			#print("No PCIR\n")
			t_position = t_start_match + 2
			continue
		
		## Only first image needed
		rom_found = True
	
	if basic_me :
		return True
	
	## Get some ROM related info
	t_pcir_id_bin = rom_data[t_pcir_off + 4:t_pcir_off + 8]
	#t_pcir_id_hex = binascii.hexlify(t_pcir_id_bin[::-1]).decode('utf-8').upper()
	t_ven_id, t_did_id = id_from_bin(t_pcir_id_bin, "id_list")
	
	if mini_me :
		## Only Nvidia IFR found so far as header before ROM
		if t_start_match and not ifr_header :
			print(Fore.MAGENTA + "Found Unknown header before ROM start, size 0x%X\n" % t_start_match + Fore.RESET)
		
		print(Style.BRIGHT + Fore.CYAN + "ID of ROM file    = %s-%s\n" % (t_ven_id, t_did_id)  + Fore.RESET + Style.NORMAL)
		
		if t_ven_id == "10DE" and t_did_id in ['0FF2', '11BF'] :
			print(Style.BRIGHT + Fore.YELLOW + "Nvidia GRID K1/K2 was detected! Using Multi-Display GOP.\n" + Fore.RESET + Style.NORMAL)
	
	## Get boundaries and sizes
	if rom_data[t_start_match + 4:t_start_match + 8] == b'\xF1\x0E\x00\x00' :
		## This part is only for extraction of single EFI ROM files
		t_rom_size  = 0
		t_rom_end   = t_start_match
		t_efi_found = True
		t_efi_begin = t_start_match
		
	else :
		## Calculate first ROM size. Sometimes the size from PCI DS is the right one.
		t_rom_size    = ord(rom_data[t_start_match + 2:t_start_match + 3]) * 0x200
		t_rom_size_ds = int.from_bytes(rom_data[t_pcir_off + 0x10:t_pcir_off + 0x12], 'little') * 0x200
		
		if t_rom_size != t_rom_size_ds :
			print(Fore.MAGENTA + "Different sizes in ROM header and PCI structure of Legacy ROM!\n" + Fore.RESET)
			t_rom_end_ds = t_start_match + t_rom_size_ds
			rom_test_ds  = rom_data[t_rom_end_ds:t_rom_end_ds + 2]
			
			if rom_test_ds in [b'\x55\xAA', b'\x56\x4E'] :
				t_rom_size = t_rom_size_ds
		
		## If all the images are contained in first ROM.
		#if rom_data[t_pcir_off + 0x20:t_pcir_off + 0x24] == b'NPDE' :
		#	t_npde_size = int.from_bytes(rom_data[t_pcir_off + 0x28:t_pcir_off + 0x2A], 'little') * 0x200
		#	
		#	if t_rom_size != t_npde_size :
		#		print(Fore.MAGENTA + "Different sizes in PCI structure and NPDE structure of Legacy ROM!\n" + Fore.RESET)
		#		## If the EFI image should be placed between Legacy and Special images, thus breaking the big container.
		#		t_rom_end_npde = t_start_match + t_npde_size
		#		rom_test_npde  = binascii.hexlify(rom_data[t_rom_end_npde:t_rom_end_npde + 2]).decode('utf-8').upper()
		#		if rom_test_npde in ['55AA', '564E'] :
		#			t_rom_size = t_npde_size
		
		t_rom_end   = t_start_match + t_rom_size
	
	## Not really needed, but it is safe. EFI should start at t_rom_end.
	## Assume that EFI follows OROM and that there is nothing in between.
	## The only structure found so far was Legacy ROM + EFI ROM, no other images in between.
	
	t_pat_efi   = re.compile(br'\x55\xAA..\xF1\x0E\x00\x00', re.DOTALL)
	t_match_efi = t_pat_efi.search(rom_data, t_rom_end)
	
	if t_match_efi is not None :
		(t_start_efi_match, t_end_efi_match) = t_match_efi.span()
		t_efi_found = True
		t_efi_begin = t_start_efi_match
		
		# Scan for special images between ROM and GOP
		while rom_data[t_rom_end:t_rom_end + 2] == b'\x56\x4E' :
			npds_ptr  = int.from_bytes(rom_data[t_rom_end + 0x18:t_rom_end + 0x1A], 'little')
			npds_off  = t_rom_end + npds_ptr
			npds_size = int.from_bytes(rom_data[npds_off + 0x10:npds_off + 0x12], 'little') * 0x200
			npds_type = "%02Xh" % ord(rom_data[npds_off + 0x14:npds_off + 0x15])
			t_rom_end += npds_size
			
			if mini_me :
				print(Style.BRIGHT + Fore.YELLOW + "Found special image %s between ROM and EFI!\n" % npds_type + Fore.RESET)
		
		# Skip intermediate images for other vendors. Added only for extraction. They will be reported later.
		while t_ven_id not in ['1002', '10DE'] and rom_data[t_rom_end:t_rom_end + 2] == b'\x55\xAA' :
			temp_pcir = int.from_bytes(rom_data[t_rom_end + 0x18:t_rom_end + 0x1A], 'little')
			temp_off  = t_rom_end + temp_pcir
			
			if rom_data[temp_off:temp_off + 4] != b'PCIR' or rom_data[t_rom_end + 4:t_rom_end + 8] == b'\xF1\x0E\x00\x00' :
				break
			
			temp_size    = ord(rom_data[t_rom_end + 2:t_rom_end + 3]) * 0x200
			tmp_size_ds  = int.from_bytes(rom_data[temp_off + 0x10:temp_off + 0x12], 'little') * 0x200
			
			if temp_size != tmp_size_ds :
				t_rom_end_ds = t_rom_end + tmp_size_ds
				rom_test_ds  = rom_data[t_rom_end_ds:t_rom_end_ds + 2]
				
				if rom_test_ds in [b'\x55\xAA', b'\x56\x4E'] :
					temp_size = tmp_size_ds
			
			t_rom_end += temp_size
				
		if t_efi_begin != t_rom_end :
			print(Style.BRIGHT + Fore.RED + "Data between ROM and EFI! Please report it\n" + Fore.RESET)
			sys.exit()
		
	else :
		#t_start_efi_match = 0
		t_efi_found = False
		t_efi_begin = t_rom_end
	
	if t_efi_found :
		t_efi_size = int.from_bytes(rom_data[t_efi_begin + 2:t_efi_begin + 4], 'little') * 0x200
		
		if mini_me :
			return (t_efi_found, t_efi_begin, t_efi_size)
	else :
		if mini_me :
			return (t_efi_found, 0, 0)
		
		## Check for a dummy EFI image. If it starts with 564E, it is a special Nvidia image.
		## If it is dummy EFI, the first two bytes are 77BB.
		
		if t_ven_id == "10DE" :
			
			test_image = rom_data[t_efi_begin:t_efi_begin + 2]
			
			## Test for dummy EFI in Nvidia.
			if len(test_image) == 2 and test_image != b'\x56\x4E' : ## 55AA or 77BB = old structure or dummy
				pci_ds_efi   = int.from_bytes(rom_data[t_efi_begin + 0x18:t_efi_begin + 0x1A], 'little')
				pcir_efi_off = t_efi_begin + pci_ds_efi
				t_struct     = rom_data[pcir_efi_off:pcir_efi_off + 4]
				
				## Old images have the special Nvidia images as normal ROMs
				if test_image == b'\x55\xAA' and t_struct == b'PCIR' :
					print(Style.BRIGHT + Fore.YELLOW + "Old structure was found in special images!\n" + Fore.RESET + Style.NORMAL)
					t_old_type = True
					t_efi_size = 0
				## A dummy EFI should have only one of the following two structures.
				elif test_image == b'\x77\xBB' and t_struct in [b'NPDS', b'RGIS'] :
					print(Style.BRIGHT + Fore.YELLOW + "Dummy EFI image was found!\n" + Fore.RESET + Style.NORMAL)
					t_efi_size = int.from_bytes(rom_data[pcir_efi_off + 0x10:pcir_efi_off + 0x12], 'little') * 0x200
				## Not old image, not dummy, not special image. What can it be?
				else :
					print(Style.BRIGHT + Fore.RED + "Strange Nvidia image was found after ROM! Please report it!\n" + 
					Fore.RESET + Style.NORMAL)
					t_efi_size = 0
			
			## No more images or Nvidia special image.
			else :
				t_efi_size = 0
		
		## Is AMD and AMD has no dummy EFI and no other images, from what I have seen.
		else :
			t_efi_size = 0
			
			mc_off_list = [0x1A000, 0x1B800, 0x1C000]
			
			for mc_off_idx in mc_off_list :
				
				mc_off     = t_start_match + mc_off_idx
			
				if rom_data[mc_off:mc_off + 4] == b'MCuC' :
					print(Style.BRIGHT + Fore.YELLOW + "AMD microcode was found at offset 0x%0.2X!\n" % mc_off + 
					Fore.RESET + Style.NORMAL)
					break
				
	return (t_old_type, t_start_match, t_pcir_off, t_pcir_id_bin, t_rom_size, t_efi_found, t_efi_begin, t_efi_size)

def efi_version(t_efi_dump) :
	t_gop_type = ""
	t_nv_type  = ""
	t_version  = ""
	t_efi_info_string = ""
	
	## AMD GOP
	pat_amd   = re.compile(br'\x44\x00\x72\x00\x69\x00\x76\x00\x65\x00\x72\x00\x20\x00\x52\x00\x65\x00\x76\x00') ## D.r.i.v.e.r. .R.e.v.
	match_amd = pat_amd.search(t_efi_dump)
	
	if match_amd is not None :
		(ver_start_match, ver_end_match) = match_amd.span()
		t_gop_type = "AMD"
		t_version  = lib_build = date = build = changelist = "0"
		bios_idtf_gop = bios_idtf_rom = 0
		
		# t_version = t_efi_dump[ver_end_match + 2: ver_end_match + 0x1A].decode('utf-16', 'ignore').upper()
		
		# # print(t_version)
		# # print(t_version[8:9])
		
		# # Max 12 chars and 5 groups ?
		
		# # 1. or 2.  = Except 0.0.1.18
		# # dd.       = Except 0.0.1.18 , 2.x.0.0.0
		# # 0.        = Except 0.0.1.18 , 1.55.2.0.0
		# # 0. or 15. = Except 0.0.1.18
		# # 0 or dd   = Except 0.0.1.18
		
		# # Either x.xx.0.0.0 or x.xx.0.15.xx
		# # Except 0.0.1.18 , 1.55.2.0.0, 2.x.0.0.0
		
		# if t_version[3:4] == "." : # For x.x.x.x.x or x.x.x.xx.xx or 0.0.1.18
			
			# if t_version[:1] == "0" : # For 0.0.1.18
				# t_version = t_version[:8]
			
			# elif t_version[7:8] == "." : # For x.x.x.x.x
				# t_version = t_version[:9]
			
			# else : # For x.x.x.xx.xx
				# t_version = t_version[:11]
		
		# elif t_version[8:9] == "." : # For x.xx.x.x.x
			
			# t_version = t_version[:10]
		
		# #else : t_version = t_version[:12] # for x.xx.x.xx.xx
		
		# verslen = 2 * len(t_version)
		# lib     = ver_end_match + 2 + verslen + 2
		# test    = t_efi_dump[lib:lib + 6].decode('utf-16', 'ignore')
		
		# if test == "Lib" : ## "4C0069006200" # Version followed by LibBuildNo:xxxx, found in all customs and vanilla 1.26.0.0.0, 1.39.0.0.0, 1.40.0.15.24, 1.45.0.15.31, 1.50.0.15.36, 1.52.0.0.0
			# #print("Lib")
			# lib_build = t_efi_dump[lib + 0x16:lib + 0x1E].decode('utf-16', 'ignore')
			# date  = t_efi_dump[lib + 0x20:lib + 0x48].decode('utf-16', 'ignore')
		
		# elif test.isalpha() : # Version followed by date, found in all other vanilla and 1.51.0.15.38_custom
			# #print("None")
			# lib_build = "----"
			# date  = t_efi_dump[lib:lib + 0x28].decode('utf-16', 'ignore')
		
		# elif test.isnumeric() : # Version followed by build, found in 1.23.0.15.15 and older.
			# #print("Old")
			# lib_build = t_efi_dump[lib:lib + 0xC].decode('utf-16', 'ignore')
			
			# try :
				# dot_off  = lib_build.index(".")
				# date_off = lib + dot_off * 2 + 2
				# lib_build = lib_build[:dot_off]
			# except :
				# date_off = lib + 0xE
				
			# date  = t_efi_dump[date_off:date_off + 0x28].decode('utf-16', 'ignore')
		
		# It was per Sir Pluto's order that we should conquer AMD once and for all!
		# Rock me AMDeus!
		
		t_version = t_efi_dump[ver_end_match + 2: ver_end_match + 0x64].split(b'\x2E\x00') # Split at 0x2E00 character
		
		for v in range(len(t_version)) :
			t_version[v] = t_version[v].decode('utf-16', 'ignore') # Decode Version + Lib + Date
		
		if t_version[0] == '0' : # Set Version length based on Major number
			ver_len = 4
		else :
			ver_len = 5
		
		if t_version[ver_len][:3] == "Lib" : ## "4C0069006200" # Version followed by LibBuildNo:xxxx, found in all customs and vanilla 1.26.0.0.0, 1.39.0.0.0, 1.40.0.15.24, 1.45.0.15.31, 1.50.0.15.36, 1.52.0.0.0
			#print("Lib")
			lib_build = t_version[ver_len][11:]
			date = t_version[ver_len + 1] # xxx xx xxxx
			time = t_version[ver_len + 2][:8] # xx:xx:xx
		
		elif t_version[ver_len][:3].isalpha() : # Version followed by date, found in all other vanilla and 1.51.0.15.38_custom
			#print("None")
			lib_build = "----"
			date = t_version[ver_len] # xxx xx xxxx
			time = t_version[ver_len + 1][:8] # xx:xx:xx
		
		elif t_version[ver_len].isnumeric() : # Version followed by build, found in 1.23.0.15.15 and older.
			#print("Old")
			lib_build = t_version[ver_len]
			date = t_version[ver_len + 1] # xxx xx xxxx
			time = t_version[ver_len + 2][:8] # xx:xx:xx
		
		t_version = '.'.join(map(str, t_version[:ver_len])) # Convert first parts (x.x.x.x or x.x.x.x.x) to version string
		date = date + " " + time
		
		print(Style.BRIGHT + Fore.RED + "AMD GOP" + Fore.WHITE + " %s  " % t_version + 
		Fore.RED + "LibBuild" + Fore.WHITE + " %s  " % lib_build + 
		Fore.RED + "Dated:" + Fore.WHITE + " %s" % date.replace(".", " ") + 
		Fore.RESET + Style.NORMAL)
		
		t_efi_info_string = t_version + " - " + lib_build.replace("-", "*") + " - " + date.replace(".", " ")
		
		## BIOS_IDTF + AMD_Build + AMD_CL. Each one takes 0x18 bytes.
		pat_idtf   = re.compile(br'\x42\x49\x4F\x53\x5F\x49\x44\x54\x46') ## BIOS_IDTF
		match_idtf = pat_idtf.search(t_efi_dump)
		
		if match_idtf is not None :
			(idtf_start_match, idtf_end_match) = match_idtf.span()
			bios_idtf_gop = int.from_bytes(t_efi_dump[idtf_start_match + 0xA:idtf_start_match + 0xE], 'little')
		else :
			idtf_start_match = 0
		
		if idtf_start_match and t_efi_dump[idtf_start_match + 0x18:idtf_start_match + 0x21] == b'AMD_Build' :
			bd_start_match = idtf_start_match + 0x18
			build = int.from_bytes(t_efi_dump[bd_start_match + 0xA:bd_start_match + 0x18], 'little')
		else :
			pat_bd   = re.compile(br'\x41\x4D\x44\x5F\x42\x75\x69\x6C\x64') ## AMD_Build
			match_bd = pat_bd.search(t_efi_dump)
			
			if match_bd is not None :
				(bd_start_match, bd_end_match) = match_bd.span()
				build = int.from_bytes(t_efi_dump[bd_start_match + 0xA:bd_start_match + 0x18], 'little')
			else :
				bd_start_match = 0
		
		if bd_start_match and t_efi_dump[bd_start_match + 0x18:bd_start_match + 0x1E] == b'AMD_CL' :
			cl_start_match = bd_start_match + 0x18
			changelist = int.from_bytes(t_efi_dump[cl_start_match + 0xA:cl_start_match + 0x18], 'little')
		else :
			pat_cl   = re.compile(br'\x41\x4D\x44\x5F\x43\x4C') ## AMD_CL
			match_cl = pat_cl.search(t_efi_dump)
			
			if match_cl is not None :
				(cl_start_match, cl_end_match) = match_cl.span()
				changelist = int.from_bytes(t_efi_dump[cl_start_match + 0xA:cl_start_match + 0x18], 'little')
		
		# TODO Use ATOMBIOS Tables to get CRC offset.
		pat_lg   = re.compile(br'\x41(\x4D\x44|\x54\x49)\x20\x41\x54\x4F\x4D\x42\x49\x4F\x53\x00') ## AMD ATOMBIOS or ATI ATOMBIOS.
		match_lg = pat_lg.search(t_efi_dump)
		
		if match_lg is not None :
			(lg_start_match, lg_end_match) = match_lg.span()
			#print("\nAMD GOP has tables! Customized GOP with legacy parts!")
			bios_idtf_rom = int.from_bytes(t_efi_dump[lg_start_match + 0xD:lg_start_match + 0x11], 'little')
			#bios_idtf_rom = " ## Legacy BIOS_IDTF 0x" + bios_idtf_rom
		
			print(Style.BRIGHT + Fore.RED + "\nAMD_Build" + Fore.WHITE + " %s  " % build + 
			Fore.RED + "AMD_ChangeList" + Fore.WHITE + " %s  " % changelist + 
			Fore.RED + "GOP BIOS_IDTF" + Fore.WHITE + " 0x%0.8X " % bios_idtf_gop + 
			"\n\nAMD GOP has tables! Customized GOP with legacy parts!!" + 
			Fore.RED + "\n\nLegacy BIOS_IDTF" + Fore.WHITE + " 0x%0.8X " % bios_idtf_rom + 
			Fore.RESET + Style.NORMAL)
			
			t_efi_info_string += " - " + "%s" % build + " - " + "%s" % changelist + " - " + "0x%0.8X" % bios_idtf_gop + \
			" - " + "0x%0.8X" % bios_idtf_rom
		
		else :
			print(Style.BRIGHT + Fore.RED + "\nAMD_Build" + Fore.WHITE + " %s  " % build + 
			Fore.RED + "AMD_ChangeList" + Fore.WHITE + " %s  " % changelist + 
			Fore.RED + "GOP BIOS_IDTF" + Fore.WHITE + " 0x%0.8X " % bios_idtf_gop + 
			Fore.RESET + Style.NORMAL)
			
			t_efi_info_string += " - " + "%s" % build + " - " + "%s" % changelist + " - " + "0x%0.8X" % bios_idtf_gop
		
		## IDs in GOP. Works only with newer GOPs.
		
		# Alternative for ID search
		#pat_id_ptr   = re.compile(br'\x01\x01\x00{6}.{4}\x00{4}\x01\x02\x00{6}.{4}\x00{4}\x01\x03\x00{6}.{4}\x00{4}\x01\x04\x00{6}.{4}\x00{4}', re.DOTALL)
		#match_id_ptr = pat_id_ptr.search(t_efi_dump)
		#
		#if match_id_ptr is not None :
		#	(id_ptr_start_match, id_ptr_end_match) = match_id_ptr.span()
		#	id_start_match = int.from_bytes(t_efi_dump[id_ptr_start_match + 8:id_ptr_start_match + 0xC], 'little')
		
		pat_id   = re.compile(br'\x00{8}\x88\x68\x00{6}')
		match_id = pat_id.search(t_efi_dump)
		
		if match_id is not None :
			(id_start_match, id_end_match) = match_id.span()
			ids_list  = ""
			step      = id_start_match + 8
			name_base = base_in_image(t_efi_dump, step)
			id_rebase = False
			
			while True :
				
				if id_rebase :
					check_null = t_efi_dump[step:step + 8]
					
					if check_null == b'\x00' * 8 : # "00000000000000"
						break
				
				else :
					check_null = t_efi_dump[step + 2:step + 8]
					
					if check_null != b'\x00' * 6 : # "000000000000"
						break
				
				id = "1002-" + binascii.hexlify(t_efi_dump[step:step + 2][::-1]).decode('utf-8').upper()
				
				if id == "1002-0000" :
					# step += 0x10 # You failed! It was actually last ID & 0xFFF0
					# continue
					
					if t_efi_dump[step + 8:step + 12] == b'\x00' * 4 :
						step += 0x10
						continue
					else :
						id = "1002-" + binascii.hexlify(t_efi_dump[step - 0x10:step - 0xE][::-1]).decode('utf-8').upper()
						id = id[:-1] + "0"
				
				if id_rebase or id == "1002-0101" : # Range of IDs
					#break # You were wrong!
					id_rebase = True
					id = "1002-" + binascii.hexlify(t_efi_dump[step + 2:step + 4][::-1]).decode('utf-8').upper()
					
					if id == "1002-0000" :
						step += 0x10
						continue
					
					else :
						
						first_id = int.from_bytes(t_efi_dump[step + 2:step + 4], 'little')
						last_id  = int.from_bytes(t_efi_dump[step + 4:step + 6], 'little')
						
						for idx in range(first_id, last_id + 1) :
							id = "1002-%0.4X" % idx
							name_off1  = int.from_bytes(t_efi_dump[step + 8:step + 0xC], 'little') + name_base
							name_off2  = int.from_bytes(t_efi_dump[name_off1 + 8:name_off1 + 0xC], 'little') + name_base
							name_str  = get_name(t_efi_dump, name_off2, 'utf-8')
							
							ids_list += id + "  =  " + name_str + "\n"
						
						step += 0x10
						continue
				
				name_off  = int.from_bytes(t_efi_dump[step + 8:step + 0xC], 'little') + name_base
				name_str  = get_name(t_efi_dump, name_off, 'utf-8')
				
				ids_list += id + "  =  " + name_str + "\n"
				step     += 0x10
			
			with open("%s_temp/AMD_GOP_%s_IDs.txt" % (file_rom, t_version), "a") as myfile :
				myfile.write(ids_list)
		
		# For Vega GOP
		
		pat_id   = re.compile(br'\xDD\x6B\xE0\xFF\x07\x61\xA6\x46\x7B\xB2\x5A\x9C\x7E\xC5\x27\x5C')
		match_id = pat_id.search(t_efi_dump[:0x1000])
		
		if match_id is not None :
			(id_start_match, id_end_match) = match_id.span()
			ids_list  = ""
			step      = id_start_match - 8
			name_base = base_in_image(t_efi_dump, step)
			id_rebase = False
			
			for x_step in range(0, 0x50, 0x10) :
				
				if t_efi_dump[step - x_step:step - x_step + 2] == b'\x10\x01' :
					#print("Eureka!")
					
					step = step - x_step
					
					while True :
						
						check_null = t_efi_dump[step:step + 4]
						
						if check_null == b'\x00' * 4 : # "00000000"
							break
						
						name_str = "Vega " + t_efi_dump[step:step + 1].hex() + "-" + t_efi_dump[step + 1:step + 2].hex()
						first_id = int.from_bytes(t_efi_dump[step + 2:step + 4], 'little')
						last_id  = int.from_bytes(t_efi_dump[step + 4:step + 6], 'little')
						
						for id in range(first_id, last_id + 1) :
							id       = "1002-%0.4X" % id
							ids_list += id + "  =  " + name_str + "\n"
						
						step     += 6
			
					with open("%s_temp/AMD_GOP_%s_IDs.txt" % (file_rom, t_version), "a") as myfile :
						myfile.write(ids_list)
					
					break
		
		## Names in GOP. Only AMD with GOPs newer than 1.34.0.0.0.
		#pat_name   = re.compile(br'\x41\x00\x6D\x00\x64\x00\x41\x00\x63\x00\x70\x00\x69\x00\x56\x00\x61\x00\x72\x00') ## A.m.d.A.c.p.i.V.a.r.
		#match_name = pat_name.search(t_efi_dump)
		#
		#if match_name is not None and int(t_version[2:4]) > 34 :
		#	#print("\nFound names")
		#	(name_start_match, name_end_match) = match_name.span()
		#	bin_test = t_efi_dump[name_end_match + 4:name_end_match + 0xE]
		#	str_test = bin_test.decode('utf-8', 'ignore')
		#	#print(bin_test)
		#	#print(str_test)
		#	
		#	if str_test == "CR has Bad" or bin_test == b'\x4C\x00\x4C\x00\x4C\x00\x4C\x00\x4C\x00' :
		#		#print("\nCR or LL")
		#		pat_name   = re.compile(br'\x00{4}\x65\x6E\x00{2}') ## ....en..
		#		match_name = pat_name.search(t_efi_dump)
		#		
		#		if match_name is not None :
		#			(name_start_match, name_end_match) = match_name.span()
		#			step = name_end_match
		#	
		#	else :
		#		#print("\nNewer names")
		#		step = name_end_match + 4
		#	
		#	gpu_list = ""
		#	gpu_char = t_efi_dump[step:step + 1]
		#	
		#	while True :
		#		gpu_name = ""
		#		
		#		while gpu_char != b'\x00' :
		#			gpu_name += gpu_char.decode('utf-8', 'ignore')
		#			step     += 1
		#			gpu_char = t_efi_dump[step:step + 1]
		#		
		#		if gpu_name[:11] in ['[ATI', 'Compromised', 'Protocol Er', 'Destination', 'ASSERT %a(%'] or len(gpu_name) < 3:
		#			break
		#		
		#		gpu_list += gpu_name + "\n"
		#						
		#		while gpu_char == b'\x00' :
		#			step     += 1
		#			gpu_char = t_efi_dump[step:step + 1]
		#		
		#	with open("%s_temp/AMD_GOP_%s_names.txt" % (file_rom, t_version), "a") as myfile :
		#			myfile.write(gpu_list)
			
		return (t_gop_type, "", t_version, t_efi_info_string)

	## Nvidia GOP
	pat_nv = re.compile(br'\x4E\x56\x2D\x55\x45\x46\x49\x2D\x42\x4C\x44\x2D\x49\x4E\x46\x4F') ## NV-UEFI-BLD-INFO
	match_nv = pat_nv.search(t_efi_dump)
	
	if match_nv is not None :
		(nv_start_match, nv_end_match) = match_nv.span()
		t_gop_type = "Nvidia"
		date      = t_efi_dump[nv_end_match + 8:nv_end_match + 0x13].decode('utf-8', 'ignore')
		t_version = t_efi_dump[nv_end_match + 0x18:nv_end_match + 0x1F].decode('utf-8', 'ignore')
		chg       = t_efi_dump[nv_end_match + 0x24:nv_end_match + 0x2C].decode('utf-8', 'ignore')
		var_test  = t_efi_dump[nv_end_match + 0x2D:nv_end_match + 0x31]
		
		if var_test == b'VAR:' : ## 5641523A
			id_test = t_efi_dump[nv_end_match + 0x31:nv_end_match + 0x3C]
			
			if id_test == b'VARIANT_ID=' :
				var = t_efi_dump[nv_end_match + 0x3C:nv_end_match + 0x4C].decode('utf-8', 'ignore')
			else :
				var = t_efi_dump[nv_end_match + 0x31:nv_end_match + 0x41].decode('utf-8', 'ignore')
			
			if var[-2:] == "01" :
				t_nv_type = "GT21x"
			elif var[-2:] == "02" :
				t_nv_type = "GF10x"
			elif var[-2:] == "03" :
				t_nv_type = "GF119"
			elif var[-2:] == "04" :
				t_nv_type = "GK1xx"
			elif var[-2:] == "05" :
				t_nv_type = "GM1xx"
			elif var[-2:] == "06" :
				t_nv_type = "GM2xx"
			elif var[-2:] == "07" :
				t_nv_type = "GP1xx"
			elif var[-2:] == "08" :
				t_nv_type = "GV1xx"
			elif var[-2:] == "09" :
				t_nv_type = "TU1xx"
			else :
				t_nv_type = "GXnew"
			
			if var[:12] != "000000000000" :
				t_nv_type += "_Strange"
			
			if var[12:14] == "01" :
				t_nv_type += "_MXM"
			elif var[12:14] == "02" :
				t_nv_type += "_Multi-Display"
			elif var[12:14] == "03" :
				t_nv_type += "_GOP-Override"
			elif var[12:14] != "00" :
				t_nv_type += "_Custom"
						
			var = "0x" + var + " = " + t_nv_type
		else :
			if re.search(br'\x4D\x58\x4D\x5F', t_efi_dump) is not None : ## MXM_ or MXM_V (\x56|\x76)
				t_nv_type = "GXxxx_MXM"
				var = "missing = GXxxx_MXM"
			else :
				t_nv_type = "GXxxx"
				var = "missing"
			
			#var = "missing" if t_nv_type == "GXxxx" else "missing = GXxxx_MXM"
		
		print(Style.BRIGHT + Fore.GREEN + "Nvidia GOP" + Fore.WHITE + " %s  " % t_version + 
		Fore.GREEN + "Variant" + Fore.WHITE + " %s \n\n" % var + 
		Fore.GREEN + "Dated:" + Fore.WHITE + " %s  " % date + 
		Fore.GREEN + "Changelist" + Fore.WHITE + " %s" % chg + 
		Fore.RESET + Style.NORMAL)
		
		t_efi_info_string = t_nv_type + " - " + t_version + " - " + date + " - " + chg
		
		return (t_gop_type, t_nv_type, t_version, t_efi_info_string)
	
	## Nvidia GOP older versions
	
	pat_nv = re.compile(br'\xD6\xDC\x9B\xE1\xDF\xA6\xE4\x4F\xB7\x53\xD6\x77\xC7\x24\x8B\x77\x70\x21\x0A\xCC\x39\x0B\xD8\x45\xB4\x69\xD0\x4E\x57\xB5\x22\xB3\xEE\x27\xE5\xF5\x83\xA2\x27\x41\x9A\x2F\xAF\xFA\xBF\x26\xDF\x70') ## Part of a hash or something
	match_nv = pat_nv.search(t_efi_dump)
	
	if match_nv is not None :
		
		(nv_start_match, nv_end_match) = match_nv.span()
		t_gop_type = "Nvidia"
		
		test_ver1  = int.from_bytes(t_efi_dump[nv_start_match - 0x18:nv_start_match - 0x14], 'little')
		test_ver2  = int.from_bytes(t_efi_dump[nv_start_match + 0x108:nv_start_match + 0x10C], 'little')
		
		if 0x10000 <= test_ver2 <= 0x100017 :
			t_version = "0x%0.5X" % test_ver2
		elif 0x10000 <= test_ver1 <= 0x100017 :
			t_version = "0x%0.5X" % test_ver1
		else :
			t_version = "unknown"
		
		if re.search(br'\x4D\x58\x4D\x5F', t_efi_dump) is not None : ## MXM_ or MXM_V (\x56|\x76)
			t_nv_type = "GXxxx_MXM"
			var = "missing = GXxxx_MXM"
		else :
			t_nv_type = "GXxxx"
			var = "missing"
		
		date = "missing"
		chg  = "missing"
		
		print(Style.BRIGHT + Fore.GREEN + "Nvidia GOP" + Fore.WHITE + " %s  " % t_version + 
		Fore.GREEN + "Variant" + Fore.WHITE + " %s \n\n" % var + 
		Fore.GREEN + "Dated:" + Fore.WHITE + " %s  " % date + 
		Fore.GREEN + "Changelist" + Fore.WHITE + " %s" % chg + 
		Fore.RESET + Style.NORMAL)
		
		t_efi_info_string = t_nv_type + " - " + t_version + " - " + date + " - " + chg
		
		return (t_gop_type, t_nv_type, t_version, t_efi_info_string)
	
	## Mac AMD
	pat_mac_ati = re.compile(br'\x41\x00\x54\x00\x49\x00\x20\x00\x52\x00\x61\x00\x64\x00\x65\x00\x6F\x00\x6E\x00\x20\x00\x55\x00\x47\x00\x41\x00\x20\x00\x44\x00\x72\x00\x69\x00\x76\x00\x65\x00\x72\x00') ## A.T.I. .R.a.d.e.o.n. .U.G.A. .D.r.i.v.e.r.
	pat_mac_amd = re.compile(br'\x41\x00\x4D\x00\x44\x00\x20\x00\x52\x00\x61\x00\x64\x00\x65\x00\x6F\x00\x6E\x00\x20\x00\x44\x00\x72\x00\x69\x00\x76\x00\x65\x00\x72\x00')
	# A.M.D. .R.a.d.e.o.n. .D.r.i.v.e.r.
	
	match_mac_amd = pat_mac_ati.search(t_efi_dump)
	
	if match_mac_amd is None :
		match_mac_amd = pat_mac_amd.search(t_efi_dump)
		
	if match_mac_amd is not None :
		(mac_start_match, mac_end_match) = match_mac_amd.span()
		t_gop_type = "Mac_AMD"
		t_version  = t_efi_dump[mac_end_match + 2:mac_end_match + 0x14].decode('utf-16', 'ignore')
		
		pat_mac_date = re.compile(br'\x45\x00\x46\x00\x49\x00\x43\x00\x6F\x00\x6D\x00\x70\x00\x69\x00\x6C\x00\x65\x00\x44\x00\x61\x00\x74\x00\x65\x00')
		match_mac_date = pat_mac_date.search(t_efi_dump)
		
		if match_mac_date is not None :
			(date_start_match, date_end_match) = match_mac_date.span()
			date = t_efi_dump[date_start_match - 0x18:date_start_match - 0xD].decode('utf-8', 'ignore')
			
			if date[:3].isnumeric() :
				date = t_efi_dump[date_end_match + 4:date_end_match + 0xF].decode('utf-8', 'ignore')
		
		else :
			date = "not found"
		
		print(Style.BRIGHT + Fore.RED + "Mac AMD GOP" + Fore.WHITE + " %s  " % t_version + Fore.RED + "Dated:" + 
		Fore.WHITE + " %s  " % date + Fore.RESET + Style.NORMAL)
		
		pat_mac_ver = re.compile(br'\x41(\x54|\x4D)(\x49|\x44)\x20\x52\x61\x64\x65\x6F\x6E\x20\x48\x44\x20') # ATI|AMD Radeon HD
		match_mac_ver = pat_mac_ver.search(t_efi_dump)
		
		if match_mac_ver is not None :
			(mac_start_ver, mac_end_ver) = match_mac_ver.span()
			ver_list = " ## "
			step     = mac_start_ver
			ver_char = t_efi_dump[step:step + 1]
			
			while True :
				ver_item = ""
				
				while ver_char != b'\x00' :
					ver_item += ver_char.decode('utf-8', 'ignore')
					step     += 1
					ver_char = t_efi_dump[step:step + 1]
				
				if len(ver_item) < 3:
					break
				
				ver_list += ver_item + " ## "
								
				while ver_char == b'\x00' :
					step     += 1
					ver_char = t_efi_dump[step:step + 1]
		
			print(Style.BRIGHT + Fore.RED + "\nDetails:" + Fore.WHITE + "%s" % ver_list + Fore.RESET + Style.NORMAL)	
		
		return (t_gop_type, "", t_version, "")
	
	## Mac Nvidia
	
	#pat_mac_nv = re.compile(br'\x4E\x00\x56\x00\x49\x00\x44\x00\x49\x00\x41\x00\x20\x00\x47\x00\x50\x00\x55\x00\x20\x00')
	##\x55\x00\x45\x00\x46\x00\x49\x00\x20\x00\x44\x00\x72\x00\x69\x00\x76\x00\x65\x00\x72\x00') ## N.V.I.D.I.A. .G.P.U. .U.E.F.I. .D.r.i.v.e.r. - False positives with normal Nvidia GOP
	#match_mac_nv = pat_mac_nv.search(t_efi_dump)
	
	# NVDA,NVMac
	# AAPL,EMC-Display-List
	# AAPL,boot-display
	# AAPL,backlight-control
	# APPLE
	# APPLE_SRC_DPCD_ACCESS
	# MacVidCards
	
	if re.search(b'NVDA,NVMac', t_efi_dump) is not None :
		match_mac_nv = True
	elif re.search(br'\x41\x00\x41\x00\x50\x00\x4C\x00\x2C\x00', t_efi_dump) is not None : # A.A.P.L.,.
		match_mac_nv = True
	elif re.search(br'\x41\x00\x50\x00\x50\x00\x4C\x00\x45\x00', t_efi_dump) is not None : # A.P.P.L.E.
		match_mac_nv = True
	else :
		match_mac_nv = False
	
	#if match_mac_nv is not None :
		#(mac_start_match, mac_end_match) = match_mac_nv.span()
	if match_mac_nv :
		t_gop_type = "Mac_Nvidia"
		pat_mac_ver = re.compile(br'\x4E\x56\x44\x41\x2D\x45\x46\x49\x2D\x42\x75\x69\x6C\x64\x2D\x49\x6E\x66\x6F')
		match_mac_ver = pat_mac_ver.search(t_efi_dump)
		
		if match_mac_ver is not None :
			(mac_start_ver, mac_end_ver) = match_mac_ver.span()
			t_version = t_efi_dump[mac_end_ver:mac_end_ver + 0x13].decode('utf-8', 'ignore').replace("-", " ").strip()
		else :
			t_version = "unknown"
		
		if re.search(br'\x4D\x58\x4D\x5F', t_efi_dump) is not None : ## MXM_
			t_version += "_MXM"
		
		print(Style.BRIGHT + Fore.GREEN + "Mac Nvidia GOP" + Fore.WHITE + " %s  " % t_version + Fore.RESET + Style.NORMAL)
		
		return (t_gop_type, "", t_version, "")
	
	
	## LSI MPT UEFI
	## Added only for extraction purpose
	pat_lsi   = re.compile(br'\x4C\x53\x49\x20\x53\x41\x53(\x32|\x33)\x20\x4D\x50\x54\x20\x55\x45\x46\x49') ## LSI SASx MPT UEFI
	match_lsi = pat_lsi.search(t_efi_dump)
	
	if match_lsi is not None :
		t_gop_type = "LSI SASx MPT UEFI"
		(lsi_start_match, lsi_end_match) = match_lsi.span()
		sas_type  = t_efi_dump[lsi_start_match + 7:lsi_start_match + 8].decode('utf-8', 'ignore')
		t_gop_type = "LSI SAS%s MPT UEFI" % sas_type
		pat_ver   = re.compile(br'\x4C\x53\x49\x20\x43\x6F\x72\x70\x6F\x72\x61\x74\x69\x6F\x6E\x0A\x76') ## LSI Corporation.v
		match_ver = pat_ver.search(t_efi_dump, lsi_end_match)
		
		if match_ver is None :
			pat_ver   = re.compile(br'\x41\x76\x61\x67\x6F\x20\x54\x65\x63\x68\x6E\x6F\x6C\x6F\x67\x69\x65\x73\x2E\x20\x41\x6C\x6C\x20\x72\x69\x67\x68\x74\x73\x20\x72\x65\x73\x65\x72\x76\x65\x64\x2E\x0A\x76') ## Avago Technologies. All rights reserved..v
			match_ver = pat_ver.search(t_efi_dump, lsi_end_match)
		
		if match_ver is not None :
			(ver_start_match, ver_end_match) = match_ver.span()
			step = ver_end_match
			
			while t_efi_dump[step:step + 1] != b'\x0A' :
				step += 1
			
			t_version = t_efi_dump[ver_end_match:step].decode('utf-8', 'ignore').strip()
			print("LSI SAS%s MPT UEFI %s" % (sas_type, t_version))
			
			try :
				cut_ver   = t_version.index("*")
				t_version = t_version[:cut_ver].strip()
			except :
				pass
			
		return (t_gop_type, "", t_version, "")
	
	print(Style.BRIGHT + Fore.CYAN + "\nEFI ROM is present, but is not standard GOP type." + Fore.RESET + Style.NORMAL)
	
	return ("Unknown", "", "unknown", "")

def nvidia_board() :
	hint_message = "Missing"
	
	pat_nv   = re.compile(br'\x4E\x56\x49\x44\x49\x41\x20\x43\x6F\x72\x70\x2E\x0D\x0A') ## NVIDIA Corp...
	match_nv = pat_nv.search(reading)
	
	if match_nv is not None :
		(nv_start_match, nv_end_match) = match_nv.span()
		
		if reading[nv_end_match:nv_end_match + 0xB] == b'\x00\x00\x00\xFF\xFF\x00\x00\x00\x00\xFF\xFF' :
			#print("Normal string")
			hint_bgn = nv_end_match + 0xB
		else :
			#print("Different string")
			hint_bgn  = nv_end_match
			skip_byte = reading[hint_bgn:hint_bgn + 1]
			
			while skip_byte == b'\x00' or skip_byte == b'\xFF' :
				hint_bgn  += 1
				skip_byte = reading[hint_bgn:hint_bgn + 1]
		
		hint_message = ""
		hint_step    = hint_bgn
		hint_char    = reading[hint_step:hint_step + 1]
		
		while hint_char != b'\x00' and hint_char != b'\xFF' and hint_char != b'\x2D' :
			hint_message += hint_char.decode('utf-8', 'ignore')
			hint_step    += 1
			hint_char    = reading[hint_step:hint_step + 1]
	
	return hint_message.strip()

def isbn_struct(nv_image, print_info) :
	isbn_sig   = nv_image[:4].decode('utf-8', 'ignore')
	isbn_hdr   = int.from_bytes(nv_image[4:8], 'little')
	flag_v1    = ord(nv_image[8:9])
	flag_v2    = ord(nv_image[9:0xA])
	bv_sig_v1  = nv_image[0xA:0xC].decode('utf-8', 'ignore')
	checksm_v1 = int.from_bytes(nv_image[0xC:0x10], 'little')
	checksm_v2 = int.from_bytes(nv_image[0x10:0x14], 'little')
	bv_sig_v2  = nv_image[0x14:0x16].decode('utf-8', 'ignore')
	isbn_size  = int.from_bytes(nv_image[0x16:0x18], 'little') # maybe 4 bytes
	flag_v3    = int.from_bytes(nv_image[0x18:0x1C], 'little')
	
	if print_info :
		print("----------ISBN_HEADER---------\n")
		print("Signature:                      %s"      % isbn_sig)
		print("Header Size:                    0x%0.2X" % isbn_hdr)
		print("Unk01:                          0x%0.2X" % flag_v1)
		print("Unk02:                          0x%0.2X" % flag_v2)
		print("BV Signature:                   %s"      % bv_sig_v1)
		print("Checksum v1:                    0x%0.2X" % checksm_v1)
		print("Checksum v2:                    0x%0.2X" % checksm_v2)
		print("BV Signature:                   %s"      % bv_sig_v2)
		print("ISBN Body Size:                 0x%0.2X" % isbn_size)
		print("Unk03:                          0x%0.2X" % flag_v3)
		print("\n------------------------------\n")
	
	isbn_step = 0x1C # Hard coded ?
	isbn_end  = isbn_hdr + isbn_size
	count     = 0
	old_size  = 0
	
	while isbn_step < isbn_end :
		
		# First is a certificate
		# Second is a certificate
		# Third is a map
		# Fourth is a hash
		# Fifth is a map
		# Sixth is a hash
		
		count     += 1
		
		cert_type = int.from_bytes(nv_image[isbn_step:isbn_step + 4], 'little')
		cert_hdr  = int.from_bytes(nv_image[isbn_step + 4:isbn_step + 8], 'little')
		map_el_nr = int.from_bytes(nv_image[isbn_step + 8:isbn_step + 0xC], 'little')
		cert_size = int.from_bytes(nv_image[isbn_step + 0xC:isbn_step + 0x10], 'little')
		cert_flg1 = int.from_bytes(nv_image[isbn_step + 0x10:isbn_step + 0x14], 'little')
		cert_flg2 = int.from_bytes(nv_image[isbn_step + 0x14:isbn_step + 0x18], 'little')
		cert_flg3 = int.from_bytes(nv_image[isbn_step + 0x18:isbn_step + 0x1C], 'little')
		cert_flg4 = int.from_bytes(nv_image[isbn_step + 0x1C:isbn_step + 0x20], 'little')
		cert_flg5 = int.from_bytes(nv_image[isbn_step + 0x20:isbn_step + 0x24], 'little')
		
		cert_bgn  = isbn_step + cert_hdr
		
		if print_info :
			
			print("----------CERT_HEADER---------\n")
			print("Type:                           0x%0.2X" % cert_type)
			print("Header Size:                    0x%0.2X" % cert_hdr)
			print("Nr of map elements:             0x%0.2X" % map_el_nr)
			print("Certificate size:               0x%0.2X" % cert_size)
			
			if cert_hdr == 0x24 :
				
				date_str = datetime.datetime.fromtimestamp(cert_flg3).strftime('%Y-%m-%d %H:%M:%S')
				
				print("Flags v1 - Sign Size:           0x%0.2X" % cert_flg1)
				print("Flags v2 - Hash Size:           0x%0.2X" % cert_flg2)
				print("Flags v3 - Date:                0x%0.2X" % cert_flg3 + " = " + date_str)
				print("Flags v4:                       0x%0.2X" % cert_flg4)
				print("Flags v5:                       0x%0.2X" % cert_flg5)
			
			elif cert_hdr == 0x1C :
				
				print("Flags v1 - Cert Type:           0x%0.2X" % cert_flg1)
				print("Flags v2 - Issuer ID:           0x%0.2X" % cert_flg2)
				print("Flags v3 - Owner ID:            0x%0.2X" % cert_flg3)
			
			elif cert_hdr > 0x10 :
				flag_nr   = 0
				flag_step = isbn_step + 0x10
				
				for ix in range(0, cert_hdr - 0x10, 4) :
					flag_nr   += 1
					cert_flgx = int.from_bytes(nv_image[flag_step:flag_step + 4], 'little')
					
					print("Flags v%0.2d :                     0x%0.2X" % (flag_nr, cert_flgx))
					
					flag_step += 4
			
			print("\n------------------------------\n")
		
		if count == 2 :
			cert_size -= old_size
		else :
			old_size  = cert_size
		
		if map_el_nr < 0x100 and count == 3 :
			
			map_step = cert_bgn
			
			for ix in range(map_el_nr) :
				
				if ix == 0 and print_info :
					print("----------MAP_Content---------\n")
					print(" Offset  | Size    | Flags \n")
				
				elem_off  = int.from_bytes(nv_image[map_step:map_step + 4], 'little')
				elem_size = int.from_bytes(nv_image[map_step + 4:map_step + 8], 'little')
				elem_flag = int.from_bytes(nv_image[map_step + 8:map_step + 0xC], 'little')
				map_step  += 0xC
				
				if print_info :
					print(" %-8X  %-8X  %-8X" % (elem_off, elem_size, elem_flag))
			
			if print_info :
				print("\n------------------------------\n")
		
		if nv_image[cert_bgn:cert_bgn + 11] == b'-----BEGIN ' :
			
			if print_info :
				print(nv_image[cert_bgn:isbn_step + cert_size].decode('utf-8', 'ignore'))
			
			with open(file_rom + "_temp/cert_nr%d.crt" % count, 'wb') as cert_file :
				cert_file.write(nv_image[cert_bgn:isbn_step + cert_size])
			
			print(Style.BRIGHT + Fore.YELLOW + "Extracted cert_nr%d.crt\n" % count + Fore.RESET + Style.NORMAL)
		
		elif map_el_nr == 0 :
			
			with open(file_rom + "_temp/cert_nr%d.lic" % count, 'wb') as cert_file :
				cert_file.write(nv_image[cert_bgn:isbn_step + cert_size])
			
			print(Style.BRIGHT + Fore.YELLOW + "Extracted cert_nr%d.lic\n" % count + Fore.RESET + Style.NORMAL)
		
		# else :
			
			# with open(file_rom + "_temp/cert_nr%d.unk" % count, 'wb') as cert_file :
				# cert_file.write(nv_image[cert_bgn:isbn_step + cert_size])
			
			# print(Style.BRIGHT + Fore.YELLOW + "Extracted cert_nr%d.unk\n" % count + Fore.RESET + Style.NORMAL)
		
		#print(count)
		
		if cert_size == 1 or count == 4 :
			
			cert_size = cert_hdr + cert_flg1 + cert_flg2
			hash_v1   = binascii.hexlify(nv_image[cert_bgn:cert_bgn + 0x80]).decode('utf-8').upper()
			hash_v2   = binascii.hexlify(nv_image[cert_bgn + 0x80:cert_bgn + 0x90]).decode('utf-8').upper()
			
			if print_info :
				print("---------SIGN_Content---------\n")
				print("\n".join(hash_v1[xstr:xstr + 32] for xstr in range(0, len(hash_v1), 32)))
				print("\n------------------------------\n")
				print("----------Image_HASH----------\n")
				print(hash_v2)
				print("\n------------------------------\n")
		
		if cert_type > 0x10 or count == 5 :
			cert_size = int.from_bytes(nv_image[isbn_step + 0x14:isbn_step + 0x18], 'little')
			flag_nr   = 0
			flag_step = isbn_step + cert_hdr
			
			if print_info :
				print("----------MAP_Content---------\n")
				print(" Flags   | Offset  | Size    | Hash\n")
			
			for ix in range(0, cert_size - cert_hdr - 0x10, 0x1C) :
				flag_nr   += 1
				cert_flgx = int.from_bytes(nv_image[flag_step:flag_step + 4], 'little')
				cert_flgy = int.from_bytes(nv_image[flag_step + 4:flag_step + 8], 'little')
				cert_flgz = int.from_bytes(nv_image[flag_step + 8:flag_step + 0xC], 'little')
				cert_hash = binascii.hexlify(nv_image[flag_step + 0xC:flag_step + 0x1C]).decode('utf-8').upper()
				
				if print_info :
					# print("Flags :                         0x%0.2X" % cert_flgx)
					# print("Offset :                        0x%0.2X" % cert_flgy)
					# print("Size :                          0x%0.2X" % cert_flgz)
					# print("Hash :                          %s"      % cert_hash)
					print(" %-8X  %-8X  %-8X  %s" % (cert_flgx, cert_flgy, cert_flgz, cert_hash))
					print()
				
				flag_step += 0x1C
			
			mast_hash = binascii.hexlify(nv_image[isbn_step + cert_size - 0x10:isbn_step + cert_size]).decode('utf-8').upper()
			
			if print_info :
				print("Master Hash :                  %s" % mast_hash)
				print("\n------------------------------\n")
		
		if count == 6 :
			cert_size = isbn_end - isbn_step
			hash_v1   = binascii.hexlify(nv_image[cert_bgn:isbn_step + cert_size]).decode('utf-8').upper()
			
			if print_info :
				print("---------SIGN_Content---------\n")
				print("\n".join(hash_v1[xstr:xstr + 32] for xstr in range(0, len(hash_v1), 32)))
				print("\n------------------------------\n")
		
		if cert_size :
			isbn_step += cert_size
		else :
			isbn_step += cert_hdr + map_el_nr * 0xC

def is_version_upd(t_last_gop, t_version, t_gop_type) :
	
	if t_gop_type == "AMD" :
		t_lastgop_int = float(t_last_gop[0:4].strip("."))
		t_version_int = float(t_version[0:4].strip("."))
	elif t_gop_type == "Nvidia" :
		t_lastgop_int = int(t_last_gop, 16)
		t_version_int = int(t_version, 16)
	
	if t_version == t_last_gop :
		print(Style.BRIGHT + Fore.CYAN + "You already have the latest available GOP!\n" + Fore.RESET + Style.NORMAL)
		sys.exit()
	elif t_version_int < t_lastgop_int :
		print("Latest available GOP is %s\n" % t_last_gop)
	else :
		print(Style.BRIGHT + Fore.YELLOW + "You have a newer version! Please report it in the forum!\n" + Fore.RESET + Style.NORMAL)
		sys.exit()
	
	return None

def remove_padding(t_end_img_old, t_end_img_new, t_all_size, t_str_err) :
	bgn_extra  = 0
	t_end_data = b''
	
	for padd_off in range (t_end_img_old, t_all_size) :
		padd_byte = reading[padd_off:padd_off + 1]
		
		if padd_byte == b'' :
			break
		
		elif padd_byte != b'\xFF' and padd_byte != b'\x00' :
			bgn_extra = padd_off
			print(Style.BRIGHT + Fore.RED + t_str_err + Fore.RESET)
			#t_end_data = reading[t_end_img_old:]
			break
	
	## If there is extra data after ROM images.
	if bgn_extra :
		## If the extra data offset is now inside the new image.
		
		if bgn_extra < t_end_img_new :
			print(Style.BRIGHT + Fore.RED + "  Unable to recover extra data at the same offset 0x%0.2X! Please report it!\n" % bgn_extra + 
			Fore.RESET + Style.NORMAL)
			t_end_data = reading[t_end_img_old:]
		
		## Extra data can be recovered at the old offset
		else :
			print(Style.BRIGHT + Fore.YELLOW + "  Recovering extra data at the same offset 0x%0.2X.\n" % bgn_extra + 
			Fore.RESET + Style.NORMAL)
			## If the new image ends after the old one, just copy from there.
			
			if t_end_img_new >= t_end_img_old :
				t_end_data = reading[t_end_img_new:]
			
			## But if the old image was bigger, we need to fill the difference with padding and then copy from the end of old image.
			else :
				t_end_data = b'\xFF' * (t_end_img_old - t_end_img_new) + reading[t_end_img_old:]
	
	return t_end_data

def check_in_database(t_efi_info_string) :
	efi_in_db     = False
	bad_nvd       = False
	bad_amd       = False
	mod_amd       = False
	#unknown_type = False
	
	#if t_efi_info_string == "" :
	#	return None
	
	if nv_type == "GXxxx" or nv_type == "GXxxx_MXM" :
		unknown_type = True
		index        = len(nv_type) + 3
	else :
		unknown_type = False
		index        = 0
	
	with open("#GOP_Files/#GOP_Database.txt", 'r+') as db_file:
		
		for line in db_file:
			
			if len(line) < 2 :
				continue
			
			elif line[:2] == "##" :
				
				if line[3:13] == "BAD_NVIDIA" :
					bad_nvd = True
				elif line[3:10] == "BAD_AMD" :
					bad_amd = True
				elif line[3:14] == "Patched GOP" :
					mod_amd = True
					mod_str = line[3:-1].replace("Patched", "patched")
				else :
					continue
			
			if line[index:] == t_efi_info_string[index:] :
				
				efi_in_db = True
				
				if gop_type == "AMD" and bad_amd :
					print(Style.BRIGHT + Fore.YELLOW + "You have a broken EFI image!\n" + Fore.RESET + Style.NORMAL)
				elif gop_type == "AMD" and mod_amd :
					print(Style.BRIGHT + Fore.YELLOW + "It appears you have a %s!\n" % mod_str + Fore.RESET + Style.NORMAL)
				elif gop_type == "Nvidia" and bad_nvd :
					print(Style.BRIGHT + Fore.YELLOW + "You have a broken EFI image!\n" + Fore.RESET + Style.NORMAL)
				
				if unknown_type :
					new_type = line[:index - 3]
				
				#print("EFI %s is present in the database!\n" % t_efi_info_string)
				break
	
	if efi_in_db :
		
		if unknown_type :
			return new_type, True
		else :
			return None, True

	else :
		print(Style.BRIGHT + Fore.YELLOW + "Note: The GOP file is not present in my database.\n\n      You can help me by reporting it.\n" + 
		Fore.RESET + Style.NORMAL)
		
		return None, False

####################################
####################################
####################################

if len(sys.argv) < 3 :
	print(Fore.RED + "Not enough arguments! Usage: GOPupd.py file.rom [ext_efirom | gop_upd | isbn]" + Fore.RESET)
	sys.exit()
else :
	file_dir   = sys.argv[1]
	file_rom   = os.path.basename(file_dir)
	file_arg   = sys.argv[2]
	extra_args = sys.argv[3:]

if not os.path.isfile(file_dir) :
	print(Fore.RED + "File %s was not found!" % file_dir + Fore.RESET)
	sys.exit()

try :
	f = open(file_dir, 'rb')
	reading = f.read()
	f.close()
except :
	print(Fore.RED + "Unable to open file %s for reading!" % file_dir + Fore.RESET)
	sys.exit()

try :
	os.mkdir(file_rom + "_temp/")
except :
	pass

fileName, fileExtension = os.path.splitext(file_rom)
position = 0

if "-ROMSCAN" in (arg_val.upper() for arg_val in extra_args) :
	
	img_nr   = 0
	position = 0
	rom_data = reading
	
	while True :
		
		rom_found, rom_start, rom_pcir_off, rom_id_bin, rom_id_hex, rom_last_img, rom_size = rom_info_scan(rom_data, position)
		
		if not rom_found :
			break
		
		img_nr   += 1
		position = rom_start + 2 # not using [position += rom_size] because of multi-images.
		
		print("Image %d -- Offset 0x%0.2X\n"  % (img_nr, rom_start))
		
		if rom_data[rom_start + 4:rom_start + 8] == b'\xF1\x0E\x00\x00' :
			rom_hdr    = get_struct(rom_data, rom_start, EFI_ROM_Header)
			rom_hdr.rom_print(rom_start)
			pnp_ptr    = 0
		elif rom_data[rom_start:rom_start + 2] == b'\x56\x4E' :
			rom_hdr    = get_struct(rom_data, rom_start, ROM_Header) # Just in case will be needed
			nv_rom_hdr = get_struct(rom_data, rom_start, NV_ROM_Header)
			nv_rom_hdr.nv_rom_print(rom_start) # rom_hdr.nv_rom_print(rom_start)
			pnp_ptr    = 0
		elif rom_data[rom_start:rom_start + 2] == b'\x77\xBB' :
			rom_hdr    = get_struct(rom_data, rom_start, ROM_Header) # Just in case will be needed
			nv_rom_hdr = get_struct(rom_data, rom_start, NV_EFI_ROM_Header)
			nv_rom_hdr.nv_rom_print(rom_start) # rom_hdr.nv_rom_print(rom_start)
			pnp_ptr    = 0
		else :
			rom_hdr = get_struct(rom_data, rom_start, ROM_Header)
			rom_hdr.rom_print(rom_start)
			pnp_ptr = rom_hdr.PnpOffset
		
		if rom_hdr.PcirOffset :
			pcir_off = rom_start + rom_hdr.PcirOffset
			pcir_hdr = get_struct(rom_data, pcir_off, PCIR_Header)
			
			if pcir_hdr.Signature == b'RGIS' :
				rgis_hdr = get_struct(rom_data, pcir_off, RGIS_Header)
				rgis_hdr.rgis_print(pcir_off)
				#pcir_hdr.rgis_print(pcir_off)
			else :
				pcir_hdr.pcir_print(pcir_off)
			
			for idx in range(pcir_off + 0x20, pcir_off + 0x60) :
				if rom_data[idx:idx + 4] == b'NPDE' :
					npde_hdr = get_struct(rom_data, idx, NPDE_Header)
					npde_hdr.npde_print(idx)
					break
		
		# PnP sections
		rom_pnp_off = rom_start + pnp_ptr
		pnp_str     = rom_data[rom_pnp_off:rom_pnp_off + 4]
		
		if pnp_ptr != 0 and pnp_str == b'$PnP' :
			pnp_step = rom_pnp_off
			pnp_nr   = 0
			
			while True :
				pnp_nr += 1
				pnp_hdr  = get_struct(rom_data, pnp_step, PnP_Header)
				pnp_next = pnp_hdr.OffsetOfNextHdr
				pnp_len  = pnp_hdr.Length * 0x10
				print("\nPnP %d:" % pnp_nr)
				pnp_hdr.pnp_print(rom_start)
				
			
				if pnp_next == 0 :
					
					test_pnp_off = pnp_step + pnp_len
					
					while rom_data[test_pnp_off:test_pnp_off + 1] == b'\x00' :
						test_pnp_off += 1
					
					#if rom_data[pnp_step + pnp_len:pnp_step + pnp_len + 4] != b'$PnP' :
					if rom_data[test_pnp_off:test_pnp_off + 4] != b'$PnP' :
						break
					
					pnp_step = test_pnp_off
				
				else :
					pnp_step = rom_start + pnp_next

if "-ISBN" in (arg_val.upper() for arg_val in extra_args) :
	rom_old_type, rom_start, rom_pcir_off, rom_id_bin, rom_size, efi_found, efi_begin, efi_size = rom_info(reading, 0, "all")
	
	if "-DEBUG" in (arg_val.upper() for arg_val in extra_args) :
		print_info = True
	else :
		print_info = False
	
	isbn_found = False
	nv_step    = rom_start + rom_size
	
	if reading[rom_pcir_off + 0x20:rom_pcir_off + 0x24] == b'NPDE' :
		npde_size = int.from_bytes(reading[rom_pcir_off + 0x28:rom_pcir_off + 0x2A], 'little') * 0x200
		
		if rom_size != npde_size :
			print("  Different sizes in PCI structure and NPDE structure of Legacy ROM!\n")
			
			rom_end_npde  = rom_start + npde_size
			rom_test_npde = reading[rom_end_npde:rom_end_npde + 2]
			
			## If NPDE size is the right one, there is one container for all ROMs.
			if rom_test_npde in [b'\x55\AA', b'\x56\x4E'] :
				print("  The Legacy ROM appears to be a container for all images.\n")
				nv_step      = rom_end_npde
			
	check_nv_ext = reading[nv_step:nv_step + 2]
				
	while check_nv_ext in [b'\x56\x4E', b'\x55\xAA', b'\x77\xBB'] :
		
		if check_nv_ext == b'\x77\xBB' :
			npds_off    = int.from_bytes(reading[nv_step + 0x18:nv_step + 0x1A], 'little')
			npds_off    += nv_step
			nv_ext_size = int.from_bytes(reading[npds_off + 0x10:npds_off + 0x12], 'little') * 0x200
		
		else :
			nv_ext_size = int.from_bytes(reading[nv_step + 2:nv_step + 4], 'little') * 0x200
		
		#print(nv_ext_size)
		
		if nv_ext_size == 0 :
			npds_off    = int.from_bytes(reading[nv_step + 0x18:nv_step + 0x1A], 'little')
			npds_off    += nv_step
			nv_ext_size = int.from_bytes(reading[npds_off + 0x10:npds_off + 0x12], 'little') * 0x200
			#print(nv_ext_size)
			
			npds_str_size = int.from_bytes(reading[npds_off + 0xA:npds_off + 0xC], 'little')
			isbn_off      = npds_off + npds_str_size
			isbn_check    = reading[isbn_off:isbn_off + 4]
			
			if isbn_check == b'ISBN' :
				print(Style.BRIGHT + Fore.YELLOW + "Found ISBN at offset 0x%0.2X\n" % isbn_off + Fore.RESET + Style.NORMAL)
				isbn_struct(reading[isbn_off:nv_step + nv_ext_size], print_info)
				isbn_found = True
		
		nv_step      += nv_ext_size
		check_nv_ext = reading[nv_step:nv_step + 2]
	
	if not isbn_found :
		print(Style.BRIGHT + Fore.YELLOW + "ISBN was not found!\n" + Fore.RESET + Style.NORMAL)

if file_arg == "ext_efirom" :
	## Get ROM info for EFI extraction
	efi_nr = 1
	
	efi_found, efi_begin, efi_size = rom_info(reading, 0, "mini")
	
	if not efi_found :
		print(Fore.RED + "No EFI ROM found!\n" + Fore.RESET)
		sys.exit()
	
	efi_rom = reading[efi_begin:efi_begin + efi_size]
	
	with open("%s_temp/%s_compr.efirom" % (file_rom, fileName), 'wb') as efi_rom_file :
		efi_rom_file.write(efi_rom)
	
	while True :
		efi_found = False
		
		if rom_info(reading, efi_begin + efi_size, "basic") :
			efi_found, efi_begin, efi_size = rom_info(reading, efi_begin + efi_size, "mini")
		
		if not efi_found :
			sys.exit()
		
		print(Fore.RED + "Extra EFI ROM found at offset 0x%0.2X!\n" % efi_begin + Fore.RESET)
		efi_nr  += 1
		efi_rom = reading[efi_begin:efi_begin + efi_size]
		
		with open("%s_temp/%s_compr_nr%d.efirom" % (file_rom, fileName, efi_nr), 'wb') as efi_rom_file :
			efi_rom_file.write(efi_rom)

elif file_arg == "gop_upd" :
	
	gop_type  = ""
	efi_in_db = False
	efi_imag  = False
	file_efi  = "%s_temp/%s_dump.efi" % (file_rom, fileName)
	file_efr  = "%s_temp/%s_compr.efirom" % (file_rom, fileName)
	#print(extra_args)
	
	if "-PATCHED" in (arg_val.upper() for arg_val in extra_args) :
		amd_gop_efirom = "amd_gop_mod.efirom"
	else :
		amd_gop_efirom = "amd_gop.efirom"
	
	if os.path.isfile(file_efi) or fileExtension in ['.efi', '.ffs'] :
		
		if fileExtension in ['.efi', '.ffs'] :
			efi_imag = True
			mz_found, mz_start = mz_off(reading, 0)
			
			if mz_found :
				mz_size  = image_size(reading[mz_start:], 'full')
				#print("%02X - %02X" % (mz_start, mz_start + mz_size))
				efi_dump = reading[mz_start:mz_start + mz_size]
			else :
				with open(file_efi, 'rb') as myfile :
					efi_dump = myfile.read()
		else :
			with open(file_efi, 'rb') as myfile :
				efi_dump = myfile.read()
		
		## Get EFI info
		gop_type, nv_type, version, efi_info_string = efi_version(efi_dump)
		
		## The machine code type, signer and CRC32 are processed outside efi_version because they are not bound to GOP.
		
		## Signer
		## Needs a full X.509 parser. Since it is not that important, only get the first signer.
		# pe_off     = int.from_bytes(efi_dump[0x3C:0x40], 'little')
		# code_size  = int.from_bytes(efi_dump[pe_off + 0x50:pe_off + 0x54], 'little') ## only works for EFI files, not for every exe.
		code_size  = image_size(efi_dump, 'naked')
		pat_sign   = re.compile(br'\x06\x09\x2A\x86\x48\x86\xF7\x0D\x01\x07\x02')
		match_sign = pat_sign.search(efi_dump, code_size)
		
		if match_sign is not None :
			(sign_start_match, sign_end_match) = match_sign.span()
			#print("\nEFI Image is signed!")
			efi_is_signed = "Signed"
			pat_signer    = re.compile(br'\x06\x03\x55\x04\x03\x13') ## 06 03 55 04 03 13
			match_signer  = pat_signer.search(efi_dump, sign_end_match)
			
			if match_signer is not None :
				(signer_start_match, signer_end_match) = match_signer.span()
				mess_len = ord(efi_dump[signer_end_match:signer_end_match + 1])
				signer   = efi_dump[signer_end_match + 1:signer_end_match + mess_len + 1].decode('utf-8', 'ignore')
				print(Style.BRIGHT + Fore.CYAN + "\nMost likely signed by: %s\n" % signer + Fore.RESET + Style.NORMAL)
			else :
				print(Style.BRIGHT + Fore.CYAN + "\nEFI Image is signed!\n" + Fore.RESET + Style.NORMAL)
		
		else :
			efi_is_signed = "Unsigned"
			print(Style.BRIGHT + Fore.CYAN + "\nEFI image is NOT signed!\n" + Fore.RESET + Style.NORMAL)
		
		if gop_type == "AMD" :
			efi_info_string += " - " + "%s" % efi_is_signed
		
		## Machine Code Type		
		mz_start, code_type, print_type = pe_machine(efi_dump)
		print(Style.BRIGHT + Fore.CYAN + "Machine Code   = %s\n" % code_type + Fore.RESET + Style.NORMAL)
		
		## CRC32
		#efi_crc32 = get_crc32(efi_dump)
		efi_crc32_int = binascii.crc32(efi_dump) & 0xFFFFFFFF
		efi_crc32_hex = "%08X" % efi_crc32_int
		print(Style.BRIGHT + Fore.CYAN + "Checksum CRC32 = %s\n" % efi_crc32_hex + Fore.RESET + Style.NORMAL)
		
		## Check in database
		if efi_info_string != "" :
						
			efi_info_string += " - " + "%s\n" % efi_crc32_hex
			
			#print(efi_info_string)
			#with open("#add_new_string.txt", "a") as myfile :
			#	myfile.write(efi_info_string)
			
			new_nv_type, efi_in_db = check_in_database(efi_info_string)
			
			if new_nv_type is not None :
				nv_type = new_nv_type
				#print("GOP identified as %s based on CRC\n" % nv_type)
				print(Style.BRIGHT + Fore.WHITE + "GOP identified as" + Fore.GREEN + " %s " % nv_type + 
				Fore.WHITE + "based on CRC \n" + Fore.RESET + Style.NORMAL)
		
		## Check integrity
		
		old_checksum, new_checksum = pe_checksum(efi_dump)
		
		if old_checksum == new_checksum :
			chk_msg = " (Same as in PE header)"
		elif old_checksum == 0 :
			chk_msg = " (Should be %0.2X)\n" % new_checksum
		else :
			chk_msg = " (Should be %0.2X). Image is most likely corrupted.\n" % new_checksum
		
		checksum_str = "PE Checksum = %0.2X" % old_checksum + chk_msg
		
		if old_checksum == 0 :
			print(Style.BRIGHT + Fore.YELLOW + checksum_str + Fore.RESET + Style.NORMAL)
		
		elif old_checksum and old_checksum != new_checksum :
			
			if not efi_in_db :
				print(Style.BRIGHT + Fore.YELLOW + "You may have a broken EFI image!\n" + Fore.RESET + Style.NORMAL)
			
			print(Style.BRIGHT + Fore.YELLOW + checksum_str + Fore.RESET + Style.NORMAL)
		
		## Rename temp files
		
		extra_ver = ""
		pat_lg    = br'\x41(\x4D\x44|\x54\x49)\x20\x41\x54\x4F\x4D\x42\x49\x4F\x53\x00' ## AMD ATOMBIOS or ATI ATOMBIOS.
		
		if gop_type == "AMD" :
			
			# TODO Check for ROM, get CRC offset, compare to 0.
			# Usually a ROM in EFI means legacy tables are present.
			if (rom_info(efi_dump, 0, "basic") or re.search(pat_lg, efi_dump) is not None) :
				extra_ver += "_custom_%s_%s" % (efi_is_signed.lower(), efi_crc32_hex)
			else :
				extra_ver += "_%s_%s" % (efi_is_signed.lower(), efi_crc32_hex)
		
		version_xt = version + extra_ver
		
		## For you
		
		gop_version  = "%s %s" % (nv_type, version_xt) if nv_type != "" else version_xt
		file_new_bgn = "%s_temp/%s GOP %s" % (file_rom, gop_type, gop_version)
		
		## For me
		
		full_rename = False
		
		if full_rename and fileName[:8] == "AMD GOP " and fileName[8:10] in ['0.', '1.'] :
			
			if fileName.find("_signed_") > 0 or fileName.find("_unsigned_") > 0 :
				needs_rename = False
			else :
				needs_rename = True
			
			#print("Orig = " + fileName)
			split_name = fileName.split()
			#print(split_name)
			fileName   = " ".join(split_name[3:])
			fileName   = fileName.rstrip()
			#print("Cut  = " + fileName)
			
			if needs_rename :
				
				try :
					fixed_name = os.path.dirname(file_dir) + "/" + "AMD GOP " + version_xt + " " + fileName.rstrip() + fileExtension
					#print(fixed_name)
					os.rename(file_dir, fixed_name)
					
					olf_efi_name = file_dir[:-13] + "_dump.efi"
					
					if os.path.isfile(olf_efi_name) :
						fixed_name = os.path.dirname(file_dir) + "/" + "AMD GOP " + version_xt + " " + fileName.rstrip() + ".efi"
						fixed_name = fixed_name.replace("_compr", "_dump")
						os.rename(olf_efi_name, fixed_name)
				
				except Exception as e:
					
					print("Error on renaming original files!\n")
					print(e)
					print()
		
		# version_me      = version_xt[2:] if version_xt[:2] == "0x" else version_xt
		# gop_version_me  = "%s %s" % (nv_type, version_me) if nv_type != "" else version_me
		# file_new_bgn    = "%s_temp/%s GOP %s %s" % (file_rom, gop_type, gop_version_me, fileName)
		
		## And nothing for the rest.
		
		file_new_efr = "%s_compr.efirom" % file_new_bgn.rstrip()
		file_new_efi = "%s_dump.efi" % file_new_bgn.rstrip()
		
		if file_efi != file_new_efi and os.path.exists(file_new_efi) :
			os.remove(file_new_efi)
		if file_efr != file_new_efr and os.path.exists(file_new_efr) :
			os.remove(file_new_efr)
		
		if not efi_imag :
			
			try :
				os.rename(file_efi, file_new_efi)
			except Exception as e:
				print("Error on renaming temp files!\n")
				print(e)
				print()
			
			try :
				os.rename(file_efr, file_new_efr)
			except Exception as e:
				print("Error on renaming temp files!\n")
				print(e)
				print()
		
		if gop_type not in ['AMD', 'Nvidia'] or not efi_in_db :
			
			# if efi_info_string != "" :
				# with open("#add_new_string.txt", "a") as myfile :
					# myfile.write(efi_info_string)
			
			src_dir = "%s_temp" % file_rom
			dst_dir = "%s_newGOP" % file_rom
			os.rename(src_dir, dst_dir)
		
	print(Fore.RED + "---------------------------------------------------------------\n" + Fore.RESET)
	
	print(Fore.GREEN + "***************************************************************")
	print("***                Processing with Python...                ***")
	print("*************************************************************** \n" + Fore.RESET)
	#print("---------------------------------------------------------------\n\n")
	
	is_vega_gop   = False
	last_amd_vega = "2.4.0.0.0"
	last_amd_new  = "1.67.0.15.50"
	last_amd_old  = "1.57.0.0.0"
	last_nv_GT21x = "0x10031"
	last_nv_GF10x = "0x1002D"
	last_nv_GF119 = "0x10030"
	last_nv_GK1xx = "0x10038"
	last_nv_GM1xx = "0x10036"
	last_nv_GM2xx = "0x20011"
	last_nv_GP1xx = "0x3000E"
	last_nv_GV1xx = "0x40006"
	last_nv_TU1xx = "0x50009"
	
	last_nv_GF10x_MXM = "0x10005"
	last_nv_GF119_MXM = "0"
	last_nv_GK1xx_MXM = "0x10033"
	last_nv_GM1xx_MXM = "0x10035"
	
	last_nv_GK1xx_MDP = "0x10030"
	
	## GOP Test
	if gop_type == "AMD" :
		
		if version[:2] == "2." :
			last_gop    = last_amd_vega
			is_vega_gop = True
		else : 
			last_gop    = last_amd_new
		
		is_version_upd(last_gop, version, gop_type)
	
	elif gop_type == "Nvidia" :
		if len(nv_type) > 12 and nv_type[6:13] == "Strange" : # GXxyz_Strange or GXxyz_Strange_[MXM|Multi-Display|Custom]
			print(Style.BRIGHT + Fore.YELLOW + "You have a strange GOP! Please report it!\n" + Fore.RESET + Style.NORMAL)
			sys.exit()
		elif len(nv_type) > 6 and nv_type[-6:] == "Custom" : # GXxyz[_Strange]_Custom
			print(Style.BRIGHT + Fore.YELLOW + "You have a custom GOP! Currently not supported. Please report it!\n" + Fore.RESET + Style.NORMAL)
			sys.exit()
		elif nv_type == "GT21x" :
			last_gop = last_nv_GT21x
			nv_file  = "nv_gop_GT21x.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GF10x" :
			last_gop = last_nv_GF10x
			nv_file  = "nv_gop_GF10x.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GF119" :
			last_gop = last_nv_GF119
			nv_file  = "nv_gop_GF119.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GK1xx" :
			last_gop = last_nv_GK1xx
			nv_file  = "nv_gop_GK1xx.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GM1xx" :
			last_gop = last_nv_GM1xx
			nv_file  = "nv_gop_GM1xx.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GM2xx" :
			last_gop = last_nv_GM2xx
			nv_file  = "nv_gop_GM2xx.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GP1xx" :
			last_gop = last_nv_GP1xx
			nv_file  = "nv_gop_GP1xx.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GV1xx" :
			last_gop = last_nv_GV1xx
			nv_file  = "nv_gop_GV1xx.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "TU1xx" :
			last_gop = last_nv_TU1xx
			nv_file  = "nv_gop_TU1xx.efirom"
			is_version_upd(last_gop, version, gop_type)
			print(Style.BRIGHT + Fore.YELLOW + "Work in progress! Be careful!\n" + Fore.RESET + Style.NORMAL)
			#sys.exit()
		elif nv_type == "GK1xx_MXM" :
			last_gop = last_nv_GK1xx_MXM
			nv_file  = "nv_gop_GK1xx_MXM.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GM1xx_MXM" :
			last_gop = last_nv_GM1xx_MXM
			nv_file  = "nv_gop_GM1xx_MXM.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif nv_type == "GK1xx_Multi-Display" :
			last_gop = last_nv_GK1xx_MDP
			nv_file  = "nv_gop_GK1xx_multi.efirom"
			is_version_upd(last_gop, version, gop_type)
		elif len(nv_type) > 3 and nv_type[-3:] == "MXM" : # GXxyz_MXM or GXxxx_MXM
			print(Style.BRIGHT + Fore.YELLOW + "You have an unsupported MXM GPU! Please report it! \n" + Fore.RESET + Style.NORMAL)
			sys.exit()
		elif len(nv_type) > 13 and nv_type[-13:] == "Multi-Display" : # GXxyz_Multi-Display
			print(Style.BRIGHT + Fore.YELLOW + "You have an unsupported Multi-Display GPU! Please report it!\n" + Fore.RESET + Style.NORMAL)
			sys.exit()
		elif nv_type != "GXxxx" : # GXnew
			print(Style.BRIGHT + Fore.YELLOW + "You have a new GOP type! Please report it!\n" + Fore.RESET + Style.NORMAL)
			sys.exit()
		else : # == GXxxx i.e. no variant ID.
			last_gop = "latest available"
			print(Style.BRIGHT + Fore.YELLOW + "Unable to determine GOP type!\n" + Fore.RESET + Style.NORMAL)
	
	elif gop_type[:4] == "Mac_" :
		print(Style.BRIGHT + Fore.RED + "Mac GOP support is limited! Drop your compressed GOP as mac_gop.efirom in #GOP_Files\n" + 
		Fore.RESET + Style.NORMAL)
		last_gop = "your file"
		mac_file  = "mac_gop.efirom"
		#sys.exit()
	elif gop_type[:3] == "LSI" :
		print(Style.BRIGHT + Fore.RED + "LSI SASx MPT UEFI not supported!\n" + Fore.RESET + Style.NORMAL)
		sys.exit()
	elif gop_type == "Unknown" :
		print(Style.BRIGHT + Fore.RED + "Not GOP or GOP is not common type! Please report it!\n" + Fore.RESET + Style.NORMAL)
		sys.exit()
	else :
		last_gop = "latest available"
		print(Style.BRIGHT + Fore.RED + "GOP is not present!!!\n" + Fore.RESET + Style.NORMAL)
	
	if efi_imag :
		print(Style.BRIGHT + Fore.CYAN + "It appears you used an EFI image! Only version display is possible." + Fore.RESET + Style.NORMAL)
		sys.exit()
	
	## Get ROM Info
	orom_old_type, orom_start, orom_pcir_off, orom_id_bin, orom_size, efi_found, efi_begin, efi_size = rom_info(reading, 0, "all")
	#ven_dev = "%s-%s" % (orom_id_hex[4:], orom_id_hex[:4])
	#pci_ven = ven_dev[:4]
	#pci_dev = ven_dev[-4:]
	ven_dev, pci_ven, pci_dev = id_from_bin(orom_id_bin, "all_list")
	efi_class_bin = reading[orom_pcir_off + 0xD:orom_pcir_off + 0x10] # Initialize for when GOP ROM missing
	#print(ven_dev)
	#print("%0.2X = %s-%s = %0.2X" % (orom_start, pci_ven, ven_dev[-4:], orom_last_img))
	#print(Style.BRIGHT + Fore.CYAN + "%s = ID of ROM file\n" % ven_dev + Fore.RESET + Style.NORMAL)
	
	
	## Check that EFI ROM header is a good match
	
	if orom_start == efi_begin :
		print(Style.BRIGHT + Fore.CYAN + "It appears you used an EFI ROM! Only extraction is possible." + Fore.RESET + Style.NORMAL)
		sys.exit()
	elif pci_ven not in ['1002', '10DE'] :
		print(Style.BRIGHT + Fore.YELLOW + "Only AMD and Nvidia GOP supported!" + Fore.RESET + Style.NORMAL)
		sys.exit()
	elif efi_found :
		if os.path.isfile(file_efi) and code_type != "x64" and gop_type[:4] != "Mac_" :
			print(Style.BRIGHT + Fore.YELLOW + "Code type %s is not supported!" % code_type + Fore.RESET + Style.NORMAL)
			sys.exit()
		
		efi_pcir_ds    = int.from_bytes(reading[efi_begin + 0x18:efi_begin + 0x1A], 'little')
		efi_pcir_off   = efi_begin + efi_pcir_ds
		efi_class_bin  = reading[efi_pcir_off + 0xD:efi_pcir_off + 0x10]
		efi_class_code = binascii.hexlify(efi_class_bin).decode('utf-8')
		efi_code_type  = reading[efi_pcir_off + 0x14:efi_pcir_off + 0x15]
		efi_last_img   = ord(reading[efi_pcir_off + 0x15:efi_pcir_off + 0x16]) & 0x80
		
		if efi_class_code not in ['030000', '000003', '030200', '000203'] and gop_type[:4] != "Mac_" :
			print(Style.BRIGHT + Fore.YELLOW + "Class-code %s is not supported!" % efi_class_code + Fore.RESET + Style.NORMAL)
			sys.exit()
		if efi_code_type != b'\x03' :
			print(Style.BRIGHT + Fore.RED + "Code mismatch in EFI ROM header!" + Fore.RESET + Style.NORMAL)
			sys.exit()
		if not efi_last_img :
			# Report not needed, found example in GP104_NotLast.rom
			#print(Style.BRIGHT + Fore.RED + "EFI ROM is not last image! Please report it!" + Fore.RESET + Style.NORMAL)
			print(Style.BRIGHT + Fore.YELLOW + "EFI ROM is not last image!" + Fore.RESET + Style.NORMAL)
			#sys.exit()
	
	## Pretty please
	ask = input("\nDo you want to update GOP to %s? Y for yes or N for no: " % last_gop)
	
	if ask.upper() not in ["Y", "YP", "YPAT"] :
		sys.exit()
	
	if ask.upper() in ["YP", "YPAT"] :
		amd_gop_efirom = "amd_gop_mod.efirom"
	
	print("")
	
	## GRID K1/K2 check
	if pci_ven == "10DE" and pci_dev in ['0FF2', '11BF'] :
		gop_type = "Nvidia"
		nv_type  = "GK1xx_Multi-Display"
		nv_file  = "nv_gop_GK1xx_multi.efirom"
		last_gop = last_nv_GK1xx_MDP
		print(Style.BRIGHT + Fore.YELLOW + "  Using Multi-Display GOP %s for GRID K1/K2.\n" % last_nv_GK1xx_MDP + Fore.RESET + Style.NORMAL)
	
	## Get the right GOP
	if gop_type == "AMD" or (pci_ven == "1002" and gop_type == "") :
		## The next two lines are needed for the case of missing GOP.
		gop_type   = "AMD"
		last_gop   = last_amd_new
		efi_id_off = 0x20 ## might change it future versions
		id_in_gop  = False
		
		if is_vega_gop :
			gop_ids_file   = "#GOP_Files/amd_gop_IDs_2.4.0.0.0.txt"
			amd_gop_efirom = "amd_gop_vega.efirom"
			last_gop       = last_amd_vega
		else :
			gop_ids_file = "#GOP_Files/amd_gop_IDs.txt"
		
		## GOP 1.59.0.0.0 (and newer) has less IDs than 1.57.0.0.0, a double check is needed.
		with open(gop_ids_file, 'r+') as id_file:
			for line in id_file:
				if line[:9] == ven_dev :
					id_in_gop = True
					#print("The ID %s is present in the GOP!\n" % ven_dev)
					break
		
		if id_in_gop :
			amd_file = amd_gop_efirom
		else :
			print(Style.BRIGHT + Fore.YELLOW + "  Warning! Your VBIOS ID %s doesn't exist in latest available GOP!\n" % ven_dev + 
			Fore.RESET + Style.NORMAL)
			ask = input("\nDo you still want to update GOP? Y for yes or any key for checking the ID in older 1.57.0.0.0 GOP: ")
			
			if ask.strip().upper() == "Y" :
				amd_file = amd_gop_efirom
				print("")
			else :
				with open("#GOP_Files/amd_gop_IDs_1.57.0.0.0.txt", 'r+') as id_file:
					for line in id_file:
						if line[:9] == ven_dev :
							id_in_gop = True
							#print("The ID %s is present in the GOP!\n" % ven_dev)
							break
				print("")
				
				if id_in_gop :
					last_gop = last_amd_old ## This is only to have the proper updated version displayed.
					amd_file = "amd_gop_1.57.0.0.0.efirom"
				else :
					print(Style.BRIGHT + Fore.YELLOW + "  Warning! Your VBIOS ID %s doesn't exist in older GOP!\n" % ven_dev + 
					Fore.RESET + Style.NORMAL)
					ask = input("\nDo you still want to update GOP? A for %s, B for 1.57.0.0.0 or any key for exit: " % last_amd_new)
					ask = ask.strip().upper()
					
					if ask == "A" :
						amd_file = amd_gop_efirom
					elif ask == "B" :
						last_gop = last_amd_old ## This is only to have the proper updated version displayed.
						amd_file = "amd_gop_1.57.0.0.0.efirom"
					else :
						sys.exit()
					
					print("")
		
		## Relocate the microcode.
		## Struct of microcode - https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/radeon/atombios.h
		mc_reloc = False
		mc_found = False
		if pci_ven == '1002' and re.search(b'MCuC', reading) is not None :
			mcuc_list = re.finditer(b'MCuC', reading)
			
			for mcuc_match in mcuc_list :
				(mcuc_bgn, end_mcuc_match) = mcuc_match.span()
				
				mc_off = int.from_bytes(reading[mcuc_bgn - 8:mcuc_bgn - 4], 'little')
				
				if reading[mc_off:mc_off + 4] == b'MCuC' :
					mc_found = True
					
					with open("#GOP_Files/%s" % amd_file, 'rb') as amd_gop :
						gop_rom = amd_gop.read()
					
					end_img_new = orom_start + orom_size + len(gop_rom)
					
					## Nothing to do if microcode doesn't move.
					if end_img_new <= mc_off :
						print(Style.BRIGHT + Fore.YELLOW + "  AMD microcode will remain at the same offset.\n" + Fore.RESET + Style.NORMAL)
					else :
						mc_reloc  = True
						
						# TODO Relocation doesn't work, use old GOP
						if mc_reloc : #False :
							print(Style.BRIGHT + Fore.YELLOW + "  Warning! Your VBIOS doesn't have enough space for latest GOP and microcode!\n  If your card needs the microcode, an older and smaller GOP will be used\n" + Fore.RESET + Style.NORMAL)
							ask = input("\nDo you want the latest GOP or the microcode? A for latest GOP, B for microcode or any key for exit: ")
							ask = ask.strip().upper()
							
							if ask == "A" :
								amd_file = amd_gop_efirom
							elif ask == "B" :
								last_gop = last_amd_old ## This is only to have the proper updated version displayed.
								amd_file = "amd_gop_mcu.efirom"
								
								with open("#GOP_Files/%s" % amd_file, 'rb') as amd_gop :
									gop_rom = amd_gop.read()
								
								end_img_new = orom_start + orom_size + len(gop_rom)
							else :
								sys.exit()
							
							print("")
						
						parm_size = int.from_bytes(reading[mc_off + 8:mc_off + 0x0A], 'little')
						code_size = int.from_bytes(reading[mc_off + 0x0A:mc_off + 0x0C], 'little')
						mc_size   = 0x10 + parm_size + code_size
						#print("%0.2X" % mc_size)
						mc_round  = mc_size + ((0x10 - mc_size % 0x10) & 0x0F)
						#print("%0.2X" % mc_round)
						mc_end    = mc_off + mc_round
						#new_mc_off = end_img_new + mc_off - end_img_old
						mc_pad     = 0x1000 - (end_img_new % 0x1000) if (end_img_new % 0x1000) > 0 else 0
						new_mc_off = end_img_new + mc_pad
						new_mc_end = new_mc_off + mc_round
						new_mc_bin = new_mc_off.to_bytes(4, 'little')
						
						if new_mc_off != mc_off :
							print(Style.BRIGHT + Fore.YELLOW + "  AMD microcode will be relocated to offset 0x%0.2X.\n" % new_mc_off + Fore.RESET + Style.NORMAL)
							reading  = reading[:mcuc_bgn - 8] + new_mc_bin + reading[mcuc_bgn - 4:]#end_img_old] + reading[mc_off:mc_end]
							#reading  = reading[:mcuc_bgn - 8] + new_mc_bin + reading[mcuc_bgn - 4:mc_off] + b'\xFF' * mc_pad + reading[mc_off:]
					
					break
			
			else :
				print(Style.BRIGHT + Fore.YELLOW + "  AMD microcode pointer was found, but not its target!\n" + Fore.RESET + Style.NORMAL)
		
		with open("#GOP_Files/%s" % amd_file, 'rb') as amd_gop :
			gop_rom = amd_gop.read()
		
	elif gop_type == "Nvidia" and nv_type != "GXxxx" :
		
		#gop_type = "Nvidia"
		efi_id_off  = 0x20 ## might change it future versions
		efr_lst_off = 0x31 ## might change it future versions
		efi_lst_off = 0x4A ## might change it future versions
		
		## Make sure the Nvidia GOP is not customized. Only the last digit of variant ID should be non-zero.
		try :
			with open("#GOP_Files/%s" % nv_file, 'rb') as nv_gop :
				gop_rom = nv_gop.read()
		except :
			print(Style.BRIGHT + Fore.RED + "  Unable to find a matching GOP! Please report it!\n" + 
			Fore.RESET + Style.NORMAL)
			sys.exit()
	
	elif pci_ven == "10DE" and (gop_type == "" or gop_type == "Nvidia") :
		
		gop_type = "Nvidia"
		efi_id_off  = 0x20 ## might change it future versions
		efr_lst_off = 0x31 ## might change it future versions
		efi_lst_off = 0x4A ## might change it future versions
		
		print(Style.BRIGHT + Fore.YELLOW + "  Warning! GOP type missing! Continue only if you know what you are doing!\n" + 
		Fore.RESET + Style.NORMAL)
		
		gpu_hint = nvidia_board()
		
		print(Style.BRIGHT + Fore.YELLOW + "  Product name = %s. This might (!!) be used to determine your GPU architecture.\n" % gpu_hint + 
		Fore.RESET + Style.NORMAL)
		
		print("\nDo you still want to update GOP? Select the number of your GPU architecture: \n\n")
		print("  1 = GT21x")
		print("  2 = GF10x")
		print("  3 = GF119")
		print("  4 = GK1xx")
		print("  5 = GM1xx")
		print("  6 = GM2xx")
		print("  7 = GP1xx")
		print("  8 = GV1xx")
		print("  9 = TU1xx")
		print("  10 = GK1xx_MXM")
		print("  11 = GM1xx_MXM")
		
		while True :
			ask = input("\n\nEnter choice: ")
			ask = ask.strip()
			
			if ask == "1" :
				last_gop = last_nv_GT21x
				nv_file = "nv_gop_GT21x.efirom"
				break
			elif ask == "2" :
				last_gop = last_nv_GF10x
				nv_file = "nv_gop_GF10x.efirom"
				break
			elif ask == "3" :
				last_gop = last_nv_GF119
				nv_file = "nv_gop_GF119.efirom"
				break
			elif ask == "4" :
				last_gop = last_nv_GK1xx
				nv_file = "nv_gop_GK1xx.efirom"
				break
			elif ask == "5" :
				last_gop = last_nv_GM1xx
				nv_file = "nv_gop_GM1xx.efirom"
				break
			elif ask == "6" :
				last_gop = last_nv_GM2xx
				nv_file = "nv_gop_GM2xx.efirom"
				break
			elif ask == "7" :
				last_gop = last_nv_GP1xx
				nv_file = "nv_gop_GP1xx.efirom"
				break
			elif ask == "8" :
				last_gop = last_nv_GV1xx
				nv_file = "nv_gop_GV1xx.efirom"
				break
			elif ask == "9" :
				last_gop = last_nv_TU1xx
				nv_file = "nv_gop_TU1xx.efirom"
				break
			elif ask == "10" :
				last_gop = last_nv_GK1xx_MXM
				nv_file  = "nv_gop_GK1xx_MXM.efirom"
				break
			elif ask == "11" :
				last_gop = last_nv_GM1xx_MXM
				nv_file  = "nv_gop_GM1xx_MXM.efirom"
				break
			else :
				print("\nWrong choice! Self destruct in 10, 9, 8, ...")
				#sys.exit()
		
		print("")
		
		with open("#GOP_Files/%s" % nv_file, 'rb') as nv_gop :
			gop_rom = nv_gop.read()
	
	elif gop_type[:4] == "Mac_" :
		efi_id_off  = 0x20 ## Might not always be true
		efr_lst_off = 0x31 ## Might not always be true
		efi_lst_off = 0x4A ## Might not always be true
		
		if not os.path.isfile("#GOP_Files/%s" % mac_file) :
			print(Fore.RED + "File %s was not found!" % mac_file + Fore.RESET)
			sys.exit()
		
		with open("#GOP_Files/%s" % mac_file, 'rb') as mac_gop :
			gop_rom = mac_gop.read()
	else :
		print(Style.BRIGHT + Fore.YELLOW + "Only AMD and Nvidia GOP supported!" + Fore.RESET + Style.NORMAL)
		sys.exit()
	
	orom_end      = orom_start + orom_size
	orom_pci_last = orom_pcir_off + 0x15
	orom_last_img = ord(reading[orom_pcir_off + 0x15:orom_pcir_off + 0x16]) & 0x80
	end_img_old   = orom_end + efi_size ## This is only [IFR + ] ROM + EFI, not all sections.
	end_img_new   = orom_end + len(gop_rom)
	all_size      = len(reading)
	orom_cl_code  = reading[orom_pcir_off + 0xD:orom_pcir_off + 0x10]
	weird_npds_ps = False
	
	## Check for special images between ROM and EFI, but not in first container. Don't know why Nvidia is doing this.
	if efi_found and efi_begin != orom_end : # Already checked for weird data in rom_info, must be special images in between
		end_img_old   = efi_begin + efi_size
		end_img_new   = efi_begin + len(gop_rom)
		weird_npds_ps = True
	
	## TODO Special case for old type with EFI between ROM and special images with 55AA. Check after last image.
	## Check for other ROM images after ROM + EFI.
	if rom_info(reading, end_img_old, "basic") :
		print(Style.BRIGHT + Fore.RED + "  There are other ROM images in this binary! Please report it!\n" + 
			Fore.RESET + Style.NORMAL)
	
	## Fix first image for EFI pointing.
	if orom_last_img :
		
		print(Style.BRIGHT + Fore.YELLOW + "  Fixing last-image-bit in PCI Structure of Legacy ROM! \n" + Fore.RESET + Style.NORMAL)
		
		## Determine checksum byte
		if gop_type == "AMD" :
			imb_test = reading[orom_start + 0x1E:orom_start + 0x21]
			
			if imb_test == b'IBM' :
				ibm_end = orom_start + 0x21
				chk_is_last = False
			else :
				ibm_sig = re.search(br'\x49\x42\x4D', reading[:0xD0])
				
				if ibm_sig is not None :
					(start_ibm, ibm_end) = ibm_sig.span()
					chk_is_last = False
					print(Style.BRIGHT + Fore.YELLOW + "  Checksum byte of Legacy OROM at offset 0x%0.2X! \n" % ibm_end + 
					Fore.RESET + Style.NORMAL)
				else :
					ibm_end = orom_end - 1
					chk_is_last = True
			
			chk_int_old = ord(reading[ibm_end:ibm_end + 1])
			chk_off     = ibm_end
		
		elif gop_type == "Nvidia" :
			chk_int_old = ord(reading[orom_end - 1:orom_end])
			chk_off     = orom_end - 1
			chk_is_last = True
		
		## Determine if there is one container for all ROMs. EFI is most likely missing.
		## Are there images where PCIR size == NPDE size?
		orom_container = False
		
		if reading[orom_pcir_off + 0x20:orom_pcir_off + 0x24] == b'NPDE' :
			npde_size = int.from_bytes(reading[orom_pcir_off + 0x28:orom_pcir_off + 0x2A], 'little') * 0x200
			
			if orom_size != npde_size :
				print(Style.BRIGHT + Fore.RED + "  Different sizes in PCI structure and NPDE structure of Legacy ROM!\n" + 
				Fore.RESET + Style.NORMAL)
				
				orom_end_npde = orom_start + npde_size
				rom_test_npde = reading[orom_end_npde:orom_end_npde + 2]
				
				## If NPDE size is the right one, there is one container for all ROMs.
				if rom_test_npde in [b'\x55\xAA', b'\x56\x4E'] :
					orom_container = True
					print(Style.BRIGHT + Fore.YELLOW + "  The Legacy ROM appears to be a container for all images.\n" + 
					Fore.RESET + Style.NORMAL)
					print(Style.BRIGHT + Fore.YELLOW + "  Fixing last-image-bit in last special image of container.\n" + Fore.RESET + Style.NORMAL)
					nv_step      = orom_end_npde
					check_nv_ext = reading[nv_step:nv_step + 2]
					
					while check_nv_ext == b'\x56\x4E' or check_nv_ext == b'\x55\xAA' :
						
						nv_ext_size = int.from_bytes(reading[nv_step + 2:nv_step + 4], 'little') * 0x200
						#print(nv_ext_size)
						
						# Need this here for cases with container + other special images.
						npds_off = int.from_bytes(reading[nv_step + 0x18:nv_step + 0x1A], 'little')
						npds_off += nv_step
						
						if nv_ext_size == 0 :
							
							nv_ext_size = int.from_bytes(reading[npds_off + 0x10:npds_off + 0x12], 'little') * 0x200
							#print(nv_ext_size)
						
						npde_start = nv_step
						npde_end   = npde_start + nv_ext_size
						#print("Current = 0x%0.2X" % nv_step)
						nv_step += nv_ext_size
						#print("Next    = 0x%0.2X" % nv_step)
						
						# Don't go above container, leave the other special images as is.						
						if nv_step >= orom_start + orom_size :
							#print("End of container!")
							break
						
						check_nv_ext = reading[nv_step:nv_step + 2]
					
					lst_img_npds_off = npds_off + 0x15
					lst_npds_int_old = ord(reading[lst_img_npds_off:lst_img_npds_off + 1])
					lst_npds_int_new = int(lst_npds_int_old & 0x7F)
					lst_npds_bin_new = bytes([lst_npds_int_new])
					
					# Fix checksum for last image only
					#checksum_old = sum(bytearray(reading[orom_start:orom_end_npde - 1]))
					checksum_old = sum(bytearray(reading[npde_start:npde_end - 1]))
					checksum_new = (checksum_old - lst_npds_int_old + lst_npds_int_new) & 0xFF
					chk_int_new  = 256 - checksum_new if checksum_new else 0
					chk_bin_new  = bytes([chk_int_new])
					#print(chk_bin_new)
					
					# reading = reading[:orom_end_npde - 1] + chk_bin_new + reading[orom_end_npde:lst_img_npds_off] + \
							# lst_npds_bin_new + reading[lst_img_npds_off + 1:]
					
					reading = reading[:lst_img_npds_off] + lst_npds_bin_new + reading[lst_img_npds_off + 1:npde_end - 1] + chk_bin_new + reading[npde_end:]
					
					npde_off_test    = npds_off + 0x20
					lst_img_npde_off = npds_off + 0x2A
					
					if reading[npde_off_test:npde_off_test + 4] == b'NPDE' :
						lst_npde_int_old = ord(reading[lst_img_npde_off:lst_img_npde_off + 1])
						lst_npde_int_new = int(lst_npde_int_old & 0x7F)		
						lst_npde_bin_new = bytes([lst_npde_int_new])
						
						reading = reading[:lst_img_npde_off] + lst_npde_bin_new + reading[lst_img_npde_off + 1:]
		
		if orom_container :
			checksum_old = sum(bytearray(reading[orom_start:orom_end_npde]))
			chk_int_old = ord(reading[orom_end_npde - 1:orom_end_npde])
		else :
			checksum_old = sum(bytearray(reading[orom_start:orom_end])) ## sumbytes(reading[orom_start:orom_end])
		
		lst_int_old  = ord(reading[orom_pci_last:orom_pci_last + 1])
		lst_int_new  = int(lst_int_old & 0x7F)
		lst_bin_new  = bytes([lst_int_new])
		
		checksum_new = (checksum_old - chk_int_old - lst_int_old + lst_int_new) & 0xFF
		
		chk_int_new  = 256 - checksum_new if checksum_new else 0
		chk_bin_new  = bytes([chk_int_new])
		
		if chk_is_last :
			print(Style.BRIGHT + Fore.YELLOW + "  Using last byte for checksum! \n" + Fore.RESET + Style.NORMAL)
			
			if orom_container :
				new_gop = reading[:orom_pci_last] + lst_bin_new + reading[orom_pci_last + 1:orom_end_npde - 1] + chk_bin_new + reading[orom_end_npde:orom_end]
			else :
				new_gop = reading[:orom_pci_last] + lst_bin_new + reading[orom_pci_last + 1:orom_end - 1] + chk_bin_new
		else :
			print(Style.BRIGHT + Fore.YELLOW + "  Using AMD byte for checksum! \n" + Fore.RESET + Style.NORMAL)
			new_gop = reading[:chk_off] + chk_bin_new + reading[chk_off + 1:orom_pci_last] + lst_bin_new + reading[orom_pci_last + 1:orom_end]
	else :
		new_gop = reading[:orom_end]
	
	## Add special images between ROM and EFI. If they are present and not part of main container, nothing else to do.
	## The last-bit is already set in ROM and special images.
	if weird_npds_ps :
		new_gop += reading[orom_end:efi_begin]
	
	## Assembly a new image
	if gop_type == "Nvidia" or gop_type == "Mac_Nvidia" :
		## Nvidia has special images and special structures, needs more care.
		efi_id_old   = sum(bytearray(gop_rom[efi_id_off:efi_id_off + 4]))
		efi_lst_old  = ord(gop_rom[efi_lst_off:efi_lst_off + 1]) #sum(bytearray(gop_rom[efi_lst_off:efi_lst_off + 1]))
		efr_lst_old  = ord(gop_rom[efr_lst_off:efr_lst_off + 1]) #sum(bytearray(gop_rom[efr_lst_off:efr_lst_off + 1]))
		checksum_old = sum(bytearray(gop_rom[:-1]))
		nvsp_data    = b''
		
		## Check if EFI is last image in Nvidia VBIOS. Change the bit in NPDE.
		check_nv_ext = reading[end_img_old:end_img_old + 2]
		if check_nv_ext == b'\x56\x4E' or check_nv_ext == b'\x55\xAA' :
			print(Style.BRIGHT + Fore.YELLOW + "  EFI is NOT last image!\n" + Fore.RESET + Style.NORMAL)
			efi_lst_new = int(efi_lst_old & 0x7F)
			efr_lst_new = int(efr_lst_old & 0x7F)
			## Remove end padding from dumped images.
			nv_step  = end_img_old
			
			while check_nv_ext == b'\x56\x4E' or check_nv_ext == b'\x55\xAA' :
				nv_ext_size = int.from_bytes(reading[nv_step + 2:nv_step + 4], 'little') * 0x200
				#print("Size = 0x%0.2X" % nv_ext_size)
				
				# Need this here for cases with container + other special images.
				npds_off = int.from_bytes(reading[nv_step + 0x18:nv_step + 0x1A], 'little')
				npds_off += nv_step
				
				if nv_ext_size == 0 :
					nv_ext_size = int.from_bytes(reading[npds_off + 0x10:npds_off + 0x12], 'little') * 0x200
					#print("Size = 0x%0.2X" % nv_ext_size)
				
				#print("Current = 0x%0.2X" % nv_step)
				nv_step += nv_ext_size
				#print("Next    = 0x%0.2X\n" % nv_step)
				check_nv_ext = reading[nv_step:nv_step + 2]
			else :
				#print("end_img_old = 0x%0.2X" % end_img_old)
				#print("Final step  = 0x%0.2X\n" % nv_step)
				turing_one = 0
				
				if efi_found and nv_type == "TU1xx" : # Turing has a backup image
					turing_pad  = 0x1000 - (nv_step % 0x1000) if (nv_step % 0x1000) > 0 else 0
					turing_one  = turing_pad + nv_step
					end_img_old += turing_one
					nv_step     += turing_one
					#print("end_img_old = 0x%0.2X" % end_img_old)
					#print("Final step  = 0x%0.2X\n" % nv_step)
					check_nv_ext = reading[nv_step:nv_step + 2]
					
					if reading[turing_one:turing_one + 4] != b'NVGI' :
						print(Style.BRIGHT + Fore.RED + "  Backup image not in expected place! Aborting...\n" + Fore.RESET + Style.NORMAL)
						sys.exit()
					
					if reading[efi_begin + turing_one + 4:efi_begin + turing_one + 8] != b'\xF1\x0E\x00\x00' :
						print(Style.BRIGHT + Fore.RED + "  Backup EFI image not in expected place! Aborting...\n" + Fore.RESET + Style.NORMAL)
						sys.exit()
					
					for idx in range(0, turing_one) :
						if reading[idx:idx + 1] != reading[turing_one + idx:turing_one + idx + 1] :
							print(Style.BRIGHT + Fore.RED + "  Backup image not identical to main image! Be careful...\n" + Fore.RESET + Style.NORMAL)
							break
				
				if check_nv_ext == b'' :
					## No extra data and no padding, so we can re-add special images as end data.
					nvsp_data = reading[end_img_old:]
					end_data  = b''
				else :
					print(Style.BRIGHT + Fore.YELLOW + "  Removing unnecessary end padding.\n" + Fore.RESET + Style.NORMAL)
					nvsp_data = reading[end_img_old:nv_step] ## This is the normal situation, where only padding follows last special image.
					end_data  = b''
					#print(end_data[:0x10])
					#print("len end_data = 0x%0.2X\n" % len(end_data))
					str_err  = "  Data after Nvidia special images! Please report it!\n"
					end_img_new += nv_step - end_img_old + turing_one # adding size of special images
					end_img_old = nv_step
					#print("end_img_old = 0x%0.2X" % end_img_old)
					#print("end_img_new = 0x%0.2X\n" % end_img_new)
					#end_data = remove_padding(end_data, nv_step, end_img_new, all_size, str_err)
					end_data = remove_padding(end_img_old, end_img_new, all_size, str_err)
					#print(end_data[:0x10])
					#print("len end_data = 0x%0.2X\n" % len(end_data))
		
		else :
			print(Style.BRIGHT + Fore.YELLOW + "  EFI is last image.\n" + Fore.RESET + Style.NORMAL)
			efi_lst_new = int(efi_lst_old | 0x80)
			efr_lst_new = int(efr_lst_old | 0x80)
			## Remove end padding from dumped images.
			end_data = b''
			
			if end_img_old < all_size :
				print(Style.BRIGHT + Fore.YELLOW + "  Removing unnecessary end padding.\n" + Fore.RESET + Style.NORMAL)
				str_err  = "  Data after ROM and not part of Nvidia special images! Please report it!\n"
				end_data = remove_padding(end_img_old, end_img_new, all_size, str_err)
		
		efi_id_new      = sum(bytearray(orom_id_bin))
		efi_lst_bin_new = bytes([efi_lst_new])
		efr_lst_bin_new = bytes([efr_lst_new])
		
		print(Style.BRIGHT + Fore.YELLOW + "  Fixing ID, last-image-bit and checksum for EFI image.\n" + Fore.RESET + Style.NORMAL)
		
		if orom_old_type : # The special images after legacy ROM have AA55 header. Fix PCIR and NPDE.
			print(Style.BRIGHT + Fore.YELLOW + "  Fixing last-image-bit in PCIR and NPDE for EFI image.\n" + Fore.RESET + Style.NORMAL)
		else : # The special images after legacy ROM have NV header. Fix only NPDE.
			
			if not efi_found or (efi_found and efi_last_img) : # There are no other AA55 ROM images after EFI. Fix only NPDE.
				efr_lst_new     = efr_lst_old
				efr_lst_bin_new = bytes([efr_lst_new])
			#else : GP104_NotLast.rom -> Say hello to one weird image. Both AA55 and NV headers.
				
		checksum_new    = (checksum_old - efi_id_old - efr_lst_old - efi_lst_old + efi_id_new + efr_lst_new + efi_lst_new) & 0xFF
		efi_chk_int_new = 256 - checksum_new if checksum_new else 0
		efi_chk_bin_new = bytes([efi_chk_int_new])
		
		if efi_found and nv_type == "TU1xx" : # Turing has a backup image
			new_gop += gop_rom[:efi_id_off] + orom_id_bin + gop_rom[efi_id_off + 4:efi_id_off + 9] + efi_class_bin + \
					gop_rom[efi_id_off + 0xC:efr_lst_off] + efr_lst_bin_new + gop_rom[efr_lst_off + 1:efi_lst_off] + \
					efi_lst_bin_new + gop_rom[efi_lst_off + 1:-1] + efi_chk_bin_new + nvsp_data
			new_gop = new_gop + (b'\xFF' * turing_pad) + new_gop + end_data
		else :
			new_gop += gop_rom[:efi_id_off] + orom_id_bin + gop_rom[efi_id_off + 4:efi_id_off + 9] + efi_class_bin + \
					gop_rom[efi_id_off + 0xC:efr_lst_off] + efr_lst_bin_new + gop_rom[efr_lst_off + 1:efi_lst_off] + \
					efi_lst_bin_new + gop_rom[efi_lst_off + 1:-1] + efi_chk_bin_new + nvsp_data + end_data
	
	else :
		## gop_type is "AMD"
		## AMD has no special images, from limited testing.
		print(Style.BRIGHT + Fore.YELLOW + "  Fixing ID for EFI image. No checksum correction is needed.\n" + Fore.RESET + Style.NORMAL)
		
		## Remove end padding from dumped images.
		end_data = b''
		
		## Standard error message for extra data
		str_err  = "  Data after ROM and not part of EFI! Please report it!\n"
		
		## If AMD microcode is present, check for extra data after it. Assume none before.
		if mc_reloc :
			str_err  = "  Data after microcode! Please report it!\n"
			end_img_old = mc_end
			end_img_new = new_mc_end
		
		if end_img_old < all_size :
			print(Style.BRIGHT + Fore.YELLOW + "  Removing unnecessary end padding.\n" + Fore.RESET + Style.NORMAL)
			#str_err  = "  Data after ROM and not part of EFI! Please report it!\n"
			end_data = remove_padding(end_img_old, end_img_new, all_size, str_err)
		
		## Add the microcode and any extra data.
		if mc_reloc :
			end_data = b'\xFF' * mc_pad + reading[mc_off:mc_end] + end_data
				
		new_gop += gop_rom[:efi_id_off] + orom_id_bin + gop_rom[efi_id_off + 4:efi_id_off + 9] + efi_class_bin + \
					gop_rom[efi_id_off + 0xC:] + end_data
	
	with open("%s_updGOP%s" % (fileName, fileExtension), 'wb') as my_gop :
		my_gop.write(new_gop)
	
	print(Style.BRIGHT + Fore.CYAN + "\nFile \"%s_updGOP%s\" with updated GOP %s was written!\n" % (fileName, fileExtension, last_gop) + 
	Fore.RESET + Style.NORMAL)
	
	if gop_type == "AMD" and amd_gop_efirom == "amd_gop_mod.efirom" :
		print(Style.BRIGHT + Fore.CYAN + "\nPatched GOP was used!\n" + Fore.RESET + Style.NORMAL)

###########################################################
