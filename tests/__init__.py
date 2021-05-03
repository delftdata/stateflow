import pytest
from tests.kafka import KafkaImage


@pytest.fixture(scope="session")
def kafka():
    kafka_image = KafkaImage()
    yield kafka_image.run()
    kafka_image.stop()
