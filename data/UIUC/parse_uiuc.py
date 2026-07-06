"""
Read one UIUC propeller data file into a simple table of rows.

UIUC data files come in three kinds, each a header line then whitespace columns:

    performance : "J  CT  CP  eta"   -- a sweep at one fixed RPM (RPM is in the
                                        filename, not the file)
    static      : "RPM  CT  CP"      -- coefficients vs RPM at zero airspeed
    geom        : "r/R  c/R  beta"   -- blade planform (radius, chord, twist)

parse_table() just returns the header names and the numeric rows; the caller
(build_uiuc.py) knows which kind it is from the filename and interprets them.
"""


def parse_table(path):
    """Return (headers, rows) where headers is a list of column names and rows
    is a list of float-lists. Blank/short lines are skipped."""
    with open(path, "r", encoding="latin-1") as f:
        lines = f.readlines()

    headers = lines[0].split()
    rows = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != len(headers):
            continue                      # skip blanks / malformed trailing lines
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue                      # a stray non-numeric line
    return headers, rows
