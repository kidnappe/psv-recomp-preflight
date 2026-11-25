#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge-patch.py —— 把 Vita 的 patch（更新）层合并进 app 层，产出 ss-delta 能吃的
"已合并 1.30" dump。

背景：NoNpDrm 的 dump 是分层的，ux0 里等于
    app/<TID>/        本体
    patch/<TID>/      更新（1.01、1.30 …）
    addcont/<TID>/    DLC
Vita 挂载时 patch 覆盖 app 的同名文件。PC 侧重编译要的是一棵合并后的树，
所以这一步必须自己做——ss-delta 的安装脚本只接受"已合并 1.30"的输入。

用法：
    python merge-patch.py --app <app目录> --patch <patch目录>            # 只出计划，不动文件
    python merge-patch.py --app ... --patch ... --out <输出目录>          # 合并到新目录（推荐）
    python merge-patch.py --app ... --patch ... --inplace                # 直接覆盖 app（先备份）

判据：
    两份 param.sfo 的 TITLE_ID 必须一致；
    patch 的 APP_VER 应当是你想合并到的版本（本例 01.30）。
"""

import argparse
import hashlib
import os
import shutil
import sys

# Windows 控制台默认 GBK，路径里的特殊字符会直接抛 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

EBOOT_NAMES = ("eboot.bin.elf", "eboot.bin", "eboot.self")


# ------------------------------------------------------------------ SFO

def parse_sfo(blob: bytes) -> dict:
    import struct
    if len(blob) < 20 or blob[0:4] != b"\x00PSF":
        raise ValueError("not an SFO")
    key_start, data_start, count = struct.unpack_from("<III", blob, 8)
    out = {}
    for i in range(count):
        off = 20 + i * 16
        koff, fmt, length, _mx, doff = struct.unpack_from("<HHIII", blob, off)
        ks = key_start + koff
        ke = blob.find(b"\x00", ks)
        key = blob[ks:ke if ke > 0 else len(blob)].decode("utf-8", "replace")
        raw = blob[data_start + doff: data_start + doff + length]
        if fmt in (0x0204, 0x0404):
            out[key] = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
        elif fmt == 0x0402 and len(raw) == 4:
            out[key] = struct.unpack("<I", raw)[0]
    return out


def find_sfo(root: str):
    for dirpath, _d, filenames in os.walk(root):
        if "param.sfo" in {f.lower() for f in filenames}:
            p = os.path.join(dirpath, next(f for f in filenames if f.lower() == "param.sfo"))
            try:
                return p, parse_sfo(open(p, "rb").read())
            except Exception:
                continue
    return None, {}


def find_eboot(root: str):
    for dirpath, _d, filenames in os.walk(root):
        lower = {f.lower(): f for f in filenames}
        for want in EBOOT_NAMES:
            if want in lower:
                return os.path.join(dirpath, lower[want])
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ 计划

def build_plan(app_root, patch_root):
    """patch 里每个文件相对于 TID 目录的位置，决定它覆盖 app 的哪个文件。"""
    plan, new, total = [], 0, 0
    for dirpath, _d, filenames in os.walk(patch_root):
        for name in filenames:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, patch_root)
            dst = os.path.join(app_root, rel)
            total += 1
            if os.path.exists(dst):
                plan.append(("replace", rel, src, dst))
            else:
                new += 1
                plan.append(("add", rel, src, dst))
    return plan, new, total


def main(argv=None):
    ap = argparse.ArgumentParser(description="合并 Vita patch 层到 app 层")
    ap.add_argument("--app", required=True, help="本体目录（含 eboot.bin 和 sce_sys/param.sfo）")
    ap.add_argument("--patch", required=True, help="更新目录（patch/<TID>/ 那一层）")
    ap.add_argument("--out", help="合并结果输出到新目录（推荐）")
    ap.add_argument("--inplace", action="store_true", help="直接覆盖 app 目录（会先写 .bak 清单）")
    ap.add_argument("--expect-ver", default="01.30", help="期望的 patch APP_VER（默认 01.30）")
    args = ap.parse_args(argv)

    if args.inplace and args.out:
        print("--out 和 --inplace 只能选一个", file=sys.stderr)
        return 2
    if not args.inplace and not args.out:
        args.dry = True
    else:
        args.dry = False

    # --- 校验两边的身份
    a_sfo, a = find_sfo(args.app)
    p_sfo, p = find_sfo(args.patch)
    if not a_sfo:
        print(f"❌ app 层没找到 param.sfo：{args.app}", file=sys.stderr)
        return 2
    if not p_sfo:
        print(f"❌ patch 层没找到 param.sfo：{args.patch}", file=sys.stderr)
        return 2

    a_tid, p_tid = a.get("TITLE_ID"), p.get("TITLE_ID")
    a_ver, p_ver = a.get("APP_VER"), p.get("APP_VER")
    print(f"app   : {a_tid}  APP_VER={a_ver}   ({a_sfo})")
    print(f"patch : {p_tid}  APP_VER={p_ver}   ({p_sfo})")
    if a_tid != p_tid:
        print(f"❌ Title ID 不一致（{a_tid} vs {p_tid}），这不是同一款游戏的更新层", file=sys.stderr)
        return 2
    if args.expect_ver and p_ver and p_ver != args.expect_ver:
        print(f"⚠️ patch 的 APP_VER 是 {p_ver}，不是期望的 {args.expect_ver}；继续，但先确认这是不是你要的版本")

    # --- 计划
    plan, new, total = build_plan(args.app, args.patch)
    bytes_in = sum(os.path.getsize(s) for _k, _r, s, _d in plan)
    print(f"\n合并计划：patch 共 {total} 个文件，其中覆盖 {total - new} 个、新增 {new} 个，"
          f"共 {bytes_in / (1 << 20):.1f} MB")

    if args.dry:
        for kind, rel, _s, _d in plan[:20]:
            print(f"  [{kind}] {rel}")
        if total > 20:
            print(f"  … 另外 {total - 20} 项")
        print("\n这是空跑。加 --out <目录> 或 --inplace 才会真正写文件。")
        return 0

    # --- 执行
    if args.inplace:
        dst_root = args.app
        bak = os.path.join(os.path.dirname(os.path.abspath(args.app)), "merge-inplace-backup.txt")
        with open(bak, "w", encoding="utf-8") as f:
            for kind, rel, _s, _d in plan:
                f.write(f"{kind}\t{rel}\n")
        print(f"已写覆盖清单：{bak}（回滚依据；本体文件请自行备份）")
    else:
        dst_root = args.out
        if os.path.exists(dst_root) and os.listdir(dst_root):
            print(f"❌ 输出目录非空：{dst_root}", file=sys.stderr)
            return 2
        print(f"复制本体到 {dst_root} …")
        shutil.copytree(args.app, dst_root)

    done = 0
    for kind, rel, src, _d in plan:
        target = os.path.join(dst_root, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(src, target)
        done += 1
    print(f"合并完成：{done} 个文件写入 {dst_root}")

    # --- 复验
    eb = find_eboot(dst_root)
    if eb:
        print(f"\n合并后 eboot : {eb}")
        print(f"  size   : {os.path.getsize(eb)}")
        print(f"  sha256 : {sha256(eb)}")
    _s, m = find_sfo(dst_root)
    print(f"  TITLE_ID={m.get('TITLE_ID')}  APP_VER={m.get('APP_VER')}")
    if m.get("APP_VER") == args.expect_ver:
        print(f"\n✅ APP_VER 已是 {args.expect_ver}，这份可以喂 ss-delta")
    else:
        print(f"\n⚠️ APP_VER 仍是 {m.get('APP_VER')}，patch 层可能没覆盖到 eboot/sce_sys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
