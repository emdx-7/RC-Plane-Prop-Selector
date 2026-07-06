"""
Parse APC PER3_*.dat performance files into a simple grid.

Each APC file is a stack of blocks, one per RPM. Inside a block, each row is one
forward speed V. We pull the columns we care about and build 2D grids indexed by
[rpm_index, speed_index] so they plot straight as 3D surfaces.

Grids returned (all numpy 2D arrays, same shape):
    rpm     : RPM for each row      (same value across a row)
    V       : speed in mph          (same value down a column, if blocks align)
    thrust  : thrust in Newtons
    power   : power in Watts
    eff     : efficiency Pe (0..~0.85), dimensionless
    torque  : torque in N-m
    mach    : tip Mach number (grows with RPM)

Note: APC blocks don't all have the same number of speed rows. We keep only the
first N speed rows common to every block so the grid is rectangular (simplest
thing that works for a surface plot).
"""

import re
import numpy as np


# column index (0-based) of each quantity in a data row, per the file header
COL = {
    "V": 0,        # mph
    "eff": 2,      # Pe
    "power": 8,    # W
    "torque": 9,   # N-m
    "thrust": 10,  # N
    "mach": 12,    # tip Mach (grows with RPM; a per-point value, not a scalar)
}


def _is_data_row(line):
    # a data row starts with a number like "  0.00 " (the V column) and has the
    # full set of 15 columns. Some files have a short/truncated last row we skip.
    s = line.strip()
    if not s:
        return False
    if re.match(r"^-?\d+\.\d+", s) is None:
        return False
    return len(s.split()) >= 15


def parse_file(path):
    """Read one PER3 file -> dict of 2D grids plus the prop name."""
    with open(path, "r") as f:
        lines = f.readlines()

    name = lines[0].strip().split()[0]  # e.g. "10x10"

    # walk the file, splitting into blocks at each "PROP RPM =" line
    blocks = []          # list of (rpm, rows) where rows is list of float-lists
    cur_rpm = None
    cur_rows = []
    for line in lines:
        m = re.search(r"PROP RPM\s*=\s*(\d+)", line)
        if m:
            if cur_rpm is not None:
                blocks.append((cur_rpm, cur_rows))
            cur_rpm = int(m.group(1))
            cur_rows = []
        elif cur_rpm is not None and _is_data_row(line):
            nums = [float(x) for x in line.split()]
            cur_rows.append(nums)
    if cur_rpm is not None:
        blocks.append((cur_rpm, cur_rows))

    # make the grid rectangular: keep the min row count common to all blocks
    n_speed = min(len(rows) for _, rows in blocks)
    rpms = np.array([rpm for rpm, _ in blocks])

    def grid(col):
        return np.array([[rows[i][col] for i in range(n_speed)] for _, rows in blocks])

    V = grid(COL["V"])
    rpm_grid = np.repeat(rpms[:, None], n_speed, axis=1)

    return {
        "name": name,
        "rpm": rpm_grid,
        "V": V,
        "thrust": grid(COL["thrust"]),
        "power": grid(COL["power"]),
        "eff": grid(COL["eff"]),
        "torque": grid(COL["torque"]),
        "mach": grid(COL["mach"]),
    }


if __name__ == "__main__":
    import glob
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    for p in sorted(glob.glob(os.path.join(here, "data", "*.dat"))):
        d = parse_file(p)
        print(f"{d['name']:>10}  grid {d['rpm'].shape}  "
              f"RPM {d['rpm'].min():.0f}-{d['rpm'].max():.0f}  "
              f"Vmax {d['V'].max():.0f}mph  Tmax {d['thrust'].max():.1f}N")
