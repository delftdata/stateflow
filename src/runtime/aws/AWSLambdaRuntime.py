import base64
from src.dataflow.dataflow import (
    Dataflow,
    IngressRouter,
    EgressRouter,
    Event,
    Route,
    RouteDirection,
)
from src.dataflow.stateful_operator import StatefulOperator
from src.dataflow.event import EventType
from src.dataflow.state import State
from src.serialization.pickle_serializer import SerDe, PickleSerializer
from src.runtime.runtime import Runtime
from python_dynamodb_lock.python_dynamodb_lock import *
import boto3
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, BinaryAttribute

"""Base class for implementing Lambda handlers as classes.
Used across multiple Lambda functions (included in each zip file).
Add additional features here common to all your Lambdas, like logging."""


class LambdaBase(object):
    @classmethod
    def get_handler(cls, *args, **kwargs):
        def handler(event, context):
            return cls(*args, **kwargs).handle(event, context)

        return handler

    def handle(self, event, context):
        raise NotImplementedError


class StateflowRecord(Model):
    """
    A Stateflow Record
    """

    class Meta:
        table_name = "stateflow"

    key = UnicodeAttribute(hash_key=True)
    state = BinaryAttribute(null=True)


class AWSLambdaRuntime(LambdaBase, Runtime):
    def __init__(
        self,
        flow: Dataflow,
        table_name="stateflow",
        request_stream="stateflow-request-stream",
        reply_stream="stateflow-reply-stream",
        serializer: SerDe = PickleSerializer(),
    ):
        self.flow: Dataflow = flow
        self.serializer: SerDe = serializer

        self.ingress_router = IngressRouter(self.serializer)
        self.egress_router = EgressRouter(self.egress_router, serialize_on_return=False)

        self.operators = {
            operator.function_type.get_full_name(): operator
            for operator in self.flow.operators
        }

        self.dynamodb = boto3.resource("dynamodb")
        self.lock_client: DynamoDBLockClient = DynamoDBLockClient(
            self.dynamodb, table_name=table_name
        )

        self.kinesis = boto3.resource("kinesis")
        self.request_stream: str = request_stream
        self.reply_stream: str = reply_stream

        if not self.does_stream_exist(request_stream):
            self.create_stream(request_stream)

        if not self.does_stream_exist(reply_stream):
            self.create_stream(reply_stream)

    def does_stream_exist(self, name: str) -> bool:
        try:
            print(self.kinesis.describe_stream(StreamName=name))
        except Exception:
            return False

        return True

    def create_stream(self, name: str):
        self.kinesis.create_stream(name, ShardCount=1)

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

    def invoke_operator(self, route: Route) -> Event:
        event: Event = route.value

        operator_name: str = route.route_name
        operator: StatefulOperator = self.operators[operator_name]

        if event.event_type == EventType.Request.InitClass:
            return operator.handle_create(event)
        else:
            full_key: str = f"{operator_name}_{route.key}"

            # Lock the key in DynamoDB.
            lock = self.lock_client(full_key)

            operator_state: State = self.get_state(full_key)
            return_event, updated_state = operator.handle(event, operator_state)

            self.save_state(updated_state)

            lock.release()
            return return_event

    def handle_invocation(self, event: Event) -> Route:
        route: Route = self.ingress_router.route(event)
        print("Routed event!")

        if route.direction == RouteDirection.INTERNAL:
            return self.egress_router(self.invoke_operator(route))
        elif route.direction == RouteDirection.EGRESS:
            return self.egress_router.route_and_serialize(route.value)
        else:
            return route

    def handle(self, event, context):
        for record in event["Records"]:
            event = base64.decode(record["kinesis"]["data"])
            print("Received event!")

            parsed_event: Event = self.ingress_router.parse(event)
            return_route: Route = self.handle_invocation(parsed_event)

            while return_route.direction != RouteDirection.CLIENT:
                return_route = self.handle_invocation(return_route.value)

            serialized_event = self.egress_router.serialize(return_route.value)
            self.kinesis.put_record(
                StreamName=self.reply_stream,
                Data=serialized_event,
                PartitionKey=return_route.value.event_id,
            )
