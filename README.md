# Mac Hardware Info

Collects Mac hardware identifiers and outputs them as a QR code for use with OpenBubbles.

## Options

There are two ways to use this tool:

### Option 1: Simple JSON Script + HTML Interface (No Dependencies)

The simplest approach with zero pip dependencies:

1. Run the JSON script on your Mac:
   ```bash
   python3 mac_hw_info_json.py
   ```

2. Copy the JSON output

3. Open `mac_hw_info.html` in any web browser

4. Paste the JSON and click "Generate QR Code"

### Option 2: Full Python Script (Requires protobuf)

A more complete script that generates QR codes directly:

```bash
pip install protobuf
pip install qrcode[pil]  # Optional, for QR code output
python3 mac_hw_info.py
```

## Requirements

- **macOS** (uses `ioreg`, `sysctl`, and other macOS-specific commands)
- **Python 3.8+**
- For `mac_hw_info.py`: **protobuf** library (`pip install protobuf`)
- For `mac_hw_info_json.py`: No dependencies (uses only Python standard library)

## Files

| File | Description | Dependencies |
|------|-------------|--------------|
| `mac_hw_info_json.py` | Simple script that outputs JSON | None |
| `mac_hw_info.html` | Self-contained HTML interface for QR generation | None (works in browser) |
| `mac_hw_info.py` | Full script with protobuf serialization | protobuf |
| `mac_hw_info.proto` | Protocol Buffer definition | None |
| `mac_hw_info_pb2.py` | Generated Protocol Buffer module | protobuf |

## How It Works

The scripts collect the following hardware information from your Mac:

- Product name/model
- Primary MAC address
- Platform serial number
- Platform UUID
- Boot disk UUID
- Board ID
- OS build number
- ROM
- MLB (Main Logic Board) serial number
- Various encrypted values from IOPower registry

This information is serialized using Protocol Buffers with an "OABS" prefix, matching the format expected by OpenBubbles.

## Security Notice

This script accesses sensitive hardware identifiers from your Mac. The output contains unique identifiers that can be used to identify your specific machine. Do not share the generated QR code or binary file publicly.

## License

See LICENSE file for details.
