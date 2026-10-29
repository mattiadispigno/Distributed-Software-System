# Distributed Systems — University of Bologna (UniBo)

This repository contains academic materials, lecture slides, and practical assignments for the **Distributed Systems** course at the University of Bologna.

---

## Homework & Laboratory Assignments

All assignments and practical implementations are organized inside the [`HomeWork/`](./HomeWork) folder:

- **[`HomeWork/01_Location Transparency in Distributed Storage.pdf`](./HomeWork/01_Location%20Transparency%20in%20Distributed%20Storage.pdf)**:
  Study and report on location transparency concepts and mechanisms in distributed storage architectures.

- **[`HomeWork/02_RemoteInvocation/`](./HomeWork/02_RemoteInvocation)**:
  Laboratory assignment on Remote Procedure Call (RPC) using **gRPC** and **Protocol Buffers** (`greeter.proto`):
  - **Server (Python)**: `GreeterService` with dynamic runtime fault injection (delays, hangs, service downtime).
  - **Client 1 (Python)**: Naive synchronous blocking invocation demonstrating semantic transparency limitations.
  - **Client 2 (Java 21)**: Resilient asynchronous non-blocking invocation with deadlines (2s) and error classification.
  - Containerized with Docker Compose. Refer to [`HomeWork/02_RemoteInvocation/README.md`](./HomeWork/02_RemoteInvocation/README.md) for quick start instructions and [`HomeWork/02_RemoteInvocation/docs/documentation.md`](./HomeWork/02_RemoteInvocation/docs/documentation.md) for full architectural documentation.
