#!/usr/bin/env python3
"""
onionfetch - fetch pages over Tor and archive them with provenance.

Runs on YOUR machine (Linux, macOS, or Android/Termux), against a local
Tor SOCKS proxy. Fetches only URLs you list explicitly: it does not crawl,
does not follow links, and does not discover addresses.

Setup
-----
  Termux (Android):   pkg install tor python && pip install 'requests[socks]'
  Debian/Ubuntu:      sudo apt install tor && pip install 'requests[socks]'
  macOS:              brew install tor && pip install 'requests[socks]'

Start Tor in another session, then wait for "Bootstrapped 100%":
  tor                        # Termux / foreground
  sudo systemctl start tor   # systemd

Usage
-----
  ./onionfetch.py --check
  ./onionfetch.py -o out/ https://example.org/ http://<addr>.onion/page
  ./onionfetch.py -o out/ --urls targets.txt --delay 5
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.parse

try:
    import requests
except ImportError:
    sys.exit("missing dependency: pip install 'requests[socks]'")

SOCKS_DEFAULT = "socks5h://127.0.0.1:9050"  # 'h' => resolve DNS at the proxy
ONION_V3 = re.compile(r"^[a-z2-7]{56}\.onion$", re.I)
CHUNK = 64 * 1024


def build_session(socks: str, retries: int) -> requests.Session:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    s.proxies = {"http": socks, "https": socks}
    # Tor Browser's UA reduces how much you stand out; still not anonymity.
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    policy = Retry(
        total=retries,
        backoff_factor=2,          # 0s, 2s, 4s, 8s...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=policy, pool_maxsize=4)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def check(session: requests.Session) -> int:
    """Confirm traffic actually leaves via Tor."""
    try:
        r = session.get("https://check.torproject.org/api/ip", timeout=30)
        data = r.json()
    except requests.exceptions.ConnectionError:
        print("FAIL  cannot reach the SOCKS proxy - is tor running on 9050?", file=sys.stderr)
        return 2
    except Exception as e:                      # noqa: BLE001
        print(f"FAIL  {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if data.get("IsTor"):
        print(f"OK    exiting via Tor, exit node {data.get('IP')}")
        return 0
    print(f"FAIL  NOT going through Tor (apparent IP {data.get('IP')}) - aborting", file=sys.stderr)
    return 1


def classify(url: str) -> tuple[str, str]:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host.endswith(".onion"):
        return host, "onion-v3" if ONION_V3.match(host) else "onion-malformed"
    return host, "clearnet"


def slug(url: str) -> str:
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    host, _ = classify(url)
    return f"{(host or 'nohost')[:40]}-{h}"


def fetch(session, url, outdir, timeout, max_bytes):
    host, kind = classify(url)
    if kind == "onion-malformed":
        return {"url": url, "status": "skipped", "reason": "not a valid v3 onion address"}

    started = dt.datetime.now(dt.timezone.utc)
    try:
        r = session.get(url, timeout=timeout, stream=True, allow_redirects=True)
    except Exception as e:                      # noqa: BLE001
        return {"url": url, "status": "error", "reason": f"{type(e).__name__}: {e}"}

    body, total, truncated = bytearray(), 0, False
    for chunk in r.iter_content(CHUNK):
        total += len(chunk)
        if total > max_bytes:
            truncated = True
            break
        body.extend(chunk)
    r.close()

    base = outdir / slug(url)
    ext = ".html" if "html" in r.headers.get("Content-Type", "") else ".bin"
    payload = base.with_suffix(ext)
    payload.write_bytes(bytes(body))

    meta = {
        "url": url,
        "final_url": r.url,
        "host": host,
        "kind": kind,
        "status": "ok",
        "http_status": r.status_code,
        "content_type": r.headers.get("Content-Type"),
        "bytes": len(body),
        "truncated": truncated,
        "sha256": hashlib.sha256(body).hexdigest(),
        "fetched_at": started.isoformat(),
        "file": payload.name,
        "redirects": [h.url for h in r.history],
    }
    base.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch pages over Tor with provenance logging.")
    p.add_argument("urls", nargs="*", help="URLs to fetch")
    p.add_argument("--urls", dest="urlfile", metavar="FILE",
                   help="file of URLs, one per line (# comments allowed)")
    p.add_argument("-o", "--outdir", default="fetched", help="output directory")
    p.add_argument("--socks", default=SOCKS_DEFAULT, help=f"SOCKS proxy (default {SOCKS_DEFAULT})")
    p.add_argument("--delay", type=float, default=3.0, help="seconds between requests")
    p.add_argument("--timeout", type=float, default=90.0, help="per-request timeout (onions are slow)")
    p.add_argument("--retries", type=int, default=4, help="retry attempts per URL")
    p.add_argument("--max-bytes", type=int, default=25 * 1024 * 1024, help="cap per response")
    p.add_argument("--check", action="store_true", help="verify Tor routing and exit")
    p.add_argument("--no-check", action="store_true", help="skip the pre-flight Tor check")
    args = p.parse_args()

    session = build_session(args.socks, args.retries)

    if args.check:
        return check(session)

    targets = list(args.urls)
    if args.urlfile:
        for line in pathlib.Path(args.urlfile).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                targets.append(line)
    if not targets:
        p.error("no URLs given (pass them as arguments or via --urls FILE)")

    # Never fetch unless we have confirmed we are behind Tor.
    if not args.no_check:
        rc = check(session)
        if rc != 0:
            return rc

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    log = outdir / "fetch-log.jsonl"
    ok = 0

    for i, url in enumerate(targets, 1):
        if i > 1:
            time.sleep(args.delay)
        print(f"[{i}/{len(targets)}] {url}", flush=True)
        meta = fetch(session, url, outdir, args.timeout, args.max_bytes)
        with log.open("a") as fh:
            fh.write(json.dumps(meta) + "\n")
        if meta["status"] == "ok":
            ok += 1
            print(f"         {meta['http_status']}  {meta['bytes']:,} B  -> {meta['file']}")
        else:
            print(f"         {meta['status']}: {meta['reason']}", file=sys.stderr)

    print(f"\n{ok}/{len(targets)} fetched into {outdir}/  (log: {log.name})")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
