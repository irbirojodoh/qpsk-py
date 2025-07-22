#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QPSK Transmitter Application
"""

import sys
import time
import signal
import threading
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.transmitter.modulator import create_packet_signal
from src.transmitter.transmitter import tx_worker
from src.common import (
    DEFAULT_SAMP_RATE, DEFAULT_CENTER_FREQ, DEFAULT_SPS, 
    DEFAULT_ALPHA, DEFAULT_GAIN, DEFAULT_USRP_TX_ADDR, DEFAULT_ANTENNA
)

# Global variables
stop_signal = threading.Event()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nStopping transmission...")
    stop_signal.set()

def main():
    """Main function"""
    
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Configuration parameters
    samp_rate = DEFAULT_SAMP_RATE
    center_freq = DEFAULT_CENTER_FREQ
    gain = DEFAULT_GAIN
    sps = DEFAULT_SPS
    alpha = DEFAULT_ALPHA
    usrp_addr = DEFAULT_USRP_TX_ADDR
    antenna = DEFAULT_ANTENNA
    message = "HELLO TX"  # Message to transmit
    
    print("=" * 60)
    print("PACKET-BASED QPSK TRANSMITTER WITH HAMMING CODE")
    print("=" * 60)
    print(f"Message: '{message}'")
    print(f"Sample Rate: {samp_rate/1e6:.1f} MHz")
    print(f"Center Frequency: {center_freq/1e9:.3f} GHz")
    print(f"Gain: {gain} dB")
    print(f"Samples per Symbol: {sps}")
    print(f"Excess Bandwidth: {alpha}")
    print(f"USRP Address: {usrp_addr}")
    print(f"Antenna: {antenna}")
    print("=" * 60)
    
    # Generate packet signal with error correction
    sequence_number = 0
    modulated_signal, packet_info = create_packet_signal(
        message, sequence_number, sps, alpha, samp_rate, verbose=True
    )
    
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
            'usrp_args': usrp_addr,
            'center_freq': center_freq,
            'samp_rate': samp_rate,
            'gain': gain,
            'antenna': antenna,
            'stop_event': stop_signal,
            'verbose': True
        }
    )
    
    tx_thread.daemon = True
    tx_thread.start()
    
    # Keep main thread alive
    try:
        print("\nTransmission started. Press Ctrl+C to stop.")
        while not stop_signal.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_signal.set()
    
    # Wait for transmission thread to finish
    tx_thread.join(timeout=5.0)
    print("Transmitter application finished")

if __name__ == '__main__':
    main()
