"""Assemble the picture: everything in its plane, back to front."""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import engine
from engine import mix, tint, fbm, blur, blur3, norm01, smoothstep
import scene
import figures
from scene import studio, KEY_DIR, KEY_COL, grids, poly_mask
from sculpt import Form, shade


def shift_layer(rgb, mask, dx, dy):
    d = (dy * scene.S, dx * scene.S)
    r = np.dstack([ndimage.shift(rgb[..., i], d, order=1, mode='nearest') for i in range(3)])
    m = ndimage.shift(mask.astype(np.float32), d, order=1, mode='constant') > 0.5
    return r, m


def over(img, rgb, m, soft=0.9):
    a = blur(m.astype(np.float32), soft * scene.S)[..., None]
    return img * (1 - a) + np.clip(rgb, 0, 1) * a


# (scale, dx, dy, rotation, pivot)
XF_A = (1.34, -102, 0, 0, 1000, 1300)        # Andromeda: 57% of the canvas height
XF_P = (1.38, -360, 110, 0, 800, 1150)       # Perseus, swooping in from the left
XF_C = (1.25, -157, 178, -20, 900, 1700)     # Cetus, jaws swung up toward him


def P(x, y):
    return (x * scene.S, y * scene.S)


def PA(x, y):
    """a point in Andromeda's design frame, in canvas pixels"""
    sx, dx, dy, rot, px, py = XF_A
    u, v = x - px, y - py
    ca, sa = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    u, v = u * ca - v * sa, u * sa + v * ca
    return ((px + u * sx + dx) * scene.S, (py + v * sx + dy) * scene.S)


def scA(v):
    return v * XF_A[0] * scene.S


def sc(v):
    return v * scene.S


# --------------------------------------------------------------------------
def chains(W, H, rng):
    """iron links from her shackled wrists up to the rock"""
    f = Form(H, W)
    iron = np.asarray(figures.IRON, np.float32)
    b = 0.3 / (scene.S * XF_A[0])
    P, sc = PA, scA
    runs = [((1236, 772), (1356, 720), 7), ((1346, 798), (1430, 764), 7)]
    for (x0, y0), (x1, y1), r in runs:
        n = 9
        for i in range(n):
            t = i / (n - 1.0)
            x = x0 + (x1 - x0) * t + np.sin(t * 9) * 4
            y = y0 + (y1 - y0) * t
            f.ellipsoid(P(x, y), (sc(r * (1.0 if i % 2 else 0.5)),
                                  sc(r * (0.5 if i % 2 else 1.0)), sc(r * 0.6)),
                        iron, 'steel', zk=1.0, blendk=b)
    # shackles
    f.capsule(P(1226, 782), P(1248, 768), sc(11), sc(11), iron, 'steel', zk=0.45, blendk=b)
    f.capsule(P(1336, 808), P(1358, 794), sc(11), sc(11), iron, 'steel', zk=0.45, blendk=b)
    # a second chain falling slack from the rock past her hip
    pts = [(1452, 1032), (1480, 1150), (1472, 1286), (1438, 1402)]
    for i in range(14):
        t = i / 13.0
        j = min(2, int(t * 3))
        tt = t * 3 - j
        x = pts[j][0] + (pts[j + 1][0] - pts[j][0]) * tt
        y = pts[j][1] + (pts[j + 1][1] - pts[j][1]) * tt
        f.ellipsoid(P(x, y), (sc(8 if i % 2 else 4), sc(4 if i % 2 else 8), sc(4)),
                    iron, 'steel', zk=1.0, blendk=b)
    rgb, _ = shade(f, studio(key=1.1, fill=0.40, bounce=0.20),
                   ao_radius=6 * scene.S, normal_scale=1.0,
                   normal_smooth=1.0 * scene.S, sky_k=0.45,
                   rim=dict(d=KEY_DIR, c=tint(KEY_COL, 1.2), k=0.9, p=2.0))
    return rgb, f.mask


def foam(W, H, rng, where, v):
    """surf: a field of broken white, heavier where water meets stone"""
    X, Y, xx, yy = grids(W, H)
    n = fbm(H, W, 48 * scene.S, rng, 5)
    n2 = fbm(H, W, 15 * scene.S, rng, 4)
    f = smoothstep(0.46, 0.80, n * 0.65 + n2 * 0.35) * where
    col = np.asarray(mix('lead_white', 2.6, 'naples', 0.8, 'cerulean', 0.55), np.float32)
    shadow = np.asarray(mix('cerulean', 1.2, 'terre_verte', 0.8, 'lead_white', 0.9), np.float32)
    gy, gx = np.gradient(blur(f, 2.0 * scene.S))
    lit = np.clip(-(gx * KEY_DIR[0] + gy * KEY_DIR[1]) * 40, -1, 1)
    c = col[None, None, :] * (0.80 + 0.30 * np.clip(lit, 0, 1))[..., None] \
        + shadow[None, None, :] * (0.28 * np.clip(-lit, 0, 1))[..., None]
    return c, np.clip(f, 0, 1)


def build(W, H, rng, stage='all'):
    S = scene.S
    img = scene.paint_sky(W, H, rng)
    img, v = scene.paint_sea(img, W, H, rng)
    rm = scene.rock_masks(W, H, rng)
    img, _ = scene.paint_rock(img, W, H, rng, rm, parts=('crag',))

    X, Y, xx, yy = grids(W, H)
    parts = {}

    # ---- the monster, in the water ----
    figures.XF = XF_C
    cet = figures.cetus(W, H, rng)
    img = over(img, figures.shade_cetus(W, H, rng, cet), cet['mask'], 1.0)
    for frm, mk in (('teeth', 'teeth_mask'), ('eye', 'eye_mask')):
        rgb, _ = shade(cet[frm], studio(key=1.15, fill=0.42, bounce=0.2),
                       ao_radius=8 * S, normal_scale=1.0, normal_smooth=1.2 * S,
                       sky_k=0.45)
        img = over(img, rgb, cet[mk], 0.6)
    parts['cetus'] = cet['mask']

    # water line: the monster is cut off by the surface
    sea_line = 2330 - 150 * np.sin(X / 420.0)
    sunk = (Y > sea_line + (fbm(H, W, 70 * S, rng, 4) - 0.5) * 190)
    deep = np.asarray(mix('viridian', 1.0, 'burnt_umber', 1.6, 'ivory_black', 2.6), np.float32)
    a = (sunk & cet['mask']).astype(np.float32)
    a = blur(a, 10 * S)[..., None] * 0.86
    img = img * (1 - a) + deep[None, None, :] * a

    # ---- the ledge she stands on, and the foreground stone ----
    img, _ = scene.paint_rock(img, W, H, rng, rm, parts=('ledge',))

    # ---- surf ----
    rock_edge = blur((rm['ledge'] | rm['crag'] | rm['fore']).astype(np.float32), 9 * S)
    edge_band = np.clip(rock_edge * (1 - rock_edge) * 4.0, 0, 1)
    wake = blur((cet['mask'] & sunk).astype(np.float32), 16 * S)
    where = np.clip(edge_band * smoothstep(2060, 2380, Y) * 1.15
                    + wake * 1.4 * smoothstep(2120, 2360, Y)
                    + smoothstep(0.62, 0.97, fbm(H, W, 190 * S, rng, 4))
                    * smoothstep(2280, 2600, Y) * 0.45, 0, 1)
    where *= ~(rm['crag'] | rm['fore'])
    fc, fa = foam(W, H, rng, where, v)
    img = img * (1 - fa[..., None] * 0.92) + fc * fa[..., None] * 0.92

    img, _ = scene.paint_rock(img, W, H, rng, rm, parts=('fore',))

    # ---- Andromeda ----
    figures.XF = XF_A
    an = figures.andromeda(W, H, rng)
    # her shadow thrown back onto the rock
    shsil = blur(an['skin'].astype(np.float32), 3 * S)
    sh = ndimage.shift(shsil, (12 * S, 54 * S), order=1)
    sh = blur(sh, 14 * S) * (rm['crag'] | rm['ledge']) * 0.62
    img = img * (1 - sh[..., None] * 0.9) + img * np.array([0.42, 0.32, 0.34], np.float32)[None, None, :] * sh[..., None] * 0.9

    foot = np.zeros((H, W), np.float32)
    fi = Image.new('L', (W, H), 0)
    fd = ImageDraw.Draw(fi)
    for cx, cy, rx, ry in ((1226, 2086, 72, 20), (1432, 2090, 76, 20)):
        fd.ellipse([PA(cx - rx, cy - ry)[0], PA(cx - rx, cy - ry)[1],
                    PA(cx + rx, cy + ry)[0], PA(cx + rx, cy + ry)[1]], fill=255)
    foot = blur(np.asarray(fi, np.float32) / 255.0, 9 * S) * 0.75
    img = img * (1 - foot[..., None]) + img * np.array([0.30, 0.22, 0.24], np.float32)[None, None, :] * foot[..., None]

    ch_rgb, ch_mask = chains(W, H, rng)
    cloth_rgb = figures.drapery(W, H, rng, an['cloth'], figures.LINEN_W,
                                fold_dir=(0.40, 1.0), fold_scale=22, thick=22, key=0.84)
    an_rgb = figures.shade_andromeda(W, H, rng, an)[0]
    an_rgb = figures.model_andromeda(W, H).apply(an_rgb, an['skin'])
    img = over(img, an_rgb, an['skin'], 0.8)
    img = over(img, figures.shade_hair(W, H, rng, an), an['hair_mask'], 0.9)
    img = over(img, cloth_rgb, an['cloth'], 0.8)
    img = over(img, ch_rgb, ch_mask, 0.6)
    parts['andromeda'] = an['skin'] | an['hair_mask'] | an['cloth']
    parts['an'] = an

    # ---- Perseus ----
    figures.XF = XF_P
    pe = figures.perseus(W, H, rng)
    cloak_rgb = figures.drapery(W, H, rng, pe['cloak'], figures.CLOAK,
                                fold_dir=(1.0, 0.38), fold_scale=30, thick=30,
                                key=0.72, mat='wool')
    img = over(img, cloak_rgb, pe['cloak'], 0.9)
    pe_rgb = figures.shade_perseus(W, H, rng, pe)
    pe_rgb = figures.model_perseus(W, H).apply(pe_rgb, pe['skin'])
    img = over(img, pe_rgb, pe['skin'], 0.8)
    img = over(img, figures.shade_hair(W, H, rng, pe), pe['hair_mask'], 0.8)
    g_rgb, _ = shade(pe['gear'], studio(key=1.35, fill=0.45, bounce=0.2),
                     ao_radius=8 * S, normal_scale=1.0, normal_smooth=1.2 * S,
                     sky_k=0.55, rim=dict(d=KEY_DIR, c=(1.0, 0.95, 0.85), k=1.0, p=2.0))
    img = over(img, g_rgb, pe['gear_mask'], 0.6)
    parts['perseus'] = pe['skin'] | pe['hair_mask'] | pe['cloak'] | pe['gear_mask']
    parts['pe'] = pe
    parts['rocks'] = rm
    parts['foam'] = fa
    parts['v'] = v
    return np.clip(img, 0, 1), parts
