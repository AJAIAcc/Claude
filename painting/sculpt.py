"""2.5-D modelling and academic studio lighting.

Figures are built the way a sculptor blocks them in: spheres, eggs and tapered
cylinders, each writing a depth into a buffer.  From that depth we get surface
normals, and from the normals we can light the figure properly - warm key,
cool sky fill, green bounce off the water, a reddish halftone where the light
dies on flesh, and reflected light in the shadows.  That halftone is the whole
secret of salon flesh painting; without it skin reads as plastic.
"""
import numpy as np
from scipy import ndimage
from engine import blur, blur3, smoothstep

MATS = {
    #                 spec pow  spec k  sss  sss colour          wrap  metal
    'skin':      dict(sp=24,  sk=0.11, ss=0.60, sc=(0.80, 0.20, 0.11), wr=0.40, me=0.0),
    'skin_m':    dict(sp=30,  sk=0.14, ss=0.42, sc=(0.70, 0.19, 0.11), wr=0.34, me=0.0),
    'linen':     dict(sp=12,  sk=0.05, ss=0.38, sc=(0.62, 0.52, 0.36), wr=0.52, me=0.0),
    'wool':      dict(sp=8,   sk=0.030, ss=0.30, sc=(0.55, 0.10, 0.08), wr=0.46, me=0.0),
    'hair':      dict(sp=58,  sk=0.34, ss=0.18, sc=(0.45, 0.17, 0.07), wr=0.30, me=0.0),
    'bronze':    dict(sp=88,  sk=0.95, ss=0.0,  sc=(0, 0, 0),          wr=0.12, me=1.0),
    'steel':     dict(sp=170, sk=1.25, ss=0.0,  sc=(0, 0, 0),          wr=0.10, me=1.0),
    'scale':     dict(sp=64,  sk=0.55, ss=0.10, sc=(0.25, 0.40, 0.18), wr=0.26, me=0.15),
    'rock':      dict(sp=13,  sk=0.055, ss=0.0, sc=(0, 0, 0),          wr=0.30, me=0.0),
    'feather':   dict(sp=22,  sk=0.13, ss=0.45, sc=(0.70, 0.52, 0.34), wr=0.50, me=0.0),
    'horn':      dict(sp=40,  sk=0.30, ss=0.35, sc=(0.78, 0.60, 0.36), wr=0.30, me=0.0),
}
MAT_ID = {k: i + 1 for i, k in enumerate(MATS)}


class Form:
    """a depth buffer you can model into.

    Everything works on a bounding box, so a figure can be built out of a few
    hundred small forms - which is what it takes before limbs stop looking
    like plumbing."""

    def __init__(self, h, w):
        self.h, self.w = h, w
        self.z = np.full((h, w), -1e6, np.float32)
        self.alb = np.zeros((h, w, 3), np.float32)
        self.mat = np.zeros((h, w), np.int16)
        self.mask = np.zeros((h, w), bool)

    def _box(self, x0, y0, x1, y1, pad=2):
        X0 = int(max(0, np.floor(min(x0, x1) - pad)))
        X1 = int(min(self.w, np.ceil(max(x0, x1) + pad) + 1))
        Y0 = int(max(0, np.floor(min(y0, y1) - pad)))
        Y1 = int(min(self.h, np.ceil(max(y0, y1) + pad) + 1))
        if X1 <= X0 or Y1 <= Y0:
            return None
        yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
        return (slice(Y0, Y1), slice(X0, X1)), xx, yy

    def _write(self, box, zz, sel, alb, mat, blendk=0.0):
        if not sel.any():
            return
        mid = MAT_ID[mat] if isinstance(mat, str) else mat
        Z = self.z[box]
        M = self.mask[box]
        upd = sel & (zz > Z)
        if upd.any():
            self.mat[box][upd] = mid
            A = np.asarray(alb, np.float32)
            if A.ndim == 1:
                self.alb[box][upd] = A
            else:
                self.alb[box][upd] = A[box][upd] if A.shape[:2] == (self.h, self.w) else A[upd]
        if blendk > 0:
            ov = sel & M
            if ov.any():
                a, b = Z[ov], zz[ov]
                mx = np.maximum(a, b)
                Z[ov] = mx + np.log1p(np.exp(-np.abs(a - b) * blendk)) / blendk
                rest = sel & ~ov
                Z[rest] = np.maximum(Z[rest], zz[rest])
            else:
                Z[sel] = np.maximum(Z[sel], zz[sel])
        else:
            Z[sel] = np.maximum(Z[sel], zz[sel])
        self.z[box] = Z
        self.mask[box] = M | sel

    def sphere(self, c, r, alb, mat, zoff=0.0, zk=1.0, blendk=0.0, squash=(1.0, 1.0), rot=0.0):
        return self.ellipsoid(c, (r * squash[0], r * squash[1], r), alb, mat,
                              zoff=zoff, zk=zk, blendk=blendk, rot=rot)

    def ellipsoid(self, c, r, alb, mat, zoff=0.0, zk=1.0, blendk=0.0, rot=0.0):
        rad = max(r[0], r[1])
        b = self._box(c[0] - rad, c[1] - rad, c[0] + rad, c[1] + rad)
        if b is None:
            return
        box, xx, yy = b
        ca, sa = np.cos(np.radians(rot)), np.sin(np.radians(rot))
        dx, dy = xx - c[0], yy - c[1]
        u, v = dx * ca + dy * sa, -dx * sa + dy * ca
        q = (u / r[0]) ** 2 + (v / r[1]) ** 2
        sel = q < 1.0
        zz = np.zeros_like(q)
        zz[sel] = zoff + np.sqrt(np.clip(1 - q[sel], 0, 1)) * r[2] * zk
        self._write(box, zz, sel, alb, mat, blendk)
        return box, sel

    def capsule(self, p0, p1, r0, r1, alb, mat, zoff=0.0, zk=1.0, blendk=0.0, zslope=0.0):
        rad = max(r0, r1)
        b = self._box(min(p0[0], p1[0]) - rad, min(p0[1], p1[1]) - rad,
                      max(p0[0], p1[0]) + rad, max(p0[1], p1[1]) + rad)
        if b is None:
            return
        box, xx, yy = b
        x0, y0 = p0
        x1, y1 = p1
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / L2, 0, 1)
        cx, cy = x0 + t * dx, y0 + t * dy
        rr = r0 + t * (r1 - r0)
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        sel = d2 < rr * rr
        zz = np.zeros_like(d2)
        zz[sel] = (zoff + t[sel] * zslope
                   + np.sqrt(np.clip(rr[sel] ** 2 - d2[sel], 0, None)) * zk)
        self._write(box, zz, sel, alb, mat, blendk)
        return box, sel

    def tube(self, pts, alb, mat, zk=1.0, blendk=0.0, steps_per=8, aspect=1.0, zoff=0.0):
        """a limb: a smooth path with a smoothly varying radius.

        pts is [(x, y, r), ...]; the path and the radius are both run through
        a Catmull-Rom spline and drawn as a dense row of ellipsoids, so the
        contour swells and tapers the way a real limb does."""
        P = np.asarray(pts, np.float64)
        n = len(P)
        if n < 2:
            return
        ext = np.vstack([P[0] + (P[0] - P[1]), P, P[-1] + (P[-1] - P[-2])])
        out = []
        for i in range(n - 1):
            p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
            seg = max(2, int(steps_per * max(1.0, np.hypot(*(p2[:2] - p1[:2])) / 18.0)))
            for s in range(seg):
                t = s / seg
                t2, t3 = t * t, t * t * t
                q = 0.5 * ((2 * p1) + (-p0 + p2) * t
                           + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                           + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
                out.append(q)
        out.append(P[-1])
        for q in out:
            self.ellipsoid((q[0], q[1]), (q[2], q[2] * aspect, q[2]), alb, mat,
                           zk=zk, blendk=blendk, zoff=zoff)

    def slab(self, mask, thick, alb, mat, zoff=0.0, soft=6.0, blendk=0.0, power=0.5):
        d = ndimage.distance_transform_edt(mask).astype(np.float32)
        d = blur(d, soft)
        zz = zoff + thick * np.clip(d / max(1e-6, d.max()), 0, 1) ** power
        box = (slice(0, self.h), slice(0, self.w))
        self._write(box, zz, mask, alb, mat, blendk)
        return mask

    def smooth_z(self, sigma, mask=None):
        """unify the blocked-in forms - the sculptor's thumb"""
        m = self.mask if mask is None else mask
        num = blur(np.where(m, self.z, 0).astype(np.float32), sigma)
        den = blur(m.astype(np.float32), sigma) + 1e-6
        self.z = np.where(m, num / den, self.z)

    def raise_by(self, mask, amount):
        self.z[mask] += amount

    def normals(self, smooth=1.6, scale=1.0):
        zf = np.where(self.mask, self.z, 0).astype(np.float32)
        zf = blur(zf, smooth)
        m = blur(self.mask.astype(np.float32), smooth) + 1e-5
        zf = zf / m
        gy, gx = np.gradient(zf)
        nx, ny = -gx * scale, -gy * scale
        nz = np.ones_like(nx)
        l = np.sqrt(nx * nx + ny * ny + nz * nz)
        return nx / l, ny / l, nz / l

    def occlusion(self, radius=22.0, k=1.0):
        zf = np.where(self.mask, self.z, self.z.min())
        wide = blur(zf, radius)
        ao = 1.0 - k * np.clip((wide - zf) / (radius * 0.55), 0, 1)
        return np.clip(ao, 0.12, 1.0)


# --------------------------------------------------------------------------
def light(dirv, col, k, kind='key'):
    d = np.asarray(dirv, np.float64)
    d /= np.linalg.norm(d)
    return dict(d=d, c=np.asarray(col, np.float64), k=float(k), kind=kind)


def shade(form, lights, *, ao_radius=24.0, ao_k=0.85, normal_scale=1.0,
          normal_smooth=1.6, sky=(0.42, 0.55, 0.80), sky_k=0.22,
          rim=None, bump=None, bump_k=0.0, edge_turn=0.0):
    """light the modelled forms"""
    h, w = form.h, form.w
    nx, ny, nz = form.normals(normal_smooth, normal_scale)
    if bump is not None and bump_k:
        gy, gx = np.gradient(blur(bump, 0.8))
        nx = nx - gx * bump_k
        ny = ny - gy * bump_k
        l = np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx / l, ny / l, nz / l
    ao = form.occlusion(ao_radius, ao_k)
    alb = form.alb
    out = np.zeros((h, w, 3), np.float32)

    # material parameter maps
    sp = np.zeros((h, w), np.float32)
    sk = np.zeros((h, w), np.float32)
    ss = np.zeros((h, w), np.float32)
    wr = np.zeros((h, w), np.float32)
    me = np.zeros((h, w), np.float32)
    sc = np.zeros((h, w, 3), np.float32)
    for name, p in MATS.items():
        m = form.mat == MAT_ID[name]
        if not m.any():
            continue
        sp[m], sk[m], ss[m], wr[m], me[m] = p['sp'], p['sk'], p['ss'], p['wr'], p['me']
        sc[m] = p['sc']

    vz = 1.0
    for L in lights:
        lx, ly, lz = L['d']
        ndl = nx * lx + ny * ly + nz * lz
        lam = np.clip(ndl, 0, 1)
        wrapped = np.clip((ndl + wr) / (1 + wr), 0, 1)
        diff = lam * (1 - wr) + wrapped * wr
        if L['kind'] == 'key':
            shadow = ao
        elif L['kind'] == 'bounce':
            shadow = 0.45 + 0.55 * ao
        else:
            shadow = 0.30 + 0.70 * ao
        c = L['c'] * L['k']
        base = alb * (1 - 0.78 * me)[..., None]
        out += base * (diff * shadow)[..., None] * c[None, None, :]
        # the halftone: light scattering through flesh where the form turns away
        if L['kind'] == 'key':
            band = np.exp(-((ndl - 0.10) / 0.33) ** 2)
            out += (alb * sc) * (band * ss * shadow * 0.85)[..., None] * c[None, None, :]
        # specular
        hx, hy, hz = lx, ly, lz + vz
        hl = np.sqrt(hx * hx + hy * hy + hz * hz) + 1e-9
        ndh = np.clip((nx * hx + ny * hy + nz * hz) / hl, 0, 1)
        s = ndh ** np.clip(sp, 1, None) * sk * shadow
        stint = np.where(me[..., None] > 0.5, alb, np.ones((h, w, 3), np.float32))
        out += (s[..., None] * stint) * c[None, None, :] * L['k'] ** 0.5

    # hemispheric sky light from straight above (y is down)
    hemi = np.clip(0.5 - ny * 0.5, 0, 1) ** 1.1
    out += alb * (hemi * sky_k * (0.25 + 0.75 * ao))[..., None] * np.asarray(sky, np.float32)[None, None, :]

    if edge_turn > 0:
        # At the silhouette the surface is edge-on to us: it has turned away
        # from the light as well, so the extreme contour darkens.  Without
        # this every figure wears a halo.
        d = ndimage.distance_transform_edt(form.mask).astype(np.float32)
        turn = np.clip(d / max(1e-6, edge_turn), 0, 1)
        turn = turn * turn * (3 - 2 * turn)
        out *= (0.34 + 0.66 * turn)[..., None]

    if rim is not None:
        rx, ry, rz = np.asarray(rim['d'], np.float64)
        ndl = nx * rx + ny * ry + nz * rz
        fres = (1 - nz) ** rim.get('p', 2.6)
        r = np.clip(ndl, 0, 1) ** 1.2 * fres * rim['k']
        out += r[..., None] * np.asarray(rim['c'], np.float32)[None, None, :]

    return np.clip(out, 0, 6), dict(nx=nx, ny=ny, nz=nz, ao=ao)
