"""The picture itself: Perseus Delivering Andromeda.

Salon logic, stated once so every later decision can refer to it:

  * Portrait canvas, eye level just below Andromeda's breast, so she reads
    heroic and the sea sits low behind her.
  * One warm light, a break in the storm upper left.  It falls on Andromeda -
    she is the lightest, highest-chroma passage in the picture and everything
    else is keyed down to serve her.
  * The dark rock behind her is the foil; the monster is a dark mass in the
    lower left; Perseus comes down the diagonal between them.
  * Colour is a restricted palette: lead white, naples, ochre, the siennas,
    light red, madder, terre verte, viridian, ultramarine, the umbers, black.
"""
import numpy as np
from scipy import ndimage
from engine import (PIGMENTS, mix, tint, fbm, warp, blur, blur3, norm01,
                    smoothstep, _up)
import sculpt
from sculpt import Form, light, shade

S = 1.0            # render scale; all coordinates are given at S = 1 (2000 x 2600)
W0, H0 = 2000, 2600
HOR0 = 1452.0
SUN0 = (430.0, 268.0)


def sc(v):
    return v * S


def P(x, y):
    return (x * S, y * S)


# ---- the light, in image space (y down, z toward the viewer) --------------
KEY_DIR = (-0.52, -0.58, 0.63)
KEY_COL = mix('lead_white', 3.0, 'naples', 2.0, 'light_red', 0.42)
SKY_COL = mix('cerulean', 2.0, 'ultramarine', 1.0, 'lead_white', 1.4)
SEA_BOUNCE = mix('terre_verte', 2.0, 'ochre', 0.8, 'lead_white', 0.7)


def studio(key=1.22, fill=0.30, bounce=0.17):
    return [
        light(KEY_DIR, KEY_COL, key, 'key'),
        light((0.46, -0.80, 0.38), SKY_COL, fill, 'fill'),
        light((0.10, 0.86, 0.50), SEA_BOUNCE, bounce, 'bounce'),
    ]


# ==========================================================================
# coordinate helpers - geometry is always written in 2000x2600 units
# ==========================================================================
def grids(W, H):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return xx / S, yy / S, xx, yy


def lerp3(a, b, t):
    A = np.asarray(a, np.float32)[None, None, :]
    B = np.asarray(b, np.float32)[None, None, :]
    return A * (1 - t[..., None]) + B * t[..., None]


# ==========================================================================
# sky - a storm with one break in it, upper left
# ==========================================================================
def _cloud(W, H, rng, *, scale, octv, thresh, soft, squash, cover, sun,
           dark, lite, hot, tau_k=2.6, drift=0.0):
    """a cloud bank lit volumetrically: light is eaten as it travels through
    the mass toward the break, so the tops glow and the bellies go violet."""
    X, Y, xx, yy = grids(W, H)
    H2 = int(H * squash)
    n = _up(fbm(H2, W, scale * S, rng, octv, 0.53), W, H)
    if drift:
        wx = fbm(H, W, scale * 2.0 * S, rng, 3) - 0.5
        wy = fbm(H, W, scale * 2.0 * S, rng, 3) - 0.5
        n = warp(n, wx, wy, drift * S)
    d = smoothstep(thresh, thresh + soft, n) * cover
    d = blur(d, 1.2 * S)
    sx, sy = sun[0] - xx, sun[1] - yy
    sl = np.hypot(sx, sy) + 1e-6
    sx, sy = sx / sl, sy / sl
    tau = np.zeros_like(d)
    for dist, wgt in ((9, 1.0), (24, 0.85), (52, 0.62), (96, 0.42), (165, 0.26)):
        dd = dist * S
        tau += wgt * ndimage.map_coordinates(d, [yy + sy * dd, xx + sx * dd],
                                             order=1, mode='nearest')
    litv = np.exp(-tau * tau_k)
    near = np.exp(-sl / (W * 0.55))
    col = lerp3(dark, lite, litv ** 0.9)
    col = col * (1 - (near * litv)[..., None] * 0.50) + \
        np.asarray(hot, np.float32)[None, None, :] * (near * litv)[..., None] * 0.50
    return col, np.clip(d * 1.25, 0, 1)


def paint_sky(W, H, rng):
    X, Y, xx, yy = grids(W, H)
    SUN = (SUN0[0] * S, SUN0[1] * S)
    t = np.clip(Y / HOR0, 0, 1)

    zenith = mix('ultramarine', 2.6, 'burnt_umber', 2.2, 'ivory_black', 1.0, 'lead_white', 0.85)
    middle = mix('cerulean', 1.0, 'ultramarine', 0.5, 'lead_white', 1.25,
                 'burnt_umber', 0.45)
    lower = mix('naples', 2.2, 'lead_white', 1.4, 'light_red', 0.70, 'raw_umber', 0.25)
    sky = lerp3(zenith, middle, smoothstep(0.0, 0.66, t))
    sky = sky * (1 - smoothstep(0.58, 1.0, t)[..., None]) + \
        lerp3(middle, lower, smoothstep(0.58, 1.0, t)) * smoothstep(0.58, 1.0, t)[..., None]

    d_sun = np.hypot(xx - SUN[0], yy - SUN[1]) / (W * 0.95)
    glow = np.exp(-d_sun * 2.4)
    sky += glow[..., None] * np.asarray(
        mix('naples', 2.4, 'lead_white', 2.0, 'light_red', 0.50), np.float32) * 0.62
    # the storm thickens to the right and overhead
    storm = smoothstep(0.02, 1.0, X / 2000 * 0.56 + (1 - t) * 0.68)
    sky *= (1 - 0.60 * storm)[..., None]

    layers = [
        dict(scale=620, octv=3, thresh=0.46, soft=0.26, squash=1.9, tau_k=2.2, drift=26,
             cover=smoothstep(0.0, 0.52, 1 - t) * 0.55,
             dark=mix('ultramarine', 1.3, 'burnt_umber', 1.2, 'lead_white', 1.9),
             lite=mix('lead_white', 2.6, 'naples', 1.0),
             hot=mix('lead_white', 3.0, 'naples', 1.4)),
        dict(scale=400, octv=3, thresh=0.48, soft=0.20, squash=1.55, tau_k=4.0, drift=34,
             cover=np.clip(smoothstep(-0.05, 0.72, 1 - t)
                           * (0.48 + 0.60 * smoothstep(0.05, 0.95, X / 2000)), 0, 1),
             dark=mix('ultramarine', 1.6, 'burnt_umber', 2.6, 'ivory_black', 0.5,
                      'lead_white', 0.85),
             lite=mix('lead_white', 2.2, 'naples', 1.5, 'light_red', 0.55),
             hot=mix('lead_white', 2.8, 'naples', 1.8, 'light_red', 0.6)),
        dict(scale=235, octv=4, thresh=0.52, soft=0.16, squash=1.25, tau_k=5.0, drift=44,
             cover=np.clip(smoothstep(0.08, 0.60, 1 - t) * 0.42
                           + smoothstep(0.42, 1.0, X / 2000)
                           * smoothstep(-0.1, 0.72, 1 - t) * 0.72, 0, 1),
             dark=mix('burnt_umber', 2.6, 'ultramarine', 1.3, 'ivory_black', 1.1,
                      'lead_white', 0.45),
             lite=mix('lead_white', 1.6, 'naples', 1.3, 'light_red', 0.95),
             hot=mix('lead_white', 2.2, 'naples', 1.7, 'light_red', 0.9)),
    ]
    for L in layers:
        c, a = _cloud(W, H, rng, sun=SUN, **L)
        sky = sky * (1 - a[..., None]) + c * a[..., None]

    # shafts of light falling out of the break
    ang = np.arctan2(yy - SUN[1], xx - SUN[0])
    ray = fbm(H, W, 30 * S, rng, 3)
    ri = np.clip(np.sin(ang * 17 + ray * 7.0) * 0.5 + 0.5, 0, 1) ** 2.6
    ri *= np.exp(-d_sun * 1.25) * smoothstep(0.03, 0.40, d_sun)
    sky += ri[..., None] * np.asarray(
        mix('naples', 2.0, 'lead_white', 1.8), np.float32) * 0.34

    # rain squall trailing from the right-hand cloud mass
    sq = fbm(H, W, 60 * S, rng, 4)
    sq = warp(sq, np.full((H, W), 0.9, np.float32), np.full((H, W), 2.4, np.float32), 90 * S)
    squall = smoothstep(0.52, 0.80, sq) * smoothstep(0.35, 0.85, X / 2000) \
        * smoothstep(0.30, 0.78, t) * smoothstep(1.02, 0.86, t)
    sky = sky * (1 - 0.42 * squall[..., None]) + lerp3(
        mix('ultramarine', 1.2, 'burnt_umber', 1.6, 'lead_white', 1.5),
        mix('lead_white', 2, 'naples', 1), np.zeros_like(squall)) * 0.42 * squall[..., None]

    haze = smoothstep(0.86, 1.0, t)[..., None]
    sky = sky * (1 - haze * 0.5) + np.asarray(
        mix('lead_white', 2.0, 'naples', 1.2, 'cerulean', 0.45), np.float32) * haze * 0.5
    return np.clip(sky, 0, 1)


# ==========================================================================
# sea - kept deliberately simple: a value gradient, near-horizontal ripple,
# the sun's road, and a few caps.  The brush will do the rest.
# ==========================================================================
def paint_sea(img, W, H, rng):
    X, Y, xx, yy = grids(W, H)
    v = np.clip((Y - HOR0) / (H0 - HOR0), 0, 1)

    far = mix('lead_white', 1.5, 'cerulean', 0.80, 'naples', 0.95, 'burnt_umber', 0.55)
    mid = mix('terre_verte', 2.0, 'ultramarine', 0.9, 'burnt_umber', 1.9, 'lead_white', 0.26)
    near = mix('viridian', 1.3, 'burnt_umber', 2.0, 'ivory_black', 3.0, 'lead_white', 0.12)
    sea = lerp3(far, mid, smoothstep(0.0, 0.20, v))
    k2 = smoothstep(0.12, 0.80, v)
    sea = sea * (1 - k2[..., None]) + lerp3(mid, near, k2) * k2[..., None]

    ph = 1.0 / (v + 0.016)
    roll = (fbm(H, W, 300 * S, rng, 3) - 0.5) * 6.0
    fine = (fbm(H, W, 90 * S, rng, 4) - 0.5) * 2.2
    crest = np.zeros((H, W), np.float32)
    for k, amp in ((1.0, 1.0), (2.1, 0.46), (4.3, 0.22)):
        crest += amp * np.sin(ph * 1.75 * k + roll * k * 0.8 + fine * k * 0.5
                              + X * 0.0008 * k)
    crest = norm01(crest)
    face = np.clip((crest - 0.5) * 2, -1, 1)
    sea *= (1 + 0.125 * face * (0.25 + 0.75 * (1 - v)))[..., None]
    sea += (np.clip(face, 0, 1) ** 3 * (1 - v) ** 2 * 0.20)[..., None] * np.asarray(far, np.float32)

    road = np.exp(-((X - SUN0[0] - 90) / (130 + 760 * v)) ** 2)
    glint = smoothstep(0.72, 0.99, crest) * road * (0.25 + 0.75 * (1 - v) ** 2)
    sea += glint[..., None] * np.asarray(mix('lead_white', 2.4, 'naples', 1.9), np.float32) * 1.05

    # a swell breaking across the middle distance
    bx = fbm(H, W, 320 * S, rng, 3)
    for cy, amp, thick, bright in ((1700, 0.75, 30, 0.9), (1900, 0.5, 40, 0.7),
                                   (2150, 0.35, 54, 0.5)):
        line = cy + (bx - 0.5) * 150
        band = np.exp(-((Y - line) / thick) ** 2)
        crestm = band * smoothstep(0.46, 0.86, fbm(H, W, 110 * S, rng, 4)) * amp
        sea = sea * (1 - 0.70 * crestm[..., None]) + np.asarray(
            mix('lead_white', 2.3, 'naples', 1.0, 'cerulean', 0.5),
            np.float32)[None, None, :] * 0.70 * crestm[..., None] * bright
        trough = np.exp(-((Y - line - thick * 2.2) / (thick * 1.7)) ** 2) * amp
        sea *= (1 - 0.22 * trough)[..., None]

    capn = fbm(H, W, 26 * S, rng, 5)
    caps = smoothstep(0.76, 0.88, capn * 0.42 + crest * 0.72) * smoothstep(0.012, 0.12, v)
    caps *= (0.40 + 0.60 * road) * smoothstep(0.75, 0.22, v)
    foam = mix('lead_white', 2.3, 'naples', 0.7, 'cerulean', 0.7)
    sea = sea * (1 - caps[..., None] * 0.85) + np.asarray(foam, np.float32) * caps[..., None] * 0.85

    out = img.copy()
    e = smoothstep(HOR0 - 2.0, HOR0 + 2.0, Y)[..., None]
    out = out * (1 - e) + np.clip(sea, 0, 1) * e
    band = np.exp(-((Y - HOR0) / 6.0) ** 2)[..., None]
    return np.clip(out * (1 - 0.20 * band), 0, 1), v


# ==========================================================================
# the crag, the ledge she stands on, a dark foreground rock
# ==========================================================================
from PIL import Image, ImageDraw


def poly_mask(W, H, polys, rng, jag=70, scale=140, octv=5, feather=0.0):
    """rasterise silhouettes, then chew the edges with noise"""
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    for pts in polys:
        d.polygon([(x * S, y * S) for x, y in pts], fill=255)
    m = np.asarray(im, np.float32) / 255.0
    if jag:
        wx = fbm(H, W, scale * S, rng, octv, ridged=True) - 0.5
        wy = fbm(H, W, scale * S, rng, octv, ridged=True) - 0.5
        wx += (fbm(H, W, scale * 0.3 * S, rng, 3) - 0.5) * 0.6
        wy += (fbm(H, W, scale * 0.3 * S, rng, 3) - 0.5) * 0.6
        m = warp(m, wx, wy, jag * S)
    if feather:
        m = blur(m, feather * S)
    return m > 0.5


CRAG = [[(2000, 90), (1836, 186), (1664, 286), (1498, 372), (1366, 452),
         (1276, 548), (1238, 660), (1252, 840), (1214, 1060), (1196, 1300),
         (1178, 1560), (1168, 1850), (1226, 2130), (1150, 2600), (2000, 2600)],
        [(1176, 598), (1330, 520), (1560, 498), (1760, 540), (1742, 712),
         (1486, 760), (1250, 726)]]
LEDGE = [[(560, 2600), (700, 2492), (900, 2420), (1140, 2372), (1420, 2348),
          (1700, 2346), (2000, 2372), (2000, 2600)]]
FORE = [[(-40, 2430), (180, 2520), (380, 2596), (470, 2600), (-40, 2600)]]


def rock_masks(W, H, rng):
    return {
        'crag': poly_mask(W, H, CRAG, rng, jag=52, scale=240, octv=3, feather=1.2),
        'ledge': poly_mask(W, H, LEDGE, rng, jag=34, scale=180, octv=3, feather=1.2),
        'fore': poly_mask(W, H, FORE, rng, jag=44, scale=200, octv=3, feather=1.2),
    }


def _rock_relief(W, H, rng, strike=0.38, blocky=0.0):
    """broad masses, bedding planes, cleavage, a few faults"""
    X, Y, xx, yy = grids(W, H)
    broad = fbm(H, W, 420 * S, rng, 3)
    med = fbm(H, W, 165 * S, rng, 3)
    grit = fbm(H, W, 22 * S, rng, 3)
    bed = np.sin((Y * 1.0 - X * strike) / 112.0 + (fbm(H, W, 300 * S, rng, 3) - 0.5) * 7.0)
    bed = (bed * 0.5 + 0.5) ** 1.6
    fault = smoothstep(0.978, 0.996, fbm(H, W, 230 * S, rng, 5, ridged=True))
    relief = broad * 1.0 + med * 0.42 + bed * 0.30 + grit * 0.07
    if blocky:
        # cleavage: stone breaks along planes, so give it hard-edged facets
        # cleavage planes: each facet is a plane, and the step between two
        # facets is kept small - a big step reads as a crack, not a ridge
        blk = np.zeros((H, W), np.float32)
        for ang, w, amp, tilt in ((22, 210, 1.0, 0.55), (-64, 270, 0.75, 0.40),
                                  (78, 150, 0.45, 0.30)):
            a = np.radians(ang)
            u = (X * np.cos(a) + Y * np.sin(a)) / w
            u = u + (fbm(H, W, 260 * S, rng, 3) - 0.5) * 2.0
            cell = np.floor(u)
            frac = u - cell
            step = ((cell * 37.0) % 7.0) / 7.0            # each facet its own height
            blk += amp * (step * 0.55 + frac * tilt)
        blk = blur(norm01(blk), 6.0 * S)
        # facets belong in the *value*, not the height: a height step reads as
        # a crack, a value step reads as a plane turning away from the light
        relief = relief * (1 - blocky * 0.22) + blur(blk, 26 * S) * blocky * 0.30
        return relief, bed, fault, grit, blk
    return relief, bed, fault, grit, None


def paint_rock(img, W, H, rng, masks=None, parts=('crag', 'ledge', 'fore')):
    out = img.copy()
    masks = masks or rock_masks(W, H, rng)
    spec = {
        'crag': dict(base=mix('burnt_umber', 3.0, 'ultramarine', 0.7, 'ivory_black', 7.0,
                              'raw_sienna', 0.5, 'lead_white', 0.40), key=0.80, relief=215, rim=0.50,
                     strike=0.40, blocky=0.72),
        'ledge': dict(base=mix('burnt_umber', 2.0, 'raw_umber', 0.8, 'ivory_black', 6.0,
                               'raw_sienna', 0.3, 'lead_white', 0.34), key=0.68, relief=130, rim=0.30,
                      strike=0.10, blocky=0.60),
        'fore': dict(base=mix('vandyke', 1.6, 'ivory_black', 7.0, 'ultramarine', 0.4,
                              'lead_white', 0.12), key=0.38, relief=90, rim=0.12,
                     strike=0.60, blocky=0.55),
    }
    for which in parts:
        p = spec[which]
        m = masks[which]
        if not m.any():
            continue
        f = Form(H, W)
        relief, bed, fault, grit, blk = _rock_relief(W, H, rng, p['strike'],
                                                     p.get('blocky', 0.0))
        tone = 0.46 * norm01(relief) + 0.22 * bed + 0.12 * grit
        if blk is not None:
            tone = tone + 0.42 * blk
        alb = (np.asarray(p['base'], np.float32)[None, None, :]
               * (0.38 + 1.08 * tone)[..., None])
        alb *= (1 - 0.30 * fault)[..., None]
        f.slab(m, 430 * S, alb, 'rock', soft=52 * S, power=0.34)
        if which == 'crag':
            X, Y, _, _ = grids(W, H)
            shaft = np.exp(-(((X - 1480) / 310.) ** 2 + ((Y - 1060) / 580.) ** 2))
            shaft += 0.8 * np.exp(-(((X - 1700) / 330.) ** 2 + ((Y - 520) / 360.) ** 2))
            shaft += 0.6 * np.exp(-(((X - 1560) / 280.) ** 2 + ((Y - 1840) / 460.) ** 2))
            alb = alb * (1 + 0.95 * shaft)[..., None]
        f.z += blur(relief - fault * 0.45, 4.0 * S) * p['relief'] * S * m
        rgb, _ = shade(f, studio(key=p['key'], fill=0.20, bounce=0.19),
                       ao_radius=30 * S, ao_k=0.88, normal_scale=1.30,
                       normal_smooth=4.0 * S, sky_k=0.17,
                       rim=dict(d=KEY_DIR, c=tint(KEY_COL, 0.55), k=p['rim'], p=3.2))
        # the sun catches the upper-left edges of the stone
        X, Y, xx, yy = grids(W, H)
        em = m.astype(np.float32)
        lit_edge = np.clip(em - ndimage.shift(em, (7 * S, 9 * S), order=1), 0, 1)
        lit_edge = blur(lit_edge, 3.4 * S) * smoothstep(2500, 1000, Y)
        rgb = rgb + lit_edge[..., None] * np.asarray(
            tint(KEY_COL, 0.60), np.float32)[None, None, :] * p['rim'] * 0.5
        al = blur(m.astype(np.float32), 1.0 * S)[..., None]
        out = out * (1 - al) + np.clip(rgb, 0, 1) * al
    return out, masks
