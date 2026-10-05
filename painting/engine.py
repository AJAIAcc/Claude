"""Oil-painting engine: ground, bristle brushes, impasto, glazes, varnish.

Nothing in this file knows about Perseus.  It is a paint box.  The canvas holds
two buffers - colour, and *thickness*, because the whole look of oil comes from
the fact that paint stands up off the cloth and catches the gallery light.  The
finishing operations (glaze, scumble, varnish, raking light) are the ones a
painter actually performs after the colour is down.
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# --------------------------------------------------------------------------
# a 19th-century studio palette.  Mixtures are stated as pigment recipes
# further down the stack, so the colour of the picture comes out of a box of
# real paints rather than arbitrary RGB.
# --------------------------------------------------------------------------
PIGMENTS = {
    'lead_white':     (0.965, 0.955, 0.928),
    'zinc_white':     (0.960, 0.962, 0.955),
    'naples':         (0.930, 0.840, 0.600),
    'ochre':          (0.760, 0.580, 0.260),
    'raw_sienna':     (0.640, 0.440, 0.215),
    'burnt_sienna':   (0.470, 0.215, 0.125),
    'light_red':      (0.600, 0.280, 0.210),
    'vermilion':      (0.790, 0.245, 0.130),
    'madder':         (0.490, 0.090, 0.150),
    'alizarin':       (0.400, 0.065, 0.125),
    'terre_verte':    (0.330, 0.370, 0.258),
    'viridian':       (0.095, 0.350, 0.280),
    'ultramarine':    (0.140, 0.170, 0.460),
    'prussian':       (0.050, 0.165, 0.250),
    'cobalt':         (0.170, 0.310, 0.600),
    'cerulean':       (0.260, 0.480, 0.620),
    'raw_umber':      (0.380, 0.320, 0.205),
    'burnt_umber':    (0.300, 0.190, 0.128),
    'vandyke':        (0.215, 0.150, 0.118),
    'ivory_black':    (0.085, 0.085, 0.098),
    'bone_black':     (0.110, 0.112, 0.130),
}


def mix(*pairs):
    """mix('lead_white', 4, 'ochre', 1) -> rgb tuple.  Slightly subtractive."""
    cols, wts = [], []
    it = iter(pairs)
    for name in it:
        w = next(it)
        cols.append(PIGMENTS[name] if isinstance(name, str) else name)
        wts.append(float(w))
    c = np.array(cols, np.float64)
    w = np.array(wts, np.float64)[:, None]
    w /= w.sum()
    lin = (c ** 1.8 * w).sum(0) ** (1 / 1.8)      # a touch darker than a mean
    return tuple(np.clip(lin, 0, 1))


def tint(c, k):
    """scale a colour's value without pushing it through white"""
    return tuple(np.clip(np.asarray(c, np.float64) * k, 0, 1))


# --------------------------------------------------------------------------
# noise / field utilities
# --------------------------------------------------------------------------
def _up(a, w, h):
    return np.asarray(Image.fromarray(a.astype(np.float32), 'F')
                      .resize((w, h), Image.BICUBIC), dtype=np.float32)


def fbm(h, w, scale, rng, octaves=5, persistence=0.5, lacunarity=2.0, ridged=False):
    out = np.zeros((h, w), np.float32)
    amp, tot, s = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        gh, gw = max(2, int(h / s) + 2), max(2, int(w / s) + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        u = _up(g, w, h)
        if ridged:
            u = 1.0 - np.abs(u * 2 - 1)
        out += amp * u
        tot += amp
        amp *= persistence
        s = max(1.5, s / lacunarity)
    return out / tot


def warp(field, dx, dy, amount):
    """push a field around by a vector field - gives clouds and water their drift"""
    h, w = field.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return ndimage.map_coordinates(field, [yy + dy * amount, xx + dx * amount],
                                   order=1, mode='nearest')


def blur(a, s):
    return a if s <= 0 else ndimage.gaussian_filter(a, s, mode='nearest')


def blur3(a, s):
    if s <= 0:
        return a
    return np.dstack([ndimage.gaussian_filter(a[..., i], s, mode='nearest') for i in range(3)])


def norm01(a):
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo + 1e-9)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-12), 0, 1)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------
# the canvas
# --------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, rng):
        self.w, self.h, self.rng = w, h, rng
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.hgt = np.zeros((h, w), np.float32)        # paint thickness in "mm"
        self.weave = self._linen()
        self._lay = None

    def _linen(self):
        """hand-primed linen: a coarse weave, slubs, and a few flecks"""
        h, w = self.h, self.w
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        p = 5.1
        warpt = np.sin(xx / p * 2 * np.pi + fbm(h, w, 90, self.rng, 3) * 1.4)
        weft = np.sin(yy / (p * 1.03) * 2 * np.pi + fbm(h, w, 90, self.rng, 3) * 1.4)
        over = (np.sin(xx / p * np.pi) * np.sin(yy / p * np.pi)) > 0
        t = np.where(over, warpt, weft) * 0.5 + 0.5
        slub = fbm(h, w, 26, self.rng, 4) ** 3 * 1.6
        return np.clip(t * 0.8 + slub * 0.2, 0, 1).astype(np.float32)

    # ---------------- ground ----------------
    def ground(self, base, imprim, rng):
        """chalk ground, then a rubbed-in warm imprimatura, thin and uneven"""
        h, w = self.h, self.w
        v = (fbm(h, w, 220, rng, 4) - 0.5) * 0.16 + 1.0
        g = np.asarray(base, np.float32)[None, None, :] * v[..., None]
        rag = fbm(h, w, 70, rng, 5)
        rag = norm01(blur(rag, 2.0))
        a = (0.55 + 0.45 * rag)[..., None]
        self.rgb = g * (1 - a) + np.asarray(imprim, np.float32)[None, None, :] * a
        self.rgb *= (0.86 + 0.14 * self.weave)[..., None]
        self.hgt += 0.05 + 0.04 * rag

    # ---------------- brushwork ----------------
    def begin(self):
        self._lay = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        self._d = ImageDraw.Draw(self._lay)
        self._hl = Image.new('L', (self.w, self.h), 0)
        self._hd = ImageDraw.Draw(self._hl)

    def end(self, load=1.0, soften=0.0, wet=0.0):
        """lay the pass down.  `wet` blends it into what is underneath, which is
        what happens when you work into paint that has not set."""
        lay = np.asarray(self._lay).astype(np.float32) / 255.0
        a = lay[..., 3:4].copy()
        col = lay[..., :3]
        if soften > 0:
            a = blur(a[..., 0], soften)[..., None]
            col = blur3(col, soften)
        new = self.rgb * (1 - a) + col * a
        if wet > 0:
            new = new * (1 - wet) + blur3(new, 1.6) * wet
        self.rgb = new
        self.hgt += (np.asarray(self._hl).astype(np.float32) / 255.0) * load
        self._lay = None

    def stroke(self, pts, color, width, *, alpha=255, bristles=None, spread=0.92,
               load=1.0, streak=0.16, taper=True, rng=None):
        """one loaded bristle brush dragged along `pts`"""
        rng = rng or self.rng
        n = len(pts)
        if n < 2:
            return
        w = max(1.0, float(width))
        nb = bristles if bristles else int(np.clip(w / 2.6, 2, 9))
        col = np.clip(np.asarray(color, np.float64), 0, 1)
        # per-point unit normals
        P = np.asarray(pts, np.float64)
        T = np.gradient(P, axis=0)
        L = np.hypot(T[:, 0], T[:, 1]) + 1e-9
        N = np.stack([-T[:, 1] / L, T[:, 0] / L], 1)
        bw = max(1.0, w / nb * 1.75)
        for i in range(nb):
            u = (i + 0.5) / nb - 0.5
            off = u * w * spread
            q = P + N * off
            # bristles carry different amounts of paint
            k = 1.0 + (rng.random() - 0.5) * 2 * streak
            dry = rng.random() < 0.13          # a bristle that has run dry
            c = tuple(int(255 * v) for v in np.clip(col * k, 0, 1))
            a = int(alpha * (0.45 if dry else 1.0) * (0.75 + 0.25 * rng.random()))
            seq = [tuple(map(float, p)) for p in q]
            self._d.line(seq, fill=c + (a,), width=int(round(bw)), joint='curve')
            if bw >= 3:
                r = bw / 2
                for p in (seq[0], seq[-1]):
                    self._d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=c + (a,))
            hv = int(np.clip(255 * load * (0.55 if dry else 1.0) * k, 0, 255))
            self._hd.line(seq, fill=hv, width=int(round(bw)), joint='curve')
            if taper and n > 2:
                # the last of the paint: thinner, more broken
                self._d.line(seq[-2:], fill=c + (int(a * 0.5),), width=max(1, int(bw * 0.6)))


# --------------------------------------------------------------------------
# painterly fill: drag strokes along a direction field, sampling a target
# --------------------------------------------------------------------------
def direction_field(target, smooth=9.0):
    """strokes want to run *along* form, i.e. across the value gradient"""
    g = target.mean(2)
    gy, gx = np.gradient(blur(g, smooth * 0.4))
    # structure tensor, smoothed, then minor eigenvector
    jxx = blur(gx * gx, smooth)
    jyy = blur(gy * gy, smooth)
    jxy = blur(gx * gy, smooth)
    t = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
    ang = t + np.pi / 2                      # along the ridge
    coh = np.hypot(jxx - jyy, 2 * jxy) / (jxx + jyy + 1e-7)
    return np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32), coh.astype(np.float32)


def blend_dir(dx, dy, dx2, dy2, w):
    """w=1 takes the second field"""
    x = dx * (1 - w) + dx2 * w
    y = dy * (1 - w) + dy2 * w
    l = np.hypot(x, y) + 1e-9
    return x / l, y / l


def paint_region(cv, target, dirx, diry, mask, size, *, rng, alpha=255, density=0.52,
                 length=2.4, wander=0.22, value_jitter=0.055, warm_jitter=0.035,
                 load=1.0, blur_target=None, width_var=(0.68, 1.30), segments=3,
                 detail=None, p_broken=0.04, broken_colors=None, spread=0.92):
    """one pass of brushwork over the region `mask`"""
    h, w = cv.h, cv.w
    tb = blur3(target, size * 0.34 if blur_target is None else blur_target)
    step = max(2.0, size * density)
    ys = np.arange(step * 0.5, h, step)
    xs = np.arange(step * 0.5, w, step)
    gx, gy = np.meshgrid(xs, ys)
    pts = np.stack([gx.ravel(), gy.ravel()], 1)
    pts += (rng.random(pts.shape) - 0.5) * step * 1.25
    xi = np.clip(pts[:, 0].astype(int), 0, w - 1)
    yi = np.clip(pts[:, 1].astype(int), 0, h - 1)
    keep = mask[yi, xi] > rng.random(len(pts)) * 0.6
    if detail is not None:
        keep &= detail[yi, xi] > rng.random(len(pts))
    pts = pts[keep]
    order = rng.permutation(len(pts))
    warm = np.array([0.055, 0.004, -0.050])
    for idx in order:
        x0, y0 = pts[idx]
        seq = [(x0, y0)]
        cx, cy = x0, y0
        seglen = size * length * rng.uniform(0.55, 1.45) / segments
        a0 = None
        for s in range(segments):
            ix, iy = int(np.clip(cx, 0, w - 1)), int(np.clip(cy, 0, h - 1))
            ux, uy = float(dirx[iy, ix]), float(diry[iy, ix])
            a = np.arctan2(uy, ux)
            if a0 is None:
                a0 = a
                if rng.random() < 0.5:
                    a0 += np.pi
            else:
                # keep going the same way round
                if np.cos(a - a0) < 0:
                    a += np.pi
                a = a0 + np.clip(np.angle(np.exp(1j * (a - a0))), -0.5, 0.5)
            a += (rng.random() - 0.5) * wander
            a0 = a
            cx += np.cos(a) * seglen
            cy += np.sin(a) * seglen
            seq.append((cx, cy))
        mx = int(np.clip((seq[0][0] + seq[-1][0]) / 2, 0, w - 1))
        my = int(np.clip((seq[0][1] + seq[-1][1]) / 2, 0, h - 1))
        c = tb[my, mx].astype(np.float64)
        c = c * (1 + (rng.random() - 0.5) * 2 * value_jitter)
        c = c + warm * (rng.random() - 0.5) * 2 * warm_jitter * (0.4 + c.mean())
        if broken_colors is not None and rng.random() < p_broken:
            # broken colour, but kept at the local value: a painter mixes a
            # different hue of the same tone, he does not drop white on a dark
            bc = np.asarray(broken_colors[rng.integers(len(broken_colors))])
            bc = bc * (c.mean() + 1e-4) / (bc.mean() + 1e-4)
            c = c * 0.58 + bc * 0.42
        cv.stroke(seq, np.clip(c, 0, 1), size * rng.uniform(*width_var),
                  alpha=alpha, load=load, rng=rng, spread=spread)


# --------------------------------------------------------------------------
# finishing
# --------------------------------------------------------------------------
def impasto(rgb, hgt, light=(-0.62, -0.72), relief=1.0, sheen=0.35):
    """rake the gallery light across the dried paint"""
    hh = blur(hgt, 0.7)
    gy, gx = np.gradient(hh)
    lx, ly = light
    lam = -(gx * lx + gy * ly) * relief
    lam = np.clip(lam, -1.2, 1.2)
    out = rgb * (1 + 0.42 * lam)[..., None]
    spec = (np.clip(lam, 0, None) ** 2 * sheen * np.clip(hgt, 0, 2))[..., None]
    return np.clip(out + spec * np.array([1.0, 0.97, 0.90]), 0, 1)


def show_weave(rgb, hgt, weave, amount=0.3):
    thin = np.exp(-np.clip(hgt, 0, 4) * 1.3)
    k = 1.0 - amount * thin * (1 - weave)
    return np.clip(rgb * k[..., None], 0, 1)


def glaze(rgb, color, amount):
    """a transparent coloured film - darkens and saturates, never lightens"""
    a = amount if np.ndim(amount) else np.full(rgb.shape[:2], amount, np.float32)
    c = np.asarray(color, np.float32)[None, None, :]
    return np.clip(rgb * (1 - a[..., None]) + rgb * c * a[..., None] * 1.55, 0, 1)


def scumble(rgb, color, amount):
    a = amount if np.ndim(amount) else np.full(rgb.shape[:2], amount, np.float32)
    c = np.asarray(color, np.float32)[None, None, :]
    return np.clip(rgb * (1 - a[..., None]) + c * a[..., None], 0, 1)


def bloom(rgb, thresh=0.72, radius=26, amount=0.30, warm=(1.0, 0.86, 0.66)):
    l = rgb.mean(2)
    m = np.clip((l - thresh) / (1 - thresh), 0, 1) ** 1.6
    b = blur(m, radius)
    return np.clip(rgb + b[..., None] * np.asarray(warm, np.float32) * amount, 0, 1)


def varnish(rgb, warm=(1.02, 0.985, 0.925), contrast=1.085, lift=0.012, chroma=1.0):
    x = np.clip(rgb, 0, 1)
    if chroma != 1.0:
        m = x.mean(2, keepdims=True)
        x = np.clip(m + (x - m) * chroma, 0, 1)
    x = (x - 0.5) * contrast + 0.5
    x = np.clip(x, 0, 1) ** 1.015
    x = x * np.asarray(warm, np.float32) + lift * np.array([1.0, 0.92, 0.78], np.float32)
    return np.clip(x, 0, 1)


def vignette(rgb, strength=0.26, power=2.3):
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx / w - 0.5) * 1.02, (yy / h - 0.5) * 1.06) * 1.62
    return np.clip(rgb * (1 - strength * np.clip(r, 0, 1) ** power)[..., None], 0, 1)


def craquelure(rgb, rng, amount=0.10, scale=120):
    h, w = rgb.shape[:2]
    n = fbm(h, w, scale, rng, 4, ridged=True)
    e = np.abs(ndimage.laplace(blur(n, 1.2)))
    cr = smoothstep(0.012, 0.05, e) * (fbm(h, w, 400, rng, 2) > 0.45)
    cr = blur(cr.astype(np.float32), 0.5)
    return np.clip(rgb * (1 - amount * cr[..., None]), 0, 1)


def save(rgb, path, w=None):
    a = (np.clip(rgb, 0, 1) ** (1 / 1.0) * 255).astype(np.uint8)
    im = Image.fromarray(a, 'RGB')
    if w:
        im = im.resize((w, int(round(w * im.height / im.width))), Image.LANCZOS)
    im.save(path, quality=96)
    return im
