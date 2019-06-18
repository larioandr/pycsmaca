import pytest
from pydesim import Model, simulate
from unittest.mock import Mock, patch, ANY
from pycsmaca.simulations.modules.app_layer import RandomSource, AppData, Sink


class DummyModel(Model):
    """We use this `DummyModel` when we need a full-functioning model.
    """
    def __init__(self, sim, name):
        super().__init__(sim)
        self.name = name

    def __str__(self):
        return self.name


#############################################################################
# TEST RandomSource MODULE
#############################################################################

# noinspection PyProtectedMember
def test_random_source_generates_packets():
    """In this test we check that `RandomSource` properly generates `AppData`.
    """
    # First, we create the `RandomSource` module, validate it is
    # inherited from `pydesim.Module` and check that upon construction source
    # scheduled the next packet arrival as specified by `interval` parameter:
    sim = Mock()
    sim.stime = 0
    source = RandomSource(sim, data_size=Mock(return_value=42),
                          interval=Mock(side_effect=(74, 21)), source_id=34,
                          dest_addr=13)
    assert isinstance(source, Model)
    sim.schedule.assert_called_with(74, source._generate)

    # Define a mock for NetworkLayer module and establish a connection:
    network_service_mock = Mock()
    source.connections['network'] = network_service_mock

    # Now we call method `_generate()` method and make sure that it sends a
    # packet via the 'network' connection.
    # Exactly it means that the connected module `handle_message(packet)`
    # method is called using `sim.schedule`, which is expected to be called
    # from within `source.connections['network']` connection.
    with patch('pycsmaca.simulations.modules.app_layer.AppData') as AppDataMock:
        _spec = dict(dest_addr=13, size=42, source_id=34)
        _packet = Mock(**_spec)
        AppDataMock.return_value = _packet

        source._generate()

        AppDataMock.assert_called_with(**_spec)

        rev_conn = source.connections['network'].reverse
        sim.schedule.assert_any_call(
            0, network_service_mock.handle_message, args=(_packet,),
            kwargs={'sender': source, 'connection': rev_conn}
        )

    # Finally, we make sure that after the _generate() call another event
    # was scheduled:
    sim.schedule.assert_any_call(21, source._generate)


# noinspection PyProtectedMember
def test_random_source_can_use_constant_distributions():
    """Validate that numeric constants can be used instead of distributions.
    """
    sim = Mock()
    sim.stime = 0
    source = RandomSource(
        sim, data_size=123, interval=34, source_id=0, dest_addr=1)

    network_service_mock = Mock()
    source.connections['network'] = network_service_mock
    sim.schedule.assert_called_with(34, source._generate)

    with patch('pycsmaca.simulations.modules.app_layer.AppData') as AppDataMock:
        _spec = dict(dest_addr=1, size=123, source_id=0)
        _packet = Mock(**_spec)
        AppDataMock.return_value = _packet

        source._generate()
        AppDataMock.assert_called_with(**_spec)

    sim.schedule.assert_any_call(34, source._generate)


# noinspection PyProtectedMember
def test_random_source_can_use_finite_intervals_distributions():
    """Validate that `RandomSource` will stop when intervals is finite tuple.
    """
    sim = Mock()
    sim.stime = 0
    source = RandomSource(
        sim, data_size=123, interval=(34, 42,), source_id=0, dest_addr=1)

    network_service_mock = Mock()
    source.connections['network'] = network_service_mock
    rev_conn = source.connections['network'].reverse

    sim.schedule.assert_called_with(34, source._generate)
    sim.schedule.reset_mock()

    source._generate()
    sim.schedule.assert_any_call(42, source._generate)
    sim.schedule.reset_mock()

    source._generate()
    sim.schedule.assert_called_once_with(
        0, network_service_mock.handle_message, args=(ANY,),
        kwargs={'sender': source, 'connection': rev_conn}
    )


# noinspection PyProtectedMember
def test_random_source_can_use_finite_data_size_distributions():
    """Validate that `RandomSource` will stop when data size is finite tuple.
    """
    sim = Mock()
    sim.stime = 0
    source = RandomSource(
        sim, data_size=(10, 20), interval=100, source_id=0, dest_addr=1)

    network_service_mock = Mock()
    source.connections['network'] = network_service_mock

    with patch('pycsmaca.simulations.modules.app_layer.AppData') as AppDataMock:
        source._generate()
        AppDataMock.assert_called_with(dest_addr=1, source_id=0, size=10)
        AppDataMock.reset_mock()

        source._generate()
        AppDataMock.assert_called_with(dest_addr=1, source_id=0, size=20)
        AppDataMock.reset_mock()

        sim.schedule.reset_mock()
        source._generate()
        AppDataMock.assert_not_called()
        sim.schedule.assert_not_called()


# noinspection PyProtectedMember
def test_random_source_provides_intervals_and_sizes_statistics():
    """Validate that `RandomSource` provides statistics.
    """
    intervals = (10, 12, 15, 17)
    data_size = (123, 453, 245, 321)

    class TestModel(Model):
        def __init__(self, sim):
            super().__init__(sim)
            self.source = RandomSource(
                sim, source_id=34, dest_addr=13,
                data_size=Mock(side_effect=data_size),
                interval=Mock(side_effect=(intervals + (1000,))),
            )
            self.network = DummyModel(sim, 'Network')
            self.source.connections['network'] = self.network

    ret = simulate(TestModel, stime_limit=sum(intervals))

    assert ret.data.source.arrival_intervals.as_tuple() == intervals
    assert ret.data.source.data_size_stat.as_tuple() == data_size

    # Also check that we can not replace statistics:
    with pytest.raises(AttributeError):
        from pydesim import Intervals
        ret.data.source.arrival_intervals = Intervals()
    with pytest.raises(AttributeError):
        from pydesim import Statistic
        ret.data.source.data_size_stat = Statistic()


#############################################################################
# TEST AppData PACKETS
#############################################################################
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


#############################################################################
# TEST Sink MODULE
#############################################################################
# def test_sink_module_accept_app_data():
#     class TestModel(Model):
#         def __init__(self, sim):
#             super().__init__(sim)
#             self.sink = Sink()
#             self.sources = [
#                 RandomSource(sim, 100, Mock(side_effect=(10, 100, 200)), 0, 5),
#                 RandomSource(sim, 300, Mock(side_effect=(20, 400, 80)), 1, 5),
#             ]
#             for source in self.sources:
#                 conn = source.connections.set('sink', self.sink, reverse=False)
#                 conn.delay = Mock()
