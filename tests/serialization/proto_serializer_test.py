from stateflow.serialization.proto.proto_serde import (
    ProtoSerializer,
    Event,
    FunctionAddress,
    FunctionType,
    EventType,
)


def test_simple_event():
    event = Event(
        "123",
        FunctionAddress(FunctionType("global", "User", True), "wouter"),
        EventType.Request.InitClass,
        {"test": "test"},
    )
    serde = ProtoSerializer()

    event_ser = serde.serialize_event(event)
    event_deser = serde.deserialize_event(event_ser)

    print(event_ser)
    assert event_deser.event_id == event.event_id
    assert event_deser.fun_address == event.fun_address
    assert event_deser.event_type == event.event_type
    assert event_deser.payload == event.payload
