import os
import signal
import sys
import time
import grpc
from concurrent import futures
import greeter_pb2
import greeter_pb2_grpc

class GreeterServiceImpl(greeter_pb2_grpc.GreeterServiceServicer):
    def __init__(self, delay=0.0, hang=False):
        self.delay = delay
        self.hang = hang

    def _apply_fault(self, context):
        for path in ("control/fault.txt", "fault.txt"):
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        content = f.read().strip().lower()
                except OSError:
                    continue
                if content and content != "ok":
                    if content == "hang":
                        while True:
                            time.sleep(3600)
                    elif content in ("down", "unavailable"):
                        context.abort(grpc.StatusCode.UNAVAILABLE, "Server simulated failure (runtime fault)")
                    elif content.startswith("delay"):
                        parts = content.split()
                        time.sleep(float(parts[1]) if len(parts) > 1 else 3.0)
                    elif content.replace(".", "", 1).isdigit():
                        time.sleep(float(content))
                return

        if self.hang:
            while True:
                time.sleep(3600)
        if self.delay > 0:
            time.sleep(self.delay)

    def Greet(self, request, context):
        self._apply_fault(context)
        greeting_str = f"hello {request.name} from server"
        return greeter_pb2.GreetReply(message=greeting_str)

def serve(delay=0.0, hang=False):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    greeter_pb2_grpc.add_GreeterServiceServicer_to_server(GreeterServiceImpl(delay, hang), server)
    server.add_insecure_port('[::]:50051')
    server.start()

    def handle_stop(*_):
        server.stop(grace=0)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    server.wait_for_termination()
