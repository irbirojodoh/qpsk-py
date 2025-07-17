#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Packet-based QPSK Transmitter with Hamming Code Error Correction
Based on simplified_qpsk_tx.py with added packet structure and error correction
"""

import numpy as np
from gnuradio import gr, blocks, digital, uhd
from gnuradio.filter import firdes
import threading
import time
import signal
import sys
import struct

# Global variables
stop_signal = False

class HammingCode:
    """Hamming(7,4) error correction code implementation"""
    
    def __init__(self):
        # Generator matrix for Hamming(7,4)
        self.G = np.array([
            [1, 0, 0, 0, 1, 1, 0],
            [0, 1, 0, 0, 1, 0, 1],
            [0, 0, 1, 0, 0, 1, 1],
            [0, 0, 0, 1, 1, 1, 1]
        ], dtype=np.uint8)
        
        # Parity check matrix for Hamming(7,4)
        self.H = np.array([
            [1, 1, 0, 1, 1, 0, 0],
            [1, 0, 1, 1, 0, 1, 0],
            [0, 1, 1, 1, 0, 0, 1]
        ], dtype=np.uint8)
    
    def encode_4bits(self, data_bits):
        """Encode 4 data bits into 7-bit Hamming codeword"""
        if len(data_bits) != 4:
            raise ValueError("Input must be exactly 4 bits")
        
        # Convert to numpy array if needed
        data_bits = np.array(data_bits, dtype=np.uint8)
        
        # Matrix multiplication in GF(2)
        codeword = np.dot(data_bits, self.G) % 2
        return codeword.astype(np.uint8)
    
    def encode_bytes(self, data):
        """Encode a sequence of bytes using Hamming code"""
        encoded_bits = []
        
        for byte in data:
            # Split byte into two 4-bit nibbles
            high_nibble = [(byte >> (7-i)) & 1 for i in range(4)]  # bits 7,6,5,4
            low_nibble = [(byte >> (3-i)) & 1 for i in range(4)]   # bits 3,2,1,0
            
            # Encode each nibble
            encoded_high = self.encode_4bits(high_nibble)
            encoded_low = self.encode_4bits(low_nibble)
            
            # Add to result
            encoded_bits.extend(encoded_high)
            encoded_bits.extend(encoded_low)
        
        return np.array(encoded_bits, dtype=np.uint8)
    
    def decode_7bits(self, received_bits):
        """Decode 7-bit Hamming codeword and correct single-bit errors"""
        if len(received_bits) != 7:
            raise ValueError("Input must be exactly 7 bits")
        
        received_bits = np.array(received_bits, dtype=np.uint8)
        
        # Calculate syndrome
        syndrome = np.dot(self.H, received_bits) % 2
        
        # Check for errors
        error_position = 0
        if np.any(syndrome):
            # Convert syndrome to error position
            error_position = syndrome[0] * 4 + syndrome[1] * 2 + syndrome[2] * 1
            
            # Correct the error
            if 1 <= error_position <= 7:
                received_bits[error_position - 1] ^= 1
        
        # Extract data bits (positions 0, 1, 2, 3)
        data_bits = received_bits[[0, 1, 2, 3]]
        return data_bits, error_position > 0
    
    def decode_bytes(self, encoded_bits):
        """Decode a sequence of Hamming-encoded bits back to bytes"""
        decoded_bytes = []
        
        # Process 14 bits at a time (two 7-bit codewords = one byte)
        for i in range(0, len(encoded_bits), 14):
            if i + 14 <= len(encoded_bits):
                # Decode high nibble (first 7 bits)
                high_codeword = encoded_bits[i:i+7]
                high_nibble, _ = self.decode_7bits(high_codeword)
                
                # Decode low nibble (next 7 bits)
                low_codeword = encoded_bits[i+7:i+14]
                low_nibble, _ = self.decode_7bits(low_codeword)
                
                # Combine nibbles into byte (high nibble in upper 4 bits, low nibble in lower 4 bits)
                byte_val = 0
                for j in range(4):
                    byte_val |= (int(high_nibble[j]) << (7-j))  # bits 7,6,5,4
                for j in range(4):
                    byte_val |= (int(low_nibble[j]) << (3-j))   # bits 3,2,1,0
                
                decoded_bytes.append(byte_val)
        
        return bytes(decoded_bytes)

class PacketBuilder:
    """Build packets with preamble, header, payload, and end marker"""
    
    def __init__(self):
        self.hamming = HammingCode()
        
        # Packet structure constants
        self.PREAMBLE = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0], dtype=np.uint8)
        self.START_MARKER = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)
        self.END_MARKER = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.uint8)
    
    def create_header(self, payload_length, sequence_number=0):
        """Create packet header with length and sequence number"""
        # Header: 4 bytes total
        # Byte 0-1: Payload length (16-bit)
        # Byte 2: Sequence number
        # Byte 3: Reserved/checksum
        
        header_bytes = bytearray(4)
        header_bytes[0] = (payload_length >> 8) & 0xFF  # High byte
        header_bytes[1] = payload_length & 0xFF         # Low byte
        header_bytes[2] = sequence_number & 0xFF
        header_bytes[3] = 0  # Reserved
        
        return bytes(header_bytes)
    
    def build_packet(self, message, sequence_number=0):
        """Build complete packet with error correction"""
        # Convert message to bytes
        if isinstance(message, str):
            payload_bytes = message.encode('utf-8')
        else:
            payload_bytes = bytes(message)
        
        # Create header
        header_bytes = self.create_header(len(payload_bytes), sequence_number)
        
        # Encode header and payload with Hamming code
        print(f"Encoding header: {len(header_bytes)} bytes")
        encoded_header = self.hamming.encode_bytes(header_bytes)
        
        print(f"Encoding payload: {len(payload_bytes)} bytes - '{payload_bytes.decode('utf-8', errors='ignore')}'")
        encoded_payload = self.hamming.encode_bytes(payload_bytes)
        
        # Build complete packet
        packet_bits = np.concatenate([
            self.PREAMBLE,
            self.START_MARKER,
            encoded_header,
            encoded_payload,
            self.END_MARKER
        ])
        
        print(f"Packet structure:")
        print(f"  - Preamble: {len(self.PREAMBLE)} bits")
        print(f"  - Start marker: {len(self.START_MARKER)} bits") 
        print(f"  - Encoded header: {len(encoded_header)} bits")
        print(f"  - Encoded payload: {len(encoded_payload)} bits")
        print(f"  - End marker: {len(self.END_MARKER)} bits")
        print(f"  - Total packet: {len(packet_bits)} bits")
        
        return packet_bits

class QpskPacketModulator(gr.top_block):
    """GNU Radio flowgraph for QPSK modulation with packet data"""
    
    def __init__(self, packet_bits, samp_rate=1e6, sps=16, alpha=0.5):
        gr.top_block.__init__(self)
        
        # Variables
        self.samp_rate = samp_rate
        self.sps = sps
        self.alpha = alpha
        
        # Create QPSK constellation
        self.constellation = digital.constellation_calcdist(
            [-1-1j, -1+1j, 1+1j, 1-1j], 
            [0, 1, 2, 3],
            4, 1, 
            digital.constellation.AMPLITUDE_NORMALIZATION
        ).base()
        
        # Convert bit stream to bytes for GNU Radio
        # Pad to byte boundary if necessary
        padded_bits = np.copy(packet_bits)
        if len(padded_bits) % 8 != 0:
            padding = 8 - (len(padded_bits) % 8)
            padded_bits = np.concatenate([padded_bits, np.zeros(padding, dtype=np.uint8)])
        
        # Convert bits to bytes
        packet_bytes = []
        for i in range(0, len(padded_bits), 8):
            byte_bits = padded_bits[i:i+8]
            byte_val = 0
            for j, bit in enumerate(byte_bits):
                byte_val |= (int(bit) << (7-j))
            packet_bytes.append(byte_val)
        
        print(f"Packet converted to {len(packet_bytes)} bytes for transmission")
        
        # Blocks
        self.packet_source = blocks.vector_source_b(packet_bytes, True)  # Repeat packet
        
        self.digital_constellation_modulator = digital.generic_mod(
            constellation=self.constellation,
            differential=True,
            samples_per_symbol=self.sps,
            pre_diff_code=True,
            excess_bw=self.alpha,
            verbose=False,
            log=False,
            truncate=False
        )
        
        self.blocks_multiply_const = blocks.multiply_const_cc(0.3)
        self.vector_sink = blocks.vector_sink_c()
        
        # Connections
        self.connect((self.packet_source, 0), (self.digital_constellation_modulator, 0))
        self.connect((self.digital_constellation_modulator, 0), (self.blocks_multiply_const, 0))
        self.connect((self.blocks_multiply_const, 0), (self.vector_sink, 0))

def create_packet_signal(message="TESTING FROM USRP 1", sequence_number=0, 
                        sps=16, alpha=0.5, samp_rate=1e6):
    """
    Generate QPSK modulated signal from packet data
    
    Args:
        message: String message to transmit
        sequence_number: Packet sequence number
        sps: Samples per symbol
        alpha: Excess bandwidth (roll-off factor)
        samp_rate: Sample rate
    
    Returns:
        Complex IQ samples
    """
    print(f"Creating packet for message: '{message}'")
    
    # Build packet with error correction
    packet_builder = PacketBuilder()
    packet_bits = packet_builder.build_packet(message, sequence_number)
    
    print(f"Packet created with {len(packet_bits)} bits")
    
    # Create the modulator flowgraph
    modulator = QpskPacketModulator(packet_bits, samp_rate, sps, alpha)
    
    # Run the flowgraph to generate samples
    modulator.start()
    
    # Let it run to generate samples
    time.sleep(1.0)  # Longer time to ensure packet generation
    
    # Stop and get the data
    modulator.stop()
    modulator.wait()
    
    # Get the generated samples
    samples = np.array(modulator.vector_sink.data())
    
    print(f"Generated {len(samples)} complex samples")
    print(f"Sample rate: {samp_rate/1e6:.1f} MHz")
    print(f"Samples per symbol: {sps}")
    print(f"Signal power: {np.mean(np.abs(samples)**2):.6f}")
    print(f"Signal peak: {np.max(np.abs(samples)):.6f}")
    
    return samples

def tx_worker(modulated_signal, usrp_args="addr=192.168.10.81", center_freq=5e9, 
              samp_rate=1e6, gain=20, antenna="J2"):
    """
    Transmit signal using USRP with GNU Radio
    
    Args:
        modulated_signal: Complex IQ samples to transmit
        usrp_args: USRP device arguments
        center_freq: Center frequency in Hz
        samp_rate: Sample rate in Hz
        gain: Transmit gain
        antenna: Antenna port
    """
    global stop_signal
    
    class USRPTransmitter(gr.top_block):
        def __init__(self, signal_data, usrp_args, center_freq, samp_rate, gain, antenna):
            gr.top_block.__init__(self)
            
            # Create vector source with the signal data (repeat continuously)
            self.vector_source = blocks.vector_source_c(signal_data, True)
            
            # Create USRP sink
            self.uhd_usrp_sink = uhd.usrp_sink(
                usrp_args,
                uhd.stream_args(
                    cpu_format="fc32",
                    args='',
                    channels=list(range(0,1)),
                ),
                "",
            )
            
            # Configure USRP
            self.uhd_usrp_sink.set_samp_rate(samp_rate)
            self.uhd_usrp_sink.set_center_freq(center_freq, 0)
            self.uhd_usrp_sink.set_antenna(antenna, 0)
            self.uhd_usrp_sink.set_bandwidth(20e6, 0)
            self.uhd_usrp_sink.set_gain(gain, 0)
            
            # Connect the blocks
            self.connect((self.vector_source, 0), (self.uhd_usrp_sink, 0))
    
    try:
        print(f"Setting up USRP transmission...")
        print(f"USRP Args: {usrp_args}")
        print(f"Center Frequency: {center_freq/1e9:.3f} GHz")
        print(f"Sample Rate: {samp_rate/1e6:.1f} MHz")
        print(f"Gain: {gain} dB")
        print(f"Antenna: {antenna}")
        print(f"Signal length: {len(modulated_signal)} samples")
        
        # Create and start the transmitter
        transmitter = USRPTransmitter(
            modulated_signal, usrp_args, center_freq, 
            samp_rate, gain, antenna
        )
        
        print("Starting transmission...")
        transmitter.start()
        
        # Keep transmitting until stop signal
        while not stop_signal:
            time.sleep(0.1)
        
        print("Stopping transmission...")
        transmitter.stop()
        transmitter.wait()
        
    except Exception as e:
        print(f"Error in tx_worker: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Transmission stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global stop_signal
    print("\nStopping transmission...")
    stop_signal = True

def main():
    """Main function"""
    global stop_signal
    
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Configuration parameters
    samp_rate = 1e6      # 1 MHz sample rate
    center_freq = 5e9    # 5 GHz center frequency
    gain = 20            # Transmit gain in dB
    sps = 16             # Samples per symbol
    alpha = 0.5          # Excess bandwidth
    message = "TESTING FROM USRP 1"  # Message to transmit
    
    print("=== Packet-based QPSK Transmitter with Hamming Code ===")
    print(f"Message: '{message}'")
    print(f"Sample Rate: {samp_rate/1e6:.1f} MHz")
    print(f"Center Frequency: {center_freq/1e9:.3f} GHz")
    print(f"Samples per Symbol: {sps}")
    print(f"Excess Bandwidth: {alpha}")
    
    # Generate packet signal with error correction
    sequence_number = 0
    modulated_signal = create_packet_signal(message, sequence_number, sps, alpha, samp_rate)
    
    if len(modulated_signal) == 0:
        print("Error: No signal generated!")
        return
    
    print(f"\nPacket signal generated successfully!")
    print(f"Signal length: {len(modulated_signal)} samples")
    print(f"Signal duration: {len(modulated_signal)/samp_rate:.3f} seconds")
    
    # Start transmission in a separate thread
    tx_thread = threading.Thread(
        target=tx_worker,
        args=(modulated_signal,),
        kwargs={
            'usrp_args': "addr=192.168.10.81",
            'center_freq': center_freq,
            'samp_rate': samp_rate,
            'gain': gain,
            'antenna': 'J2'
        }
    )
    
    tx_thread.daemon = True
    tx_thread.start()
    
    # Keep main thread alive
    try:
        print("\nTransmission started. Press Ctrl+C to stop.")
        while not stop_signal:
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_signal = True
    
    # Wait for transmission thread to finish
    tx_thread.join(timeout=5.0)
    print("Program finished")

if __name__ == '__main__':
    main()
