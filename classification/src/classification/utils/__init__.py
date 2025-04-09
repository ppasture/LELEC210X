import struct
import numpy as np
from common.defaults import MELVEC_LENGTH, N_MELVECS
 
def payload_to_melvecs(
    payload: str, melvec_length: int = MELVEC_LENGTH, n_melvecs: int = N_MELVECS
) -> np.ndarray:
    """Convert a payload string to a melvecs array (Q7 format)."""
    fmt = f"!{melvec_length}b"  # Changer "h" (16 bits) en "b" (8 bits)
    buffer = bytes.fromhex(payload.strip())
    unpacked = struct.iter_unpack(fmt, buffer)
    melvecs_q7int = np.asarray(list(unpacked), dtype=np.int8)  # Changer np.int16 en np.int8
    melvecs = melvecs_q7int.astype(float) / 128  # Changer 32768 en 128 (2 ** 7)
    melvecs = np.rot90(melvecs, k=-1, axes=(0, 1))
    melvecs = np.fliplr(melvecs)
    return melvecs