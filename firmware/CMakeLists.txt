# CMakeLists.txt — STM32 (STM32Cube + arm-none-eabi) 构建参考
# 依赖：ARM GCC toolchain、CMSIS、HAL 库（按芯片型号替换）
cmake_minimum_required(VERSION 3.20)
project(iot_sensor_node C CXX ASM)

set(MCU cortex-m4)
set(CMAKE_C_FLAGS "-mcpu=${MCU} -mthumb -O2 -Wall")
set(CMAKE_EXE_LINKER_FLAGS "-T${CMAKE_SOURCE_DIR}/STM32F4xx_FLASH.ld")

add_executable(node.elf
    main.c
    sensor.c
    sensor.h
    protocol.c
    protocol.h
    mqtt_at.c
    mqtt_at.h
)

# PC 联调（验证协议/与上位机对接，无需硬件）：
#   mkdir build && cd build && cmake -DPC_BUILD=ON .. && make
option(PC_BUILD "Build for host (protocol/uart sanity check)" OFF)
if(PC_BUILD)
    target_compile_definitions(node.elf PRIVATE PC_BUILD)
    target_link_libraries(node.elf m)
endif()
