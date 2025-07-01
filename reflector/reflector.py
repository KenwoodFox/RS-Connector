import asyncio
import websockets
import json
from PIL import Image, ImageDraw, ImageFont
import os

# Config
RS_CONNECTOR_WS = os.environ.get("RS_CONNECTOR_WS", "ws://172.17.0.3:8765")
OUTPUT_IMAGE = os.environ.get("REFLECTOR_IMAGE", "reflector_output.jpg")
FONT_PATH = os.environ.get(
    "REFLECTOR_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)
IMG_SIZE = (640, 480)
BG_COLOR = (30, 30, 30)
TEXT_COLOR = (255, 255, 255)

last_button = "None"


def update_image(text):
    img = Image.new("RGB", IMG_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 48)
    except Exception:
        font = ImageFont.load_default()
    w, h = draw.textsize(text, font=font)
    draw.text(
        ((IMG_SIZE[0] - w) // 2, (IMG_SIZE[1] - h) // 2),
        text,
        fill=TEXT_COLOR,
        font=font,
    )
    img.save(OUTPUT_IMAGE)
    print(f"Updated image with: {text}")


async def listen_buttons():
    global last_button
    async with websockets.connect(RS_CONNECTOR_WS) as ws:
        print(f"Connected to {RS_CONNECTOR_WS}")
        async for message in ws:
            try:
                data = json.loads(message)
                if "user" in data and "command" in data:
                    last_button = f"{data['user']}: {data['command']} ({data.get('key_position','')})"
                    update_image(last_button)
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(listen_buttons())
