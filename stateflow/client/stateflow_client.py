from typing import Optional, Any, List
from stateflow.client.future import StateflowFuture, T
from stateflow.serialization.json_serde import SerDe, JsonSerializer
from stateflow.dataflow.event import Event, EventType
from stateflow.dataflow.address import FunctionAddress, FunctionType
import uuid


class StateflowClient:
    from stateflow.dataflow.dataflow import Dataflow

    def __init__(self, flow: Dataflow, serializer: SerDe = JsonSerializer()):
        self.flow = flow
        self.serializer: SerDe = serializer

    def send(self, event: Event) -> StateflowFuture[T]:
        pass

    def find(self, clasz, key: str) -> StateflowFuture[Optional[Any]]:
        event_id = str(uuid.uuid4())
        event_type = EventType.Request.FindClass
        fun_address = FunctionAddress(FunctionType.create(clasz.descriptor), key)
        payload = {}

        return self.send(Event(event_id, fun_address, event_type, payload), clasz)

    def await_futures(self, future_list: List[StateflowFuture[T]]):
        waiting_for = [fut for fut in future_list if not fut.is_completed]
        while len(waiting_for):
            waiting_for = [fut for fut in future_list if not fut.is_completed]
