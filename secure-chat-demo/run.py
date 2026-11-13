"""
run.py - start the classroom digital-signature chat demo.

    python3 run.py                 # listen on all interfaces, port 8070
    python3 run.py --port 9000
    python3 run.py --host 127.0.0.1   # local only (no phones)

On start it prints:
  * the URL / QR link students open on their phones (same Wi-Fi), and
  * the ADMIN PASSCODE for the teacher dashboard at <url>/admin.

Everything is stored in memory only and is gone when you stop the server
(Ctrl+C) or press Reset in the dashboard.
"""

import os
import socket
import sys
import webbrowser

from server.app import serve
from server.state import STORE


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    argv = sys.argv[1:]
    host = "0.0.0.0"
    port = 8070
    if "--host" in argv:
        host = argv[argv.index("--host") + 1]
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    # Fixed admin passcode (so it does not change every restart)
    if "--passcode" in argv:
        STORE.admin_passcode = str(argv[argv.index("--passcode") + 1])

    # The address students connect to. Inside Docker, set --public-host (or env
    # SC_PUBLIC_HOST) to the laptop's Wi-Fi IP so the printed URL and QR are reachable.
    public_host = os.environ.get("SC_PUBLIC_HOST")
    if "--public-host" in argv:
        public_host = argv[argv.index("--public-host") + 1]
    if public_host:
        ip = public_host
    elif host == "127.0.0.1":
        ip = "127.0.0.1"
    else:
        ip = lan_ip()
    base_url = f"http://{ip}:{port}/"
    httpd = serve(host, port, base_url)

    line = "=" * 60
    print(line)
    print("  SecureChat - digital signature classroom demo")
    print(line)
    print(f"  Students join at : {base_url}")
    print(f"  (scan the QR shown on the admin screen)")
    print(f"  Teacher dashboard: {base_url}admin")
    print(f"  ADMIN PASSCODE   : {STORE.admin_passcode}")
    print(line)
    print("  All data is in memory and is wiped when you stop the server.")
    print("  Press Ctrl+C to stop.")
    print(line)
    if "--open" in argv:
        webbrowser.open(f"{base_url}admin")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. All demo data wiped.")


if __name__ == "__main__":
    main()
