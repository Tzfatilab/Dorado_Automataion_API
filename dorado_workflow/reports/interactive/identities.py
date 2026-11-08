"""Join exported source records by NanoTel Serial while preserving original IDs."""


def serial_number(value):
    try:
        number = float(value)
        return int(number) if number >= 1 and number.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        return None


class ReadIndex:
    def __init__(self, reads):
        self.full, self.tokens, self.serials = {}, {}, {}
        for read in reads:
            self.full.setdefault(read.original_id, []).append(read)
            self.tokens.setdefault(read.original_id.split()[0], []).append(read)
            fact = read.metrics.get('read_number')
            if fact and fact.status == 'available':
                self.serials.setdefault(serial_number(fact.value), []).append(read)

    def find(self, identifier, serial=None):
        identifier = str(identifier or '').strip()
        if not identifier:
            return []
        candidates = self.full.get(identifier, []) or self.tokens.get(identifier.split()[0], [])
        number = serial_number(serial)
        if number is not None:
            allowed = {read.id for read in self.serials.get(number, [])}
            candidates = [read for read in candidates if read.id in allowed]
        return candidates
