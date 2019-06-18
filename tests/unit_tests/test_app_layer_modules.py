import pytest
from pydesim import Model
from unittest.mock import Mock, patch
from pycsmaca.simulations.modules.app_layer import RandomSource, AppData


# noinspection PyProtectedMember
def test_random_source_generates_packets():
    sim = Mock()
    source = RandomSource(sim, data_size=Mock(return_value=42),
                          interval=Mock(side_effect=(74, 21)), source_id=34,
                          dest_addr=13)
    assert isinstance(source, Model)

    # Provide necessary connections:
    network_service_mock = Mock()
    source.connections['network'] = network_service_mock

    # First, check that upon construction source scheduled the next packet
    # arrival as specified by `interval` parameter:
    sim.schedule.assert_called_with(74, source._generate)

    # Then, we call that method and make sure that it sends a packet via the
    # 'network' connection. Exactly it means that the connected module
    # `handle_message(packet)` method is called using `sim.schedule`, which
    # is expected to be called from within `source.connections`
    with patch('pycsmaca.simulations.modules.app_layer.AppData') as AppDataMock:
        _spec = dict(dest_addr=13, size=42, source_id=34)
        _packet = Mock(**_spec)
        AppDataMock.return_value = _packet

        source._generate()

        AppDataMock.assert_called_with(**_spec)
        sim.schedule.assert_any_call(
            0, network_service_mock.handle_message, args=(_packet,),
            kwargs={'sender': source}
        )

    # Make sure that after the _generate() call another event was scheduled:
    sim.schedule.assert_any_call(21, source._generate)


# noinspection PyPropertyAccess
def test_app_data_is_immutable():
    app_data = AppData(dest_addr=5, size=20, source_id=13)
    assert app_data.dest_addr == 5
    assert app_data.size == 20
    assert app_data.source_id == 13
    with pytest.raises(AttributeError):
        app_data.dest_addr = 11
    with pytest.raises(AttributeError):
        app_data.size = 21
    with pytest.raises(AttributeError):
        app_data.source_id = 26


def test_app_data_provides_str():
    app_data = AppData(dest_addr=1, size=250, source_id=2)
    assert str(app_data) == 'AppData{sid=2,dst=1,size=250}'
