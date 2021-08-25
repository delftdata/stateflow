import base64
from stateflow.dataflow.dataflow import (
    Dataflow,
    IngressRouter,
    EgressRouter,
    Event,
    Route,
    RouteDirection,
    EventFlowGraph,
    EventFlowNode,
)
from stateflow.dataflow.stateful_operator import StatefulOperator
from stateflow.dataflow.event import EventType
from stateflow.serialization.pickle_serializer import SerDe, PickleSerializer
from stateflow.runtime.runtime import Runtime
from python_dynamodb_lock.python_dynamodb_lock import *
import boto3
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, BinaryAttribute
from botocore.config import Config
import datetime

"""Base class for implementing Lambda handlers as classes.
Used across multiple Lambda functions (included in each zip file).
Add additional features here common to all your Lambdas, like logging."""


class LambdaBase(object):
    @classmethod
    def get_handler(cls, *args, **kwargs):
        inst = cls(*args, **kwargs)

        def handler(event, context):
            return inst.handle(event, context)

        return inst, handler

    def handle(self, event, context):
        raise NotImplementedError


class StateflowRecord(Model):
    """
    A Stateflow Record
    """

    class Meta:
        table_name = "stateflow"
        region = "eu-west-2"

    key = UnicodeAttribute(hash_key=True)
    state = BinaryAttribute(null=True)


class AWSLambdaRuntime(LambdaBase, Runtime):
    def __init__(
        self,
        flow: Dataflow,
        table_name="stateflow",
        serializer: SerDe = PickleSerializer(),
        config: Config = Config(region_name="eu-west-2"),
    ):
        self.flow: Dataflow = flow
        self.serializer: SerDe = serializer

        self.ingress_router = IngressRouter(self.serializer)
        self.egress_router = EgressRouter(self.serializer, serialize_on_return=False)

        self.operators = {
            operator.function_type.get_full_name(): operator
            for operator in self.flow.operators
        }

        self.dynamodb = self._setup_dynamodb(config)
        self.lock_client: DynamoDBLockClient = self._setup_lock_client(3)

    def _setup_dynamodb(self, config: Config):
        return boto3.resource("dynamodb", config=config)

    def _setup_lock_client(self, expiry_period: int) -> DynamoDBLockClient:
        return DynamoDBLockClient(
            self.dynamodb, expiry_period=datetime.timedelta(seconds=expiry_period)
        )

    def lock_key(self, key: str):
        return self.lock_client.acquire_lock(key)

    def get_state(self, key: str):
        try:
            record = StateflowRecord.get(key)
            return record.state
        except StateflowRecord.DoesNotExist:
            print(f"{key} does not exist yet")
            return None

    def save_state(self, key: str, state):
        record = StateflowRecord(key, state=state)
        record.save()

    def is_request_state(self, event: Event) -> bool:
        if event.event_type == EventType.Request.GetState:
            return True

        if event.event_type != EventType.Request.EventFlow:
            return False

        flow_graph: EventFlowGraph = event.payload["flow"]
        current_node = flow_graph.current_node

        if current_node.typ == EventFlowNode.REQUEST_STATE:
            return True

        return False

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

            # Lock the key in DynamoDB.
            if not self.is_request_state(event):
                lock = self.lock_key(full_key)
                lock = None
            else:
                lock = None

            operator_state = self.get_state(full_key)

            return_event, updated_state = operator.handle(event, operator_state)

            if updated_state is not operator_state:
                self.save_state(full_key, updated_state)

            if lock:
                lock.release()
            return return_event

    def handle_invocation(self, event: Event) -> Route:
        route: Route = self.ingress_router.route(event)

        if route.direction == RouteDirection.INTERNAL:
            return self.egress_router.route_and_serialize(self.invoke_operator(route))
        elif route.direction == RouteDirection.EGRESS:
            return self.egress_router.route_and_serialize(route.value)
        else:
            return route

    def handle(self, event, context):
        raise NotImplementedError("Needs to be implemented by subclasses.")
