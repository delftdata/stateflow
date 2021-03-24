from apache_beam import DoFn
from apache_beam.coders import BytesCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec
import apache_beam as beam

from runtime.runtime import Runtime
from src.dataflow.dataflow import Dataflow


class BeamOperator(DoFn):

    STATE_SPEC = ReadModifyWriteStateSpec("state", BytesCoder())

    def __init__(self, fun):
        self.fun = fun

    def process(self, element, state=DoFn.StateParam(STATE_SPEC)):
        # WE NEED TO EMBED THE PyFunc HERE!
        current_value = state.read() or None
        print(f"Processing {element}")
        if element[0] == "CREATE":
            if current_value is None:
                print(f"{element[1]} does not exist exists!")
                state.write(element[1])
            else:
                state.write(current_value)

        return ["CREATED!"]


class BeamRuntime(Runtime):
    def transform(self, dataflow: Dataflow):
        pass

    def run(self):
        print("Running Beam pipeline!")

        with beam.Pipeline() as pipeline:
            res = (
                pipeline
                | beam.Create([("CREATE", "User"), ("CREATE", "Item")])
                | beam.ParDo(BeamOperator())
                | "Print" >> beam.Map(print)
            )
