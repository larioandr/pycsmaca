from pydesim import Model


class NetworkPacket:
    def __init__(self, dst_addr, src_addr, rcv_addr, snd_addr, data):
        pass


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
