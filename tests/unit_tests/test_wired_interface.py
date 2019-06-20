from unittest.mock import Mock, patch, ANY

import pytest
from numpy import inf

from pycsmaca.simulations.modules.app_layer import AppData
from pycsmaca.simulations.modules.network_layer import NetworkPacket
from pycsmaca.simulations.modules.wired_interface import (
    WiredInterface, WireFrame
)


WIRE_FRAME_CLASS = 'pycsmaca.simulations.modules.wired_interface.WireFrame'


#############################################################################
# TEST WireFrame
#############################################################################
def test_wire_frame_init_and_properties():
    pkt_1 = NetworkPacket(data=AppData(100))
    pkt_2 = NetworkPacket(data=AppData(200))

    frame_1 = WireFrame(pkt_1, header_size=10, preamble=0.2, duration=1.5)
    assert frame_1.packet == pkt_1
    assert frame_1.duration == 1.5
    assert frame_1.header_size == 10
    assert frame_1.preamble == 0.2

    frame_2 = WireFrame(packet=pkt_2)
    assert frame_2.packet == pkt_2
    assert frame_2.duration == 0
    assert frame_2.header_size == 0
    assert frame_2.preamble == 0


def test_wire_frame_implements_str():
    pkt_1 = NetworkPacket(data=AppData(100))
    pkt_2 = NetworkPacket(data=AppData(200))

    frame_1 = WireFrame(pkt_1, header_size=10, preamble=1, duration=2)
    assert str(frame_1) == f'WireFrame[D=2,HDR=10,PR=1 | {pkt_1}]'

    frame_2 = WireFrame(pkt_2)
    assert str(frame_2) == f'WireFrame[D=0,HDR=0,PR=0 | {pkt_2}]'


#############################################################################
# TEST WiredInterface MODEL
#############################################################################

# noinspection PyPropertyAccess
@pytest.mark.parametrize('address, bitrate, header_size, preamble, ifs', (
        (1, 100, 10, 0.2, 0.05),
        (8, 512, 22, 0.08, 0.1),
))
def test_wired_interface_properties(
        address, bitrate, header_size, preamble, ifs
):
    sim = Mock()
    iface = WiredInterface(
        sim, address=address, bitrate=bitrate, header_size=header_size,
        preamble=preamble, ifs=ifs,
    )

    # Check that interface has a read-only address:
    assert iface.address == address
    with pytest.raises(AttributeError):
        iface.address = 13

    # Check that interface has bitrate, header size, preamble and ifs attrs:
    assert iface.bitrate == bitrate
    assert iface.header_size == header_size
    assert iface.preamble == preamble
    assert iface.ifs == ifs

    # We also check that interface is in ready state, but not started:
    assert not iface.started
    assert iface.tx_ready
    assert not iface.tx_busy
    assert iface.rx_ready
    assert not iface.rx_busy

    # Check that statuses are read-only from outside:
    with pytest.raises(AttributeError):
        iface.started = False
    with pytest.raises(AttributeError):
        iface.tx_ready = True
    with pytest.raises(AttributeError):
        iface.tx_busy = False
    with pytest.raises(AttributeError):
        iface.rx_ready = True
    with pytest.raises(AttributeError):
        iface.rx_busy = False


@pytest.mark.parametrize('address, bitrate, header_size, preamble, ifs', (
        (1, 100, 10, 0.2, 0.05),
        (8, 512, 22, 0.08, 0.1),
))
def test_wired_interface_packet_from_queue_transmission(
        address, bitrate, header_size, preamble, ifs
):
    sim = Mock()
    iface = WiredInterface(
        sim, address=address, bitrate=bitrate, header_size=header_size,
        preamble=preamble, ifs=ifs,
    )

    # Now we connect the interface with a queue and start it. Make sure
    # that the queue is connected via 'queue' link, and after start `get_next()`
    # is called.
    queue = Mock()
    queue_rev_conn = Mock()
    queue.connections.set = Mock(return_value=queue_rev_conn)

    queue_conn = iface.connections.set('queue', queue, rname='iface')
    queue.get_next.assert_not_called()

    iface.start()  # start of the interface causes `get_next()` call

    queue.get_next.assert_called_once_with(iface)
    queue.get_next.reset_mock()
    assert iface.started and iface.tx_ready and not iface.tx_busy

    #
    # After being started, interface expects a `NetworkPacket` in its
    # handle_message() call. We connect another mock to the interface via
    # 'peer' connection and make sure that after the call that `send()` was
    # called on that peer connection.
    #
    # Since `WireFrame` objects are expected to be used in connections
    # between peers, we patch them.
    #
    peer = Mock()
    peer_rev_conn = Mock()
    peer.connections.set = Mock(return_value=peer_rev_conn)

    iface.connections.set('peer', peer, rname='peer')
    packet = NetworkPacket(data=AppData(size=500))
    duration = (packet.size + header_size) / bitrate + preamble

    with patch(WIRE_FRAME_CLASS) as WireFrameMock:
        frame_kwargs = {
            'packet': packet,
            'header_size': header_size,
            'duration': duration,
            'preamble': preamble,
        }
        frame_instance = Mock()
        frame_instance.duration = duration
        WireFrameMock.return_value = frame_instance

        iface.handle_message(packet, sender=queue, connection=queue_conn)
        sim.schedule.assert_any_call(
            0, peer.handle_message, args=(frame_instance,), kwargs={
                'connection': peer_rev_conn, 'sender': iface,
            }
        )
        WireFrameMock.assert_called_once_with(**frame_kwargs)

        # Also check that wired interface scheduled a timeout:
        sim.schedule.assert_any_call(duration, iface.handle_tx_end)

        # .. and that now interface is busy:
        assert iface.started and not iface.tx_ready and iface.tx_busy
        sim.schedule.reset_mock()

    # Now we imitate `handle_tx_end()` call, make sure that after that the
    # interface is not yet ready, but schedules `handle_ifs_end()`:
    sim.stime = duration
    iface.handle_tx_end()
    sim.schedule.assert_called_once_with(ifs, iface.handle_ifs_end)
    assert iface.started and not iface.tx_ready and iface.tx_busy

    # After the IFS waiting finished, interface is expected to call
    # `queue.get_next(iface)` and be ready for new packets:
    sim.stime += ifs
    iface.handle_ifs_end()
    queue.get_next.assert_called_once_with(iface)
    assert iface.started and iface.tx_ready and not iface.tx_busy


def test_wired_interface_raises_error_if_requested_tx_during_another_tx():
    sim, peer, queue = Mock(), Mock(), Mock()
    iface = WiredInterface(sim, address=0, bitrate=100)
    queue_conn = iface.connections.set('queue', queue, rname='iface')
    iface.connections.set('peer', peer, rname='peer')

    pkt_1 = NetworkPacket(data=AppData(size=10))
    pkt_2 = NetworkPacket(data=AppData(size=20))

    iface.start()
    iface.handle_message(pkt_1, sender=queue, connection=queue_conn)

    with pytest.raises(RuntimeError):
        iface.handle_message(pkt_2, sender=queue, connection=queue_conn)


def test_wired_interface_sends_data_up_when_rx_completed():
    sim, sender, switch = Mock(), Mock(), Mock()
    sim.stime = 0
    iface = WiredInterface(sim, address=0)

    pkt = NetworkPacket(data=AppData(size=100))
    frame = WireFrame(pkt, duration=0.5, header_size=20, preamble=0.01)

    switch_rev_conn = Mock()
    switch.connections.set = Mock(return_value=switch_rev_conn)
    iface.connections.set('up', switch, rname='iface')
    sender_conn = iface.connections.set('peer', sender, rname='peer')

    assert iface.rx_ready and not iface.rx_busy

    iface.handle_message(frame, sender=sender, connection=sender_conn)
    assert not iface.rx_ready and iface.rx_busy
    sim.schedule.assert_called_once_with(
        frame.duration, iface.handle_rx_end, args=(frame,),
    )
    sim.schedule.reset_mock()

    sim.stime += frame.duration
    iface.handle_rx_end(frame)
    sim.schedule.assert_called_once_with(
        0, switch.handle_message, args=(pkt,), kwargs={
            'sender': iface, 'connection': switch_rev_conn,
        }
    )
    assert iface.rx_ready and not iface.rx_busy


@pytest.mark.parametrize('bitrate, header_size, preamble, size', (
        (1000, 10, 0.2, 1540),
        (2000, 12, 0.3, 800),
))
def test_wired_interface_is_full_duplex(bitrate, header_size, preamble, size):
    sim, peer, queue, switch = Mock(), Mock(), Mock(), Mock()
    sim.stime = 0

    eth = WiredInterface(sim, address=0, header_size=header_size,
                         bitrate=bitrate, preamble=preamble, ifs=0)

    peer_conn = eth.connections.set('peer', peer, reverse=False)
    queue_conn = eth.connections.set('queue', queue, reverse=False)
    eth.connections.set('up', switch, reverse=False)

    inp_pkt = NetworkPacket(data=AppData(size=size))
    out_pkt_1 = NetworkPacket(data=AppData(size=size))
    out_pkt_2 = NetworkPacket(data=AppData(size=size))
    duration = (header_size + size) / bitrate + preamble
    frame = WireFrame(inp_pkt, duration=duration, header_size=header_size,
                      preamble=preamble)

    # 1) Interface starts transmitting `out_pkt_1`:
    sim.stime = 0
    eth.start()
    eth.handle_message(out_pkt_1, queue_conn, queue)
    assert eth.tx_busy
    assert eth.rx_ready
    sim.schedule.assert_any_call(duration, eth.handle_tx_end)
    sim.schedule.assert_any_call(0, peer.handle_message, args=ANY, kwargs=ANY)
    sim.schedule.reset_mock()

    # 2) Then, after 2/3 of the packet was transmitted, a packet arrives:
    sim.stime = 2 * duration / 3
    eth.handle_message(frame, peer_conn, peer)
    assert eth.tx_busy
    assert eth.rx_busy
    sim.schedule.assert_called_with(duration, eth.handle_rx_end, args=(frame,))
    sim.schedule.reset_mock()

    # 3) After duration, call handle_tx_end and handle_ifs_end:
    sim.stime = duration
    eth.handle_tx_end()
    eth.handle_ifs_end()
    assert eth.tx_ready
    assert eth.rx_busy
    sim.schedule.reset_mock()

    # 4) After another 1/3 duration start new TX (during RX this time):
    sim.stime = 4/3 * duration
    eth.handle_message(out_pkt_2, queue_conn, queue)
    assert eth.tx_busy
    assert eth.rx_busy
    sim.schedule.assert_any_call(duration, eth.handle_tx_end)
    sim.schedule.assert_any_call(0, peer.handle_message, args=ANY, kwargs=ANY)
    sim.schedule.reset_mock()

    # 5) After 5/3 duration, RX ends, but TX still goes on:
    sim.stime = 5/3 * duration
    eth.handle_rx_end(frame)
    assert eth.tx_busy
    assert eth.rx_ready
    sim.schedule.assert_called_with(0, switch.handle_message, args=ANY,
                                    kwargs=ANY)


def test_wired_interface_ignores_frames_not_from_peer():
    sim, sender, switch = Mock(), Mock(), Mock()
    sim.stime = 0
    iface = WiredInterface(sim, address=0)

    pkt = NetworkPacket(data=AppData(size=100))
    frame = WireFrame(pkt, duration=0.5, header_size=20, preamble=0.01)

    iface.connections.set('up', switch, reverse=False)
    sender_conn = iface.connections.set('wrong_name', sender, reverse=False)

    iface.handle_message(frame, sender=sender, connection=sender_conn)
    sim.schedule.assert_not_called()
    assert iface.rx_ready
