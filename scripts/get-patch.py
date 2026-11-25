#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get-patch.py —— 直接从索尼官方更新接口查任意 PSV 游戏的补丁包地址。

原理（不是猜的，是索尼客户端自己在用的那条路）：
    GET http://gs-sec.ww.np.dl.playstation.net/pl/np/<TITLE>/<HMAC>/<TITLE>-ver.xml
其中 HMAC = HMAC-SHA256(KEY, "np_" + TITLE)，KEY 是公开常量（wololo 论坛早年逆出来的）。
返回的 XML 里每个 <package> 就是一个可下载的补丁 pkg：version / size / sha1sum / url / content_id。

要点：
  * 补丁 pkg 免费，不需要账号、不需要购买凭证。
  * pkg2zip 解 patch 类型 pkg **不需要 zRIF**（只有 app 类型的本体才要授权串）。
  * type="cumulative" 表示累积更新，装最新那个即可，不用逐个叠。

用法：
    python get-patch.py PCSA00152          # 查一个
    python get-patch.py PCSA00152 --json   # 机器可读
"""

import argparse
import hashlib
import hmac
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

# Windows 控制台默认 GBK，标题里的 ™ 等字符会直接抛 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

KEY = bytes.fromhex("E5E278AA1EE34082A088279C83F9BBC806821C52F2AB5D2B4ABD995450355114")
BASE = "http://gs-sec.ww.np.dl.playstation.net/pl/np/{t}/{h}/{t}-ver.xml"


def fetch_xml(title: str) -> str | None:
    digest = hmac.new(KEY, ("np_" + title).encode("ascii"), hashlib.sha256).hexdigest()
    url = BASE.format(t=title, h=digest)
    try:
        with urllib.request.urlopen(url, timeout=30) as f:
            return f.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for tag in root.findall("./tag"):
        for p in tag.findall("./package"):
            sfo = p.find("./paramsfo")
            title = None
            if sfo is not None:
                el = sfo.find("./title")
                title = el.text if el is not None else None
            out.append({
                "version": p.get("version"),
                "size": int(p.get("size") or 0),
                "sha1sum": p.get("sha1sum"),
                "url": p.get("url"),
                "content_id": p.get("content_id"),
                "type": p.get("type"),
                "fw": p.get("psp2_system_ver"),
                "title": title,
            })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="查 PSV 官方补丁 pkg 地址")
    ap.add_argument("title", help="Title ID，如 PCSA00152")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    xml = fetch_xml(args.title.upper())
    if xml is None:
        print(f"{args.title}: 该接口没有记录（404），可能不是零售标题或 ID 写错", file=sys.stderr)
        return 1

    pkgs = parse(xml)
    if args.json:
        print(json.dumps(pkgs, ensure_ascii=False, indent=2))
        return 0

    print(f"{args.title.upper()}：共 {len(pkgs)} 个补丁包")
    for p in pkgs:
        print(f"  版本 {p['version']}  {p['size'] / (1 << 20):.1f} MB  type={p['type']}")
        print(f"    content_id : {p['content_id']}")
        print(f"    sha1       : {p['sha1sum']}")
        print(f"    url        : {p['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
