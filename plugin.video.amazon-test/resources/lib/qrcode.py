#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Minimal pure-Python ISO/IEC 18004 QR Code (EC Level M, Versions 1-10) PNG generator."""

import struct
import zlib

# (total_codewords, ec_per_block, g1_blocks, g1_data, g2_blocks, g2_data, align_coords)
_VERSIONS_M = {
    1:  (26,  10, 1, 16, 0,  0, ()),
    2:  (44,  16, 1, 28, 0,  0, (6, 18)),
    3:  (70,  26, 1, 44, 0,  0, (6, 22)),
    4:  (100, 18, 2, 32, 0,  0, (6, 26)),
    5:  (134, 24, 2, 43, 0,  0, (6, 30)),
    6:  (172, 16, 4, 27, 0,  0, (6, 34)),
    7:  (196, 18, 4, 31, 0,  0, (6, 22, 38)),
    8:  (242, 22, 2, 38, 2, 39, (6, 24, 42)),
    9:  (292, 22, 3, 36, 2, 37, (6, 26, 46)),
    10: (346, 26, 4, 43, 1, 44, (6, 28, 50)),
}

_MASKS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: ((r // 2) + (c // 3)) % 2 == 0,
    lambda r, c: ((r * c) % 2) + ((r * c) % 3) == 0,
    lambda r, c: (((r * c) % 2) + ((r * c) % 3)) % 2 == 0,
    lambda r, c: (((r + c) % 2) + ((r * c) % 3)) % 2 == 0,
)


def _gf_mul(x, y):
    r = 0
    while y:
        if y & 1:
            r ^= x
        x <<= 1
        if x & 0x100:
            x ^= 0x11d
        y >>= 1
    return r


def _rs_generator(degree):
    poly = [1]
    root = 1
    for _ in range(degree):
        nxt = [0] * (len(poly) + 1)
        for i, coef in enumerate(poly):
            nxt[i] ^= coef
            nxt[i + 1] ^= _gf_mul(coef, root)
        poly = nxt
        root = _gf_mul(root, 2)
    return poly


def _rs_encode(data, ec_count):
    gen = _rs_generator(ec_count)
    rem = [0] * ec_count
    for b in data:
        factor = b ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i in range(ec_count):
                rem[i] ^= _gf_mul(gen[i + 1], factor)
    return rem


def _format_bits(mask_id):
    # EC level M -> 0b00
    data = mask_id & 0x7
    rem = data << 10
    for i in range(4, -1, -1):
        if rem & (1 << (i + 10)):
            rem ^= 0x537 << i
    return ((data << 10) | rem) ^ 0x5412


def _version_bits(version):
    rem = version << 12
    for i in range(5, -1, -1):
        if rem & (1 << (i + 12)):
            rem ^= 0x1f25 << i
    return (version << 12) | rem


def _select_version(byte_len):
    for ver, (_, _, g1b, g1d, g2b, g2d, _) in _VERSIONS_M.items():
        data_cw = g1b * g1d + g2b * g2d
        count_bits = 8 if ver < 10 else 16
        cap_bytes = (data_cw * 8 - 4 - count_bits) // 8
        if byte_len <= cap_bytes:
            return ver
    raise ValueError(f'Payload too long for QR versions 1-10 ({byte_len} bytes)')


def _encode_codewords(payload_bytes, version):
    _, ec_len, g1b, g1d, g2b, g2d, _ = _VERSIONS_M[version]
    data_cw = g1b * g1d + g2b * g2d
    count_bits = 8 if version < 10 else 16

    bits = []
    # Mode indicator: Byte mode (0100)
    bits.extend((0, 1, 0, 0))
    n = len(payload_bytes)
    for i in range(count_bits - 1, -1, -1):
        bits.append((n >> i) & 1)
    for b in payload_bytes:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)

    max_bits = data_cw * 8
    term = min(4, max_bits - len(bits))
    bits.extend([0] * term)
    while len(bits) % 8:
        bits.append(0)

    cw = []
    for i in range(0, len(bits), 8):
        val = 0
        for j in range(8):
            val = (val << 1) | bits[i + j]
        cw.append(val)

    pad = (0xEC, 0x11)
    pidx = 0
    while len(cw) < data_cw:
        cw.append(pad[pidx])
        pidx ^= 1

    # Split into blocks and compute Reed-Solomon EC codewords
    data_blocks = []
    ec_blocks = []
    pos = 0
    for count, size in ((g1b, g1d), (g2b, g2d)):
        for _ in range(count):
            blk = cw[pos:pos + size]
            pos += size
            data_blocks.append(blk)
            ec_blocks.append(_rs_encode(blk, ec_len))

    # Interleave data codewords, then EC codewords
    out = []
    max_data = max(len(b) for b in data_blocks)
    for i in range(max_data):
        for blk in data_blocks:
            if i < len(blk):
                out.append(blk[i])
    for i in range(ec_len):
        for blk in ec_blocks:
            out.append(blk[i])
    return out


def _build_base_matrix(version):
    size = 17 + 4 * version
    mat = [[0] * size for _ in range(size)]
    func = [[False] * size for _ in range(size)]

    def set_fn(r, c, val):
        if 0 <= r < size and 0 <= c < size:
            mat[r][c] = val
            func[r][c] = True

    # Finder patterns + 1-module white separators
    for fr, fc in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = fr + dr, fc + dc
                if 0 <= r < size and 0 <= c < size:
                    in_outer = 0 <= dr <= 6 and 0 <= dc <= 6
                    on_border = dr in (0, 6) or dc in (0, 6)
                    in_core = 2 <= dr <= 4 and 2 <= dc <= 4
                    set_fn(r, c, 1 if (in_outer and (on_border or in_core)) else 0)

    # Timing patterns
    for i in range(8, size - 8):
        bit = 1 if i % 2 == 0 else 0
        set_fn(6, i, bit)
        set_fn(i, 6, bit)

    # Alignment patterns
    coords = _VERSIONS_M[version][6]
    for ar in coords:
        for ac in coords:
            if (ar == 6 and ac == 6) or (ar == 6 and ac == size - 7) or (ar == size - 7 and ac == 6):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    val = 1 if max(abs(dr), abs(dc)) != 1 else 0
                    set_fn(ar + dr, ac + dc, val)

    # Reserve format info areas and set dark module
    for i in range(9):
        if i != 6:
            set_fn(8, i, 0)
            set_fn(i, 8, 0)
    for i in range(8):
        set_fn(8, size - 1 - i, 0)
    for i in range(7):
        set_fn(size - 1 - i, 8, 0)
    set_fn(size - 8, 8, 1)

    # Version info for versions >= 7
    if version >= 7:
        vbits = _version_bits(version)
        for i in range(18):
            bit = (vbits >> i) & 1
            a = i // 3
            b = size - 11 + (i % 3)
            set_fn(b, a, bit)
            set_fn(a, b, bit)

    return mat, func


def _place_format(mat, mask_id):
    size = len(mat)
    fb = _format_bits(mask_id)
    # Copy 1 around top-left finder
    c1_coords = (
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    )
    for idx, (r, c) in enumerate(c1_coords):
        mat[r][c] = (fb >> (14 - idx)) & 1
    # Copy 2 bottom-left + top-right
    for i in range(7):
        mat[size - 1 - i][8] = (fb >> (14 - i)) & 1
    for i in range(8):
        mat[8][size - 8 + i] = (fb >> (7 - i)) & 1


def _place_data(mat, func, codewords):
    size = len(mat)
    bits = []
    for b in codewords:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    bidx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not func[r][c]:
                    mat[r][c] = bits[bidx] if bidx < len(bits) else 0
                    bidx += 1
        upward = not upward
        col -= 2


def _penalty(mat):
    size = len(mat)
    score = 0
    # Rule 1: runs of 5+ same color in rows and columns
    for r in range(size):
        run = 1
        for c in range(1, size):
            if mat[r][c] == mat[r][c - 1]:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run = 1
        if run >= 5:
            score += run - 2
    for c in range(size):
        run = 1
        for r in range(1, size):
            if mat[r][c] == mat[r - 1][c]:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run = 1
        if run >= 5:
            score += run - 2
    # Rule 2: 2x2 blocks of same color
    for r in range(size - 1):
        for c in range(size - 1):
            v = mat[r][c]
            if v == mat[r][c + 1] == mat[r + 1][c] == mat[r + 1][c + 1]:
                score += 3
    # Rule 3: finder-like 1:1:3:1:1 patterns
    p1 = (1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0)
    p2 = (0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1)
    for r in range(size):
        row = tuple(mat[r])
        for c in range(size - 10):
            seg = row[c:c + 11]
            if seg == p1 or seg == p2:
                score += 40
    for c in range(size):
        col = tuple(mat[r][c] for r in range(size))
        for r in range(size - 10):
            seg = col[r:r + 11]
            if seg == p1 or seg == p2:
                score += 40
    # Rule 4: dark module balance
    dark = sum(sum(row) for row in mat)
    pct = (dark * 100) // (size * size)
    score += min(abs(pct - 50) // 5, abs(pct + 1 - 50) // 5) * 10
    return score


def make_qr_matrix(text):
    payload = text.encode('utf-8') if isinstance(text, str) else bytes(text)
    version = _select_version(len(payload))
    codewords = _encode_codewords(payload, version)
    base, func = _build_base_matrix(version)
    _place_data(base, func, codewords)
    size = len(base)

    best_mat = None
    best_score = None
    for mask_id, mask_fn in enumerate(_MASKS):
        cand = [
            [
                base[r][c] ^ (1 if (not func[r][c] and mask_fn(r, c)) else 0)
                for c in range(size)
            ]
            for r in range(size)
        ]
        _place_format(cand, mask_id)
        sc = _penalty(cand)
        if best_score is None or sc < best_score:
            best_score = sc
            best_mat = cand
    return best_mat


def _png_chunk(ctype, data):
    return struct.pack('>I', len(data)) + ctype + data + struct.pack('>I', zlib.crc32(ctype + data) & 0xFFFFFFFF)


def make_qr_png(text, scale=10, border=4):
    """Render `text` as a crisp grayscale PNG byte string."""
    mat = make_qr_matrix(text)
    size = len(mat)
    img_size = (size + 2 * border) * scale
    white_row = b'\x00' + (b'\xff' * img_size)
    raw_rows = [white_row] * (border * scale)
    border_px = b'\xff' * (border * scale)
    for row in mat:
        line = bytearray(b'\x00')
        line.extend(border_px)
        for bit in row:
            line.extend((b'\x00' if bit else b'\xff') * scale)
        line.extend(border_px)
        row_bytes = bytes(line)
        for _ in range(scale):
            raw_rows.append(row_bytes)
    raw_rows.extend([white_row] * (border * scale))

    ihdr = struct.pack('>IIBBBBB', img_size, img_size, 8, 0, 0, 0, 0)
    idat = zlib.compress(b''.join(raw_rows), level=9)
    return (
        b'\x89PNG\r\n\x1a\n'
        + _png_chunk(b'IHDR', ihdr)
        + _png_chunk(b'IDAT', idat)
        + _png_chunk(b'IEND', b'')
    )
