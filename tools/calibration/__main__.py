"""python -m tools.calibration {capture,calibrate,verify,list} --help"""

import argparse
from pathlib import Path

import numpy as np

from tools.calibration import DEFAULT_COLS, DEFAULT_ROWS, DEFAULT_SQUARE_MM, images_dir
from tools.calibration import __doc__ as GUIDE
from tools.calibration.calib_io import DEFAULT_OUT_DIR, list_all, load

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp")


def _name(args) -> str:
    """--name, else the camera: 'tello' or 'webcam'."""
    return args.name or getattr(args, "camera", "tello")


def _images(args) -> Path:
    return Path(args.images) if args.images else images_dir(_name(args))


def _open(args):
    from tools.calibration.camera import open_camera

    return open_camera(args.camera, args.ip, args.index)


def cmd_capture(args) -> None:
    from tools.calibration.capture import capture

    cam = _open(args)
    try:
        saved = capture(cam, _images(args), args.cols, args.rows)
    finally:
        cam.close()
    print(f"\n{saved} new pictures in {_images(args)}. Next: python -m tools.calibration calibrate --name {_name(args)}")


def cmd_calibrate(args) -> None:
    from tools.calibration.calibrate import run

    run(_images(args), _name(args), args.cols, args.rows, args.square, args.show, Path(args.out))


def cmd_verify(args) -> None:
    from tools.calibration.verify import verify_images, verify_live

    calib = load(_name(args), Path(args.out))
    if args.images:
        verify_images(sorted(p for p in Path(args.images).glob("*") if p.suffix.lower() in IMAGE_SUFFIXES), calib)
        return
    cam = _open(args)
    try:
        verify_live(cam, calib)
    finally:
        cam.close()


def cmd_list(args) -> None:
    calibs = list_all(Path(args.out))
    if not calibs:
        print(f"No calibrations in {args.out}")
    np.set_printoptions(precision=2, suppress=True)
    for c in calibs:
        size = f"{c['image_size'][0]}x{c['image_size'][1]}" if c["image_size"] else "size unknown"
        rms = f"rms {c['rms']:.3f} px" if c["rms"] is not None else "rms unknown"
        K = c["camera_matrix"]
        focal = f"fx={K[0, 0]:.1f} fy={K[1, 1]:.1f} cx={K[0, 2]:.1f} cy={K[1, 2]:.1f}"
        print(f"{c['name']:<10} {size:<12} {rms:<14} {focal} dist={c['dist_coeffs'].ravel()}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tools.calibration", description=GUIDE, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def camera(p):
        p.add_argument("--camera", choices=["tello", "webcam"], default="tello", help="video source (default tello)")
        p.add_argument("--ip", default="192.168.10.1", help="Tello IP (default 192.168.10.1 = its hotspot; e.g. 192.168.10.133 in station mode)")
        p.add_argument("--index", type=int, default=0, help="webcam: which camera (default 0)")

    def names(p):
        p.add_argument("--name", default=None, help="calibration name (default: the --camera, i.e. tello / webcam)")
        p.add_argument("--images", default=None, help="picture folder (default tools/calibration/images/<name>/)")
        p.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="calibration folder (default core/video/calibration)")

    def board(p):
        p.add_argument("--cols", type=int, default=DEFAULT_COLS, help=f"INNER corners horizontally (default {DEFAULT_COLS})")
        p.add_argument("--rows", type=int, default=DEFAULT_ROWS, help=f"INNER corners vertically (default {DEFAULT_ROWS})")

    p = sub.add_parser("capture", help="live video, SPACE saves a chessboard picture")
    camera(p), names(p), board(p)
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("calibrate", help="pictures -> <out>/<name>.npz")
    p.add_argument("--camera", choices=["tello", "webcam"], default="tello", help="only picks the default --name")
    names(p), board(p)
    p.add_argument("--square", type=float, default=DEFAULT_SQUARE_MM, help=f"square edge in mm (default {DEFAULT_SQUARE_MM})")
    p.add_argument("--show", action="store_true", help="show the found corners of every picture")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("verify", help="original | undistorted side by side (live, or --images to step through pictures)")
    camera(p), names(p)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("list", help="show the calibrations")
    p.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="calibration folder")
    p.set_defaults(func=cmd_list)

    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        pass
    except (RuntimeError, FileNotFoundError, ConnectionError, TimeoutError, ValueError) as e:
        raise SystemExit(f"\nError: {e}") from None


if __name__ == "__main__":
    main()
