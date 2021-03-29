from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam
from src.dataflow import StatefulOperator
from typing import List

from runtime.runtime import Runtime
from src.dataflow import Dataflow
from src.dataflow import State, Event


class BeamOperator(DoFn):

    STATE_SPEC = ReadModifyWriteStateSpec("state", BytesCoder())

    def __init__(self, operator: StatefulOperator):
        self.operator = operator

    def process(
        self, element, operator_state=DoFn.StateParam(STATE_SPEC)
    ) -> List[Event]:
        if operator_state.read() is not None:
            state_decoded = State.deserialize(operator_state.read())
        else:
            state_decoded = None

        # Execute event.
        operator_return, updated_state = self.operator.handle(element[1], state_decoded)

        # Update state.

        if updated_state is not None:
            state_encoded = State.serialize(updated_state)
            operator_state.write(state_encoded)

        return [operator_return]


class BeamRuntime(Runtime):
    def __init__(self):
        self.operators: List[BeamOperator] = []

    def transform(self, dataflow: Dataflow):
        for operator in dataflow.operators:
            self.operators.append(BeamOperator(operator))

    def run(self, events):
        print("Running Beam pipeline!")

        with beam.Pipeline() as pipeline:
            res = (
                pipeline
                | beam.Create(events)
                | beam.ParDo(self.operators[0])
                | "Print" >> beam.Map(print)
            )
