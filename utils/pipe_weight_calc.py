# sch40_pipe_weights.py
"""
Appendix: Schedule 40 Carbon Steel Pipe Weights
================================================

Provides a function to calculate the weight per meter (kg/m)
of Schedule 40 carbon steel pipes for standard DN sizes.

Usage:
    from sch40_pipe_weights import pipe_weight_per_m

    weight = pipe_weight_per_m(100)   # DN100
    print(weight)   # e.g., 16.1 kg/m
"""

import math

# Density of carbon steel (kg/m³)
RHO_STEEL = 7850

# Standard data: (DN, OD [mm], wall thickness [mm])
SCHEDULE_40_DATA = {
    15: (21.34, 2.77),
    20: (26.67, 2.87),
    25: (33.40, 3.38),
    32: (42.16, 3.56),
    40: (48.26, 3.68),
    50: (60.33, 3.91),
    65: (73.03, 5.16),
    80: (88.90, 5.49),
    90: (101.60, 5.74),
    100: (114.30, 6.02),
    125: (141.30, 6.55),
    150: (168.28, 7.11),
    200: (219.10, 8.18),
    250: (273.05, 9.27),
    300: (323.85, 9.53),
}

def pipe_mass_per_m(DN: int) -> float:
    """
    Calculate weight per meter of a Schedule 40 carbon steel pipe.

    Parameters
    ----------
    DN : int
        Nominal diameter (DN size, e.g., 50, 100, 200)

    Returns
    -------
    float
        Weight per meter in kg/m

    Raises
    ------
    ValueError
        If the DN size is not available in the dataset.
    """
    if DN not in SCHEDULE_40_DATA:
        raise ValueError(f"DN{DN} not found in Schedule 40 dataset.")

    OD, t = SCHEDULE_40_DATA[DN]
    ID = OD - 2 * t
    A = (math.pi / 4) * (OD**2 - ID**2) / 1e6   # m²
    V = A * 1.0                                # m³ per meter
    W = V * RHO_STEEL                          # kg/m
    return round(W, 2)


def china_elbow_mass(DN: int,) -> float:
    """
    Estimate the cost of a 90° LR elbow in USD for a given DN size using China steel price.
    Uses elbow mass ≈ k × pipe_mass_per_m(DN), with k depending on DN.
    """
    pipe_mass = pipe_mass_per_m(DN)  # kg/m
    # Approximation: elbow ~ 0.5 × pipe_mass_per_m for LR 90° elbow
    elbow_mass = 0.5 * pipe_mass
    return round(elbow_mass, 2)

