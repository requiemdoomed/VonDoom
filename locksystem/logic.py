"""A two-bit Moore machine, clocked once per submitted key."""


def _check(state, key):
    if type(state) is not int or not 0 <= state <= 3:
        raise ValueError("State must be an integer from 0 to 3.")
    if type(key) is not int or not 0 <= key <= 15:
        raise ValueError("Key must be an integer from 0 to 15.")


def decode(key):
    _check(0, key)
    b3, b2, b1, b0 = ((key >> i) & 1 for i in (3, 2, 1, 0))
    return (b3 & (1-b2) & b1 & (1-b0),
            (1-b3) & b2 & b1 & (1-b0),
            b3 & (1-b2) & (1-b1) & b0)


def table_next(state, key):
    _check(state, key)
    return state + 1 if state < 3 and key == (10, 6, 9)[state] else 0


def gate_next(state, key):
    _check(state, key)
    q1, q0 = state >> 1, state & 1
    i10, i6, i9 = decode(key)
    d1 = ((1-q1) & q0 & i6) | (q1 & (1-q0) & i9)
    d0 = ((1-q1) & (1-q0) & i10) | (q1 & (1-q0) & i9)
    return (d1 << 1) | d0


class SequenceLock:
    def __init__(self):
        self.state = 0

    @property
    def unlocked(self):
        return self.state == 3

    def press(self, key):
        self.state = gate_next(self.state, key)
        return self.state

    def reset(self):
        self.state = 0
