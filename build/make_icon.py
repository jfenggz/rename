"""由 build/logo.svg 生成多尺寸 app.ico。

做法：用 Edge 无头模式渲染一张大图，自动裁掉透明边，再用
纯 Python（zlib + 面积平均）缩放到各尺寸，最后按 ICO 规范打包。
不依赖 Pillow，也不受系统 DPI 缩放影响。
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGO = HERE / "logo.svg"
OUT = HERE / "app.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

CANVAS = 768          # 渲染窗口边长（远大于绘制尺寸，防止被 DPI 缩放裁切）
DRAW = 320            # SVG 绘制边长

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def find_browser() -> str:
    for path in EDGE_CANDIDATES:
        if os.path.exists(path):
            return path
    found = shutil.which("msedge") or shutil.which("chrome")
    if not found:
        raise SystemExit("未找到 Edge / Chrome，无法渲染图标")
    return found


# ----------------------------------------------------------------- PNG 读写
def decode_png(data: bytes) -> tuple[int, int, bytearray]:
    """只支持 8bit RGB/RGBA、非隔行的 PNG（浏览器截图即为此格式）。"""
    pos, width, height, idat, color = 8, 0, 0, bytearray(), 6
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            if depth != 8 or color not in (2, 6):
                raise SystemExit(f"不支持的 PNG 格式 depth={depth} color={color}")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length

    bpp = 4 if color == 6 else 3
    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        filt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if filt == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        base = y * width * 4
        if bpp == 4:
            out[base:base + width * 4] = line
        else:
            for x in range(width):
                out[base + x * 4:base + x * 4 + 3] = line[x * 3:x * 3 + 3]
                out[base + x * 4 + 3] = 255
        prev = line
    return width, height, out


def encode_png(width: int, height: int, pixels: bytearray) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * width * 4:(y + 1) * width * 4]

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


# ----------------------------------------------------------------- 图像处理
def alpha_bbox(width: int, height: int, pixels: bytearray) -> tuple[int, int, int, int]:
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            if pixels[row + x * 4 + 3] > 8:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right < 0:
        raise SystemExit("渲染结果是空白图")
    return left, top, right + 1, bottom + 1


def crop(width: int, pixels: bytearray, box: tuple[int, int, int, int]) -> tuple[int, int, bytearray]:
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    out = bytearray(w * h * 4)
    for y in range(h):
        src = (top + y) * width * 4 + left * 4
        out[y * w * 4:(y + 1) * w * 4] = pixels[src:src + w * 4]
    return w, h, out


def resize(width: int, height: int, pixels: bytearray, dw: int, dh: int) -> bytearray:
    """面积平均缩放（预乘 alpha，避免边缘发黑）。"""
    pre = bytearray(len(pixels))
    for i in range(0, len(pixels), 4):
        a = pixels[i + 3]
        pre[i] = pixels[i] * a // 255
        pre[i + 1] = pixels[i + 1] * a // 255
        pre[i + 2] = pixels[i + 2] * a // 255
        pre[i + 3] = a

    out = bytearray(dw * dh * 4)
    sx, sy = width / dw, height / dh
    for dy in range(dh):
        y0, y1 = dy * sy, (dy + 1) * sy
        for dx in range(dw):
            x0, x1 = dx * sx, (dx + 1) * sx
            r = g = b = a = area = 0.0
            iy = int(y0)
            while iy < min(int(y1) + 1, height):
                oy = min(y1, iy + 1) - max(y0, iy)
                if oy <= 0:
                    iy += 1
                    continue
                ix = int(x0)
                while ix < min(int(x1) + 1, width):
                    ox = min(x1, ix + 1) - max(x0, ix)
                    if ox > 0:
                        wgt = ox * oy
                        base = (iy * width + ix) * 4
                        r += pre[base] * wgt
                        g += pre[base + 1] * wgt
                        b += pre[base + 2] * wgt
                        a += pre[base + 3] * wgt
                        area += wgt
                    ix += 1
                iy += 1
            if area <= 0:
                continue
            pa = a / area
            o = (dy * dw + dx) * 4
            if pa > 0:
                scale = 255.0 / pa
                out[o] = min(255, int(r / area * scale + 0.5))
                out[o + 1] = min(255, int(g / area * scale + 0.5))
                out[o + 2] = min(255, int(b / area * scale + 0.5))
            out[o + 3] = min(255, int(pa + 0.5))
    return out


# ----------------------------------------------------------------- 渲染
def render_source(browser: str, workdir: Path) -> tuple[int, int, bytearray]:
    svg = LOGO.read_text(encoding="utf-8")
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}'
        'svg{display:block;width:100%;height:100%}'
        f'.wrap{{width:{DRAW}px;height:{DRAW}px}}</style></head>'
        f'<body><div class="wrap">{svg}</div></body></html>'
    )
    page = workdir / "logo.html"
    page.write_text(html, encoding="utf-8")
    png = workdir / "logo.png"
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check",
        "--disable-sync", "--disable-extensions",
        "--default-background-color=00000000",
        f"--window-size={CANVAS},{CANVAS}",
        f"--screenshot={png}",
        f"--user-data-dir={workdir / 'profile'}",
        page.as_uri(),
    ]
    subprocess.run(cmd, check=True, timeout=60,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return decode_png(png.read_bytes())


def build_ico(frames: list[tuple[int, bytes]]) -> bytes:
    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)
    directory, blob = b"", b""
    offset = 6 + 16 * count
    for size, data in frames:
        dim = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blob += data
    return header + directory + blob


def main() -> None:
    browser = find_browser()
    workdir = Path(tempfile.mkdtemp(prefix="ico_"))
    try:
        w, h, px = render_source(browser, workdir)
        print(f"原始截图 {w}x{h}")
        w, h, px = crop(w, px, alpha_bbox(w, h, px))
        print(f"裁切后 {w}x{h}")

        frames = [(size, encode_png(size, size, resize(w, h, px, size, size)))
                  for size in SIZES]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    OUT.write_bytes(build_ico(frames))
    print(f"已生成 {OUT}（{'/'.join(map(str, SIZES))}，{OUT.stat().st_size / 1024:.1f} KB）")

    (HERE / "preview_256.png").write_bytes(frames[-1][1])
    (HERE / "preview_32.png").write_bytes(dict(frames)[32])


if __name__ == "__main__":
    main()
