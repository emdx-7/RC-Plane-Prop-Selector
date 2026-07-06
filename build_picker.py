"""
Build the candidate-picker data bundle.

Reads every propeller/<name>.json (the merged APC + UIUC files) and writes one
compact JavaScript file, picker_data.js, that picker.html loads directly. We do
this instead of embedding all 611 full sweeps in the HTML (that is ~87 MB); the
slimmed bundle is ~13 MB and works offline from a plain file:// open.

For each prop we keep:
    summary : the identity + range fields the table filters/sorts on
    sim     : the APC sweep, slimmed to the 6 plotted columns (or null)
    emp     : the UIUC sweep, CONVERTED to the same dimensional units (or null)

Empirical conversion (UIUC gives only coefficients CT, CP, eta and advance
ratio J). Using standard propeller-coefficient physics with sea-level air:
    rho = 1.225 kg/m^3
    D   = diameter_in * 0.0254            (m)
    n   = rpm / 60                        (rev/s)
    thrust  = CT * rho * n^2 * D^4        (N)
    power   = CP * rho * n^3 * D^5        (W)
    torque  = power / (2*pi*n)            (N-m)
    V       = J * n * D                   (m/s)  -> * 2.23694 -> mph
so an empirical point lands on the same Thrust/Power/Torque/mph axes as the APC
sweep. Efficiency uses eta directly.

Run:  py build_picker.py   ->  writes picker_data.js
"""

import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROP_DIR = os.path.join(HERE, "propeller")
OUT = os.path.join(HERE, "picker_data.js")

RHO = 1.225                    # kg/m^3, sea-level air density
IN_TO_M = 0.0254               # inches -> meters
MS_TO_MPH = 2.23694            # m/s -> mph


def r(x, nd=3):
    """Round to nd decimals, keeping JSON small. None passes through."""
    return None if x is None else round(float(x), nd)


def slim_sim(sim):
    """APC sweep -> parallel arrays of the 6 columns the picker plots.

    Arrays (not per-point dicts) keep the bundle small. All the same length,
    one entry per (rpm, speed) grid point, in the file's original order."""
    if sim is None:
        return None
    s = sim["sweep"]
    return {
        "rpm":    [r(p["rpm"], 0) for p in s],
        "V_mph":  [r(p["V_mph"], 2) for p in s],
        "thrust": [r(p["thrust_N"], 3) for p in s],
        "power":  [r(p["power_W"], 2) for p in s],
        "eff":    [r(p["eff"], 4) for p in s],
        "torque": [r(p["torque_Nm"], 4) for p in s],
    }


def slim_emp(emp, diameter_in):
    """UIUC sweep -> the same 6 columns, converting coefficients to dimensional
    units (see the module docstring for the physics)."""
    if emp is None or diameter_in is None:
        return None
    D = diameter_in * IN_TO_M
    rpm, V, thrust, power, eff, torque = [], [], [], [], [], []
    for p in emp["sweep"]:
        n = p["rpm"] / 60.0
        if n <= 0:
            continue
        T = p["CT"] * RHO * n**2 * D**4
        P = p["CP"] * RHO * n**3 * D**5
        Q = P / (2 * math.pi * n)
        V_mph = p["J"] * n * D * MS_TO_MPH        # J=0 for static points -> 0 mph
        rpm.append(r(p["rpm"], 0))
        V.append(r(V_mph, 2))
        thrust.append(r(T, 3))
        power.append(r(P, 2))
        eff.append(r(p["eta"], 4))
        torque.append(r(Q, 4))
    return {"rpm": rpm, "V_mph": V, "thrust": thrust,
            "power": power, "eff": eff, "torque": torque}


def summary(meta, sim, emp):
    """The flat fields the table shows / filters / sorts on. Ranges come from the
    APC side when present (it's the catalog reference), else the UIUC side."""
    src = sim or emp or {}
    return {
        "name": meta["name"],
        "diameter_in": meta["diameter_in"],
        "pitch_in": meta["pitch_in"],
        "blades": meta["blades"],
        "type": ", ".join(meta["type"]) if meta.get("type") else "",
        "has_sim": meta["has_simulated"],
        "has_emp": meta["has_empirical"],
        "rpm_min": src.get("rpm_min"),
        "rpm_max": src.get("rpm_max"),
        "v_max_mph": (sim or {}).get("v_max_mph"),
        "max_thrust_N": (sim or {}).get("max_thrust_N"),
        "max_power_W": (sim or {}).get("max_power_W"),
    }


def main():
    props = []
    for path in sorted(glob.glob(os.path.join(PROP_DIR, "*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        meta = d["meta"]
        sim = d["sources"]["simulated"]
        emp = d["sources"]["empirical"]
        props.append({
            "summary": summary(meta, sim, emp),
            "sim": slim_sim(sim),
            "emp": slim_emp(emp, meta["diameter_in"]),
        })

    # write as a JS global so picker.html can open straight from file:// (a plain
    # .json would need fetch(), which browsers block on local files)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.PROP_DATA = ")
        json.dump(props, f, separators=(",", ":"))
        f.write(";\n")

    mb = os.path.getsize(OUT) / 1e6
    n_emp = sum(1 for p in props if p["emp"])
    print(f"wrote {OUT}  ({mb:.1f} MB)  {len(props)} props, {n_emp} with empirical")


if __name__ == "__main__":
    main()
