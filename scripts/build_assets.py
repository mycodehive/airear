"""Convert the supplied AirEar artwork into Windows multi-resolution icons."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
folder = root / 'src/airear/assets'
with Image.open(folder / 'icon-source.png') as source:
    image = source.convert('RGBA')
    image.save(folder / 'airear.ico', sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])
    image.resize((256, 256), Image.Resampling.LANCZOS).save(folder / 'airear.png')
