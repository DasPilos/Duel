from pathlib import Path

from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "fighters" / "equipment" / "placeholders"
SIZE = 1024


def layer():
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))


def save(image, name):
    image.save(OUTPUT_DIR / f"{name}.png", "PNG", optimize=True)


def helmet():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.ellipse((438, 90, 586, 238), fill=(82, 94, 112, 255), outline=(225, 190, 92, 255), width=7)
    draw.polygon([(430, 170), (594, 170), (580, 220), (444, 220)], fill=(55, 65, 82, 255), outline=(225, 190, 92, 255))
    draw.line((512, 100, 512, 214), fill=(225, 190, 92, 255), width=6)
    save(image, "head_iron_helmet")


def cloak():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.polygon([(390, 235), (634, 235), (710, 760), (314, 760)], fill=(54, 61, 88, 220), outline=(190, 155, 75, 255))
    draw.line((390, 260, 335, 735), fill=(110, 120, 155, 220), width=8)
    draw.line((634, 260, 689, 735), fill=(110, 120, 155, 220), width=8)
    save(image, "back_blue_cloak")


def body_armor():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.polygon([(421, 252), (603, 252), (634, 455), (390, 455)], fill=(103, 112, 128, 235), outline=(225, 190, 92, 255))
    draw.line((512, 270, 512, 440), fill=(225, 190, 92, 255), width=6)
    draw.line((430, 315, 594, 315), fill=(168, 176, 190, 220), width=5)
    save(image, "body_steel_breastplate")


def belt():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((390, 440, 634, 490), radius=12, fill=(96, 54, 34, 255), outline=(225, 190, 92, 255), width=6)
    draw.rectangle((493, 438, 531, 492), fill=(225, 190, 92, 255), outline=(80, 55, 32, 255), width=4)
    save(image, "belt_bronze_belt")


def gauntlets():
    image = layer()
    draw = ImageDraw.Draw(image)
    for box in ((352, 340, 414, 515), (610, 340, 672, 515)):
        draw.rounded_rectangle(box, radius=18, fill=(75, 87, 105, 245), outline=(225, 190, 92, 255), width=6)
    save(image, "hands_steel_gauntlets")


def legs():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.polygon([(426, 476), (495, 476), (480, 720), (408, 720)], fill=(71, 82, 103, 240), outline=(225, 190, 92, 255))
    draw.polygon([(529, 476), (598, 476), (616, 720), (544, 720)], fill=(71, 82, 103, 240), outline=(225, 190, 92, 255))
    save(image, "legs_steel_greaves")


def boots():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((393, 690, 489, 842), radius=24, fill=(65, 48, 42, 255), outline=(225, 190, 92, 255), width=7)
    draw.rounded_rectangle((535, 690, 631, 842), radius=24, fill=(65, 48, 42, 255), outline=(225, 190, 92, 255), width=7)
    save(image, "feet_iron_boots")


def sword():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.polygon([(680, 360), (708, 370), (812, 610), (778, 624)], fill=(186, 201, 220, 255), outline=(225, 190, 92, 255))
    draw.line((690, 365, 795, 615), fill=(255, 255, 255, 210), width=7)
    draw.line((745, 560, 812, 590), fill=(225, 190, 92, 255), width=12)
    draw.rounded_rectangle((775, 590, 815, 690), radius=10, fill=(75, 45, 30, 255), outline=(225, 190, 92, 255), width=5)
    save(image, "right_hand_steel_sword")


def shield():
    image = layer()
    draw = ImageDraw.Draw(image)
    draw.ellipse((220, 380, 390, 590), fill=(58, 76, 104, 245), outline=(225, 190, 92, 255), width=9)
    draw.polygon([(305, 410), (350, 480), (305, 550), (260, 480)], fill=(225, 190, 92, 220))
    save(image, "left_hand_round_shield")


def jewelry():
    necklace = layer()
    draw = ImageDraw.Draw(necklace)
    draw.arc((425, 205, 599, 330), 15, 165, fill=(225, 190, 92, 255), width=7)
    draw.ellipse((495, 300, 529, 350), fill=(76, 139, 176, 255), outline=(225, 190, 92, 255), width=5)
    save(necklace, "neck_sapphire_pendant")

    earrings = layer()
    draw = ImageDraw.Draw(earrings)
    draw.ellipse((440, 190, 456, 220), fill=(225, 190, 92, 255))
    draw.ellipse((568, 190, 584, 220), fill=(225, 190, 92, 255))
    save(earrings, "ears_gold_earrings")

    rings = layer()
    draw = ImageDraw.Draw(rings)
    draw.ellipse((388, 520, 413, 545), outline=(225, 190, 92, 255), width=7)
    draw.ellipse((610, 520, 635, 545), outline=(225, 190, 92, 255), width=7)
    save(rings, "rings_gold_rings")


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
helmet()
cloak()
body_armor()
belt()
gauntlets()
legs()
boots()
sword()
shield()
jewelry()
print(f"created {len(list(OUTPUT_DIR.glob('*.png')))} placeholder layers in {OUTPUT_DIR}")