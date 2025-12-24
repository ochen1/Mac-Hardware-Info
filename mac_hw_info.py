#!/usr/bin/env python3
"""
Mac Hardware Info - Collects Mac hardware identifiers and outputs as QR code or binary file.

This script collects hardware information from a Mac and outputs it in a format
compatible with OpenBubbles. It tries to display a QR code if the 'qrcode' library
is installed, otherwise it saves the data to a .bin file that can be converted
to a QR code using 'qrencode'.

Usage:
    python3 mac_hw_info.py

Requirements:
    - macOS (uses ioreg and sysctl commands)
    - protobuf library (pip install protobuf)
    - Optional: qrcode library for QR output (pip install qrcode[pil])
"""

import subprocess
import re
import hashlib
import sys
import os

# Try to import protobuf - required
try:
    import mac_hw_info_pb2 as pb
except ImportError:
    print("Error: mac_hw_info_pb2 module not found.")
    print("Make sure mac_hw_info_pb2.py is in the same directory as this script.")
    print("You can generate it with: protoc --python_out=. mac_hw_info.proto")
    sys.exit(1)

# ============================================================================
# Hardware Information Collection Functions
# ============================================================================

def run_command(cmd: list[str]) -> str:
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Warning: Command failed: {' '.join(cmd)}")
        return ""

def get_ioreg_value(path: str, key: str, as_bytes: bool = False) -> str | bytes | None:
    """Get a value from the IORegistry."""
    try:
        output = run_command(['ioreg', '-r', '-d', '1', '-p', path, '-l'])
        
        # Try to find the key in the output
        for line in output.split('\n'):
            if f'"{key}"' in line:
                # Extract value - could be string or data
                if '<' in line and '>' in line:
                    # It's binary data
                    match = re.search(r'<([0-9a-fA-F\s]+)>', line)
                    if match:
                        hex_str = match.group(1).replace(' ', '')
                        data = bytes.fromhex(hex_str)
                        return data if as_bytes else data.decode('utf-8', errors='replace').rstrip('\x00')
                else:
                    # It's a string value
                    match = re.search(r'"' + re.escape(key) + r'"\s*=\s*"([^"]*)"', line)
                    if match:
                        return match.group(1).encode() if as_bytes else match.group(1)
    except Exception as e:
        print(f"Warning: Failed to get {key} from {path}: {e}")
    return None

def get_ioreg_entry(entry_path: str, key: str, as_bytes: bool = False) -> str | bytes | None:
    """Get a value from a specific IORegistry entry path."""
    try:
        output = run_command(['ioreg', '-a', '-c', 'IOPlatformExpertDevice'])
        
        # Parse the output to find the key
        for line in output.split('\n'):
            if f'<key>{key}</key>' in line:
                # Next line should have the value
                continue
            if key in line:
                match = re.search(r'<string>([^<]+)</string>', line)
                if match:
                    return match.group(1).encode() if as_bytes else match.group(1)
                match = re.search(r'<data>([^<]+)</data>', line)
                if match:
                    import base64
                    data = base64.b64decode(match.group(1))
                    return data if as_bytes else data.decode('utf-8', errors='replace').rstrip('\x00')
    except Exception as e:
        print(f"Warning: Failed to get {key}: {e}")
    return None

def get_platform_info() -> dict:
    """Get platform information from IOPlatformExpertDevice."""
    info = {}
    try:
        output = run_command(['ioreg', '-a', '-c', 'IOPlatformExpertDevice'])
        
        # Parse keys we need
        import plistlib
        data = plistlib.loads(output.encode())
        
        def extract_from_dict(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k in ['IOPlatformSerialNumber', 'IOPlatformUUID', 'model', 'product-name', 'board-id']:
                        if isinstance(v, bytes):
                            info[k] = v.rstrip(b'\x00').decode('utf-8', errors='replace')
                        else:
                            info[k] = str(v)
                    elif isinstance(v, (dict, list)):
                        extract_from_dict(v)
            elif isinstance(d, list):
                for item in d:
                    extract_from_dict(item)
        
        extract_from_dict(data)
    except Exception as e:
        print(f"Warning: Failed to parse platform info: {e}")
    
    return info

def get_mac_address() -> bytes:
    """Get the primary MAC address."""
    try:
        # Use ioreg to get the primary ethernet interface MAC address
        output = run_command(['ioreg', '-r', '-c', 'IOEthernetController', '-l'])
        
        for line in output.split('\n'):
            if '"IOMACAddress"' in line:
                match = re.search(r'<([0-9a-fA-F\s]+)>', line)
                if match:
                    hex_str = match.group(1).replace(' ', '')
                    return bytes.fromhex(hex_str)
        
        # Fallback: try networksetup
        output = run_command(['networksetup', '-getmacaddress', 'en0'])
        match = re.search(r'([0-9a-fA-F:]{17})', output)
        if match:
            return bytes.fromhex(match.group(1).replace(':', ''))
    except Exception as e:
        print(f"Warning: Failed to get MAC address: {e}")
    
    return b'\x00' * 6

def get_sysctl(name: str) -> str:
    """Get a sysctl value."""
    return run_command(['sysctl', '-n', name])

def get_iopower_value(key: str) -> bytes:
    """Get encrypted values from IOPower registry."""
    try:
        output = run_command(['ioreg', '-r', '-c', 'IOPMrootDomain', '-l'])
        
        for line in output.split('\n'):
            if f'"{key}"' in line:
                match = re.search(r'<([0-9a-fA-F\s]+)>', line)
                if match:
                    hex_str = match.group(1).replace(' ', '')
                    return bytes.fromhex(hex_str)
    except Exception as e:
        print(f"Warning: Failed to get IOPower value {key}: {e}")
    
    return b''

def get_nvram_value(key: str) -> str | None:
    """Get a value from NVRAM."""
    try:
        output = run_command(['nvram', key])
        if output:
            parts = output.split('\t', 1)
            if len(parts) > 1:
                return parts[1]
    except Exception:
        pass
    return None

def get_boot_uuid() -> str:
    """Get the boot volume UUID."""
    try:
        output = run_command(['diskutil', 'info', '/'])
        for line in output.split('\n'):
            if 'Volume UUID' in line:
                match = re.search(r':\s*([A-F0-9-]+)', line)
                if match:
                    return match.group(1)
    except Exception as e:
        print(f"Warning: Failed to get boot UUID: {e}")
    return ""

def get_rom() -> bytes:
    """Get ROM value from NVRAM or derive from unique-chip-id for M1 Macs."""
    # Try NVRAM first (Intel Macs)
    rom_value = get_nvram_value('4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14:ROM')
    if rom_value:
        # Parse the value - it may be in various formats
        try:
            # Remove any prefix like %XX encoding
            cleaned = rom_value.replace('%', '')
            return bytes.fromhex(cleaned)
        except:
            return rom_value.encode()
    
    # M1 Macs: derive from unique-chip-id
    try:
        output = run_command(['ioreg', '-a', '-c', 'IOPlatformExpertDevice'])
        import plistlib
        data = plistlib.loads(output.encode())
        
        def find_unique_chip_id(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == 'unique-chip-id' and isinstance(v, bytes):
                        return v
                    result = find_unique_chip_id(v)
                    if result:
                        return result
            elif isinstance(d, list):
                for item in d:
                    result = find_unique_chip_id(item)
                    if result:
                        return result
            return None
        
        unique_chip_id = find_unique_chip_id(data)
        if unique_chip_id:
            # Take last 6 bytes of SHA256 hash
            hash_value = hashlib.sha256(unique_chip_id).digest()
            return hash_value[-6:]
    except Exception as e:
        print(f"Warning: Failed to get ROM: {e}")
    
    return b''

def get_mlb() -> str:
    """Get MLB (Main Logic Board) serial number."""
    # Try NVRAM first
    mlb = get_nvram_value('4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14:MLB')
    if mlb:
        return mlb.strip()
    
    # Try IODeviceTree
    try:
        output = run_command(['ioreg', '-a', '-c', 'IOPlatformExpertDevice'])
        import plistlib
        data = plistlib.loads(output.encode())
        
        def find_mlb(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == 'mlb-serial-number':
                        if isinstance(v, bytes):
                            return v.rstrip(b'\x00').decode('utf-8', errors='replace')
                        return str(v)
                    result = find_mlb(v)
                    if result:
                        return result
            elif isinstance(d, list):
                for item in d:
                    result = find_mlb(item)
                    if result:
                        return result
            return None
        
        result = find_mlb(data)
        if result:
            return result
    except Exception as e:
        print(f"Warning: Failed to get MLB: {e}")
    
    return ""

def get_hw_info() -> pb.HwInfo:
    """Collect all hardware information and return as HwInfo protobuf message."""
    platform_info = get_platform_info()
    
    # Build the inner message
    inner = pb.HwInfo.InnerHwInfo()
    inner.product_name = platform_info.get('product-name', platform_info.get('model', ''))
    inner.io_mac_address = get_mac_address()
    inner.platform_serial_number = platform_info.get('IOPlatformSerialNumber', '')
    inner.platform_uuid = platform_info.get('IOPlatformUUID', '')
    inner.root_disk_uuid = get_boot_uuid()
    
    board_id = platform_info.get('board-id', '')
    if not board_id:
        # Try to construct from IODeviceTree for M1
        try:
            output = run_command(['ioreg', '-a', '-p', 'IODeviceTree', '-c', 'IOPlatformExpertDevice'])
            import plistlib
            data = plistlib.loads(output.encode())
            
            def find_board_id(d):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if k == 'board-id':
                            if isinstance(v, bytes):
                                return 'Mac-' + v.hex()
                            return str(v)
                        result = find_board_id(v)
                        if result:
                            return result
                elif isinstance(d, list):
                    for item in d:
                        result = find_board_id(item)
                        if result:
                            return result
                return None
            
            board_id = find_board_id(data) or ''
        except:
            pass
    inner.board_id = board_id
    
    inner.os_build_num = get_sysctl('kern.osversion')
    
    # Get encrypted values from IOPower
    inner.platform_serial_number_enc = get_iopower_value('Gq3489ugfi')
    inner.platform_uuid_enc = get_iopower_value('Fyp98tpgj')
    inner.root_disk_uuid_enc = get_iopower_value('kbjfrfpoJU')
    inner.rom = get_rom()
    inner.rom_enc = get_iopower_value('oycqAZloTNDm')
    inner.mlb = get_mlb()
    inner.mlb_enc = get_iopower_value('abKPld1EcMni')
    
    # Build the outer message
    hw_info = pb.HwInfo()
    hw_info.inner.CopyFrom(inner)
    hw_info.version = get_sysctl('kern.osproductversion')
    hw_info.protocol_version = 1640
    hw_info.device_id = platform_info.get('IOPlatformUUID', '')
    hw_info.icloud_ua = 'com.apple.iCloudHelper/282 CFNetwork/1408.0.4 Darwin/22.5.0'
    hw_info.aoskit_version = 'com.apple.AOSKit/282 (com.apple.accountsd/113)'
    
    return hw_info

def create_payload(hw_info: pb.HwInfo, prevent_sharing: bool = False) -> bytes:
    """Create the payload with OABS prefix."""
    data = b'OABS'
    data += bytes([1 if prevent_sharing else 0])
    data += hw_info.SerializeToString()
    return data

def output_qr(data: bytes, filename: str = 'mac_hw_info.bin') -> None:
    """Try to output QR code, fallback to binary file."""
    try:
        import qrcode
        
        # Create QR code
        qr = qrcode.QRCode(
            version=None,  # Auto-determine
            error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Try to display in terminal
        try:
            qr.print_ascii(invert=True)
            print("\nQR code displayed above. You can also scan it from the saved image.")
        except:
            pass
        
        # Save as PNG
        img = qr.make_image(fill_color="black", back_color="white")
        png_filename = filename.replace('.bin', '.png')
        img.save(png_filename)
        print(f"QR code saved to: {png_filename}")
        
    except ImportError:
        # QR library not available, save as binary
        print("Note: 'qrcode' library not installed. Saving as binary file.")
        print("To install: pip install qrcode[pil]")
        print(f"To generate QR manually: qrencode -r {filename} -o qr.png")
        
        with open(filename, 'wb') as f:
            f.write(data)
        print(f"Binary data saved to: {filename}")

def main():
    """Main entry point."""
    import platform
    
    if platform.system() != 'Darwin':
        print("Error: This script only works on macOS.")
        sys.exit(1)
    
    print("Collecting Mac hardware information...")
    
    try:
        hw_info = get_hw_info()
    except Exception as e:
        print(f"Error collecting hardware info: {e}")
        sys.exit(1)
    
    # Display collected info (masked for privacy)
    print("\nCollected hardware information:")
    print(f"  Product Name: {hw_info.inner.product_name}")
    serial = hw_info.inner.platform_serial_number
    if len(serial) > 4:
        print(f"  Serial Number: {'*' * (len(serial) - 4)}{serial[-4:]}")
    else:
        print(f"  Serial Number: {serial}")
    print(f"  Platform UUID: {hw_info.inner.platform_uuid[:8]}...{hw_info.inner.platform_uuid[-4:]}")
    print(f"  macOS Version: {hw_info.version}")
    print(f"  OS Build: {hw_info.inner.os_build_num}")
    
    # Create payload
    payload = create_payload(hw_info, prevent_sharing=False)
    print(f"\nPayload size: {len(payload)} bytes")
    
    # Output
    output_qr(payload)

if __name__ == '__main__':
    main()
