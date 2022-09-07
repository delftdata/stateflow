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
from statefun import StatefulFunctions, simple_type, RequestReplyHandler, kafka_egress_message, \
    Context, Message, message_builder, ValueSpec
from aiohttp import web


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

    def _route(self, ctx: Context, outgoing_event: Event):
        egress_route: Route = self.egress_router.route_and_serialize(outgoing_event)

        if egress_route.direction == RouteDirection.CLIENT:
            ctx.send_egress(
                kafka_egress_message(
                    typename="stateflow/kafka-egress",
                    topic=self.reply_topic,
                    key=egress_route.value.event_id,
                    value=self.egress_router.serialize(egress_route.value),
                )
            )
            return

        ingress_route: Route = self.ingress_router.route(egress_route.value)

        if ingress_route.direction == RouteDirection.INTERNAL:
            ctx.send(
                message_builder(
                    target_typename=ingress_route.route_name,
                    target_id=ingress_route.key,
                    value=self.egress_router.serialize(ingress_route.value),
                    value_type=self.byte_type,
                )
            )
        elif ingress_route.direction == RouteDirection.EGRESS:
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
                incoming_event = self.serializer.deserialize_event(event_serialized)

                outgoing_event, updated_state = self.operators_dict[
                    ctx.address.typename
                ].handle(incoming_event, current_state)

                if current_state != updated_state:
                    ctx.storage.state = updated_state

                self._route(ctx, outgoing_event)

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
