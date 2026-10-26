"""LZX decompression, as used by XNA/MonoGame .xnb content files (window 2^16).

Written from Microsoft's published LZX format description. The stream is
cut into chunks; each chunk is decoded with a fresh bit reader while the
window, the repeated-offset registers and the current block carry over.
"""

from __future__ import annotations

MIN_MATCH = 2
NUM_CHARS = 256
NUM_PRIMARY_LENGTHS = 7
NUM_SECONDARY_LENGTHS = 249
PRETREE_SYMBOLS, PRETREE_BITS = 20, 6
ALIGNED_SYMBOLS, ALIGNED_BITS = 8, 7
LENGTH_BITS, MAIN_BITS = 12, 12
VERBATIM, ALIGNED, UNCOMPRESSED = 1, 2, 3
POSITION_SLOTS = {15: 30, 16: 32, 17: 34, 18: 36, 19: 38, 20: 42, 21: 50}

EXTRA_BITS: list[int] = []
_j = 0
for _i in range(0, 52, 2):
    EXTRA_BITS += [_j, _j]
    if _i and _j < 17:
        _j += 1
POSITION_BASE: list[int] = []
_j = 0
for _i in range(51):
    POSITION_BASE.append(_j)
    _j += 1 << EXTRA_BITS[_i]


class LzxError(ValueError):
    pass


class _Bits:
    """MSB-first bits over 16-bit little-endian words."""

    __slots__ = ("data", "pos", "buf", "n")

    def __init__(self, data: bytes, pos: int = 0):
        self.data, self.pos, self.buf, self.n = data, pos, 0, 0

    def ensure(self, k: int) -> None:
        while self.n < k:
            d, p = self.data, self.pos
            lo = d[p] if p < len(d) else 0
            hi = d[p + 1] if p + 1 < len(d) else 0
            self.pos = p + 2
            self.buf = (self.buf << 16) | (hi << 8) | lo
            self.n += 16

    def peek(self, k: int) -> int:
        self.ensure(k)
        return (self.buf >> (self.n - k)) & ((1 << k) - 1)

    def drop(self, k: int) -> None:
        self.n -= k
        self.buf &= (1 << self.n) - 1

    def read(self, k: int) -> int:
        if k == 0:
            return 0
        v = self.peek(k)
        self.drop(k)
        return v


class _Huffman:
    """Canonical Huffman decoding via a full lookup table on the longest code."""

    __slots__ = ("table", "bits")

    def __init__(self, lengths: list[int]):
        self.bits = max(lengths) if any(lengths) else 1
        size = 1 << self.bits
        table: list[int] = [-1] * size
        code = 0
        for length in range(1, self.bits + 1):
            for sym, ln in enumerate(lengths):
                if ln == length:
                    start = code << (self.bits - length)
                    end = start + (1 << (self.bits - length))
                    if end > size:
                        raise LzxError("over-subscribed Huffman table")
                    table[start:end] = [(sym << 5) | length] * (end - start)
                    code += 1
            code <<= 1
        self.table = table

    def decode(self, bits: _Bits) -> int:
        e = self.table[bits.peek(self.bits)]
        if e < 0:
            raise LzxError("invalid Huffman code")
        bits.drop(e & 31)
        return e >> 5


class LzxDecoder:
    def __init__(self, window_bits: int = 16):
        if window_bits not in POSITION_SLOTS:
            raise LzxError(f"unsupported window size 2^{window_bits}")
        self.window_size = 1 << window_bits
        self.window = bytearray(self.window_size)
        self.abs = 0  # bytes written to the window, ever
        self.frame_abs = 0  # where the next output frame starts
        self.main_elements = NUM_CHARS + POSITION_SLOTS[window_bits] * 8
        self.main_len = [0] * self.main_elements
        self.length_len = [0] * NUM_SECONDARY_LENGTHS
        self.r = [1, 1, 1]
        self.header_read = False
        self.block_type = 0
        self.block_remaining = 0
        self.block_length = 0
        self.main = self.length = self.aligned = None

    def _read_lengths(self, bits: _Bits, lens: list[int], first: int, last: int) -> None:
        pre = _Huffman([bits.read(4) for _ in range(PRETREE_SYMBOLS)])
        x = first
        while x < last:
            z = pre.decode(bits)
            if z == 17:
                run = bits.read(4) + 4
                lens[x:x + run] = [0] * run
                x += run
            elif z == 18:
                run = bits.read(5) + 20
                lens[x:x + run] = [0] * run
                x += run
            elif z == 19:
                run = bits.read(1) + 4
                z = pre.decode(bits)
                v = (lens[x] - z + 17) % 17
                lens[x:x + run] = [v] * run
                x += run
            else:
                lens[x] = (lens[x] - z + 17) % 17
                x += 1

    def _new_block(self, bits: _Bits) -> _Bits:
        data = bits.data
        if self.block_type == UNCOMPRESSED:  # realign after an odd-length raw block
            if self.block_length & 1:
                bits = _Bits(data, bits.pos + 1)
            else:
                bits = _Bits(data, bits.pos)
        self.block_type = bits.read(3)
        self.block_remaining = self.block_length = (bits.read(16) << 8) | bits.read(8)
        if self.block_type == ALIGNED:
            self.aligned = _Huffman([bits.read(3) for _ in range(ALIGNED_SYMBOLS)])
        if self.block_type in (VERBATIM, ALIGNED):
            self._read_lengths(bits, self.main_len, 0, NUM_CHARS)
            self._read_lengths(bits, self.main_len, NUM_CHARS, self.main_elements)
            self.main = _Huffman(self.main_len)
            self._read_lengths(bits, self.length_len, 0, NUM_SECONDARY_LENGTHS)
            self.length = _Huffman(self.length_len)
        elif self.block_type == UNCOMPRESSED:
            bits.ensure(16)
            pos = bits.pos - (2 if bits.n > 16 else 0)
            self.r = [int.from_bytes(data[pos + 4 * i:pos + 4 * i + 4], "little") for i in range(3)]
            bits = _Bits(data, pos + 12)
        else:
            raise LzxError(f"bad block type {self.block_type}")
        return bits

    def decompress(self, chunk: bytes, out_len: int) -> bytes:
        """Decode one chunk; return the next `out_len` bytes of output. A match may run past the frame:
        those bytes are already in the window and start the next frame."""
        bits = _Bits(chunk)
        if not self.header_read:
            if bits.read(1):  # Intel E8 translation: not used by XNA content
                raise LzxError("E8 translation is not supported")
            self.header_read = True
        window, mask = self.window, self.window_size - 1
        frame_end = self.frame_abs + out_len
        r0, r1, r2 = self.r
        while self.abs < frame_end:
            if self.block_remaining == 0:
                self.r = [r0, r1, r2]
                bits = self._new_block(bits)
                r0, r1, r2 = self.r
            todo = min(self.block_remaining, frame_end - self.abs)
            if self.block_type == UNCOMPRESSED:
                for b in bits.data[bits.pos:bits.pos + todo]:
                    window[self.abs & mask] = b
                    self.abs += 1
                bits.pos += todo
                self.block_remaining -= todo
                continue
            aligned_block = self.block_type == ALIGNED
            main, length, aligned = self.main, self.length, self.aligned
            w = self.abs
            stop = w + todo
            while w < stop:
                sym = main.decode(bits)
                if sym < NUM_CHARS:
                    window[w & mask] = sym
                    w += 1
                    continue
                sym -= NUM_CHARS
                match_len = sym & NUM_PRIMARY_LENGTHS
                if match_len == NUM_PRIMARY_LENGTHS:
                    match_len += length.decode(bits)
                match_len += MIN_MATCH
                slot = sym >> 3
                if slot > 2:
                    extra = EXTRA_BITS[slot]
                    off = POSITION_BASE[slot] - 2
                    if aligned_block and extra >= 3:
                        if extra > 3:
                            off += bits.read(extra - 3) << 3
                        off += aligned.decode(bits)
                    elif extra:
                        off += bits.read(extra)
                    else:
                        off = 1
                    r2, r1, r0 = r1, r0, off
                elif slot == 0:
                    off = r0
                elif slot == 1:
                    off = r1
                    r1, r0 = r0, off
                else:
                    off = r2
                    r2, r0 = r0, off
                for _ in range(match_len):
                    window[w & mask] = window[(w - off) & mask]
                    w += 1
            self.block_remaining -= w - self.abs
            if self.block_remaining < 0:
                raise LzxError("match ran past the end of its block")
            self.abs = w
        self.r = [r0, r1, r2]
        start = self.frame_abs & mask
        self.frame_abs = frame_end
        if start + out_len <= self.window_size:
            return bytes(window[start:start + out_len])
        return bytes(window[start:]) + bytes(window[:start + out_len - self.window_size])


def decompress_xnb(data: bytes, out_size: int) -> bytes:
    """XNA framing: each chunk is [0xFF frame_hi frame_lo] block_hi block_lo, then that many bytes."""
    dec = LzxDecoder(16)
    out = bytearray()
    pos = 0
    while pos < len(data) and len(out) < out_size:
        frame_size = 0x8000
        hi = data[pos]
        if hi == 0xFF:
            frame_size = (data[pos + 1] << 8) | data[pos + 2]
            block_size = (data[pos + 3] << 8) | data[pos + 4]
            pos += 5
        else:
            block_size = (hi << 8) | data[pos + 1]
            pos += 2
        if block_size == 0 or frame_size == 0:
            break
        out += dec.decompress(data[pos:pos + block_size], min(frame_size, out_size - len(out)))
        pos += block_size
    if len(out) != out_size:
        raise LzxError(f"decompressed {len(out)} bytes, expected {out_size}")
    return bytes(out)
