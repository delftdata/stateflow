from stateflow.client.stateflow_client import StateflowClient, StateflowFuture, T
from stateflow.dataflow.dataflow import Dataflow
from stateflow.dataflow.stateful_operator import StatefulOperator
from stateflow.serialization.pickle_serializer import SerDe, PickleSerializer
from stateflow.dataflow.dataflow import (
    IngressRouter,
    EgressRouter,
    Route,
    RouteDirection,
    EventType,
)
from stateflow.dataflow.event import Event
from typing import Dict, ByteString
import time
import pandas as pd


class LocalRuntime(StateflowClient):
    def __init__(
        self,
        flow: Dataflow,
        experiment: pd.DataFrame,
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
        [op.set_experiment_client(self) for op in flow.operators]

        self.state: Dict[str, ByteString] = {}
        self.return_future: bool = return_future

        self.experiment: pd.DataFrame = experiment
        self.experiment_id: str = ""
        self.repetition: int = 0
        self.state_size: str = ""
        self.experiment_mode: bool = False

    def enable_experiment_mode(self):
        self.experiment_mode = True

    def set_repetition(self, rep: int):
        self.repetition = rep

    def set_experiment_id(self, experiment_id: str):
        self.experiment_id = experiment_id

    def set_state_size_experiment(self, state_size: str):
        self.state_size = state_size

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
        start = time.perf_counter()
        route: Route = self.ingress_router.route(event)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        self.add_to_last_row("ROUTING_DURATION", time_ms)

        if route.direction == RouteDirection.INTERNAL:
            invocation = self.invoke_operator(route)
            start = time.perf_counter()
            routing = self.egress_router.route_and_serialize(invocation)
            end = time.perf_counter()
            time_ms = (end - start) * 1000
            self.add_to_last_row("ROUTING_DURATION", time_ms)

            return routing
        elif route.direction == RouteDirection.EGRESS:
            start = time.perf_counter()
            routing = self.egress_router.route_and_serialize(route.value)
            end = time.perf_counter()
            time_ms = (end - start) * 1000
            self.add_to_last_row("ROUTING_DURATION", time_ms)
            return routing
        else:
            return route

    def add_to_last_row(self, action: str, to_add: int):
        if not self.experiment_mode:
            return

        last_row_id = self.experiment.index[-1]
        self.experiment.loc[last_row_id, action] = (
            self.experiment.loc[last_row_id, action] + to_add
        )

    def execute_event(self, event: Event) -> Event:
        # Prep first row
        if self.experiment_mode:
            self.experiment.loc[len(self.experiment)] = [
                self.experiment_id,
                self.repetition,
                self.state_size,
                0,
                0,
                0,
                0,
            ]

        start = time.perf_counter()
        parsed_event: Event = self.ingress_router.parse(event)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        self.add_to_last_row("EVENT_SERIALIZATION_DURATION", time_ms)

        return_route: Route = self.handle_invocation(parsed_event)

        while return_route.direction != RouteDirection.CLIENT:
            return_route = self.handle_invocation(return_route.value)

        # We just serialize for timings
        start = time.perf_counter()
        self.serializer.serialize_event(return_route.value)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        self.add_to_last_row("EVENT_SERIALIZATION_DURATION", time_ms)

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
