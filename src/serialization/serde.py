from src.dataflow.event import Event, FunctionAddress
from typing import Dict


class SerDe:
    def serialize_event(self, event: Event) -> bytes:
        pass

    def deserialize_event(self, event: bytes) -> Event:
        pass

    def serialize_dict(self, dict: Dict) -> bytes:
        pass

    def deserialize_dict(self, dict: bytes) -> Dict:
        pass
