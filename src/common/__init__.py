"""
Common utilities and shared components for QPSK communication system
"""

import numpy as np
from gnuradio import digital
from gnuradio.filter import firdes

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

# System parameters
DEFAULT_SAMP_RATE = 1e6
DEFAULT_CENTER_FREQ = 5e9
DEFAULT_SPS = 16
DEFAULT_ALPHA = 0.50
DEFAULT_NFILTS = 32
DEFAULT_GAIN = 20
DEFAULT_USRP_TX_ADDR = "addr=192.168.10.81"
DEFAULT_USRP_RX_ADDR = "addr=192.168.10.16"
DEFAULT_ANTENNA = "J2"
