import sys
import os
from server import serve

if __name__ == "__main__":
    delay = float(os.environ.get("SERVER_DELAY", 0))
    hang = os.environ.get("SERVER_HANG", "0").lower() in ("1", "true", "yes")

    if "--hang" in sys.argv:
        hang = True
    for i, arg in enumerate(sys.argv):
        if arg in ("--delay", "-d") and i + 1 < len(sys.argv):
            delay = float(sys.argv[i + 1])

    if hang:
        print("gRPC server listening on :50051 [SIMULATION: HANG - not responding]", flush=True)
    elif delay > 0:
        print(f"gRPC server listening on :50051 [SIMULATION: DELAY {delay}s]", flush=True)
    else:
        print("gRPC server listening on :50051", flush=True)

    serve(delay=delay, hang=hang)
