import os
import pickle
from pathlib import Path
from collections.abc import Iterator
from typing import Optional

import click
import serial
import zmq
import numpy as np
import requests
import json
import common
from auth import PRINT_PREFIX
from common.env import load_dotenv
from common.logging import logger
from .utils import payload_to_melvecs
import sys

sys.path.append(os.path.abspath("auth/src"))

from auth import packet
load_dotenv()

# Server details
hostname = "http://lelec210x.sipr.ucl.ac.be"
key = "jNvyuAfUUwf3iZAWF40sqSuW3DHRkjTj8jwDb0-d"

# Categories mapping
categories = ["chainsaw", "fire", "fireworks", "gunshot"]

# Create output directory
output_dir = Path("melvecs")
output_dir.mkdir(parents=True, exist_ok=True)

def parse_packet(line: str) -> Optional[bytes]:
    """Parse a line into a packet."""
    line = line.strip()
    if line.startswith(PRINT_PREFIX):
        return bytes.fromhex(line[len(PRINT_PREFIX):])
    return None

def hex_to_bytes(ctx: click.Context, param: click.Parameter, value: str) -> bytes:
    """Convert a hex string into bytes."""
    return bytes.fromhex(value)

@click.command()
@click.option(
    "-i", "--input", "_input",
    default=None, type=click.File("r"),
    help="Where to read the input stream. If not specified, read from TCP address."
)
@click.option(
    "-o", "--output",
    default="-", type=click.File("w"),
    help="Where to write the output stream. Default to stdout."
)
@click.option(
    "--serial-port",
    default=None, envvar="SERIAL_PORT", show_envvar=True,
    help="If specified, read the packet from the given serial port."
)
@click.option(
    "--tcp-address",
    default="tcp://127.0.0.1:10000", envvar="TCP_ADDRESS",
    show_default=True, show_envvar=True,
    help="TCP address to be used to read the input stream."
)
@click.option(
    "-k", "--auth-key",
    default=16 * "00", envvar="AUTH_KEY", callback=hex_to_bytes,
    show_default=True, show_envvar=True,
    help="Authentication key (hex string)."
)
@click.option(
    "--authenticate/--no-authenticate",
    default=True, is_flag=True,
    help="Enable / disable authentication."
)
@common.click.melvec_length
@common.click.n_melvecs
@common.click.verbosity
def main(
    _input: Optional[click.File],
    output: click.File,
    serial_port: Optional[str],
    tcp_address: str,
    auth_key: bytes,
    authenticate: bool,
    melvec_length: int,
    n_melvecs: int,
) -> None:
    """
    Parse packets from the MCU, perform authentication, and classify MELVECs contained in payloads.
    """
    logger.debug(f"Unwrapping packets with auth. key: {auth_key.hex()}")

    unwrapper = packet.PacketUnwrapper(
        key=auth_key,
        allowed_senders=[0],
        authenticate=authenticate,
    )

    def reader() -> Iterator[str]:
        """Reads packets from serial port, input file, or TCP stream."""
        if serial_port:
            ser = serial.Serial(port=serial_port, baudrate=115200)
            ser.reset_input_buffer()
            ser.read_until(b"\n")
            logger.debug(f"Reading packets from serial port: {serial_port}")
            while True:
                line = ser.read_until(b"\n").decode("ascii").strip()
                packet_data = parse_packet(line)
                if packet_data:
                    yield packet_data
        elif _input:
            logger.debug(f"Reading packets from input: {_input!s}")
            for line in _input:
                packet_data = parse_packet(line)
                if packet_data:
                    yield packet_data
        else:
            context = zmq.Context()
            socket = context.socket(zmq.SUB)
            socket.setsockopt(zmq.SUBSCRIBE, b"")
            socket.setsockopt(zmq.CONFLATE, 1)
            socket.connect(tcp_address)
            logger.debug(f"Reading packets from TCP address: {tcp_address}")
            while True:
                yield socket.recv(2 * melvec_length * n_melvecs)

    input_stream = reader()

    # Load the model

    x = 0
    for msg in input_stream:
        try:
            x += 1
            sender, payload = unwrapper.unwrap_packet(msg)
            logger.debug(f"From {sender}, received packet: {payload.hex()}")
            print("Received packet:")
            print(payload.hex())

            output.write(PRINT_PREFIX + payload.hex() + "\n")
            output.flush()

            # Convert payload to MELVECs
            melvecs = payload_to_melvecs(payload.hex(), melvec_length, n_melvecs)
            logger.info(f"Parsed payload into Mel vectors: {melvecs}")

            # Determine category based on `x`
            category_index = (x - 1) // 40  # 40 per category
            if category_index < len(categories):
                category = categories[category_index]
                filename = f"{category}_{(x - 1) % 40:02d}.npy"
                filepath = output_dir / filename
                np.save(filepath, melvecs)
                logger.info(f"✅ Saved MELVEC: {filepath}")


        except packet.InvalidPacket as e:
            logger.error(f"❌ Invalid packet error: {e.args[0]}")
        except Exception as e:
            logger.exception(f"❌ Unexpected error while processing packet: {e}")
