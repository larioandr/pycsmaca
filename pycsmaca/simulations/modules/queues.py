from collections import deque

from pydesim import Model, Trace


class Queue(Model):
    def __init__(self, sim, capacity=None):
        super().__init__(sim)
        self.__capacity = capacity
        self.__packets = deque()
        self.__num_dropped = 0
        self.__data_requests = deque()
        # Statistics:
        self.__size_trace = Trace()
        self.__bitsize_trace = Trace()
        self.__size_trace.record(sim.stime, 0)
        self.__bitsize_trace.record(sim.stime, 0)

    @property
    def capacity(self):
        return self.__capacity

    @property
    def num_dropped(self):
        return self.__num_dropped

    @property
    def size_trace(self):
        return self.__size_trace

    @property
    def bitsize_trace(self):
        return self.__bitsize_trace

    def empty(self):
        return len(self) == 0

    def full(self):
        return len(self) == self.capacity

    def __len__(self):
        return len(self.__packets)

    def size(self):
        return len(self)

    def bitsize(self):
        return sum(pkt.size for pkt in self.__packets)

    def as_tuple(self):
        return tuple(self.__packets)

    def push(self, packet):
        if self.__data_requests:
            connection = self.__data_requests.popleft()
            connection.send(packet)
        else:
            if self.capacity is None or len(self) < self.capacity:
                self.__packets.append(packet)
                self.__size_trace.record(self.sim.stime, len(self))
                self.__bitsize_trace.record(self.sim.stime, self.bitsize())
            else:
                self.__num_dropped += 1

    def pop(self):
        try:
            ret = self.__packets.popleft()
        except IndexError as err:
            raise ValueError('pop from empty Queue') from err
        else:
            self.__size_trace.record(self.sim.stime, len(self))
            self.__bitsize_trace.record(self.sim.stime, self.bitsize())
            return ret

    def get_next(self, service):
        connection = self._get_connection_to(service)
        if not self.empty():
            connection.send(self.pop())
        else:
            self.__data_requests.append(connection)

    def _get_connection_to(self, module):
        for conn_name, peer in self.connections.as_dict().items():
            if module == peer:
                return self.connections[conn_name]
        raise ValueError(f'connection to {module} not found')

    def __str__(self):
        prefix = f'{self.parent}.' if self.parent is not None else ''
        return f'{prefix}Queue'
