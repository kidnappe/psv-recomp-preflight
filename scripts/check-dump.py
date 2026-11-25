#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check-dump.py — 校验一份 PS Vita 游戏副本能不能喂给重编译工具链。

为什么需要它：ss-delta / Project Nativ 都是用 eboot 的 SHA-256 认版本的，
区码或版本对不上会直接被 import 拒绝，白装一遍工具链。

用法：
    python check-dump.py <dump路径>          # 目录 / .vpk / 单个 eboot
    python check-dump.py <dump路径> --json   # 机器可读输出

判读依据（写死在 TARGETS 里，来自两个项目的 pack 与 README）：
    PCSF00532 (EU, Delta v1.00)  -> Luufen/nativ 有 pack，SHA-256 已公开
    PCSA00152 (US, Delta v1.30)  -> vita-recomps/ss-delta 支持，按 TITLE_ID + eboot 哈希判
    PCSC00049 / PCSD00079        -> 两个项目都不支持
    PCSA00092 (原版)             -> 只走 Vita3K
"""

import argparse
import hashlib
import io
import json
import os
import struct
import sys
import zipfile

# Windows 控制台默认 GBK，游戏名里的 ™ 等字符会直接抛 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 已知目标表

TARGETS = {
    "PCSF00532": {
        "name": "Soul Sacrifice Delta (EU)",
        "version": "1.00",
        "sha256": "a4c2712ff93e746e07c6e50a1495872de0e7a303cda7b3ac099677f1eac51178",
        "verdict": "可直接用 Luufen/nativ v0.1.5-lf5+（解压即用，README 记录 Win11 实测可玩）",
    },
    "PCSA00152": {
        "name": "Soul Sacrifice Delta (US)",
        "version": "1.30",
        # 官方 1.30 补丁里的 eboot；与 1.30 补丁合并后的成品应当一致
        "sha256": "fa278b30c958187111f8b9face800d5c76c4bf5ec86a23fa0d35e6fcb04da3bf",
        "verdict": "走 vita-recomps/ss-delta，但必须自己编译（VS2022 + Qt 6.11 + Vulkan SDK），且需 1.30 补丁合并",
    },
    "PCSC00049": {
        "name": "Soul Sacrifice Delta (JP)",
        "version": None,
        "sha256": None,
        "verdict": "两个重编译项目都不支持；只能 Vita3K（官方状态 Playable，带 graphics bug）",
    },
    "PCSD00079": {
        "name": "Soul Sacrifice Delta (ASIA)",
        "version": None,
        "sha256": None,
        # 注意：官方列表逐条数据里亚洲版是 Ingame +（shader bug），不是 Playable
        "verdict": "两个重编译项目都不支持；只能 Vita3K，且官方状态仅 Ingame +（graphics bug + shader bug）——想通关得靠运气",
    },
    "PCSA00092": {
        "name": "Soul Sacrifice (US, 2013 原版)",
        "version": None,
        "sha256": None,
        "verdict": "两个项目都只做 Delta；原版只能走 Vita3K",
    },
}

EBOOT_NAMES = ("eboot.bin.elf", "eboot.bin", "eboot.self")
SFO_NAMES = ("param.sfo", "sce_sys/param.sfo", "sce_sys\\param.sfo")


# ---------------------------------------------------------------- SFO 解析

def parse_sfo(blob: bytes) -> dict:
    """极简 SFO 读取器：只取字符串与 u32 两类字段。"""
    if len(blob) < 20 or blob[0:4] != b"\x00PSF":
        raise ValueError("not an SFO (magic mismatch)")
    key_start, data_start, count = struct.unpack_from("<III", blob, 8)
    out = {}
    for i in range(count):
        off = 20 + i * 16
        key_off, fmt, length, _maxlen, data_off = struct.unpack_from("<HHIII", blob, off)
        key = _cstr(blob, key_start + key_off)
        raw = blob[data_start + data_off: data_start + data_off + length]
        if fmt == 0x0204:  # UTF-8 string
            out[key] = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
        elif fmt == 0x0404:  # binary / utf-8 string
            out[key] = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
        elif fmt == 0x0402:  # uint32
            out[key] = struct.unpack("<I", raw)[0] if len(raw) == 4 else None
        else:
            out[key] = raw.hex()
    return out


def _cstr(blob: bytes, start: int) -> str:
    end = blob.find(b"\x00", start)
    if end < 0:
        end = len(blob)
    return blob[start:end].decode("utf-8", "replace")


def _ver_tuple(ver: str):
    """把 '01.30' / '1.30' 归一化后比较，避免前导零造成误报。"""
    try:
        return tuple(int(part) for part in str(ver).split("."))
    except ValueError:
        return (str(ver),)


# ---------------------------------------------------------------- 收集文件

def collect(path: str):
    """返回 (eboot 字节候选 [(label, bytes)], param.sfo 候选 [(label, dict)])"""
    ebo, sfos = [], []

    def walk_dir(root):
        for dirpath, _dirnames, filenames in os.walk(root):
            lower = {f.lower(): f for f in filenames}
            for want in EBOOT_NAMES:
                if want in lower:
                    full = os.path.join(dirpath, lower[want])
                    ebo.append((full, open(full, "rb").read()))
                    break
            for want in ("param.sfo",):
                if want in lower:
                    full = os.path.join(dirpath, lower[want])
                    try:
                        sfos.append((full, parse_sfo(open(full, "rb").read())))
                    except Exception as exc:  # noqa: BLE001
                        sfos.append((full, {"_error": str(exc)}))

    if os.path.isdir(path):
        walk_dir(path)
    elif path.lower().endswith(".vpk") or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                base = os.path.basename(info.filename).lower()
                if base in EBOOT_NAMES:
                    ebo.append((f"{path}!{info.filename}", zf.read(info)))
                if base == "param.sfo":
                    try:
                        sfos.append((f"{path}!{info.filename}", parse_sfo(zf.read(info))))
                    except Exception as exc:  # noqa: BLE001
                        sfos.append((f"{path}!{info.filename}", {"_error": str(exc)}))
    else:
        blob = open(path, "rb").read()
        ebo.append((path, blob))
        try:
            sfos.append((path + " (as sfo)", parse_sfo(blob)))
        except Exception:
            pass

    return ebo, sfos


# ---------------------------------------------------------------- 主流程

def analyze(path: str) -> dict:
    ebo, sfos = collect(path)
    result = {"input": path, "title_id": None, "app_ver": None, "title": None,
              "eboot": [], "sfo_files": [s for s, _ in sfos], "verdict": None, "notes": []}

    # 优先读 app/ 层的 param.sfo（addcont 里也有自己的 param.sfo，标题会串）
    sfos.sort(key=lambda kv: (0 if "\\app\\" in kv[0] or "/app/" in kv[0] else 1))

    for label, info in sfos:
        if "_error" in info:
            result["notes"].append(f"{label}: {info['_error']}")
            continue
        result["title_id"] = result["title_id"] or info.get("TITLE_ID")
        result["app_ver"] = result["app_ver"] or info.get("APP_VER")
        result["title"] = result["title"] or info.get("TITLE")

    for label, blob in ebo:
        digest = hashlib.sha256(blob).hexdigest()
        result["eboot"].append({"path": label, "size": len(blob), "sha256": digest})

    tid = result["title_id"]
    target = TARGETS.get(tid or "")
    hashes = {e["sha256"] for e in result["eboot"]}

    if not ebo:
        result["verdict"] = "没找到 eboot（eboot.bin / eboot.bin.elf / eboot.self）。这不是可喂给工具链的解密 dump。"
    elif target is None:
        result["verdict"] = f"Title ID {tid!r} 不在已知目标表里，需人工判路线。"
    elif target["sha256"]:
        if target["sha256"] in hashes:
            result["verdict"] = f"✅ 完全匹配 {tid} {target['version']}：{target['verdict']}"
        else:
            result["verdict"] = (f"⚠️ Title ID 是 {tid}，但 eboot 哈希与 {target['version']} 的已知值不符"
                                 f"（可能版本不同或补丁未合并）。{target['verdict']}")
    else:
        result["verdict"] = f"Title ID {tid}：{target['verdict']}"

    if (target and target["version"] and result["app_ver"]
            and _ver_tuple(result["app_ver"]) != _ver_tuple(target["version"])):
        result["notes"].append(
            f"APP_VER={result['app_ver']}，目标要求 {target['version']}；请合并对应补丁后再使用。")

    if not sfos:
        result["notes"].append("没有 param.sfo，无法确认 Title ID / 区码。")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验 PS Vita dump 是否匹配 ss-delta / Nativ 的要求")
    ap.add_argument("path", help="dump 目录、.vpk 或单个 eboot 文件（.pkg 请先用 pkg2zip 解开）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if not os.path.exists(args.path):
        print(f"路径不存在：{args.path}", file=sys.stderr)
        return 2

    res = analyze(args.path)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    print(f"输入        : {res['input']}")
    print(f"标题        : {res['title'] or '(未知)'}")
    print(f"Title ID    : {res['title_id'] or '(未知)'}")
    print(f"APP_VER     : {res['app_ver'] or '(未知)'}")
    print("eboot 候选  :")
    if not res["eboot"]:
        print("  (无)")
    for e in res["eboot"]:
        print(f"  {e['size']:>10} B  {e['sha256']}  {e['path']}")
    for n in res["notes"]:
        print(f"note        : {n}")
    print()
    print(f"结论        : {res['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
