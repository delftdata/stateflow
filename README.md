# StateFlow
[![CI](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml/badge.svg)](https://github.com/wzorgdrager/stateful_dataflows/actions/workflows/python-app.yml)
[![codecov](https://codecov.io/gh/wzorgdrager/stateful_dataflows/branch/main/graph/badge.svg)](https://codecov.io/gh/wzorgdrager/stateful_dataflows)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)  
Tested against Python 3.8. 

## Demo
To run a demo:
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
