"""The brushwork.

The composed image is the underpainting - it is never shown.  What gets shown
is paint: a warm ground, a dead-colour lay-in, then passes of progressively
smaller bristle brushes that follow the form, broken colour, then glazes in
the shadows, scumbles in the sky, impasto in the lights, and varnish.
"""
import numpy as np
from scipy import ndimage
import engine
from engine import (Canvas, mix, tint, fbm, blur, blur3, norm01, smoothstep,
                    direction_field, blend_dir, paint_region, impasto,
                    show_weave, glaze, scumble, bloom, varnish, vignette, craquelure)
import scene


def fields(target, W, H, rng, parts):
    """where the strokes should run"""
    X, Y, xx, yy = scene.grids(W, H)
    dx, dy, coh = direction_field(target, smooth=11.0 * scene.S)

    # sky: strokes sweep out of the break, following the weather
    SUN = (scene.SUN0[0], scene.SUN0[1])
    ax, ay = X - SUN[0], Y - SUN[1]
    al = np.hypot(ax, ay) + 1e-6
    sx, sy = -ay / al, ax / al                       # tangential to the break
    sx = sx * 0.20 + 1.00
    sy = sy * 0.20 + 0.08
    sl = np.hypot(sx, sy)
    sky_m = smoothstep(scene.HOR0 + 30, scene.HOR0 - 60, Y)
    dx, dy = blend_dir(dx, dy, sx / sl, sy / sl, sky_m * 0.62)

    # water: flat horizontal drag
    sea_m = smoothstep(scene.HOR0 - 20, scene.HOR0 + 40, Y)
    dx, dy = blend_dir(dx, dy, np.ones_like(dx), np.zeros_like(dy), sea_m * 0.58)

    # where the picture needs the small brushes
    g = np.abs(ndimage.laplace(blur(target.mean(2), 1.6 * scene.S)))
    detail = norm01(blur(g, 2.2 * scene.S)) ** 0.5
    for k, w in (('andromeda', 1.0), ('perseus', 0.85), ('cetus', 0.55)):
        if k in parts:
            detail = np.maximum(detail, blur(parts[k].astype(np.float32), 2 * scene.S) * w)
    return dx, dy, np.clip(detail, 0, 1), sky_m, sea_m


BROKEN = [mix('ochre', 2, 'lead_white', 1), mix('terre_verte', 2, 'lead_white', 1),
          mix('light_red', 2, 'lead_white', 1), mix('cerulean', 1.5, 'lead_white', 1.5),
          mix('madder', 1, 'lead_white', 2), mix('raw_umber', 2, 'lead_white', 1)]


def paint(target, parts, W, H, rng, quality=1.0):
    S = scene.S
    cv = Canvas(W, H, rng)
    cv.ground(mix('lead_white', 5, 'ochre', 1, 'raw_umber', 0.5),
              mix('raw_umber', 3, 'light_red', 1.4, 'lead_white', 1.0), rng)

    dx, dy, detail, sky_m, sea_m = fields(target, W, H, rng, parts)
    full = np.ones((H, W), np.float32)
    X, Y, xx, yy = scene.grids(W, H)

    fig = np.zeros((H, W), np.float32)
    for k, w in (('andromeda', 1.0), ('perseus', 0.95), ('cetus', 0.8)):
        if k in parts:
            fig = np.maximum(fig, blur(parts[k].astype(np.float32), 3 * S) * w)
    fig = np.clip(blur(fig, 6 * S) * 1.6, 0, 1)

    # ---- 1. dead colour: the whole canvas blocked in with a big brush ----
    dead = target * 0.86 + np.asarray(
        mix('raw_umber', 2, 'terre_verte', 1, 'lead_white', 1.4),
        np.float32)[None, None, :] * 0.14
    cv.begin()
    paint_region(cv, dead, dx, dy, full, 74 * S, rng=rng, density=0.40, length=3.6,
                 value_jitter=0.080, warm_jitter=0.05, load=0.55, wander=0.26,
                 blur_target=30 * S, broken_colors=BROKEN, p_broken=0.05)
    cv.end(load=0.40, soften=0.6 * S, wet=0.28)

    # ---- 2. blocking in, full colour ----
    cv.begin()
    paint_region(cv, target, dx, dy, full, 34 * S, rng=rng, density=0.42, length=3.4,
                 value_jitter=0.058, warm_jitter=0.040, load=0.75, wander=0.24,
                 blur_target=13 * S, broken_colors=BROKEN, p_broken=0.045)
    cv.end(load=0.52, soften=0.4 * S, wet=0.18)

    # ---- 3. modelling ----
    cv.begin()
    paint_region(cv, target, dx, dy, full, 17 * S, rng=rng, density=0.44, length=3.2,
                 value_jitter=0.044, warm_jitter=0.032, load=0.9, wander=0.20,
                 blur_target=5.5 * S, broken_colors=BROKEN, p_broken=0.032)
    cv.end(load=0.66, soften=0.3 * S, wet=0.12)

    # ---- 4. drawing back in where the picture is read ----
    m4 = np.clip(detail * 0.9 + fig * 0.8, 0, 1)
    cv.begin()
    paint_region(cv, target, dx, dy, m4, 9.5 * S, rng=rng, density=0.40, length=3.0,
                 value_jitter=0.026, warm_jitter=0.019, load=1.0, wander=0.16,
                 blur_target=2.2 * S, p_broken=0.018, broken_colors=BROKEN)
    cv.end(load=0.72, soften=0.18 * S, wet=0.05)

    # ---- 5. the small brush: heads, hands, chain, teeth, the sword ----
    fine = np.zeros((H, W), np.float32)
    for (cx, cy, r) in ((1248, 1040, 190), (846, 756, 150), (1240, 790, 110),
                        (1356, 800, 110), (980, 1400, 190), (1120, 1310, 150)):
        fine += np.exp(-(((X - cx) / r) ** 2 + ((Y - cy) / r) ** 2))
    fine = np.clip(fine * 1.2, 0, 1) * np.clip(detail + fig * 0.7, 0, 1)
    cv.begin()
    paint_region(cv, target, dx, dy, fine, 5.0 * S, rng=rng, density=0.42, length=2.6,
                 value_jitter=0.018, warm_jitter=0.013, load=1.0, wander=0.12,
                 blur_target=0.9 * S)
    cv.end(load=0.8, soften=0.0, wet=0.0)

    # ---- 5b. the heads get the finest brush in the box ----
    heads = np.zeros((H, W), np.float32)
    for (cx, cy, r) in ((1248, 1038, 120), (846, 752, 90)):
        heads += np.exp(-(((X - cx) / r) ** 4 + ((Y - cy) / r) ** 4))
    heads = np.clip(heads, 0, 1)
    cv.begin()
    paint_region(cv, target, dx, dy, heads, 3.0 * S, rng=rng, density=0.42, length=2.4,
                 value_jitter=0.018, warm_jitter=0.012, load=1.0, wander=0.10,
                 blur_target=0.5 * S)
    cv.end(load=0.6, soften=0.0, wet=0.0)

    # ---- 5c. blending.  A salon surface is blended, not dabbed: the
    #          brush is only allowed to show in the air, the water and the
    #          stone.  Flesh gets fused, then touched again. ----
    wblend = np.clip(0.26 + fig * 0.54 + heads * 0.22 + detail * 0.10, 0, 0.84)
    cv.rgb = cv.rgb * (1 - wblend[..., None]) + blur3(target, 0.7 * S) * wblend[..., None]
    cv.begin()
    paint_region(cv, target, dx, dy, np.clip(fig * 1.1, 0, 1), 6.0 * S, rng=rng,
                 density=0.46, length=2.8, value_jitter=0.016, warm_jitter=0.013,
                 load=0.8, wander=0.14, blur_target=1.1 * S, alpha=150)
    cv.end(load=0.5, soften=0.1 * S, wet=0.10)
    cv.begin()
    paint_region(cv, target, dx, dy, heads, 2.6 * S, rng=rng, density=0.5, length=2.2,
                 value_jitter=0.010, warm_jitter=0.008, load=0.8, wander=0.08,
                 blur_target=0.4 * S, alpha=170)
    cv.end(load=0.4, soften=0.0, wet=0.0)

    # ---- 5d. cutting in.  The background is brought back up to the
    #          contour, which is what kills the halo a loaded brush leaves
    #          when it drags light paint off a figure. ----
    figm = fig > 0.5
    for it, size, dens, ln in ((int(26 * S), 11.0, 0.30, 1.5),
                               (int(12 * S), 6.0, 0.28, 1.4),
                               (int(5 * S), 3.2, 0.30, 1.3)):
        band = (ndimage.binary_dilation(figm, iterations=max(2, it))
                & ~ndimage.binary_erosion(figm, iterations=max(1, int(2 * S))))
        cut = blur(band.astype(np.float32), 1.4 * S)
        cv.begin()
        paint_region(cv, target, dx, dy, np.clip(cut * 1.6, 0, 1), size * S, rng=rng,
                     density=dens, length=ln, value_jitter=0.026, warm_jitter=0.018,
                     load=0.8, wander=0.34, blur_target=0.8 * S)
        cv.end(load=0.5, soften=0.0, wet=0.05)

    # ---- 6. accents: the touches put on last with a loaded brush ----
    accents(cv, target, parts, W, H, rng)
    return cv, dict(dx=dx, dy=dy, detail=detail, sky_m=sky_m, sea_m=sea_m, fig=fig)


def accents(cv, target, parts, W, H, rng):
    """impasto highlights - the last, thickest paint on the picture"""
    S = scene.S
    lum = target.mean(2)
    hot = smoothstep(0.80, 0.97, lum)
    X, Y, xx, yy = scene.grids(W, H)
    # the lights on the figure and the sparkle on water and metal
    figs = np.clip(
        blur(parts.get('andromeda', np.zeros((H, W), bool)).astype(np.float32), 3 * S)
        + blur(parts.get('perseus', np.zeros((H, W), bool)).astype(np.float32), 3 * S), 0, 1)
    # on flesh the impasto is a few precise touches, not a snowfall
    weight = hot * (0.55 * (1 - figs) + 0.10 * figs)
    weight += smoothstep(0.84, 0.99, lum) * smoothstep(scene.HOR0 - 40, scene.HOR0 + 300, Y) * 0.5
    weight = np.clip(weight, 0, 1) * smoothstep(0.34, 0.60, lum)
    tb = blur3(target, 1.2 * S)
    cv.begin()
    ys, xs = np.nonzero(weight > 0.35)
    if len(ys):
        pick = rng.choice(len(ys), size=min(len(ys), int(20000 * S * S)), replace=False)
        for i in pick:
            y0, x0 = int(ys[i]), int(xs[i])
            if rng.random() > weight[y0, x0]:
                continue
            c = tb[y0, x0] * (1.03 + rng.random() * 0.10)
            a = rng.uniform(0, 2 * np.pi)
            L = rng.uniform(3, 13) * S
            seq = [(x0, y0), (x0 + np.cos(a) * L, y0 + np.sin(a) * L)]
            cv.stroke(seq, np.clip(c, 0, 1), rng.uniform(2.0, 5.5) * S,
                      alpha=255, load=1.6, rng=rng, bristles=2)
    cv.end(load=1.5, soften=0.0)


# ==========================================================================
# finishing: glazes, impasto, varnish
# ==========================================================================
def finish(cv, target, aux, parts, W, H, rng):
    S = scene.S
    X, Y, xx, yy = scene.grids(W, H)
    rgb = cv.rgb.copy()
    lum = rgb.mean(2)

    # a warm glaze in the shadows - the oil painter's way of getting depth
    shadow = smoothstep(0.52, 0.04, lum)
    rgb = glaze(rgb, mix('burnt_sienna', 2.6, 'burnt_umber', 1.0, 'madder', 0.8,
                          'ochre', 0.5), shadow * 0.40)
    # the crag and the foreground, glazed cooler and deeper still
    rocks = parts.get('rocks', {})
    rockm = np.zeros((H, W), np.float32)
    for k in ('crag', 'fore'):
        if k in rocks:
            rockm = np.maximum(rockm, rocks[k].astype(np.float32))
    rgb = glaze(rgb, mix('burnt_umber', 2.4, 'ultramarine', 0.7, 'ivory_black', 0.8,
                          'lead_white', 0.5), blur(rockm, 3 * S) * 0.22)
    # aerial perspective: the far water and the sky lose contrast
    far = smoothstep(scene.HOR0 + 220, scene.HOR0 - 40, Y)
    rgb = scumble(rgb, mix('lead_white', 2.2, 'naples', 1.0, 'cerulean', 0.7),
                  far * 0.16)

    # the warm half-tone that a hundred years of varnish gives the bottom
    rgb = glaze(rgb, mix('ochre', 2.0, 'burnt_sienna', 1.0, 'lead_white', 1.4),
                smoothstep(scene.HOR0, 2600, Y) * 0.17)

    # light scatter out of the break, and off the lit water
    rgb = bloom(rgb, thresh=0.88, radius=16 * S, amount=0.05)

    # the paint itself, raked by the gallery light
    rgb = impasto(rgb, cv.hgt, light=(-0.62, -0.72), relief=1.15 / max(S, 0.2) * 0.55,
                  sheen=0.26)
    rgb = show_weave(rgb, cv.hgt, cv.weave, amount=0.26)
    rgb = craquelure(rgb, rng, amount=0.045, scale=150 * S)
    rgb = np.clip(rgb * 1.07, 0, 1)
    rgb = varnish(rgb, contrast=1.075, lift=0.016, chroma=1.17,
                  warm=(1.035, 0.990, 0.912))
    rgb = vignette(rgb, strength=0.17, power=2.2)
    return np.clip(rgb, 0, 1)
