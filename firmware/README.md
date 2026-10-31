# C 固件协议演示与 STM32 移植参考

本目录当前可验证的是 **PC 主机 JSON 协议程序**。sensor.c 返回软件模拟数值，mqtt_at.c 的 PC 适配器将 JSON 写到 stdout。它不连接 WiFi、不访问 MQTT broker，也不会自动将数据送到 Python 服务。

真实 STM32、HAL/CMSIS、ESP-AT 指令状态机、传感器驱动、RTC/NTP 同步与烧录尚未实现或验证。非 PC CMake 构建会给出明确错误，板端集成需放入完整的板级工程。

## 主机构建

需要 CMake 3.20+ 与 C 编译器（GCC/Clang/MSVC），在仓库根目录：

```sh
cmake -S firmware -B build/firmware -DPC_BUILD=ON
cmake --build build/firmware --config Release
./build/firmware/node.elf --frames 3
```

Windows PowerShell / MSVC 多配置构建运行：

```powershell
.\build\firmware\Release\node.exe --frames 3
```

GCC 直接编译也可：

```sh
gcc -std=c11 -Wall -Wextra -Werror -DPC_BUILD firmware/main.c firmware/sensor.c firmware/protocol.c firmware/mqtt_at.c -lm -o node_demo
./node_demo --frames 3
```

`--frames N` 接受 1–100000，立即输出 N 行后退出；无参数时每秒输出一帧。每行都是 JSON，anomaly 为 false，ts 为 Unix 毫秒。主机快速模式为重复毫秒增加 1，仅供协议验证。

## 文件与协议

- main.c：采集/组帧/发布参考及有限帧主机入口。
- sensor.c/.h：可替换的模拟驱动。
- protocol.c/.h：JSON 转义、有限数检查、容量检测；序列化返回字节数或 -1，错误时清空输出。
- mqtt_at.c/.h：PC stdout 适配器，非 PC 接口在未接入真实传输前返回失败。
- CMakeLists.txt：主机 C11 构建；不将 ARM 参数或板级链接脚本带入 PC。

字符串需保证 UTF-8 且在固定数组内终止。传入缓冲不足时不得发布截断内容。设备时钟必须经 RTC/NTP 转成 Unix 毫秒，不可直接使用 RTOS tick。详见 [技术说明](../docs/technical.md)。

## 板端后续接入工作

示例硬件可选 STM32F407/F103、DHT22/AHT20、BH1750 与 ESP 模组，具体适配及兼容性待验证。

1. 生成对应 MCU 的 GPIO/I2C/UART/时钟和 CMSIS/RTOS 初始化，提供链接脚本与工具链。
2. 替换 sensor.c 模拟值，处理真实总线故障和传感器读写时序。
3. 实现 WiFi/MQTT 配置、AT 版本适配、UART 发送接收、响应状态机、负载/凭证转义及重试。
4. 实现 device_unix_time_ms()，约定同步失败处理和时间质量。
5. 配置 Python 输入网关或 MQTT 订阅桥接，随后做板端、网络、上位机端到端测试。当前没有此桥接。
6. 烧录并记录板型、固件/AT 版本与实测结果后，再声明真实硬件能力。

## 第一次看固件目录：怎么使用

**它做什么？** 先在电脑上生成与 Python 读数格式相同的 JSON，方便检查 C 程序发出的数据能否被其他程序理解。

**它怎样执行？** 模拟驱动生成温湿度和光照，主程序添加节点与时间，序列化检查数值、字符串和缓冲大小，最后每行输出一个 JSON。

**怎样启动？** 安装 CMake 和 C 编译器，按上面的主机构建命令运行，再用 `--frames 3` 启动程序；没有编译器时可以先运行仓库根目录的 Python 网页演示。

**怎样判断成功？** 终端恰好输出三行合法 JSON 后退出；完整 Python 测试还会自动编译并解析这三行。这里只证明主机协议路径，接上真实设备需要完成前述移植工作。
