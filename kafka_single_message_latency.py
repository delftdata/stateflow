from confluent_kafka import Producer, Consumer
import uuid
import time
import statistics
import pickle

prod = Producer({"bootstrap.servers": "localhost:9092"})
cons = Consumer(
    {
        "bootstrap.servers": "localhost:9092",
        "group.id": str(uuid.uuid4()),
        "auto.offset.reset": "latest",
    }
)
cons.subscribe(["latency-experiment"])
all_times = []
for i in range(0, 10000):
    val = pickle.dumps(bytearray([1] * 50000))
    start = time.perf_counter()
    prod.produce("latency-experiment", key=f"message-{i}", value=val)
    msg = cons.poll()

    if msg.error():
        raise RuntimeError(msg.error())
    else:
        print(msg.key())

    end = time.perf_counter()
    time_ms = (end - start) * 1000
    all_times.append(time_ms)

print(f"Mean: {statistics.mean(all_times)}")
print(f"Stdev: {statistics.stdev(all_times)}")
