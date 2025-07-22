"""
Packet display utilities for receiver
"""

import time
import threading
import numpy as np
from collections import deque
import matplotlib
# Try different backends in order of preference
try:
    matplotlib.use('Qt5Agg')  # Try Qt5 first
except ImportError:
    try:
        matplotlib.use('TkAgg')  # Then Tk
    except ImportError:
        try:
            matplotlib.use('Agg')  # Fallback to non-interactive
            print("Warning: Using non-interactive matplotlib backend")
        except ImportError:
            print("Warning: No suitable matplotlib backend found")

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle

try:
    from scipy import signal as scipy_signal
    from scipy.fft import fft, fftfreq
except ImportError:
    # Fallback to numpy if scipy not available
    from numpy.fft import fft, fftfreq
    scipy_signal = None

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

def start_terminal_display(receiver, update_interval=0.5):
    """Start packet display in terminal in a separate thread"""
    display_thread = threading.Thread(
        target=display_packets_terminal, 
        args=(receiver, update_interval)
    )
    display_thread.daemon = True
    display_thread.start()
    return display_thread

class LivePlotDisplay:
    """Live plotting display for constellation, time domain, and frequency domain"""
    
    def __init__(self, receiver, update_interval=0.2):
        self.receiver = receiver
        self.update_interval = update_interval
        self.running = False
        
        # Data buffers
        self.constellation_data = []
        self.time_data = []
        self.freq_data = []
        self.time_axis = []
        self.freq_axis = []
        
        # Figure setup
        plt.style.use('dark_background')
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 10))
        self.fig.suptitle('QPSK Receiver - Live Signal Analysis', fontsize=14, color='white')
        
        # Constellation plot (top left)
        self.ax_const = self.axes[0, 0]
        self.ax_const.set_title('Constellation Diagram', color='white')
        self.ax_const.set_xlabel('In-Phase (I)', color='white')
        self.ax_const.set_ylabel('Quadrature (Q)', color='white')
        self.ax_const.grid(True, alpha=0.3)
        self.ax_const.set_xlim(-2, 2)
        self.ax_const.set_ylim(-2, 2)
        self.ax_const.set_aspect('equal')
        
        # Add reference circles and ideal constellation points
        circle1 = Circle((0, 0), 1.0, fill=False, color='gray', alpha=0.5, linestyle='--')
        circle2 = Circle((0, 0), 1.414, fill=False, color='gray', alpha=0.3, linestyle='--')
        self.ax_const.add_patch(circle1)
        self.ax_const.add_patch(circle2)
        
        # Ideal QPSK constellation points
        ideal_points = [-1-1j, -1+1j, 1+1j, 1-1j]
        for point in ideal_points:
            self.ax_const.plot(point.real, point.imag, 'ro', markersize=8, alpha=0.7)
        
        self.const_scatter = self.ax_const.scatter([], [], c='cyan', alpha=0.6, s=20)
        
        # Time domain plot (top right)
        self.ax_time = self.axes[0, 1]
        self.ax_time.set_title('Time Domain Signal', color='white')
        self.ax_time.set_xlabel('Time (samples)', color='white')
        self.ax_time.set_ylabel('Amplitude', color='white')
        self.ax_time.grid(True, alpha=0.3)
        
        self.line_time_i, = self.ax_time.plot([], [], 'c-', label='I component', alpha=0.8)
        self.line_time_q, = self.ax_time.plot([], [], 'm-', label='Q component', alpha=0.8)
        self.ax_time.legend()
        
        # Frequency domain plot (bottom left)
        self.ax_freq = self.axes[1, 0]
        self.ax_freq.set_title('Frequency Domain (FFT)', color='white')
        self.ax_freq.set_xlabel('Frequency (Hz)', color='white')
        self.ax_freq.set_ylabel('Power (dB)', color='white')
        self.ax_freq.grid(True, alpha=0.3)
        
        self.line_freq, = self.ax_freq.plot([], [], 'y-', alpha=0.8)
        
        # Signal statistics (bottom right)
        self.ax_stats = self.axes[1, 1]
        self.ax_stats.set_title('Signal Statistics', color='white')
        self.ax_stats.axis('off')
        
        self.stats_text = self.ax_stats.text(0.05, 0.95, '', transform=self.ax_stats.transAxes, 
                                           fontsize=10, verticalalignment='top', color='white',
                                           fontfamily='monospace')
        
        # Packet history display
        self.packet_history = deque(maxlen=10)
        self.packet_text = self.ax_stats.text(0.05, 0.5, '', transform=self.ax_stats.transAxes,
                                            fontsize=9, verticalalignment='top', color='lightgreen',
                                            fontfamily='monospace')
        
        # Tight layout
        plt.tight_layout()
        
        # Animation
        self.ani = None
    
    def update_plot(self, frame):
        """Update all plots with new data"""
        if not self.running:
            return []
        
        try:
            # Get constellation data
            constellation_data = self.receiver.get_constellation_data()
            if len(constellation_data) > 0:
                # Take recent data points
                recent_const = constellation_data[-500:] if len(constellation_data) > 500 else constellation_data
                if len(recent_const) > 0:
                    self.const_scatter.set_offsets(np.column_stack([recent_const.real, recent_const.imag]))
            
            # Get time domain data from symbol sync output
            time_data = self.receiver.get_symbol_sync_data()
            if len(time_data) > 0:
                # Take recent samples
                recent_time = time_data[-1000:] if len(time_data) > 1000 else time_data
                if len(recent_time) > 0:
                    time_samples = np.arange(len(recent_time))
                    i_component = np.real(recent_time)
                    q_component = np.imag(recent_time)
                    
                    self.line_time_i.set_data(time_samples, i_component)
                    self.line_time_q.set_data(time_samples, q_component)
                    
                    # Auto-scale time domain plot
                    if len(recent_time) > 1:
                        self.ax_time.set_xlim(0, len(recent_time))
                        y_min = min(np.min(i_component), np.min(q_component))
                        y_max = max(np.max(i_component), np.max(q_component))
                        margin = (y_max - y_min) * 0.1
                        self.ax_time.set_ylim(y_min - margin, y_max + margin)
                    
                    # Compute and display frequency domain
                    if len(recent_time) > 64:  # Need enough samples for meaningful FFT
                        # Apply window to reduce spectral leakage
                        if scipy_signal:
                            windowed_data = recent_time * scipy_signal.windows.hann(len(recent_time))
                        else:
                            # Simple hanning window implementation
                            n = len(recent_time)
                            window = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / (n - 1))
                            windowed_data = recent_time * window
                        
                        # Compute FFT
                        fft_data = fft(windowed_data)
                        fft_freqs = fftfreq(len(windowed_data), 1/self.receiver.samp_rate)
                        
                        # Convert to power spectrum in dB
                        power_spectrum = 20 * np.log10(np.abs(fft_data) + 1e-12)
                        
                        # Only plot positive frequencies
                        positive_freqs = fft_freqs[:len(fft_freqs)//2]
                        positive_power = power_spectrum[:len(power_spectrum)//2]
                        
                        self.line_freq.set_data(positive_freqs, positive_power)
                        
                        # Auto-scale frequency domain plot
                        if len(positive_freqs) > 1:
                            self.ax_freq.set_xlim(0, positive_freqs[-1])
                            self.ax_freq.set_ylim(np.min(positive_power), np.max(positive_power) + 5)
            
            # Update signal statistics
            self.update_statistics()
            
            # Update packet information
            self.update_packet_display()
            
        except Exception as e:
            if self.receiver.debug:
                print(f"Plot update error: {e}")
        
        return []
    
    def update_statistics(self):
        """Update signal statistics display"""
        try:
            # Get current signal power
            signal_power = self.receiver.get_signal_power()
            power_db = 10 * np.log10(signal_power + 1e-10)
            
            # Get symbol and bit data
            symbols = self.receiver.get_symbol_data()
            bits = list(self.receiver.vector_sink_bits.data()) if hasattr(self.receiver, 'vector_sink_bits') else []
            
            # Calculate rates
            symbol_rate = len(symbols) / max(1, time.time() - getattr(self, 'start_time', time.time()))
            bit_rate = len(bits) / max(1, time.time() - getattr(self, 'start_time', time.time()))
            expected_symbol_rate = self.receiver.samp_rate / self.receiver.sps
            
            # Get constellation data for EVM calculation
            constellation_data = self.receiver.get_constellation_data()
            evm_rms = 0.0
            snr_est = 0.0
            
            if len(constellation_data) > 10:
                recent_const = constellation_data[-100:] if len(constellation_data) > 100 else constellation_data
                
                # Calculate EVM (Error Vector Magnitude)
                ideal_points = np.array([-1-1j, -1+1j, 1+1j, 1-1j])
                
                # Find closest ideal point for each received point
                errors = []
                for point in recent_const:
                    distances = np.abs(point - ideal_points)
                    closest_ideal = ideal_points[np.argmin(distances)]
                    error = np.abs(point - closest_ideal)
                    errors.append(error)
                
                if errors:
                    evm_rms = np.sqrt(np.mean(np.array(errors)**2)) * 100  # Convert to percentage
                    
                    # Estimate SNR from constellation
                    signal_power_est = np.mean(np.abs(recent_const)**2)
                    noise_power_est = np.mean(np.array(errors)**2)
                    if noise_power_est > 1e-12:
                        snr_est = 10 * np.log10(signal_power_est / noise_power_est)
            
            # Symbol distribution
            symbol_dist = [0, 0, 0, 0]
            if len(symbols) > 0:
                recent_symbols = symbols[-100:] if len(symbols) > 100 else symbols
                for i in range(4):
                    symbol_dist[i] = recent_symbols.count(i)
            
            # Format statistics text
            stats_text = f"""SIGNAL STATISTICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Power Level: {power_db:6.1f} dB
Symbol Rate: {symbol_rate:6.1f} sym/s
Expected:    {expected_symbol_rate:6.1f} sym/s
Bit Rate:    {bit_rate:6.1f} bits/s

QUALITY METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVM RMS:     {evm_rms:6.1f} %
SNR Est:     {snr_est:6.1f} dB

SYMBOL DISTRIBUTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sym 0: {symbol_dist[0]:4d}  Sym 1: {symbol_dist[1]:4d}
Sym 2: {symbol_dist[2]:4d}  Sym 3: {symbol_dist[3]:4d}

DATA COUNTERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Symbols: {len(symbols):6d}
Total Bits:    {len(bits):6d}"""
            
            self.stats_text.set_text(stats_text)
            
        except Exception as e:
            if self.receiver.debug:
                print(f"Statistics update error: {e}")
    
    def update_packet_display(self):
        """Update packet display"""
        try:
            # Check for new packets
            latest_packet = self.receiver.get_latest_packet()
            if latest_packet is not None:
                self.packet_history.append(latest_packet)
            
            # Format packet history
            if self.packet_history:
                packet_text = "RECENT PACKETS\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                
                for i, pkt in enumerate(list(self.packet_history)[-5:]):  # Show last 5
                    current_time = time.strftime("%H:%M:%S", time.localtime())
                    try:
                        msg = pkt['payload'].decode('utf-8', errors='replace')
                        msg_display = msg[:25] + "..." if len(msg) > 25 else msg
                    except:
                        msg_display = f"[Binary: {len(pkt['payload'])} bytes]"
                    
                    packet_text += f"#{pkt['packet_number']:2d}: {msg_display}\n"
                    packet_text += f"     SEQ={pkt['sequence_number']:3d} ERR(H={pkt['header_errors']},P={pkt['payload_errors']})\n"
                
                total_packets = len(self.packet_history)
                total_errors = sum(pkt['header_errors'] + pkt['payload_errors'] for pkt in self.packet_history)
                
                packet_text += f"\nTotal Packets: {total_packets}"
                packet_text += f"\nTotal Errors:  {total_errors}"
            else:
                packet_text = "RECENT PACKETS\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nWaiting for packets..."
            
            self.packet_text.set_text(packet_text)
            
        except Exception as e:
            if self.receiver.debug:
                print(f"Packet display update error: {e}")
    
    def start(self):
        """Start the live plotting"""
        self.running = True
        self.start_time = time.time()
        
        try:
            # Create animation
            self.ani = animation.FuncAnimation(
                self.fig, self.update_plot, 
                interval=int(self.update_interval * 1000),  # Convert to milliseconds
                blit=False, cache_frame_data=False
            )
            
            # Show the plot and start event loop
            plt.show(block=True)
            
        except Exception as e:
            print(f"Error starting plot display: {e}")
            print("Falling back to terminal-only mode")
            # Don't raise exception, just continue without plots
        finally:
            self.running = False
    
    def start_non_blocking(self):
        """Start the live plotting without blocking"""
        self.running = True
        self.start_time = time.time()
        
        try:
            # Create animation
            self.ani = animation.FuncAnimation(
                self.fig, self.update_plot, 
                interval=int(self.update_interval * 1000),  # Convert to milliseconds
                blit=False, cache_frame_data=False
            )
            
            # Show the plot without blocking
            plt.show(block=False)
            plt.draw()
            
            return True
            
        except Exception as e:
            print(f"Error starting plot display: {e}")
            self.running = False
            return False
    
    def stop(self):
        """Stop the live plotting"""
        self.running = False
        if self.ani:
            self.ani.event_source.stop()
        try:
            plt.close(self.fig)
        except:
            pass

def start_live_plot_display(receiver, update_interval=0.2):
    """Start live plotting display - must be called from main thread"""
    display = LivePlotDisplay(receiver, update_interval)
    return display  # Return display object so caller can start it
