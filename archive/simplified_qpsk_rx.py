#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Simplified QPSK Receiver using GNU Radio
# Based on the original gnuradio_rx.py but with simplified structure

import numpy as np
import matplotlib.pyplot as plt
from gnuradio import gr, blocks, digital, analog, filter, uhd
from gnuradio.filter import firdes
import time
import threading
import signal
import sys
import math


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


def plot_constellation_live(receiver, update_interval=1.0):
    """Plot constellation diagram with live updates using matplotlib"""
    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Setup plot
    ax.set_xlabel('In-Phase')
    ax.set_ylabel('Quadrature')
    ax.set_title('Live QPSK Constellation')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-2, 2)
    ax.set_ylim(-2, 2)
    ax.set_aspect('equal')
    
    # Add ideal constellation points
    ideal_points = np.array([-1-1j, -1+1j, 1+1j, 1-1j])
    ax.scatter(ideal_points.real, ideal_points.imag, 
               color='red', s=100, marker='x', linewidth=3, 
               label='Ideal QPSK Points', zorder=5)
    ax.legend()
    
    # Initialize scatter plot
    scatter = ax.scatter([], [], alpha=0.6, s=1, color='blue', label='Received')
    
    plt.tight_layout()
    plt.show(block=False)
    
    print("Starting live constellation display...")
    print("Close the plot window or press Ctrl+C to stop.")
    
    last_data_len = 0
    no_signal_count = 0
    
    try:
        while True:
            # Get latest constellation data
            constellation_data = receiver.get_constellation_data()
            
            # Get signal power for detection
            signal_power = receiver.get_signal_power()
            power_db = 10 * np.log10(signal_power + 1e-10)  # Convert to dB, avoid log(0)
            
            if len(constellation_data) > 0 and power_db > -60:  # Signal threshold in dB
                # Filter out data that might be noise (points too far from ideal constellation)
                filtered_data = filter_constellation_data(constellation_data)
                
                # Check if we have valid signal or just noise
                if len(filtered_data) > 10:  # Minimum number of valid points
                    # Take the most recent data points for display (limit to avoid overcrowding)
                    display_data = filtered_data[-1000:] if len(filtered_data) > 1000 else filtered_data
                    
                    # Update scatter plot with latest data
                    scatter.set_offsets(np.column_stack([display_data.real, display_data.imag]))
                    
                    # Update title with data count and power
                    ax.set_title(f'Live QPSK Constellation ({len(display_data)} points, {power_db:.1f} dB)')
                    
                    no_signal_count = 0  # Reset no signal counter
                else:
                    # Likely noise, increment counter
                    no_signal_count += 1
                    if no_signal_count > 3:  # Clear display after 3 consecutive noise readings
                        scatter.set_offsets(np.empty((0, 2)))
                        ax.set_title(f'Live QPSK Constellation (Noise Only, {power_db:.1f} dB)')
                
                # Refresh the plot
                fig.canvas.draw()
                fig.canvas.flush_events()
                
                # Reset data sink more frequently to avoid accumulating noise
                if len(constellation_data) > last_data_len + 200:
                    receiver.reset_data_sink()
                    last_data_len = 0
                else:
                    last_data_len = len(constellation_data)
            else:
                # No signal or very weak signal
                no_signal_count += 1
                if no_signal_count > 2:
                    scatter.set_offsets(np.empty((0, 2)))
                    ax.set_title(f'Live QPSK Constellation (No Signal, {power_db:.1f} dB)')
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                    receiver.reset_data_sink()  # Clear accumulated noise
            
            time.sleep(update_interval)
            
    except KeyboardInterrupt:
        print("\nStopping constellation display...")
    except Exception as e:
        print(f"Plot error: {e}")
    finally:
        plt.close(fig)


def filter_constellation_data(constellation_data, max_distance=1.5):
    """Filter out constellation points that are too far from ideal QPSK points (likely noise)"""
    if len(constellation_data) == 0:
        return constellation_data
    
    # Ideal QPSK constellation points
    ideal_points = np.array([-1-1j, -1+1j, 1+1j, 1-1j])
    
    # Calculate distances from each received point to nearest ideal point
    filtered_points = []
    for point in constellation_data:
        distances = np.abs(point - ideal_points)
        min_distance = np.min(distances)
        
        # Only keep points that are reasonably close to ideal constellation
        if min_distance < max_distance:
            filtered_points.append(point)
    
    return np.array(filtered_points)


class SimplifiedQPSKReceiver(gr.top_block):
    """Simplified QPSK Receiver Flow Graph"""
    
    def __init__(self):
        gr.top_block.__init__(self, "Simplified QPSK Receiver")
        
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
        
        # Setup blocks
        self.setup_blocks()
        self.connect_blocks()
        
        # Data collection
        self.constellation_data = []
        self.collect_data = True
        
    def setup_blocks(self):
        """Setup all GNU Radio blocks"""
        
        # USRP Source
        self.usrp_source = setup_usrp(self.samp_rate, self.center_freq, self.gain)
        
        # AGC
        self.agc = analog.agc_cc(1e-4, 1.0, 1.0)
        
        # FLL Band Edge
        self.fll_band_edge = digital.fll_band_edge_cc(
            self.sps, self.alpha, (self.sps * 2 + 1), 
            (2 * math.pi / self.sps / 100 / self.sps)
        )
        
        # Skip initial samples
        self.skiphead = blocks.skiphead(gr.sizeof_gr_complex * 1, int(self.samp_rate))
        
        # Symbol Synchronization
        self.symbol_sync = digital.symbol_sync_cc(
            digital.TED_SIGNAL_TIMES_SLOPE_ML,
            self.sps,
            0.045,
            1.0,
            1.0,
            0.1,
            1,
            self.constellation,
            digital.IR_PFB_MF,
            self.nfilts,
            self.rrc_taps
        )
        
        # Constellation Receiver
        self.constellation_receiver = digital.constellation_receiver_cb(
            self.constellation,
            (2 * math.pi / 100),
            (-math.pi),
            math.pi
        )
        
        # Differential Decoder
        self.diff_decoder = digital.diff_decoder_bb(
            self.constellation.arity(),
            digital.DIFF_DIFFERENTIAL
        )
        
        # Data sink for constellation visualization
        self.vector_sink = blocks.vector_sink_c()
        
        # Add power measurement for signal detection
        self.power_probe = blocks.probe_signal_f()
        self.complex_to_mag_squared = blocks.complex_to_mag_squared()
        self.moving_average = blocks.moving_average_ff(int(self.samp_rate/100), 1.0/int(self.samp_rate/100), 4000)
        
        # Null sinks for unused outputs
        self.null_sink1 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink2 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink3 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink4 = blocks.null_sink(gr.sizeof_float * 1)
        self.null_sink5 = blocks.null_sink(gr.sizeof_char * 1)  # For diff_decoder output
    
    def connect_blocks(self):
        """Connect all blocks in the flow graph"""
        
        # Main signal path
        self.connect((self.usrp_source, 0), (self.agc, 0))
        self.connect((self.agc, 0), (self.fll_band_edge, 0))
        self.connect((self.fll_band_edge, 0), (self.skiphead, 0))
        self.connect((self.skiphead, 0), (self.symbol_sync, 0))
        self.connect((self.symbol_sync, 0), (self.constellation_receiver, 0))
        self.connect((self.constellation_receiver, 0), (self.diff_decoder, 0))
        
        # Constellation data collection - use the constellation receiver output (port 4)
        # This gives us the properly demodulated constellation points
        self.connect((self.constellation_receiver, 4), (self.vector_sink, 0))
        
        # Power measurement for signal detection
        self.connect((self.fll_band_edge, 0), (self.complex_to_mag_squared, 0))
        self.connect((self.complex_to_mag_squared, 0), (self.moving_average, 0))
        self.connect((self.moving_average, 0), (self.power_probe, 0))
        
        # Connect unused outputs to null sinks
        self.connect((self.symbol_sync, 1), (self.null_sink1, 0))
        self.connect((self.constellation_receiver, 1), (self.null_sink2, 0))
        self.connect((self.constellation_receiver, 2), (self.null_sink3, 0))
        self.connect((self.constellation_receiver, 3), (self.null_sink4, 0))
        self.connect((self.diff_decoder, 0), (self.null_sink5, 0))
    
    def get_constellation_data(self):
        """Get constellation data for plotting"""
        return np.array(self.vector_sink.data())
    
    def get_signal_power(self):
        """Get current signal power level"""
        return self.power_probe.level()
    
    def reset_data_sink(self):
        """Reset the vector sink to collect fresh data"""
        try:
            self.vector_sink.reset()
        except:
            # If reset doesn't work, we'll just work with accumulated data
            pass


def start_live_constellation_display(receiver, update_interval=1.0):
    """Start live constellation display in a separate thread"""
    display_thread = threading.Thread(
        target=plot_constellation_live, 
        args=(receiver, update_interval)
    )
    display_thread.daemon = True
    display_thread.start()
    return display_thread


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\nShutting down gracefully...')
    plt.close('all')  # Close all matplotlib windows
    sys.exit(0)


def main():
    """Main function"""
    print("Starting Simplified QPSK Receiver...")
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create receiver
        receiver = SimplifiedQPSKReceiver()
        
        print("Starting receiver...")
        receiver.start()
        
        # Wait a moment for the receiver to initialize
        time.sleep(2)
        
        # Start live constellation display
        display_thread = start_live_constellation_display(receiver, update_interval=0.5)
        
        print("Receiver running with live constellation display.")
        print("Close the plot window or press Ctrl+C to stop.")
        
        # Keep the main thread running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping receiver...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            receiver.stop()
            receiver.wait()
        except:
            pass
        print("Receiver stopped.")


if __name__ == '__main__':
    main()
