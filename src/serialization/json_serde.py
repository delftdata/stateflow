from src.serialization.serde import SerDe, Event, Dict
from src.dataflow.args import Arguments
from src.dataflow.event import EventType, FunctionAddress
from src.dataflow.event_flow import EventFlowNode
import ujson


class JsonSerializer(SerDe):
    def serialize_event(self, event: Event) -> bytes:
        event_id: str = event.event_id
        event_type: str = event.event_type.value
        fun_address: dict = event.fun_address.to_dict()
        payload: dict = event.payload

        for item in payload:
            if hasattr(payload[item], "to_dict"):
                payload[item] = payload[item].to_dict()

        if "flow" in payload:
            for id, value in payload["flow"].items():
                payload["flow"][id]["node"] = payload["flow"][id]["node"].to_dict()

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "fun_address": fun_address,
            "payload": payload,
        }

        return self.serialize_dict(event)

    def deserialize_event(self, event: bytes) -> Event:
        json = self.deserialize_dict(event)

        event_id: str = json["event_id"]
        event_type: str = EventType.from_str(json["event_type"])
        fun_address: dict = FunctionAddress.from_dict(json["fun_address"])
        payload: dict = json["payload"]

        if "args" in payload:
            payload["args"] = Arguments.from_dict(json["payload"]["args"])

        if "flow" in payload:
            for id, value in payload["flow"].items():
                payload["flow"][id]["node"] = EventFlowNode.from_dict(
                    payload["flow"][id]["node"]
                )

        return Event(event_id, fun_address, event_type, payload)

    def serialize_dict(self, dictionary: Dict) -> bytes:
        return ujson.encode(dictionary)

    def deserialize_dict(self, dictionary: bytes) -> Dict:
        return ujson.decode(dictionary)
