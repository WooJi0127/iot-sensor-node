/*
 * sensor.h — 传感器驱动接口（温湿度 DHT22/AHT20 + 光照 BH1750）
 *
 * 这里给出与硬件无关的接口与"桩"实现，方便在 PC 上编译联调；
 * 移植到 STM32 时，把 *_read() 内部替换为 HAL_I2C / HAL_GPIO 的真实读写即可。
 */
#ifndef SENSOR_H
#define SENSOR_H

#include <stdint.h>
#include <stdbool.h>

/* 初始化所有传感器（I2C / 单总线） */
bool sensors_init(void);

/* 读取温湿度 (°C, %) —— 对接 DHT22 或 AHT20 */
bool sensor_read_th(float *temp_c, float *hum_pct);

/* 读取光照 (lux) —— 对接 BH1750 */
bool sensor_read_lux(float *lux);

#endif /* SENSOR_H */
