# QPSK Digital Communication System

A comprehensive implementation of Quadrature Phase Shift Keying (QPSK) digital communication system using GNU Radio and Python with modular architecture.

## Features

- **Modular Design**: Separate transmitter and receiver modules with shared common components
- **Packet-based QPSK Communication**: Transmits data packets with error correction
- **Hamming(7,4) Error Correction**: Built-in error correction for reliable communication
- **USRP Support**: Compatible with USRP (Universal Software Radio Peripheral) devices
- **Real-time Processing**: Live packet transmission and reception
- **Terminal Display**: Clean terminal-based packet display
- **Automatic Signal Detection**: Receiver automatically detects when transmitter starts

## Project Structure

```
qpsk-py/
├── src/
│   ├── common/               # Shared components
│   │   ├── __init__.py      # Common utilities and constants
│   │   ├── hamming.py       # Hamming error correction
│   │   ├── packet.py        # Packet protocol definitions
│   │   └── usrp_config.py   # USRP configuration utilities
│   ├── transmitter/         # Transmitter module
│   │   ├── __init__.py
│   │   ├── modulator.py     # QPSK modulation
│   │   └── transmitter.py   # USRP transmission
│   └── receiver/            # Receiver module
│       ├── __init__.py
│       ├── decoder.py       # Packet decoding
│       ├── receiver.py      # QPSK demodulation
│       └── display.py       # Terminal display
├── transmit.py              # Transmitter application
├── receive.py               # Receiver application
├── setup.py                 # Package setup
├── requirements.txt         # Dependencies
├── README.md               # This file
└── .gitignore              # Git ignore rules
```

## Legacy Files

The following files are kept for reference but the modular versions should be used:
- `packet_qpsk_tx.py` - Legacy transmitter (use `transmit.py` instead)
- `packet_qpsk_rx.py` - Legacy receiver (use `receive.py` instead)
- `simplified_qpsk_tx.py` - Basic transmitter example
- `simplified_qpsk_rx.py` - Basic receiver example
- `from-grc.py` - GNU Radio Companion generated code

## Requirements

- Python 3.6+
- GNU Radio 3.8+
- NumPy
- USRP Hardware (or compatible SDR)

## Installation

### Option 1: Direct Installation

1. Install GNU Radio:
   ```bash
   sudo apt-get install gnuradio gnuradio-dev
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the package (optional):
   ```bash
   pip install -e .
   ```

### Option 2: Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/irbirojodoh/qpsk-py.git
   cd qpsk-py
   ```

2. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

## Usage

### Receiver

**Basic terminal mode:**
```bash
python3 receive.py
```

**With live plots (constellation, time/frequency domain):**
```bash
python3 receive.py --plot
```

**Debug mode with plots:**
```bash
python3 receive.py --debug --plot
```

**Terminal only (no plots):**
```bash
python3 receive.py --terminal-only
```

**Custom plot update rate:**
```bash
python3 receive.py --plot --update-rate 0.1
```

The receiver will:
- Automatically detect incoming signals
- Decode packets with error correction
- Display received messages in terminal
- Show packet statistics and error corrections
- (With --plot) Display live constellation diagram, time domain, and frequency domain plots

### Transmitter

```bash
python3 transmit.py
```

The transmitter will:
- Encode messages using Hamming(7,4) error correction
- Transmit packets with preamble, header, payload, and end marker
- Display transmission statistics

### Live Plotting Features

When using `--plot`, the receiver displays:

1. **Constellation Diagram** - Shows received QPSK symbols with:
   - Ideal constellation points (red circles)
   - Reference circles for signal quality assessment
   - Real-time received symbols (cyan dots)

2. **Time Domain Plot** - Shows I and Q components over time:
   - In-phase (I) component in cyan
   - Quadrature (Q) component in magenta
   - Auto-scaling for optimal view

3. **Frequency Domain Plot** - Shows power spectrum:
   - FFT of received signal with windowing
   - Power in dB vs frequency
   - Helps identify interference and signal bandwidth

4. **Signal Statistics** - Real-time metrics:
   - Signal power level in dB
   - Symbol rate vs expected rate
   - EVM (Error Vector Magnitude) percentage  
   - SNR estimation
   - Symbol distribution
   - Data counters

5. **Recent Packets** - Shows last received packets with:
   - Sequence numbers
   - Error correction statistics
   - Message content preview

### Configuration

Edit the configuration parameters in the main application files:

**Transmitter (`transmit.py`):**
- `message`: Text message to transmit
- `samp_rate`: Sample rate (default: 1 MHz)
- `center_freq`: Center frequency (default: 5 GHz)
- `gain`: Transmit gain (default: 20 dB)
- `usrp_addr`: USRP TX address (default: "addr=192.168.10.81")

**Receiver (`receive.py`):**
- `DEBUG_MODE`: Enable detailed debugging (default: False)
- `samp_rate`: Sample rate (default: 1 MHz) 
- `center_freq`: Center frequency (default: 5 GHz)
- `gain`: Receive gain (default: 20 dB)
- `usrp_addr`: USRP RX address (default: "addr=192.168.10.16")

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

1. Connect USRP devices to network:
   - TX USRP: 192.168.10.81 (default)
   - RX USRP: 192.168.10.16 (default)
2. Use J2 antenna connector
3. Configure appropriate gain settings for your environment

## Development

### Adding New Features

1. **Common Components**: Add shared utilities to `src/common/`
2. **Transmitter Features**: Extend `src/transmitter/` modules
3. **Receiver Features**: Extend `src/receiver/` modules
4. **Applications**: Modify `transmit.py` or `receive.py`

### Testing

Run tests (when available):
```bash
pytest tests/
```

### Code Formatting

Format code with Black:
```bash
black src/ *.py
```

## Troubleshooting

- Ensure USRP devices are properly connected and configured
- Check network connectivity to USRP devices
- Verify antenna connections
- Adjust gain settings if signal is too weak/strong
- Use debug mode (`DEBUG_MODE = True`) for detailed diagnostic information
- Check that GNU Radio and dependencies are properly installed

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues and pull requests to improve the system. Please follow the existing code structure and add appropriate tests for new features.
