from benchmark.hotel.user import User
from benchmark.hotel.search import Search, Geo, Rate
from benchmark.hotel.reservation import Reservation
from benchmark.hotel.profile import Profile, HotelProfile
from benchmark.hotel.recommend import RecommendType, Recommend, stateflow
from stateflow.runtime.aws.gateway_lambda import AWSGatewayLambdaRuntime

# Initialize stateflow
flow = stateflow.init()

runtime, handler = AWSGatewayLambdaRuntime.get_handler(flow, gateway=True)
