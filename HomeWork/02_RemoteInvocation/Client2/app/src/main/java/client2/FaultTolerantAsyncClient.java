import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import it.unibo.dss.greeter.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Asynchronous gRPC client with deadline and fault-tolerant error handling.
 */
public class FaultTolerantAsyncClient {

    /**
     * Sends an asynchronous greet request with a deadline.
     *
     * @param host server hostname or IP address
     * @param name name to send in the greeting request
     * @throws InterruptedException if interrupted while awaiting response or channel termination
     */
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
