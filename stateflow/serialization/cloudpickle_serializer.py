import struct

from stateflow.serialization.serde import SerDe
from stateflow.dataflow.event import Event
from typing import Dict
import cloudpickle


class CloudpickleSerializer(SerDe):
    def serialize_event(self, event: Event) -> bytes:
        return struct.pack('>H', 0) + cloudpickle.dumps(event)

    def deserialize_event(self, event: bytes) -> Event:
        return cloudpickle.loads(event)

    def serialize_dict(self, dictionary: Dict) -> bytes:
        return struct.pack('>H', 0) + cloudpickle.dumps(dictionary)

    def deserialize_dict(self, dictionary: bytes) -> Dict:
        return cloudpickle.loads(dictionary)
