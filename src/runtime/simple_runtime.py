from dataflow import *


class SimpleRuntime:
    def __init__(self, dataflow: Dataflow):
        self.dataflow = Dataflow

    def execute_flow(self, input_event: Event) -> List[Event]:
        first_edge: Edge = self.dataflow.get_edge_by_event(input_event)

        first_edge.flow()
