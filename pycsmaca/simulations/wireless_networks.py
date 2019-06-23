from math import pi, cos, sin

from numpy.random.mtrand import uniform
from pydesim import Model

from pycsmaca.simulations.modules import RandomSource, Queue, Transmitter, \
    Receiver, Radio, ConnectionManager, WirelessInterface, SaturatedQueue
from pycsmaca.simulations.modules.app_layer import ControlledSource
from pycsmaca.simulations.modules.station import Station


class _HalfDuplexNetworkBase(Model):
    def __init__(self, sim):
        super().__init__(sim)

        if sim.params.num_stations < 2:
            raise ValueError('minimum number of stations in network is 2')

        # Building connection manager:
        self.__conn_manager = ConnectionManager(sim)

        self.__stations = []

        conn_radius = sim.params.connection_radius
        for i in range(sim.params.num_stations):
            # Building elementary components:
            source = self.create_source(i)
            max_propagation = conn_radius / sim.params.speed_of_light
            transmitter = Transmitter(sim, max_propagation=max_propagation)
            receiver = Receiver(sim)
            queue = self.create_queue(i, source=source)
            radio = Radio(
                sim, self.__conn_manager,
                connection_radius=conn_radius,
                position=self.get_position(i)
            )

            # Building wireless interfaces:
            iface = WirelessInterface(sim, i + 1, queue, transmitter,
                                      receiver, radio)

            # Building station:
            sta = Station(sim, source=source, interfaces=[iface])
            self.__stations.append(sta)

            # Writing switching table:
            self.write_switch_table(i)

        # Adding stations as children:
        self.children['stations'] = self.__stations

    @property
    def destination_address(self):
        raise NotImplementedError

    def create_source(self, index):
        raise NotImplementedError

    def create_queue(self, index, source=None):
        return Queue(self.sim)

    def get_position(self, index):
        raise NotImplementedError

    def write_switch_table(self, index):
        raise NotImplementedError

    @property
    def stations(self):
        return self.__stations

    @property
    def connection_manager(self):
        return self.__conn_manager

    @property
    def num_stations(self):
        return len(self.stations)

    def get_iface(self, index):
        if index < self.num_stations:
            return self.stations[index].interfaces[-1]
        raise ValueError(f'station index {index} out of bounds')

    def __str__(self):
        return 'Network'


class WirelessHalfDuplexLineNetwork(_HalfDuplexNetworkBase):
    def __init__(self, sim):
        super().__init__(sim)

    def create_source(self, index):
        if index in self.sim.params.active_sources:
            return RandomSource(
                self.sim,
                self.sim.params.payload_size,
                self.sim.params.source_interval,
                source_id=index,
                dest_addr=self.destination_address
            )
        return None

    @property
    def destination_address(self):
        return self.sim.params.num_stations

    def get_position(self, index):
        return index * self.sim.params.distance, 0

    def write_switch_table(self, index):
        if index < self.sim.params.num_stations - 1:
            sta = self.stations[index]
            iface = sta.interfaces[0]
            switch_conn = sta.get_switch_connection_for(iface)
            sta.switch.table.add(
                self.destination_address,
                switch_conn.name,
                iface.address + 1
            )


class CollisionDomainNetwork(_HalfDuplexNetworkBase):
    def __init__(self, sim):
        super().__init__(sim)

    @property
    def destination_address(self):
        return 1

    def create_source(self, index):
        if index > 0:
            return RandomSource(
                self.sim, self.sim.params.payload_size,
                self.sim.params.source_interval,
                source_id=index, dest_addr=self.destination_address
            )
        return None

    def get_position(self, index):
        area_radius = self.sim.params.connection_radius / 2.1
        distance, angle = uniform(0.1, 1) * area_radius, uniform(0, 2 * pi)
        position = (distance * cos(angle), distance * sin(angle))
        return position

    def write_switch_table(self, index):
        if index > 0:
            sta = self.stations[index]
            iface = sta.interfaces[0]
            switch_conn = sta.get_switch_connection_for(iface)
            sta.switch.table.add(
                self.destination_address,
                switch_conn.name,
                self.destination_address
            )


class CollisionDomainSaturatedNetwork(CollisionDomainNetwork):
    def __init__(self, sim):
        super().__init__(sim)

    def create_source(self, index):
        if index > 0:
            return ControlledSource(
                self.sim, self.sim.params.payload_size,
                source_id=index, dest_addr=self.destination_address
            )
        return None

    def create_queue(self, index, source=None):
        if index > 0:
            return SaturatedQueue(self.sim, source=source)
        return Queue(self.sim)

