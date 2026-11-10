"""
tools/ - standalone helper programs (NOT part of DFU's runtime - they need only the
standard library, opencv-python and numpy). Run them from the repo root:

    python -m tools.set_tello_wifi --help      put a Tello EDU / Talent on your Wi-Fi (station mode)
    python -m tools.calibration --help         camera calibration: capture -> calibrate -> verify
    powershell -File tools/count1.ps1          count lines of code per folder (Windows)
"""
