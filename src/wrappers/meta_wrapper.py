from src.client import ClassRef, StateflowClient, StateflowFuture
from src.dataflow import FunctionType
from src.descriptors import ClassDescriptor
from src.dataflow.event import Event, FunctionType, FunctionAddress, EventType
from src.dataflow.args import Arguments
from typing import Union
import uuid


class MetaWrapper(type):
    def __new__(msc, name, bases, dct, descriptor):
        msc.client: StateflowClient = None
        msc.descriptor: ClassDescriptor = descriptor
        return super(MetaWrapper, msc).__new__(msc, name, bases, dct)

    def __call__(msc, *args, **kwargs) -> Union[ClassRef, StateflowFuture]:
        if "__key" in kwargs:
            return ClassRef(
                FunctionType.create(msc.descriptor), msc.descriptor, kwargs["__key"]
            )

        fun_address = FunctionAddress(FunctionType.create(msc.descriptor), None)

        event_id: str = str(uuid.uuid4())

        # Build arguments.
        args = Arguments.from_args_and_kwargs(
            msc.descriptor.get_method_by_name("__init__").input_desc.get(),
            *args,
            **kwargs,
        )

        payload = {"args": args}

        # Creates a class event.
        create_class_event = Event(
            event_id, fun_address, EventType.Request.InitClass, payload
        )

        return msc.client.send(create_class_event, msc)

    def set_client(msc, client: StateflowClient):
        msc.client = client
