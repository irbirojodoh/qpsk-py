"""
Packet structure and protocol definitions
"""

import numpy as np
from .hamming import HammingEncoder, HammingDecoder

class PacketProtocol:
    """Packet protocol constants and utilities"""
    
    # Packet structure constants
    PREAMBLE = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0], dtype=np.uint8)
    START_MARKER = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)
    END_MARKER = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.uint8)
    
    # Packet limits
    MAX_PAYLOAD_LENGTH = 255
    MIN_PAYLOAD_LENGTH = 1
    HEADER_LENGTH = 4  # bytes
    
    @staticmethod
    def get_packet_info():
        """Get packet structure information"""
        return {
            'preamble_bits': len(PacketProtocol.PREAMBLE),
            'start_marker_bits': len(PacketProtocol.START_MARKER),
            'header_bits': PacketProtocol.HEADER_LENGTH * 14,  # 14 bits per byte with Hamming
            'end_marker_bits': len(PacketProtocol.END_MARKER),
            'min_payload_bits': PacketProtocol.MIN_PAYLOAD_LENGTH * 14,
            'max_payload_bits': PacketProtocol.MAX_PAYLOAD_LENGTH * 14
        }

class PacketBuilder:
    """Build packets with preamble, header, payload, and end marker"""
    
    def __init__(self):
        self.hamming = HammingEncoder()
    
    def create_header(self, payload_length, sequence_number=0):
        """Create packet header with length and sequence number"""
        # Header: 4 bytes total
        # Byte 0-1: Payload length (16-bit)
        # Byte 2: Sequence number
        # Byte 3: Reserved/checksum
        
        if payload_length < PacketProtocol.MIN_PAYLOAD_LENGTH or payload_length > PacketProtocol.MAX_PAYLOAD_LENGTH:
            raise ValueError(f"Payload length must be between {PacketProtocol.MIN_PAYLOAD_LENGTH} and {PacketProtocol.MAX_PAYLOAD_LENGTH}")
        
        header_bytes = bytearray(PacketProtocol.HEADER_LENGTH)
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
        encoded_header = self.hamming.encode_bytes(header_bytes)
        encoded_payload = self.hamming.encode_bytes(payload_bytes)
        
        # Build complete packet
        packet_bits = np.concatenate([
            PacketProtocol.PREAMBLE,
            PacketProtocol.START_MARKER,
            encoded_header,
            encoded_payload,
            PacketProtocol.END_MARKER
        ])
        
        return packet_bits, {
            'payload_length': len(payload_bytes),
            'sequence_number': sequence_number,
            'preamble_bits': len(PacketProtocol.PREAMBLE),
            'start_marker_bits': len(PacketProtocol.START_MARKER),
            'header_bits': len(encoded_header),
            'payload_bits': len(encoded_payload),
            'end_marker_bits': len(PacketProtocol.END_MARKER),
            'total_bits': len(packet_bits)
        }
