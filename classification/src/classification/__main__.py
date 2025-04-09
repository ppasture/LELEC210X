import os
import pickle
from pathlib import Path
from collections.abc import Iterator
from typing import Optional
from classification.utils.plots import plot_specgram
import matplotlib.pyplot as plt
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
hostname = "http://lelec210x.sipr.ucl.ac.be"
key = "jNvyuAfUUwf3iZAWF40sqSuW3DHRkjTj8jwDb0-d"
from .utils import payload_to_melvecs
import sys
import os

sys.path.append(os.path.abspath("auth/src"))

from auth import packet
load_dotenv()

def parse_packet(line: str) -> Optional[bytes]:
    """Parse a line into a packet."""
    line = line.strip()
    if line.startswith(PRINT_PREFIX):
        return bytes.fromhex(line[len(PRINT_PREFIX) :])
    return None

def hex_to_bytes(ctx: click.Context, param: click.Parameter, value: str) -> bytes:
    """Convert a hex string into bytes."""
    return bytes.fromhex(value)

@click.command()
@click.option(
    "-i",
    "--input",
    "_input",
    default=None,
    type=click.File("r"),
    help="Where to read the input stream. If not specified, read from TCP address. You can pass '-' to read from stdin.",
)
@click.option(
    "-o",
    "--output",
    default="-",
    type=click.File("w"),
    help="Where to write the output stream. Default to '-', a.k.a. stdout.",
)
@click.option(
    "--serial-port",
    default=None,
    envvar="SERIAL_PORT",
    show_envvar=True,
    help="If specified, read the packet from the given serial port. E.g., '/dev/tty0'. This takes precedence over `--input` and `--tcp-address` options.",
)
@click.option(
    "--tcp-address",
    default="tcp://127.0.0.1:10000",
    envvar="TCP_ADDRESS",
    show_default=True,
    show_envvar=True,
    help="TCP address to be used to read the input stream.",
)
@click.option(
    "-k",
    "--auth-key",
    default=16 * "00",
    envvar="AUTH_KEY",
    callback=hex_to_bytes,
    show_default=True,
    show_envvar=True,
    help="Authentication key (hex string).",
)
@click.option(
    "--authenticate/--no-authenticate",
    default=True,
    is_flag=True,
    help="Enable / disable authentication, useful for skipping authentication step.",
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
                yield socket.recv(1 * melvec_length * n_melvecs)

    # Load model
    pca_path = Path("classification/data/models/pca.pickle")
    rf_model_path = Path("classification/data/models/mod_pca.pickle")
    with pca_path.open("rb") as pca_file:
        pca = pickle.load(pca_file)

    with rf_model_path.open("rb") as rf_file:
        model_rf = pickle.load(rf_file)

    input_stream = reader()

    for msg in input_stream:
        try:
            sender, payload, shift = unwrapper.unwrap_packet(msg)
            #logger.debug(f"From {sender}, received packet: {payload.hex()}")
            #print("Received packet:")
            #print(payload.hex())

            #output.write(PRINT_PREFIX + payload.hex() + "\n")
            #output.flush()
            print(shift)
            melvec = payload_to_melvecs(payload.hex(), melvec_length, n_melvecs)

            # Appliquer la démultiplication (multiplication par 2^shift)
            demultiplier = 2 ** shift
            melvec = melvec * demultiplier  # Multiplie chaque valeur du melvec par 2^shift
            plt.figure()
            plot_specgram(melvec.reshape((20, 20)).T,ax=plt.gca(),is_mel=True)
            plt.draw()
            plt.savefig("melvec.png")
            #logger.info(f"Parsed payload into Mel vectors: {melvecs}")
            fv = melvec.reshape(1, -1)
            melvec = fv/np.linalg.norm(fv)
            #plot melvecs
            plt.figure()
            plot_specgram(melvec.reshape((20, 20)),ax=plt.gca(),is_mel=True)
            plt.draw()
            plt.savefig("melvec.png")



            melvecs_pca = pca.transform(melvec)

            proba_rf = model_rf.predict_proba(melvecs_pca)[0]
            prediction_rf = model_rf.predict(melvecs_pca)
            
            sorted_indices = np.argsort(proba_rf)[::-1]
            best_class = sorted_indices[0]
            second_best_class = sorted_indices[1]
            
            
            # Condition met, send the prediction
            prediction_given = best_class
            logger.info(f"Accepted Prediction: {prediction_given} (Probability: {proba_rf[best_class]:.2f})")
            
            answer = requests.post(f"{hostname}/lelec210x/leaderboard/submit/{key}/{prediction_rf[0]}", timeout=1)
            print(answer.text)
            json_answer = json.loads(answer.text)
            print(json_answer)
            
            logger.info(f"Predictions: {proba_rf}")
            logger.info(f"Prediction: {prediction_rf[0]}")

        
        except packet.InvalidPacket as e:
            logger.error(f"Invalid packet error: {e.args[0]}")
        except Exception as e:
            logger.exception(f"Unexpected error while processing packet: {e}")
