# Report: Remote Invocation with gRPC and Protocol Buffers

## 1. Introduction and Architectural Considerations on gRPC and Protocol Buffers

The transition from local to distributed programming introduces structural challenges that do not exist within a single address space: **network latency** (orders of magnitude higher than RAM access), the **absence of shared memory** (rendering local pointers meaningless across distinct nodes), and above all, the presence of **partial failures**, whereby a remote node or communication channel may degrade or fail independently and unpredictably from the caller process.

To relieve developers from manual management of TCP/UDP sockets and low-level byte formatting on the wire, distributed systems introduce a **Middleware** layer based on the **Remote Procedure Call (RPC)** paradigm (or **Remote Method Invocation - RMI** in object-oriented contexts). The primary objective of an RPC middleware is to provide **syntactic transparency**: through the automated generation of local proxy components — the **Client Stub** on the caller side and the **Server Skeleton** on the callee side — the invocation of a remote procedure adopts the exact same syntax as a standard local function call. However, as highlighted by distributed systems theory and experimentally verified in this project, it is impossible to guarantee complete **semantic transparency**: completely masking the network is unattainable, and application code must necessarily account for execution timing constraints (via _timeouts_ or _deadlines_) and communication failures.

### 1.1 The Role of Protocol Buffers (`.proto`) as an IDL and External Data Representation

In this project, **gRPC** was adopted — a modern, high-performance, open-source RPC framework originally developed by Google, which roots its architecture in a strictly **contract-first** approach based on **Protocol Buffers (Protobuf)**.

The `.proto` file simultaneously serves two distinct yet complementary architectural functions:

1. **Interface Definition Language (IDL):** it represents a declarative, language- and platform-agnostic metalanguage used to formalize the public service contract (which procedures are exposed, what data structures they accept as input, and what they return as output). From a single `.proto` file, the `protoc` compiler (along with language-specific plugins) automatically generates source code for the client _Stub_ and the server _Skeleton_. This natively enables **polyglot interoperability**: in our system, the exact same contract allows a server implemented in **Python** to communicate seamlessly with both a **Python** client and a **Java** client.
2. **External Data Representation and Binary Serialization (Marshalling / Unmarshalling):** during transmission between Stub and Skeleton, in-memory data structures must be flattened into a linear sequence of bytes (_marshalling_) and subsequently reconstructed by the receiver (_unmarshalling_), fundamentally resolving any hardware incompatibilities related to _endianness_ (_big-endian_ vs. _little-endian_). Unlike traditional text formats such as XML (used in SOAP) or JSON (common in REST APIs), which redundantly repeat textual keys in every message and require CPU-intensive lexical parsing, Protobuf adopts a **strictly binary encoding based on numeric field tags**. Each message field is assigned a unique integer identifier (e.g., `= 1`): over the network wire, the field name (e.g., `"name"`) is never transmitted, but only its binary tag along with its wire type and compactly encoded value. This dramatically shrinks the network payload size and speeds up serialization and deserialization operations by orders of magnitude.

### 1.2 Analysis of the `greeter.proto` Contract and Interface Evolution

The contract defined for the assignment, contained in the file `greeter.proto`, models the `GreeterService` service and its associated remote procedure `Greet`:

```protobuf
syntax = "proto3";

package greeter;

option java_multiple_files = true;
option java_package = "it.unibo.dss.greeter";
option java_outer_classname = "GreeterProto";

service GreeterService {
  rpc Greet (GreetRequest) returns (GreetReply);
}

message GreetRequest {
  string name = 1;
}

message GreetReply {
  string message = 1;
}
```

Analysis of this file highlights several key architectural decisions:

- **Encapsulation in `message` structures and backward/forward evolution:** although the specification conceptually requires sending a single string and receiving a greeting string, Protobuf mandates that RPC arguments and return values be encapsulated inside `message` structures (`GreetRequest` and `GreetReply`). This requirement is essential to ensure **backward compatibility** and **forward compatibility** when clients and servers evolve across independent release lifecycles. Thanks to numeric tags (`= 1`), if a future version of the service adds a second parameter (for example, `string language = 2;` inside `GreetRequest`), un-updated clients continue to function normally (the server assigns the default value `""` to the missing field), whereas any recipient using an older schema version simply skips unrecognized numeric tags during unmarshalling, preventing decoding crashes.
- **Multi-language compilation directives:** the options `java_multiple_files`, `java_package` (`it.unibo.dss.greeter`), and `java_outer_classname` instruct the `protoc` compiler on how to structure the generated packages and classes for Client 2 in Java, while being transparently ignored by the Python generator used for Server and Client 1.
- **Communication pattern and operational properties:** the signature `rpc Greet (GreetRequest) returns (GreetReply)` defines a **Unary RPC**, representing the modern transposition of the classic **Request-Reply (RR)** protocol in which the client sends a single request and awaits a single reply that also acts as an implicit acknowledgment. Furthermore, because the `Greet` procedure merely constructs and returns a string without altering any persistent server-side state, it constitutes a **Safe** and inherently **Idempotent** operation: executing it once or multiple times with the same input produces the exact same system effect — an essential property for enabling safe retry policies in the event of failure.

### 1.3 Considerations on gRPC: Comparison with REST and Synchronous/Asynchronous Models

Compared to the **REST** architectural style, which adopts a _resource-oriented_ paradigm (modeling the domain as resources identified by URIs and leveraging standard HTTP verbs such as `GET`, `POST`, `PUT`, `DELETE` with textual JSON payloads), **gRPC** proposes an _action/procedure-oriented_ paradigm specifically designed for internal _backend-to-backend_ communication among microservices requiring high throughput and low latency.

A crucial architectural aspect concerns the **synchronous vs. asynchronous** nature of gRPC, which operates across three distinct levels:

1. **Transport Layer (HTTP/2) — Intrinsically Asynchronous:** unlike HTTP/1.1 (which suffers from application-level head-of-line blocking), gRPC strictly relies on **HTTP/2**. All communications are divided into binary frames tagged with a unique _Stream ID_ (conceptually analogous to the `requestId` in theoretical Request-Reply protocols) and multiplexed over a single, persistent, full-duplex TCP connection.
2. **Application API Layer (Stub) — Both Synchronous and Asynchronous:** from the same `.proto` file, developers can choose whether to interact with the remote service in a **synchronous blocking** manner (suspending the calling thread until the Reply is received, as implemented in _Client 1_) or in an **asynchronous non-blocking** manner via callback registration (`StreamObserver`) or `Future`s (as implemented in _Client 2_).
3. **Communication Pattern Layer — Unary and Streaming:** beyond the _Unary RPC_ invocation used in this exercise, native HTTP/2 stream support allows gRPC to offer _Server Streaming_, _Client Streaming_, and _Bidirectional Streaming_ patterns, where clients and servers exchange continuous streams of messages without having to wait for a response after each individual transmission.

---

## 2. Architecture and Implementation of Server and Clients

The complete system is structured into three distinct components (`Server`, `Client1`, `Client2`), orchestrated via Docker Compose but also executable directly in a local environment.

### 2.1 Python Server: Skeleton, Real Object, and Fault Injection

In Python, the contract compilation command:

```bash
python -m grpc_tools.protoc -I. --python_out=Server --grpc_python_out=Server greeter.proto
```

generates two distinct modules:

- `greeter_pb2.py`, containing the message modeling and serialization classes (`GreetRequest` and `GreetReply`);
- `greeter_pb2_grpc.py`, containing both the client **Stub** (`GreeterServiceStub`) and the abstract class `GreeterServiceServicer`, which constitutes the **Server Skeleton**.

The main server code (`Server/server.py`) extends `GreeterServiceServicer` to provide the concrete implementation of the **Real Object** (`GreeterServiceImpl`):

```python
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
    ...
    server.wait_for_termination()
```

#### Server Considerations

- **Control Flow and Concurrency:** the gRPC server is instantiated with a `ThreadPoolExecutor` configured with 10 worker threads, enabling it to serve multiple concurrent RPC requests in parallel. When a request arrives on port `50051`, the Skeleton (`GreeterServiceServicer`) reads the HTTP/2 frames, unmarshals the binary payload into an instance of `GreetRequest`, and invokes the `Greet(self, request, context)` method of the Real Object. The latter constructs the string `f"hello {request.name} from server"` and returns a `GreetReply` object, which the Skeleton then serializes and transmits back as a Reply to the client.
- **Dynamic Fault Injection Mechanism (`_apply_fault`):** to enable thorough testing of client resilience against slow responses or outages without requiring Docker image rebuilds or server process restarts, the `_apply_fault(context)` method inspects the shared file `control/fault.txt` on every invocation (in addition to supporting command-line flags and environment variables in `Server/main.py`). Based on the file contents, the server can operate nominally (`ok`), introduce artificial latency (`delay X`), block execution indefinitely (`hang`), or immediately abort the RPC returning the standard status code `grpc.StatusCode.UNAVAILABLE` via `context.abort(...)` (`down`).

---

### 2.2 Client 1 (Python): Naive Synchronous Approach and the Fallacy of Semantic Transparency

**Client 1** (`Client1/client.py`), written in Python, implements the baseline requirements by connecting to the server and invoking the remote `Greet` method with the parameter `"Client1"`:

```python
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
```

#### Client 1 Considerations

Client 1 was deliberately designed with a **naive** approach, blindly trusting the illusion created by the Stub's syntactic transparency (`stub.Greet(...)` looks identical to a local function call) and disregarding the realities of network communication:

1. **Synchronous Blocking Invocation without a Deadline:** the call `stub.Greet(...)` does not specify any `timeout` parameter. The main thread enters an idle wait state until a response is received from the server. If the server is overloaded or enters a stall (_hang_), the client hangs indefinitely, tying up local resources.
2. **Absence of RPC Exception Handling:** the client does not wrap the remote call in a `try...except grpc.RpcError` block. Consequently, if the server is down or unreachable, the `_InactiveRpcError` exception thrown by the Stub causes an **uncontrolled crash** of the entire application process.
3. **_Maybe_ Invocation Semantics:** because no retransmission or error-verification mechanism is provided, network anomalies cause the client to fall back to the weakest fault-tolerance semantics (_Maybe_), offering no guarantees or visibility into whether the remote procedure was actually executed.

---

### 2.3 Client 2 (Java): Polyglot Interoperability, Asynchronous Invocation, and Fault Tolerance

To fulfill the project extension, **Client 2** was developed in **Java 21** (using the Gradle build system) from the exact same `greeter.proto` file. Through the `com.google.protobuf` Gradle plugin, `protoc` and the `protoc-gen-grpc-java` plugin are automatically fetched during the build phase, generating the message classes (`GreetRequest`, `GreetReply`) and the `GreeterServiceGrpc` class within the `it.unibo.dss.greeter` package.

Unlike Client 1, Client 2 (`Client2/app/src/main/java/client2/FaultTolerantAsyncClient.java`) was engineered with full awareness of the unreliable nature of distributed systems, adopting an **asynchronous non-blocking Stub** equipped with **deadlines** and explicit error handling:

```java
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import it.unibo.dss.greeter.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public class FaultTolerantAsyncClient {

    public static void greet(String host, String name) throws InterruptedException {
        ManagedChannel channel = ManagedChannelBuilder.forAddress(host, 50051)
                .usePlaintext()
                .build();
        CountDownLatch done = new CountDownLatch(1);

        GreeterServiceGrpc.GreeterServiceStub asyncStub = GreeterServiceGrpc.newStub(channel)
                .withDeadlineAfter(2, TimeUnit.SECONDS);

        GreetRequest request = GreetRequest.newBuilder().setName(name).build();

        asyncStub.greet(request, new StreamObserver<GreetReply>() {
            @Override
            public void onNext(GreetReply reply) {
                System.out.println("Response received successfully: " + reply.getMessage());
            }

            @Override
            public void onError(Throwable t) {
                Status status = Status.fromThrowable(t);
                if (status.getCode() == Status.Code.DEADLINE_EXCEEDED) {
                    System.err.println("[ASYNC ERROR] Deadline exceeded: server is too slow or overloaded.");
                } else if (status.getCode() == Status.Code.UNAVAILABLE) {
                    System.err.println("[ASYNC ERROR] Service unavailable: server might be down.");
                } else {
                    System.err.println("[ASYNC ERROR] Unexpected RPC error: " + status.getDescription());
                }
                done.countDown();
            }

            @Override
            public void onCompleted() {
                System.out.println("RPC transaction completed.");
                done.countDown();
            }
        });

        System.out.println("Request sent, waiting for callback...");

        done.await();
        channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
    }
}
```

#### Client 2 Considerations

1. **Asynchronous Non-Blocking Callback-Based Model (`StreamObserver`):** instead of using `BlockingStub` (`GreeterServiceGrpc.newBlockingStub(channel)`), Client 2 instantiates the asynchronous stub via `GreeterServiceGrpc.newStub(channel)`. When `asyncStub.greet(request, observer)` is invoked, the main thread does not block on network I/O, immediately printing `"Request sent, waiting for callback..."` (the `CountDownLatch` at the end merely prevents the CLI Java process from exiting before Netty's I/O worker thread receives the response). When the response or error frame arrives over the HTTP/2 channel, the gRPC runtime asynchronously triggers the `StreamObserver` callback methods:
   - `onNext(GreetReply reply)` upon receiving and deserializing the reply message;
   - `onCompleted()` upon orderly completion of the RPC transaction;
   - `onError(Throwable t)` if any network error, server failure, or timeout occurs.
2. **Deadline Configuration (`withDeadlineAfter(2, TimeUnit.SECONDS)`):** a strict upper bound of **2 seconds** is established for completing the entire invocation. In gRPC, the concept of a _deadline_ is far more sophisticated than a simple local socket timeout: the absolute deadline is propagated inside HTTP/2 call metadata across downstream microservice chains, allowing servers to cancel processing if the client's allotted timeframe has already elapsed.
3. **Fault Discrimination and Idempotence:** inside `onError(Throwable t)`, the exception is inspected via `io.grpc.Status` to evaluate the standardized status code:
   - `Status.Code.DEADLINE_EXCEEDED` indicates that the 2-second threshold expired without receiving a Reply (e.g., due to a slow or hung server, or severe network congestion);
   - `Status.Code.UNAVAILABLE` indicates that the service is unreachable (TCP connection refused, container stopped, or an explicit unavailable status emitted by the server).
     In both cases, the client handles the failure gracefully (_graceful degradation_) without crashing. Furthermore, because `Greet` is an **idempotent** operation, a **retry policy with exponential backoff and jitter** ($T = \text{base\_delay} \times 2^n + \text{jitter}$) could be safely incorporated directly into the `onError` handler, elevating invocation semantics from _Maybe_ to **At-least-once** without risking duplicate side effects or triggering a backend _retry storm_.

---

## 3. Testing Session and Results Analysis Across Three Scenarios

To experimentally verify the behavior of both clients, the environment was containerized using `compose.yaml`, defining a virtual network where the `server` service exposes port `50051` and mounts the `./control` directory in read-only mode to receive runtime directives issued by the `./scripts/set_fault.sh` script. Both clients (`client1` in Python and `client2` in Java) connect using the hostname `GREETER_HOST=server`.

The server was started in the background with:

```bash
docker compose up -d --build server
```

The following sections document the results observed by executing both clients across the **three defined operational scenarios**.

---

### 3.1 Scenario 1: Normal Operation (Active and Responsive Server)

In this first scenario, the server is configured in nominal mode (`./scripts/set_fault.sh ok`), responding immediately to incoming RPC requests.

#### Executed Commands and Output

```text
$ ./scripts/set_fault.sh ok
-> Server set to mode: NORMAL (immediate response)

$ docker compose run --rm client1
Response received: hello Client1 from server

$ docker compose run --rm client2
Request sent, waiting for callback...
Response received successfully: hello Client2 from server
RPC transaction completed.
```

#### Behavioral Analysis

- **Client 1 (Python):** sends the `GreetRequest(name="Client1")` message synchronously, waits a few milliseconds for round-trip completion over Docker's bridge network, and correctly prints the deserialized reply `"hello Client1 from server"`.
- **Client 2 (Java):** sends `GreetRequest(name="Client2")` via the asynchronous stub; the main thread proceeds immediately, printing `"Request sent, waiting for callback..."`. Shortly thereafter (well within the 2-second deadline), the I/O thread invokes the `onNext()` callback in sequence (printing `"Response received successfully: hello Client2 from server"`) followed by `onCompleted()` (printing `"RPC transaction completed."` and releasing the `CountDownLatch`). This validates complete **polyglot interoperability** between the Python server and the Java client derived from the single `greeter.proto` contract.

---

### 3.2 Scenario 2: Slow or Stalled Server (`delay 3` and `hang`)

In this second scenario, we evaluate both clients' resilience when the server exceeds the 2-second deadline configured on Client 2, examining both **temporary degradation** (3-second artificial latency, `./scripts/set_fault.sh delay 3`) and **indefinite stalls** (`./scripts/set_fault.sh hang`).

#### Case 2A: Slow Server (3-second delay)

```text
$ ./scripts/set_fault.sh delay 3
-> Server set to mode: SLOW (waits 3s before responding)

$ time docker compose run --rm client1
Response received: hello Client1 from server
docker compose run --rm client1  0.07s user 0.04s system 2% cpu 4.133 total

$ time docker compose run --rm client2
Request sent, waiting for callback...
[ASYNC ERROR] Deadline exceeded: server is too slow or overloaded.
docker compose run --rm client2  0.07s user 0.03s system 2% cpu 3.407 total
```

#### Case 2B: Stalled Server (infinite `hang`)

```text
$ ./scripts/set_fault.sh hang
-> Server set to mode: HANG (never responds, hangs request)

$ docker compose run --rm client2
Request sent, waiting for callback...
[ASYNC ERROR] Deadline exceeded: server is too slow or overloaded.
```

_(Note: when executing `client1` against a server in `hang` mode, the process blocks indefinitely on the terminal without producing any output until terminated externally via `SIGINT`/`SIGKILL`)._

#### Behavioral Analysis

- **Client 1 (Python):** having configured no deadline, it passively endures whatever delay the server experiences. In Case 2A, it remains blocked for the full 3-second delay before printing the reply (total container execution time ~4.1s). In Case 2B (`hang`), the absence of a timeout leads to **permanent stalling of the calling process** (_resource starvation_), demonstrating why remote calls without deadlines represent a critical anti-pattern in distributed computing.
- **Client 2 (Java):** in both subcases (3-second delay and infinite hang), upon reaching the exact **2-second** threshold defined via `.withDeadlineAfter(2, TimeUnit.SECONDS)`, the gRPC runtime aborts waiting for the RPC and invokes `onError(Throwable t)` with `Status.Code.DEADLINE_EXCEEDED`. The client intercepts the error, outputs the diagnostic log `[ASYNC ERROR] Deadline exceeded: server is too slow or overloaded.`, and gracefully tears down the gRPC channel, shielding the application from unbounded blocking.

---

### 3.3 Scenario 3: Unreachable / Down Server

In the third scenario, we analyze client behavior when the remote service is unavailable, testing both runtime failure simulation via `./scripts/set_fault.sh down` (where the server aborts the RPC with `StatusCode.UNAVAILABLE`) and physical shutdown of the server container (`docker compose down`, producing a `Connection refused` error at the TCP socket level).

#### Case 3A: Simulated Runtime Outage (`./scripts/set_fault.sh down`)

```text
$ ./scripts/set_fault.sh down
-> Server set to mode: DOWN (simulates unreachable server: UNAVAILABLE)

$ docker compose run --rm client1
Traceback (most recent call last):
  File "/app/main.py", line 4, in <module>
    run_naive_client()
    ~~~~~~~~~~~~~~~~^^
  File "/app/client.py", line 11, in run_naive_client
    response = stub.Greet(greeter_pb2.GreetRequest(name="Client1"))
  File "/usr/local/lib/python3.13/site-packages/grpc/_channel.py", line 1168, in __call__
    return _end_unary_response_blocking(state, call, False, None)
  File "/usr/local/lib/python3.13/site-packages/grpc/_channel.py", line 999, in _end_unary_response_blocking
    raise _InactiveRpcError(state)  # pytype: disable=not-instantiable
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
grpc._channel._InactiveRpcError: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "Server simulated failure (runtime fault)"
	debug_error_string = "UNAVAILABLE:Server simulated failure (runtime fault)"
>

$ docker compose run --rm client2
Request sent, waiting for callback...
[ASYNC ERROR] Service unavailable: server might be down.
```

#### Case 3B: Physically Stopped Server (`Connection refused`)

Once the server container is completely stopped (`docker compose down`), local execution of both clients yields an entirely consistent outcome:

```text
$ ../.venv/bin/python Client1/main.py
Traceback (most recent call last):
  ...
grpc._channel._InactiveRpcError: <_InactiveRpcError of RPC that terminated with:
	status = StatusCode.UNAVAILABLE
	details = "failed to connect to all addresses; last error: UNKNOWN: ipv4:127.0.0.1:50051: Failed to connect to remote host: Connection refused"
	debug_error_string = "UNAVAILABLE:failed to connect to all addresses; last error: UNKNOWN: ipv4:127.0.0.1:50051: Failed to connect to remote host: Connection refused"
>

$ cd Client2 && ./gradlew -q :app:run
Request sent, waiting for callback...
[ASYNC ERROR] Service unavailable: server might be down.
```

#### Behavioral Analysis

- **Client 1 (Python):** erroneously assuming remote invocations behave like local in-memory function calls (semantic transparency), it fails to catch `grpc.RpcError`. When the connection is refused or the server returns `StatusCode.UNAVAILABLE`, the Stub throws `_InactiveRpcError`, causing the **Python process to crash abruptly** with a non-zero exit code and an unhandled stack trace.
- **Client 2 (Java):** experiences no crash. The connection failure is reported asynchronously to the `onError(Throwable t)` method of `StreamObserver`. There, the client extracts the `Status` from the exception, recognizes the `Status.Code.UNAVAILABLE` code, cleanly logs `[ASYNC ERROR] Service unavailable: server might be down.`, and releases channel resources before terminating cleanly.

---

## 4. Comparative Summary and Conclusions

The following table summarizes the observed behavior of both clients across the three experimental scenarios:

| Operational Scenario | Server Status | **Client 1** Behavior (Python, Naive Synchronous) | **Client 2** Behavior (Java, Fault-Tolerant Asynchronous with 2s Deadline) |
| :--- | :--- | :--- | :--- |
| **1. Normal (`ok`)** | Immediate response | Receives and prints `"hello Client1 from server"` synchronously in a blocking manner. | Sends request without blocking the caller thread; receives `"hello Client2 from server"` in `onNext()` callback and closes in `onCompleted()`. |
| **2A. Slow Server (`delay 3`)** | Responds after 3s | Stays blocked in idle wait for the entire 3s until receiving the response. | Deadline expires after **2s**: terminates waiting and invokes `onError()`, detecting `Status.Code.DEADLINE_EXCEEDED`. |
| **2B. Stalled Server (`hang`)** | Never responds | **Infinite block (permanent hang)** of calling process. | Deadline expires after **2s**: invokes `onError()` with `Status.Code.DEADLINE_EXCEEDED` and terminates cleanly. |
| **3. Server Down (`down` / stopped)** | Unreachable / `Connection refused` | **Uncontrolled crash** of the process with unhandled exception `_InactiveRpcError` (`StatusCode.UNAVAILABLE`). | No crash: intercepts error in `onError()` callback, identifies `Status.Code.UNAVAILABLE`, and orderly closes the channel. |

In conclusion, this laboratory activity experimentally confirmed that **gRPC and Protocol Buffers** provide outstanding **syntactic transparency** and seamless **multi-language interoperability** (Python/Java) via the automatic generation of Stubs and Skeletons from a single `.proto` contract. At the same time, the direct comparison between _Client 1_ and _Client 2_ demonstrates that in distributed systems **semantic transparency does not exist**: building resilient distributed applications requires complementing Stubs with explicit fault-tolerance mechanisms, such as non-blocking invocations, systematic configuration of **deadlines**, and granular handling of RPC error status codes (`DEADLINE_EXCEEDED`, `UNAVAILABLE`).

