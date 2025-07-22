"""
QPSK Modulator for packet transmission
"""

import numpy as np
import time
from gnuradio import gr, blocks, digital
from ..common import create_constellation

class QpskPacketModulator(gr.top_block):
    """GNU Radio flowgraph for QPSK modulation with packet data"""
    
    def __init__(self, packet_bits, samp_rate=1e6, sps=16, alpha=0.5):
        gr.top_block.__init__(self)
        
        # Variables
        self.samp_rate = samp_rate
        self.sps = sps
        self.alpha = alpha
        
        # Create QPSK constellation
        self.constellation = create_constellation()
        
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

def create_packet_signal(message="HELLO FROM TX", sequence_number=0, 
                        sps=16, alpha=0.5, samp_rate=1e6, verbose=True):
    """
    Generate QPSK modulated signal from packet data
    
    Args:
        message: String message to transmit
        sequence_number: Packet sequence number
        sps: Samples per symbol
        alpha: Excess bandwidth (roll-off factor)
        samp_rate: Sample rate
        verbose: Print debug information
    
    Returns:
        Complex IQ samples and packet info
    """
    from ..common.packet import PacketBuilder
    
    if verbose:
        print(f"Creating packet for message: '{message}'")
    
    # Build packet with error correction
    packet_builder = PacketBuilder()
    packet_bits, packet_info = packet_builder.build_packet(message, sequence_number)
    
    if verbose:
        print(f"Packet created with {len(packet_bits)} bits")
        print(f"Packet structure:")
        for key, value in packet_info.items():
            print(f"  - {key}: {value}")
    
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
    
    if verbose:
        print(f"Generated {len(samples)} complex samples")
        print(f"Sample rate: {samp_rate/1e6:.1f} MHz")
        print(f"Samples per symbol: {sps}")
        print(f"Signal power: {np.mean(np.abs(samples)**2):.6f}")
        print(f"Signal peak: {np.max(np.abs(samples)):.6f}")
    
    return samples, packet_info
