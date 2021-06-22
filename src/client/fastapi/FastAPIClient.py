from fastapi import FastAPI
from src.dataflow.dataflow import Dataflow, ClassDescriptor
from src.descriptors.method_descriptor import MethodDescriptor
from src.dataflow.dataflow import Operator
from aiokafka import AIOKafkaProducer


class FastAPIClient:
    def __init__(self, flow: Dataflow):
        self.app: FastAPI = FastAPI()
        self.producer: AIOKafkaProducer = None

        self.setup_init()

        for operator in flow.operators:
            cls_descriptor: ClassDescriptor = operator.class_wrapper.class_desc
            fun_type = operator.function_type

            for method in cls_descriptor.methods_dec:
                if not self.get_name(method) == "__key__":
                    self.create_method_handler(fun_type, method)

            self.create_fun_get(fun_type)

    def setup_init(self):
        @self.app.on_event("startup")
        async def setup_kafka():
            self.producer = AIOKafkaProducer(bootstrap_servers="localhost:9092")
            await self.producer.start()

        @self.app.on_event("shutdown")
        async def stop_kafka():
            await self.producer.close()

        return setup_kafka

    def get_name(self, method: MethodDescriptor) -> str:
        if method.method_name == "__init__":
            return "create"
        return method.method_name

    def create_fun_get(self, function_type):
        @self.app.get(
            f"/stateflow/{function_type.get_full_name()}/find/",
            name=f"find_{function_type.get_full_name()}",
        )
        async def endpoint():
            return {"Hey I am": f"create: {function_type.to_dict()}"}

        return endpoint

    def create_method_handler(self, function_type, method_desc: MethodDescriptor):
        @self.app.post(
            f"/stateflow/{function_type.get_full_name()}/{self.get_name(method_desc)}",
            name=self.get_name(method_desc),
        )
        async def endpoint():
            return {"Hey I am": method_desc.method_name}

        return endpoint

    def get_app(self) -> FastAPI:
        return self.app
