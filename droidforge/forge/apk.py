"""APK packaging (aligned zip) and APK Signature Scheme v2 signing + verification.

Zip layout follows PKWARE APPNOTE; the signing block and digests follow the
Android "APK Signature Scheme v2" specification.
"""
import datetime
import hashlib
import os
import struct
import zlib

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

DOS_TIME = (0 << 11) | (0 << 5) | 0
DOS_DATE = ((2026 - 1980) << 9) | (1 << 5) | 1
ALIGN_EXTRA_ID = 0xD935


# ------------------------------------------------------------------ zip
def build_zip(entries):
    """entries: list of (name, data, store: bool, align: int).
    Stored entries get their data aligned to `align` bytes (zipalign)."""
    out = bytearray()
    central = bytearray()
    for (name, data, store, align) in entries:
        nb = name.encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        if store:
            comp = data
            method = 0
        else:
            co = zlib.compressobj(9, zlib.DEFLATED, -15)
            comp = co.compress(data) + co.flush()
            method = 8
        offset = len(out)
        extra = b""
        if store and align > 1:
            base = offset + 30 + len(nb)
            pad = (-(base + 6)) % align
            extra = struct.pack("<HHH", ALIGN_EXTRA_ID, 2 + pad, align) + b"\0" * pad
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0800, method, DOS_TIME, DOS_DATE, crc,
                           len(comp), len(data), len(nb), len(extra)) + nb + extra
        if store and align > 1:
            assert len(out) % align == 0
        out += comp
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0800, method, DOS_TIME, DOS_DATE,
                               crc, len(comp), len(data), len(nb), 0, 0, 0, 0, 0, offset) + nb
    cd_off = len(out)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries), len(central), cd_off, 0)
    return bytes(out)


def zip_sections(z):
    """-> (cd_offset, eocd_offset)"""
    eocd = z.rfind(b"PK\x05\x06", max(0, len(z) - 65557))
    if eocd < 0:
        raise ValueError("EOCD not found")
    (cd_size, cd_off) = struct.unpack_from("<II", z, eocd + 12)
    if cd_off + cd_size != eocd:
        raise ValueError("central directory not immediately before EOCD")
    return cd_off, eocd


# ------------------------------------------------------------------ keys
def load_or_create_key(keydir, cn="DroidForge Developer"):
    os.makedirs(keydir, exist_ok=True)
    kp = os.path.join(keydir, "release-key.pem")
    cp = os.path.join(keydir, "release-cert.der")
    if os.path.exists(kp) and os.path.exists(cp):
        key = serialization.load_pem_private_key(open(kp, "rb").read(), None)
        return key, open(cp, "rb").read()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365 * 30))
            .sign(key, hashes.SHA256()))
    open(kp, "wb").write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    os.chmod(kp, 0o600)
    der = cert.public_bytes(serialization.Encoding.DER)
    open(cp, "wb").write(der)
    return key, der


# ------------------------------------------------------------------ v2 signing
SIG_RSA_PKCS1_SHA256 = 0x0103
V2_BLOCK_ID = 0x7109871A
VERITY_PADDING_ID = 0x42726577
CHUNK = 1024 * 1024


def lp(b):
    return struct.pack("<I", len(b)) + b


def lp_seq(items):
    return lp(b"".join(lp(i) for i in items))


def chunked_sha256(sections):
    digests = []
    for sec in sections:
        for i in range(0, len(sec), CHUNK):
            c = sec[i:i + CHUNK]
            digests.append(hashlib.sha256(b"\xa5" + struct.pack("<I", len(c)) + c).digest())
    return hashlib.sha256(b"\x5a" + struct.pack("<I", len(digests)) + b"".join(digests)).digest()


def sign_v2(z, key, cert_der):
    cd_off, eocd_off = zip_sections(z)
    contents, cd, eocd = z[:cd_off], z[cd_off:eocd_off], z[eocd_off:]
    digest = chunked_sha256([contents, cd, eocd])  # EOCD already points at cd_off == block start
    signed_data = (lp_seq([struct.pack("<I", SIG_RSA_PKCS1_SHA256) + lp(digest)])
                   + lp_seq([cert_der])
                   + lp(b""))
    sig = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    pub = key.public_key().public_bytes(serialization.Encoding.DER,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    signer = lp(signed_data) + lp_seq([struct.pack("<I", SIG_RSA_PKCS1_SHA256) + lp(sig)]) + lp(pub)
    v2_value = lp_seq([signer])

    def pair(pid, value):
        return struct.pack("<QI", 4 + len(value), pid) + value

    pairs = pair(V2_BLOCK_ID, v2_value)
    # pad the whole block to a multiple of 4096 like apksigner (verity padding pair)
    block_len = 8 + len(pairs) + 8 + 16
    if block_len % 4096:
        pad = 4096 - (block_len % 4096)
        if pad < 12:
            pad += 4096
        pairs += pair(VERITY_PADDING_ID, b"\0" * (pad - 12))
    size = len(pairs) + 8 + 16
    block = struct.pack("<Q", size) + pairs + struct.pack("<Q", size) + b"APK Sig Block 42"
    new_eocd = bytearray(eocd)
    struct.pack_into("<I", new_eocd, 16, cd_off + len(block))
    return contents + block + cd + bytes(new_eocd)


def verify_v2(apk):
    """Independent verification following the spec.  Returns a report dict; raises on failure."""
    cd_off, eocd_off = zip_sections(apk)
    if apk[cd_off - 16:cd_off] != b"APK Sig Block 42":
        raise ValueError("no APK Signing Block")
    (size2,) = struct.unpack_from("<Q", apk, cd_off - 24)
    block_start = cd_off - size2 - 8
    (size1,) = struct.unpack_from("<Q", apk, block_start)
    if size1 != size2:
        raise ValueError("signing block size fields differ")
    p = block_start + 8
    end = cd_off - 24
    v2 = None
    while p < end:
        (ln, pid) = struct.unpack_from("<QI", apk, p)
        if pid == V2_BLOCK_ID:
            v2 = apk[p + 12:p + 8 + ln]
        p += 8 + ln
    if v2 is None:
        raise ValueError("no v2 block")

    def rd(b, o):
        (n,) = struct.unpack_from("<I", b, o)
        return b[o + 4:o + 4 + n], o + 4 + n

    signers, _ = rd(v2, 0)
    signer, _ = rd(signers, 0)
    signed_data, o = rd(signer, 0)
    sigs, o = rd(signer, o)
    pub_der, o = rd(signer, o)
    s1, _ = rd(sigs, 0)
    (alg,) = struct.unpack_from("<I", s1, 0)
    sig, _ = rd(s1, 4)
    pub = serialization.load_der_public_key(pub_der)
    pub.verify(sig, signed_data, padding.PKCS1v15(), hashes.SHA256())
    digests, o = rd(signed_data, 0)
    certs, o = rd(signed_data, o)
    d1, _ = rd(digests, 0)
    (dalg,) = struct.unpack_from("<I", d1, 0)
    want, _ = rd(d1, 4)
    cert_der, _ = rd(certs, 0)
    cert = x509.load_der_x509_certificate(cert_der)
    if cert.public_key().public_bytes(serialization.Encoding.DER,
                                      serialization.PublicFormat.SubjectPublicKeyInfo) != pub_der:
        raise ValueError("certificate public key != signer public key")
    eocd = bytearray(apk[eocd_off:])
    struct.pack_into("<I", eocd, 16, block_start)
    got = chunked_sha256([apk[:block_start], apk[cd_off:eocd_off], bytes(eocd)])
    if got != want:
        raise ValueError("content digest mismatch")
    return {"algorithm": hex(alg), "digest": got.hex(), "cert": cert.subject.rfc4514_string(),
            "cert_sha256": hashlib.sha256(cert_der).hexdigest()}
