# Vita3K 跑通《灵魂献祭 Delta》——从零到进游戏

> 适用：Windows 11 x64。
> 这份文档只解决“把手上这份 dump 跑起来”，不涉及重编译。
> 标注 **[需按版本核对]** 的地方，以你装的那个 Vita3K 版本的界面为准。

---

## 0. 先校验，再动手

不要装完才发现区码/格式不对。在仓库根目录执行：

```powershell
python scripts/check-dump.py <解压出来的目录 或 .vpk>
```

看三行就够：`Title ID` / `APP_VER` / 结论。

- `PCSD00079` = 港版亚洲版，Vita3K 官方状态 `Ingame +`（带 graphics bug、shader bug）；
- `PCSA00152` / `PCSF00532` = 美/欧版，`Playable`。

---

## 1. 装 Vita3K

1. 拿官方 Windows 版（GitHub Releases 的 `.exe` 安装包或 `.zip` 绿色版）。
2. 首次启动会让你选一个 **数据目录**——所有东西（固件、游戏、存档、着色器缓存）都在这一个目录下，放在空间充足的盘上。
3. 进去之后先别装游戏，先装固件。

---

## 2. 装固件（必须）

`File → Install Firmware` **[需按版本核对]**，选 `PSVUPDAT.PUP`。

- 只需要 `PSVUPDAT.PUP`（PS Vita 系统固件）。`PSP2UPDAT.PUP` 是 PSP 模拟部分用的，跑 PSV 游戏不需要。
- 固件 Sony 官网公开提供；重编译工具链（ss-delta）要的也是同一个文件。
- 装完 Vita3K 会显示固件版本，此时模拟器才算能用。

---

## 3. 放游戏——按你手上的形态选一种

### A. NoNpDrm 目录（`app` / `patch` / `addcont`）—— 推荐

解压后你会看到类似：

```
app/PCSD00079/          <- 本体（eboot.bin、sce_sys/、sce_module/ …）
patch/PCSD00079/        <- 升级补丁（有的话，SSD 的 1.30 就在这）
addcont/PCSD00079/      <- DLC（有的话）
```

把这三个目录**整体**合并到 Vita3K 数据目录下的 `ux0/` 里（即 `ux0/app/PCSD00079/...`）。
`ux0` 的实际路径在 Vita3K 设置里能看到/改，默认在它的数据目录下。

放完在 Vita3K 里**刷新应用列表**（重启或界面上的 refresh），游戏图标会出现在列表里。

> 提示：NoNpDrm 解压后可能看不到文件（隐藏属性），这是正常的，复制时别漏。

### B. `.vpk` —— 最省事

`File → Install .zip, .vpk` **[需按版本核对]**，选 vpk，等装完。

### C. `.pkg` + `work.bin`

`File → Install .pkg` **[需按版本核对]**，选 pkg，再选对应的 `work.bin`。
补丁 pkg 用同一个入口再装一次。
**只有 pkg 没有 work.bin 的，这条路走不通**，要先补 license 文件。

### D. Mai233 格式 —— 别用

`mai/PCSD00079/...` 这种结构是 MaiDumpTool 的加载器体系，Vita3K 不是它的目标平台。
PC 侧没有干净的转换办法，直接去同一批合集里找 NoNpDrm 版（条目通常挨着）。

---

## 4. 进游戏前必调的几项

| 项 | 建议值 | 为什么 |
|---|---|---|
| 渲染后端 | **Vulkan** | SSD 在 OpenGL 后端问题更多；有 Vulkan 的显卡就用 Vulkan |
| 分辨率倍率 | 2×（1920×1088） | 原生 3D 是 720×408 拉伸的，2× 才有实际像素收益 |
| 着色器缓存 / 异步编译 | 开 | 不开的话每次进新场景都卡一下 |
| 帧率上限 | 30（先跑通再谈） | SSD 原始节奏是 30fps，先稳定再加 |
| 音频缓冲 | 默认 | 爆音再调 |

---

## 5. 已知症状 → 处置

| 症状 | 原因 / 处置 |
|---|---|
| **地面全白、过曝** | NVIDIA 上的已知渲染 bug。Vita3K 上游和 Plus 分支都有；`ss-delta` 为此专门加了 sRGB 纹理采样修复。模拟器侧只能换后端/升级版本试试 |
| **移动物体带 bloom 拖影** | 同上，重编译版修了，模拟器版没修 |
| **新场景卡顿几秒** | 着色器现场编译，开缓存 + 多跑几遍会缓解 |
| 进得了主菜单但进任务卡住/花屏 | 亚洲版的 `Ingame +` 就是这个表现；日/美/欧版是 `Playable` |
| 存档 | 存在 Vita3K 数据目录的 `ux0/user/00/savedata/` |

---

## 6. 跑通之后的判断点

跑完这一遍，你要回答的其实是两个问题：

1. **画质和帧率你能不能接受？** 能 → 就停在 Vita3K，不值得为原生版折腾。
2. **拿到的是哪个区？** 只有 `PCSF00532`（欧）或 `PCSA00152`（美 1.30）才谈得上重编译：
   - 欧版 → `Luufen/nativ` v0.1.5-lf5 解压即用
   - 美版 1.30 → `vita-recomps/ss-delta`，要 VS2022 + Qt 6.11 + Vulkan SDK 自建

亚洲版/日版 → 原生这条路到此为止，别在编译环境上浪费时间。

> 如果只是要中文：美版 1.30 的原生版可以在 `ss-delta.ini` 里设 `language = chinese_s`（简中）或 `chinese_t`（繁中），不必为了中文去啃亚洲版的 pack。见 [`dump-formats.md`](dump-formats.md#7-语言资源不是按区锁死的)。
