"""
QPSK Receiver implementation
"""

import numpy as np
import time
import threading
import math
from gnuradio import gr, blocks, digital, analog, filter
from ..common import create_constellation, create_rrc_taps
from ..common.usrp_config import setup_usrp_source
from .decoder import PacketDecoder

class PacketQPSKReceiver(gr.top_block):
    """Packet-based QPSK Receiver Flow Graph"""
    
    def __init__(self, debug=False, samp_rate=1e6, center_freq=5e9, gain=20, 
                 usrp_addr="addr=192.168.10.16", antenna="J2"):
        gr.top_block.__init__(self, "Packet QPSK Receiver")
        
        # Debug flag to control verbose output
        self.debug = debug
        
        # Parameters
        self.samp_rate = samp_rate
        self.center_freq = center_freq
        self.gain = gain
        self.usrp_addr = usrp_addr
        self.antenna = antenna
        self.sps = 16  # samples per symbol
        self.alpha = 0.50  # rolloff factor
        self.nfilts = 32
        
        # Create constellation and RRC taps
        self.constellation = create_constellation()
        self.rrc_taps = create_rrc_taps(self.nfilts, self.samp_rate, self.sps, self.alpha)
        
        # Packet decoder
        self.packet_decoder = PacketDecoder(debug=self.debug)
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
        self.usrp_source = setup_usrp_source(
            self.samp_rate, self.center_freq, self.gain, 
            self.usrp_addr, self.antenna
        )
        
        # AGC
        self.agc = analog.agc_cc(1e-4, 1.0, 1.0, 65536)
        
        # Low-pass filter to clean up signal before synchronization
        lpf_taps = filter.firdes.low_pass(
            1.0,                    # gain
            self.samp_rate,         # sampling rate
            self.samp_rate / self.sps * 0.6,  # cutoff frequency
            self.samp_rate / self.sps * 0.2   # transition width
        )
        self.lpf = filter.fir_filter_ccc(1, lpf_taps)
        
        # Frequency correction
        self.freq_xlating_fir_filter = filter.freq_xlating_fir_filter_ccc(
            1, [1.0], 0, self.samp_rate
        )
        
        # FLL Band Edge
        self.fll_band_edge = digital.fll_band_edge_cc(
            self.sps, self.alpha, (self.sps * 2 + 1), 
            (2 * math.pi / self.sps / 100 / self.sps)
        )
        
        # Skip initial samples
        self.skiphead = blocks.skiphead(gr.sizeof_gr_complex * 1, int(self.samp_rate * 0.1))
        
        # Symbol sync
        self.symbol_sync = digital.symbol_sync_cc(
            digital.TED_SIGNAL_TIMES_SLOPE_ML,
            self.sps, 0.08, 1.0, 1.0, 0.2, 1,
            self.constellation, digital.IR_PFB_MF,
            self.nfilts, self.rrc_taps
        )
        
        # Decimation filter
        self.decimator = filter.fir_filter_ccc(1, [1.0])
        
        # Constellation Receiver
        self.constellation_receiver = digital.constellation_receiver_cb(
            self.constellation, (2 * math.pi / 100), (-math.pi), math.pi
        )
        
        # Differential Decoder
        self.diff_decoder = digital.diff_decoder_bb(
            self.constellation.arity(), digital.DIFF_DIFFERENTIAL
        )
        
        # Unpack bits from symbols
        self.unpack_k_bits = blocks.unpack_k_bits_bb(2)  # QPSK = 2 bits per symbol
        
        # Data sinks
        self.vector_sink_constellation = blocks.vector_sink_c()
        self.vector_sink_bits = blocks.vector_sink_b()
        self.vector_sink_symbols = blocks.vector_sink_b()
        self.vector_sink_clock_recovery = blocks.vector_sink_c()
        
        # Power measurement
        self.power_probe = blocks.probe_signal_f()
        self.complex_to_mag_squared = blocks.complex_to_mag_squared()
        self.moving_average = blocks.moving_average_ff(
            int(self.samp_rate/100), 1.0/int(self.samp_rate/100), 4000
        )
        
        # Null sinks for unused outputs
        self.null_sink1 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink2 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink3 = blocks.null_sink(gr.sizeof_float * 1)
    
    def connect_blocks(self):
        """Connect all blocks in the flow graph"""
        
        # Main signal path
        self.connect((self.usrp_source, 0), (self.freq_xlating_fir_filter, 0))
        self.connect((self.freq_xlating_fir_filter, 0), (self.agc, 0))
        self.connect((self.agc, 0), (self.lpf, 0))
        self.connect((self.lpf, 0), (self.fll_band_edge, 0))
        self.connect((self.fll_band_edge, 0), (self.skiphead, 0))
        self.connect((self.skiphead, 0), (self.symbol_sync, 0))
        self.connect((self.symbol_sync, 0), (self.vector_sink_clock_recovery, 0))
        self.connect((self.symbol_sync, 0), (self.decimator, 0))
        self.connect((self.decimator, 0), (self.constellation_receiver, 0))
        self.connect((self.constellation_receiver, 0), (self.vector_sink_symbols, 0))
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
        stuck_counter = 0
        last_power_check = 0
        power_threshold = 1e-8
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
                    if self.debug and current_time - last_time >= 5.0:
                        bit_rate = bit_rate_counter / (current_time - last_time)
                        symbol_rate = (current_symbol_count - last_symbol_count) / (current_time - last_time)
                        expected_symbol_rate = self.samp_rate / self.sps
                        
                        print(f"Bit rate: {bit_rate:.1f} bits/sec, Symbol rate: {symbol_rate:.1f} sym/sec")
                        print(f"Expected symbol rate: {expected_symbol_rate:.1f} sym/sec")
                        print(f"Signal detected: {signal_detected}, Power: {10 * np.log10(current_power + 1e-10):.1f} dB")
                        
                        bit_rate_counter = 0
                        last_time = current_time
                        last_symbol_count = current_symbol_count
                    
                    # Only process bits if we have signal and reasonable symbol diversity
                    if signal_detected and len(current_symbols) > 20:
                        recent_symbols = current_symbols[-20:]
                        unique_symbols = len(set(recent_symbols))
                        
                        # Check if we have at least 2 different symbols
                        if unique_symbols >= 2:
                            # Try to decode packet
                            packet = self.packet_decoder.add_bits(new_bits)
                            
                            if packet:
                                if self.debug:
                                    print(f"Packet decoded! Bits processed: {len(current_bits)}")
                                stuck_counter = 0
                                with self.packet_lock:
                                    self.latest_packet = packet
                        else:
                            if self.debug and signal_detected:
                                print("Skipping packet decode - no symbol diversity despite signal")
                    
                    last_bit_count = len(current_bits)
                    
                    # Reset sink periodically to avoid memory issues
                    if len(current_bits) > 15000:
                        if self.debug:
                            print(f"Resetting bit sink after {len(current_bits)} bits")
                        self.vector_sink_bits.reset()
                        self.vector_sink_symbols.reset()
                        last_bit_count = 0
                        last_symbol_count = 0
                
                time.sleep(0.1)
                
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
    
    def get_symbol_sync_data(self):
        """Get symbol sync output data for analysis"""
        return list(self.vector_sink_clock_recovery.data())
    
    def get_signal_power(self):
        """Get current signal power level"""
        return self.power_probe.level()
    
    def get_latest_packet(self):
        """Get latest decoded packet (returns None if no new packet)"""
        with self.packet_lock:
            packet = self.latest_packet
            self.latest_packet = None  # Clear after reading
            return packet
    
    def reset_for_new_signal(self):
        """Reset receiver when new signal is detected"""
        try:
            if self.debug:
                print("Resetting receiver for new signal...")
            
            # Reset all data sinks
            self.vector_sink_bits.reset()
            self.vector_sink_symbols.reset()
            self.vector_sink_constellation.reset()
            self.vector_sink_clock_recovery.reset()
            
            # Clear packet decoder buffer
            self.packet_decoder.bit_buffer.clear()
            
            if self.debug:
                print("Receiver reset for new signal complete")
            
        except Exception as e:
            print(f"Error resetting for new signal: {e}")
    
    def print_config(self):
        """Print receiver configuration"""
        print(f"QPSK Receiver Configuration:")
        print(f"  USRP Address: {self.usrp_addr}")
        print(f"  Center Frequency: {self.center_freq/1e9:.3f} GHz")
        print(f"  Sample Rate: {self.samp_rate/1e6:.1f} MHz")
        print(f"  Gain: {self.gain} dB")
        print(f"  Antenna: {self.antenna}")
        print(f"  Samples per Symbol: {self.sps}")
        print(f"  Rolloff Factor: {self.alpha}")
        print(f"  Debug Mode: {self.debug}")
