# 固件（STM32 + FreeRTOS 参考实现）

本目录是**真实硬件**一侧的代码：在 STM32 上采集温湿度/光照，并通过 ESP-AT 模组走 MQTT 上报，与 `simulator/` 共用 `protocol.h` 的数据帧格式，因此**软件模拟器和真实板子可以无缝共用同一套看板与异常检测服务**。

## 硬件清单（示例）
- MCU：STM32F407 / F103 系列
- 温湿度：DHT22 或 AHT20（I2C / 单总线）
- 光照：BH1750（I2C）
- 联网：ESP-01S（ESP8266 AT 固件）接 USART

## 目录
| 文件 | 说明 |
|---|---|
| `main.c` | FreeRTOS 采样任务 + 上报主循环 |
| `sensor.c/.h` | 传感器驱动接口与桩（便于 PC 联调） |
| `protocol.h/.c` | 数据帧格式 + JSON 序列化（与模拟器对齐） |
| `mqtt_at.c/.h` | ESP-AT 指令封装（WiFi + MQTT 发布） |
| `CMakeLists.txt` | 构建脚本（含 PC 联调选项） |

## 快速验证（无需硬件）
```bash
# 用 GCC 在电脑上编译联调，验证协议与上位机对接
gcc main.c sensor.c protocol.c mqtt_at.c -o node_demo -DPC_BUILD
./node_demo
# 输出示例：{"id":"node-A","name":"实验室-01","ts":...,"temp":24.12,"hum":55.3,"lux":418.0,"anomaly":0}
```

## 移植到真实板子
1. 用 STM32CubeMX 生成 `MX_*` 初始化（`I2C1`、`USART2`、`GPIO`、`SystemClock`）。
2. 把 `sensor.c` 里的 `sensor_read_th/lux` 替换为 HAL_I2C / HAL_GPIO 真实读写。
3. `mqtt_at.c` 的 `at_send` 替换为 `HAL_UART_Transmit/Receive` 并解析 `OK/ERROR`。
4. `arm-none-eabi-gcc` + OpenOCD / STM32CubeProgrammer 烧录。

> 固件默认 `anomaly=0`，异常判定交给边缘侧（`edge-anomaly-llm`）或云端，符合"端-边-云"分工。
