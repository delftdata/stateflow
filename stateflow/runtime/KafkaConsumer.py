from __future__ import division, print_function

from apache_beam import PTransform, ParDo, DoFn, Create, combiners, RestrictionProvider
from typing import Tuple, ByteString
from apache_beam.transforms.userstate import (
    TimerSpec,
    TimeDomain,
    on_timer,
    BagStateSpec,
    CombiningValueStateSpec,
    ReadModifyWriteStateSpec,
)
import time
from apache_beam.io.restriction_trackers import OffsetRange
from apache_beam.coders import VarIntCoder, TupleCoder, StrUtf8Coder, BytesCoder
from apache_beam.utils.timestamp import Timestamp, Duration
from kafka import KafkaConsumer, KafkaProducer
from confluent_kafka import Consumer, TopicPartition, OFFSET_END
from confluent_kafka.admin import (
    AdminClient,
    ClusterMetadata,
    TopicMetadata,
    PartitionMetadata,
)
import confluent_kafka


class KafkaConsume(PTransform):
    """A :class:`~apache_beam.transforms.ptransform.PTransform` for reading from an Apache Kafka topic. This is a streaming
    Transform that never returns. The transform uses `KafkaConsumer` from the
    `kafka` python library.

    It outputs a :class:`~apache_beam.pvalue.PCollection` of
    ``key-values:s``, each object is a Kafka message in the form (msg-key, msg)

    Args:
        consumer_config (dict): the kafka consumer configuration. The topic to
            be subscribed to should be specified with a key called 'topic'. The
            remaining configurations are those of `KafkaConsumer` from the
            `kafka` python library.
        value_decoder (function): Optional function to decode the consumed
            message value. If not specified, "bytes.decode" is used by default.
            "bytes.decode" which assumes "utf-8" encoding.

    Examples:
        Consuming from a Kafka Topic `notifications` ::

            import apache_beam as beam
            from apache_beam.options.pipeline_options import PipelineOptions
            from beam_nuggets.io import kafkaio

            consumer_config = {"topic": "notifications",
                               "bootstrap_servers": "localhost:9092",
                               "group_id": "notification_consumer_group"}

            with beam.Pipeline(options=PipelineOptions()) as p:
                notifications = p | "Reading messages from Kafka" >> kafkaio.KafkaConsume(
                    consumer_config=consumer_config,
                    value_decoder=bytes.decode,  # optional
                )
                notifications | 'Writing to stdout' >> beam.Map(print)

        The output will be something like ::

            ("device 1", {"status": "healthy"})
            ("job #2647", {"status": "failed"})

        Where the first element of the tuple is the Kafka message key and the second element is the Kafka message being passed through the topic
    """

    def __init__(
        self, consumer_config, timeout=-1, value_decoder=None, *args, **kwargs
    ):
        """Initializes ``KafkaConsume``"""
        super(KafkaConsume, self).__init__()
        self._consumer_args = dict(
            consumer_config=consumer_config,
            value_decoder=value_decoder,
            timeout=timeout,
        )

    def expand(self, pcoll):
        return (
            pcoll
            | Create([("key", self._consumer_args)])
            | ParDo(_ConsumeKafkaTopic(self._consumer_args))
        )


class _ConsumeKafkaTopic(DoFn):
    """Internal ``DoFn`` to read from Kafka topic and return messages"""

    BUFFER_TIMER = TimerSpec("buffer_timer", TimeDomain.REAL_TIME)
    STALE_TIMER = TimerSpec("stale_timer", TimeDomain.REAL_TIME)
    OFFSET_STATE = ReadModifyWriteStateSpec("offsets", StrUtf8Coder())

    def __init__(self, consumer_args):
        self.consumer_config = consumer_args.pop("consumer_config")
        self.topic = self.consumer_config.pop("topic")
        self.timeout = consumer_args.pop("timeout")
        self.value_decoder = consumer_args.pop("value_decoder") or bytes.decode
        self.max_buffer_size = 1

        self.consumer: Consumer = None

    def process(
        self,
        element_pair,
    ):
        if self.timeout == -1:
            self.consumer = Consumer(**self.consumer_config)
            self.consumer.subscribe(topics=self.topic)
            while True:
                msg = self.consumer.poll(0.1)
                if msg is None:
                    continue

                if msg.error():
                    print("Consumer error: {}".format(msg.error()))
                    continue

                yield msg.key(), msg.value()
        else:
            print(f"Now starting Kafka with a timeout of {self.timeout}")
            start_time = time.time() + self.timeout
            self.consumer = Consumer(**self.consumer_config)
            self.consumer.subscribe(topics=self.topic)
            while True:
                if time.time() >= start_time:
                    print("Now returning due to timeout.")
                    return
                msg = self.consumer.poll(0.1)
                if msg is None:
                    continue

                if msg.error():
                    print("Consumer error: {}".format(msg.error()))
                    continue

                yield msg.key(), msg.value()


class KafkaProduce(PTransform):
    """A :class:`~apache_beam.transforms.ptransform.PTransform` for pushing messages
    into an Apache Kafka topic. This class expects a tuple with the first element being the message key
    and the second element being the message. The transform uses `KafkaProducer`
    from the `kafka` python library.

    Args:
        topic: Kafka topic to publish to
        servers: list of Kafka servers to listen to

    Examples:
        Examples:
        Pushing message to a Kafka Topic `notifications` ::

            from __future__ import print_function
            import apache_beam as beam
            from apache_beam.options.pipeline_options import PipelineOptions
            from beam_nuggets.io import kafkaio

            with beam.Pipeline(options=PipelineOptions()) as p:
                notifications = (p
                                 | "Creating data" >> beam.Create([('dev_1', '{"device": "0001", status": "healthy"}')])
                                 | "Pushing messages to Kafka" >> kafkaio.KafkaProduce(
                                                                                        topic='notifications',
                                                                                        servers="localhost:9092"
                                                                                    )
                                )
                notifications | 'Writing to stdout' >> beam.Map(print)

        The output will be something like ::

            ("dev_1", '{"device": "0001", status": "healthy"}')

        Where the key is the Kafka topic published to and the element is the Kafka message produced
    """

    def __init__(self, topic=None, servers="127.0.0.1:9092"):
        """Initializes ``KafkaProduce``"""
        super(KafkaProduce, self).__init__()
        self._attributes = dict(topic=topic, servers=servers)

    def expand(self, pcoll):
        return pcoll | ParDo(_ProduceKafkaMessage(self._attributes))


class _ProduceKafkaMessage(DoFn):
    """Internal ``DoFn`` to publish message to Kafka topic"""

    def __init__(self, attributes, *args, **kwargs):
        super(_ProduceKafkaMessage, self).__init__(*args, **kwargs)
        self.attributes = attributes

    def start_bundle(self):
        self._producer = KafkaProducer(bootstrap_servers=self.attributes["servers"])

    def finish_bundle(self):
        self._producer.close()

    def process(self, element):
        try:
            self._producer.send(
                self.attributes["topic"], element[1], key=element[0].encode()
            )
            yield element
        except Exception as e:
            raise e
