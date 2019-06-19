from pydesim import Model

from pycsmaca.utilities import ReadOnlyDict


class NetworkPacket:
    def __init__(self, dst_addr=None, src_addr=None, rcv_addr=None,
                 snd_addr=None, ssn=None, data=None):
        self.dst_addr = dst_addr
        self.src_addr = src_addr
        self.snd_addr = snd_addr
        self.rcv_addr = rcv_addr
        self.ssn = ssn
        self.data = data

    def __str__(self):
        fields = []
        for field, value in [('DST', self.dst_addr), ('SRC', self.src_addr),
                             ('SND', self.snd_addr), ('RCV', self.rcv_addr),
                             ('SSN', self.ssn)]:
            if value is not None:
                fields.append(f'{field}={value}')
        header = ','.join(fields)
        body = f' | {self.data}' if self.data is not None else ''
        return f'NetPkt{{{header}{body}}}'


class NetworkService(Model):
    def __init__(self, sim):
        super().__init__(sim)

    def handle_message(self, message, connection=None, sender=None):
        if connection == self.connections.get('source'):
            packet = NetworkPacket(
                dst_addr=message.dst_addr, src_addr=None, rcv_addr=None,
                snd_addr=None, data=message
            )
            self.connections['network'].send(packet)
        elif connection == self.connections.get('network'):
            self.connections['sink'].send(message.data)

    def __str__(self):
        prefix = f'{self.parent}.' if self.parent else ''
        return f'{prefix}NetworkService'


class SwitchTable:
    class Link:
        def __init__(self, connection, next_hop):
            self.connection = connection
            self.next_hop = next_hop

        def as_tuple(self):
            return self.connection, self.next_hop

        def __str__(self):
            return f'conn={self.connection}, next_hop={self.next_hop}'

    def __init__(self):
        self.__records = {}

    def add(self, dst, connection, next_hop):
        self.__records[dst] = SwitchTable.Link(connection, next_hop)

    def as_dict(self):
        return ReadOnlyDict({
            dst: link.as_tuple() for dst, link in self.__records.items()
        })

    def __getitem__(self, dst):
        return self.__records[dst]

    def get(self, dst, default=None):
        return self.__records.get(dst, default)

    def __contains__(self, dst):
        return dst in self.__records

    def __str__(self):
        records = (
            f'{dst}: ({link.connection}, {link.next_hop})'
            for dst, link in self.__records.items()
        )
        return f'SwitchTable{{{", ".join(records)}}}'


class NetworkSwitch(Model):
    def __init__(self, sim):
        super().__init__(sim)
        self.__table = SwitchTable()
        self.__ssns = {}

    @property
    def table(self):
        return self.__table

    def handle_message(self, message, connection=None, sender=None):
        assert isinstance(message, NetworkPacket)

        if message.src_addr is not None:
            assert message.ssn is not None
            # Check that this message is not too old by checking its SSN:
            if message.src_addr not in self.__ssns:
                self.__ssns[message.src_addr] = message.ssn
            elif message.ssn <= self.__ssns[message.src_addr]:
                return  # do not process this message due to old SSN
            else:
                self.__ssns[message.src_addr] = message.ssn

        dst_addr = message.dst_addr
        for _, module in self.connections.as_dict().items():
            if hasattr(module, 'address') and module.address == dst_addr:
                self.connections['user'].send(message)
                return

        link = self.table.get(dst_addr)
        if link is None:
            return
        iface_connection = self.connections[link.connection]

        if connection.name == 'user':
            message.src_addr = iface_connection.module.address

            # Choose, assign and inc SSN for the given source address:
            if message.dst_addr not in self.__ssns:
                self.__ssns[message.dst_addr] = 0
            else:
                self.__ssns[message.dst_addr] += 1
            message.ssn = self.__ssns[message.dst_addr]
        else:
            # If the message is not from the user, it MUST have src_addr
            # being properly set. Validate this:
            assert message.src_addr is not None
            assert message.ssn is not None

        # Update receiver and sender addresses, forward the message to
        # the proper interface:
        message.rcv_addr = link.next_hop
        message.snd_addr = iface_connection.module.address
        iface_connection.send(message)

    def __str__(self):
        prefix = f'{self.parent}.' if self.parent is not None else ''
        return f'{prefix}Switch'

