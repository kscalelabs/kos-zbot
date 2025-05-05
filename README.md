# kos-zbot

K-OS Operating System

---

## Installation

Install in editable/development mode:

```bash
pip install -e .
```

---

## Quick Start

**IMPORTANT:**  
Before using any other commands, you must start the KOS service. This will connect to the servo network, automatically scan and register available servos, and connect to the IMU.

```bash
kos service
```

---

## CLI Usage

Get help for any command or subcommand with `-h` or `--help`:

```bash
kos --help
kos status --help
kos actuator --help
kos actuator move --help
# etc.
```

---

## Commands Overview

### 1. Start the KOS Service

```bash
kos service
```
- **Description:** Starts the KOS service, connects to the servo network, scans and registers servos, and connects to the IMU.
- **Run this first before any other command!**

---

### 2. Show Live System Status

```bash
kos status [--scale DEG]
```
- **Arguments:**
  - `--scale DEG` (optional, default: 50.0): Max |position| in degrees for bar scaling.
- **Example:**
  ```bash
  kos status --scale 90
  ```

---

### 3. Actuator Operations

All actuator commands are grouped under `kos actuator`.

#### a. Move Actuators

```bash
kos actuator move IDS POS1 [POS2 ...] [OPTIONS]
```
- **Arguments:**
  - `IDS`: Comma-separated actuator IDs (e.g., `11,12,13`)
  - `POS1 [POS2 ...]`: Target positions (float, in degrees) for each actuator
- **Options:**
  - `--kp FLOAT`: Position gain (optional)
  - `--kd FLOAT`: Velocity gain (optional)
  - `--acceleration FLOAT`: Acceleration (optional)
  - `--wait FLOAT`: Seconds to wait for actuators to reach target (default: 3.0)
- **Examples:**
  ```bash
  kos actuator move 11,12 10.0 20.0
  kos actuator move 11 15.0 --kp 30 --kd 10 --acceleration 500 --wait 5
  ```

#### b. Enable/Disable Torque

```bash
kos actuator torque ACTION IDS
```
- **Arguments:**
  - `ACTION`: `enable` or `disable`
  - `IDS`: Comma-separated actuator IDs (e.g., `11,12,13`)
- **Examples:**
  ```bash
  kos actuator torque enable 11,12,13
  kos actuator torque disable 21
  ```

#### c. Zero Actuators

```bash
kos actuator zero IDS
```
- **Arguments:**
  - `IDS`: Comma-separated actuator IDs (e.g., `11,12,13`) or `all`
- **Examples:**
  ```bash
  kos actuator zero 11,12,13
  kos actuator zero all
  ```

#### d. Dump Actuator Parameters

```bash
kos actuator dump IDS [--diff]
```
- **Arguments:**
  - `IDS`: Comma-separated actuator IDs (e.g., `11,12,13`)
- **Options:**
  - `--diff`: Only show parameters that differ
- **Examples:**
  ```bash
  kos actuator dump 11,12,13
  kos actuator dump 11,12,13 --diff
  ```

---

### 4. Run Built-in Tests

All test commands are grouped under `kos test`.

#### a. Sine Wave Test

```bash
kos test sync_wave
```
- **Description:** Runs a sine wave test on a predefined set of actuators.

#### b. Step Test

```bash
kos test sync_step
```
- **Description:** Runs a step test on a predefined set of actuators.

#### c. IMU Test

```bash
kos test imu
```
- **Description:** Runs the IMU test (currently a placeholder).

---

## Example Workflow

1. **Start the service:**
   ```bash
   kos service
   ```

2. **Check system status:**
   ```bash
   kos status
   ```

3. **Move actuators 11 and 12 to positions 10 and 20 degrees:**
   ```bash
   kos actuator move 11,12 10 20
   ```

4. **Enable torque on actuators 11, 12, 13:**
   ```bash
   kos actuator torque enable 11,12,13
   ```

5. **Zero all actuators:**
   ```bash
   kos actuator zero all
   ```

6. **Dump parameters for actuators 11, 12, 13, showing only differences:**
   ```bash
   kos actuator dump 11,12,13 --diff
   ```

7. **Run the step test:**
   ```bash
   kos test sync_step
   ```

---

## Help

For more details on any command or subcommand, use the `--help` flag:

```bash
kos actuator move --help
kos actuator torque --help
kos test --help
```

---

## Notes

- Always start the service (`kos service`) before running any actuator or test commands.
- All actuator IDs should be comma-separated (e.g., `11,12,13`).
- For development, use the editable install: `pip install -e .`

---

## License

[MIT License](LICENSE)