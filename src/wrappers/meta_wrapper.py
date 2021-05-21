from src.client.class_ref import ClassRef, StateflowClient, StateflowFuture
from src.dataflow.address import FunctionType
from src.descriptors import ClassDescriptor
from src.dataflow.event import Event, FunctionAddress, EventType
from src.dataflow.args import Arguments
from typing import Union
import uuid


class MetaWrapper(type):
    """A meta-class around the client-side class definition.
    We use this meta-implementation to intercept interaction with a class.
    This interception is used to generate events to the back-end/runtime.

    For example, when the class is constructed an event is sent to the runtime to generate this instance there.
    This wrapper is responsible for two kind of behaviours:
    1. Sending an event to the runtime to instantiate a class
    2. Creating a ClientRef based on a created instance.
    """

    def __new__(msc, name, bases, dct, descriptor: ClassDescriptor):
        """Constructs a meta-class for a certain class definition.

        :param name: name of the original class.
        :param bases: bases of the original class.
        :param dct: dct of the original class.
        :param descriptor: the class descriptor of this class.
        """
        msc.client: StateflowClient = None
        dct["descriptor"]: ClassDescriptor = descriptor
        return super(MetaWrapper, msc).__new__(msc, name, bases, dct)

    def __call__(msc, *args, **kwargs) -> Union[ClassRef, StateflowFuture]:
        """Invoked on constructing an instance of class.
        We cover two scenarios here:

        1. The instance is _not_ yet created on the server (we don't verify this here), and we send
        an event via the client to the runtime to create this object with the given args and kwargs.
        Therefore, we verify if the args + kwargs _matches_ the InputDescriptor of the __init__ method of the class.
        2. The instance is created on the server and therefore we know the _key_ of the object. In that case,
        a ClassRef is returned. This a reference that the client-side can interact with (i.e. call methods, get and
        update attributes).

        We differentiate between both scenarios by looking for the "__key" attribute in kwargs. If this _is_ given
        we 'know' the instance has been created on the server and we can safely create and return a ClassRef.
        We might get conflicts if a user defines a "__key" argument in its __init__ method, but we assume this is
        very unlikely. We don't explicitly check if this is the case right now.

        :param args: invocation args.
        :param kwargs: invocation kwargs.
        :return: either a StateflowFuture or ClassRef.
        """
        if "__key" in kwargs:
            return ClassRef(
                FunctionAddress(FunctionType.create(msc.descriptor), kwargs["__key"]),
                msc.descriptor,
                msc.client,
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
        """Sets the client of this class.
        The reason we have to set it explicitly (and not add it as constructor argument)
        is because we initialize the meta class _before_ the client is initialized.

        I.e.
        stateflow.init()
        is called before
        StateFlowClient()

        :param client: the client to set.
        """
        msc.client = client
