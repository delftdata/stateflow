from src.client import ClassRef, StateflowClient, StateflowFuture
from src.dataflow import FunctionType
from src.descriptors import ClassDescriptor
from src.dataflow.event import Event, FunctionType, FunctionAddress, EventType
from src.dataflow.args import Arguments
import uuid


class MetaWrapper(type):
    def __new__(msc, name, bases, dct, descriptor):
        msc.client: StateflowClient = None
        msc.descriptor: ClassDescriptor = descriptor
        return super(MetaWrapper, msc).__new__(msc, name, bases, dct)

    def __call__(msc, *args, **kwargs) -> StateflowFuture[ClassRef]:
        # print(f"Calling class {msc} with client {msc.client}")
        # print(f"Calling with {args} and {kwargs}")
        # print(msc)

        # We didn't create it yet, so key is still None.
        fun_address = FunctionAddress(FunctionType.create(msc.descriptor), None)

        event_id: str = str(uuid.uuid4())

        # Build arguments.
        args = Arguments.from_args_and_kwargs(
            msc.descriptor.get_method_by_name("__init__").input_desc.get(),
            *args,
            **kwargs,
        )

        # Creates a class event.
        create_class_event = Event(
            event_id, fun_address, EventType.Request.value.InitClass, args
        )

        # ClassRef(FunctionType.create(msc.descriptor), msc.descriptor)

        # Hier "creeren" we de class (stoppen we t in een class-reference maybe)?.
        return msc.client.send(create_class_event, ClassRef)
        # return super(GenericMeta, msc).__call__(*args, **kwargs)

    def set_client(msc, client: StateflowClient):
        msc.client = client
