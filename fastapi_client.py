import uuid

from src.client.fastapi.fastapi_client import FastAPIClient
from demo_common import stateflow, User
from src.wrappers.meta_wrapper import MetaWrapper

client = FastAPIClient(stateflow.init())
app = client.get_app()


@app.get("/hoi")
async def handler():
    import asyncio

    # multiple = [User(f"{str(uuid.uuid4())}") for x in range(0, 200)]
    # done, _ = await asyncio.wait(multiple)
    # multiple = [res.result() for res in done]
    # print(multiple)
    # res = [x.simple_for_loop(multiple) for x in multiple]
    # done, _ = await asyncio.wait(res)
    # # print(done)
    # # return sum([x.result() for x in done])
    multiple = []
    for x in range(0, 1):
        hi: User = await User(str(uuid.uuid4()))
        multiple.append(hi)

    # multiple = [User(f"{str(uuid.uuid4())}") for x in range(0, 1)]
    # done, _ = await asyncio.wait(multiple)
    #
    # multiple = [res.result() for res in done]
    # print(f"HERE WITH MULTIPLE {multiple}")

    print(multiple)
    for_res = await hi.simple_for_loop(multiple * 10)
    return for_res
