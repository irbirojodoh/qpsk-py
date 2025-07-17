#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple QPSK Modem Script using GNU Radio
Simplified version maintaining GNU Radio signal processing
"""

import numpy as np
from gnuradio import gr, blocks, digital, uhd
from gnuradio.filter import firdes
import threading
import time
import signal
import sys

# Global variables
stop_signal = False

class QpskModulator(gr.top_block):
    """GNU Radio flowgraph for QPSK modulation"""
    def __init__(self, samp_rate=1e6, sps=16, alpha=0.5):
        gr.top_block.__init__(self)
        
        # Variables
        self.samp_rate = samp_rate
        self.sps = sps
        self.alpha = alpha
        
        # Create QPSK constellation (same as your original)
        self.constellation = digital.constellation_calcdist(
            [-1-1j, -1+1j, 1+1j, 1-1j], 
            [0, 1, 2, 3],
            4, 1, 
            digital.constellation.AMPLITUDE_NORMALIZATION
        ).base()
        # self.constellation.set_npwr(1.0)
        
        # Blocks
        self.analog_random_source = blocks.vector_source_b(
            list(map(int, np.random.randint(0, 256, (1024//8)))), 
            True
        )
        
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
        self.connect((self.analog_random_source, 0), (self.digital_constellation_modulator, 0))
        self.connect((self.digital_constellation_modulator, 0), (self.blocks_multiply_const, 0))
        self.connect((self.blocks_multiply_const, 0), (self.vector_sink, 0))

def qpsk_modulation(data_length=8192, sps=16, alpha=0.5, samp_rate=1e6):
    """
    Generate QPSK modulated signal using GNU Radio
    
    Args:
        data_length: Length of data to generate
        sps: Samples per symbol
        alpha: Excess bandwidth (roll-off factor)
        samp_rate: Sample rate
    
    Returns:
        Complex IQ samples
    """
    print("Generating QPSK signal using GNU Radio...")
    
    # Create the modulator flowgraph
    modulator = QpskModulator(samp_rate, sps, alpha)
    
    # Run the flowgraph to generate samples
    modulator.start()
    
    # Let it run for a bit to generate samples
    time.sleep(0.5)
    
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

def rx_worker(modulated_signal, usrp_args="addr=192.168.10.81", center_freq=5e9, 
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
        print(f"Error in rx_worker: {e}")
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
    data_length = 8192   # Data length for generation
    
    print("=== QPSK Modem with GNU Radio ===")
    print(f"Sample Rate: {samp_rate/1e6:.1f} MHz")
    print(f"Center Frequency: {center_freq/1e9:.3f} GHz")
    print(f"Samples per Symbol: {sps}")
    print(f"Excess Bandwidth: {alpha}")
    
    # Generate QPSK modulated signal using GNU Radio
    modulated_signal = qpsk_modulation(data_length, sps, alpha, samp_rate)
    
    if len(modulated_signal) == 0:
        print("Error: No signal generated!")
        return
    
    print(f"\nSignal generated successfully!")
    print(f"Signal length: {len(modulated_signal)} samples")
    print(f"Signal duration: {len(modulated_signal)/samp_rate:.3f} seconds")
    
    # Start transmission in a separate thread
    tx_thread = threading.Thread(
        target=rx_worker,
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