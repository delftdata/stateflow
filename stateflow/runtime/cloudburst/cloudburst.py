from cloudburst.client.client import CloudburstConnection, CloudburstFuture
from stateflow.runtime.runtime import Runtime
from stateflow.dataflow.dataflow import (
    Dataflow,
    Route,
    IngressRouter,
    EgressRouter,
    Event,
    RouteDirection,
)
from stateflow.dataflow.stateful_operator import StatefulOperator
from stateflow.serialization.pickle_serializer import SerDe, PickleSerializer


class CloudBurstRuntime(Runtime):
    def __init__(
        self,
        flow: Dataflow,
        cloudburst_ip: str,
        client_ip: str,
        serializer: SerDe = PickleSerializer(),
    ):
        self.dataflow: Dataflow = flow
        self.operators = self.dataflow.operators

        self.cloudburst_ip: str = cloudburst_ip
        self.serializer: SerDe = serializer

        self.cloudb: CloudburstConnection = CloudburstConnection(
            cloudburst_ip, client_ip
        )

        # All (incoming) events are send to a router,
        # which then calls all functions/dags and finally returns to the client.
        self._register_classes()
        self._register_routers()

    def _register_classes(self):
        for operator in self.operators:
            op: StatefulOperator = operator

            class CloudBurstCreateOperator:
                def __init__(self, op: StatefulOperator):
                    self.operator = op

                def run(self, cloudburst_client, route: Route):
                    return self.operator.handle_create(route.event)

            class CloudBurstOperator:
                def __init__(self, op: StatefulOperator):
                    self.operator = op

                def run(self, cloudburst_client, route: Route):
                    operator_state = cloudburst_client.get_object(route.key)
                    return_event, updated_state = self.operator.handle(
                        route.value, operator_state
                    )

                    if updated_state is not operator_state:
                        cloudburst_client.put_object(route.key, updated_state)

                    return return_event

            self.cloudb.register(
                (CloudBurstCreateOperator, op),
                f"{op.function_type.get_full_name()}_create",
            )
            self.cloudb.register(
                (CloudBurstOperator, op), f"{op.function_type.get_full_name()}"
            )

            # We have a DAG for the create flow of an actor/function.
            # For an existing actor we just invoke the operator directly.
            self.cloudb.register_dag(
                f"{op.function_type.get_full_name()}_create_dag",
                [
                    f"{op.function_type.get_full_name()}_create",
                    f"{op.function_type.get_full_name()}",
                ],
                [
                    (
                        f"{op.function_type.get_full_name()}_create",
                        f"{op.function_type.get_full_name()}",
                    )
                ],
            )

    def _register_routers(self):
        ingress = IngressRouter(self.serializer)
        egress = EgressRouter(self.serializer, False)

        class RouterOperator:
            def __init__(self, ingress: IngressRouter, egress: EgressRouter):
                self.ingress = ingress
                self.egress = egress

            def handle_invocation(self, cloudburst_client, route: Route) -> Route:
                # If this is a 'create' event, we have no key
                if not route.key:
                    return_event: Event = cloudburst_client.call_dag(
                        f"{route.route_name}_create", {"route": route}
                    ).get()
                    return self.egress.route_and_serialize(return_event)
                elif route.direction == RouteDirection.EGRESS:
                    return self.egress_router.route_and_serialize(route.value)
                else:
                    return_event: Event = CloudburstFuture(
                        cloudburst_client.exec_func(
                            f"{route.route_name}", {"route": route}
                        ),
                        cloudburst_client.kvs_client,
                        cloudburst_client.serializer,
                    ).get()
                    return self.egress.route_and_serialize(return_event)

            def run(self, cloudburst_client, incoming_event: bytes) -> bytes:
                # All incoming events are handled by this stateless, preferably scaled operator.
                incoming_route: Route = self.ingress.parse_and_route(incoming_event)
                return_route: Route = self.handle_invocation(incoming_route)

                while return_route.direction != RouteDirection.CLIENT:
                    return_route = self.handle_invocation(return_route)

                return_event_serialized = self.egress_router.serialize(
                    return_route.value
                )
                return return_event_serialized

        self.cloudb.register((RouterOperator, ingress, egress), f"stateflow")
