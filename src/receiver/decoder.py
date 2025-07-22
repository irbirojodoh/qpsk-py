"""
Packet decoder for QPSK receiver
"""

import numpy as np
from collections import deque
from ..common.hamming import HammingDecoder
from ..common.packet import PacketProtocol

class PacketDecoder:
    """Decode packets with preamble, header, payload, and end marker"""
    
    def __init__(self, debug=False):
        self.hamming = HammingDecoder()
        self.debug = debug
        
        # Packet structure constants from protocol
        self.PREAMBLE = PacketProtocol.PREAMBLE
        self.START_MARKER = PacketProtocol.START_MARKER
        self.END_MARKER = PacketProtocol.END_MARKER
        
        # For packet search
        self.bit_buffer = deque(maxlen=1000)  # Circular buffer for incoming bits
        self.packets_received = 0
    
    def find_pattern(self, data, pattern, max_errors=0):
        """Find pattern in data array with strict matching"""
        pattern_len = len(pattern)
        best_pos = -1
        min_errors = float('inf')
        
        for i in range(len(data) - pattern_len + 1):
            chunk = data[i:i+pattern_len]
            errors = np.sum(chunk != pattern)
            
            if errors <= max_errors and errors < min_errors:
                min_errors = errors
                best_pos = i
                if errors == 0:  # Perfect match found
                    break
        
        return best_pos if min_errors <= max_errors else -1
    
    def add_bits(self, new_bits):
        """Add new bits to the buffer and try to decode packets"""
        old_len = len(self.bit_buffer)
        self.bit_buffer.extend(new_bits)
        
        # Debug: Show buffer status occasionally
        if self.debug and len(self.bit_buffer) > old_len and len(self.bit_buffer) % 200 == 0:
            print(f"Bit buffer: {len(self.bit_buffer)} bits")
            
            # Show current preamble we're looking for
            preamble_str = ''.join(map(str, self.PREAMBLE))
            print(f"Looking for preamble: {preamble_str}")
            
            # Check if we have the exact preamble pattern anywhere
            buffer_array = np.array(list(self.bit_buffer), dtype=np.uint8)
            if len(buffer_array) >= len(self.PREAMBLE):
                # Try perfect match search across the buffer
                perfect_match_pos = self.find_pattern(buffer_array, self.PREAMBLE, max_errors=0)
                if perfect_match_pos >= 0:
                    print(f"PERFECT preamble match found at position {perfect_match_pos}!")
                else:
                    # Show what we have at the beginning
                    first_bits = buffer_array[:min(len(self.PREAMBLE), len(buffer_array))]
                    first_str = ''.join(map(str, first_bits))
                    print(f"First {len(first_bits)} bits: {first_str}")
        
        return self.try_decode_packet()
    
    def try_decode_packet(self):
        """Try to decode a packet from the current bit buffer"""
        min_packet_size = (len(self.PREAMBLE) + len(self.START_MARKER) + 
                          PacketProtocol.HEADER_LENGTH * 14 + 
                          PacketProtocol.MIN_PAYLOAD_LENGTH * 14 + 
                          len(self.END_MARKER))
        
        if len(self.bit_buffer) < min_packet_size:
            return None  # Not enough data for a minimal packet
        
        # Convert deque to numpy array for processing
        buffer_array = np.array(list(self.bit_buffer), dtype=np.uint8)
        
        # Look for preamble (require perfect match)
        preamble_pos = self.find_pattern(buffer_array, self.PREAMBLE, max_errors=0)
        
        if preamble_pos == -1:
            return None
        
        # Look for start marker after preamble
        expected_start_pos = preamble_pos + len(self.PREAMBLE)
        if expected_start_pos + len(self.START_MARKER) > len(buffer_array):
            return None
        
        start_marker_data = buffer_array[expected_start_pos:expected_start_pos + len(self.START_MARKER)]
        start_marker_errors = np.sum(start_marker_data != self.START_MARKER)
        if start_marker_errors > 0:  # Require perfect match for start marker
            # Remove processed bits and try again
            for _ in range(preamble_pos + 1):
                if self.bit_buffer:
                    self.bit_buffer.popleft()
            return None
        
        # Try to decode header (4 bytes = 56 encoded bits)
        header_start = expected_start_pos + len(self.START_MARKER)
        header_end = header_start + PacketProtocol.HEADER_LENGTH * 14
        
        if header_end > len(buffer_array):
            return None  # Not enough data for header
        
        header_bits = buffer_array[header_start:header_end]
        try:
            header_bytes, header_errors = self.hamming.decode_bytes(header_bits)
            if len(header_bytes) < PacketProtocol.HEADER_LENGTH:
                return None
            
            # Parse header
            payload_length = (header_bytes[0] << 8) | header_bytes[1]
            sequence_number = header_bytes[2]
            
            # Validate payload length
            if (payload_length < PacketProtocol.MIN_PAYLOAD_LENGTH or 
                payload_length > PacketProtocol.MAX_PAYLOAD_LENGTH):
                # Invalid payload length, probably not a real packet
                for _ in range(preamble_pos + 1):
                    if self.bit_buffer:
                        self.bit_buffer.popleft()
                return None
            
            # Calculate expected payload encoded length
            payload_encoded_length = payload_length * 14  # Each byte becomes 14 bits with Hamming encoding
            
            # Check if we have enough data for the complete packet
            payload_start = header_end
            payload_end = payload_start + payload_encoded_length
            end_marker_start = payload_end
            end_marker_end = end_marker_start + len(self.END_MARKER)
            
            if end_marker_end > len(buffer_array):
                return None  # Not enough data for complete packet
            
            # Decode payload
            payload_bits = buffer_array[payload_start:payload_end]
            payload_bytes, payload_errors = self.hamming.decode_bytes(payload_bits)
            
            # Check end marker (require perfect match)
            end_marker_data = buffer_array[end_marker_start:end_marker_end]
            end_marker_errors = np.sum(end_marker_data != self.END_MARKER)
            if end_marker_errors > 0:  # Require perfect match for end marker
                # Remove processed bits and try again
                for _ in range(preamble_pos + 1):
                    if self.bit_buffer:
                        self.bit_buffer.popleft()
                return None
            
            # Successful packet decode
            self.packets_received += 1
            
            # Remove the decoded packet from buffer
            for _ in range(end_marker_end):
                if self.bit_buffer:
                    self.bit_buffer.popleft()
            
            # Return decoded packet info
            packet_info = {
                'sequence_number': sequence_number,
                'payload_length': payload_length,
                'payload': payload_bytes,
                'header_errors': header_errors,
                'payload_errors': payload_errors,
                'total_packet_bits': end_marker_end - preamble_pos,
                'packet_number': self.packets_received
            }
            
            return packet_info
            
        except Exception as e:
            if self.debug:
                print(f"Packet decode error: {e}")
            # Remove some bits and try again
            for _ in range(preamble_pos + 1):
                if self.bit_buffer:
                    self.bit_buffer.popleft()
            return None
