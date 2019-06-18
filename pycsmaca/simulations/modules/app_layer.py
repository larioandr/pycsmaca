from pydesim import Model, Intervals, Statistic


class AppData:
    def __init__(self, dest_addr, size, source_id):
        self.__dest_addr = dest_addr
        self.__size = size
        self.__source_id = source_id

    @property
    def dest_addr(self):
        return self.__dest_addr

    @property
    def size(self):
        return self.__size

    @property
    def source_id(self):
        return self.__source_id

    def __str__(self):
        fields = ','.join([
            f'sid={self.source_id}', f'dst={self.dest_addr}',
            f'size={self.size}'
        ])
        return f'AppData{{{fields}}}'


class RandomSource(Model):
    """This module provides data source with independent intervals and sizes.

    `RandomSource` generates `AppData` packets with a given bit size
    distribution. Inter-arrival intervals are also randomly distributed,
    and this distribution is independent from data size distribution.

    Note: distributions are passed to the constructor as callable objects,
    but they also can be specified with constants.

    Source directs its packets to network layer. Packets have a given
    destination address. Source is specified with its SourceID.

    Provided statistics:
    - `arrival_intervals`: inter-arrival intervals;
    - `data_size_stat`: generated data sizes statistics.

    Events:
    - timeout: fired when inter-arrival interval is reached.

    Connections:
    - 'network': connected network layer module; should implement
        `handle_message(app_data)` method.
    """
    def __init__(self, sim, data_size, interval, source_id, dest_addr):
        """Create `RandomSource` module.

        :param sim: `pydesim.Simulator` object;
        :param data_size: callable without arguments or constant, application
            data size distribution;
        :param interval: callable without arguments or constant, inter-arrival
            intervals distribution;
        :param source_id: this source ID (more like IP address, not MAC)
        :param dest_addr: destination MAC address.
        """
        super().__init__(sim)
        self.data_size = data_size
        self.interval = interval
        self.source_id = source_id
        self.dest_addr = dest_addr
        # Statistics:
        self.__arrival_intervals = Intervals()
        self.__data_size_stat = Statistic()
        # Initialize:
        sim.schedule(self.__get_next_interval(), self._generate)

    @property
    def arrival_intervals(self):
        return self.__arrival_intervals

    @property
    def data_size_stat(self):
        return self.__data_size_stat

    def _generate(self):
        data_size = self.__get_next_size()
        app_data = AppData(dest_addr=self.dest_addr, size=data_size,
                           source_id=self.source_id)
        self.connections['network'].send(app_data)
        self.sim.schedule(self.__get_next_interval(), self._generate)
        # Recording statistics:
        self.arrival_intervals.record(self.sim.stime)
        self.data_size_stat.append(data_size)

    def __get_next_interval(self):
        try:
            return self.interval()
        except TypeError:
            return self.interval

    def __get_next_size(self):
        try:
            return self.data_size()
        except TypeError:
            return self.data_size

    def __str__(self):
        return f'Source({self.source_id})'
