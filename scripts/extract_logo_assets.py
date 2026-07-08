"""One-shot: crop the brand lockup / mark / app icon out of the master logo
image and save transparent PNGs into landing/assets and frontend/public."""
from pathlib import Path

from PIL import Image

SRC = Path(
    r"C:\Users\Hasan\.cursor\projects\c-Users-Hasan-Desktop-AI-Rep-main\assets"
    r"\c__Users_Hasan_AppData_Roaming_Cursor_User_workspaceStorage_dd4f5c4f91a06a6c6ec39cc3229a3621_images_3dfd5d43-5472-4bf6-b444-2c2bf1cec564-c0a41dcf-bc44-4e2d-9461-da02b108f777.png"
)
ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "landing" / "assets"
PUBLIC = ROOT / "frontend" / "public"
LANDING.mkdir(parents=True, exist_ok=True)
PUBLIC.mkdir(parents=True, exist_ok=True)

WHITE_CUTOFF = 242


def make_transparent(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= WHITE_CUTOFF and g >= WHITE_CUTOFF and b >= WHITE_CUTOFF:
                px[x, y] = (r, g, b, 0)
    return im


def bbox_of_content(im: Image.Image) -> tuple:
    """Bounding box of non-near-white pixels."""
    gray = im.convert("L").point(lambda v: 0 if v >= WHITE_CUTOFF else 255)
    return gray.getbbox()


def crop_region(im: Image.Image, box: tuple, pad: int = 8) -> Image.Image:
    region = im.crop(box)
    bb = bbox_of_content(region)
    if not bb:
        raise SystemExit(f"No content found in region {box}")
    l, t, r, b = bb
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(region.width, r + pad)
    b = min(region.height, b + pad)
    return region.crop((l, t, r, b))


im = Image.open(SRC)
W, H = im.size

# Top ~60% holds the horizontal lockup (mark + wordmark)
lockup = crop_region(im, (0, 0, W, int(H * 0.62)))
# Within the lockup, the mark is the left chunk (before the wordmark starts)
mark = crop_region(im, (0, 0, int(W * 0.32), int(H * 0.62)))
# Bottom ~38% holds the rounded app icon
icon = crop_region(im, (0, int(H * 0.58), W, H))

lockup_t = make_transparent(lockup)
mark_t = make_transparent(mark)
icon_t = make_transparent(icon)

lockup_t.save(LANDING / "logo-lockup.png")
mark_t.save(LANDING / "logo-mark.png")
icon_t.save(LANDING / "logo-icon.png")

mark_t.save(PUBLIC / "logo-mark.png")
icon_t.save(PUBLIC / "logo-icon.png")

# Favicon-sized copies
icon_t.resize((64, 64), Image.LANCZOS).save(PUBLIC / "favicon.png")
icon_t.resize((64, 64), Image.LANCZOS).save(LANDING / "favicon.png")

print("lockup:", lockup_t.size)
print("mark:", mark_t.size)
print("icon:", icon_t.size)
print("saved to", LANDING, "and", PUBLIC)
