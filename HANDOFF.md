# cas + iOS 16.5：准备状态与交接

生成时间：2026-11-22。目标：小米 10 Ultra（cas / SM8250，已解 BL）跑 iOS 16.5 (20F66)。

## 一、已经做完的（本机实测）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| UniXNU 框架 | 已克隆 `UnixNU/`（HEAD `8542980 docs: refresh device records`） | `git log --oneline -1` |
| iOS 16.5 profile | 已装进 `UnixNU/profiles/os/ios-16.5-20F66/` | `profiles/os/` 里与 ipados-17.7.11 并列 |
| 板级仓库 | 已组装 `UniXNU-cas/`：`board.toml`、64 个补丁、`os-profiles/`、3 个脚本 | 覆盖自 `cas-ios16.5/` |
| 配置解析 | `./unixnu defconfig cas_defconfig --device ../UniXNU-cas` 通过 | `out/cas/ios-16.5-20F66/cas/.config` |
| OS 片段合并 | ios.config 的键确实进了 `.config`：`TRUST_CACHE_RUNTIME=y`、`NATIVE_CS_HASH_CACHE=y`、`CRYPTO_BOOTSTRAP="prelinked"`；`SOURCE_MOCKFS` 被 profile 关掉 | `grep` 结果，见下 |
| 无用归档清理 | 因为 mockfs 关掉，`build-mockfs-fixture.py` 已从 `[kernel].archives` 删除（否则白跑一个可能失败的阶段） | `board.toml` |
| 补丁系列 | xnu-8796.101.5 上串行应用 **64/64 成功** | `applied=64 failed=0`（本机 `xnu-gate/`） |
| 源码 fetch | 进行中/已完成：sm8250-common、drivers/*、xnu@`aca3bea` … | `/tmp/cas-fetch2.log` |
| 日志脚本 | `cas-ios16.5/scripts/grab-logs.sh`（dmesg / pstore / NC mailbox / GPT） | `sh -n` 通过 |
| 启动脚本 | `cas-ios16.5/scripts/bringup.sh`（fastboot boot + 等设备回来 + 自动抓日志） | `sh -n` 通过 |

## 二、三个拦截点（需要你决定）

### 1. 这台机器没有编译器，且不能 sudo

```
clang  MISSING      make  MISSING     dtc  MISSING
lz4    MISSING      mtools MISSING    sudo -n → interactive authentication required
```

UniXNU 在 Linux 上构建内核要 `scripts/linux/setup-toolchain.py`：它从源码编一份带
`__builtin_xnu_type_*` 的 clang（llvm-project `58c46bae`）、cctools-port 1030.6.3-ld64-956.6、
mig、iig、lzfse，装到 `/opt/unixnu-linux`。这一步本身要 apt 装 `build-essential llvm-dev
libclang-dev device-tree-compiler ninja-build mtools` 等，必须先有 root。

**要你做的**：给一个可用的 sudo 口令（或你自己跑 `sudo -v` 留下凭证），我就后台开跑；
LLVM 源码编译在这台 8 核 aarch64 上大约 1–3 小时。

### 2. 这台机器没有 USB 主机

```
/dev/bus/usb          → 不存在
/sys/bus/usb/devices  → 空
adb devices / fastboot devices → 都为空
dmesg → qcom_battmgr.pmic_glink_power_supply ...（本机是 erhai/SM8750 上的 aarch64 Linux）
```

也就是说：**手机插到这台机器上不会出现**，`fastboot flash/boot` 在这里跑不了。

两条出路：
- **刷机放到有 USB 的电脑上**（Windows/Linux 都行），我给你成品 `boot.img` 和一条 `fastboot boot`；
- 或者你确认这台设备的 USB-C 能出 host 模式（OTG），插上后我再查一次 `/dev/bus/usb`。

### 3. 没有 16.5 的 IPSW

需要 `iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw`（约 5 GB，ipsw.me → iPhone10,3 → 16.5 → 20F66）。
没有它：kernelcache 拿不到 → `emit-prelink-cas.py` 无法校验 Libm 池 → `payload` 产不出
`kernel.macho.adt` → **没有可刷的镜像**。profile 里的 pin（`e6fa7559…dad5`、30 个 roots、
2 个 trust cache 哈希）都是围绕这个构建写死的。

**要你做的**：把 IPSW 放到某个目录，告诉我路径（或 `UNIXNU_IPSW` 指过去）。

## 三、日志怎么拿（即使这台机器没有 USB）

镜像刷上去、XNU 挂掉之后，Android 会重启回来，日志留在 **pstore/ramoops**：

```sh
adb connect <手机IP>:5555          # 手机先 adb tcpip 5555（root）
./scripts/grab-logs.sh logs/cas-01 <手机IP>:5555
```

`grab-logs.sh` 会抓：
- `dmesg.txt`：当次启动的 Android 内核日志（含上一次重启的原因、`ramoops` 搬运记录）；
- `pstore.txt`：`/sys/fs/pstore/ramoops-*` 里的 XNU panic 原文（**最关键**）；
- `last_kmsg.txt`、`cmdline.txt`、`gpt.txt`（userdata 边界复核）；
- `mailbox.txt`：`0x9f960000` 那块 NC mailbox（`CAS_ENTRY_TRACE` 写的 magic `"CAS H0"` 与阶段值），用 `/dev/mem` 直接读。

刷机前后统一用 `bringup.sh`：它会保存 `fastboot getvar all`、`fastboot boot` 的输出，并在设备回到 Android 时自动调 `grab-logs.sh`。

## 四、下面这些命令是"镜像一出来就能跑"的

```sh
# 本机（构建）
cd UnixNU
./unixnu defconfig cas_defconfig --device ../UniXNU-cas
./unixnu fetch    --device ../UniXNU-cas
./unixnu status   --device ../UniXNU-cas --json
./unixnu tree     --device ../UniXNU-cas
UNIXNU_IPSW=/path/to/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw \
  ./unixnu ipsw fetch --device ../UniXNU-cas
./unixnu build kernel --device ../UniXNU-cas
./unixnu payload      --device ../UniXNU-cas
cd ../UniXNU-cas && python3 scripts/cas_bootimg.py

# 有 USB 的电脑（刷机 + 抓日志）
fastboot boot boot.img
# 设备回到 Android 后
adb connect <IP>:5555
./scripts/grab-logs.sh
```

## 五、当前风险

1. **构建可能在这里跑不动**：aarch64 主机 + 自编 LLVM，`cctools-port` 在 aarch64 上的
   构建未在本机验证过（上游 CI 是 x86_64）。若失败，退到 macOS 或 x86_64 Linux 构建。
2. **`emit-prelink-cas.py` 的 Libm 池是按 iPhone10,3 / 20F66 量的**。换构建号会主动报错停下，
   这是设计。
3. **cas 自己的 `cas-continuous-cpu0.patch` 在 8796 上打不上**（`osfmk/arm/arm_init.c:617`），
   已从系列中移除，需要时按 `XNU_WORK` 流程重做。
4. **`[userdata]` 会覆盖 Android /data**。先只用 `fastboot boot`（不落盘），或按官方
   `dual_system/partition.py` 切独立 `unixnu` 分区。
