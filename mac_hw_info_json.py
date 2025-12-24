#!/usr/bin/env python3
"""
Mac Hardware Info - Simple JSON Output

A minimal script that collects Mac hardware identifiers and outputs them as JSON.
No pip dependencies required - uses only Python standard library.

The JSON output can be pasted into the accompanying HTML file to generate a QR code.

Usage:
    python3 mac_hw_info_json.py
    python3 mac_hw_info_json.py > hw_info.json
"""

import subprocess
import re
import hashlib
import json
import sys
import base64
import plistlib


def run_command(cmd):
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_platform_info():
    """Get platform information from IOPlatformExpertDevice."""
    info = {}
    try:
        output = run_command(['ioreg', '-a', '-c', 'IOPlatformExpertDevice'])
        data = plistlib.loads(output.encode())
        
        def extract_from_dict(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k in ['IOPlatformSerialNumber', 'IOPlatformUUID', 'model', 'product-name', 'board-id', 'unique-chip-id', 'mlb-serial-number']:
                        if isinstance(v, bytes):
                            if k in ['unique-chip-id']:
                                info[k] = base64.b64encode(v).decode('ascii')
                            else:
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
        print(f"Warning: Failed to parse platform info: {e}", file=sys.stderr)
    
    return info


def get_mac_address():
    """Get the primary MAC address as hex string."""
    try:
        output = run_command(['ioreg', '-r', '-c', 'IOEthernetController', '-l'])
        
        for line in output.split('\n'):
            if '"IOMACAddress"' in line:
                match = re.search(r'<([0-9a-fA-F\s]+)>', line)
                if match:
                    return match.group(1).replace(' ', '').lower()
        
        # Fallback: try networksetup
        output = run_command(['networksetup', '-getmacaddress', 'en0'])
        match = re.search(r'([0-9a-fA-F:]{17})', output)
        if match:
            return match.group(1).replace(':', '').lower()
    except Exception as e:
        print(f"Warning: Failed to get MAC address: {e}", file=sys.stderr)
    
    return "000000000000"


def get_sysctl(name):
    """Get a sysctl value."""
    return run_command(['sysctl', '-n', name])


def get_iopower_value(key):
    """Get encrypted values from IOPower registry as hex string."""
    try:
        output = run_command(['ioreg', '-r', '-c', 'IOPMrootDomain', '-l'])
        
        for line in output.split('\n'):
            if f'"{key}"' in line:
                match = re.search(r'<([0-9a-fA-F\s]+)>', line)
                if match:
                    return match.group(1).replace(' ', '').lower()
    except Exception as e:
        print(f"Warning: Failed to get IOPower value {key}: {e}", file=sys.stderr)
    
    return ""


def get_nvram_value(key):
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


def get_boot_uuid():
    """Get the boot volume UUID."""
    try:
        output = run_command(['diskutil', 'info', '/'])
        for line in output.split('\n'):
            if 'Volume UUID' in line:
                match = re.search(r':\s*([A-F0-9-]+)', line)
                if match:
                    return match.group(1)
    except Exception as e:
        print(f"Warning: Failed to get boot UUID: {e}", file=sys.stderr)
    return ""


def get_rom(platform_info):
    """Get ROM value as hex string."""
    # Try NVRAM first (Intel Macs)
    rom_value = get_nvram_value('4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14:ROM')
    if rom_value:
        try:
            cleaned = rom_value.replace('%', '')
            # Validate it's hex
            bytes.fromhex(cleaned)
            return cleaned.lower()
        except:
            return rom_value.encode().hex()
    
    # M1 Macs: derive from unique-chip-id
    unique_chip_id_b64 = platform_info.get('unique-chip-id')
    if unique_chip_id_b64:
        try:
            unique_chip_id = base64.b64decode(unique_chip_id_b64)
            hash_value = hashlib.sha256(unique_chip_id).digest()
            return hash_value[-6:].hex()
        except Exception as e:
            print(f"Warning: Failed to derive ROM from unique-chip-id: {e}", file=sys.stderr)
    
    return ""


def get_mlb(platform_info):
    """Get MLB (Main Logic Board) serial number."""
    # Try NVRAM first
    mlb = get_nvram_value('4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14:MLB')
    if mlb:
        return mlb.strip()
    
    # From platform info
    if 'mlb-serial-number' in platform_info:
        return platform_info['mlb-serial-number']
    
    return ""


def get_board_id(platform_info):
    """Get board ID."""
    if 'board-id' in platform_info:
        board_id = platform_info['board-id']
        if board_id.startswith('Mac-'):
            return board_id
        # It might be raw bytes that need Mac- prefix
        try:
            return 'Mac-' + bytes.fromhex(board_id).hex()
        except:
            return board_id
    
    # Try IODeviceTree for M1
    try:
        output = run_command(['ioreg', '-a', '-p', 'IODeviceTree', '-c', 'IOPlatformExpertDevice'])
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
        
        return find_board_id(data) or ""
    except:
        pass
    
    return ""


def collect_hw_info():
    """Collect all hardware information and return as dictionary."""
    platform_info = get_platform_info()
    
    hw_info = {
        "inner": {
            "product_name": platform_info.get('product-name', platform_info.get('model', '')),
            "io_mac_address": get_mac_address(),
            "platform_serial_number": platform_info.get('IOPlatformSerialNumber', ''),
            "platform_uuid": platform_info.get('IOPlatformUUID', ''),
            "root_disk_uuid": get_boot_uuid(),
            "board_id": get_board_id(platform_info),
            "os_build_num": get_sysctl('kern.osversion'),
            "platform_serial_number_enc": get_iopower_value('Gq3489ugfi'),
            "platform_uuid_enc": get_iopower_value('Fyp98tpgj'),
            "root_disk_uuid_enc": get_iopower_value('kbjfrfpoJU'),
            "rom": get_rom(platform_info),
            "rom_enc": get_iopower_value('oycqAZloTNDm'),
            "mlb": get_mlb(platform_info),
            "mlb_enc": get_iopower_value('abKPld1EcMni'),
        },
        "version": get_sysctl('kern.osproductversion'),
        "protocol_version": 1640,
        "device_id": platform_info.get('IOPlatformUUID', ''),
        "icloud_ua": "com.apple.iCloudHelper/282 CFNetwork/1408.0.4 Darwin/22.5.0",
        "aoskit_version": "com.apple.AOSKit/282 (com.apple.accountsd/113)"
    }
    
    return hw_info


def main():
    """Main entry point."""
    import platform
    
    if platform.system() != 'Darwin':
        print("Error: This script only works on macOS.", file=sys.stderr)
        sys.exit(1)
    
    print("Collecting Mac hardware information...", file=sys.stderr)
    
    try:
        hw_info = collect_hw_info()
    except Exception as e:
        print(f"Error collecting hardware info: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print summary to stderr
    print("\nCollected hardware information:", file=sys.stderr)
    print(f"  Product Name: {hw_info['inner']['product_name']}", file=sys.stderr)
    serial = hw_info['inner']['platform_serial_number']
    if len(serial) > 4:
        print(f"  Serial Number: {'*' * (len(serial) - 4)}{serial[-4:]}", file=sys.stderr)
    else:
        print(f"  Serial Number: {serial}", file=sys.stderr)
    uuid = hw_info['inner']['platform_uuid']
    print(f"  Platform UUID: {uuid[:8]}...{uuid[-4:]}", file=sys.stderr)
    print(f"  macOS Version: {hw_info['version']}", file=sys.stderr)
    print(f"  OS Build: {hw_info['inner']['os_build_num']}", file=sys.stderr)
    
    print("\n--- JSON OUTPUT (copy this into the HTML interface) ---\n", file=sys.stderr)
    
    # Output JSON to stdout for easy piping/copying
    print(json.dumps(hw_info, indent=2))
    
    print("\n--- END JSON OUTPUT ---", file=sys.stderr)
    print("\nYou can redirect stdout to a file: python3 mac_hw_info_json.py > hw_info.json", file=sys.stderr)


if __name__ == '__main__':
    main()
