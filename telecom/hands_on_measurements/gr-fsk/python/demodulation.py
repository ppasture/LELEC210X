#!/usr/bin/env python
#
# Copyright 2021 UCLouvain.
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

from distutils.version import LooseVersion

import numpy as np
from gnuradio import gr


def demodulate(y, B, R, Fdev):
    """
    Non-coherent demodulator.
    
    Args:
        y: The received signal (array of complex samples).
        B: Bit rate (symbol rate).
        R: Oversampling rate (samples per symbol).
        Fdev: Frequency deviation of the modulated signal.
    
    Returns:
        bits_hat: The estimated bits after demodulation.
    """
    # Compute the number of symbols
    nb_syms = int(len(y) // R)
    
    # Reshape the signal into symbols, each symbol is a row of R samples
    y = np.resize(y, (nb_syms, R))
    
    # Symbol duration in time
    T = 1 / B

    # Initialize the array for the demodulated bits
    bits_hat = np.zeros(nb_syms, dtype=int)

    # Loop over each symbol and compute correlation with reference waveforms
    for k in range(nb_syms):
        # Get samples for the current symbol
        symbol_samples = y[k]


class demodulation(gr.basic_block):
    """
    docstring for block demodulation
    """

    def __init__(self, drate, fdev, fsamp, payload_len, crc_len):
        self.drate = drate
        self.fdev = fdev
        self.fsamp = fsamp
        self.frame_len = payload_len + crc_len
        self.osr = int(fsamp / drate)

        gr.basic_block.__init__(
            self, name="Demodulation", in_sig=[np.complex64], out_sig=[np.uint8]
        )

        self.gr_version = gr.version()

        # Redefine function based on version
        if LooseVersion(self.gr_version) < LooseVersion("3.9.0"):
            print("Compiling the Python codes for GNU Radio 3.8")
            self.forecast = self.forecast_v38
        else:
            print("Compiling the Python codes for GNU Radio 3.10")
            self.forecast = self.forecast_v310

    def forecast_v38(self, noutput_items, ninput_items_required):
        """
        input items are samples (with oversampling factor)
        output items are bytes
        """
        ninput_items_required[0] = noutput_items * self.osr * 8

    def forecast_v310(self, noutput_items, ninputs):
        """
        forecast is only called from a general block
        this is the default implementation
        """
        ninput_items_required = [0] * ninputs
        for i in range(ninputs):
            ninput_items_required[i] = noutput_items * self.osr * 8

        return ninput_items_required

    def symbols_to_bytes(self, symbols):
        """
        Converts symbols (bits here) to bytes
        """
        if len(symbols) == 0:
            return []

        n_bytes = int(len(symbols) / 8)
        bitlists = np.array_split(symbols, n_bytes)
        out = np.zeros(n_bytes).astype(np.uint8)

        for i, l in enumerate(bitlists):
            for bit in l:
                out[i] = (out[i] << 1) | bit

        return out

    def general_work(self, input_items, output_items):
        n_syms = len(output_items[0]) * 8
        buf_len = n_syms * self.osr

        y = input_items[0][:buf_len]
        self.consume_each(buf_len)

        s = demodulate(y, self.drate, self.osr, self.fdev)
        b = self.symbols_to_bytes(s)
        output_items[0][: len(b)] = b

        return len(b)
