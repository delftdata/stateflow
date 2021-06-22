from fastapi import FastAPI
from src.dataflow.dataflow import Dataflow, ClassDescriptor
from src.descriptors.method_descriptor import MethodDescriptor
from src.dataflow.dataflow import Operator


class FastAPIClient:
    def __init__(self, flow: Dataflow):
        self.app: FastAPI = FastAPI()

        for operator in flow.operators:
            cls_descriptor: ClassDescriptor = operator.class_wrapper.class_desc
            fun_type = operator.function_type

            for method in cls_descriptor.methods_dec:
                if not self.get_name(method) == "__key__":
                    self.get_handler(fun_type, method)

            self.get_handler(
                fun_type,
            )

    def get_name(self, method: MethodDescriptor) -> str:
        if method.method_name == "__init__":
            return "create"
        return method.method_name

    def get_handler(
        self, function_type, method_desc: MethodDescriptor, method: str = "POST"
    ):
        @self.app.api_route(
            f"/stateflow/{function_type.get_full_name()}/{self.get_name(method_desc)}",
            methods=[method],
        )
        async def endpoint():
            return {"Hey I am": method_desc.method_name}

        return endpoint

    def get_app(self) -> FastAPI:
        return self.app
