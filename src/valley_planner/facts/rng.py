"""The game's random numbers, so seeded rolls (the Traveling Cart's stock…) can be worked out ahead.

In our words:
- The game uses .NET's System.Random created from a seed: Knuth's
  subtractive generator, as .NET Framework had it (modern .NET keeps that
  algorithm whenever a seed is given). Next() is the raw 31-bit sample;
  Next(n) and Next(a, b) scale sample / (2^31 - 1); NextDouble() is that
  fraction.
- Seeds are made from up to five numbers (Utility.CreateRandomSeed): each is
  taken modulo 2^31 - 1, keeping its sign, and cut to a 32-bit int; the five
  ints are hashed with 32-bit xxHash (seed 0) over their little-endian bytes.
  Saves that use "legacy random" add them up instead.
- The day's shop random: (days played, game id / 2) (CreateDaySaveRandom).
- SYNCED_RANDOM <interval> <key> <chance>: seeded from (hash of the key's
  UTF-8 text, the game id, days played for 'day' — or the hash of
  season + year / "year" + year).
"""

from __future__ import annotations

import math
import struct

MBIG = 2**31 - 1
_MSEED = 161803398


def _i32(x: int) -> int:
    return (x + 2**31) % 2**32 - 2**31


class NetRandom:
    """System.Random(seed)."""

    def __init__(self, seed: int):
        s = MBIG if seed == -(2**31) else abs(seed)
        a = [0] * 56
        mj = _MSEED - s
        a[55] = mj
        mk, ii = 1, 0
        for _ in range(1, 55):
            ii = (ii + 21) % 55
            a[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += MBIG
            mj = a[ii]
        for _ in range(4):
            for i in range(1, 56):
                n = i + 30
                if n >= 55:
                    n -= 55
                a[i] = _i32(a[i] - a[1 + n])
                if a[i] < 0:
                    a[i] += MBIG
        self._a, self._i, self._p = a, 0, 21
        self.draws = 0

    def _sample(self) -> int:
        i = self._i + 1 if self._i < 55 else 1
        p = self._p + 1 if self._p < 55 else 1
        r = self._a[i] - self._a[p]
        if r == MBIG:
            r -= 1
        if r < 0:
            r += MBIG
        self._a[i] = r
        self._i, self._p = i, p
        self.draws += 1
        return r

    def next(self, lo: int | None = None, hi: int | None = None) -> int:
        """Next() / Next(max) / Next(min, max) — max exclusive."""
        if lo is None:
            return self._sample()
        if hi is None:
            lo, hi = 0, lo
        return int(self._sample() * (1.0 / MBIG) * (hi - lo)) + lo

    def next_double(self) -> float:
        return self._sample() * (1.0 / MBIG)

    def choose(self, options):
        """RandomExtensions.ChooseFrom."""
        return options[self.next(len(options))] if options else None


_P1, _P2, _P3, _P4, _P5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393
_M32 = 0xFFFFFFFF


def _rotl(x: int, r: int) -> int:
    return ((x << r) | (x >> (32 - r))) & _M32


def xxhash32(data: bytes, seed: int = 0) -> int:
    """32-bit xxHash, as a signed int (BitConverter.ToInt32 of the digest)."""
    n, i = len(data), 0
    if n >= 16:
        v = [(seed + _P1 + _P2) & _M32, (seed + _P2) & _M32, seed & _M32, (seed - _P1) & _M32]
        while i + 16 <= n:
            for k in range(4):
                (w,) = struct.unpack_from("<I", data, i)
                i += 4
                v[k] = (_rotl((v[k] + w * _P2) & _M32, 13) * _P1) & _M32
        h = (_rotl(v[0], 1) + _rotl(v[1], 7) + _rotl(v[2], 12) + _rotl(v[3], 18)) & _M32
    else:
        h = (seed + _P5) & _M32
    h = (h + n) & _M32
    while i + 4 <= n:
        (w,) = struct.unpack_from("<I", data, i)
        h = (_rotl((h + w * _P3) & _M32, 17) * _P4) & _M32
        i += 4
    while i < n:
        h = (_rotl((h + data[i] * _P5) & _M32, 11) * _P1) & _M32
        i += 1
    h ^= h >> 15
    h = (h * _P2) & _M32
    h ^= h >> 13
    h = (h * _P3) & _M32
    h ^= h >> 16
    return _i32(h)


def hash_text(text: str) -> int:
    return xxhash32(text.encode("utf-8"))


def random_seed(*values: float, legacy: bool = False) -> int:
    """Utility.CreateRandomSeed for up to five values."""
    vals = [math.fmod(v, MBIG) for v in (*values, 0, 0, 0, 0, 0)[:5]]
    if legacy:
        return int(math.fmod(sum(vals), MBIG))
    return xxhash32(struct.pack("<5i", *(_i32(int(v)) for v in vals)))


def day_save_random(days_played: int, game_id: int, *, legacy: bool = False) -> NetRandom:
    return NetRandom(random_seed(days_played, game_id // 2, legacy=legacy))


def synced_random(interval: str, key: str, *, game_id: int, days_played: int, season: str, year: int,
                  legacy: bool = False) -> NetRandom | None:
    """Utility.TryCreateIntervalRandom; None for 'tick' (not knowable ahead) or an unknown interval."""
    interval = interval.lower()
    if interval == "day":
        c = days_played
    elif interval == "season":
        c = hash_text(f"{season}{year}")
    elif interval == "year":
        c = hash_text(f"year{year}")
    else:
        return None
    return NetRandom(random_seed(hash_text(key) if key else 0, game_id, c, legacy=legacy))
