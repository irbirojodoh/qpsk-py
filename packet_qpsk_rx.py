#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Packet-based QPSK Receiver with Hamming Code Error Correction
Based on simplified_qpsk_rx.py with added packet decoding capabilities
"""

import numpy as np
from gnuradio import gr, blocks, digital, analog, filter, uhd
from gnuradio.filter import firdes
import time
import threading
import signal
import sys
import math
from collections import deque

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

class PacketDecoder:
    """Decode packets with preamble, header, payload, and end marker"""
    
    def __init__(self):
        self.hamming = HammingDecoder()
        self.debug = False  # Will be set by receiver
        
        # Packet structure constants
        self.PREAMBLE = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0], dtype=np.uint8)
        self.START_MARKER = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)
        self.END_MARKER = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.uint8)
        
        # For packet search
        self.bit_buffer = deque(maxlen=1000)  # Circular buffer for incoming bits
        self.packets_received = 0
    
    def find_pattern(self, data, pattern, max_errors=0):
        """Find pattern in data array with very strict matching"""
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
        
        # Debug: Show buffer status occasionally and search for preamble more often
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
                    
                    # Try with 1 error to see how close we are
                    close_match_pos = self.find_pattern(buffer_array, self.PREAMBLE, max_errors=1)
                    if close_match_pos >= 0:
                        close_bits = buffer_array[close_match_pos:close_match_pos+len(self.PREAMBLE)]
                        close_str = ''.join(map(str, close_bits))
                        errors = np.sum(close_bits != self.PREAMBLE)
                        print(f"Close match (1 error) at pos {close_match_pos}: {close_str} ({errors} errors)")
            
        return self.try_decode_packet()
    
    def try_decode_packet(self):
        """Try to decode a packet from the current bit buffer"""
        if len(self.bit_buffer) < len(self.PREAMBLE) + len(self.START_MARKER) + 56 + len(self.END_MARKER):
            return None  # Not enough data for a minimal packet
        
        # Convert deque to numpy array for processing
        buffer_array = np.array(list(self.bit_buffer), dtype=np.uint8)
        
        # Look for preamble (require perfect match)
        preamble_pos = self.find_pattern(buffer_array, self.PREAMBLE, max_errors=0)
        
        # # Debug: Log preamble search results occasionally
        # if len(self.bit_buffer) % 500 == 0:  # Reduce debug frequency
        #     if preamble_pos >= 0:
        #         print(f"Found PERFECT preamble at position {preamble_pos} in {len(buffer_array)} bits")
        #     else:
        #         print(f"No perfect preamble in {len(buffer_array)} bits")
        
        if preamble_pos == -1:
            return None
        
        # Look for start marker after preamble (allow some errors)
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
        header_end = header_start + 56
        
        if header_end > len(buffer_array):
            return None  # Not enough data for header
        
        header_bits = buffer_array[header_start:header_end]
        try:
            header_bytes, header_errors = self.hamming.decode_bytes(header_bits)
            if len(header_bytes) < 4:
                return None
            
            # Parse header
            payload_length = (header_bytes[0] << 8) | header_bytes[1]
            sequence_number = header_bytes[2]
            
            # Validate payload length (should be reasonable - between 1 and 255 bytes)
            if payload_length < 1 or payload_length > 255:
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

def create_constellation():
    """Create QPSK constellation"""
    return digital.constellation_calcdist(
        [-1-1j, -1+1j, 1+1j, 1-1j], 
        [0, 1, 2, 3],
        4, 1, 
        digital.constellation.AMPLITUDE_NORMALIZATION
    ).base()

def create_rrc_taps(nfilts, samp_rate, sps, alpha):
    """Create Root Raised Cosine filter taps"""
    return firdes.root_raised_cosine(
        nfilts, 
        nfilts * samp_rate, 
        samp_rate / sps, 
        alpha, 
        (11 * sps * nfilts)
    )

def setup_usrp(samp_rate, center_freq, gain):
    """Setup USRP source"""
    usrp_source = uhd.usrp_source(
        ",".join(("addr=192.168.10.16", '')),
        uhd.stream_args(
            cpu_format="fc32",
            args='',
            channels=list(range(0, 1)),
        ),
    )
    usrp_source.set_samp_rate(samp_rate)
    usrp_source.set_center_freq(center_freq, 0)
    usrp_source.set_antenna('J2', 0)
    usrp_source.set_bandwidth(20e6, 0)
    usrp_source.set_rx_agc(False, 0)
    usrp_source.set_gain(gain, 0)
    return usrp_source

def display_packets_terminal(receiver, update_interval=1.0):
    """Display packet information in terminal without plotting"""
    
    if receiver.debug:
        print("Starting packet decoder (terminal mode)...")
        print("Press Ctrl+C to stop.")
    
    packet_history = deque(maxlen=10)  # Keep last 10 packets for display
    
    try:
        while True:
            # Get signal power for detection
            signal_power = receiver.get_signal_power()
            power_db = 10 * np.log10(signal_power + 1e-10)  # Convert to dB, avoid log(0)
            
            # Show signal status periodically (only in debug mode)
            if receiver.debug and int(time.time()) % 10 == 0:  # Every 10 seconds
                print(f"Signal power: {power_db:.1f} dB")
            
            # Check for new packets
            latest_packet = receiver.get_latest_packet()
            if latest_packet is not None:
                packet_history.append(latest_packet)
                
                # Get current time for display
                current_time = time.strftime("%H:%M:%S", time.localtime())
                
                if receiver.debug:
                    # Full debug display
                    print(f"\n{'='*60}")
                    print(f"PACKET #{latest_packet['packet_number']} RECEIVED")
                    print(f"{'='*60}")
                    print(f"Time: {current_time}")
                    print(f"Sequence Number: {latest_packet['sequence_number']}")
                    print(f"Payload Length: {latest_packet['payload_length']} bytes")
                    print(f"Header Errors Corrected: {latest_packet['header_errors']}")
                    print(f"Payload Errors Corrected: {latest_packet['payload_errors']}")
                    print(f"Total Packet Size: {latest_packet['total_packet_bits']} bits")
                    print(f"Signal Power: {power_db:.1f} dB")
                    
                    try:
                        decoded_message = latest_packet['payload'].decode('utf-8', errors='replace')
                        print(f"Message: '{decoded_message}'")
                    except:
                        print(f"Raw Payload: {latest_packet['payload'].hex()}")
                    
                    print(f"{'='*60}")
                    
                    # Show packet history summary
                    if len(packet_history) > 1:
                        print(f"\nPacket History ({len(packet_history)} packets):")
                        for i, pkt in enumerate(list(packet_history)[-5:]):  # Show last 5
                            try:
                                msg = pkt['payload'].decode('utf-8', errors='replace')
                                msg_display = msg[:40] + "..." if len(msg) > 40 else msg
                            except:
                                msg_display = f"[Binary: {len(pkt['payload'])} bytes]"
                            
                            print(f"  #{pkt['packet_number']:3d}: SEQ={pkt['sequence_number']:3d} "
                                  f"Errors(H={pkt['header_errors']},P={pkt['payload_errors']}) "
                                  f"'{msg_display}'")
                        print()
                else:
                    # Simple display - just time and message
                    try:
                        decoded_message = latest_packet['payload'].decode('utf-8', errors='replace')
                        print(f"[{current_time}] {decoded_message}")
                    except:
                        print(f"[{current_time}] Binary data: {latest_packet['payload'].hex()}")
            
            time.sleep(update_interval)
            
    except KeyboardInterrupt:
        print("\nStopping packet decoder...")
    except Exception as e:
        print(f"Display error: {e}")
        if receiver.debug:
            import traceback
            traceback.print_exc()

class PacketQPSKReceiver(gr.top_block):
    """Packet-based QPSK Receiver Flow Graph"""
    
    def __init__(self, debug=False):
        gr.top_block.__init__(self, "Packet QPSK Receiver")
        
        # Debug flag to control verbose output
        self.debug = debug
        
        # Parameters
        self.samp_rate = 1e6
        self.center_freq = 5e9
        self.gain = 20
        self.sps = 16  # samples per symbol
        self.alpha = 0.50  # rolloff factor
        self.nfilts = 32
        
        # Create constellation
        self.constellation = create_constellation()
        
        # Create RRC taps
        self.rrc_taps = create_rrc_taps(self.nfilts, self.samp_rate, self.sps, self.alpha)
        
        # Packet decoder
        self.packet_decoder = PacketDecoder()
        self.packet_decoder.debug = self.debug  # Pass debug flag to decoder
        self.latest_packet = None
        self.packet_lock = threading.Lock()
        
        # Setup blocks
        self.setup_blocks()
        self.connect_blocks()
        
        # Start bit processing thread
        self.process_bits = True
        self.bit_thread = threading.Thread(target=self.bit_processing_loop)
        self.bit_thread.daemon = True
        
    def setup_blocks(self):
        """Setup all GNU Radio blocks"""
        
        # USRP Source
        self.usrp_source = setup_usrp(self.samp_rate, self.center_freq, self.gain)
        
        # AGC - use same parameters as GRC code
        self.agc = analog.agc_cc(1e-4, 1.0, 1.0, 65536)  # Same as GRC
        
        # Low-pass filter to clean up signal before synchronization
        lpf_taps = firdes.low_pass(
            1.0,                    # gain
            self.samp_rate,         # sampling rate
            self.samp_rate / self.sps * 0.6,  # cutoff frequency (slightly below symbol rate)
            self.samp_rate / self.sps * 0.2   # transition width
        )
        self.lpf = filter.fir_filter_ccc(1, lpf_taps)
        
        # Frequency correction - helps with carrier offset
        self.freq_xlating_fir_filter = filter.freq_xlating_fir_filter_ccc(
            1, 
            [1.0], 
            0,  # No initial offset
            self.samp_rate
        )
        
        # FLL Band Edge - use same parameters as GRC code
        self.fll_band_edge = digital.fll_band_edge_cc(
            self.sps, self.alpha, (self.sps * 2 + 1), 
            (2 * math.pi / self.sps / 100 / self.sps)  # Same as GRC
        )
        
        # Skip initial samples - reduce this to help with signal acquisition
        self.skiphead = blocks.skiphead(gr.sizeof_gr_complex * 1, int(self.samp_rate * 0.1))  # Only skip 0.1 second
        
        # Use symbol sync with parameters optimized for signal acquisition
        self.symbol_sync = digital.symbol_sync_cc(
            digital.TED_SIGNAL_TIMES_SLOPE_ML,  # Signal Times Slope Maximum Likelihood
            self.sps,                           # samples per symbol
            0.08,                              # Slightly higher loop bandwidth for faster acquisition
            1.0,                               # damping factor
            1.0,                               # ted gain
            0.2,                               # Higher maximum rate deviation for better acquisition
            1,                                 # output samples per symbol
            self.constellation,                # constellation
            digital.IR_PFB_MF,                # Polyphase Filterbank Matched Filter
            self.nfilts,                       # number of filters
            self.rrc_taps                      # filter taps
        )
        
        # Additional decimation to ensure exactly 1 sample per symbol
        self.decimator = filter.fir_filter_ccc(1, [1.0])  # No decimation, just ensure clean signal
        
        # Try a different approach - add a slicer instead of constellation receiver
        # This might help debug if the issue is with constellation recovery
        self.complex_to_real = blocks.complex_to_real()
        self.complex_to_imag = blocks.complex_to_imag()
        self.add_const_real = blocks.add_const_ff(0.0)
        self.add_const_imag = blocks.add_const_ff(0.0)
        self.float_to_complex = blocks.float_to_complex()
        
        # Simple slicer for debugging
        self.binary_slicer = digital.binary_slicer_fb()
        
        # Keep constellation receiver for comparison
        # Constellation Receiver - use same parameters as GRC code
        self.constellation_receiver = digital.constellation_receiver_cb(
            self.constellation,
            (2 * math.pi / 100),  # Same as GRC
            (-math.pi),
            math.pi
        )
        
        # Differential Decoder
        self.diff_decoder = digital.diff_decoder_bb(
            self.constellation.arity(),
            digital.DIFF_DIFFERENTIAL
        )
        
        # Unpack bits from symbols
        self.unpack_k_bits = blocks.unpack_k_bits_bb(2)  # QPSK = 2 bits per symbol
        
        # Data sinks
        self.vector_sink_constellation = blocks.vector_sink_c()  # For constellation display
        self.vector_sink_bits = blocks.vector_sink_b()  # For bit data
        self.vector_sink_symbols = blocks.vector_sink_b()  # For raw symbol data (before diff decode)
        self.vector_sink_clock_recovery = blocks.vector_sink_c()  # For clock recovery output
        
        # Power measurement
        self.power_probe = blocks.probe_signal_f()
        self.complex_to_mag_squared = blocks.complex_to_mag_squared()
        self.moving_average = blocks.moving_average_ff(int(self.samp_rate/100), 1.0/int(self.samp_rate/100), 4000)
        
        # Null sinks for unused outputs
        self.null_sink1 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink2 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink3 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink4 = blocks.null_sink(gr.sizeof_float * 1)
    
    def connect_blocks(self):
        """Connect all blocks in the flow graph"""
        
        # Main signal path
        self.connect((self.usrp_source, 0), (self.freq_xlating_fir_filter, 0))
        self.connect((self.freq_xlating_fir_filter, 0), (self.agc, 0))
        self.connect((self.agc, 0), (self.lpf, 0))
        self.connect((self.lpf, 0), (self.fll_band_edge, 0))
        self.connect((self.fll_band_edge, 0), (self.skiphead, 0))
        self.connect((self.skiphead, 0), (self.symbol_sync, 0))
        self.connect((self.symbol_sync, 0), (self.vector_sink_clock_recovery, 0))  # Capture symbol sync output
        self.connect((self.symbol_sync, 0), (self.decimator, 0))
        self.connect((self.decimator, 0), (self.constellation_receiver, 0))
        self.connect((self.constellation_receiver, 0), (self.vector_sink_symbols, 0))  # Raw symbols
        self.connect((self.constellation_receiver, 0), (self.diff_decoder, 0))
        self.connect((self.diff_decoder, 0), (self.unpack_k_bits, 0))
        self.connect((self.unpack_k_bits, 0), (self.vector_sink_bits, 0))
        
        # Constellation data collection
        self.connect((self.constellation_receiver, 4), (self.vector_sink_constellation, 0))
        
        # Power measurement
        self.connect((self.fll_band_edge, 0), (self.complex_to_mag_squared, 0))
        self.connect((self.complex_to_mag_squared, 0), (self.moving_average, 0))
        self.connect((self.moving_average, 0), (self.power_probe, 0))
        
        # Connect unused outputs to null sinks
        self.connect((self.constellation_receiver, 1), (self.null_sink1, 0))
        self.connect((self.constellation_receiver, 2), (self.null_sink2, 0))
        self.connect((self.constellation_receiver, 3), (self.null_sink3, 0))
    
    def start(self):
        """Start the receiver and bit processing"""
        super().start()
        self.bit_thread.start()
    
    def stop(self):
        """Stop the receiver and bit processing"""
        self.process_bits = False
        super().stop()
    
    def bit_processing_loop(self):
        """Process incoming bits for packet decoding"""
        last_bit_count = 0
        bit_rate_counter = 0
        last_time = time.time()
        last_symbol_count = 0
        stuck_counter = 0  # Count how many times we detect stuck state
        last_power_check = 0
        power_threshold = 1e-8  # Threshold for signal detection
        signal_detected = False
        
        if self.debug:
            print("Bit processing thread started...")
        
        while self.process_bits:
            try:
                # Check signal power periodically
                current_power = self.get_signal_power()
                current_time = time.time()
                
                # Check for signal presence every 2 seconds
                if current_time - last_power_check >= 2.0:
                    power_db = 10 * np.log10(current_power + 1e-10)
                    
                    # Detect signal presence
                    if current_power > power_threshold:
                        if not signal_detected:
                            if self.debug:
                                print(f"Signal detected! Power: {power_db:.1f} dB")
                            signal_detected = True
                            # Reset everything when signal is first detected
                            self.reset_for_new_signal()
                    else:
                        if signal_detected:
                            if self.debug:
                                print(f"Signal lost! Power: {power_db:.1f} dB")
                            signal_detected = False
                    
                    last_power_check = current_time
                
                # Get new bits
                current_bits = list(self.vector_sink_bits.data())
                
                if len(current_bits) > last_bit_count:
                    # Process new bits
                    new_bits = current_bits[last_bit_count:]
                    
                    # Check symbol recovery too
                    current_symbols = self.get_symbol_data()
                    current_symbol_count = len(current_symbols)
                    
                    # Debug: Show bit rate and symbol rate periodically
                    bit_rate_counter += len(new_bits)
                    if self.debug and current_time - last_time >= 5.0:  # Every 5 seconds
                        bit_rate = bit_rate_counter / (current_time - last_time)
                        
                        # Calculate symbol rate properly
                        symbol_rate = (current_symbol_count - last_symbol_count) / (current_time - last_time)
                        
                        expected_symbol_rate = self.samp_rate / self.sps  # Expected symbols per second
                        
                        print(f"Bit rate: {bit_rate:.1f} bits/sec, Symbol rate: {symbol_rate:.1f} sym/sec")
                        print(f"Expected symbol rate: {expected_symbol_rate:.1f} sym/sec")
                        print(f"Total bits: {len(current_bits)}, Total symbols: {current_symbol_count}")
                        print(f"Signal detected: {signal_detected}, Power: {10 * np.log10(current_power + 1e-10):.1f} dB")
                        
                        # Analyze symbol sync
                        sync_analysis = self.analyze_symbol_sync()
                        
                        # Check if we're stuck (very low or zero symbol rate)
                        is_stuck = False
                        if signal_detected and symbol_rate <= 0.1:
                            is_stuck = True
                            stuck_counter += 1
                            print(f"WARNING: Symbol rate extremely low despite signal presence - receiver appears stuck (count: {stuck_counter})")
                        
                        # Symbol rate ratio analysis
                        if symbol_rate > 0:
                            symbol_ratio = symbol_rate / expected_symbol_rate
                            print(f"Symbol rate ratio: {symbol_ratio:.2f}x expected")
                            if symbol_ratio > 10:
                                print("WARNING: Symbol rate too high - timing recovery may be failing")
                            elif symbol_ratio < 0.1:
                                print("WARNING: Symbol rate too low - check signal presence")
                        
                        # Show some recent bits and symbols for debugging
                        if len(new_bits) > 0:
                            recent_bits = new_bits[-min(32, len(new_bits)):]
                            bit_str = ''.join(map(str, recent_bits))
                            print(f"Recent bits: {bit_str}")
                            
                            # Check for bit diversity
                            bit_counts = [recent_bits.count(i) for i in [0, 1]]
                            print(f"Bit distribution (0s, 1s): {bit_counts}")
                            
                            # Check if we're stuck with all 0s or all 1s
                            if bit_counts[0] == len(recent_bits) or bit_counts[1] == len(recent_bits):
                                print("WARNING: All bits are the same - receiver may be stuck")
                                if signal_detected:
                                    is_stuck = True
                        
                        if len(current_symbols) > 10:
                            recent_symbols = current_symbols[-10:]
                            print(f"Recent symbols: {recent_symbols}")
                            
                            # Check for symbol distribution
                            symbol_counts = [recent_symbols.count(i) for i in range(4)]
                            print(f"Symbol distribution in last 10: {symbol_counts}")
                            
                            # Check if we have symbol diversity
                            unique_symbols = len(set(recent_symbols))
                            print(f"Unique symbols in recent data: {unique_symbols}/4")
                            if unique_symbols <= 1 and signal_detected:
                                print("WARNING: No symbol diversity despite signal presence - constellation receiver may be stuck")
                                is_stuck = True
                        
                        # If we're stuck, try more aggressive recovery
                        if is_stuck:
                            print("Attempting aggressive recovery...")
                            self.aggressive_recovery()
                            stuck_counter += 1
                            
                            # If we've been stuck many times, suggest checking the transmitter
                            if stuck_counter > 3:  # Reduced threshold
                                print("CRITICAL: Receiver has been stuck multiple times.")
                                print("Trying to restart synchronization...")
                                self.restart_synchronization()
                                stuck_counter = 0  # Reset counter
                        
                        bit_rate_counter = 0
                        last_time = current_time
                        last_symbol_count = current_symbol_count
                    
                    # Only process bits if we have signal and reasonable symbol diversity
                    if signal_detected and len(current_symbols) > 20:
                        recent_symbols = current_symbols[-20:]
                        unique_symbols = len(set(recent_symbols))
                        
                        # Check if we have at least 2 different symbols (some diversity)
                        if unique_symbols >= 2:
                            # Try to decode packet
                            packet = self.packet_decoder.add_bits(new_bits)
                            
                            if packet:
                                if self.debug:
                                    print(f"Packet decoded! Bits processed: {len(current_bits)}")
                                stuck_counter = 0 # Reset stuck counter on successful decode
                                with self.packet_lock:
                                    self.latest_packet = packet
                        else:
                            if self.debug and signal_detected:
                                print("Skipping packet decode - no symbol diversity despite signal")
                    
                    last_bit_count = len(current_bits)
                    
                    # Reset sink periodically to avoid memory issues
                    if len(current_bits) > 15000:  # Increase threshold
                        if self.debug:
                            print(f"Resetting bit sink after {len(current_bits)} bits")
                        self.vector_sink_bits.reset()
                        self.vector_sink_symbols.reset()  # Also reset symbols
                        last_bit_count = 0
                        last_symbol_count = 0
                
                time.sleep(0.1)  # Longer delay to reduce CPU usage
                
            except Exception as e:
                if self.debug:
                    print(f"Bit processing error: {e}")
                time.sleep(0.1)
    
    def get_constellation_data(self):
        """Get constellation data for plotting"""
        return np.array(self.vector_sink_constellation.data())
    
    def get_symbol_data(self):
        """Get raw symbol data"""
        return list(self.vector_sink_symbols.data())
    
    def get_signal_power(self):
        """Get current signal power level"""
        return self.power_probe.level()
    
    def get_latest_packet(self):
        """Get latest decoded packet (returns None if no new packet)"""
        with self.packet_lock:
            packet = self.latest_packet
            self.latest_packet = None  # Clear after reading
            return packet
    
    def reset_data_sink(self):
        """Reset the vector sink to collect fresh data"""
        try:
            self.vector_sink_constellation.reset()
        except:
            pass
    
    def reset_constellation_receiver(self):
        """Reset constellation receiver state to help with synchronization"""
        try:
            # Reset the vector sinks to clear stuck data
            self.vector_sink_bits.reset()
            self.vector_sink_symbols.reset()
            self.vector_sink_constellation.reset()
            
            # Note: We can't easily reset the constellation receiver's internal state
            # but clearing the data sinks should help
            print("Constellation receiver data sinks reset")
            
        except Exception as e:
            print(f"Error resetting constellation receiver: {e}")
    
    def aggressive_recovery(self):
        """Aggressive recovery when receiver is stuck"""
        try:
            print("Performing aggressive recovery...")
            
            # Reset all data sinks
            self.vector_sink_bits.reset()
            self.vector_sink_symbols.reset()
            self.vector_sink_constellation.reset()
            self.vector_sink_clock_recovery.reset()  # This now captures symbol sync output
            
            # Clear packet decoder buffer
            self.packet_decoder.bit_buffer.clear()
            
            print("All data sinks and buffers reset")
            
            # We can't easily restart the flowgraph from here without stopping it
            # but we can suggest checking the transmitter or restarting
            
        except Exception as e:
            print(f"Error in aggressive recovery: {e}")
    
    def get_symbol_sync_data(self):
        """Get symbol sync output data for analysis"""
        return list(self.vector_sink_clock_recovery.data())
    
    def analyze_symbol_sync(self):
        """Analyze symbol sync output to see if timing is working"""
        try:
            sync_data = self.get_symbol_sync_data()
            if len(sync_data) > 100:
                # Analyze the magnitude and phase diversity
                magnitudes = [abs(x) for x in sync_data[-100:]]
                phases = [np.angle(x) for x in sync_data[-100:]]
                
                mag_std = np.std(magnitudes)
                phase_std = np.std(phases)
                
                print(f"Symbol sync analysis: Mag std={mag_std:.3f}, Phase std={phase_std:.3f}")
                
                if mag_std < 0.01:
                    print("WARNING: Very low magnitude variation - signal may be stuck")
                if phase_std < 0.1:
                    print("WARNING: Very low phase variation - timing may not be locked")
                
                return {"mag_std": mag_std, "phase_std": phase_std}
        except Exception as e:
            print(f"Error analyzing symbol sync: {e}")
        
        return None
    
    def reset_for_new_signal(self):
        """Reset receiver when new signal is detected"""
        try:
            print("Resetting receiver for new signal...")
            
            # Reset all data sinks
            self.vector_sink_bits.reset()
            self.vector_sink_symbols.reset()
            self.vector_sink_constellation.reset()
            self.vector_sink_clock_recovery.reset()
            
            # Clear packet decoder buffer
            self.packet_decoder.bit_buffer.clear()
            
            print("Receiver reset for new signal complete")
            
        except Exception as e:
            print(f"Error resetting for new signal: {e}")
    
    def restart_synchronization(self):
        """Restart synchronization blocks when severely stuck"""
        try:
            print("Attempting to restart synchronization...")
            
            # Reset all sinks
            self.reset_for_new_signal()
            
            # We can't easily restart the GNU Radio blocks without stopping the flowgraph
            # but we can suggest manual intervention
            print("Consider restarting the receiver if problems persist")
            
        except Exception as e:
            print(f"Error restarting synchronization: {e}")

def start_terminal_display(receiver, update_interval=0.5):
    """Start packet display in terminal in a separate thread"""
    display_thread = threading.Thread(
        target=display_packets_terminal, 
        args=(receiver, update_interval)
    )
    display_thread.daemon = True
    display_thread.start()
    return display_thread

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\nShutting down gracefully...')
    sys.exit(0)

def main():
    """Main function"""
    # Set debug mode here - change to True for full debug output
    DEBUG_MODE = False
    
    print("=" * 60)
    print("PACKET-BASED QPSK RECEIVER WITH HAMMING CODE")
    print("=" * 60)
    print("Features:")
    print("- Terminal-based packet display")
    print("- Packet decoding with error correction")
    print("- Live display of received messages")
    print("- Hamming(7,4) error correction")
    print("- Automatic signal detection and recovery")
    print("- Works when transmitter starts after receiver")
    if DEBUG_MODE:
        print("- DEBUG MODE: Full diagnostic output enabled")
    else:
        print("- NORMAL MODE: Clean message display only")
    print("=" * 60)
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create receiver with debug flag
        receiver = PacketQPSKReceiver(debug=DEBUG_MODE)
        
        print("Starting packet receiver...")
        receiver.start()
        
        # Wait a moment for the receiver to initialize
        time.sleep(2)
        
        # Start terminal display
        display_thread = start_terminal_display(receiver, update_interval=0.5)
        
        if DEBUG_MODE:
            print("\nReceiver running with terminal display.")
            print("The receiver will automatically detect when the transmitter starts.")
            print("You can start the transmitter at any time.")
            print("Press Ctrl+C to stop.")
            print("=" * 60)
        else:
            print("\nReceiver ready. Waiting for messages...")
            print("Press Ctrl+C to stop.")
        
        # Keep the main thread running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping receiver...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            receiver.stop()
            receiver.wait()
        except:
            pass
        print("Receiver stopped.")

if __name__ == '__main__':
    main()
