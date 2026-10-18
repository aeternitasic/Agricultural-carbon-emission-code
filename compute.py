import numpy as np


def compute_ace(Q: np.ndarray, Phi: np.ndarray) -> np.ndarray:
    result =  np.einsum("ipt, ip -> pt", Q, Phi)
    return result
