from math import floor

import pytest
from numpy.testing import assert_allclose
from pydesim import simulate, Logger
from pyqumo.distributions import Constant

from pycsmaca.model import WiredLineNetwork


SIM_TIME_LIMIT = 1000
PAYLOAD_SIZE = Constant(100.0)      # 100 bits data payload
SOURCE_INTERVAL = Constant(1.0)     # 1 second between packets
HEADER_SIZE = 10                    # 10 bits header
BITRATE = 500                       # 500 bps
DISTANCE = 500                      # 500 meters between stations
SPEED_OF_LIGHT = 10000              # 10 kilometers per second speed of light


def test_two_wire_connected_stations():
    sr = simulate(
        WiredLineNetwork,
        stime_limit=SIM_TIME_LIMIT,
        params=dict(
            num_stations=2,
            payload_size=PAYLOAD_SIZE,
            header_size=HEADER_SIZE,
            bitrate=BITRATE,
            distance=DISTANCE,
            speed_of_light=SPEED_OF_LIGHT,
            active_sources=[0],
        ),
        loglevel=Logger.Level.ERROR
    )

    client = sr.data.stations[0]
    server = sr.data.stations[1]

    expected_interval_avg = SOURCE_INTERVAL.mean()
    expected_number_of_packets = floor(SIM_TIME_LIMIT / expected_interval_avg)

    assert client.source.num_packets_sent == expected_number_of_packets
    assert (expected_number_of_packets - 1 <=
            server.sink.num_packets_received <= expected_number_of_packets)

    expected_transmission_delay = (PAYLOAD_SIZE.mean() + HEADER_SIZE) / BITRATE
    expected_delay = DISTANCE / SPEED_OF_LIGHT + expected_transmission_delay

    assert_allclose(client.source.delay_vector.mean(), expected_delay, rtol=0.1)

    client_if = client.get_interface_to(server)
    assert client_if.queue.size_trace.mean() == 0

    expected_busy_ratio = expected_transmission_delay / expected_interval_avg
    assert_allclose(client_if.transceiver.busy_vector.mean(),
                    expected_busy_ratio, rtol=0.1)


@pytest.mark.parametrize('num_stations', [(3,), (4,)])
def test_wired_line_network_with_single_source(num_stations):
    sr = simulate(
        WiredLineNetwork,
        stime_limit=SIM_TIME_LIMIT,
        params=dict(
            num_stations=4,
            payload_size=PAYLOAD_SIZE,
            header_size=HEADER_SIZE,
            bitrate=BITRATE,
            distance=DISTANCE,
            speed_of_light=SPEED_OF_LIGHT,
            active_sources=[0],
        ),
        loglevel=Logger.Level.ERROR
    )

    client = sr.data.stations[0]
    server = sr.data.stations[-1]

    expected_interval_avg = SOURCE_INTERVAL.mean()
    expected_number_of_packets = floor(SIM_TIME_LIMIT / expected_interval_avg)

    assert client.source.num_packets_sent == expected_number_of_packets
    assert (expected_number_of_packets - 1 <=
            server.sink.num_packets_received <= expected_number_of_packets)

    expected_transmission_delay = (PAYLOAD_SIZE.mean() + HEADER_SIZE) / BITRATE
    expected_delay = (DISTANCE / SPEED_OF_LIGHT + expected_transmission_delay
                      ) * (num_stations - 1)

    assert_allclose(client.source.delay_vector.mean(), expected_delay, rtol=0.1)

    client_if = client.get_interface_to(server)
    assert client_if.queue.size_trace.mean() == 0

    expected_busy_ratio = expected_transmission_delay / expected_interval_avg
    assert_allclose(client_if.transceiver.busy_vector.mean(),
                    expected_busy_ratio, rtol=0.1)


@pytest.mark.parametrize('num_stations', [(3,), (4,)])
def test_wired_line_network_without_cross_traffic(num_stations):
    sr = simulate(
        WiredLineNetwork,
        stime_limit=SIM_TIME_LIMIT,
        params=dict(
            num_stations=num_stations,
            payload_size=PAYLOAD_SIZE,
            header_size=HEADER_SIZE,
            bitrate=BITRATE,
            distance=DISTANCE,
            speed_of_light=SPEED_OF_LIGHT,
            active_sources=range(num_stations - 1),  # all except last station
        ),
        loglevel=Logger.Level.ERROR
    )

    client = sr.data.stations[0]
    server = sr.data.stations[-1]

    expected_interval_avg = SOURCE_INTERVAL.mean()
    expected_number_of_packets = floor(SIM_TIME_LIMIT / expected_interval_avg)

    assert client.source.num_packets_sent == expected_number_of_packets
    assert (expected_number_of_packets - 1 <=
            server.sink.num_packets_received <= expected_number_of_packets)

    expected_transmission_delay = (PAYLOAD_SIZE.mean() + HEADER_SIZE) / BITRATE
    expected_delay = (DISTANCE / SPEED_OF_LIGHT + expected_transmission_delay
                      ) * (num_stations - 1)

    assert_allclose(client.source.delay_vector.mean(), expected_delay, rtol=0.1)

    client_if = client.get_interface_to(server)
    assert client_if.queue.size_trace.timeavg() == 0

    for i in range(1, num_stations - 1):
        sta = sr.data.stations[i]
        next_sta = sr.data.stations[i + 1]
        sta_if = sta.get_interface_to(next_sta)
        assert sta_if.queue.size_trace.timeavg() == 0

    expected_busy_ratio = expected_transmission_delay / expected_interval_avg
    assert_allclose(client_if.transceiver.busy_vector.mean(),
                    expected_busy_ratio, rtol=0.1)


@pytest.mark.parametrize('num_stations', [(3,), (4,)])
def test_wired_line_network_with_cross_traffic(num_stations):
    sr = simulate(
        WiredLineNetwork,
        stime_limit=SIM_TIME_LIMIT,
        params=dict(
            num_stations=num_stations,
            payload_size=PAYLOAD_SIZE,
            header_size=HEADER_SIZE,
            bitrate=BITRATE,
            distance=DISTANCE,
            speed_of_light=SPEED_OF_LIGHT,
            active_sources=range(num_stations - 1),  # all except last station
        ),
        loglevel=Logger.Level.ERROR
    )

    client = sr.data.stations[0]
    server = sr.data.stations[-1]

    expected_interval_avg = SOURCE_INTERVAL.mean()
    expected_number_of_packets = floor(SIM_TIME_LIMIT / expected_interval_avg)

    assert client.source.num_packets_sent == expected_number_of_packets
    assert (expected_number_of_packets - 1 <=
            server.sink.num_packets_received <= expected_number_of_packets)

    expected_transmission_delay = (PAYLOAD_SIZE.mean() + HEADER_SIZE) / BITRATE
    delay_low_bound = (DISTANCE / SPEED_OF_LIGHT + expected_transmission_delay
                       ) * (num_stations - 1)

    assert client.source.delay_vector.mean() > delay_low_bound

    client_if = client.get_interface_to(server)
    assert client_if.queue.size_trace.timeavg() == 0

    # However, here we make sure that out interfaces for all middle stations
    # have non-empty queues since they also generate traffic at almost the same
    # time as they receive packets from connected stations:
    for i in range(1, num_stations - 1):
        sta = sr.data.stations[i]
        next_sta = sr.data.stations[i + 1]
        sta_if = sta.get_interface_to(next_sta)
        assert sta_if.queue.size_trace.timeavg() > 0

    expected_busy_ratio = expected_transmission_delay / expected_interval_avg
    assert_allclose(client_if.transceiver.busy_vector.mean(),
                    expected_busy_ratio, rtol=0.1)
