"""Small ISO9660 reader/editor for this project's MODE1/2352 GD-ROM track.

Writes regenerate Mode 1 EDC and both ECC parities. Allocation only uses sectors
unreferenced by the ISO directory tree and outside the first 64 system sectors.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import struct

SECTOR = 2352
USER = 2048
BASE_LBA = 45000

EDC_TABLE = []
ECC_FORWARD = []
ECC_BACKWARD = [0] * 256
for value in range(256):
    crc = value
    for _ in range(8):
        crc = (crc >> 1) ^ (0xD8018001 if crc & 1 else 0)
    EDC_TABLE.append(crc)
    doubled = (value << 1) ^ (0x11D if value & 0x80 else 0)
    ECC_FORWARD.append(doubled)
    ECC_BACKWARD[value ^ doubled] = value


def parity(source, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    result = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            temp = source[index]
            index = (index + minor_inc) % size
            a ^= temp
            b ^= temp
            a = ECC_FORWARD[a]
        a = ECC_BACKWARD[ECC_FORWARD[a] ^ b]
        result[major] = a
        result[major + major_count] = a ^ b
    return result


def checksums(raw):
    result = bytearray(raw)
    if len(result) != SECTOR or result[15] != 1:
        raise ValueError("Expected a complete Mode 1 sector")
    crc = 0
    for value in result[:2064]:
        crc = (crc >> 8) ^ EDC_TABLE[(crc ^ value) & 255]
    struct.pack_into("<I", result, 2064, crc)
    result[2068:2076] = bytes(8)
    result[2076:2248] = parity(result[12:2076], 86, 24, 2, 86)
    result[2248:2352] = parity(result[12:2248], 52, 43, 86, 88)
    return result


@dataclass
class Entry:
    path: str
    lba: int
    size: int
    directory: bool
    record_lba: int
    record_offset: int


class Disc:
    def __init__(self, path, writable=False):
        self.path = Path(path)
        self.handle = self.path.open("r+b" if writable else "rb")
        length = self.path.stat().st_size
        if length % SECTOR:
            raise ValueError("Track length is not a multiple of 2352")
        self.limit = BASE_LBA + length // SECTOR
        self.entries = {}
        pvd = self.read(BASE_LBA + 16, USER)
        if pvd[:7] != b"\x01CD001\x01":
            raise ValueError("Missing ISO9660 primary volume descriptor")
        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]
        self.root = Entry("", root_lba, root_size, True, 0, 0)
        self._directory(self.root)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.handle.close()

    def raw_sector(self, lba):
        if not BASE_LBA <= lba < self.limit:
            raise ValueError(f"LBA outside track: {lba}")
        self.handle.seek((lba - BASE_LBA) * SECTOR)
        raw = self.handle.read(SECTOR)
        if len(raw) != SECTOR:
            raise ValueError("Short sector")
        return raw

    def read(self, lba, size):
        result = bytearray()
        while size:
            raw = self.raw_sector(lba)
            take = min(size, USER)
            result += raw[16:16 + take]
            size -= take
            lba += 1
        return bytes(result)

    def read_file(self, path):
        entry = self.entries[path]
        return self.read(entry.lba, entry.size)

    def _directory(self, entry):
        data = self.read(entry.lba, entry.size)
        position = 0
        while position < len(data):
            count = data[position]
            if not count:
                position = (position // USER + 1) * USER
                continue
            record = data[position:position + count]
            if len(record) != count or count < 34:
                raise ValueError("Invalid directory record")
            name = record[33:33 + record[32]]
            record_lba, record_offset = entry.lba + position // USER, position % USER
            position += count
            if name in (b"\x00", b"\x01"):
                continue
            name = name.decode("ascii").split(";")[0]
            path = f"{entry.path}/{name}".lstrip("/")
            lba = struct.unpack_from("<I", record, 2)[0]
            size = struct.unpack_from("<I", record, 10)[0]
            child = Entry(path, lba, size, bool(record[25] & 2), record_lba, record_offset)
            self.entries[path] = child
            if child.directory:
                self._directory(child)

    def write_sector(self, lba, user_data):
        if len(user_data) != USER:
            raise ValueError("Expected 2048 user bytes")
        raw = bytearray(self.raw_sector(lba))
        raw[16:2064] = user_data
        raw = checksums(raw)
        self.handle.seek((lba - BASE_LBA) * SECTOR)
        self.handle.write(raw)

    def free_intervals(self):
        occupied = [(BASE_LBA, BASE_LBA + 64)]
        for entry in [self.root, *self.entries.values()]:
            occupied.append((entry.lba, entry.lba + math.ceil(entry.size / USER)))
        cursor = BASE_LBA
        result = []
        for start, end in sorted(occupied):
            if start > cursor:
                result.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < self.limit:
            result.append((cursor, self.limit))
        return result

    def replace(self, path, payload):
        entry = self.entries[path]
        if entry.directory:
            raise ValueError("Cannot replace a directory with data")
        required = math.ceil(len(payload) / USER)
        available = math.ceil(entry.size / USER)
        target = entry.lba
        if required > available:
            intervals = [(a, b) for a, b in self.free_intervals() if b - a >= required]
            if not intervals:
                raise ValueError(f"No unallocated extent for {path}: {len(payload)} bytes")
            # Prefer the tightest gap; never overwrite an existing file's extent.
            target = min(intervals, key=lambda pair: pair[1] - pair[0])[0]
        padded = payload + bytes(required * USER - len(payload))
        for number in range(required):
            self.write_sector(target + number, padded[number * USER:(number + 1) * USER])
        directory_sector = bytearray(self.read(entry.record_lba, USER))
        position = entry.record_offset
        struct.pack_into("<I", directory_sector, position + 2, target)
        struct.pack_into(">I", directory_sector, position + 6, target)
        struct.pack_into("<I", directory_sector, position + 10, len(payload))
        struct.pack_into(">I", directory_sector, position + 14, len(payload))
        self.write_sector(entry.record_lba, directory_sector)
        entry.lba, entry.size = target, len(payload)
        return target
