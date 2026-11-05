"""J413 (T8112 / Apple M2) CPU frequency and P-state control.

Windows ARM64 has no native Apple Silicon DVFS driver, so cores stay at the
P-states initialized by m1n1 unless raised. On the M2 (T8112):
- E-cluster (Blizzard): P-states 1..7 (up to 2424 MHz)
- P-cluster (Avalanche): P-states 1..12 (up to 3480 MHz)
"""

# T8112 cluster bases from m1n1 cpufreq.c
ECPU_BASE = 0x210E00000
PCPU_BASE = 0x211E00000
CLUSTER_PSTATE = 0x20020

PCPU_PSTATE_REG = PCPU_BASE + CLUSTER_PSTATE
ECPU_PSTATE_REG = ECPU_BASE + CLUSTER_PSTATE

PSTATE_BUSY = 1 << 31
PSTATE_SET = 1 << 25
PSTATE_DESIRED2 = 0xF << 12
PSTATE_DESIRED1 = 0x1F

PCPU_MAX_NON_TURBO = 12
PCPU_MHZ = {
    1: 720,
    2: 1044,
    3: 1368,
    4: 1692,
    5: 2016,
    6: 2340,
    7: 2664,
    8: 2988,
    9: 3180,
    10: 3300,
    11: 3420,
    12: 3480,
}

ECPU_MAX_PSTATE = 7
ECPU_MHZ = {
    1: 696,
    2: 984,
    3: 1272,
    4: 1560,
    5: 1848,
    6: 2136,
    7: 2424,
}


def pcpu_pstate_command(current: int, pstate: int) -> int:
    """Return the command register value requesting Avalanche `pstate`."""
    if not isinstance(pstate, int) or not 1 <= pstate <= PCPU_MAX_NON_TURBO:
        raise ValueError(f"M2 P-cluster P-state {pstate!r} is outside 1..{PCPU_MAX_NON_TURBO}")
    value = current & ~(PSTATE_DESIRED1 | PSTATE_DESIRED2 | PSTATE_BUSY)
    return value | PSTATE_SET | (pstate << 12) | pstate


def requested_pstate(value: int) -> int:
    return value & PSTATE_DESIRED1


def set_pcpu_pstate(proxy, pstate: int, polls: int = 4000):
    """Request M2 P-cluster `pstate` through m1n1 proxy and wait for completion."""
    before = proxy.read64(PCPU_PSTATE_REG)
    proxy.write64(PCPU_PSTATE_REG, pcpu_pstate_command(before, pstate))
    for _ in range(polls):
        after = proxy.read64(PCPU_PSTATE_REG)
        if not after & PSTATE_BUSY:
            break
    else:
        raise RuntimeError(f"M2 P-cluster switch to P-state {pstate} timed out: 0x{after:x}")
    if requested_pstate(after) != pstate:
        raise RuntimeError(f"M2 P-cluster request not retained: 0x{after:x}")
    return before, after


def set_ecpu_pstate(proxy, pstate: int, polls: int = 4000):
    """Request M2 E-cluster `pstate` through m1n1 proxy and wait for completion."""
    if not isinstance(pstate, int) or not 1 <= pstate <= ECPU_MAX_PSTATE:
        raise ValueError(f"M2 E-cluster P-state {pstate!r} is outside 1..{ECPU_MAX_PSTATE}")
    before = proxy.read64(ECPU_PSTATE_REG)
    cmd = (before & ~(PSTATE_DESIRED1 | PSTATE_DESIRED2 | PSTATE_BUSY)) | PSTATE_SET | (pstate << 12) | pstate
    proxy.write64(ECPU_PSTATE_REG, cmd)
    for _ in range(polls):
        after = proxy.read64(ECPU_PSTATE_REG)
        if not after & PSTATE_BUSY:
            break
    else:
        raise RuntimeError(f"M2 E-cluster switch to P-state {pstate} timed out: 0x{after:x}")
    return before, after
