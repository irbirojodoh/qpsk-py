# QPSK Digital Communication System

A comprehensive implementation of Quadrature Phase Shift Keying (QPSK) digital communication system using GNU Radio and Python.

## Features

- **Packet-based QPSK Transmitter**: Transmits data packets with error correction
- **Packet-based QPSK Receiver**: Receives and decodes packets with error correction
- **Hamming(7,4) Error Correction**: Built-in error correction for reliable communication
- **USRP Support**: Compatible with USRP (Universal Software Radio Peripheral) devices
- **Real-time Processing**: Live packet transmission and reception
- **Terminal Display**: Clean terminal-based packet display
- **Automatic Signal Detection**: Receiver automatically detects when transmitter starts

## Files

- `packet_qpsk_tx.py` - Packet-based QPSK transmitter with Hamming encoding
- `packet_qpsk_rx.py` - Packet-based QPSK receiver with Hamming decoding
- `simplified_qpsk_tx.py` - Simplified QPSK transmitter (basic version)
- `simplified_qpsk_rx.py` - Simplified QPSK receiver (basic version)
- `from-grc.py` - GNU Radio Companion generated code

## Requirements

- Python 3.6+
- GNU Radio 3.8+
- NumPy
- USRP Hardware (or compatible SDR)

## Installation

1. Install GNU Radio:
   ```bash
   sudo apt-get install gnuradio gnuradio-dev
   ```

2. Install Python dependencies:
   ```bash
   pip install numpy
   ```

3. Connect your USRP device and configure network settings

## Usage

### Transmitter

```bash
python3 packet_qpsk_tx.py
```

The transmitter will:
- Encode messages using Hamming(7,4) error correction
- Transmit packets with preamble, header, payload, and end marker
- Display transmission statistics

### Receiver

```bash
python3 packet_qpsk_rx.py
```

The receiver will:
- Automatically detect incoming signals
- Decode packets with error correction
- Display received messages in terminal
- Show packet statistics and error corrections

### Debug Mode

For detailed debugging information, edit the files and set `DEBUG_MODE = True` in the main function.

## System Parameters

- **Sampling Rate**: 1 MHz
- **Center Frequency**: 5 GHz
- **Samples per Symbol**: 16
- **Rolloff Factor**: 0.50
- **Modulation**: QPSK with differential encoding
- **Error Correction**: Hamming(7,4) code

## Packet Structure

Each packet contains:
1. **Preamble**: 16-bit synchronization pattern
2. **Start Marker**: 8-bit packet start indicator
3. **Header**: 4 bytes (payload length, sequence number, etc.)
4. **Payload**: Variable length data (1-255 bytes)
5. **End Marker**: 8-bit packet end indicator

## Error Correction

The system uses Hamming(7,4) error correction:
- Each 4-bit data nibble is encoded into 7 bits
- Single-bit errors are automatically corrected
- Error statistics are displayed during operation

## Hardware Setup

1. Connect USRP devices to network (default IP: 192.168.10.16)
2. Use J2 antenna connector
3. Configure appropriate gain settings for your environment

## Troubleshooting

- Ensure USRP devices are properly connected and configured
- Check network connectivity to USRP
- Verify antenna connections
- Adjust gain settings if signal is too weak/strong
- Use debug mode for detailed diagnostic information

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues and pull requests to improve the system.
