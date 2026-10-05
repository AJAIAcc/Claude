"""The figures, modelled as a sculptor blocks them: eggs, spheres, cylinders.

Every coordinate is given on the 2000 x 2600 canvas.  Anatomy is laid out
from the skeleton outward - shoulder, elbow, wrist - so the forms sit on a
believable armature rather than being traced from a silhouette.
"""
import numpy as np
from scipy import ndimage
from engine import mix, tint, fbm, blur, blur3, norm01, smoothstep, warp
import scene
from scene import studio, KEY_DIR, KEY_COL, grids, lerp3


# Each figure is drawn in its own design frame and then placed on the canvas.
# XF = (scale, dx, dy): a figure can be enlarged and moved without rewriting
# every coordinate in its anatomy.
# (scale, dx, dy, rot_degrees, pivot_x, pivot_y)
XF = (1.0, 0.0, 0.0, 0.0, 1000.0, 1300.0)


def TX(x, y):
    sx, dx, dy, rot, px, py = XF
    u, v = x - px, y - py
    if rot:
        ca, sa = np.cos(np.radians(rot)), np.sin(np.radians(rot))
        u, v = u * ca - v * sa, u * sa + v * ca
    return (px + u * sx + dx, py + v * sx + dy)


def TS(v):
    return v * XF[0]


def TR(rot):
    return rot + XF[3]


def sc(v):
    return v * XF[0] * scene.S


def P(x, y):
    X, Y = TX(x, y)
    return (X * scene.S, Y * scene.S)


def TP(pts):
    """transform a tube's (x, y, r) list into canvas pixels"""
    return [(P(x, y)[0], P(x, y)[1], sc(r)) for x, y, r in pts]


def TPoly(polys):
    return [[TX(x, y) for x, y in poly] for poly in polys]
from sculpt import Form, light, shade

# ---- flesh ---------------------------------------------------------------
FLESH = mix('lead_white', 6.0, 'naples', 1.5, 'light_red', 1.05, 'ochre', 0.40)
FLESH_WARM = mix('lead_white', 5.0, 'naples', 1.3, 'light_red', 2.0, 'vermilion', 0.35)
FLESH_COOL = mix('lead_white', 6.0, 'naples', 1.0, 'light_red', 0.70,
                 'terre_verte', 0.45, 'ultramarine', 0.12)
FLESH_M = mix('lead_white', 2.9, 'ochre', 1.7, 'light_red', 1.6, 'raw_sienna', 1.1)
FLESH_M_WARM = mix('lead_white', 2.4, 'ochre', 1.5, 'light_red', 2.6, 'burnt_sienna', 0.9)
FLESH_M_COOL = mix('lead_white', 3.0, 'ochre', 1.4, 'light_red', 1.1, 'terre_verte', 0.8)

HAIR_DARK = mix('burnt_umber', 2.4, 'vandyke', 1.6, 'burnt_sienna', 1.0, 'ivory_black', 0.8)
HAIR_LIT = mix('raw_sienna', 2.0, 'burnt_sienna', 1.4, 'naples', 0.8)
LINEN_W = mix('lead_white', 3.6, 'naples', 1.8, 'ochre', 0.80, 'ultramarine', 0.35)
CLOAK = mix('madder', 2.4, 'vermilion', 0.9, 'burnt_sienna', 1.4, 'alizarin', 1.0)
BRONZE = mix('ochre', 2.2, 'raw_sienna', 1.4, 'burnt_sienna', 0.8, 'lead_white', 0.7)
STEEL = mix('lead_white', 2.0, 'ultramarine', 0.6, 'ivory_black', 0.9)
IRON = mix('ivory_black', 2.4, 'burnt_umber', 1.2, 'ultramarine', 0.5, 'lead_white', 0.45)


def _mottle(W, H, rng, k=0.06, scale=46):
    return 1.0 + (fbm(H, W, scale * scene.S, rng, 4) - 0.5) * 2 * k


# ==========================================================================
# anatomy relief - landmarks drawn as a greyscale sketch and fed to the
# shader as a bump.  Clavicle, sternum, linea alba, iliac crest, kneecap,
# the tendons behind the ankle: the things that make flesh read as a body.
# ==========================================================================
from PIL import Image, ImageDraw


class Relief:
    """draw raised (+) and sunken (-) anatomy"""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.pos = Image.new('L', (W, H), 0)
        self.neg = Image.new('L', (W, H), 0)
        self.dp = ImageDraw.Draw(self.pos)
        self.dn = ImageDraw.Draw(self.neg)

    def line(self, pts, width, v):
        d = self.dp if v > 0 else self.dn
        d.line([P(*p) for p in pts], fill=int(min(255, abs(v) * 255)),
               width=max(1, int(round(sc(width)))), joint='curve')

    def blob(self, c, r, v, squash=(1.0, 1.0)):
        d = self.dp if v > 0 else self.dn
        x, y = P(*c)
        rx, ry = sc(r * squash[0]), sc(r * squash[1])
        d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=int(min(255, abs(v) * 255)))

    def field(self, soft=3.0):
        a = np.asarray(self.pos, np.float32) / 255.0
        b = np.asarray(self.neg, np.float32) / 255.0
        return blur(a - b, soft * scene.S)


# ==========================================================================
# ANDROMEDA
#   8 heads tall; weight on her left leg so that hip rides high and the
#   ribcage counter-shifts left; arms drawn up and bound above her head;
#   the head thrown back and turned up to the left, where Perseus comes.
# ==========================================================================
def local(c, rot):
    """head-local (u right, v down the face) -> canvas"""
    ca, sa = np.cos(np.radians(rot)), np.sin(np.radians(rot))

    def g(u, v):
        return (c[0] + u * ca - v * sa, c[1] + u * sa + v * ca)
    return g


HEAD_C, HEAD_R, HEAD_ROT = (1248, 1040), (55, 66, 56), -14


def andromeda(W, H, rng):
    f = Form(H, W)
    mot = _mottle(W, H, rng, 0.04)[..., None]

    def A(c, k=1.0):
        return np.clip(np.asarray(c, np.float32)[None, None, :] * mot * k, 0, 1)

    sk, skw, skc = A(FLESH), A(FLESH_WARM), A(FLESH_COOL)
    B = 0.045 / scene.S

    def T(pts, alb=sk, mat='skin', zk=0.86, aspect=1.0):
        f.tube(TP(pts), alb, mat, zk=zk, blendk=B, aspect=aspect)

    def ell(c, r, alb=sk, mat='skin', zk=1.0, **kw):
        return f.ellipsoid(P(*c), (sc(r[0]), sc(r[1]), sc(r[2])), alb, mat,
                           blendk=B, zk=zk, **kw)

    def sph(c, r, alb=sk, mat='skin', zk=0.85, **kw):
        return f.sphere(P(*c), sc(r), alb, mat, blendk=B, zk=zk, **kw)

    hl = local(HEAD_C, HEAD_ROT)

    # ---------------- legs ----------------
    # her right: the free leg, knee turned in, calf swelling outboard
    T([(1268, 1506, 60), (1262, 1572, 57), (1252, 1652, 52), (1244, 1722, 45),
       (1240, 1780, 41), (1238, 1812, 39), (1240, 1848, 37), (1226, 1892, 35),
       (1234, 1944, 27), (1248, 1992, 21), (1256, 2030, 17)], skc, zk=0.84)
    T([(1256, 2034, 17), (1240, 2056, 18), (1214, 2068, 14), (1206, 2074, 10),
       (1194, 2076, 7)], skw, zk=0.7)
    # her left: the weight leg, straight, hip riding high
    T([(1376, 1500, 61), (1382, 1566, 58), (1392, 1646, 53), (1400, 1718, 46),
       (1404, 1776, 42), (1406, 1806, 40), (1408, 1844, 38), (1422, 1888, 36),
       (1414, 1942, 27), (1403, 1994, 21), (1398, 2034, 17)], sk, zk=0.84)
    T([(1398, 2038, 17), (1414, 2060, 18), (1442, 2072, 14), (1456, 2078, 10),
       (1470, 2080, 7)], skw, zk=0.7)

    # ---------------- torso ----------------
    T([(1262, 1188, 99), (1274, 1252, 101), (1284, 1322, 95), (1292, 1392, 83),
       (1300, 1452, 72), (1310, 1502, 88), (1318, 1546, 104), (1320, 1588, 97),
       (1320, 1616, 84)], sk, zk=0.80)
    sph((1196, 1212), 38, sk, zk=0.72)                        # deltoids
    sph((1340, 1218), 38, sk, zk=0.72)
    T([(1206, 1200, 26), (1256, 1176, 28), (1300, 1178, 28), (1348, 1204, 26)],
      sk, zk=0.48)                                            # trapezius
    T([(1270, 1202, 32), (1262, 1160, 29), (1256, 1122, 27)], skc, zk=0.88)
    T([(1268, 1150, 11), (1284, 1178, 13), (1296, 1196, 13)], skw, zk=0.5)

    # ---------------- arms ----------------
    T([(1190, 1206, 39), (1164, 1132, 34), (1142, 1062, 30), (1126, 1012, 26),
       (1138, 964, 25), (1164, 912, 22), (1188, 874, 18), (1200, 854, 15)], sk, zk=0.86)
    T([(1200, 852, 16), (1208, 830, 18), (1216, 810, 18)], skw, zk=0.8)   # palm
    for fx, fy, ex, ey, r0 in ((1206, 806, 1214, 776, 6.5), (1216, 804, 1226, 772, 6.8),
                               (1226, 806, 1236, 778, 6.4), (1234, 812, 1242, 790, 5.6),
                               (1200, 812, 1192, 788, 5.8)):
        T([(fx, fy, r0), ((fx + ex) / 2, (fy + ey) / 2, r0 * 0.88), (ex, ey, r0 * 0.6)],
          skw, zk=0.75)
    T([(1338, 1212, 39), (1374, 1140, 34), (1410, 1076, 30), (1440, 1030, 26),
       (1438, 984, 25), (1416, 938, 22), (1396, 902, 18), (1384, 882, 15)], sk, zk=0.86)
    T([(1384, 880, 16), (1376, 858, 18), (1368, 838, 18)], skw, zk=0.8)   # palm
    for fx, fy, ex, ey, r0 in ((1360, 832, 1352, 802, 6.5), (1370, 830, 1364, 798, 6.8),
                               (1380, 832, 1376, 802, 6.4), (1388, 838, 1386, 814, 5.6),
                               (1356, 840, 1342, 820, 5.8)):
        T([(fx, fy, r0), ((fx + ex) / 2, (fy + ey) / 2, r0 * 0.88), (ex, ey, r0 * 0.6)],
          skw, zk=0.75)

    f.smooth_z(5.0 * scene.S)

    # ---------------- secondary forms, after the thumb ----------------
    ell((1212, 1300), (46, 39, 34), skw, rot=TR(-22), zk=1.0, zoff=sc(7))   # breasts
    ell((1322, 1288), (45, 38, 33), skw, rot=TR(20), zk=1.0, zoff=sc(7))
    sph((1232, 1796), 18, skw, zk=0.5)                         # kneecaps
    sph((1412, 1790), 18, skw, zk=0.5)
    # head
    ell(HEAD_C, HEAD_R, sk, rot=TR(HEAD_ROT), zk=0.95)
    sph(hl(-2, 52), 16, skw, zk=0.42)
    T([(hl(-30, 28)[0], hl(-30, 28)[1], 14), (hl(-4, 46)[0], hl(-4, 46)[1], 15),
       (hl(28, 26)[0], hl(28, 26)[1], 14)], sk, zk=0.22)       # jaw
    sph(hl(-26, 2), 13, sk, zk=0.20)
    sph(hl(22, 4), 13, sk, zk=0.20)
    T([(hl(-5, 2)[0], hl(-5, 2)[1], 5), (hl(-7, 16)[0], hl(-7, 16)[1], 6),
       (hl(-8, 27)[0], hl(-8, 27)[1], 7)], skw, zk=0.75)       # nose
    sph(hl(38, 2), 10, skc, zk=0.35)                           # ear
    f.smooth_z(1.5 * scene.S)
    skin = f.mask.copy()

    # ---------------- the face ----------------
    face_alb, face_rel = face(W, H, TX(*HEAD_C), HEAD_R, HEAD_ROT, skin,
                              dark=HAIR_DARK, fs=XF[0],
                              lip=mix('madder', 1.4, 'light_red', 1.5, 'lead_white', 1.5))
    a4 = face_alb[..., 3:4]
    f.alb = f.alb * (1 - a4) + face_alb[..., :3] * a4

    # ---------------- anatomy relief (whisper-light) ----------------
    r = Relief(W, H)
    r.line([(1282, 1196), (1242, 1198), (1206, 1204)], 13, 0.24)
    r.line([(1282, 1196), (1320, 1200), (1352, 1208)], 13, 0.24)
    r.blob((1282, 1198), 8, -0.32)
    r.line([(1288, 1214), (1292, 1270)], 10, 0.12)
    r.line([(1300, 1348), (1304, 1440)], 9, 0.11)
    r.blob((1304, 1448), 7, -0.40)
    r.line([(1234, 1352), (1272, 1390), (1302, 1398)], 12, 0.10)
    r.line([(1350, 1344), (1326, 1384), (1306, 1396)], 12, 0.10)
    r.line([(1256, 1480), (1304, 1500), (1364, 1476)], 14, 0.14)
    r.line([(1268, 1498), (1302, 1530)], 11, 0.12)
    r.line([(1356, 1492), (1322, 1526)], 11, 0.12)
    r.line([(1250, 2010), (1258, 2030)], 7, 0.13)
    r.line([(1392, 2016), (1398, 2036)], 7, 0.13)
    r.blob((1214, 1316), 21, -0.15)
    r.blob((1320, 1306), 21, -0.15)
    relief = r.field(5.0) + face_rel * 0.55

    # ---------------- hair ----------------
    hair = Form(H, W)
    hb = 0.07 / scene.S
    hcol = np.asarray(HAIR_DARK, np.float32)
    hc = local(HEAD_C, HEAD_ROT)(0, -34)
    hair.ellipsoid(P(*hc), (sc(58), sc(44), sc(48)), hcol, 'hair',
                   rot=TR(HEAD_ROT), blendk=hb, zk=0.8)
    for pts in (
        [(1204, 1000, 26), (1186, 1036, 25), (1176, 1082, 23), (1166, 1132, 20),
         (1150, 1186, 16), (1132, 1240, 11), (1116, 1288, 6)],
        [(1222, 986, 24), (1200, 1018, 22), (1190, 1062, 19), (1184, 1110, 15),
         (1178, 1156, 10)],
        [(1296, 1012, 22), (1312, 1058, 19), (1322, 1104, 14), (1330, 1146, 8)],
        [(1252, 968, 26), (1284, 982, 22), (1302, 1008, 16)]):
        hair.tube(TP(pts), hcol, 'hair', zk=0.78, blendk=hb)
    hair.smooth_z(4.0 * scene.S)
    # keep the face clear: hair frames it, it does not swallow it
    hf = local(HEAD_C, HEAD_ROT)
    X, Y, _, _ = grids(W, H)
    ca, sa = np.cos(np.radians(TR(HEAD_ROT))), np.sin(np.radians(TR(HEAD_ROT)))
    hcx, hcy = TX(*HEAD_C)
    du, dv = (X - hcx) / XF[0], (Y - hcy) / XF[0]
    uu, vv = du * ca + dv * sa, -du * sa + dv * ca
    face_oval = ((uu - 0) / 47.0) ** 2 + ((vv - 14) / 50.0) ** 2 < 1.0
    hair_mask = hair.mask & ~face_oval

    # ---------------- cloth ----------------
    from scene import poly_mask
    cloth_poly = [
        # a slip of cloth low on the hips, and a short fall - no more
        [(1234, 1520), (1292, 1498), (1360, 1496), (1420, 1512), (1446, 1542),
         (1440, 1588), (1396, 1600), (1330, 1592), (1268, 1584), (1234, 1562)],
        [(1414, 1580), (1444, 1596), (1446, 1664), (1434, 1736), (1416, 1796),
         (1396, 1832), (1378, 1824), (1396, 1760), (1408, 1690), (1410, 1626)],
        [(1246, 1562), (1206, 1586), (1178, 1624), (1168, 1664), (1198, 1650),
         (1230, 1614), (1254, 1584)]]
    cloth = poly_mask(W, H, TPoly(cloth_poly), rng, jag=12, scale=80)

    return dict(form=f, skin=skin, relief=relief, hair=hair, hair_mask=hair_mask,
                cloth=cloth, head=(HEAD_C, HEAD_R, HEAD_ROT))


# --------------------------------------------------------------------------
def face(W, H, c, r, rot, skin, dark, lip, male=False, mid=-5.0, eye_v=4.0, fs=1.0):
    """features in head-local coordinates; albedo overlay + relief"""
    X, Y, xx, yy = grids(W, H)
    ca, sa = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    dx, dy = X - c[0], Y - c[1]
    u = (dx * ca + dy * sa) / fs
    v = (-dx * sa + dy * ca) / fs
    out = np.zeros((H, W, 4), np.float32)
    rel = np.zeros((H, W), np.float32)

    def el(cu, cv, ru, rv, soft=1.5):
        q = ((u - cu) / ru) ** 2 + ((v - cv) / rv) ** 2
        return smoothstep(1.0, 1.0 - soft / max(ru, rv), q)

    def put(m, col, a=1.0):
        aa = (m * a)[..., None]
        out[..., :3] = out[..., :3] * (1 - aa) + np.asarray(col, np.float32)[None, None, :] * aa
        out[..., 3] = np.maximum(out[..., 3], (m * a))

    ew = 10.5 if not male else 11.5
    # sockets, brow ridge, nose, mouth: relief only
    rel -= (el(mid - 19, eye_v, 16, 11) + el(mid + 14, eye_v, 15, 11)) * 0.34
    rel += (el(mid - 19, eye_v - 13, 17, 6) + el(mid + 14, eye_v - 13, 16, 6)) * 0.26
    rel += el(mid - 3, eye_v + 10, 5.5, 20) * 0.26
    rel -= (el(mid - 11, eye_v + 27, 4, 3) + el(mid + 6, eye_v + 27, 4, 3)) * 0.40
    rel += el(mid - 3, eye_v + 38, 11, 5) * 0.16
    rel -= el(mid - 3, eye_v + 39.5, 10, 1.6) * 0.40

    sclera = mix('lead_white', 2.2, 'ochre', 0.30, 'light_red', 0.22, 'ultramarine', 0.10)
    iris = mix('burnt_umber', 2.0, 'raw_sienna', 1.2, 'ivory_black', 0.5)
    for cu, s in ((mid - 19, -1), (mid + 14, 1)):
        e = el(cu, eye_v, ew, 5.6, soft=1.0)
        put(e, sclera, 0.80)
        # the eyes are turned up: the iris rides high under the lid
        iy = eye_v - 1.6 if not male else eye_v + 0.6
        put(el(cu + 1.2 * s, iy, 5.0, 5.0, soft=0.9) * e, iris, 0.92)
        put(el(cu + 1.2 * s, iy, 2.1, 2.1, soft=0.9) * e, (0.06, 0.055, 0.06), 0.95)
        put(el(cu - 1.8, iy - 1.8, 1.2, 1.2, soft=0.9) * e, (0.99, 0.97, 0.92), 0.85)
        put(el(cu, eye_v - 4.0, ew, 2.4, soft=0.9) * e, tint(dark, 1.3), 0.30)
        put(el(cu, eye_v - 4.8, ew + 0.5, 0.9, soft=0.9), tint(dark, 1.0), 0.42)
        put(el(cu, eye_v + 5.4, ew * 0.9, 1.0, soft=0.9), tint(dark, 1.5), 0.30)
    # brows lifted and drawn together: the expression does most of the work
    brow_lift = 0.0 if male else 2.6
    for cu, tilt in ((mid - 20, 2.2), (mid + 15, -2.2)):
        put(el(cu, eye_v - 12 - brow_lift - tilt * 0.4, 15, 2.8, soft=1.1),
            tint(dark, 1.25), 0.45)
        put(el(cu + 7 * np.sign(tilt), eye_v - 11 - brow_lift, 7, 2.0, soft=1.1),
            tint(dark, 1.15), 0.30)
    # the mouth is open - she is calling out
    gap = 0.0 if male else 2.3
    put(el(mid - 3, eye_v + 35 - gap, 9.0, 3.3), lip, 0.60)
    put(el(mid - 3, eye_v + 42.5 + gap, 9.8, 4.1), tint(lip, 1.16), 0.60)
    if not male:
        put(el(mid - 3, eye_v + 39, 7.4, 2.6), tint(dark, 0.95), 0.72)
        put(el(mid - 3, eye_v + 41.4, 6.0, 1.1), (0.72, 0.60, 0.56), 0.35)
    else:
        put(el(mid - 3, eye_v + 38.5, 9.5, 0.8), tint(lip, 0.72), 0.55)
    put(el(mid - 10, eye_v + 27, 2.6, 2.0), tint(dark, 1.1), 0.38)
    put(el(mid + 5, eye_v + 27, 2.6, 2.0), tint(dark, 1.1), 0.38)

    out[..., 3] *= skin.astype(np.float32)
    return out, rel * skin


def shade_andromeda(W, H, rng, parts, key=1.14):
    f = parts['form']
    pores = fbm(H, W, 11 * scene.S, rng, 3)
    rgb, nrm = shade(f, studio(key=key, fill=0.32, bounce=0.22),
                     ao_radius=26 * scene.S, ao_k=0.95, normal_scale=1.0,
                     normal_smooth=2.6 * scene.S, sky_k=0.24,
                     rim=dict(d=(0.84, -0.24, 0.48), c=tint(scene.SKY_COL, 0.9),
                              k=0.11, p=3.8),
                     bump=parts['relief'] * 7.0 * scene.S + pores * 0.8 * scene.S,
                     bump_k=1.0, edge_turn=5.0 * scene.S * XF[0])
    return rgb, nrm


def shade_hair(W, H, rng, parts, flow=None):
    hair = parts['hair']
    strand = fbm(H, W, 22 * scene.S, rng, 3)
    strand = blur(strand, 2.0 * scene.S)
    rgb, _ = shade(hair, studio(key=1.15, fill=0.30, bounce=0.16),
                   ao_radius=18 * scene.S, ao_k=1.0, normal_scale=1.0,
                   normal_smooth=2.0 * scene.S, sky_k=0.18,
                   rim=dict(d=KEY_DIR, c=tint(KEY_COL, 1.2), k=0.55, p=2.2),
                   bump=strand * 5.0 * scene.S, bump_k=1.0)
    return rgb


def drapery(W, H, rng, mask, colour, *, fold_dir=(0.25, 1.0), fold_scale=34,
            thick=58, key=1.18, mat='linen'):
    """cloth: a slab with folds running down it"""
    X, Y, xx, yy = grids(W, H)
    f = Form(H, W)
    n = fbm(H, W, 120 * scene.S, rng, 4)
    ph = (X * fold_dir[0] + Y * fold_dir[1]) / fold_scale + n * 2.6
    folds = (np.sin(ph) * 0.5 + 0.5) ** 1.3
    folds = folds * 0.82 + fbm(H, W, 46 * scene.S, rng, 3) * 0.18
    mot = _mottle(W, H, rng, 0.05)[..., None]
    alb = np.clip(np.asarray(colour, np.float32)[None, None, :] * mot
                  * (0.70 + 0.62 * folds)[..., None], 0, 1)
    f.slab(mask, thick * scene.S, alb, mat, soft=7 * scene.S, power=0.5)
    f.z += blur(folds, 1.6 * scene.S) * 58 * scene.S * mask
    rgb, _ = shade(f, studio(key=key, fill=0.34, bounce=0.22),
                   ao_radius=16 * scene.S, ao_k=0.95, normal_scale=1.0,
                   normal_smooth=2.0 * scene.S, sky_k=0.28,
                   rim=dict(d=KEY_DIR, c=tint(KEY_COL, 1.0), k=0.35, p=2.4))
    return rgb


# ==========================================================================
# the modelling pass - the part a painter actually does by hand.
# Shaded geometry gives you a lay figure; the picture only comes alive when
# somebody draws the shadow shapes, the halftones and the accents onto it.
# ==========================================================================
class Mod:
    """soft shapes painted over the shaded form: shadow, light, reflection"""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.layers = []

    def _draw(self, kind, col, amt, soft, shapes, width=0):
        im = Image.new('L', (self.W, self.H), 0)
        d = ImageDraw.Draw(im)
        for shp in shapes:
            if shp[0] == 'poly':
                d.polygon([P(*p) for p in shp[1]], fill=255)
            elif shp[0] == 'line':
                d.line([P(*p) for p in shp[1]], fill=255,
                       width=max(1, int(round(sc(shp[2])))), joint='curve')
            elif shp[0] == 'blob':
                (x, y), rx, ry, rot = shp[1], shp[2], shp[3], TR(shp[4])
                n = 28
                th = np.linspace(0, 2 * np.pi, n, endpoint=False)
                ca, sa = np.cos(np.radians(rot)), np.sin(np.radians(rot))
                pts = [(x + (rx * np.cos(t)) * ca - (ry * np.sin(t)) * sa,
                        y + (rx * np.cos(t)) * sa + (ry * np.sin(t)) * ca) for t in th]
                d.polygon([P(*p) for p in pts], fill=255)
        a = blur(np.asarray(im, np.float32) / 255.0, soft * scene.S) * amt
        self.layers.append((kind, np.asarray(col, np.float32), a))

    def shade_(self, col, amt, soft, *shapes):
        self._draw('mul', col, amt, soft, shapes)

    def light_(self, col, amt, soft, *shapes):
        self._draw('over', col, amt, soft, shapes)

    def glow_(self, col, amt, soft, *shapes):
        self._draw('add', col, amt, soft, shapes)

    def apply(self, rgb, mask):
        m = mask.astype(np.float32)
        out = rgb.copy()
        for kind, col, a in self.layers:
            aa = (a * m)[..., None]
            if kind == 'mul':
                out = out * (1 - aa) + out * col[None, None, :] * aa
            elif kind == 'over':
                out = out * (1 - aa) + col[None, None, :] * aa
            else:
                out = out + col[None, None, :] * aa
        return np.clip(out, 0, 1)


SHADOW_WARM = (0.52, 0.335, 0.285)        # multiplicative: warm transparent shadow
SHADOW_DEEP = (0.32, 0.185, 0.165)
HALFTONE = (0.82, 0.74, 0.76)
LIGHT_HOT = mix('lead_white', 5.0, 'naples', 1.5, 'light_red', 0.22, 'cerulean', 0.10)
LIGHT_SOFT = mix('lead_white', 4.0, 'naples', 1.2, 'light_red', 0.8)
REFLECT_C = mix('cerulean', 1.2, 'terre_verte', 0.8, 'lead_white', 1.0)
REFLECT_W = mix('ochre', 1.4, 'light_red', 1.0, 'lead_white', 1.2)


def model_andromeda(W, H):
    """Drawn by hand.  One light, from the upper left and a little in front,
    so the light family runs down her right side (our left) and the shadow
    family down her left.  The terminator is kept crisp where the form turns
    hard and soft where it turns slowly - which is most of the drawing."""
    m = Mod(W, H)
    B = lambda c, rx, ry, rot=0: ('blob', c, rx, ry, rot)
    L = lambda pts, w: ('line', pts, w)
    PO = lambda pts: ('poly', pts)

    # ---------------- the shadow family ----------------
    m.shade_(SHADOW_WARM, 0.92, 7, PO([
        (1296, 1130), (1352, 1180), (1392, 1250), (1398, 1330), (1386, 1420),
        (1390, 1500), (1420, 1560), (1444, 1650), (1452, 1760), (1442, 1880),
        (1428, 1990), (1412, 2055), (1366, 2052), (1374, 1930), (1378, 1800),
        (1366, 1680), (1348, 1560), (1340, 1440), (1344, 1330), (1330, 1230),
        (1300, 1170)]))
    # the core of it, deeper and tighter
    m.shade_(SHADOW_DEEP, 0.50, 5, PO([
        (1352, 1240), (1392, 1300), (1392, 1400), (1386, 1490), (1416, 1570),
        (1444, 1680), (1448, 1800), (1436, 1920), (1420, 2020), (1392, 2020),
        (1402, 1900), (1404, 1770), (1388, 1650), (1370, 1530), (1366, 1400),
        (1362, 1300)]))
    # the arms
    m.shade_(SHADOW_WARM, 0.72, 6, PO([
        (1400, 1200), (1444, 1140), (1472, 1060), (1470, 1000), (1442, 960),
        (1414, 980), (1428, 1040), (1416, 1110), (1376, 1180)]))
    m.shade_(SHADOW_WARM, 0.55, 6, PO([
        (1182, 1180), (1156, 1100), (1142, 1020), (1152, 980), (1178, 996),
        (1172, 1060), (1186, 1130), (1212, 1182)]))
    m.shade_(SHADOW_WARM, 0.60, 5, PO([
        (1452, 1000), (1420, 940), (1392, 892), (1374, 868), (1392, 856),
        (1416, 902), (1446, 960), (1468, 1004)]))

    # ---------------- cast shadows and the places form meets form ----------
    m.shade_(SHADOW_DEEP, 0.72, 5, B((1252, 1134), 42, 17, -10))      # chin on the neck
    m.shade_(SHADOW_WARM, 0.58, 6, B((1298, 1168), 30, 20, 20))       # neck into the pit
    m.shade_(SHADOW_DEEP, 0.52, 6, B((1216, 1208), 44, 16, -8))       # hair on the shoulder
    m.shade_(SHADOW_WARM, 0.46, 7, B((1176, 1270), 26, 40, -12))
    m.shade_(SHADOW_DEEP, 0.80, 4, B((1212, 1330), 40, 13, -16))      # under the breasts
    m.shade_(SHADOW_DEEP, 0.74, 4, B((1324, 1318), 38, 12, 14))
    m.shade_(SHADOW_WARM, 0.52, 5, B((1194, 1300), 15, 22, -24))      # their far sides
    m.shade_(SHADOW_WARM, 0.60, 6, B((1186, 1236), 30, 22, 24))       # armpits
    m.shade_(SHADOW_WARM, 0.60, 6, B((1382, 1240), 30, 22, -24))
    m.shade_(SHADOW_WARM, 0.40, 7, B((1256, 1394), 46, 18, -4))       # the rib arch
    m.shade_(SHADOW_WARM, 0.40, 7, B((1346, 1386), 40, 16, 6))
    m.shade_(SHADOW_DEEP, 0.55, 3, B((1304, 1450), 8, 7, 0))          # the navel
    m.shade_(SHADOW_WARM, 0.46, 7, B((1300, 1492), 70, 16, -3))       # under the belly
    m.shade_(SHADOW_DEEP, 0.66, 8, B((1318, 1556), 46, 34, 0))        # the groin
    m.shade_(SHADOW_WARM, 0.62, 9, B((1318, 1700), 30, 140, -2))      # between the thighs
    m.shade_(SHADOW_WARM, 0.48, 6, B((1252, 1552), 24, 30, 16))       # the inguinal folds
    m.shade_(SHADOW_WARM, 0.48, 6, B((1372, 1540), 24, 30, -16))
    m.shade_(SHADOW_WARM, 0.52, 6, B((1234, 1846), 32, 20, 0))        # behind the knees
    m.shade_(SHADOW_WARM, 0.52, 6, B((1404, 1838), 32, 20, 0))
    m.shade_(SHADOW_WARM, 0.40, 5, B((1246, 1792), 22, 12, -8))       # above the kneecaps
    m.shade_(SHADOW_WARM, 0.40, 5, B((1392, 1786), 22, 12, 8))
    m.shade_(SHADOW_DEEP, 0.52, 5, B((1240, 2062), 40, 11, -6))       # under the feet
    m.shade_(SHADOW_DEEP, 0.52, 5, B((1430, 2068), 42, 11, -6))
    m.shade_(SHADOW_WARM, 0.46, 5, B((1258, 1004), 40, 16, -18))      # hair across the brow
    m.shade_(SHADOW_WARM, 0.34, 6, B((1292, 1058), 20, 28, -14))      # the far cheek

    # ---------------- the light family ----------------
    m.light_(LIGHT_HOT, 0.36, 5, B((1228, 992), 21, 11, -26))         # the forehead
    m.light_(LIGHT_HOT, 0.28, 4, B((1222, 1040), 11, 8, -20))         # the cheekbone
    m.light_(LIGHT_HOT, 0.24, 3, B((1240, 1056), 5, 7, -14))          # the bridge
    m.light_(LIGHT_SOFT, 0.38, 5, B((1234, 1198), 36, 9, -5))         # the collarbone
    m.light_(LIGHT_SOFT, 0.30, 5, B((1194, 1216), 22, 14, -22))       # the shoulder cap
    m.light_(LIGHT_SOFT, 0.56, 6, B((1194, 1282), 23, 25, -24))       # the near breast
    m.light_(LIGHT_SOFT, 0.26, 6, B((1304, 1270), 20, 21, 16))
    m.light_(LIGHT_SOFT, 0.34, 8, B((1262, 1348), 40, 48, -5))        # the ribs in front
    m.light_(LIGHT_SOFT, 0.30, 9, B((1278, 1464), 38, 34, -4))        # the belly
    m.light_(LIGHT_SOFT, 0.26, 8, B((1242, 1524), 34, 24, -8))        # the hip plane
    m.light_(LIGHT_SOFT, 0.34, 10, B((1250, 1640), 32, 80, -4))       # the near thigh
    m.light_(LIGHT_SOFT, 0.22, 9, B((1366, 1630), 26, 76, 4))
    m.light_(LIGHT_HOT, 0.30, 4, B((1232, 1800), 15, 10, 0))          # the kneecaps
    m.light_(LIGHT_HOT, 0.24, 4, B((1406, 1792), 14, 10, 0))
    m.light_(LIGHT_SOFT, 0.36, 7, B((1244, 1912), 20, 58, -3))        # the shin crests
    m.light_(LIGHT_SOFT, 0.22, 7, B((1392, 1908), 17, 54, 2))
    m.light_(LIGHT_SOFT, 0.34, 6, B((1156, 1096), 16, 62, 14))        # the near arm
    m.light_(LIGHT_SOFT, 0.34, 6, B((1160, 930), 14, 52, -28))
    m.light_(LIGHT_SOFT, 0.20, 6, B((1424, 1104), 14, 58, -12))
    m.light_(LIGHT_SOFT, 0.20, 6, B((1410, 940), 13, 48, 32))
    m.light_(LIGHT_HOT, 0.26, 4, B((1222, 800), 14, 14, 0))           # the hands
    m.light_(LIGHT_HOT, 0.20, 4, B((1372, 826), 13, 13, 0))

    # ---------------- reflected light ----------------
    # cool off the sky down her shadow contour, warm off the lit rock low down
    m.glow_(REFLECT_C, 0.26, 5, L([(1400, 1230), (1420, 1330), (1414, 1430)], 11))
    m.glow_(REFLECT_C, 0.22, 5, L([(1452, 1620), (1460, 1740), (1450, 1860)], 11))
    m.glow_(REFLECT_W, 0.30, 7, L([(1424, 1900), (1432, 2010)], 15))
    m.glow_(REFLECT_W, 0.26, 7, L([(1352, 1930), (1322, 2000)], 14))
    m.glow_(REFLECT_W, 0.20, 8, L([(1352, 1560), (1366, 1680)], 14))
    m.glow_(REFLECT_C, 0.18, 5, L([(1452, 1020), (1468, 1110)], 10))
    return m


# ==========================================================================
# PERSEUS - coming down the diagonal out of the broken sky, harpe raised,
# the Gorgon's bag at his hip and the cloak dragging behind him.
# Lit from above and behind, so he reads as a dark, rimmed silhouette
# against the break: Andromeda stays the brightest thing in the picture.
# ==========================================================================
P_HEAD_C, P_HEAD_R, P_HEAD_ROT = (886, 1006), (37, 45, 39), 26


def perseus(W, H, rng):
    f = Form(H, W)
    mot = _mottle(W, H, rng, 0.05)[..., None]

    def A(c, k=1.0):
        return np.clip(np.asarray(c, np.float32)[None, None, :] * mot * k, 0, 1)

    sk, skw, skc = A(FLESH_M), A(FLESH_M_WARM), A(FLESH_M_COOL)
    B = 0.055 / scene.S

    def T(pts, alb=sk, mat='skin', zk=0.86):
        f.tube(TP(pts), alb, mat, zk=zk, blendk=B)

    def ell(c, r, alb=sk, mat='skin', zk=1.0, **kw):
        return f.ellipsoid(P(*c), (sc(r[0]), sc(r[1]), sc(r[2])), alb, mat,
                           blendk=B, zk=zk, **kw)

    def sph(c, r, alb=sk, mat='skin', zk=0.85, **kw):
        return f.sphere(P(*c), sc(r), alb, mat, blendk=B, zk=zk, **kw)

    hl = local(P_HEAD_C, P_HEAD_ROT)

    # ---- legs, trailing back and up to the left ----
    T([(734, 1206, 46), (686, 1200, 42), (640, 1192, 34), (596, 1184, 26),
       (556, 1180, 20), (522, 1176, 15), (500, 1174, 11)], skc)     # his right leg
    T([(500, 1174, 11), (476, 1184, 11), (452, 1194, 8)], skw)      # foot
    T([(736, 1236, 47), (690, 1254, 43), (644, 1276, 34), (606, 1296, 27),
       (610, 1330, 25), (628, 1366, 20), (648, 1400, 15), (660, 1422, 11)],
      skc)                                                          # his left, bent
    T([(660, 1422, 11), (682, 1436, 11), (702, 1446, 8)], skw)

    # ---- torso along the dive ----
    T([(846, 1068, 56), (810, 1104, 60), (776, 1142, 57), (744, 1180, 50),
       (724, 1216, 52), (716, 1244, 46)], sk, zk=0.84)
    sph((866, 1056), 34, sk, zk=0.7)                                # deltoids
    sph((826, 1126), 33, sk, zk=0.7)
    T([(852, 1058, 21), (868, 1046, 20), (880, 1036, 19)], skc)      # neck
    ell(P_HEAD_C, P_HEAD_R, sk, rot=TR(P_HEAD_ROT), zk=0.95)
    sph(hl(0, 36), 12, skw, zk=0.45)                                # chin
    T([(hl(-20, 20)[0], hl(-20, 20)[1], 11), (hl(-2, 32)[0], hl(-2, 32)[1], 11),
       (hl(20, 18)[0], hl(20, 18)[1], 11)], sk, zk=0.22)            # jaw
    T([(hl(-3, 2)[0], hl(-3, 2)[1], 4), (hl(-5, 12)[0], hl(-5, 12)[1], 5),
       (hl(-6, 19)[0], hl(-6, 19)[1], 5)], skw, zk=0.75)            # nose
    sph(hl(26, 2), 8, skc, zk=0.35)

    # ---- arms ----
    T([(876, 1054, 32), (912, 1010, 28), (946, 968, 24), (964, 938, 20),
       (968, 918, 16)], sk)                                         # sword arm
    T([(968, 918, 16), (982, 902, 15), (996, 890, 12)], skw)        # fist on the hilt
    T([(834, 1118, 32), (876, 1146, 28), (918, 1172, 24), (946, 1188, 19),
       (962, 1196, 15)], skc)                                       # shield arm
    T([(962, 1196, 15), (978, 1200, 14), (992, 1202, 11)], skw)

    f.smooth_z(4.0 * scene.S)
    sph((790, 1118), 26, sk, zk=0.45)                               # pectoral
    sph((762, 1152), 24, sk, zk=0.42)
    f.smooth_z(1.4 * scene.S)
    skin = f.mask.copy()

    face_alb, face_rel = face(W, H, TX(*P_HEAD_C), P_HEAD_R, P_HEAD_ROT, skin, fs=XF[0],
                              dark=mix('ivory_black', 2.0, 'burnt_umber', 1.0),
                              lip=mix('light_red', 1.6, 'burnt_sienna', 1.0,
                                      'lead_white', 1.0),
                              male=True, mid=-4.0, eye_v=2.0)
    a4 = face_alb[..., 3:4]
    f.alb = f.alb * (1 - a4) + face_alb[..., :3] * a4

    # ---- hair: short dark curls, blown back ----
    hair = Form(H, W)
    hcol = np.asarray(mix('ivory_black', 2.0, 'burnt_umber', 1.4, 'burnt_sienna', 0.5),
                      np.float32)
    hb = 0.08 / scene.S
    hair.ellipsoid(P(*hl(-2, -20)), (sc(38), sc(29), sc(32)), hcol, 'hair',
                   rot=TR(P_HEAD_ROT), blendk=hb, zk=0.75)
    for pts in ([(872, 976, 16), (854, 976, 14), (838, 982, 10), (826, 990, 6)],
                [(866, 1000, 13), (848, 1008, 10), (836, 1016, 6)]):
        hair.tube(TP(pts), hcol, 'hair', zk=0.8, blendk=hb)
    hair.smooth_z(3.0 * scene.S)
    ca, sa = np.cos(np.radians(TR(P_HEAD_ROT))), np.sin(np.radians(TR(P_HEAD_ROT)))
    X, Y, _, _ = grids(W, H)
    pcx, pcy = TX(*P_HEAD_C)
    du, dv = (X - pcx) / XF[0], (Y - pcy) / XF[0]
    uu, vv = du * ca + dv * sa, -du * sa + dv * ca
    face_oval = (uu / 32.0) ** 2 + ((vv - 10) / 34.0) ** 2 < 1.0
    hair_mask = hair.mask & ~face_oval

    # ---- the cloak, dragging up and to the left ----
    from scene import poly_mask
    cloak_poly = [
        [(884, 1012), (830, 974), (756, 948), (676, 940), (594, 948), (512, 970),
         (436, 1008), (376, 1060), (338, 1124), (316, 1192), (362, 1206),
         (398, 1136), (446, 1078), (510, 1036), (584, 1012), (664, 1004),
         (744, 1012), (818, 1034), (872, 1060)],
        [(856, 1064), (778, 1080), (698, 1106), (624, 1144), (558, 1192),
         (504, 1248), (464, 1312), (436, 1382), (482, 1392), (514, 1320),
         (562, 1256), (624, 1202), (698, 1160), (776, 1126), (844, 1104)],
        [(372, 1092), (306, 1118), (252, 1158), (220, 1208), (256, 1222),
         (298, 1176), (352, 1134)]]
    cloak = poly_mask(W, H, TPoly(cloak_poly), rng, jag=16, scale=120) & ~skin

    # ---- harpe and shield ----
    gear = Form(H, W)
    gb = 0.09 / scene.S
    stl = np.asarray(STEEL, np.float32)
    brz = np.asarray(BRONZE, np.float32)
    # the hooked blade
    gear.tube(TP([(1000, 884, 13), (1034, 842, 14), (1070, 798, 14), (1106, 754, 13),
                  (1140, 712, 11), (1168, 678, 8)]), stl, 'steel', zk=0.45, blendk=gb)
    gear.tube(TP([(1086, 772, 11), (1124, 766, 12), (1158, 780, 10), (1178, 806, 7),
                  (1182, 834, 5)]), stl, 'steel', zk=0.45, blendk=gb)   # the hook
    gear.tube(TP([(974, 906, 7), (992, 886, 8), (1006, 872, 7)]), brz, 'bronze',
              zk=0.6, blendk=gb)                                    # grip
    gear.capsule(P(962, 918), P(1012, 866), sc(13), sc(13), brz, 'bronze',
                 zk=0.35, blendk=gb)                                # guard
    gear.ellipsoid(P(988, 1192), (sc(62), sc(86), sc(27)),
                   np.asarray(tint(BRONZE, 0.80), np.float32), 'bronze',
                   rot=TR(-24), zk=1.0, blendk=gb)
    gear.ellipsoid(P(988, 1192), (sc(50), sc(72), sc(22)),
                   np.asarray(tint(BRONZE, 0.95), np.float32), 'bronze',
                   rot=TR(-24), zk=0.9, blendk=gb, zoff=sc(5))
    gear.sphere(P(988, 1192), sc(13), np.asarray(tint(BRONZE, 1.3), np.float32),
                'bronze', zk=1.0, blendk=gb, zoff=sc(16))
    gear.smooth_z(1.6 * scene.S)
    gear_mask = gear.mask & ~skin

    return dict(form=f, skin=skin, relief=r_perseus(W, H) , hair=hair,
                hair_mask=hair_mask, cloak=cloak, gear=gear,
                gear_mask=gear_mask)


def r_perseus(W, H):
    r = Relief(W, H)
    r.line([(844, 1066), (812, 1092), (790, 1112)], 9, 0.22)     # clavicle
    r.line([(818, 1126), (790, 1150), (770, 1166)], 9, 0.18)
    r.line([(790, 1120), (762, 1154), (738, 1184)], 8, 0.16)     # sternum line
    r.line([(764, 1164), (740, 1196)], 10, -0.18)                # under the pectorals
    r.line([(748, 1176), (726, 1208)], 9, 0.14)
    r.blob((736, 1196), 6, -0.35)                                # navel
    return r.field(4.0)


def shade_perseus(W, H, rng, parts, key=0.80):
    f = parts['form']
    rgb, _ = shade(f, studio(key=key, fill=0.30, bounce=0.14),
                   ao_radius=20 * scene.S, ao_k=0.95, normal_scale=1.0,
                   normal_smooth=2.2 * scene.S, sky_k=0.30,
                   rim=dict(d=(-0.62, -0.60, 0.50), c=tint(KEY_COL, 1.35), k=0.95, p=2.0),
                   bump=parts['relief'] * 7.0 * scene.S, bump_k=1.0,
                   edge_turn=4.0 * scene.S * XF[0])
    return rgb


def model_perseus(W, H):
    """He is against the light.  Almost all of him is in shadow; the drawing
    is done by the warm edge running along his back, shoulder and sword arm."""
    m = Mod(W, H)
    B = lambda c, rx, ry, rot=0: ('blob', c, rx, ry, rot)
    L = lambda pts, w: ('line', pts, w)
    PO = lambda pts: ('poly', pts)

    # the whole figure comes down a key first
    m.shade_((0.66, 0.56, 0.56), 0.88, 3, B((740, 1180), 460, 330, 0))
    # then the front of him goes further down
    m.shade_(SHADOW_WARM, 0.72, 7, PO([
        (896, 1034), (918, 1070), (884, 1108), (840, 1148), (796, 1190),
        (760, 1226), (736, 1262), (694, 1268), (704, 1216), (740, 1168),
        (782, 1126), (826, 1082), (868, 1050)]))
    m.shade_(SHADOW_DEEP, 0.44, 6, B((796, 1176), 40, 26, -42))
    m.shade_(SHADOW_DEEP, 0.60, 5, B((900, 1046), 26, 15, 22))      # chin on the chest
    m.shade_(SHADOW_WARM, 0.55, 7, B((944, 1180), 38, 28, -22))     # the shield's shadow
    m.shade_(SHADOW_DEEP, 0.48, 7, B((726, 1236), 38, 24, -12))     # the hip crease
    m.shade_(SHADOW_WARM, 0.46, 6, B((650, 1206), 56, 15, 3))       # under the trailing leg
    m.shade_(SHADOW_WARM, 0.46, 6, B((640, 1292), 52, 14, 14))
    m.shade_(SHADOW_WARM, 0.40, 5, B((612, 1332), 20, 26, 20))      # behind the bent knee

    # the light that describes him: a warm edge along back, shoulder, arm
    m.light_(LIGHT_HOT, 0.55, 4, L([(866, 974), (892, 992), (906, 1016)], 9))
    m.light_(LIGHT_HOT, 0.62, 5, L([(852, 1040), (826, 1072), (800, 1100)], 12))
    m.light_(LIGHT_SOFT, 0.50, 6, L([(800, 1098), (768, 1134), (740, 1172)], 13))
    m.light_(LIGHT_SOFT, 0.44, 6, L([(740, 1172), (718, 1206), (710, 1238)], 12))
    m.light_(LIGHT_HOT, 0.46, 4, L([(880, 1048), (912, 1008), (944, 968)], 10))
    m.light_(LIGHT_HOT, 0.40, 4, L([(944, 968), (966, 936), (982, 906)], 9))
    m.light_(LIGHT_SOFT, 0.38, 5, L([(718, 1200), (660, 1192), (600, 1184)], 11))
    m.light_(LIGHT_SOFT, 0.32, 5, L([(560, 1182), (524, 1180), (496, 1178)], 9))
    m.light_(LIGHT_SOFT, 0.34, 5, L([(726, 1250), (672, 1266), (618, 1286)], 11))
    m.light_(LIGHT_SOFT, 0.28, 5, L([(600, 1300), (610, 1340), (634, 1382)], 9))
    m.light_(LIGHT_HOT, 0.34, 4, B((870, 980), 18, 11, 24))         # the top of the head
    m.light_(LIGHT_SOFT, 0.30, 5, B((790, 1116), 22, 15, -42))      # the back plane
    m.light_(LIGHT_SOFT, 0.24, 5, B((756, 1158), 20, 14, -42))

    # the trailing legs
    m.shade_(SHADOW_WARM, 0.50, 6, PO([
        (700, 1226), (650, 1222), (596, 1212), (548, 1204), (510, 1198),
        (502, 1180), (548, 1188), (600, 1196), (652, 1206), (702, 1210)]))
    m.shade_(SHADOW_WARM, 0.50, 6, PO([
        (706, 1272), (658, 1290), (612, 1308), (592, 1340), (608, 1382),
        (632, 1414), (612, 1418), (586, 1382), (572, 1336), (590, 1292),
        (646, 1268), (700, 1250)]))
    m.light_(LIGHT_SOFT, 0.34, 5, B((644, 1192), 58, 10, 2))
    m.light_(LIGHT_SOFT, 0.26, 5, B((648, 1272), 54, 9, 12))
    m.light_(LIGHT_SOFT, 0.22, 4, B((616, 1350), 9, 30, 10))
    m.shade_(SHADOW_DEEP, 0.36, 4, B((520, 1196), 26, 8, 4))

    # reflected: cool off the sky into his shadow side, warm off the water
    m.glow_(REFLECT_C, 0.30, 6, L([(876, 1086), (832, 1138), (786, 1186)], 11))
    m.glow_(REFLECT_W, 0.26, 7, L([(744, 1232), (702, 1256)], 13))
    m.glow_(REFLECT_W, 0.20, 6, L([(640, 1300), (600, 1310)], 11))
    return m


# ==========================================================================
# CETUS - the sea monster.  It comes out of the water in the lower left on a
# long neck, jaws open, so the line of its back carries the eye up the
# diagonal to Perseus.  Kept dark and cold: it is the picture's bass note.
# ==========================================================================
SCALE_DK = mix('viridian', 1.2, 'burnt_umber', 2.0, 'ivory_black', 7.0, 'lead_white', 0.10)
SCALE_LT = mix('terre_verte', 1.6, 'ochre', 0.9, 'burnt_umber', 1.8, 'ivory_black', 1.0, 'lead_white', 0.40)
BELLY = mix('ochre', 1.3, 'lead_white', 1.5, 'burnt_umber', 1.0, 'terre_verte', 0.5)
MAW = mix('madder', 1.6, 'burnt_umber', 1.4, 'vandyke', 1.0)
TOOTH = mix('lead_white', 1.9, 'naples', 1.3, 'raw_umber', 0.7)


def cetus(W, H, rng):
    f = Form(H, W)
    mot = _mottle(W, H, rng, 0.10, 30)[..., None]
    scl = np.clip(np.asarray(SCALE_DK, np.float32)[None, None, :] * mot, 0, 1)
    sclL = np.clip(np.asarray(SCALE_LT, np.float32)[None, None, :] * mot, 0, 1)
    belly = np.clip(np.asarray(BELLY, np.float32)[None, None, :] * mot, 0, 1)
    B = 0.04 / scene.S

    def T(pts, alb=scl, mat='scale', zk=0.9):
        f.tube(TP(pts), alb, mat, zk=zk, blendk=B)

    # ---- the body: out of the water on the left, up into a rearing neck ----
    T([(150, 2430, 120), (300, 2372, 128), (450, 2300, 126), (560, 2214, 116),
       (632, 2110, 104), (684, 2000, 92), (716, 1902, 80), (748, 1816, 70),
       (790, 1746, 62), (836, 1694, 56)], scl, zk=0.92)
    # a coil breaking the surface further out
    T([(830, 2420, 74), (930, 2372, 78), (1030, 2352, 72), (1120, 2366, 62),
       (1186, 2410, 50)], scl, zk=0.9)
    T([(214, 2214, 56), (300, 2168, 62), (392, 2156, 58), (474, 2178, 46),
       (520, 2220, 34)], scl, zk=0.9)

    # ---- the head: heavy skull, deep jaw ----
    T([(828, 1704, 62), (862, 1652, 62), (898, 1608, 58), (944, 1578, 50)], scl)
    T([(944, 1576, 48), (1000, 1548, 40), (1056, 1522, 31), (1104, 1500, 22),
       (1138, 1486, 13)], scl)                                   # upper jaw
    T([(898, 1656, 42), (952, 1680, 36), (1010, 1700, 29), (1062, 1716, 21),
       (1098, 1726, 12)], sclL)                                  # lower jaw, dropped
    f.ellipsoid(P(982, 1626), (sc(78), sc(38), sc(18)),
                np.asarray(MAW, np.float32), 'scale', rot=TR(-18), zk=0.5, blendk=B)
    f.sphere(P(884, 1596), sc(28), sclL, 'scale', zk=0.7, blendk=B)   # brow
    f.smooth_z(3.0 * scene.S)
    # horns and the dorsal comb, set on after the thumb so they stay sharp
    for a, b_, r0, r1 in (((876, 1570), (842, 1492), 15, 3),
                          ((916, 1562), (906, 1486), 13, 3),
                          ((844, 1606), (776, 1556), 12, 3),
                          ((862, 1640), (800, 1636), 10, 3)):
        f.capsule(P(*a), P(*b_), sc(r0), sc(r1), sclL, 'horn', zk=0.6, blendk=0.3 / scene.S)
    spines = [((816, 1706), (778, 1618)), ((782, 1768), (726, 1698)),
              ((748, 1836), (680, 1782)), ((716, 1906), (644, 1866)),
              ((684, 1994), (606, 1970)), ((644, 2088), (564, 2082)),
              ((582, 2186), (502, 2202)), ((494, 2278), (416, 2312)),
              ((374, 2350), (296, 2398))]
    for a, b_ in spines:
        f.capsule(P(*a), P(*b_), sc(21), sc(3), sclL, 'horn', zk=0.62,
                  blendk=0.3 / scene.S)

    # ---- teeth ----
    teeth = Form(H, W)
    tcol = np.asarray(TOOTH, np.float32)
    for i, (t, L) in enumerate([(0.03, 34), (0.18, 27), (0.33, 30), (0.50, 22),
                                (0.66, 17), (0.82, 12)]):
        x = 952 + t * 180
        y = 1572 - t * 76 + 14
        teeth.capsule(P(x, y), P(x + 5, y + L), sc(6.5 - 3.4 * t), sc(1.2),
                      tcol, 'horn', zk=0.5, blendk=0.2 / scene.S)
    for i, (t, L) in enumerate([(0.08, 28), (0.26, 23), (0.45, 19), (0.64, 14),
                                (0.82, 10)]):
        x = 946 + t * 158
        y = 1670 + t * 50
        teeth.capsule(P(x, y), P(x + 3, y - L), sc(6.0 - 3.0 * t), sc(1.2),
                      tcol, 'horn', zk=0.5, blendk=0.2 / scene.S)
    teeth_mask = teeth.mask

    # ---- the eye ----
    eye = Form(H, W)
    eye.sphere(P(890, 1588), sc(15), np.asarray(
        mix('naples', 2.2, 'ochre', 1.4, 'vermilion', 0.35), np.float32), 'scale',
        zk=1.0, blendk=0.3 / scene.S)
    eye.capsule(P(890, 1578), P(890, 1598), sc(3.6), sc(3.6),
                np.asarray((0.05, 0.045, 0.04), np.float32), 'scale', zk=1.0,
                zoff=sc(16))
    eye_mask = eye.mask

    return dict(form=f, mask=f.mask.copy(), teeth=teeth, teeth_mask=teeth_mask,
                eye=eye, eye_mask=eye_mask)


def shade_cetus(W, H, rng, parts):
    f = parts['form']
    scales = fbm(H, W, 26 * scene.S, rng, 2, ridged=True)
    rgb, _ = shade(f, studio(key=0.72, fill=0.20, bounce=0.24),
                   ao_radius=30 * scene.S, ao_k=1.0, normal_scale=1.0,
                   normal_smooth=2.6 * scene.S, sky_k=0.30,
                   rim=dict(d=KEY_DIR, c=tint(KEY_COL, 1.1), k=0.75, p=2.4),
                   bump=scales * 3.5 * scene.S, bump_k=1.0,
                   edge_turn=5.0 * scene.S * XF[0])
    return rgb
