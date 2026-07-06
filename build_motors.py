"""
Build motors/motors_data.js from motors/motors.json.

Same reason as picker_data.js: picker.html and the motor-match tab open via
file://, and browsers block fetch() on local files. So the motor list is
compiled into a plain .js file that assigns a JS global, and loaded with a
<script> tag instead.

Run:  py build_motors.py   ->  writes motors/motors_data.js
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "motors", "motors.json")
OUT = os.path.join(HERE, "motors", "motors_data.js")


def main():
    motors = json.load(open(SRC, encoding="utf-8"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.MOTOR_DATA = ")
        json.dump(motors, f, indent=2)
        f.write(";\n")
    print(f"wrote {OUT}  ({len(motors)} motors)")


if __name__ == "__main__":
    main()
