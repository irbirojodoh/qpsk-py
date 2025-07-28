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

#### Basic Usage

```bash
python3 transmit.py
```

The transmitter will:
- Encode messages using Hamming(7,4) error correction
- Transmit packets with preamble, header, payload, and end marker
- Display transmission statistics

> **⚠️ Known Limitations**: 
> - Single-shot transmissions may be unreliable (see [Known Issues](#known-issues))
> - Continuous transmission provides better consistency
> - Consider using retry logic for critical single messages

#### Transmitting Your Own Data

The system supports multiple ways to transmit custom data:

##### Method 1: Edit the Message in Code

Modify the `message` variable in `transmit.py`:

```python
# In transmit.py, around line 43
message = "Your custom message here"  # Change this line
```

##### Method 2: Create a Custom Transmitter Script

Create your own Python script that uses the transmitter modules:

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.transmitter.modulator import create_packet_signal
from src.transmitter.transmitter import tx_worker
from src.common import *

# Your custom data
custom_message = "Hello from my custom transmitter!"

# Generate and transmit packet
modulated_signal, packet_info = create_packet_signal(
    custom_message, sequence_number=0, 
    sps=DEFAULT_SPS, alpha=DEFAULT_ALPHA, samp_rate=DEFAULT_SAMP_RATE
)

# Transmit (add proper threading and configuration as in transmit.py)
```

##### Method 3: Transmit Binary Data

The system can handle both text strings and binary data:

```python
# Text data (automatically converted to UTF-8 bytes)
text_data = "Hello World!"

# Binary data (provide as bytes directly)
binary_data = b'\x01\x02\x03\x04\x05'

# File data
with open('data.txt', 'rb') as f:
    file_data = f.read()

# Use any of these with create_packet_signal()
modulated_signal, packet_info = create_packet_signal(
    message=binary_data,  # or text_data, or file_data
    sequence_number=0
)
```

##### Method 4: Interactive Input

Create an interactive transmitter:

```python
#!/usr/bin/env python3
# Interactive transmitter example

while True:
    user_input = input("Enter message to transmit (or 'quit'): ")
    if user_input.lower() == 'quit':
        break
    
    # Generate and transmit packet
    modulated_signal, packet_info = create_packet_signal(user_input)
    # Add transmission code here
```

##### Method 5: File-based Transmission

Transmit data from files:

```python
#!/usr/bin/env python3
import os

def transmit_file(filename):
    """Transmit a file's contents"""
    try:
        with open(filename, 'rb') as f:
            file_data = f.read()
        
        # Split large files into chunks if needed
        max_chunk_size = 200  # Leave room for headers
        
        if len(file_data) <= max_chunk_size:
            # Single packet transmission
            modulated_signal, packet_info = create_packet_signal(file_data)
            # Transmit signal
        else:
            # Multi-packet transmission
            for i, chunk_start in enumerate(range(0, len(file_data), max_chunk_size)):
                chunk = file_data[chunk_start:chunk_start + max_chunk_size]
                modulated_signal, packet_info = create_packet_signal(
                    chunk, sequence_number=i
                )
                # Transmit each chunk
                
    except FileNotFoundError:
        print(f"File {filename} not found")

# Usage
transmit_file("my_data.txt")
```

#### Data Limitations

- **Maximum payload size**: 255 bytes per packet
- **Supported data types**: 
  - Text strings (automatically encoded as UTF-8)
  - Binary data (bytes objects)
  - File contents
- **Character encoding**: UTF-8 for text data
- **Large data**: Split into multiple packets with sequence numbers

#### Custom Configuration

You can also customize transmission parameters:

```python
# Custom transmission parameters
custom_config = {
    'samp_rate': 2e6,           # 2 MHz sample rate
    'center_freq': 2.4e9,       # 2.4 GHz center frequency  
    'gain': 30,                 # 30 dB gain
    'sps': 8,                   # 8 samples per symbol
    'alpha': 0.35,              # 0.35 rolloff factor
}

# Generate signal with custom parameters
modulated_signal, packet_info = create_packet_signal(
    message="Custom config test",
    sps=custom_config['sps'],
    alpha=custom_config['alpha'],
    samp_rate=custom_config['samp_rate']
)
```

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

## Advanced Data Transmission

### Streaming Data Transmission

For continuous data transmission, you can implement a streaming pattern:

```python
#!/usr/bin/env python3
"""
Example: Streaming data transmitter
"""
import time
import threading
from queue import Queue

class StreamingTransmitter:
    def __init__(self):
        self.data_queue = Queue()
        self.sequence_number = 0
        self.stop_event = threading.Event()
    
    def add_data(self, data):
        """Add data to transmission queue"""
        self.data_queue.put(data)
    
    def transmission_worker(self):
        """Worker thread for continuous transmission"""
        while not self.stop_event.is_set():
            try:
                data = self.data_queue.get(timeout=1.0)
                
                # Generate and transmit packet
                modulated_signal, packet_info = create_packet_signal(
                    data, self.sequence_number
                )
                
                # Actual transmission code here
                self.sequence_number += 1
                
            except:
                continue  # Queue timeout, continue checking
    
    def start(self):
        """Start streaming transmission"""
        self.worker_thread = threading.Thread(target=self.transmission_worker)
        self.worker_thread.start()
    
    def stop(self):
        """Stop streaming transmission"""
        self.stop_event.set()
        self.worker_thread.join()

# Usage
transmitter = StreamingTransmitter()
transmitter.start()

# Add data dynamically
transmitter.add_data("Message 1")
transmitter.add_data("Message 2")
transmitter.add_data(b'\x01\x02\x03')  # Binary data

time.sleep(5)
transmitter.stop()
```

### Data Serialization Examples

#### JSON Data Transmission

```python
import json

# Transmit structured data as JSON
data = {
    "sensor_id": "temp_01",
    "temperature": 23.5,
    "humidity": 65.2,
    "timestamp": "2025-01-01T12:00:00Z"
}

json_message = json.dumps(data)
modulated_signal, packet_info = create_packet_signal(json_message)
```

#### CSV Data Transmission

```python
import csv
import io

# Transmit CSV data
csv_data = [
    ["Name", "Age", "City"],
    ["Alice", "25", "New York"],
    ["Bob", "30", "San Francisco"]
]

output = io.StringIO()
writer = csv.writer(output)
writer.writerows(csv_data)
csv_message = output.getvalue()

modulated_signal, packet_info = create_packet_signal(csv_message)
```

#### Compressed Data Transmission

```python
import gzip
import base64

# Compress data before transmission
original_data = "This is a long message that will be compressed before transmission" * 10

# Compress
compressed_data = gzip.compress(original_data.encode('utf-8'))

# Encode as base64 for text transmission
encoded_data = base64.b64encode(compressed_data).decode('ascii')

modulated_signal, packet_info = create_packet_signal(encoded_data)
```

### Multi-packet File Transmission

```python
#!/usr/bin/env python3
"""
Example: Large file transmission with progress tracking
"""
import os
import hashlib

def transmit_large_file(filename, chunk_size=200):
    """
    Transmit a large file in chunks with metadata
    """
    if not os.path.exists(filename):
        print(f"File {filename} not found")
        return
    
    # Get file info
    file_size = os.path.getsize(filename)
    file_hash = hashlib.md5(open(filename, 'rb').read()).hexdigest()
    
    # Send file metadata first
    metadata = {
        "filename": os.path.basename(filename),
        "size": file_size,
        "chunks": (file_size + chunk_size - 1) // chunk_size,
        "hash": file_hash
    }
    
    metadata_json = json.dumps(metadata)
    print(f"Sending file metadata: {metadata_json}")
    
    # Send metadata packet
    modulated_signal, packet_info = create_packet_signal(
        f"META:{metadata_json}", sequence_number=0
    )
    # Transmit metadata
    
    # Send file chunks
    with open(filename, 'rb') as f:
        chunk_number = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            chunk_header = f"CHUNK:{chunk_number}:"
            chunk_data = chunk_header.encode('ascii') + chunk
            
            print(f"Sending chunk {chunk_number}/{metadata['chunks']} "
                  f"({len(chunk)} bytes)")
            
            modulated_signal, packet_info = create_packet_signal(
                chunk_data, sequence_number=chunk_number
            )
            # Transmit chunk
            
            chunk_number += 1
    
    # Send end marker
    modulated_signal, packet_info = create_packet_signal(
        "END_OF_FILE", sequence_number=chunk_number
    )
    print("File transmission complete")

# Usage
transmit_large_file("large_document.pdf")
```

### Real-time Sensor Data

```python
#!/usr/bin/env python3
"""
Example: Real-time sensor data transmission
"""
import random
import time
import json
from datetime import datetime

def simulate_sensor_data():
    """Simulate sensor readings"""
    return {
        "timestamp": datetime.now().isoformat(),
        "temperature": round(random.uniform(20, 30), 2),
        "humidity": round(random.uniform(40, 80), 2),
        "pressure": round(random.uniform(1000, 1020), 2),
        "sensor_id": "ENV_001"
    }

def transmit_sensor_data(duration_seconds=60, interval_seconds=5):
    """Transmit sensor data at regular intervals"""
    start_time = time.time()
    sequence = 0
    
    while time.time() - start_time < duration_seconds:
        # Get sensor data
        sensor_data = simulate_sensor_data()
        json_data = json.dumps(sensor_data)
        
        print(f"Transmitting sensor data: {json_data}")
        
        # Create and transmit packet
        modulated_signal, packet_info = create_packet_signal(
            json_data, sequence_number=sequence
        )
        # Actual transmission code here
        
        sequence += 1
        time.sleep(interval_seconds)

# Usage
transmit_sensor_data(duration_seconds=300, interval_seconds=10)  # 5 minutes, every 10 seconds
```

## Configuration

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

### Known Issues

#### Data Transfer Consistency

**Issue 1: Continuous transmission required for reliability**
- **Problem**: Data transfer is only consistent when done continuously
- **Symptoms**: 
  - Intermittent packet loss during sporadic transmissions
  - Better success rate with streaming data vs single packets
- **Current Status**: Under investigation
- **Workaround**: Use continuous transmission patterns for critical data

**Issue 2: One-shot message transmission inconsistency**
- **Problem**: Single message transmission is unreliable
- **Symptoms**:
  - Random failures when sending isolated packets
  - Receiver may not detect single transmissions
  - First packet in a sequence often lost
- **Current Status**: Known limitation
- **Workarounds**: 
  - Send duplicate packets for important single messages
  - Use a "warm-up" transmission before actual data
  - Implement retry logic for critical single messages

#### Workaround Examples

**For Single Message Reliability:**
```python
def reliable_single_transmission(message, retries=3):
    """Send single message with retries for better reliability"""
    for attempt in range(retries):
        print(f"Transmission attempt {attempt + 1}/{retries}")
        
        # Send a warm-up packet first
        if attempt == 0:
            warm_up_signal, _ = create_packet_signal("WARMUP", sequence_number=0)
            # Transmit warm-up
        
        # Send actual message
        modulated_signal, packet_info = create_packet_signal(
            message, sequence_number=attempt + 1
        )
        # Transmit actual message
        
        # Add delay between retries
        time.sleep(0.5)

# Usage
reliable_single_transmission("Important single message")
```

**For Continuous Data Reliability:**
```python
def continuous_transmission_recommended(messages):
    """Recommended pattern for reliable data transmission"""
    print("Starting continuous transmission (recommended for reliability)")
    
    for i, message in enumerate(messages):
        modulated_signal, packet_info = create_packet_signal(
            message, sequence_number=i
        )
        # Transmit
        
        # Small delay to maintain continuous stream
        time.sleep(0.1)  # 100ms between packets
    
    print("Continuous transmission complete")

# Usage - this is more reliable than single shots
message_list = ["Message 1", "Message 2", "Message 3"]
continuous_transmission_recommended(message_list)
```

### General Issues

- Ensure USRP devices are properly connected and configured
- Check network connectivity to USRP devices
- Verify antenna connections
- Adjust gain settings if signal is too weak/strong
- Use debug mode (`DEBUG_MODE = True`) for detailed diagnostic information
- Check that GNU Radio and dependencies are properly installed

### Custom Data Transmission Issues

#### Data Size Limitations

**Problem**: "Payload length must be between 1 and 255" error
```
ValueError: Payload length must be between 1 and 255
```

**Solution**: Split large data into smaller chunks
```python
def split_data(data, max_size=200):
    """Split data into transmittable chunks"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    chunks = []
    for i in range(0, len(data), max_size):
        chunks.append(data[i:i + max_size])
    return chunks

# Usage
large_data = "Very long message..." * 100
chunks = split_data(large_data)
for i, chunk in enumerate(chunks):
    modulated_signal, packet_info = create_packet_signal(chunk, sequence_number=i)
```

#### Unicode and Encoding Issues

**Problem**: Unicode characters causing encoding errors
```
UnicodeEncodeError: 'ascii' codec can't encode character
```

**Solution**: Handle encoding explicitly
```python
# For text with special characters
message = "Héllo Wørld! 你好"
safe_message = message.encode('utf-8')  # Convert to bytes first

# Or use error handling
try:
    modulated_signal, packet_info = create_packet_signal(message)
except UnicodeError:
    # Fall back to ASCII-safe version
    safe_message = message.encode('ascii', errors='replace')
    modulated_signal, packet_info = create_packet_signal(safe_message)
```

#### Binary Data Issues

**Problem**: Binary data being corrupted during transmission

**Solution**: Use proper binary handling
```python
# Read binary files correctly
with open('image.jpg', 'rb') as f:  # Note the 'rb' mode
    binary_data = f.read()

# Transmit binary data directly
modulated_signal, packet_info = create_packet_signal(binary_data)

# For debugging, check data integrity
print(f"Original data length: {len(binary_data)}")
print(f"First 10 bytes: {binary_data[:10]}")
```

#### Memory Issues with Large Data

**Problem**: Out of memory when processing large files

**Solution**: Use streaming approach
```python
def stream_file_transmission(filename, chunk_size=100):
    """Memory-efficient file transmission"""
    with open(filename, 'rb') as f:
        sequence = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            # Transmit chunk immediately, don't store all chunks
            modulated_signal, packet_info = create_packet_signal(
                chunk, sequence_number=sequence
            )
            # Transmit here
            sequence += 1
            
            # Optional: Add delay between chunks
            time.sleep(0.1)
```

#### Debugging Data Content

**Problem**: Need to verify what data is actually being transmitted

**Solution**: Add debug output
```python
def debug_packet_content(message):
    """Debug helper to see packet contents"""
    from src.common.packet import PacketBuilder
    
    builder = PacketBuilder()
    packet_bits, packet_info = builder.build_packet(message)
    
    print(f"Original message: {repr(message)}")
    print(f"Message type: {type(message)}")
    print(f"Message length: {len(message)} characters/bytes")
    print(f"Packet info: {packet_info}")
    print(f"Total packet bits: {len(packet_bits)}")
    
    return packet_bits, packet_info

# Usage
debug_packet_content("Test message")
debug_packet_content(b'\x01\x02\x03')
```

### Performance Optimization

#### Transmission Rate Optimization

```python
# Optimize for faster transmission
fast_config = {
    'sps': 4,           # Fewer samples per symbol
    'alpha': 0.25,      # Lower rolloff factor
    'samp_rate': 2e6,   # Higher sample rate
}

# Optimize for reliability
reliable_config = {
    'sps': 16,          # More samples per symbol
    'alpha': 0.5,       # Higher rolloff factor
    'gain': 25,         # Higher gain
}
```

#### Batch Transmission

```python
def batch_transmit(messages, delay_between=0.1):
    """Transmit multiple messages efficiently"""
    for i, message in enumerate(messages):
        modulated_signal, packet_info = create_packet_signal(
            message, sequence_number=i
        )
        # Transmit
        time.sleep(delay_between)  # Prevent overwhelming receiver
```

## Quick Reference for Custom Data Transmission

### Common Scenarios

| Data Type | Example Code | Notes |
|-----------|--------------|--------|
| Simple text | `create_packet_signal("Hello World!")` | Automatically encoded as UTF-8 |
| Binary data | `create_packet_signal(b'\x01\x02\x03')` | Raw bytes |
| File content | `create_packet_signal(open('file.txt', 'rb').read())` | Remember 'rb' mode |
| JSON data | `create_packet_signal(json.dumps(data))` | Convert dict to JSON string |
| Numbers | `create_packet_signal(str(42))` | Convert to string first |
| Lists | `create_packet_signal(','.join(my_list))` | Convert to CSV-like format |

### File Types and Handling

| File Type | Reading Method | Example |
|-----------|----------------|---------|
| Text files | `open('file.txt', 'r').read()` | For UTF-8 text |
| Binary files | `open('file.bin', 'rb').read()` | Images, executables, etc. |
| CSV files | `csv.reader()` + string conversion | Tabular data |
| JSON files | `json.load()` + `json.dumps()` | Structured data |
| Large files | Chunk reading with `f.read(chunk_size)` | Memory efficient |

### Data Size Guidelines

- **Single packet**: Up to 200 bytes (leaves room for headers)
- **Multiple packets**: Split data and use sequence numbers
- **Text messages**: Most short messages fit in one packet
- **Binary files**: Usually require multiple packets
- **Streaming data**: Use queue-based approach

> **⚠️ Reliability Note**: Single-shot transmissions may fail. Use continuous transmission patterns for better reliability.

### Transmission Reliability

| Transmission Pattern | Reliability | Recommended Use |
|---------------------|-------------|-----------------|
| Single message | ⚠️ Inconsistent | Avoid for critical data |
| Continuous stream | ✅ Reliable | Recommended approach |
| Batch transmission | ✅ Good | Multiple related messages |
| With retries | ✅ Good | Important single messages |

### Sequence Numbers

```python
# Single message
create_packet_signal("Message", sequence_number=0)

# Multiple related messages
for i, message in enumerate(messages):
    create_packet_signal(message, sequence_number=i)

# Continuous transmission
sequence = 0
while transmitting:
    create_packet_signal(get_next_data(), sequence_number=sequence)
    sequence += 1
```

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues and pull requests to improve the system. Please follow the existing code structure and add appropriate tests for new features.
