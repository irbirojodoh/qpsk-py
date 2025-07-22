"""
USRP hardware configuration and setup utilities
"""

from gnuradio import uhd

def setup_usrp_source(samp_rate, center_freq, gain, usrp_addr="addr=192.168.10.16", antenna="J2"):
    """Setup USRP source for receiving"""
    usrp_source = uhd.usrp_source(
        ",".join((usrp_addr, '')),
        uhd.stream_args(
            cpu_format="fc32",
            args='',
            channels=list(range(0, 1)),
        ),
    )
    usrp_source.set_samp_rate(samp_rate)
    usrp_source.set_center_freq(center_freq, 0)
    usrp_source.set_antenna(antenna, 0)
    usrp_source.set_bandwidth(20e6, 0)
    usrp_source.set_rx_agc(False, 0)
    usrp_source.set_gain(gain, 0)
    return usrp_source

def setup_usrp_sink(samp_rate, center_freq, gain, usrp_addr="addr=192.168.10.81", antenna="J2"):
    """Setup USRP sink for transmitting"""
    usrp_sink = uhd.usrp_sink(
        usrp_addr,
        uhd.stream_args(
            cpu_format="fc32",
            args='',
            channels=list(range(0, 1)),
        ),
        "",
    )
    usrp_sink.set_samp_rate(samp_rate)
    usrp_sink.set_center_freq(center_freq, 0)
    usrp_sink.set_antenna(antenna, 0)
    usrp_sink.set_bandwidth(20e6, 0)
    usrp_sink.set_gain(gain, 0)
    return usrp_sink

def print_usrp_info(usrp, device_type="USRP"):
    """Print USRP device information"""
    try:
        print(f"{device_type} Device Information:")
        print(f"  Sample Rate: {usrp.get_samp_rate()/1e6:.1f} MHz")
        print(f"  Center Frequency: {usrp.get_center_freq()/1e9:.3f} GHz")
        print(f"  Gain: {usrp.get_gain()} dB")
        print(f"  Antenna: {usrp.get_antenna()}")
        print(f"  Bandwidth: {usrp.get_bandwidth()/1e6:.1f} MHz")
    except Exception as e:
        print(f"Error getting {device_type} info: {e}")
