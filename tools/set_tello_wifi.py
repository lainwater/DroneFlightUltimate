"""
Put a Tello EDU / Tello Talent on your Wi-Fi network (station mode). Standalone:
only the Python standard library, no DFU needed.

    python -m tools.set_tello_wifi --ssid MY_NETWORK --password MY_PASSWORD
    python tools/set_tello_wifi.py --ssid MY_NETWORK --password MY_PASSWORD --ip 192.168.10.133

1. Connect your PC to the Tello's own hotspot (TELLO-xxxxxx), or - to move a Tello
   that is already on a network - to that network and pass its --ip.
2. Run this. The Tello answers "ok", reboots and joins your network.
3. Find its new IP in your router's DHCP client list (or reserve one for its MAC),
   put it in the project's config/mydrone.json ("ip") and connect the PC to that network.

Only the Tello EDU and Tello Talent (RoboMaster TT) support this; the basic Tello can't.
Back to hotspot mode: hold the power button ~5 s until the LED blinks (Wi-Fi reset).
Nothing is stored: SSID and password are only sent to the drone.
"""

import argparse
import socket

TELLO_PORT = 8889
LOCAL_PORT = 9000  # same as DFU, so the same firewall rule works


def send(sock: socket.socket, address: tuple[str, int], command: str, timeout: float) -> str | None:
    """One command -> the Tello's answer, None if there is none."""
    sock.settimeout(timeout)
    sock.sendto(command.encode(), address)
    try:
        return sock.recvfrom(1024)[0].decode(errors="replace").strip()
    except (socket.timeout, ConnectionResetError):
        return None


def set_wifi(ip: str, ssid: str, password: str, local_port: int = LOCAL_PORT, timeout: float = 5.0) -> bool:
    address = (ip, TELLO_PORT)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("", local_port))
        answer = send(sock, address, "command", timeout)
        print(f"command -> {answer}")
        if answer is None:
            print(f"\nNo answer from the Tello at {ip}. Is your PC on the Tello's network? Firewall: allow inbound UDP {local_port}.")
            return False
        answer = send(sock, address, f"ap {ssid} {password}", 10.0)
        print(f"ap {ssid} ******** -> {answer}")
    if answer is None:
        print(f"\nSent, no answer (the Tello often reboots before replying). Check your router for it on '{ssid}'.")
        return True
    if answer.lower().endswith("ok"):
        print(f"\nDone. The Tello reboots and joins '{ssid}'. Find its new IP in your router and put it in config/mydrone.json.")
        return True
    print(f"\nThe Tello answered '{answer}'. Only Tello EDU / Tello Talent support station mode.")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Put a Tello EDU / Talent on your Wi-Fi network (station mode).",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ssid", required=True, help="name of the Wi-Fi network the Tello should join")
    parser.add_argument("--password", required=True, help="its password (the Tello needs at least 8 characters)")
    parser.add_argument("--ip", default="192.168.10.1", help="current IP of the Tello (default 192.168.10.1 = its own hotspot)")
    parser.add_argument("--local-port", type=int, default=LOCAL_PORT, help=f"UDP port on this PC for the answers (default {LOCAL_PORT})")
    args = parser.parse_args()
    if len(args.password) < 8:
        parser.error("the Tello needs a password with at least 8 characters")
    if " " in args.ssid or " " in args.password:
        parser.error("SSID and password must not contain spaces (the Tello command is space separated)")
    raise SystemExit(0 if set_wifi(args.ip, args.ssid, args.password, args.local_port) else 1)


if __name__ == "__main__":
    main()
