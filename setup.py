from setuptools import setup, find_packages

setup(
    name="stateflow",
    version="0.0.1",
    author="Wouter Zorgdrager",
    author_email="zorgdragerw@gmail.com",
    python_requires=">=3.6",
    packages=find_packages(exclude=("tests")),
    install_requires=[
        "graphviz",
        "libcst",
        "apache-beam",
        "ujson",
        "confluent-kafka",
        "apache-flink",
        "pynamodb",
        "boto3",
        "fastapi",
        "uvicorn",
        "aiokafka",
    ],
)
