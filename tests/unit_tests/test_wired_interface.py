from unittest.mock import Mock, patch, ANY

import pytest

from pycsmaca.simulations.modules.app_layer import AppData
from pycsmaca.simulations.modules.network_layer import NetworkPacket
from pycsmaca.simulations.modules.wired_interface import (
    WiredInterface, WireFrame
)


WIRE_FRAME_CLASS = 'pycsmaca.simulations.modules.wired_interface.WireFrame'


@pytest.mark.parametrize('address, bitrate, header_size, preamble', (
        (1, 100, 10, 0.2),
        (8, 512, 22, 0.08),
))
def test_wired_interface_properties(address, bitrate, header_size, preamble):
    sim = Mock()
    iface = WiredInterface(
        sim, address=address, bitrate=bitrate, header_size=header_size,
        preamble=preamble,
    )

    # Check that interface has a read-only address:
    assert iface.address == address
    with pytest.raises(AttributeError):
        iface.address = 13

    # Check that interface has bitrate, and it may be updated:
    assert iface.bitrate == bitrate
    iface.bitrate = 3434
    assert iface.bitrate == 3434
    iface.bitrate = bitrate

    # Check that header size and preamble can be read:
    assert iface.header_size == header_size
    assert iface.preamble == preamble

    # We also check that interface is in ready state, but not started:
    assert iface.tx_ready
    assert not iface.busy
    assert not iface.started


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

    assert iface.started and iface.tx_ready and not iface.busy
    queue.get_next.assert_called_once_with(iface)
    queue.get_next.reset_mock()

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
        WireFrameMock.return_value = frame_instance

        iface.handle_message(packet, sender=queue, connection=queue_conn)
        sim.schedule.assert_any_call(
            0, peer.handle_message, args=(frame_instance,), kwargs={
                'connection': peer_rev_conn, 'sender': iface,
            }
        )
        WireFrameMock.assert_called_once_with(**frame_kwargs)

        # Also check that wired interface scheduled a timeout:
        sim.schedule.assert_any_call(
            duration, iface.handle_tx_end, args=ANY, kwargs=ANY
        )

        # .. and that now interface is busy:
        assert iface.started and not iface.tx_ready and iface.busy
        sim.schedule.reset_mock()

    # Now we imitate `handle_tx_end()` call, make sure that after that the
    # interface is not yet ready, but schedules `handle_ifs_end()`:
    sim.stime = duration
    iface.handle_tx_end()
    sim.schedule.assert_called_once_with(
        ifs, iface.handle_ifs_end, args=ANY, kwargs=ANY
    )
    assert iface.started and not iface.tx_ready and iface.busy

    # After the IFS waiting finished, interface is expected to call
    # `queue.get_next(iface)` and be ready for new packets:
    sim.stime += ifs
    iface.handle_ifs_end()
    queue.get_next.assert_called_once_with(iface)
    assert iface.started and iface.tx_ready and not iface.tx_busy


def test_wired_interface_raises_error_if_requested_tx_during_another_tx():
    sim, peer, queue = Mock(), Mock(), Mock()
    iface = WiredInterface(sim, address=0, bitrate=100)
    queue_conn = iface.connect('queue', queue, rname='iface')
    iface.connect('peer', peer, rname='peer')

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

    iface.handle_message(frame, sender=sender, conneciton=sender_conn)
    assert not iface.rx_ready and iface.rx_busy
    sim.schedule.assert_called_once_with(
        frame.duration, iface.handle_rx_end, args=(frame,), kwargs=ANY
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


def test_wired_interface_is_full_duplex():
    bitrate = [1000, 1500]
    address = [10, 20]
    size = [190, 140]
    preamble = [0.05, 0.08]
    header_size = [16, 12]
    ifs = [0.1, 0.2]
    delay = 0.0023
    duration = [
        preamble[i] + (size[i] + header_size[i]) / bitrate[i] for i in range(2)
    ]
    packets = [NetworkPacket(data=AppData(size=sz)) for sz in size]
    frame_mocks = [Mock(), Mock()]
    for frame, pkt, d, hs in zip(frame_mocks, packets, duration, header_size):
        frame.packet = pkt
        frame.duration = d
        frame.header_size = hs

    sim, queues, switches = Mock(), (Mock(), Mock()), (Mock(), Mock())
    sim.stime = 0

    ifaces = [
        WiredInterface(sim, address=a, bitrate=b, preamble=p, header_size=h)
        for a, b, p, h in zip(address, bitrate, preamble, header_size)
    ]

    queue_rev_conns = []
    switch_rev_conns = []
    for i in range(2):
        queue_rev_conn = Mock()
        queues[i].connections.set = Mock(return_value=queue_rev_conn)
        queue_rev_conns.append(queue_rev_conn)

        switch_rev_conn = Mock()
        switches[i].connections.set = Mock(return_value=switch_rev_conn)
        switch_rev_conns.append(switch_rev_conn)

        ifaces[i].connect('queue', queues[i], rname='iface')
        ifaces[i].connect('up', switches[i], rname='iface')

        ifaces[i].start()

    ifaces[0].connections.set('peer', ifaces[1], rname='peer')
    ifaces[0].connections['peer'].delay = delay
    ifaces[1].connections['peer'].delay = delay

    with patch(WIRE_FRAME_CLASS) as WireFrameMock:
        #
        # 1) The first interface starts transmit:
        #
        WireFrameMock.return_value = frame_mocks[0]
        ifaces[0].handle_message(
            packets[0], sender='queue', connection=queue_rev_conns[0]
        )
        sim.schedule.assert_any_call(
            delay, ifaces[1].handle_message, args=(frame_mocks[0],), kwargs={
                'sender': ifaces[0], 'connection': ifaces[0].connections['peer']
            }
        )
        sim.schedule.reset_mock()
        assert ifaces[0].tx_busy and ifaces[0].rx_ready

        # ... and the second interface also starts transmit:
        WireFrameMock.return_value = frame_mocks[1]
        ifaces[1].handle_message(
            packets[1], sender='queue', connection=queue_rev_conns[1]
        )
        sim.schedule.assert_any_call(
            delay, ifaces[0].handle_message, args=(frame_mocks[1],), kwargs={
                'sender': ifaces[1], 'connection': ifaces[1].connections['peer']
            }
        )
        sim.schedule.reset_mock()
        assert ifaces[1].tx_busy and ifaces[1].rx_ready

        #
        # 2) Simulate like the message receive started (propagation delay
        # is smaller then packet duration):
        #
        sim.stime = delay
        ifaces[1].handle_message(
            frame_mocks[0], sender=ifaces[0],
            connection=ifaces[1].connections['peer']
        )
        sim.schedule.assert_called_once_with(
            duration[0], ifaces[1].handle_rx_end, args=frame_mocks[0],
            kwargs=ANY
        )
        sim.schedule.reset_mock()
        assert ifaces[1].tx_busy and ifaces[1].rx_busy

        ifaces[0].handle_message(
            frame_mocks[1], sender=ifaces[1],
            connection=ifaces[0].connections['peer']
        )
        sim.schedule.assert_called_once_with(
            duration[0], ifaces[1].handle_rx_end, args=frame_mocks[0],
            kwargs=ANY
        )
        sim.schedule.reset_mock()
        assert ifaces[0].tx_busy and ifaces[0].rx_busy

        # If we are here and now errors raised, everything is expected to be
        # fine - finish the test.
