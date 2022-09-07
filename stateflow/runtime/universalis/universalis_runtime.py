from typing import List

from universalis.common.local_state_backends import LocalStateBackend
from universalis.common.stateflow_graph import StateflowGraph
from universalis.common.stateful_function import StatefulFunction
from universalis.universalis import Universalis
from universalis.common.operator import Operator
from universalis.common.logging import logging
from universalis.common.base_state import ReadUncommitedException
from universalis.common.serialization import pickle_deserialization


from stateflow.dataflow.dataflow import (
    Dataflow,
    RouteDirection,
    Route,
    EventType, IngressRouter, EgressRouter,
)
from stateflow.dataflow.event import Event
from stateflow.dataflow.event_flow import EventFlowGraph
from stateflow.dataflow.stateful_operator import StatefulOperator

from stateflow.runtime.runtime import Runtime
from stateflow.serialization.pickle_serializer import PickleSerializer
from stateflow.serialization.serde import SerDe


class UniversalisRuntime(Runtime):

    def __init__(self,
                 dataflow: Dataflow,
                 universalis_interface: Universalis,
                 graph_name: str,
                 n_partitions: int,
                 serializer: SerDe = PickleSerializer()):
        super().__init__()
        self.dataflow = dataflow

        self.serializer = serializer
        self.ingress_router: IngressRouter = IngressRouter(self.serializer)
        self.egress_router: EgressRouter = EgressRouter(self.serializer, serialize_on_return=False)

        self.universalis_interface = universalis_interface

        self.graph: StateflowGraph = StateflowGraph(graph_name, operator_state_backend=LocalStateBackend.REDIS)
        self.n_partitions = n_partitions

        self.operators = self.dataflow.operators
        self.operators_dict = {}

        self.pipeline_initialized: bool = False

        self.universalis_operators: dict[str, Operator] = {}

    def _add_ping_endpoint(self) -> Operator:

        ingress_router = self.ingress_router

        class UniversalisPingOperator(StatefulFunction):

            async def run(self, event):
                if event.event_type != EventType.Request.Ping:
                    raise AttributeError(
                        f"Expected a Ping but got an {event.event_type}."
                    )

                outgoing_route: Route = ingress_router.route(event)

                return outgoing_route.value
        universalis_ping_operator = Operator("global_Ping", n_partitions=1)
        universalis_ping_operator.register_stateful_function(UniversalisPingOperator)
        self.universalis_operators["global_Ping"] = universalis_ping_operator
        return universalis_ping_operator

    def _add_operator_create_endpoints(self) -> List[Operator]:
        universalis_operators = []

        ingress_router = self.ingress_router

        # For each stateful function in the dataflow graph of Statefun, we create an endpoint in Universalis
        for operator in self.operators:
            self.operators_dict[f"{operator.function_type.get_safe_full_name()}_create"] = operator
            operators_dict = self.operators_dict

            class UniversalisCreateOperator(StatefulFunction):

                async def run(self, event: Event):

                    route: Route = ingress_router.route(event)
                    operator_name: str = route.route_name.replace("/", "_")
                    outgoing_event: Event = operators_dict[operator_name].handle_create(event)
                    # operator_name: str = outgoing_event.fun_address.function_type.get_safe_full_name()

                    await self.call_remote_function_no_response(operator_name,
                                                                "UniversalisOperator",
                                                                outgoing_event.fun_address.key,
                                                                (outgoing_event,))

            universalis_operator = Operator(f"{operator.function_type.get_safe_full_name()}_create",
                                            n_partitions=self.n_partitions)
            universalis_operator.register_stateful_function(UniversalisCreateOperator)
            universalis_operators.append(universalis_operator)
            self.universalis_operators[f"{operator.function_type.get_safe_full_name()}_create"] = universalis_operator

        return universalis_operators

    def _add_operator_endpoints(self) -> List[Operator]:
        universalis_operators = []

        ingress_router = self.ingress_router
        egress_router = self.egress_router

        # For each stateful function in the dataflow graph of Statefun, we create an endpoint in Universalis
        for operator in self.operators:
            self.operators_dict[operator.function_type.get_safe_full_name()] = operator
            operators_dict = self.operators_dict

            class UniversalisOperator(StatefulFunction):

                async def run(self, event: Event):
                    # logging.warning(f'Event payload: {event.payload}')
                    route: Route = ingress_router.route(event)

                    stateful_operator: StatefulOperator = operators_dict[
                        event.fun_address.function_type.get_safe_full_name()
                    ]

                    states_key = route.key

                    try:
                        # logging.warning(f'Retrieving state for key: {states_key}')
                        current_state = await self.get(states_key)
                        # current_state_to_print = pickle_deserialization(current_state)
                    except ReadUncommitedException:
                        # key does not exist in state
                        current_state = {}
                        # current_state_to_print = {}

                    # logging.warning(f'Running stateflow function: '
                    #                 f'{event.fun_address.function_type.get_safe_full_name()} '
                    #                 f'with state: {current_state_to_print}')
                    # run the function
                    return_event, updated_state = stateful_operator.handle(event, current_state)

                    if updated_state is not current_state and updated_state is not None:
                        await self.put(route.key, updated_state)

                    # if updated_state is not None:
                    #     logging.warning(f'Updating the state with: {pickle_deserialization(updated_state)} '
                    #                     f'at key: {states_key}')

                    # logging.warning(f'outgoing_event key: {return_event.fun_address.key}')
                    # Routing
                    egress_route: Route = egress_router.route_and_serialize(return_event)

                    if egress_route.direction == RouteDirection.CLIENT:
                        # logging.warning(f'Returning to client')
                        return egress_route.value

                    # logging.warning(f'egress_route.value key: {egress_route.value.fun_address.key}')
                    ingress_route: Route = ingress_router.route(egress_route.value)

                    if ingress_route.direction == RouteDirection.INTERNAL:
                        # logging.warning(f'Sending internal message')
                        # Fire and forget to other stateful function
                        other_operator_name = ingress_route.route_name.replace("/", "_")
                        other_operator_key = ingress_route.key
                        # logging.warning(f'Calling remote from key: {event.fun_address.key} '
                        #                 f'to key: {other_operator_key}')
                        await self.call_remote_function_no_response(other_operator_name,
                                                                    "UniversalisOperator",
                                                                    other_operator_key,
                                                                    (ingress_route.value, ))
                    elif ingress_route.direction == RouteDirection.EGRESS:
                        # logging.warning(f'Returning to client')
                        return ingress_route.value

            universalis_operator = Operator(operator.function_type.get_safe_full_name(), n_partitions=self.n_partitions)
            universalis_operator.register_stateful_function(UniversalisOperator)
            universalis_operators.append(universalis_operator)
            self.universalis_operators[operator.function_type.get_safe_full_name()] = universalis_operator

        return universalis_operators

    # def _add_operator_endpoints(self) -> List[Operator]:
    #     universalis_operators = []
    #
    #     ingress_router = self.ingress_router
    #     egress_router = self.egress_router
    #
    #     # For each stateful function in the dataflow graph of Statefun, we create an endpoint in Universalis
    #     for operator in self.operators:
    #         self.operators_dict[operator.function_type.get_safe_full_name()] = operator
    #         operators_dict = self.operators_dict
    #
    #         class UniversalisOperator(StatefulFunction):
    #
    #             async def run(self, event: Event):
    #                 logging.warning(f'Event payload: {event.payload}')
    #                 route: Route = ingress_router.route(event)
    #
    #                 event: Event = route.value
    #
    #                 stateful_operator: StatefulOperator = operators_dict[
    #                     event.fun_address.function_type.get_safe_full_name()
    #                 ]
    #
    #                 if "flow" in event.payload:
    #                     flow_graph: EventFlowGraph = event.payload["flow"]
    #                     current_node = flow_graph.current_node
    #                     states_key = current_node.fun_addr.key
    #                 else:
    #                     states_key = route.key
    #
    #                 try:
    #                     logging.warning(f'Retrieving state for key: {states_key}')
    #                     current_state = await self.get(states_key)
    #                     current_state_to_print = pickle_deserialization(current_state)
    #                 except ReadUncommitedException:
    #                     # key does not exist in state
    #                     current_state = None
    #                     current_state_to_print = None
    #
    #                 logging.warning(f'Running stateflow function: '
    #                                 f'{event.fun_address.function_type.get_safe_full_name()} '
    #                                 f'with state: {current_state_to_print}')
    #                 # run the function
    #                 return_event, updated_state = stateful_operator.handle(event, current_state)
    #
    #                 if updated_state is not current_state and updated_state is not None:
    #                     await self.put(route.key, updated_state)
    #
    #                 if updated_state is not None:
    #                     logging.warning(f'Updating the state with: {pickle_deserialization(updated_state)} '
    #                                     f'at key: {states_key}')
    #
    #                 logging.warning(f'outgoing_event key: {return_event.fun_address.key}')
    #                 # Routing
    #                 egress_route: Route = egress_router.route_and_serialize(return_event)
    #
    #                 if egress_route.direction == RouteDirection.CLIENT:
    #                     logging.warning(f'Returning to client')
    #                     return egress_route.value
    #
    #                 logging.warning(f'egress_route.value key: {egress_route.value.fun_address.key}')
    #                 ingress_route: Route = ingress_router.route(egress_route.value)
    #
    #                 if ingress_route.direction == RouteDirection.INTERNAL:
    #                     logging.warning(f'Sending internal message')
    #                     # Fire and forget to other stateful function
    #                     other_operator_name = ingress_route.route_name.replace("/", "_")
    #                     other_operator_key = ingress_route.key
    #                     logging.warning(f'Calling remote from key: {event.fun_address.key} '
    #                                     f'to key: {other_operator_key}')
    #                     await self.call_remote_function_no_response(other_operator_name,
    #                                                                 "UniversalisOperator",
    #                                                                 other_operator_key,
    #                                                                 (ingress_route.value, ))
    #                 elif ingress_route.direction == RouteDirection.EGRESS:
    #                     logging.warning(f'Returning to client')
    #                     return ingress_route.value
    #
    #         universalis_operator = Operator(operator.function_type.get_safe_full_name(), n_partitions=self.n_partitions)
    #         universalis_operator.register_stateful_function(UniversalisOperator)
    #         universalis_operators.append(universalis_operator)
    #         self.universalis_operators[operator.function_type.get_safe_full_name()] = universalis_operator
    #
    #     return universalis_operators

    def _setup_pipeline(self):
        [self.graph.add_operator(op) for op in self._add_operator_endpoints() + self._add_operator_create_endpoints() + [self._add_ping_endpoint()]]

    async def run(self, modules: tuple = None, async_execution=False):
        if not self.pipeline_initialized:
            self._setup_pipeline()
        print("Now running Universalis runtime!", flush=True)

        await self.universalis_interface.submit(self.graph, modules)
        return self.universalis_operators
