from stateflow.runtime.runtime import Runtime
from stateflow.serialization.pickle_serializer import PickleSerializer, SerDe
from stateflow.dataflow.dataflow import Dataflow, Event, EgressRouter, IngressRouter, RouteDirection
from statefun import *
from aiohttp import web


class StatefunRuntime(Runtime):
    def __init__(self, dataflow: Dataflow, serializer: SerDe = PickleSerializer()):
        self.dataflow = dataflow
        self.stateful_functions = StatefulFunctions()
        self.serializer = serializer

        self.ingress_router = IngressRouter(self.serializer)
        self.egress_router = EgressRouter(self.serializer, serialize_on_return=False)

        self.byte_type = simple_type(
            "state_type", serialize_fn=lambda _: _, deserialize_fn=lambda _: _
        )

        self._add_endpoints()
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

    def _egress_event(self, event: Event, ctx: Context):

    def _add_endpoints(self):
        for operator in self.dataflow.operators:

            async def endpoint(ctx: Context, msg: Message):
                event_serialized = msg.raw_value()
                current_state = ctx.storage.state

                route = self.ingress_router.route(
                    self.serializer.deserialize_event(event_serialized)
                )

                if route.direction == RouteDirection.EGRESS:
                    self._egress_event(route.)

                outgoing_event, updated_state = operator.handle(
                    incoming_event, current_state
                )

                if current_state != updated_state:
                    ctx.storage.state = updated_state

            self.stateful_functions.bind(
                f"{operator.function_type.get_full_name()}",
                specs=[ValueSpec(name="state", type=self.byte_type)],
            )

    def get_app(self):
        return self.app
