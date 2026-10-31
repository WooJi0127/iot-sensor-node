# iot-sensor-node · 环境监测软件演示

用 Python 模拟实验室、温室、机房三个传感器节点，通过 SSE 把温度、湿度、光照推到原生 Canvas 看板。也提供最新快照和历史导出，可与 [edge-anomaly-llm](https://github.com/WooJi0127/edge-anomaly-llm) 联动。

软件服务只需 Python 3.10+，无需 pip 安装、设备或云账户。C 固件目录是协议演示及 STM32 移植参考；**没有验证真实传感器、STM32 烧录、ESP-AT 或 MQTT 网络链路**。

## 三分钟启动

从仓库根目录运行，两种 shell 都支持：

```text
python run.py
```

浏览器打开 <http://localhost:8000/>。应出现三个节点卡片，状态为“已连接”，曲线持续增加。点击“导出历史 CSV”可保存本次进程收集的数据。Ctrl+C 停止。

Windows PowerShell 可配置端口、间隔和随机种子：

```powershell
$env:SENSOR_PORT = "8000"
$env:SENSOR_INTERVAL = "1"
$env:SENSOR_SEED = "portfolio-17"
python run.py
# 另一个终端读取快照：
Invoke-RestMethod http://localhost:8000/latest
Invoke-WebRequest http://localhost:8000/history.csv -OutFile sensor-history.csv
```

POSIX shell：

```sh
SENSOR_PORT=8000 SENSOR_INTERVAL=1 SENSOR_SEED=portfolio-17 python run.py
# 另一个终端：
curl http://localhost:8000/latest
curl -o sensor-history.csv http://localhost:8000/history.csv
curl -N http://localhost:8000/stream
```

默认间隔 1 秒，必须为有限正数。服务沿用绑定 `0.0.0.0`，用于可信的本地演示；Python http.server 未提供生产级部署能力。

## 能展示什么

- 三节点周期变化、噪声及约 4% 的模拟异常标签；标签用于演示，不是检测结论。
- 有界 SSE 队列，慢客户端丢弃最早待发事件，采样线程不执行网络写入。
- 看板按节点使用不同颜色与线型，显示单位，忽略重复/倒序时间戳，断线自动重连。
- 每节点最多 600 帧的内存历史，导出完整 JSON/CSV；重启清空。
- 注入独立随机数发生器与时间，复现相同测试序列。服务仅固定种子仍会使用当前时间，不能保证两次实时运行逐字相同。
- C 主机程序生成有限帧 JSON，自动验证布尔类型、时间戳、字符串转义及缓冲不足处理。

## 数据与接口

| 路径 | 响应 |
| --- | --- |
| `/` | 自带看板，无 CDN |
| `/nodes` | 节点定义 |
| `/latest` | 各节点最新帧组成的 JSON 数组，原接口保留 |
| `/stream` | SSE：初始快照为数组，后续每个事件为单帧对象 |
| `/history` | 完整历史帧的 JSON 数组，按节点 ID、节点内采样顺序排列 |
| `/history.csv` | UTF-8 CSV，列为 id,name,ts,temp,hum,lux,anomaly |

```json
{"id":"node-A","name":"实验室-01","ts":1793400000000,"temp":24.12,"hum":55.3,"lux":418.0,"anomaly":false}
```

`ts` 是 Unix 毫秒；temp 为 °C、hum 为 %、lux 为 lux，anomaly 为 JSON boolean。CSV 的布尔值写作 `true/false`。每次导出先在锁内获取完整快照再编码；采样期间分别请求两个导出端点，内容可能相差新到的帧。

## 验证

```text
python -m unittest discover -s tests -v
```

Python 测试覆盖确定性、历史容量/快照隔离/CSV、连续 SSE 事件、慢/快 HTTP 客户端和断开清理。安装 Node.js 时还会执行真实看板脚本的去重/颜色/重连回归；安装 CMake 与 C 编译器时会编译并检查主机固件。缺少工具会显示 skip；CI 要求主机固件测试通过，不能静默跳过。

主机协议演示（CMake + GCC/Clang 或 MSVC；无需硬件）：

```sh
cmake -S firmware -B build/firmware -DPC_BUILD=ON
cmake --build build/firmware --config Release
# Linux/macOS:
./build/firmware/node.elf --frames 3
```

PowerShell/MSVC 多配置生成器的运行命令：

```powershell
.\build\firmware\Release\node.exe --frames 3
# CMake 不在 PATH 时，可在测试前指定它的完整路径：
$env:CMAKE = "C:\path\to\cmake.exe"
python -m unittest discover -s tests -v
```

本轮本地实测：Windows、Python 3.14、Node.js 24.15、CMake/MSVC，9 项测试通过，包含实际 C 编译、有限帧 JSON 解析和受限终端编码下的启动。Linux 与 Python 3.10/3.14 的工作流见 [.github/workflows/ci.yml](.github/workflows/ci.yml)，远程结果以 Actions 为准。

## 技术与展示材料

- [技术说明](docs/technical.md)：数据契约、并发/缓冲策略、时钟和硬件限制。
- [60–90 秒演示与面试问题](docs/demo.md)。
- [固件移植参考](firmware/README.md)。
- 相关项目：[edge-anomaly-llm](https://github.com/WooJi0127/edge-anomaly-llm)、[llm-rag-kb](https://github.com/WooJi0127/llm-rag-kb)。
- [MIT License](LICENSE)。

后续可增加 CO₂、土壤湿度或真实设备接入；当前没有串口接收、MQTT broker 订阅、持久化或历史回放。

## 第一次看这个项目：它怎样工作

**主要做什么？** 它在电脑里模拟三个环境监测设备，让你看到不同地点的温度、湿度和光照怎样变化，也能把这些读数交给异常检测项目。没有传感器也能运行。

**执行流程是什么？** 程序每隔一段时间生成三个节点的读数，把最新值和最近的历史保存在内存里，再通过持续连接发给浏览器。网页把读数显示为卡片和折线；导出按钮把当前保留的历史保存为 CSV。红色异常提示来自模拟器预设的标签。

**怎样启动？** 安装 Python 3.10 或更新版本，进入项目文件夹，在终端输入 `python run.py`，然后打开 `http://localhost:8000/`。先运行 Python 演示即可，C 固件不是启动网页的前提。

**怎样判断成功？** 网页出现三个节点，状态显示“已连接”，卡片数值和曲线继续变化；访问 `/latest` 能看到读数，下载 CSV 后能看到包含节点和时间的数据行。终端执行测试命令看到通过结果，可以进一步确认核心功能；出现 skip 表示该项没有在当前电脑验证。
