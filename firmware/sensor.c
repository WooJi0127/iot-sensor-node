/*
 * sensor.c — 传感器驱动桩实现
 *
 * 移植说明（STM32 + HAL）：
 *   - sensor_read_th: 用 HAL_GPIO 读 DHT22 单总线时序，或 HAL_I2C 读 AHT20
 *   - sensor_read_lux: 用 HAL_I2C 向 BH1750 发 0x23（连续高分辨率）后读 2 字节
 * 当前为可编译的桩，返回带轻微噪声的"环境基准值"，便于无硬件时联调上位机。
 */
#include "sensor.h"
#include <math.h>
#include <stdlib.h>

bool sensors_init(void)
{
    /* 真实板子：MX_I2C1_Init(); HAL_Delay(20); 等 */
    return true;
}

bool sensor_read_th(float *temp_c, float *hum_pct)
{
    static float t = 24.0f;
    t += (float)((rand() % 100) / 100.0 - 0.5) * 0.4f;   /* 模拟抖动 */
    *temp_c = t;
    *hum_pct = 55.0f + (float)((rand() % 100) / 100.0 - 0.5) * 3.0f;
    return true;
}

bool sensor_read_lux(float *lux)
{
    *lux = 420.0f + (float)((rand() % 100) / 100.0 - 0.5) * 30.0f;
    return true;
}

