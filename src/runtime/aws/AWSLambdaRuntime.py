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
from botocore.config import Config

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
        region = "eu-west-1"

    key = UnicodeAttribute(hash_key=True)
    state = BinaryAttribute(null=True)


class AWSLambdaRuntime(LambdaBase, Runtime):
    def __init__(
        self,
        flow: Dataflow,
        table_name="stateflow",
        request_stream="stateflow-request",
        reply_stream="stateflow-reply",
        serializer: SerDe = PickleSerializer(),
        config: Config = Config(region_name="eu-west-1"),
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

        self.kinesis = self._setup_kinesis(config)
        self.request_stream: str = request_stream
        self.reply_stream: str = reply_stream

    def _setup_dynamodb(self, config: Config):
        return boto3.resource("dynamodb", config=config)

    def _setup_kinesis(self, config: Config):
        return boto3.client("kinesis", config=config)

    def _setup_lock_client(self, expiry_period: int) -> DynamoDBLockClient:
        return DynamoDBLockClient(
            self.dynamodb, expiry_period=datetime.timedelta(seconds=expiry_period)
        )

    def lock_key(self, key: str):
        print(f"Locking {key}")
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
            lock = self.lock_key(full_key)

            operator_state: State = self.get_state(full_key)
            return_event, updated_state = operator.handle(event, operator_state)

            self.save_state(full_key, updated_state)

            print(f"Releasing lock {full_key}")
            lock.release()
            return return_event

    def handle_invocation(self, event: Event) -> Route:
        route: Route = self.ingress_router.route(event)
        print(f"Received and routed event! {event.event_type}")

        if route.direction == RouteDirection.INTERNAL:
            return self.egress_router.route_and_serialize(self.invoke_operator(route))
        elif route.direction == RouteDirection.EGRESS:
            return self.egress_router.route_and_serialize(route.value)
        else:
            return route

    def handle(self, event, context):
        for record in event["Records"]:
            event = base64.b64decode(record["kinesis"]["data"])

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
