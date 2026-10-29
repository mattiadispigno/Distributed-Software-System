public class Main {
    public static void main(String[] args) throws InterruptedException {
        String host = System.getenv().getOrDefault("GREETER_HOST", "localhost");
        FaultTolerantAsyncClient.greet(host, "Client2");
    }
}
