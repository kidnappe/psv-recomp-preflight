#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
psv-lookup.py — 按名字 / Title ID 查一款 PSV 游戏的三件事：
    1) Vita3K 官方兼容状态（含各区）
    2) 有没有现成的静态重编译支持（Nativ pack / ss-delta）
    3) 因此该走哪条路、要不要纠结区码

数据源：vita3k-compat.json（https://api.vita3k.org/list/commercial 的原样落盘）。
文件被截断也能用——JSON 解析失败时退回正则抽取。

用法：
    python psv-lookup.py soul            # 模糊匹配名字
    python psv-lookup.py PCSF00532       # 按 Title ID
    python psv-lookup.py --region EU     # 列出有重编译支持的欧版游戏
"""

import argparse
import json
import os
import re
import sys

# Windows 控制台默认 GBK，游戏名里的 ™ 等字符会直接抛 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, os.pardir, "data", "vita3k-compat.json"))

# 区码：Title ID 第 4 位
REGION = {"A": "USA", "E": "USA", "B": "EUR", "F": "EUR",
          "C": "JPN", "G": "JPN", "D": "ASIA", "H": "ASIA", "I": "INT"}

# Project Nativ（上游 + Luufen fork）有 pack 的游戏，键为 Title ID
NATIV = {
    "PCSF00532": "Soul Sacrifice Delta (EU)",
    "PCSE00764": "Persona 4: Dancing All Night (US)",
    "PCSE01274": "Persona 3: Dancing in Moonlight (US)",
    "PCSE01275": "Persona 5: Dancing in Starlight (US)",
    "PCSF00001": "Uncharted: Golden Abyss (EU)",
    "PCSF00476": "Tearaway",
    "PCSB00672": "Medieval Defenders",
    "PCSB00245": "Persona 4 Golden",
    "PCSF00415": "Invizimals: Hidden Challenges",
    "PCSF00510": "Invizimals: The Resistance",
    "PCSF00243": "Killzone: Mercenary (EU)",
    "PCSD00005": "WipEout 2048",
    "PCSA00017": "LittleBigPlanet",
    "PCSF00024": "Gravity Rush",
    "PCSF00482": "Ratchet & Clank Trilogy",
    "PCSF00153": "PlayStation All-Stars Battle Royale",
    "PCSB00356": "Injustice: Gods Among Us UE",
    "PCSB00144": "Street Fighter X Tekken",
    "PCSE00595": "J-Stars Victory VS+",
    "PCSB00874": "God Eater Resurrection",
    "PCSB00875": "God Eater 2 Rage Burst",
    "PCSB00232": "Call of Duty: Black Ops Declassified (RU)",
    "PCSB00500": "LEGO Ninjago: Nindroids",
    "PCSB00742": "XCOM: Enemy Unknown Plus",
    "PCSB00353": "Batman: Arkham Origins Blackgate",
    "PCSH00118": "Rayman Legends (CN)",
    "PCSH00110": "Toukiden Kiwami (CN)",
    # 上游 TheLostPantheon/nativ 自带的四款
    "PCSA00107": "Killzone: Mercenary (US)",
    "PCSA00029": "Uncharted: Golden Abyss (US)",
    "PCSA00014": "Unit 13 (US)",
    "PCSE00640": "Shovel Knight (US)",
}

# vita-recomps/ss-delta 支持范围
SSDELTA = {"PCSA00152": "Soul Sacrifice Delta (US, v1.30) — 需自建工具链"}


def load():
    if not os.path.exists(DATA):
        sys.exit(f"缺少数据文件：{DATA}")
    raw = open(DATA, encoding="utf-8", errors="replace").read()
    try:
        return json.loads(raw)["list"], "json"
    except Exception:
        # 截断文件：按条目正则抽取
        rows = []
        for m in re.finditer(
            r'\{"name":"(.*?)","titleId":"(\w*)","labels":"(.*?)","issueId":(\d+)\}', raw):
            rows.append({"name": m.group(1), "titleId": m.group(2),
                         "labels": m.group(3), "issueId": int(m.group(4))})
        return rows, f"regex(截断恢复 {len(rows)} 条)"


def status_of(labels_json):
    try:
        names = [x["name"] for x in json.loads(labels_json.replace('\\"', '"'))]
    except Exception:
        names = re.findall(r'name\\?":\\?"(.*?)\\?"', labels_json)
    known = ["Playable", "Ingame +", "Ingame -", "Menu", "Intro", "Bootable", "Nothing"]
    st = next((k for k in known if k in names), "?")
    extra = [n for n in names if n not in known and n not in
             ("online-only", "camera", "unity", "gamemaker", "outdated")]
    return st, extra


def route(tid):
    out = []
    if tid in SSDELTA:
        out.append("ss-delta（美版 1.30，需 VS2022+Qt6.11+Vulkan SDK 自建）")
    if tid in NATIV:
        out.append(f"Nativ（{NATIV[tid]}，解压即用）")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="PSV 游戏兼容性 / 重编译支持查询")
    ap.add_argument("query", nargs="?", default="", help="游戏名片段或 Title ID")
    ap.add_argument("--region", help="只列出该区的原生支持游戏（USA/EUR/JPN/ASIA）")
    args = ap.parse_args(argv)

    rows, src = load()
    print(f"# 数据源: {src}\n")

    if args.region:
        alias = {"EU": "EUR", "US": "USA", "JP": "JPN", "AS": "ASIA"}
        want = args.region.upper()
        want = alias.get(want, want)
        hits = [(t, n) for t, n in {**NATIV, **SSDELTA}.items()
                if REGION.get(t[3], "?") == want]
        print(f"{want} 区有重编译支持的：{len(hits)} 款")
        for t, n in sorted(hits):
            print(f"  {t}  {n}")
        return 0

    q = args.query.lower()
    hits = [r for r in rows if q in r["name"].lower() or q in r["titleId"].lower()]
    if not hits:
        print(f"没匹配到 {args.query!r}")
        return 1

    # 本次查询里哪些"游戏名"有原生支持，用来标记同款的其他区
    native_names = {r["name"].strip().lower() for r in hits if route(r["titleId"])}

    for r in hits:
        st, extra = status_of(r.get("labels", ""))
        region = REGION.get(r["titleId"][3:4], "?")
        native = route(r["titleId"])
        same_game_other_region = (
            not native and r["name"].strip().lower() in native_names)
        print(f"{r['name']}")
        print(f"  Title ID : {r['titleId']}  ({region})")
        print(f"  Vita3K   : {st}" + (f"  ({', '.join(extra)})" if extra else ""))
        if native:
            print(f"  重编译   : {' / '.join(native)}")
        elif same_game_other_region:
            print("  重编译   : 无 —— 同款另一区才有 pack，这个区码对不上")
        else:
            print("  重编译   : 无 —— 只能 Vita3K")
        print()

    ids = {r["titleId"] for r in hits}
    native_any = [t for t in ids if t in NATIV or t in SSDELTA]
    if native_any:
        print(f"提示：{len(native_any)} 个区版本可走原生重编译 → {', '.join(sorted(native_any))}")
    else:
        print("提示：以上版本都没有现成 pack。免费资源里能拿到的多半也是这些，"
              "先按 Vita3K 路线走，别先装编译器。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
