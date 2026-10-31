/* Reference acquisition loop. PC_BUILD validates JSON only, with no MQTT network. */
#if defined(PC_BUILD) && !defined(_WIN32)
#define _POSIX_C_SOURCE 200809L
#endif
#include "protocol.h"
#include "sensor.h"
#include "mqtt_at.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#ifdef PC_BUILD
#ifdef _WIN32
#include <windows.h>
static void delay_ms(int ms) { Sleep((DWORD)ms); }
#else
static void delay_ms(int ms) {
    struct timespec delay = {ms / 1000, (ms % 1000) * 1000000L};
    nanosleep(&delay, NULL);
}
#endif
#else
#include "cmsis_os.h"
/* Board integrator must provide RTC/NTP-derived Unix milliseconds, NOT ticks. */
extern int64_t device_unix_time_ms(void);
#define delay_ms(ms) osDelay(ms)
#endif

static sensor_frame_t make_frame(float temp, float hum, float lux) {
    sensor_frame_t frame = {0};
    memcpy(frame.id, NODE_ID, sizeof(NODE_ID));
    memcpy(frame.name, NODE_NAME, sizeof(NODE_NAME));
#ifdef PC_BUILD
    static int64_t last = 0;
    struct timespec now;
    timespec_get(&now, TIME_UTC);
    frame.ts = (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
    if (frame.ts <= last) frame.ts = last + 1;
    last = frame.ts;
#else
    frame.ts = device_unix_time_ms();
#endif
    frame.temp = temp; frame.hum = hum; frame.lux = lux;
    frame.anomaly = 0;
    return frame;
}

static int publish_sample(void) {
    float temp, hum, lux;
    if (!sensor_read_th(&temp, &hum) || !sensor_read_lux(&lux)) return 1;
    sensor_frame_t frame = make_frame(temp, hum, lux);
    if (!mqtt_publish_frame(&frame)) return 1;
    uart_send_frame(&frame);
    return 0;
}

#ifdef PC_BUILD
int main(int argc, char **argv) {
    long frames = 0; /* no arguments: continuous, 1 second between frames */
    if (argc != 1) {
        char *end;
        if (argc != 3 || strcmp(argv[1], "--frames") != 0) return 2;
        errno = 0;
        frames = strtol(argv[2], &end, 10);
        if (errno || *end || end == argv[2] || frames <= 0 || frames > 100000) return 2;
    }
    if (!sensors_init() || !mqtt_connect("", "", "", 0)) return 1;
    for (long count = 0; frames == 0 || count < frames; ++count) {
        if (publish_sample()) return 1;
        if (frames == 0) delay_ms(1000);
    }
    return 0;
}
#else
static void sensor_task(void *arg) {
    (void)arg;
    sensors_init();
    if (!mqtt_connect("YOUR_SSID", "YOUR_PSK", "YOUR_BROKER", 1883)) return;
    for (;;) { publish_sample(); delay_ms(1000); }
}
/* HAL startup, pin mapping and RTOS creation belong in the board project. */
#endif
