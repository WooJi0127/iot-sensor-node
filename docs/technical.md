# 技术说明

## 数据流与边界

Python 线程按固定节点顺序调用 `_gen_reading(node, unix_seconds, rng=None)`，随后通过 `_publish` 更新最新值、完整帧历史及订阅队列。前端读取 `/nodes`、`/latest`，再连接 `/stream`；每个节点只接收时间戳严格更新的读数。该策略避免初始快照/重连重复绘图，但时钟回拨后的帧也会被忽略。

现阶段没有真实设备的输入网关，C 主机程序的标准输出也不会自动送入 Python。跨项目检测消费的是 Python `/latest` JSON 数组。

## 契约与时间

帧字段：id/name 为 UTF-8 字符串，ts 为非负 Unix 毫秒整数；temp/hum/lux 为有限数值，单位分别为 °C/%/lux；anomaly 为布尔型模拟标签。模拟序列有噪声和约 4% 的注入事件，并不对应真实环境概率或真实检测性能。

实时采样使用系统时钟；`SENSOR_SEED` 只控制随机序列。要逐帧复现，需使用相同 Python 版本、节点调用顺序、种子和时间序列，例如：

```python
import random
from simulator.sensor_sim import NODES, _gen_reading
rng = random.Random("portfolio-17")
frames = [_gen_reading(NODES[0], t, rng) for t in (100, 101, 102)]
```

Python 随机算法的跨版本细节可能变化，故不声称跨版本逐位一致。非常短的间隔或系统时钟回拨可能产生重复/倒序 ts；消费者按节点去重即可，但会损失这些样本。生产采集应使用经过同步且具有明确质量标记的设备时钟。

C 主机使用 UTC 时钟并在快速有限帧模式把重复毫秒递增为下一毫秒，适合协议测试，不是传感器真实采样精度。板端必须实现 `device_unix_time_ms()`，将 RTC/NTP 时间转成 Unix 毫秒；RTOS tick 既不是 Unix 时间，也不能不经频率换算直接当毫秒。

## SSE 定界与背压

HTTP/1.1 的 SSE 响应不发送 Content-Length，用 Connection: close 表明连接关闭时结束响应。事件以空行分隔，初始数据为数组，此后是对象；每 0.5 秒空闲发送注释心跳。浏览器 EventSource 自动重连，重连后只取得当前快照，没有事件 ID/可靠重放承诺。

每个订阅者队列最多 32 个事件，最多 32 个订阅者；超额返回 HTTP 503。满队列丢弃最早的待发事件，保留最新值。采样线程在短锁内执行非阻塞队列操作，从不等待网络。每个 HTTP 处理线程负责自己的 socket 写入，写入超时 5 秒后清理订阅；操作系统仍有自己的有限 socket 缓冲。本方案展示小规模本地并发，不等于任意连接数下的吞吐保证。

标准库 HTTP 服务适合演示，不含认证、TLS、请求速率限制或生产网关配置。服务沿用 0.0.0.0 绑定，应在可信环境运行。

## 历史与导出

deque 为每节点保留最近 600 个完整帧，三个固定节点合计最多 1800 帧。读取时持锁复制帧，序列化在锁外进行；快照被调用者修改不会改变服务状态。JSON/CSV 共用这个快照路径，列为 id,name,ts,temp,hum,lux,anomaly。节点按 ID 排序，节点内保持采样顺序；不是跨节点全局排序。空 CSV 仍有表头，重启清空历史，不提供数据库或长期审计。

## 主机 C 验证与硬件状态

PC_BUILD 仅编译通用 C 代码，不再引入 ARM 指令集或 STM32 链接脚本，也只保留 mqtt_at.c 一份接口定义。它的 publish 适配器只向 stdout 输出 JSON，不建立网络连接。无参数时每秒输出，`--frames N` 输出 N 帧后退出，N 范围为 1–100000。

`frame_to_json` 成功返回字节数，失败返回 -1 并清空已提供的非空缓冲，调用者检查返回值后才能发布。它转义 JSON 引号、反斜杠与控制字符，拒绝未终止字符串、负时间戳和 NaN/Infinity；字符串需由调用方保证有效 UTF-8。固定结构的 512 字节缓冲覆盖转义后的字段。格式化遵循程序默认 C locale；嵌入到更大宿主时应保持数值格式为 C locale。

非 PC 的传感器、ESP-AT、HAL、RTOS、RTC 与烧录均未验证。ESP-AT 参考接口故意返回失败，直到真实 UART 发送/接收、响应校验、凭证/负载转义、超时与重试被实现。独立 CMake 的非 PC 构建会明确停止，避免把缺少板级支持的骨架误称为可烧录工程。

## 验证方法与实测范围

`python -m unittest discover -s tests -v` 包含状态/HTTP、原生 JS、受限管道编码下的入口启动和 C 主机构建测试。Windows + Python 3.14 + Node.js 24.15 + MSVC 本轮 9 项通过。慢客户端测试建立两条真实 SSE 连接，缩小服务端 socket 缓冲，一个不读消息，另一个持续消费；发布 3000 帧后检查末帧、最新快照、队列界限与断开清理。这是功能回归，不是生产压测。

C 测试实际配置/编译所有主机源文件并运行三帧，检查 JSON 字段、boolean 和唯一 Unix-ms ts；另一个 C harness 检查转义、缓冲截断、非有限值、无终止符/空指针等错误。CMake 可通过 CMAKE 环境变量指定，未安装时本地显示 skip；CI 的 REQUIRE_FIRMWARE_TESTS=1 将工具缺失视为失败。Node.js 未安装时 JS 回归会显示 skip，CI 显式安装 Node。

## 一手资料

- [WHATWG Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)：事件流格式与 EventSource。
- [Python http.server](https://docs.python.org/3/library/http.server.html)：标准库处理器与演示服务器的边界。

