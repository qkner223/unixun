# cas（小米 10 Ultra / SM8250）移植 iOS 16.5 —— 执行手册

已解 BL，走 UniXNU 的格式 2 流程。本目录是一份**可直接覆盖到 `UniXNU-cas` 仓库的补丁集**，把板级目标从 iPadOS 17.7.11 / xnu-10063 换成 iOS 16.5 (20F66) / xnu-8796.101.5。

## 0. 先确认版本事实（这几条决定后面所有参数）

| 项 | 值 | 依据 |
| --- | --- | --- |
| 系统 | iOS 16.5，构建 **20F66**，Darwin **22.5.0** | IPSW 名字 `iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw` |
| XNU | **8796.101.5**，commit `aca3beaa3dfbd42498b42c5e5ce20a938e6554e5` | apple-oss-distributions/xnu；8796 系列的开源版还有 8796.121.2 / 8796.141.3，101.5 最接近 Darwin 22.5.0 |
| 架构 | **arm64**（不是 arm64e） | 官方文档：iOS 16 与 iPadOS 17 都是 arm64 目标，共用 `profiles/arch/arm64`；arm64e 要 A12+ 的 PAC 硬件，SM8250 没有 |
| donor | **iPhone X**（`iPhone10,3` / `d22ap`，T8015） | 16.5 支持且是 arm64；屏幕 1125×2436@3x，和 cas 的 1080×2340 接近，用户态布局不用改太多 |
| 页大小 | **4 KiB**（`MACHINE_CONFIGS=BCM2837`） | UniXNU 的内核构建约定；原版 kernelcache 里的 kext 是 Mach-O，与页大小无关，prelink 时才决定 |
| 引导 | cas 用 **boot header v2 + CasBootShim**，`scripts/cas_bootimg.py` 打包 | 不是 NX769J 那种 Android 14 的 v4 |

> 关键结论：**iOS 16.5 在 UniXNU 上不是"没人走过"的路**。`Asultop/UniXNU-NX769J` 已经把这套共享补丁系列整体 rebase 到 xnu-8796.101.5，并把 iPhone X 16.5 的 IPSW pin 全部读了出来。本目录的 `patches/xnu/` 就是那份 rebase 的成品，我在本机重新验证过：

```
xnu-8796.101.5 (aca3bea) 上按序应用 64 个补丁 → applied=64 failed=0
```

## 1. 本目录内容与落地方式

```
cas-ios16.5/
├── board.toml                                  # 覆盖 UniXNU-cas/board.toml
├── configs/                                    # （不用覆盖，保持 cas 原样）
├── os-profiles/ios-16.5-20F66/
│   ├── profile.toml                            # 16.5 OS profile（iPhone X 身份 + IPSW pin 已填）
│   └── configs/ios.config                      # OS 层内核配置片段
├── patches/xnu/series + 64 个补丁              # 覆盖 UniXNU-cas/patches/xnu/
└── scripts/
    ├── install-profile.sh                      # 把 profile 装进 UniXNU 检出
    ├── emit-prelink-cas.py                     # prelink 适配器（16.5 kernelcache 的 Libm 字面量池）
    └── extract-ipsw-pins.py                    # 从 IPSW 重算所有 pin（校验/换构建时用）
```

落地：

```sh
cd /path/to/UniXNU-cas
cp ../cas-ios16.5/board.toml .
rm -rf patches/xnu && cp -R ../cas-ios16.5/patches/xnu patches/
cp -R ../cas-ios16.5/os-profiles .
cp ../cas-ios16.5/scripts/install-profile.sh ../cas-ios16.5/scripts/emit-prelink-cas.py \
   ../cas-ios16.5/scripts/extract-ipsw-pins.py scripts/
chmod +x scripts/install-profile.sh scripts/emit-prelink-cas.py
```

`patches/xnu/` 被整体替换掉了 `cas-continuous-cpu0.patch` 和 `cas-entry-trace.patch`，原因见 §5 第 6 条。

## 2. 阶段与判据

### S0 环境

```sh
# 两个仓库放同一父目录
git clone https://github.com/UniXNU/UniXNU.git UniXNU
git clone <你的 UniXNU-cas 仓库> UniXNU-cas
cd UniXNU-cas

# 按 §1 把本目录覆盖进去后，把 profile 装进框架检出
./scripts/install-profile.sh ../UniXNU
```

判据：`UniXNU/profiles/os/ios-16.5-20F66/profile.toml` 存在。**每次改 profile 都要重跑这一步**，因为 copy 是替换不是合并。

### S1 解析

```sh
./unixnu defconfig cas_defconfig --device ../UniXNU-cas
./unixnu fetch --device ../UniXNU-cas
./unixnu status --device ../UniXNU-cas --json | tee /tmp/cas-status.json
./unixnu tree --device ../UniXNU-cas
```

判据（`status` 里逐条核）：
- `os_profile = ios-16.5-20F66`、`xnu_version = 8796.101.5`；
- 补丁顺序只有一段 `device:patches/xnu/series`，64 条，**没有 `patch missing`**；
- `soc_source = sm8250`，XNU commit 是 `aca3bea…`。

### S2 IPSW 输入

准备 `iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw`（约 5 GB，ipsw.me 上 iPhone10,3 / 16.5 / 20F66）。**不随仓库分发**。

```sh
UNIXNU_IPSW=/path/to/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw \
  ./unixnu ipsw fetch --device ../UniXNU-cas
```

判据：`096-04088-077.dmg` 与 `096-04666-078.dmg` 的 sha256 对上 profile 里的 pin；kernelcache 解压后用 `scripts/extract-ipsw-pins.py` 复算，`kernelcache_sha256` 应等于 `e6fa7559…dad5`。
换构建号（比如想用 16.6）时，**这一步的所有值都要重算，不能沿用**。

### S3 内核

```sh
./unixnu build kernel --device ../UniXNU-cas
```

判据：`out/cas/ios-16.5-20F66/*/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped` 产出。
注意 8796 没有 `.unstripped.noctf`（那个名字是 10063 之后的），profile 里已经把 `kernel.prelink.kernel` 指到 `.unstripped`。

### S4 payload 与启动镜像

```sh
./unixnu payload --device ../UniXNU-cas
python3 scripts/cas_bootimg.py            # cas 专用：header v2 + CasBootShim
fastboot boot out/cas/boot.img            # 先临时启动，不落盘
```

判据：进 UniXNU 菜单（按键可用）、DarwinBoot 交接内核、屏幕出现 panic 页或进度。

### S5 内核早期

看 `patches/xnu` 里 `native-text-fixup` / `zzz-boot-progress` 提供的打点，以及 cas 原有的 NC mailbox（`0x9f960000`，magic `"CAS H0"`）。

判据：CPU0 过 `arm_vm_init` → 早期 platform expert → `cpu_timebase_init` → `bsd_init` → `vfs_mountroot`。cas 在 17.7.11 上已经到过这一层，16.5 的差异主要在 prelink 与 ABM/AMFI 路径。

### S6 根卷（第一个真正卡人的地方）

要加组件：`ShengUfs`、`RamBlock`、`VerifiedRoot`（可选 `AppleKeyStoreState`），并填 `[root]` 的三个值：

```toml
[root]
os_volume_uuid = "<OS 窗口里 APFS 卷的 UUID>"
systemos_volume_uuid = "<Cryptex1,SystemOS 的 UUID>"
os_image_sha256 = "<…>"
systemos_image_sha256 = "<…>"
```

`os_volume_uuid` 用 `scripts/extract-root-volume-uuid.py` 从构建出的 userdata 镜像里读，**不是猜**；容器 UUID 与卷 UUID 不是一个东西。

判据：`vfs_mountroot` 成功、`launchd` 起来。

### S7 显示与输入

`GopFramebuffer`（CPU 呈现，先不碰 DPU/DSC）→ Hello 界面；`ST FTS`（`0x49` @ QUP I2C `0xa94000`，GPIO38/39，与小米 10 同控制器）→ 能点。参数名直接照 `UniXNU-umi`。

### S8 记录

`porting.toml` 里要同步的：`[device].os_profile`、`configuration` / `packaging` 两个 area 的 `inputs`（XNU 8796 + 16.5 IPSW）、`patch_series` 说明、`evidence`。记录校验 `python3 scripts/porting-record.py check --device ../UniXNU-cas` 要能过。

## 3. 已验证/未验证（别自己骗自己）

已在本机验证：

- 64 个补丁在 xnu-8796.101.5 上严格按序应用成功（applied=64 failed=0）；
- `patches/xnu/series` 里列出的每个补丁文件都存在；
- `board.toml`、`profile.toml` 均能被 `tomllib` 解析；
- `cas-entry-trace.patch` 打完 8796 系列后仍能应用。

未验证（需要你的机器）：

- 8796 内核在 cas 上编译通过与链接；
- prelink（`emit-prelink-cas.py` 的 Libm 池校验需要在真 kernelcache 上跑一次）；
- 任何真机启动结果。

## 4. 关于 iPhone X 身份

profile 里 `adt.root.string.model = iPhone10,3`、`compatible = D22AP`、`artwork-device-idiom = phone`、`artwork-device-subtype = 2436`、`device-perf-memory-class = 4`、`oled-display = 1` 都是 d22ap 的真实值（从 `Firmware/all_flash/DeviceTree.d22ap.im4p` 读的），共享给任何 16.5/d22ap 移植。`product-id`（20 字节，`MGGetProductType()` 查表用）也在 profile 里。

cas 的板级只覆盖 `[adt.root.string].hardware-model` 和 `[payload.adt]` 的 `chip_id = "8015"`（T8015）、`ipad_identity = false`、`owned_memory_size = "0x130000000"`。

## 5. 十个会直接卡住你的坑

1. **prelink ABI 版本绑定**：17.7.11 的 `kernelcache_sha256`、`early_security_init`、`roots`、trust cache 一个都不能沿用。profile 里已是 16.5 的值。
2. **`early_security_init` 保持注释掉**。它要的是 `AppleMobileFileIntegrity` 在 `__TEXT_EXEC` 里的函数地址，不是 `__TEXT` 的 `_PrelinkExecutableLoadAddr`；cas 没有 Apple PMGR 块，caihong/others 在这条路上撞过 `AMFI: No PMGR?`。留空 = 跳过 pre-lockdown 调用，AMFI 仍走普通 start。
3. **不要引用共享补丁系列**。`arch:` / `soc:` / `os:` / `component:XnuPrelink` 四段都还指向 10063.141.1，写进 `patch_series` 会让 `unixnu status` 直接 `patch missing` 中断。等上游 rebase 完再切回四段式。
4. **8796 没有 `.unstripped.noctf`**。指错名字会报 "not found; run unixnu build kernel first"，即使你已经构建过。
5. **Libm 字面量池**是逐 kernelcache 的。`emit-prelink-cas.py` 里那组 `0xFFFFFFF005B8E054 + 0x4CC` 属于 iPhone10,3 16.5；换 IPSW 它会主动拒绝运行，这是设计而不是 bug。
6. **cas 自己的两个补丁**：`cas-entry-trace.patch` 在 8796 上可应用；`cas-continuous-cpu0.patch` 失败（`osfmk/arm/arm_init.c:617` 上下文变了），要用 `XNU_WORK` 流程基于 8796 重新导出。
7. **4 KiB 页**：`BCM2837` 携带 4 KiB 布局，dts 与驱动里任何 16K 假设都要改掉。
8. **userdata 会毁 Android**：`[userdata]` 的 `first_lba 0x2c0000`–`last_lba 0x3b4b7fa` 是 Android `/data`。要么先按官方 `dual_system/partition.py` 从 userdata 尾部切出 `unixnu` 分区，要么全程只用 `fastboot boot` 不落盘。
9. **boot header v2**：cas 的 ABL 要 v2，用 `scripts/cas_bootimg.py`，别照 NX769J 的 v4/v0 结论改。
10. **记录校验**：`porting.toml` 的 `[device].os_profile` 不改，`porting-record` 会拿 17.7.11 的身份去核你的 16.5 证据。

## 6. 下一步（按顺序做，别跳）

1. 跑通 S1，把 `status --json` 存下来；
2. 备好 16.5 IPSW，跑 S2，确认 kernelcache pin 对上；
3. `build kernel` 过编译（这一步最容易在 linux-clang 补丁上炸，系列里已带 4 个）；
4. `fastboot boot` 到 DarwinBoot 交接；
5. 用 boot-progress / NC mailbox 定位第一个 panic；
6. 再谈 UFS 根卷和显示。


## 构建产物（2026-11-22）

| 产物 | 尺寸 | sha256 |
| --- | --- | --- |
| `boot.img` | 101511168 | `1f14cc0f84ca8717054e8f37568f7fda4bf9a0a3622ad01b46c91f16b91a3af2` |
| `SILICIUM_UEFI.fd` | 8388608 | `11f034c9dc403a0d2a2e40a3f12b1e8d0bf11ee011d753048bca45549234a38e` |
| `payload.img` | 100663296 | `381c68d50331d198353e575b46382289058d6664942167644046eb694d5ea8d1` |
| `kernel.macho` | — | `386f10ac80fffd8a9ff19af8723dcb543c42452be80b47a7e03b036a8f0ea49c` |

固件来自 `uefi-cas` 的 `main` 分支（`cas` 分支缺 `BootShim/CasBootLog.S`，且没有
`casPkg/cas-upstream.dsc`）。stock DTB 用本机手机 boot.img 的第 2 个 DTB
（533297 字节，sha256 `d7dcb539…`），`Resources/Configs/cas.toml` 的三个 pin 已按它更新；
上游 pin（536890 字节）属于作者那台机器的 ROM 版本。

刷入：`fastboot boot boot.img`（临时启动，不写 flash）。
