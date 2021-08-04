from stateflow.dataflow.dataflow import Dataflow
from typing import List
import yaml


def generate(
    flow: Dataflow, statefun_cluster_url: str = "http://localhost:8000/statefun"
):
    spec = {"endpoints": [], "ingresses": {}, "egresses": {}}

    spec["endpoints"].append(
        {"endpoint": _generate_endpoint_dict("globals/ping", statefun_cluster_url)}
    )

    all_functions: List[str] = []
    for operator in flow.operators:
        fun_name: str = operator.function_type.get_full_name()
        spec["endpoints"].append(
            {"endpoint": _generate_endpoint_dict(fun_name, statefun_cluster_url)}
        )

        spec["endpoints"].append(
            {
                "endpoint": _generate_endpoint_dict(
                    f"{fun_name}_create", statefun_cluster_url
                )
            }
        )

        all_functions.append(fun_name)
        all_functions.append(f"{fun_name}_create")

    all_functions.append("globals/ping")

    spec["ingresses"] = [{"ingress": _generate_kafka_ingress(all_functions)}]
    spec["egresses"] = [
        {
            "egress": {
                "meta": {
                    "type": "io.statefun.kafka/egress",
                    "id": "stateflow/kafka-egress",
                },
                "spec": {"address": "localhost:9092"},
            }
        }
    ]

    basic_setup = {
        "version": "3.0",
        "module": {"meta": {"type": "remote"}, "spec": spec},
    }

    return yaml.dump(basic_setup)


def _generate_endpoint_dict(function_name: str, statefun_cluster_url: str):
    return {
        "meta": {"kind": "http"},
        "spec": {"functions": function_name, "urlPathTemplate": statefun_cluster_url},
    }


def _generate_kafka_ingress(
    all_functions: List[str], kafka_broker: str = "localhost:9092"
):
    topics = []

    for topic in all_functions:
        topics.append(
            {
                "topic": topic.replace("/", "_"),
                "valueType": "stateflow/byte_type",
                "targets": [topic],
            }
        )

    return {
        "meta": {"type": "io.statefun.kafka/ingress", "id": "stateflow/kafka-ingress"},
        "spec": {
            "address": kafka_broker,
            "consumerGroupId": "stateflow-statefun-consumer",
            "topics": topics,
        },
    }
