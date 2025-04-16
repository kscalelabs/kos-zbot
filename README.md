# kos-zbot

Run KOS
```
python -m kos_zbot.kos
```

Tests
```
python -m kos_zbot.tests.sync_step
```

Tools
```
Compare Servo Parameters
python -m kos_zbot.tools.feetech_compare --device /dev/ttyAMA5 --baudrate 500000 --ids 11,12,13,14

Get Servo Status Report
python -m kos_zbot.tools.feetech_report --ids 11,12,13,14
./feetech_report.py --ids 11,12,13,14 --watch --interval 1.0

Zero Servo Positions
./feetech_zero.py --device /dev/ttyUSB0 --baudrate 500000 --ids 11,12,13,14

```