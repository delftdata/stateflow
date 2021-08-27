# StateFlow | Object Oriented Code to Distributed Stateful Dataflows
[![CI](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml/badge.svg)](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml)
[![codecov](https://codecov.io/gh/delftdata/stateflow/branch/main/graph/badge.svg?token=AUL4CXQQJX)](https://codecov.io/gh/delftdata/stateflow)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)

StateFlow is a framework which compiles object oriented Python code to distributed stateful dataflows. 
These dataflows can be executed on different target systems. At the moment, we support the following runtime systems:

|   **Runtime**  | **Local execution** | **Cluster execution** |                                                                             **Notes**                                                                             |
|:--------------:|:-------------------:|:---------------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------:|
|     PyFlink    |  :white_check_mark: |   :white_check_mark:  |                                                                                 -                                                                                 |
|   Apache Beam  |  :white_check_mark: |          :x:          | Beam [suffers a bug with Kafka](https://issues.apache.org/jira/browse/BEAM-11998), which can be bypassed locally. Deployment in a Dataflow runner does not work.  |
| Flink Statefun |  :white_check_mark: |   :white_check_mark:  |                                                                                 -                                                                                 |
|   AWS Lambda   |  :white_check_mark: |   :white_check_mark:  |                                                                                 -                                                                                 |
|   CloudBurst   |         :x:         |          :x:          |                       CloudBurst has never been officially released. Due to missing Docker files and documentation, execution does not work.                      |


## Features
- Analysis and transformation of Python classes to distributed stateful dataflows. These dataflows can be ported to cloud services and dataflow systems.
- Due to the nature of dataflow systems, stateful entities cannot directly interact with each other. Therefore, direct calls to other objects, as done in object-oriented code, does not work in stateful dataflows. StateFlow splits such functions at the AST level to get rid of the remote call.
  Instead, StateFlow splits a function into several parts such that the dataflow system can move back and forth between the different stateful entities (e.g. dataflow operators).
- Support for compilation to several (cloud) services including: AWS Lambda, Apache Beam, Flink Statefun and PyFlink.
- Support for several client-side connectivity services including: Apache Kafka, AWS Kinesis, AWS Gateway. Depending on the runtime system, a compatible client has to be used. 
  A developer can either use StateFlow futures or asyncio to interact with the remote stateful entities.
- Integration with FastAPI: each class function will be covered by an HTTP endpoint. Developers can easily add their own.

## Walkthrough
To work with StateFlow, a developer annotates its classes with the `@stateflow` decorator.
```python
from typing import List
import stateflow

@stateflow.stateflow
class Item:
    def __init__(self, item_name: str, price: int):
        self.item_name: str = item_name
        self.stock: int = 0
        self.price: int = price
        
    def set_stock(self, amount: int):
        self.stock = amount

    def __key__(self):
        return self.item_name

   
@stateflow.stateflow
class User:
    def __init__(self, username: str):
        self.username: str = username
        self.balance: int = 1

    def update_balance(self, x: int):
        self.balance += x

    def buy_item(self, amount: int, item: Item) -> bool:
        total_price = amount * item.price
   
        if self.balance < total_price:
            return False
   
        # Decrease the stock.
        decrease_stock = item.update_stock(-amount)
   
        if not decrease_stock:
            return False  # For some reason, stock couldn't be decreased.
   
        self.balance -= total_price
        return True
    
    def __key__(self):
        return self.username
```
Each stateful entities has to implement the `key` method to define the static partitioning key. This key cannot change during execution
and ensures the entity is addressable in the distributed runtime. Think of this key as the primary key in databases.

To deploy this to, for example, as a Flink job simply import the annotated classes and initialize stateflow.
```python
from demo_common import User, Item, stateflow
from stateflow.runtime.flink.pyflink import FlinkRuntime, Runtime

# Initialize stateflow
flow = stateflow.init()

runtime: FlinkRuntime = FlinkRuntime(flow)
runtime.run()
```
This code will generate a `streaming dataflow graph` compatible with Apache Flink.
Finally, to interact with these stateful entities:
```python
from demo_common import User, Item, stateflow
from stateflow.client.kafka_client import StateflowKafkaClient, StateflowClient, StateflowFuture

# Initialize stateflow
flow = stateflow.init()
client: StateflowClient = StateflowKafkaClient(
    flow, brokers="localhost:9092", statefun_mode=False
)

future_user: StateflowFuture[User] = User("new-user")
user: User = future_user.get()

user.update_balance(10).get()
```

## Demo
To run a (full) demo:
1. Launch a Kafka cluster  
   ```
   cd deployment
   docker-compose up
   ```
2. Run `demo_runtime.py`, this will deploy the actor dataflow on Apache Beam. The actors are defined in `demo_common.py`.
3. Run `demo_client.py`, this will start a client being able to interact with actors.

## Demo (with FastAPI)
1. Launch a Kafka cluster  
   ```
   cd deployment
   docker-compose up
   ```
2. Run `demo_runtime.py`, this will deploy the actor dataflow on Apache Beam. The actors are defined in `demo_common.py`.
3. Run ` uvicorn fastapi_client:app`, this will start a FastAPI client on http://localhost:8000 
   being able to interact with actors using Kafka. To find all (generated) endpoints visit http://localhost:8000/docs.
   New endpoints can be added in `fastapi_client.py`.

## Credits
This repository is part of the research conducted at the [Delft Data Management Lab](http://www.wis.ewi.tudelft.nl/data-management.html).  
Contributors:
- [Wouter Zorgdrager](https://github.com/wzorgdrager)
- [All contributors](https://github.com/delftdata/stateflow/graphs/contributors)
