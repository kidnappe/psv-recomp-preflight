# dump 形态与判据

> 判据优先级：**区码 > 版本 > 格式**。区码不对，后面全白搭。
> 本文只讨论如何识别与校验自己手上的副本，不提供任何游戏文件的获取渠道。

---

## 1. 四种常见形态

| 看到什么 | 是什么 | Vita3K | 重编译 |
|---|---|---|---|
| `app/` + `patch/` + `addcont/` 三个目录 | NoNpDrm | ✅ | ✅ Nativ / ss-delta |
| `mai/` 目录 + MaiDumpTool 提示 | Mai233 | ❌ | ❌ PC 侧无干净转换 |
| 单个 `.vpk` | 打包安装体 | ✅ 直接装 | ❌ 不能直接喂工具链 |
| `.pkg` + `work.bin` / zRIF | PSN 形态 | ✅ | ss-delta 认 pkg + work.bin |

`addcont/` 是 DLC，`patch/` 是更新层；Vita 挂载时 patch 覆盖 app 的同名文件。
重编译要的是**已合并**的一棵树，见 `scripts/merge-patch.py`。

---

## 2. 区码：认 content id，不认页面标题

pkg 文件头偏移 `0x30` 起 48 字节是 content id，第一段就是区：

| 前缀 | 区 |
|---|---|
| `HP9000` | 亚洲（港/台/韩） |
| `UP9000` | 美 |
| `EP9000` | 欧 |
| `JP9000` | 日 |

第二段是 Title ID。例：`HP9000-PCSD00079_00-SOULSACDELTAAS00` = 亚洲版本体。

NoNpDrm 目录则直接看 `param.sfo` 的 `TITLE_ID`：第 4 位是区码
（`A/E` = 美，`B/F` = 欧，`C/G` = 日，`D/H` = 亚洲）。

**镜像站/网盘的页面标题经常写错区**，唯一可信的是 content id 与 `param.sfo`。

---

## 3. 版本：看 APP_VER

- `param.sfo` 的 `APP_VER` 是实际版本（如 `01.00`、`01.30`）。
- 本体 + 补丁分开存放时，**只有 app 层的 `APP_VER` 是旧的**，合并后才会变成 1.30。
- `addcont/` 里也有自己的 `param.sfo`，标题会串；优先读 `app/` 层。

---

## 4. 补丁：走索尼官方更新接口

补丁免费、无需账号，接口就是索尼客户端自己在用的那条：

```
GET http://gs-sec.ww.np.dl.playstation.net/pl/np/<TITLE>/<HMAC>/<TITLE>-ver.xml
HMAC = HMAC-SHA256(KEY, "np_" + TITLE)
KEY  = E5E278AA1EE34082A088279C83F9BBC806821C52F2AB5D2B4ABD995450355114
```

返回 XML 里每个 `<package>` 就是一个补丁 pkg：

- `type="cumulative"` 表示累积更新，装最新那个即可，不用逐个叠。
- `pkg2zip` 解 **patch 类型** pkg 不需要 zRIF；只有 app 类型本体才要授权串。

工具：`scripts/get-patch.py`（任意 Title ID 通用）。

三个区都有 1.30 累积补丁：

| Title ID | 版本 | 大小 | content_id |
|---|---|---|---|
| PCSA00152 (US) | 01.30 | 162.6 MB | `UP9000-PCSA00152_00-SOULSACDELTAUS00` |
| PCSF00532 (EU) | 01.30 | 155.2 MB | `EP9000-PCSF00532_00-SOULSACDELTAEU00` |
| PCSD00079 (ASIA) | 01.30 | 155.9 MB | `HP9000-PCSD00079_00-SOULSACDELTAAS00` |

---

## 5. 校验流程

```powershell
# 解压/安装完先跑这个，别装完工具链才发现区码不对
python scripts/check-dump.py <目录 或 .vpk 或 eboot>
```

要看到：

- `Title ID: PCSA00152` → 美版，可上 ss-delta（需 1.30）
- `Title ID: PCSF00532` → 欧版，可直接吃 Nativ
- `Title ID: PCSD00079` / `PCSC00049` → 只走 Vita3K
- `APP_VER: 01.30` → 补丁已合并；仍是 `01.00` 就先跑 `merge-patch.py`

---

## 6. 易错点

| 现象 | 说明 |
|---|---|
| 页面写 USA，实际是亚洲版 | 认 content id / `TITLE_ID`，不认标题 |
| 官方 XML 的 `sha1sum` 与实际文件不符 | 索尼可能重签过包；以大小、pkg2zip 结构校验、内部 `PARAM.SFO` 为准 |
| NoNpDrm 解压后“看不到文件” | 可能带隐藏属性，复制时别漏 |
| `.vpk` 能装 Vita3K 但重编译不认 | 重编译要目录形态（或 pkg + work.bin） |
| 合并后 `APP_VER` 仍是旧值 | patch 层没覆盖到 eboot / `sce_sys`，检查 `--patch` 指到的是不是 `patch/<TID>` |

---

## 7. 语言资源不是按区锁死的

ss-delta 安装时会解密 `archive.pfs` / `archive.pk`。解密后的索引里可以直接看到多语言资源，例如：

- `achievement_text_cn.msgt` / `achievement_text_tw.msgt`
- `elder_cn_font0.gxt` / `elder_tw_font0.gxt`
- `font_config_cn.csv` / `font_config_tw.csv`

美版 1.30 的 archive 里本来就带这些文件；安装器只是解密，没有换区。语言由 ss-delta 的 `[game] language` 选择：

```ini
language = chinese_s   ; 简中；chinese_t = 繁中
```

所以“要中文”不等于“必须用亚洲版”。区码决定的是 SKU、语音包和本地化图标；文本语言可以在 ss-delta 里切。

