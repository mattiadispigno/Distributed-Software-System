# Remote Invocation with gRPC and Protocol Buffers

A distributed system demonstrating Remote Procedure Call (RPC) interactions, multi-language interoperability, and fault tolerance using **gRPC** and **Protocol Buffers**.

### Components
- **Server (Python)**: Implements `GreeterService` with runtime fault injection capabilities (delays, hangs, service unavailability).
- **Client 1 (Python)**: Naive synchronous blocking client without deadlines or error handling.
- **Client 2 (Java 21)**: Resilient asynchronous non-blocking client with a 2-second deadline and error handling.

> For an in-depth architectural breakdown and test analysis across failure scenarios, see [`docs/documentation.md`](docs/documentation.md).

---

## 1. Protocol Buffers Stub Generation

The service contract is defined in `greeter.proto`.

### Python (Server & Client 1)
Python stubs must be generated before building Docker images:

```bash
python -m grpc_tools.protoc -I. --python_out=Server  --grpc_python_out=Server  greeter.proto
python -m grpc_tools.protoc -I. --python_out=Client1 --grpc_python_out=Client1 greeter.proto
```

### Java (Client 2)
Java stubs are generated automatically during the Docker build by the `com.google.protobuf` Gradle plugin.
*(For local generation without Docker: `cd Client2 && ./gradlew :app:generateProto`)*

---

## 2. Running with Docker

All components are orchestrated through Docker Compose. Run commands from the `HomeWork/02_RemoteInvocation/` root directory.

### Start the Server
```bash
docker compose up -d --build server
```

### Run Client 1 (Python - Synchronous)
```bash
docker compose run --rm client1
```

### Run Client 2 (Java - Asynchronous Fault-Tolerant)
```bash
docker compose run --rm client2
```

---

## 3. Runtime Fault Simulation (Zero Rebuild / Zero Restart)

Use `./scripts/set_fault.sh` to alter the server's runtime behavior dynamically without restarting containers:

```bash
# Normal operation (immediate reply)
./scripts/set_fault.sh ok

# Simulate slow server (3-second delay, triggers DEADLINE_EXCEEDED on Client 2)
./scripts/set_fault.sh delay 3

# Simulate stalled server (indefinite hang, Client 2 timeouts, Client 1 freezes)
./scripts/set_fault.sh hang

# Simulate server outage (returns UNAVAILABLE, causes Client 1 to crash, Client 2 degrades gracefully)
./scripts/set_fault.sh down
```

---

## 4. Teardown

Stop and clean up containers and networks:

```bash
docker compose down
```

