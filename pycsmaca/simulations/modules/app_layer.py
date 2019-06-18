from pydesim import Model


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
    def __init__(self, sim, data_size, interval, source_id, dest_addr):
        super().__init__(sim)
        self.data_size = data_size
        self.interval = interval
        self.source_id = source_id
        self.dest_addr = dest_addr
        # Initialize:
        sim.schedule(interval(), self._generate)

    def _generate(self):
        app_data = AppData(dest_addr=self.dest_addr, size=self.data_size(),
                           source_id=self.source_id)
        self.connections['network'].send(app_data)
        self.sim.schedule(self.interval(), self._generate)

    def handle_message(self, message, sender=None):
        pass
