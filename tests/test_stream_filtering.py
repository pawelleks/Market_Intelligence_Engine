import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from mie_lib.realtime.theta_streamer import ThetaStreamer, StreamMsg, StreamMsgType, SecurityType

# Mock Enum classes since we might not have the real lib
class MockContract:
    def __init__(self, root, security_type):
        self.root = root
        self.security_type = security_type
        self.strike = 0
        self.right = None
        self.exp = "2024-01-01"
        self.isCall = False

class MockTradeCondition:
    def __init__(self, name):
        self.name = name

class MockTrade:
    def __init__(self, price, size, condition_name, ms=0):
        self.price = price
        self.size = size
        self.condition = MockTradeCondition(condition_name)
        self.ms_of_day = ms

class MockStreamMsg:
    def __init__(self, msg_type, contract, trade):
        self.type = msg_type
        self.contract = contract
        self.trade = trade

def test_stream_filtering_outliers():
    streamer = ThetaStreamer(["SPX"])
    streamer.loop = MagicMock()
    streamer.loop.call_soon_threadsafe = MagicMock()
    streamer.active = True
    
    # 1. Test Regular Stock Trade (Should Pass)
    msg_good = MockStreamMsg(
        StreamMsgType.TRADE,
        MockContract("SPX", SecurityType.INDEX),
        MockTrade(5000.0, 100, "REGULAR")
    )
    
    streamer._on_stream_msg(msg_good)
    assert streamer.loop.call_soon_threadsafe.called
    args = streamer.loop.call_soon_threadsafe.call_args_list[0][0]
    # Check if broadcast was called
    # method is broadcast_sync, arg is data dict
    assert "SPX" == args[1]["root"]
    assert 5000.0 == args[1]["price"]
    assert "STOCK" == args[1]["asset_type"]

    # Reset
    streamer.loop.call_soon_threadsafe.reset_mock()
    streamer.state["SPX"] = {"price": 5000.0, "net_flow": 0.0} # Set last known

    # 2. Test Outlier Price (>1% deviation)
    # 5100 is > 1% of 5000 (50 points is 1%, so 100 points is 2%)
    msg_outlier = MockStreamMsg(
        StreamMsgType.TRADE,
        MockContract("SPX", SecurityType.INDEX),
        MockTrade(5100.0, 100, "REGULAR")
    )
    streamer._on_stream_msg(msg_outlier)
    # Should NOT process
    assert not streamer.loop.call_soon_threadsafe.called

    # 3. Test Bad Condition
    msg_bad_cond = MockStreamMsg(
        StreamMsgType.TRADE,
        MockContract("SPX", SecurityType.INDEX),
        MockTrade(5005.0, 100, "SOLD_OUT_OF_SEQUENCE")
    )
    streamer._on_stream_msg(msg_bad_cond)
    assert not streamer.loop.call_soon_threadsafe.called

def test_asset_type_distinction():
    streamer = ThetaStreamer(["SPX"])
    streamer.loop = MagicMock()
    streamer.active = True

    # Option Trade
    msg_opt = MockStreamMsg(
        StreamMsgType.TRADE,
        MockContract("SPX", SecurityType.OPTION),
        MockTrade(10.5, 10, "REGULAR")
    )
    
    streamer._on_stream_msg(msg_opt)
    call_args = streamer.loop.call_soon_threadsafe.call_args[0] # check last call (broadcast or update_state)
    # Actually checking update_state logic requires mocking that too or checking logic
    
    # Verify the DATA dict passed to broadcast_sync
    # call_soon calls broadcast_sync(data)
    # We grab the first call arguments
    data = streamer.loop.call_soon_threadsafe.call_args_list[0][0][1]
    assert data["asset_type"] == "OPTION"
