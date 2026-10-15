#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iot-sensor-node 启动入口

用法：
    python run.py                 # 默认端口 8000
    SENSOR_PORT=9000 python run.py # 自定义端口
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator.sensor_sim import main

if __name__ == "__main__":
    main()
