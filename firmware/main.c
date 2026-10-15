/*
 * main.c — 智慧环境监测终端固件（STM32 + FreeRTOS 参考实现）
 *
 * 数据流：传感器采集 -> 组帧 -> 通过 ESP-AT(MQTT) 或 UART 上报
 * 与 simulator/sensor_sim.py 共用 protocol.h 的帧格式。
 *
 * 编译（PC 联调桩，验证协议与上位机对接）：
 *   gcc main.c sensor.c mqtt_at.c -o node_demo -DPC_BUILD
 * 烧录（真实板子）：
 *   arm-none-eabi-gcc + OpenOCD / STM32CubeProgrammer
 */
#include "protocol.h"
#include "sensor.h"
#include "mqtt_at.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef PC_BUILD
/* PC 联调：用标准库实现一个最小 mqtt_at 桩 */
bool mqtt_connect(const char *ssid, const char *psk, const char *broker, int port)
{ (void)ssid;(void)psk;(void)broker;(void)port; return true; }
bool mqtt_publish_frame(const sensor_frame_t *f)
{ char buf[160]; frame_to_json(f, buf, sizeof(buf)); printf("%s\n", buf); return true; }
void uart_send_frame(const sensor_frame_t *f)
{ char buf[160]; frame_to_json(f, buf, sizeof(buf)); printf("[UART] %s\n", buf); }

static void delay_ms(int ms){ struct timespec ts={ms/1000,(ms%1000)*1000000}; nanosleep(&ts,0); }
#else
#include "cmsis_os.h"   /* FreeRTOS / CMSIS 封装 */
#define delay_ms(ms) osDelay(ms)
#endif

/* 采样周期（ms），与模拟器 PUSH_INTERVAL 对齐 */
#define SAMPLE_PERIOD_MS 1000

static sensor_frame_t make_frame(float temp, float hum, float lux)
{
    sensor_frame_t f;
    memset(&f, 0, sizeof(f));
    strncpy(f.id, NODE_ID, sizeof(f.id) - 1);
    strncpy(f.name, NODE_NAME, sizeof(f.name) - 1);
#ifdef PC_BUILD
    f.ts = (int64_t)time(NULL) * 1000;
#else
    f.ts = (int64_t)osKernelGetTickCount();   /* 真实板子用 RTC/系统节拍 */
#endif
    f.temp = temp; f.hum = hum; f.lux = lux; f.anomaly = 0;
    return f;
}

static void sensor_task(void *arg)
{
    (void)arg;
    float temp, hum, lux;
    sensors_init();
    mqtt_connect("YOUR_SSID", "YOUR_PSK", "broker.emqx.io", 1883);

    for (;;) {
        if (sensor_read_th(&temp, &hum) && sensor_read_lux(&lux)) {
            sensor_frame_t f = make_frame(temp, hum, lux);
            mqtt_publish_frame(&f);   /* 走 MQTT */
            uart_send_frame(&f);      /* 同时打串口，便于调试 */
        }
        delay_ms(SAMPLE_PERIOD_MS);
    }
}

#ifdef PC_BUILD
int main(void)
{
    printf("=== iot-sensor-node firmware (PC build / 协议联调) ===\n");
    sensor_task(NULL);
    return 0;
}
#else
int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init(); MX_I2C1_Init(); MX_USART2_UART_Init();
    osKernelInitialize();
    osThreadNew(sensor_task, NULL, NULL);
    osKernelStart();
    for (;;) {}
}
#endif
