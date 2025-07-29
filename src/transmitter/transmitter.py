"""
USRP-based QPSK transmitter
"""

import time
import threading
from gnuradio import gr, blocks
from ..common.usrp_config import setup_usrp_sink, print_usrp_info

class USRPTransmitter(gr.top_block):
    """GNU Radio flowgraph for USRP transmission"""
    
    def __init__(self, signal_data, usrp_args, center_freq, samp_rate, gain, antenna):
        gr.top_block.__init__(self)
        
        # Create vector source with the signal data (repeat continuously)
        self.vector_source = blocks.vector_source_c(signal_data, True)
        
        # Create USRP sink
        self.uhd_usrp_sink = setup_usrp_sink(samp_rate, center_freq, gain, usrp_args, antenna)
        
        # Connect the blocks
        self.connect((self.vector_source, 0), (self.uhd_usrp_sink, 0))
        
        # Store parameters for info display
        self.usrp_args = usrp_args
        self.center_freq = center_freq
        self.samp_rate = samp_rate
        self.gain = gain
        self.antenna = antenna
        self.signal_length = len(signal_data)

class USRPSingleShotTransmitter(gr.top_block):
    """GNU Radio flowgraph for single-shot USRP transmission"""
    
    def __init__(self, signal_data, usrp_args, center_freq, samp_rate, gain, antenna):
        gr.top_block.__init__(self)
        
        # Create vector source with the signal data (no repeat for single-shot)
        self.vector_source = blocks.vector_source_c(signal_data, False)
        
        # Create USRP sink
        self.uhd_usrp_sink = setup_usrp_sink(samp_rate, center_freq, gain, usrp_args, antenna)
        
        # Connect the blocks
        self.connect((self.vector_source, 0), (self.uhd_usrp_sink, 0))
        
        # Store parameters for info display
        self.usrp_args = usrp_args
        self.center_freq = center_freq
        self.samp_rate = samp_rate
        self.gain = gain
        self.antenna = antenna
        self.signal_length = len(signal_data)
    
    def print_config(self):
        """Print transmitter configuration"""
        print(f"USRP Transmitter Configuration:")
        print(f"  USRP Args: {self.usrp_args}")
        print(f"  Center Frequency: {self.center_freq/1e9:.3f} GHz")
        print(f"  Sample Rate: {self.samp_rate/1e6:.1f} MHz")
        print(f"  Gain: {self.gain} dB")
        print(f"  Antenna: {self.antenna}")
        print(f"  Signal length: {self.signal_length} samples")

def tx_worker(modulated_signal, usrp_args="addr=192.168.10.81", center_freq=5e9, 
              samp_rate=1e6, gain=20, antenna="J2", stop_event=None, verbose=True):
    """
    Transmit signal using USRP with GNU Radio
    
    Args:
        modulated_signal: Complex IQ samples to transmit
        usrp_args: USRP device arguments
        center_freq: Center frequency in Hz
        samp_rate: Sample rate in Hz
        gain: Transmit gain
        antenna: Antenna port
        stop_event: Threading event to signal stop
        verbose: Print debug information
    """
    try:
        if verbose:
            print("Setting up USRP transmission...")
        
        # Create and start the transmitter
        transmitter = USRPTransmitter(
            modulated_signal, usrp_args, center_freq, 
            samp_rate, gain, antenna
        )
        
        # if verbose:
        #     transmitter.print_config()
        
        if verbose:
            print("Starting transmission...")
        transmitter.start()
        
        # Keep transmitting until stop signal
        while stop_event is None or not stop_event.is_set():
            time.sleep(0.1)
        
        if verbose:
            print("Stopping transmission...")
        transmitter.stop()
        transmitter.wait()
        
    except Exception as e:
        print(f"Error in tx_worker: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if verbose:
            print("Transmission stopped")

def tx_single_shot(modulated_signal, usrp_args="addr=192.168.10.81", center_freq=5e9, 
                   samp_rate=1e6, gain=20, antenna="J2", verbose=True):
    """
    Transmit signal once using USRP with GNU Radio (single-shot mode)
    
    Args:
        modulated_signal: Complex IQ samples to transmit
        usrp_args: USRP device arguments
        center_freq: Center frequency in Hz
        samp_rate: Sample rate in Hz
        gain: Transmit gain
        antenna: Antenna port
        verbose: Print debug information
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if verbose:
            print("Setting up single-shot USRP transmission...")
        
        # Create and start the single-shot transmitter
        transmitter = USRPSingleShotTransmitter(
            modulated_signal, usrp_args, center_freq, 
            samp_rate, gain, antenna
        )
        
        if verbose:
            print(f"Transmitting {len(modulated_signal)} samples...")
        
        transmitter.start()
        
        # Calculate transmission time and wait for completion
        transmission_time = len(modulated_signal) / samp_rate
        buffer_time = 0.1  # Reduced buffer time for faster operation
        total_time = transmission_time + buffer_time
        
        if verbose:
            print(f"Transmission duration: {transmission_time:.3f}s + {buffer_time}s buffer")
        
        # Wait for transmission to complete
        time.sleep(total_time)
        
        if verbose:
            print("Stopping transmission...")
        transmitter.stop()
        transmitter.wait()
        
        if verbose:
            print("Single-shot transmission completed")
        
        return True
        
    except Exception as e:
        print(f"Error in tx_single_shot: {e}")
        import traceback
        traceback.print_exc()
        return False
