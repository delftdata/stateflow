from src.serialization.serde import SerDe
from src.dataflow.event import Event
from typing import Dict
import pickle


class PickleSerializer(SerDe):
    def serialize_event(self, event: Event) -> bytes:
        return pickle.dumps(event)

    def deserialize_event(self, event: bytes) -> Event:
        return pickle.loads(event)

    def serialize_dict(self, dictionary: Dict) -> bytes:
        return pickle.dumps(dictionary)

    def deserialize_dict(self, dictionary: bytes) -> Dict:
        return pickle.loads(dictionary)
