from stateflow.runtime.runtime import Runtime
from stateflow.serialization.pickle_serializer import PickleSerializer, SerDe
from stateflow.dataflow.dataflow import (
    Dataflow,
    Event,
    EgressRouter,
    IngressRouter,
    RouteDirection,
    Route,
    EventType,
)
from statefun import *
from aiohttp import web
import time


class StatefunRuntime(Runtime):
    def __init__(
        self,
        dataflow: Dataflow,
        serializer: SerDe = PickleSerializer(),
        reply_topic: str = "client_reply",
    ):
        self.dataflow = dataflow
        self.stateful_functions = StatefulFunctions()
        self.serializer = serializer
        self.reply_topic = reply_topic

        self.ingress_router = IngressRouter(self.serializer)
        self.egress_router = EgressRouter(self.serializer, serialize_on_return=False)

        self.byte_type = simple_type(
            "stateflow/byte_type", serialize_fn=lambda _: _, deserialize_fn=lambda _: _
        )

        self.operators_dict = {}

        self._add_ping_endpoint()
        self._add_operator_endpoints()
        self._add_create_endpoints()

        self.handle = self._build_handler()

        self.app = web.Application()
        self.app.add_routes([web.post("/statefun", self.handle)])

    def _build_handler(self):
        self.handler = RequestReplyHandler(self.stateful_functions)

        async def handle(request):
            req = await request.read()
            res = await self.handler.handle_async(req)
            return web.Response(body=res, content_type="application/octet-stream")

        return handle

    def _add_ping_endpoint(self):
        async def ping_endpoint(ctx: Context, msg: Message):
            event_serialized = msg.raw_value()
            incoming_event = self.serializer.deserialize_event(event_serialized)

            if incoming_event.event_type != EventType.Request.Ping:
                raise AttributeError(
                    f"Expected a Ping but got an {incoming_event.event_type}."
                )

            outgoing_route: Route = self.ingress_router.route(incoming_event)

            ctx.send_egress(
                kafka_egress_message(
                    typename="stateflow/kafka-egress",
                    topic=self.reply_topic,
                    key=outgoing_route.value.event_id,
                    value=self.egress_router.serialize(outgoing_route.value),
                )
            )

        self.stateful_functions.register("globals/ping", ping_endpoint)

    def _route(self, ctx: Context, outgoing_event: Event, current_experiment_data):
        start = time.perf_counter()
        egress_route: Route = self.egress_router.route_and_serialize(outgoing_event)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        current_experiment_data["ROUTING_DURATION"] += time_ms
        current_experiment_data["OUTGOING_TIMESTAMP"] = round(time.time() * 1000)

        if egress_route.direction == RouteDirection.CLIENT:
            start = time.perf_counter()
            self.egress_router.serialize(egress_route.value)
            end = time.perf_counter()
            time_ms = (end - start) * 1000
            current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms

            egress_route.value.payload.update(current_experiment_data)

            ctx.send_egress(
                kafka_egress_message(
                    typename="stateflow/kafka-egress",
                    topic=self.reply_topic,
                    key=egress_route.value.event_id,
                    value=self.egress_router.serialize(egress_route.value),
                )
            )
            return

        start = time.perf_counter()
        ingress_route: Route = self.ingress_router.route(egress_route.value)
        end = time.perf_counter()
        time_ms = (end - start) * 1000
        current_experiment_data["ROUTING_DURATION"] += time_ms

        if ingress_route.direction == RouteDirection.INTERNAL:
            start = time.perf_counter()
            self.egress_router.serialize(ingress_route.value)
            end = time.perf_counter()
            time_ms = (end - start) * 1000
            current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms

            ingress_route.value.payload.update(current_experiment_data)
            ingress_route.value.payload["INCOMING_TIMESTAMP"] = round(
                time.time() * 1000
            )

            ctx.send(
                message_builder(
                    target_typename=ingress_route.route_name,
                    target_id=ingress_route.key,
                    value=self.egress_router.serialize(ingress_route.value),
                    value_type=self.byte_type,
                )
            )
        elif ingress_route.direction == RouteDirection.EGRESS:
            start = time.perf_counter()
            self.egress_router.serialize(ingress_route.value)
            end = time.perf_counter()
            time_ms = (end - start) * 1000
            current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms

            ingress_route.value.payload.update(current_experiment_data)

            ctx.send_egress(
                kafka_egress_message(
                    typename="stateflow/kafka-egress",
                    topic=self.reply_topic,
                    key=ingress_route.value.event_id,
                    value=self.egress_router.serialize(ingress_route.value),
                )
            )

    def _add_operator_endpoints(self):
        for operator in self.dataflow.operators:
            self.operators_dict[operator.function_type.get_full_name()] = operator

            async def endpoint(ctx: Context, msg: Message):
                event_serialized = msg.raw_value()
                current_state = ctx.storage.state

                start = time.perf_counter()
                incoming_event = self.serializer.deserialize_event(event_serialized)
                end = time.perf_counter()
                time_ms = (end - start) * 1000

                if "STATEFUN" in incoming_event.payload:
                    current_experiment_data = {
                        "STATE_SERIALIZATION_DURATION": incoming_event.payload[
                            "STATE_SERIALIZATION_DURATION"
                        ],
                        "EVENT_SERIALIZATION_DURATION": incoming_event.payload[
                            "EVENT_SERIALIZATION_DURATION"
                        ],
                        "ROUTING_DURATION": incoming_event.payload["ROUTING_DURATION"],
                        "ACTOR_CONSTRUCTION": incoming_event.payload[
                            "ACTOR_CONSTRUCTION"
                        ],
                        "EXECUTION_GRAPH_TRAVERSAL": incoming_event.payload[
                            "EXECUTION_GRAPH_TRAVERSAL"
                        ],
                        "STATEFUN": incoming_event.payload["STATEFUN"],
                    }
                else:
                    current_experiment_data = {
                        "STATE_SERIALIZATION_DURATION": 0,
                        "EVENT_SERIALIZATION_DURATION": 0,
                        "ROUTING_DURATION": 0,
                        "ACTOR_CONSTRUCTION": 0,
                        "EXECUTION_GRAPH_TRAVERSAL": 0,
                        "STATEFUN": 0,
                    }

                current_experiment_data["EVENT_SERIALIZATION_DURATION"] += time_ms

                incoming_time = round(time.time() * 1000) - incoming_event.payload.pop(
                    "INCOMING_TIMESTAMP"
                )
                # print(f"Made a trip in Statefun! This took {incoming_time}.")

                current_experiment_data["STATEFUN"] += incoming_time

                operator = self.operators_dict[ctx.address.typename]
                operator.current_experiment_date = current_experiment_data
                operator.class_wrapper.current_experiment_date = current_experiment_data

                outgoing_event, updated_state = operator.handle(
                    incoming_event, current_state
                )

                if current_state != updated_state:
                    ctx.storage.state = updated_state

                self._route(ctx, outgoing_event, current_experiment_data)

            self.stateful_functions.register(
                f"{operator.function_type.get_full_name()}",
                endpoint,
                specs=[ValueSpec(name="state", type=self.byte_type)],
            )

    def _add_create_endpoints(self):
        for operator in self.dataflow.operators:
            self.operators_dict[
                f"{operator.function_type.get_full_name()}_create"
            ] = operator

            async def endpoint(ctx: Context, msg: Message):
                event_serialized = msg.raw_value()
                incoming_event = self.serializer.deserialize_event(event_serialized)
                print(
                    f"Now got a create request {incoming_event} for operator {operator.class_wrapper}"
                )
                print(f"{ctx.address}")

                outgoing_event: Event = self.operators_dict[
                    ctx.address.typename
                ].handle_create(incoming_event)

                ctx.send(
                    message_builder(
                        target_typename=outgoing_event.fun_address.function_type.get_full_name(),
                        target_id=outgoing_event.fun_address.key,
                        value=self.egress_router.serialize(outgoing_event),
                        value_type=self.byte_type,
                    )
                )

            self.stateful_functions.register(
                f"{operator.function_type.get_full_name()}_create", endpoint
            )

    def get_app(self):
        return self.app
