"""
Hamming(7,4) error correction code implementation
"""

import numpy as np

class HammingEncoder:
    """Hamming(7,4) error correction code encoder"""
    
    def __init__(self):
        # Generator matrix for Hamming(7,4)
        self.G = np.array([
            [1, 0, 0, 0, 1, 1, 0],
            [0, 1, 0, 0, 1, 0, 1],
            [0, 0, 1, 0, 0, 1, 1],
            [0, 0, 0, 1, 1, 1, 1]
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

class HammingDecoder:
    """Hamming(7,4) error correction code decoder"""
    
    def __init__(self):
        # Parity check matrix for Hamming(7,4)
        self.H = np.array([
            [1, 1, 0, 1, 1, 0, 0],
            [1, 0, 1, 1, 0, 1, 0],
            [0, 1, 1, 1, 0, 0, 1]
        ], dtype=np.uint8)
    
    def decode_7bits(self, received_bits):
        """Decode 7-bit Hamming codeword and correct single-bit errors"""
        if len(received_bits) != 7:
            raise ValueError("Input must be exactly 7 bits")
        
        received_bits = np.array(received_bits, dtype=np.uint8)
        
        # Calculate syndrome
        syndrome = np.dot(self.H, received_bits) % 2
        
        # Check for errors
        error_position = 0
        error_corrected = False
        if np.any(syndrome):
            # Convert syndrome to error position
            error_position = syndrome[0] * 4 + syndrome[1] * 2 + syndrome[2] * 1
            
            # Correct the error
            if 1 <= error_position <= 7:
                received_bits[error_position - 1] ^= 1
                error_corrected = True
        
        # Extract data bits (positions 0, 1, 2, 3)
        data_bits = received_bits[[0, 1, 2, 3]]
        return data_bits, error_corrected
    
    def decode_bytes(self, encoded_bits):
        """Decode a sequence of Hamming-encoded bits back to bytes"""
        decoded_bytes = []
        total_errors = 0
        
        # Process 14 bits at a time (two 7-bit codewords = one byte)
        for i in range(0, len(encoded_bits), 14):
            if i + 14 <= len(encoded_bits):
                # Decode high nibble (first 7 bits)
                high_codeword = encoded_bits[i:i+7]
                high_nibble, error1 = self.decode_7bits(high_codeword)
                
                # Decode low nibble (next 7 bits)
                low_codeword = encoded_bits[i+7:i+14]
                low_nibble, error2 = self.decode_7bits(low_codeword)
                
                if error1 or error2:
                    total_errors += 1
                
                # Combine nibbles into byte (high nibble in upper 4 bits, low nibble in lower 4 bits)
                byte_val = 0
                for j in range(4):
                    byte_val |= (int(high_nibble[j]) << (7-j))  # bits 7,6,5,4
                for j in range(4):
                    byte_val |= (int(low_nibble[j]) << (3-j))   # bits 3,2,1,0
                
                decoded_bytes.append(byte_val)
        
        return bytes(decoded_bytes), total_errors
