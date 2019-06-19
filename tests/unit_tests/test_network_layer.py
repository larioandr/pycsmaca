from collections import namedtuple
from unittest.mock import Mock, patch

from pydesim import Model

from pycsmaca.simulations.modules.network_layer import NetworkService


NET_PACKET_CLASS = 'pycsmaca.simulations.modules.network_layer.NetworkPacket'


class DummyModel(Model):
    """We use this `DummyModel` when we need a full-functioning model.
    """
    def __init__(self, sim, name):
        super().__init__(sim)
        self.name = name

    def __str__(self):
        return self.name


#############################################################################
# TEST NetworkService
#############################################################################
def test_network_service_accepts_packets_from_app():
    sim, app, net = Mock(), Mock(), Mock()
    ns = NetworkService(sim)
    app_conn = ns.connections.set('source', app, reverse=False)

    net_conn = Mock()
    net.connections.set = Mock(return_value=net_conn)

    ns.connections.set('network', net, rname='user')
    net.connections.set.assert_called_once_with('user', ns, reverse=False)

    # Now we simulate packet arrival from APP:
    app_data = Mock()
    app_data.dst_addr = 13
    with patch(NET_PACKET_CLASS) as NetworkPacketMock:
        pkt_spec = dict(
            src_addr=None, dst_addr=13, rcv_addr=None, snd_addr=None,
            data=app_data
        )
        packet_instance_mock = Mock()
        NetworkPacketMock.return_value = packet_instance_mock

        # Calling `handle_message()` as it to be called upon receiving new
        # `AppData` from 'app' connection:
        ns.handle_message(app_data, connection=app_conn, sender=app)

        # Check that a packet was properly created and also that
        # Network.handle_message() was called:
        NetworkPacketMock.assert_called_once_with(**pkt_spec)
        sim.schedule.assert_called_with(
            0, net.handle_message, args=(packet_instance_mock,), kwargs={
                'connection': net_conn, 'sender': ns,
            }
        )


def test_network_service_ignores_app_data_via_other_connections():
    sim, app = Mock(), Mock()
    ns = NetworkService(sim)
    wrong_app_conn = ns.connections.set('wrong_name', app, reverse=False)

    # Now we simulate packet arrival from APP via unsupported connection:
    app_data = Mock()
    app_data.dst_addr = 1
    with patch(NET_PACKET_CLASS) as NetworkPacketMock:
        # Imitate packet AppData arrival via wrong connections and make
        # sure it doesn't cause NetworkPacket instantiation:
        ns.handle_message(app_data, connection=wrong_app_conn, sender=app)
        NetworkPacketMock.assert_not_called()


def test_network_service_accept_packets_from_network():
    sim, network, sink = Mock(), Mock(), Mock()
    ns = NetworkService(sim)
    net_conn = ns.connections.set('network', network, reverse=False)

    sink_conn = Mock()
    sink.connections.set = Mock(return_value=sink_conn)
    ns.connections.set('sink', sink, rname='network')

    # Now we are going to simulate `NetworkPacket` arrival and make sure
    # `AppData` is extracted and passed up via the "sink" connection.
    # First, we define app_data and network_packet:
    app_data = Mock()
    network_packet = Mock()
    network_packet.data = app_data

    # Calling `handle_message()` as it to be called upon receiving new
    # `NetworkPacket` from 'network' connection:
    ns.handle_message(network_packet, connection=net_conn, sender=network)

    # Check that `sink.handle_message` call is scheduled:
    sim.schedule.assert_called_with(
        0, sink.handle_message, args=(app_data,), kwargs={
            'connection': sink_conn, 'sender': ns,
        }
    )


def test_network_service_ignores_net_packets_received_via_other_connections():
    sim, network = Mock(), Mock()
    ns = NetworkService(sim)
    wrong_conn = ns.connections.set('wrong_name', network, reverse=False)

    # Imitate `NetworkPacket` arrival via the wrong connection and make sure
    # nothing is being scheduled:
    network_packet = Mock()
    ns.handle_message(network_packet, connection=wrong_conn, sender=network)
    sim.schedule.assert_not_called()


def test_str_uses_parent_if_specified():
    sim = Mock()
    parent = DummyModel(sim, 'DummyParent')
    ns1 = NetworkService(sim)
    ns2 = NetworkService(sim)
    parent.children['ns'] = ns2

    assert str(ns1) == "NetworkService"
    assert str(ns2) == "DummyParent.NetworkService"
