# Mac Hardware Info

A simple Python script that collects Mac hardware identifiers and outputs them as a QR code or binary file for use with OpenBubbles.

## Requirements

- **macOS** (uses `ioreg`, `sysctl`, and other macOS-specific commands)
- **Python 3.8+**
- **protobuf** library: `pip install protobuf`
- **Optional**: `qrcode` library for QR code output: `pip install qrcode[pil]`

## Installation

1. Clone this repository or download the files:
   ```bash
   git clone https://github.com/ochen1/Mac-Hardware-Info.git
   cd Mac-Hardware-Info
   ```

2. Install the required Python dependencies:
   ```bash
   pip install protobuf
   ```

3. (Optional) Install qrcode for QR code generation:
   ```bash
   pip install qrcode[pil]
   ```

## Usage

Run the script on your Mac:

```bash
python3 mac_hw_info.py
```

### Output Options

1. **With `qrcode` library installed**: The script will display a QR code in the terminal (if supported) and save a PNG image file.

2. **Without `qrcode` library**: The script saves the data to a `.bin` file. You can then use `qrencode` to generate the QR code manually:
   ```bash
   qrencode -r mac_hw_info.bin -o qr.png
   ```

## Files

- `mac_hw_info.py` - Main Python script
- `mac_hw_info.proto` - Protocol Buffer definition file
- `mac_hw_info_pb2.py` - Generated Protocol Buffer Python module

## How It Works

The script collects the following hardware information from your Mac:

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
