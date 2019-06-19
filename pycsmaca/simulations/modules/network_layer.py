from pydesim import Model


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
