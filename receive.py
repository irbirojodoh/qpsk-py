#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QPSK Receiver Application
"""

import sys
import time
import signal
import argparse
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.receiver.receiver import PacketQPSKReceiver
from src.receiver.display import start_terminal_display, start_live_plot_display
from src.common import (
    DEFAULT_SAMP_RATE, DEFAULT_CENTER_FREQ, DEFAULT_GAIN, 
    DEFAULT_USRP_RX_ADDR, DEFAULT_ANTENNA
)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\nShutting down gracefully...')
    sys.exit(0)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='QPSK Packet Receiver')
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug mode for verbose output')
    parser.add_argument('--plot', action='store_true', 
                       help='Enable live plotting (constellation, time/freq domain)')
    parser.add_argument('--terminal-only', action='store_true', 
                       help='Use terminal display only (no plots)')
    parser.add_argument('--update-rate', type=float, default=0.2,
                       help='Plot update rate in seconds (default: 0.2)')
    parser.add_argument('--plot-blocking', action='store_true',
                       help='Make plot window block main thread (closes receiver when window closes)')
    
    args = parser.parse_args()
    
    # Set debug mode
    DEBUG_MODE = args.debug
    
    # Configuration parameters
    samp_rate = DEFAULT_SAMP_RATE
    center_freq = DEFAULT_CENTER_FREQ
    gain = DEFAULT_GAIN
    usrp_addr = DEFAULT_USRP_RX_ADDR
    antenna = DEFAULT_ANTENNA
    
    print("=" * 60)
    print("PACKET-BASED QPSK RECEIVER WITH HAMMING CODE")
    print("=" * 60)
    print("Features:")
    print("- Terminal-based packet display")
    print("- Packet decoding with error correction")
    print("- Live display of received messages")
    print("- Hamming(7,4) error correction")
    print("- Automatic signal detection and recovery")
    if args.plot and not args.terminal_only:
        print("- Live constellation and signal visualization")
    if DEBUG_MODE:
        print("- DEBUG MODE: Full diagnostic output enabled")
    else:
        print("- NORMAL MODE: Clean message display only")
    print("=" * 60)
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create receiver with debug flag and configuration
        receiver = PacketQPSKReceiver(
            debug=DEBUG_MODE,
            samp_rate=samp_rate,
            center_freq=center_freq,
            gain=gain,
            usrp_addr=usrp_addr,
            antenna=antenna
        )
        
        if DEBUG_MODE:
            receiver.print_config()
        
        print("Starting packet receiver...")
        receiver.start()
        
        # Wait a moment for the receiver to initialize
        time.sleep(2)
        
        # Start appropriate display
        if args.plot and not args.terminal_only:
            print("Starting live plotting display...")
            
            # Start terminal display in background thread
            terminal_display = start_terminal_display(receiver, update_interval=0.5)
            
            # Create plot display
            plot_display = start_live_plot_display(receiver, update_interval=args.update_rate)
            
            if args.plot_blocking:
                print("Starting plots in blocking mode...")
                print("Close the plot window to stop the receiver.")
                # This will block in the main thread until window is closed
                plot_display.start()
            else:
                print("Starting plots in non-blocking mode...")
                print("Press Ctrl+C to stop the receiver.")
                # Start plots without blocking
                if plot_display.start_non_blocking():
                    # Keep the main thread running
                    try:
                        while True:
                            time.sleep(0.1)
                            # Check if plot window is still open
                            if not plot_display.running:
                                break
                    except KeyboardInterrupt:
                        pass
                else:
                    print("Failed to start plot display, continuing with terminal only")
                    # Keep the main thread running for terminal-only mode
                    while True:
                        time.sleep(1)
            
        else:
            # Start terminal display only
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
            
            # Keep the main thread running for terminal-only mode
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
