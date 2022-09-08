# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: event.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='event.proto',
  package='',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x0b\x65vent.proto\"A\n\x0c\x46unctionType\x12\x11\n\tnamespace\x18\x01 \x01(\t\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x10\n\x08stateful\x18\x03 \x01(\x08\"?\n\x0f\x46unctionAddress\x12\x1f\n\x08\x66un_type\x18\x01 \x01(\x0b\x32\r.FunctionType\x12\x0b\n\x03key\x18\x02 \x01(\t\"Q\n\rEventFlowNode\x12%\n\x0b\x63urrent_fun\x18\x05 \x01(\x0b\x32\x10.FunctionAddress\x12\x19\n\x11\x63urrent_node_type\x18\x06 \x01(\t\"\xb6\x01\n\x05\x45vent\x12\x10\n\x08\x65vent_id\x18\x01 \x01(\t\x12%\n\x0b\x66un_address\x18\x02 \x01(\x0b\x32\x10.FunctionAddress\x12\x1b\n\x07request\x18\x03 \x01(\x0e\x32\x08.RequestH\x00\x12\x17\n\x05reply\x18\x04 \x01(\x0e\x32\x06.ReplyH\x00\x12\x0f\n\x07payload\x18\x05 \x01(\x0c\x12\x1f\n\x07\x63urrent\x18\x06 \x01(\x0b\x32\x0e.EventFlowNodeB\x0c\n\nevent_type\"\x8b\x01\n\x05Route\x12\"\n\tdirection\x18\x01 \x01(\x0e\x32\x0f.RouteDirection\x12\x12\n\nroute_name\x18\x02 \x01(\t\x12\x0b\n\x03key\x18\x03 \x01(\t\x12\x1d\n\x0b\x65vent_value\x18\x04 \x01(\x0b\x32\x06.EventH\x00\x12\x15\n\x0b\x62ytes_value\x18\x05 \x01(\x0cH\x00\x42\x07\n\x05value\"P\n\x11\x45ventRequestReply\x12\x15\n\x05\x65vent\x18\x01 \x01(\x0b\x32\x06.Event\x12\r\n\x05state\x18\x02 \x01(\x0c\x12\x15\n\roperator_name\x18\x03 \x01(\t*\x99\x01\n\x05Reply\x12\x18\n\x14SuccessfulInvocation\x10\x00\x12\x19\n\x15SuccessfulCreateClass\x10\x01\x12\x0e\n\nFoundClass\x10\x02\x12\x0f\n\x0bKeyNotFound\x10\x03\x12\x1a\n\x16SuccessfulStateRequest\x10\x04\x12\x14\n\x10\x46\x61iledInvocation\x10\x05\x12\x08\n\x04Pong\x10\x06*\xa7\x01\n\x07Request\x12\x13\n\x0fInvokeStateless\x10\x00\x12\x12\n\x0eInvokeStateful\x10\x01\x12\r\n\tInitClass\x10\x02\x12\r\n\tFindClass\x10\x03\x12\x0c\n\x08GetState\x10\x04\x12\x0c\n\x08SetState\x10\x05\x12\x0f\n\x0bUpdateState\x10\x06\x12\x0f\n\x0b\x44\x65leteState\x10\x07\x12\r\n\tEventFlow\x10\x08\x12\x08\n\x04Ping\x10\t*6\n\x0eRouteDirection\x12\n\n\x06\x45GRESS\x10\x00\x12\x0c\n\x08INTERNAL\x10\x01\x12\n\n\x06\x43LIENT\x10\x02\x62\x06proto3')
)

_REPLY = _descriptor.EnumDescriptor(
  name='Reply',
  full_name='Reply',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='SuccessfulInvocation', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SuccessfulCreateClass', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FoundClass', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='KeyNotFound', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SuccessfulStateRequest', index=4, number=4,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FailedInvocation', index=5, number=5,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Pong', index=6, number=6,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=640,
  serialized_end=793,
)
_sym_db.RegisterEnumDescriptor(_REPLY)

Reply = enum_type_wrapper.EnumTypeWrapper(_REPLY)
_REQUEST = _descriptor.EnumDescriptor(
  name='Request',
  full_name='Request',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='InvokeStateless', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='InvokeStateful', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='InitClass', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FindClass', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='GetState', index=4, number=4,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SetState', index=5, number=5,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='UpdateState', index=6, number=6,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DeleteState', index=7, number=7,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='EventFlow', index=8, number=8,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Ping', index=9, number=9,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=796,
  serialized_end=963,
)
_sym_db.RegisterEnumDescriptor(_REQUEST)

Request = enum_type_wrapper.EnumTypeWrapper(_REQUEST)
_ROUTEDIRECTION = _descriptor.EnumDescriptor(
  name='RouteDirection',
  full_name='RouteDirection',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='EGRESS', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INTERNAL', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CLIENT', index=2, number=2,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=965,
  serialized_end=1019,
)
_sym_db.RegisterEnumDescriptor(_ROUTEDIRECTION)

RouteDirection = enum_type_wrapper.EnumTypeWrapper(_ROUTEDIRECTION)
SuccessfulInvocation = 0
SuccessfulCreateClass = 1
FoundClass = 2
KeyNotFound = 3
SuccessfulStateRequest = 4
FailedInvocation = 5
Pong = 6
InvokeStateless = 0
InvokeStateful = 1
InitClass = 2
FindClass = 3
GetState = 4
SetState = 5
UpdateState = 6
DeleteState = 7
EventFlow = 8
Ping = 9
EGRESS = 0
INTERNAL = 1
CLIENT = 2



_FUNCTIONTYPE = _descriptor.Descriptor(
  name='FunctionType',
  full_name='FunctionType',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='namespace', full_name='FunctionType.namespace', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='FunctionType.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='stateful', full_name='FunctionType.stateful', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=15,
  serialized_end=80,
)


_FUNCTIONADDRESS = _descriptor.Descriptor(
  name='FunctionAddress',
  full_name='FunctionAddress',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='fun_type', full_name='FunctionAddress.fun_type', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='key', full_name='FunctionAddress.key', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=82,
  serialized_end=145,
)


_EVENTFLOWNODE = _descriptor.Descriptor(
  name='EventFlowNode',
  full_name='EventFlowNode',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='current_fun', full_name='EventFlowNode.current_fun', index=0,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='current_node_type', full_name='EventFlowNode.current_node_type', index=1,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=147,
  serialized_end=228,
)


_EVENT = _descriptor.Descriptor(
  name='Event',
  full_name='Event',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='event_id', full_name='Event.event_id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='fun_address', full_name='Event.fun_address', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='request', full_name='Event.request', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='reply', full_name='Event.reply', index=3,
      number=4, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='payload', full_name='Event.payload', index=4,
      number=5, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='current', full_name='Event.current', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
    _descriptor.OneofDescriptor(
      name='event_type', full_name='Event.event_type',
      index=0, containing_type=None, fields=[]),
  ],
  serialized_start=231,
  serialized_end=413,
)


_ROUTE = _descriptor.Descriptor(
  name='Route',
  full_name='Route',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='direction', full_name='Route.direction', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='route_name', full_name='Route.route_name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='key', full_name='Route.key', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='event_value', full_name='Route.event_value', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='bytes_value', full_name='Route.bytes_value', index=4,
      number=5, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
    _descriptor.OneofDescriptor(
      name='value', full_name='Route.value',
      index=0, containing_type=None, fields=[]),
  ],
  serialized_start=416,
  serialized_end=555,
)


_EVENTREQUESTREPLY = _descriptor.Descriptor(
  name='EventRequestReply',
  full_name='EventRequestReply',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='event', full_name='EventRequestReply.event', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='state', full_name='EventRequestReply.state', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='operator_name', full_name='EventRequestReply.operator_name', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=557,
  serialized_end=637,
)

_FUNCTIONADDRESS.fields_by_name['fun_type'].message_type = _FUNCTIONTYPE
_EVENTFLOWNODE.fields_by_name['current_fun'].message_type = _FUNCTIONADDRESS
_EVENT.fields_by_name['fun_address'].message_type = _FUNCTIONADDRESS
_EVENT.fields_by_name['request'].enum_type = _REQUEST
_EVENT.fields_by_name['reply'].enum_type = _REPLY
_EVENT.fields_by_name['current'].message_type = _EVENTFLOWNODE
_EVENT.oneofs_by_name['event_type'].fields.append(
  _EVENT.fields_by_name['request'])
_EVENT.fields_by_name['request'].containing_oneof = _EVENT.oneofs_by_name['event_type']
_EVENT.oneofs_by_name['event_type'].fields.append(
  _EVENT.fields_by_name['reply'])
_EVENT.fields_by_name['reply'].containing_oneof = _EVENT.oneofs_by_name['event_type']
_ROUTE.fields_by_name['direction'].enum_type = _ROUTEDIRECTION
_ROUTE.fields_by_name['event_value'].message_type = _EVENT
_ROUTE.oneofs_by_name['value'].fields.append(
  _ROUTE.fields_by_name['event_value'])
_ROUTE.fields_by_name['event_value'].containing_oneof = _ROUTE.oneofs_by_name['value']
_ROUTE.oneofs_by_name['value'].fields.append(
  _ROUTE.fields_by_name['bytes_value'])
_ROUTE.fields_by_name['bytes_value'].containing_oneof = _ROUTE.oneofs_by_name['value']
_EVENTREQUESTREPLY.fields_by_name['event'].message_type = _EVENT
DESCRIPTOR.message_types_by_name['FunctionType'] = _FUNCTIONTYPE
DESCRIPTOR.message_types_by_name['FunctionAddress'] = _FUNCTIONADDRESS
DESCRIPTOR.message_types_by_name['EventFlowNode'] = _EVENTFLOWNODE
DESCRIPTOR.message_types_by_name['Event'] = _EVENT
DESCRIPTOR.message_types_by_name['Route'] = _ROUTE
DESCRIPTOR.message_types_by_name['EventRequestReply'] = _EVENTREQUESTREPLY
DESCRIPTOR.enum_types_by_name['Reply'] = _REPLY
DESCRIPTOR.enum_types_by_name['Request'] = _REQUEST
DESCRIPTOR.enum_types_by_name['RouteDirection'] = _ROUTEDIRECTION
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

FunctionType = _reflection.GeneratedProtocolMessageType('FunctionType', (_message.Message,), dict(
  DESCRIPTOR = _FUNCTIONTYPE,
  __module__ = 'event_pb2'
  # @@protoc_insertion_point(class_scope:FunctionType)
  ))
_sym_db.RegisterMessage(FunctionType)

FunctionAddress = _reflection.GeneratedProtocolMessageType('FunctionAddress', (_message.Message,), dict(
  DESCRIPTOR = _FUNCTIONADDRESS,
  __module__ = 'event_pb2'
  # @@protoc_insertion_point(class_scope:FunctionAddress)
  ))
_sym_db.RegisterMessage(FunctionAddress)

EventFlowNode = _reflection.GeneratedProtocolMessageType('EventFlowNode', (_message.Message,), dict(
  DESCRIPTOR = _EVENTFLOWNODE,
  __module__ = 'event_pb2'
  # @@protoc_insertion_point(class_scope:EventFlowNode)
  ))
_sym_db.RegisterMessage(EventFlowNode)

Event = _reflection.GeneratedProtocolMessageType('Event', (_message.Message,), dict(
  DESCRIPTOR = _EVENT,
  __module__ = 'event_pb2'
  # @@protoc_insertion_point(class_scope:Event)
  ))
_sym_db.RegisterMessage(Event)

Route = _reflection.GeneratedProtocolMessageType('Route', (_message.Message,), dict(
  DESCRIPTOR = _ROUTE,
  __module__ = 'event_pb2'
  # @@protoc_insertion_point(class_scope:Route)
  ))
_sym_db.RegisterMessage(Route)

EventRequestReply = _reflection.GeneratedProtocolMessageType('EventRequestReply', (_message.Message,), dict(
  DESCRIPTOR = _EVENTREQUESTREPLY,
  __module__ = 'event_pb2'
  # @@protoc_insertion_point(class_scope:EventRequestReply)
  ))
_sym_db.RegisterMessage(EventRequestReply)


# @@protoc_insertion_point(module_scope)