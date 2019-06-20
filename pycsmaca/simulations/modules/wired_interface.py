from numpy import inf
from pydesim import Model


class WireFrame:
    def __init__(self, packet, duration=0, header_size=0, preamble=0):
        self.packet = packet
        self.duration = duration
        self.header_size = header_size
        self.preamble = preamble

    def __str__(self):
        fields = ','.join([
            f'D={self.duration}', f'HDR={self.header_size}',
            f'PR={self.preamble}'
        ])
        body = f' | {self.packet}' if self.packet else ''
        return f'WireFrame[{fields}{body}]'


class WiredTransceiver(Model):
    def __init__(self, sim, bitrate=inf, header_size=0, preamble=0, ifs=0):
        super().__init__(sim)
        self.bitrate = bitrate
        self.header_size = header_size
        self.preamble = preamble
        self.ifs = ifs
        # State variables:
        self.__started = False
        self.__tx_frame = None
        self.__wait_ifs = False
        self.__rx_frame = None

    @property
    def started(self):
        return self.__started

    @property
    def tx_ready(self):
        return not self.tx_busy

    @property
    def tx_busy(self):
        return self.__tx_frame is not None or self.__wait_ifs

    @property
    def rx_ready(self):
        return self.__rx_frame is None

    @property
    def rx_busy(self):
        return not self.rx_ready

    def start(self):
        self.connections['queue'].module.get_next(self)
        self.__started = True

    def handle_message(self, message, connection=None, sender=None):
        if connection.name == 'queue':
            if self.tx_busy:
                raise RuntimeError('new NetworkPacket while another TX running')
            duration = ((self.header_size + message.size) / self.bitrate +
                        self.preamble)
            frame = WireFrame(
                packet=message, duration=duration, header_size=self.header_size,
                preamble=self.preamble
            )
            self.connections['peer'].send(frame)
            self.sim.schedule(duration, self.handle_tx_end)
            self.__tx_frame = frame
        elif connection.name == 'peer':
            self.sim.schedule(
                message.duration, self.handle_rx_end, args=(message,)
            )
            self.__rx_frame = message

    def handle_tx_end(self):
        self.__tx_frame = None
        self.__wait_ifs = True
        self.sim.schedule(self.ifs, self.handle_ifs_end)

    def handle_ifs_end(self):
        self.__wait_ifs = False
        self.connections['queue'].module.get_next(self)

    def handle_rx_end(self, frame):
        self.connections['up'].send(frame.packet)
        self.__rx_frame = None
