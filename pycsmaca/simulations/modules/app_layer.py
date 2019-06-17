from pydesim import Model


class AppData:
    def __init__(self, dest_addr, size, source_id):
        pass


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
