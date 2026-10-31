"""Generate source-controlled deterministic app icon from vector-like Pillow drawing."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
folder = root / 'src/airear/assets'
folder.mkdir(parents=True, exist_ok=True)
im = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(im)
draw.rounded_rectangle((8, 8, 248, 248), radius=56, fill='#2563eb')
for x, h in [(63, 48), (95, 104), (127, 160), (159, 104), (191, 48)]:
    draw.rounded_rectangle((x - 9, 128 - h // 2, x + 9, 128 + h // 2), radius=9, fill='white')
im.save(folder / 'airear.ico', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
im.save(folder / 'airear.png')
