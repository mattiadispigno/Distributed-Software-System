import os
import grpc
import greeter_pb2
import greeter_pb2_grpc

def run_naive_client():
    host = os.environ.get('GREETER_HOST', 'localhost')
    channel = grpc.insecure_channel(f'{host}:50051')
    stub = greeter_pb2_grpc.GreeterServiceStub(channel)

    response = stub.Greet(greeter_pb2.GreetRequest(name="Client1"))
    print(f"Response received: {response.message}")
