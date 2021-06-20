from src.client.stateflow_client import StateflowClient, StateflowFuture, T
from src.runtime.runtime import Runtime
from src.dataflow.dataflow import Dataflow
from src.dataflow.stateful_operator import StatefulOperator
from src.serialization.pickle_serializer import SerDe, PickleSerializer
from src.dataflow.dataflow import (
    IngressRouter,
    EgressRouter,
    Route,
    RouteDirection,
    EventType,
)
from src.dataflow.event import Event
import datetime
from typing import Dict, ByteString
import time


class LocalRuntime(StateflowClient):
    def __init__(
        self,
        flow: Dataflow,
        serializer: SerDe = PickleSerializer(),
        return_future: bool = False,
    ):
        super().__init__(flow, serializer)

        self.flow: Dataflow = flow
        self.serializer: SerDe = serializer

        self.ingress_router = IngressRouter(self.serializer)
        self.egress_router = EgressRouter(self.serializer, serialize_on_return=False)

        self.operators = {
            operator.function_type.get_full_name(): operator
            for operator in self.flow.operators
        }

        # Set the wrapper.
        [op.meta_wrapper.set_client(self) for op in flow.operators]

        self.state: Dict[str, ByteString] = {}
        self.return_future: bool = return_future

    def invoke_operator(self, route: Route) -> Event:
        event: Event = route.value

        operator_name: str = route.route_name
        operator: StatefulOperator = self.operators[operator_name]

        if event.event_type == EventType.Request.InitClass and route.key is None:
            new_event = operator.handle_create(event)
            return self.invoke_operator(
                Route(
                    RouteDirection.INTERNAL,
                    operator_name,
                    new_event.fun_address.key,
                    new_event,
                )
            )
        else:
            full_key: str = f"{operator_name}_{route.key}"
            operator_state = self.state.get(full_key)
            return_event, updated_state = operator.handle(event, operator_state)
            self.state[full_key] = updated_state

            return return_event

    def handle_invocation(self, event: Event) -> Route:
        route: Route = self.ingress_router.route(event)

        if route.direction == RouteDirection.INTERNAL:
            return self.egress_router.route_and_serialize(self.invoke_operator(route))
        elif route.direction == RouteDirection.EGRESS:
            return self.egress_router.route_and_serialize(route.value)
        else:
            return route

    def execute_event(self, event: Event) -> Event:
        parsed_event: Event = self.ingress_router.parse(event)
        return_route: Route = self.handle_invocation(parsed_event)

        while return_route.direction != RouteDirection.CLIENT:
            return_route = self.handle_invocation(return_route.value)

        return return_route.value

    def send(self, event: Event, return_type: T = None) -> T:
        return_event = self.execute_event(self.serializer.serialize_event(event))
        future = StateflowFuture(
            event.event_id, time.time(), event.fun_address, return_type
        )

        future.complete(return_event)
        if self.return_future:
            return future
        else:
            return future.get()
