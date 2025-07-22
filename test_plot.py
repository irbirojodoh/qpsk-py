#!/usr/bin/env python3
"""
Test script for matplotlib plotting without USRP hardware
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.receiver.display import LivePlotDisplay

class MockReceiver:
    """Mock receiver for testing plots"""
    
    def __init__(self):
        self.debug = True
        self.samp_rate = 1e6
        self.sps = 16
        self.packet_counter = 0
        self.latest_packet = None
        
        # Generate some test data
        self.generate_test_data()
    
    def generate_test_data(self):
        """Generate synthetic QPSK-like data for testing"""
        # Create constellation points with some noise
        ideal_points = np.array([-1-1j, -1+1j, 1+1j, 1-1j])
        
        # Generate constellation data
        n_points = 1000
        symbol_indices = np.random.randint(0, 4, n_points)
        self.constellation_data = ideal_points[symbol_indices] + 0.1 * (np.random.randn(n_points) + 1j * np.random.randn(n_points))
        
        # Generate time domain data
        n_samples = 2048
        t = np.arange(n_samples)
        # Simulate QPSK signal with some filtering
        symbols_time = np.repeat(ideal_points[np.random.randint(0, 4, n_samples//16)], 16)[:n_samples]
        noise = 0.1 * (np.random.randn(n_samples) + 1j * np.random.randn(n_samples))
        self.time_data = symbols_time + noise
        
        # Generate symbol and bit data
        self.symbol_data = np.random.randint(0, 4, 100).tolist()
        self.bit_data = np.random.randint(0, 2, 200)
    
    def get_constellation_data(self):
        # Add some new random points to simulate live data
        new_points = np.random.choice([-1-1j, -1+1j, 1+1j, 1-1j], 10)
        noise = 0.1 * (np.random.randn(10) + 1j * np.random.randn(10))
        new_data = new_points + noise
        
        # Keep only recent data
        self.constellation_data = np.concatenate([self.constellation_data[-490:], new_data])
        return self.constellation_data
    
    def get_symbol_sync_data(self):
        # Update time data slightly
        n_new = 48  # Use consistent size
        # Generate new symbols that align with the sample size
        n_symbols = n_new // 16
        if n_symbols == 0:
            n_symbols = 1
        new_symbols = np.repeat(np.random.choice([-1-1j, -1+1j, 1+1j, 1-1j], n_symbols), 16)[:n_new]
        new_noise = 0.1 * (np.random.randn(n_new) + 1j * np.random.randn(n_new))
        new_data = new_symbols + new_noise
        
        # Ensure we maintain consistent array size
        self.time_data = np.concatenate([self.time_data[-(2048-n_new):], new_data])
        return self.time_data.tolist()
    
    def get_symbol_data(self):
        # Add some new symbols
        new_symbols = np.random.randint(0, 4, 5).tolist()
        self.symbol_data.extend(new_symbols)
        return self.symbol_data[-100:]  # Keep only recent
    
    def get_signal_power(self):
        return np.random.uniform(1e-6, 1e-4)  # Simulate varying power
    
    def get_latest_packet(self):
        # Simulate occasional packets
        if np.random.random() < 0.1:  # 10% chance of new packet
            self.packet_counter += 1
            packet = {
                'packet_number': self.packet_counter,
                'sequence_number': self.packet_counter % 256,
                'payload_length': 20,
                'payload': f"Test message {self.packet_counter}".encode(),
                'header_errors': np.random.randint(0, 2),
                'payload_errors': np.random.randint(0, 3),
                'total_packet_bits': 200
            }
            return packet
        return None
    
    # Mock the vector_sink_bits attribute
    class MockVectorSink:
        def data(self):
            return np.random.randint(0, 2, 500).tolist()
    
    def __getattr__(self, name):
        if name == 'vector_sink_bits':
            return self.MockVectorSink()
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

def main():
    print("Testing matplotlib plotting with mock QPSK data...")
    print("This will open a plot window with synthetic data.")
    print("Close the window to exit.")
    
    try:
        # Create mock receiver
        receiver = MockReceiver()
        
        # Create and start display
        display = LivePlotDisplay(receiver, update_interval=0.2)
        display.start()
        
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
