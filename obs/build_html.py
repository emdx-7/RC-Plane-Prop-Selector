"""
Build a single self-contained HTML demo (Plotly): 4 props as 4 adjacent columns.

Each prop = one card (no sub-cards), a vertical stack of:
    - 3D scatter of Thrust   vs (RPM, speed)   [z normalized to this prop's max thrust]
    - 3D scatter of Power    vs (RPM, speed)   [z normalized to this prop's max power]
    - 3D scatter of Efficiency vs (RPM, speed) [z normalized to this prop's max eff]
    - 2D slice at ~0 mph  : quantities vs RPM (nearest real point to that speed)
    - 2D slice at ~40 mph : quantities vs RPM
    - prop name (header) + basic info

Everything is a scatter of REAL computed APC points. The 2D slices pick, within
each RPM row, the data point whose speed is nearest the target speed -- so every
dot is a real point, nothing interpolated.

The four 3D plots in a row share a synchronized camera: rotate/zoom one and the
others follow (wired with Plotly relayout events at the bottom of the file).

Run:  py build_html.py   ->  writes demo.html
"""

import glob
import os

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from parse_apc import parse_file


# the 3 quantities that get their own 3D plot: (label, key, color)
Q3D = [
    ("Thrust", "thrust", "#4C78A8"),
    ("Power", "power", "#E45756"),
    ("Efficiency", "eff", "#54A24B"),
]

# two absolute speeds (mph) for the 2D slices, same for every prop
SLICE_SPEEDS = [0.0, 40.0]

DEMO_PROPS = ["10x10", "42x4", "28x20-4", "11x7SF"]


def load(stem):
    here = os.path.dirname(os.path.abspath(__file__))
    matches = glob.glob(os.path.join(here, "data", f"*{stem}*.dat"))
    return parse_file(matches[0]) if matches else None


def axis_range(rng, key):
    """[floor, max] for a quantity. floor is 0 for now; swap to rng['min'][key]
    later for any quantity that needs a global-min baseline."""
    floor = 0.0                       # <- change to rng["min"][key] to use global min
    return [floor, rng["max"][key]]


def fig_3d(d, label, key, color, div_id, rng):
    """One 3D scatter for a single quantity in RAW units, on shared axes so the
    same position means the same value on every prop."""
    rpm, V, Z = d["rpm"], d["V"], d[key]
    fig = go.Figure(go.Scatter3d(
        x=rpm.flatten(), y=V.flatten(), z=Z.flatten(),
        mode="markers", marker=dict(size=2, color=color),
        name=label,
    ))
    fig.update_layout(
        title=label,
        scene=dict(
            xaxis=dict(title="RPM", range=axis_range(rng, "rpm")),
            yaxis=dict(title="mph", range=axis_range(rng, "V")),
            zaxis=dict(title="", range=axis_range(rng, key)),
            aspectmode="cube",
        ),
        height=380, margin=dict(l=0, r=0, t=28, b=0), showlegend=False,
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id=div_id)


def slice_points(d, target_speed):
    """For each RPM row, pick the RAW value at the point nearest target_speed."""
    rpm_axis = d["rpm"][:, 0]
    V = d["V"]
    j = np.argmin(np.abs(V - target_speed), axis=1)   # nearest real speed per row
    rows = np.arange(V.shape[0])
    picked = {key: d[key][rows, j] for _, key, _ in Q3D}
    return rpm_axis, picked


def fig_slice(d, target_speed, rng, div_id):
    """2D scatter vs RPM at (nearest to) one speed. Each quantity gets its OWN
    y-axis (Thrust left, Power + Efficiency on the right), matplotlib twin-axis
    style. Each axis range is shared across all props via the global max, so a
    given quantity reads on the same scale on every card.

    The div_id lets the RPM range slider retarget this plot's x-axis."""
    rpm_axis, picked = slice_points(d, target_speed)

    # which quantity sits on which y-axis: thrust=yaxis, power=yaxis2, eff=yaxis3
    axis_of = {"thrust": "y", "power": "y2", "eff": "y3"}

    fig = go.Figure()
    for label, key, color in Q3D:
        fig.add_trace(go.Scatter(
            x=rpm_axis, y=picked[key], mode="markers+lines",
            name=label, marker=dict(size=4, color=color),
            line=dict(color=color, width=1), yaxis=axis_of[key],
        ))

    C = {q[1]: q[2] for q in Q3D}   # color per key, to tint each axis
    fig.update_layout(
        title=f"slice @ {target_speed:.0f} mph",
        xaxis=dict(title="RPM", range=axis_range(rng, "rpm"), domain=[0.0, 0.80]),
        # left axis: Thrust (N)
        yaxis=dict(title=dict(text="Thrust (N)", font=dict(color=C["thrust"])),
                   range=axis_range(rng, "thrust"), tickfont=dict(color=C["thrust"])),
        # first right axis: Power (W)
        yaxis2=dict(title=dict(text="Power (W)", font=dict(color=C["power"])),
                    range=axis_range(rng, "power"), tickfont=dict(color=C["power"]),
                    overlaying="y", side="right"),
        # second right axis: Efficiency on a fixed 0-1 (0-100%) scale, no title.
        # A green line at 1.0 marks the 100% ceiling (data never reaches it).
        yaxis3=dict(range=[0.0, 1.0], tickfont=dict(color=C["eff"]),
                    overlaying="y", side="right", anchor="free", position=0.92),
        autosize=True, margin=dict(l=45, r=70, t=30, b=36),
        legend=dict(orientation="h", y=-0.35, font=dict(size=9)),
    )
    # green 100% reference line, pinned to the efficiency axis (y3)
    fig.add_hline(y=1.0, line=dict(color=C["eff"], width=1, dash="dot"), yref="y3")
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id=div_id)


def info_block(d):
    rpm = d["rpm"]
    return (f"RPM {rpm.min():.0f}&ndash;{rpm.max():.0f} &nbsp;|&nbsp; "
            f"grid {rpm.shape[0]}&times;{rpm.shape[1]} &nbsp;|&nbsp; "
            f"max thrust {d['thrust'].max():.1f} N &nbsp;|&nbsp; "
            f"max power {d['power'].max():.0f} W")


def main():
    here = os.path.dirname(os.path.abspath(__file__))

    # load every prop once, then compute global min/max per quantity so all cards
    # share identical axes (same screen position => same value on every prop)
    props = [d for d in (load(s) for s in DEMO_PROPS) if d is not None]
    keys = ["rpm", "V", "thrust", "power", "eff", "torque"]
    rng = {
        "max": {k: max(float(d[k].max()) for d in props) for k in keys},
        "min": {k: min(float(d[k].min()) for d in props) for k in keys},
    }

    cards = []
    scene_ids = []   # div ids of every 3D plot, for camera sync
    slice_ids = []   # div ids of every 2D slice plot, for the RPM range slider
    for card_i, d in enumerate(props):
        stem = d["name"]

        # the Rebuild button sits between the 2D slices and the 3D plots in the
        # first card; the other cards get an empty slot of the same height there
        # so all 3D plots stay aligned across cards
        if card_i == 0:
            mid_slot = ('<div class="mid-slot">'
                        '<button id="rebuildBtn">Rebuild &mdash; apply top-left '
                        'angle to all</button></div>')
        else:
            mid_slot = '<div class="mid-slot"></div>'

        plots_3d = []
        for label, key, color in Q3D:
            div_id = f"g3d_{stem}_{key}".replace(".", "")
            scene_ids.append(div_id)
            # plotly.js is loaded once in <head>, so every plot omits the library
            plots_3d.append(fig_3d(d, label, key, color, div_id, rng))

        slices = []
        for s in SLICE_SPEEDS:
            sid = f"sl_{stem}_{s:.0f}".replace(".", "")
            slice_ids.append(sid)
            # wrap in a 5:4 (w:h) box so the plot sizes by width, not absolute px
            slices.append(f'<div class="slicebox">{fig_slice(d, s, rng, sid)}</div>')

        cards.append(f"""
        <div class="card">
          {''.join(slices)}
          <hr class="divider">
          {mid_slot}
          {''.join(plots_3d)}
          <div class="propname">{d['name']}</div>
          <div class="info">{info_block(d)}</div>
        </div>
        """)

    # --- manual camera sync: only the FIRST 3D plot is draggable; the rest are
    # locked. The Rebuild button copies the first plot's camera to all the others.
    # This avoids the auto-sync feedback loop (only one plot ever emits events).
    master_id = scene_ids[0]
    other_ids_js = ", ".join(f'"{i}"' for i in scene_ids[1:])
    slice_ids_js = ", ".join(f'"{i}"' for i in slice_ids)
    rpm_max = int(rng["max"]["rpm"])
    sync_js = f"""
    <script>
    window.addEventListener('load', function() {{
      var master = "{master_id}";
      var others = [{other_ids_js}];

      // lock every non-master 3D plot: no rotate/zoom drag
      others.forEach(function(id) {{
        var gd = document.getElementById(id);
        if (gd) Plotly.relayout(id, {{'scene.dragmode': false}});
      }});

      // remember the master's camera whenever the user finishes rotating it.
      // Only the master emits events, so there is no feedback loop.
      var lastCam = null;
      document.getElementById(master).on('plotly_relayout', function(ev) {{
        if (ev && ev['scene.camera']) lastCam = ev['scene.camera'];
      }});

      // Rebuild: push the remembered master camera to all the others
      document.getElementById('rebuildBtn').addEventListener('click', function() {{
        if (!lastCam) return;  // nothing to copy until the user has rotated once
        others.forEach(function(id) {{
          Plotly.relayout(id, {{'scene.camera': lastCam}});
        }});
      }});

      // --- RPM range slider: retarget the x-axis of every 2D slice plot ---
      var sliceIds = [{slice_ids_js}];
      var loEl = document.getElementById('rpmMin');
      var hiEl = document.getElementById('rpmMax');
      function applyRpm() {{
        var lo = parseFloat(loEl.value), hi = parseFloat(hiEl.value);
        if (lo > hi) {{ var t = lo; lo = hi; hi = t; }}   // keep min <= max
        document.getElementById('rpmLabel').textContent =
          lo.toFixed(0) + ' - ' + hi.toFixed(0) + ' RPM';
        sliceIds.forEach(function(id) {{
          Plotly.relayout(id, {{'xaxis.range': [lo, hi]}});
        }});
      }}
      loEl.addEventListener('input', applyRpm);
      hiEl.addEventListener('input', applyRpm);
      applyRpm();

      // make each slice fill its 5:4 box (Plotly needs a resize nudge)
      sliceIds.forEach(function(id) {{ Plotly.Plots.resize(id); }});
      window.addEventListener('resize', function() {{
        sliceIds.forEach(function(id) {{ Plotly.Plots.resize(id); }});
      }});
    }});
    </script>
    """

    # load plotly.js exactly once, in <head>, so every plot (in any DOM order)
    # has the library available before its init script runs
    plotly_lib = pio.to_html(go.Figure(), include_plotlyjs=True, full_html=False,
                             div_id="__lib__")
    # keep the biggest <script> block (that's the ~4MB plotly library itself)
    import re as _re
    scripts = _re.findall(r"<script[^>]*>.*?</script>", plotly_lib, _re.DOTALL)
    lib_script = max(scripts, key=len)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>APC Prop Demo</title>
{lib_script}
<style>
  body {{ font-family: system-ui, sans-serif; margin: 8px; background:#fff; color:#111; }}
  h1 {{ font-size: 19px; }}
  .note {{ color:#555; font-size:13px; max-width:900px; margin-bottom:10px; }}
  .row {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:6px; }}
  .card {{ border:1px solid #ccc; border-radius:6px; padding:5px; }}
  .propname {{ font-size:18px; font-weight:700; margin-top:8px; }}
  .info {{ font-size:12px; color:#444; margin-top:2px; }}
  #rebuildBtn {{ font-size:14px; padding:6px 14px; margin:0;
    cursor:pointer; border:1px solid #888; border-radius:4px; background:#f0f0f0; }}
  /* fixed-height slot between 2D and 3D in every card so 3D plots stay aligned;
     only card 1 fills it (with the Rebuild button) */
  .mid-slot {{ height:34px; display:flex; align-items:center; margin-bottom:4px; }}
  .toolbar {{ display:flex; align-items:center; gap:16px; flex-wrap:wrap;
    margin-bottom:10px; }}
  .rpmctl {{ font-size:13px; }}
  .rpmctl input[type=range] {{ width:180px; vertical-align:middle; }}
  /* 2D slices: size by width at a 5:4 (w:h) ratio */
  .slicebox {{ width:100%; aspect-ratio: 5 / 4; margin-top:4px; }}
  .slicebox > .plotly-graph-div {{ width:100% !important; height:100% !important; }}
  .divider {{ border:0; border-top:1px solid #bbb; margin:10px 0; }}
</style>
</head>
<body>
<h1>APC Propeller Demo &mdash; 4 props, side by side</h1>
<p class="note">
  Every dot is a real APC computed point &mdash; nothing interpolated, RAW units. All plots
  share identical axes across props, so the same position means the same value on every
  card: Thrust plots share one Newton scale, Power plots one Watt scale, Efficiency plots
  one scale; RPM and speed axes are shared too. Small props therefore look tiny &mdash; by
  design. The two speed slices (0 and 40 mph) put all three quantities on one raw y-axis, so
  Power dominates and thrust/efficiency read near-flat. Only the top-left 3D plot rotates
  &mdash; drag it, then click Rebuild to copy that angle to every other 3D plot. The 2D
  slices now use three shared y-axes (Thrust left, Power &amp; Efficiency right). Use the
  RPM slider to zoom the 2D x-axis across all cards at once.
</p>
<div class="toolbar">
  <span class="rpmctl">
    2D RPM range:
    min <input type="range" id="rpmMin" min="0" max="{rpm_max}" value="0" step="500">
    max <input type="range" id="rpmMax" min="0" max="{rpm_max}" value="{rpm_max}" step="500">
    <span id="rpmLabel"></span>
  </span>
</div>
<div class="row">
{''.join(cards)}
</div>
{sync_js}
</body></html>
"""

    out = os.path.join(here, "demo.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out}  ({os.path.getsize(out) / 1e6:.1f} MB)  3D plots: {len(scene_ids)}")


if __name__ == "__main__":
    main()
