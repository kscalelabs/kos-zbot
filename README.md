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
Before using any other commands, you must start the KOS service. You can either start it without robot metadata or for a specific robot.

### Option 1: Start service without robot metadata
```bash
kos service
```

### Option 2: Start service for a specific robot
```bash
kos <robot_name>
```
**When robot metadata is loaded, the system automatically:**
- Sets servo gains (kp, kd, ki) based on robot configuration
- Enforces position and velocity limits for safety
- Applies robot-specific actuator configurations

### Option 3: Run inference for a specific robot
```bash
kos <robot_name> infer --model path/to/model
```

---

## CLI Usage

Get help for any command or subcommand with `-h` or `--help`:

```bash
kos --help
kos status --help
kos actuator --help
kos actuator move --help
kos <robot_name> --help
# etc.
```

---

## Commands Overview

### 1. Start the KOS Service

#### Generic Service (No Robot Metadata)
```bash
kos service
```
- **Description:** Starts the KOS service without robot-specific metadata.
- **Note:** Uses default servo gains and no enforced limits.

#### Robot-Specific Service
```bash
kos <robot_name>
```
- **Description:** Starts the KOS service for a specific robot, loading its metadata.
- **Automatic Configuration:**
  - **Servo Gains:** Sets kp, kd, ki values from robot metadata
  - **Safety Limits:** Enforces position and velocity limits
  - **Actuator Mapping:** Applies robot-specific actuator configurations
  - **Hardware Settings:** Configures communication parameters
- **Example:**
  ```bash
  kos zbot
  ```

#### Robot Inference Mode
```bash
kos <robot_name> infer [OPTIONS]
```
- **Description:** Run a dedicated inference loop for the specified robot.
- **Includes:** All robot-specific configurations (gains, limits, mappings)
- **Options:**
  - `--model PATH`: Path to the policy model file
  - `--action-scale FLOAT`: Scale factor for model outputs (0.0 to 1.0, default: 0.1)
  - `--episode-length FLOAT`: Run episode length in seconds (default: 30.0)
  - `--device STRING`: Serial device for actuator controller (default: /dev/ttyAMA5)
  - `--baudrate INT`: Serial baudrate for actuator controller (default: 1000000)
  - `--rate INT`: Control loop rate in Hz (default: 50)
- **Example:**
  ```bash
  kos zbot infer --model ./policy.onnx --action-scale 0.2 --episode-length 60
  ```

---

### 2. Show Live System Status

```bash
kos status [--scale DEG] [--ip IP]
```
- **Options:**
  - `--scale DEG` (optional, default: 50.0): Max |position| in degrees for bar scaling.
  - `--ip IP` (optional, default: 127.0.0.1): KOS service IP address.
- **Example:**
  ```bash
  kos status --scale 90 --ip 192.168.1.100
  ```

---

### 3. Policy Operations

All policy commands are grouped under `kos policy`.

#### a. Start Policy Deployment

```bash
kos policy start POLICY_FILE [OPTIONS]
```
- **Arguments:**
  - `POLICY_FILE`: Path to the policy file
- **Options:**
  - `--episode-length FLOAT`: Episode length in seconds (default: 30.0)
  - `--action-scale FLOAT`: Scale factor for model outputs (default: 0.1)
  - `--dry-run`: Run policy in dry-run mode (no actuators will be moved)
- **Example:**
  ```bash
  kos policy start ./my_policy.onnx --episode-length 45 --action-scale 0.15
  ```

#### b. Stop Policy Deployment

```bash
kos policy stop
```

#### c. Get Policy Status

```bash
kos policy status
```

---

### 4. Actuator Operations

All actuator commands are grouped under `kos actuator`.

#### a. Move Actuators

```bash
kos actuator move --id IDS --pos POSITION [OPTIONS]
```
- **Required Options:**
  - `--id, --ids IDS`: Actuator IDs (comma-separated or 'all')
  - `--pos, --position POSITION`: Target position in degrees
- **Optional Options:**
  - `--vel, --velocity FLOAT`: Target velocity in degrees/second
  - `--kp FLOAT`: Position gain (overrides robot metadata if specified)
  - `--kd FLOAT`: Velocity gain (overrides robot metadata if specified)
  - `--acceleration FLOAT`: Acceleration
  - `--wait FLOAT`: Seconds to wait for actuators to reach target (default: 3.0)
- **Safety Notes:**
  - When robot metadata is loaded, position and velocity limits are automatically enforced
  - Commands that exceed limits will be clamped to safe ranges
  - Default gains from robot metadata are used unless explicitly overridden
- **Examples:**
  ```bash
  # Move all actuators to 0 degrees
  kos actuator move --id all --pos 0

  # Move actuators 11,12 to 90 degrees at 45 deg/s
  kos actuator move --id 11,12 --pos 90 --vel 45

  # Move actuator 11 to -45 degrees with custom gains
  kos actuator move --id 11 --pos -45 --kp 100 --kd 4
  
  # Move actuators 11,12 to -10 degrees at 2 deg/s
  kos actuator move --pos -10 --vel 2 --id 11,12
  ```

#### b. Enable/Disable Torque

```bash
kos actuator torque ACTION IDS
```
- **Arguments:**
  - `ACTION`: `enable` or `disable`
  - `IDS`: Comma-separated actuator IDs (e.g., `11,12,13`) or `all`
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
  - `IDS`: Comma-separated actuator IDs (e.g., `11,12,13`) or `all`
- **Options:**
  - `--diff`: Only show parameters that differ
- **Examples:**
  ```bash
  kos actuator dump 11,12,13
  kos actuator dump 11,12,13 --diff
  ```

---

### 5. Run Built-in Tests

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

### 6. Run Demonstration Sequences

All demo commands are grouped under `kos demo`.

#### a. Salute Demo

```bash
kos demo salute [OPTIONS]
```
- **Options:**
  - `--duration FLOAT`: Duration of the salute in seconds (default: 5.0)
  - `--amplitude FLOAT`: Salute amplitude in degrees (default: 15.0)
  - `--frequency FLOAT`: Salute frequency in Hz (default: 0.75)
  - `--ip STRING`: KOS service IP address (default: 127.0.0.1)

#### b. Hand Wave Demo

```bash
kos demo hand_wave [OPTIONS]
```
- **Options:**
  - `--duration FLOAT`: Duration of the hand wave in seconds (default: 5.0)
  - `--amplitude FLOAT`: Wave amplitude in degrees (default: 15.0)
  - `--frequency FLOAT`: Wave frequency in Hz (default: 1.5)
  - `--ip STRING`: KOS service IP address (default: 127.0.0.1)

---

## Robot Metadata and Safety

### Automatic Configuration
When you start the service with a robot name (`kos <robot_name>`), the system automatically:

1. **Loads Robot Metadata:**
   - Actuator mappings and configurations
   - Joint limits (position and velocity)
   - Default servo gains (kp, kd, ki)
   - Hardware communication settings

2. **Applies Safety Limits:**
   - Position commands are clamped to safe ranges
   - Velocity commands respect maximum speeds
   - Prevents dangerous movements outside operational limits

3. **Sets Servo Gains:**
   - Configures optimal control gains for each actuator
   - Ensures stable and responsive movement
   - Can be overridden with explicit `--kp` and `--kd` options

### Generic vs Robot-Specific Service
- **Generic Service (`kos service`):** No limits, default gains, manual configuration required
- **Robot-Specific Service (`kos <robot_name>`):** Automatic safety, optimized gains, plug-and-play operation

---

## Example Workflows

### Basic Workflow (Generic Service)

1. **Start the service:**
   ```bash
   kos service
   ```

2. **Check system status:**
   ```bash
   kos status
   ```

3. **Move actuators 11 and 12 to -10 degrees at 2 deg/s:**
   ```bash
   kos actuator move --id 11,12 --pos -10 --vel 2
   ```

4. **Enable torque on actuators 11, 12, 13:**
   ```bash
   kos actuator torque enable 11,12,13
   ```

5. **Zero all actuators:**
   ```bash
   kos actuator zero all
   ```

### Robot-Specific Workflow (Recommended)

1. **Start service for a specific robot (with automatic configuration):**
   ```bash
   kos zbot
   ```
   *This automatically sets gains and enforces limits*

2. **Move actuators safely (limits enforced automatically):**
   ```bash
   kos actuator move --id 11,12 --pos 45 --vel 30
   ```

3. **Run inference with a trained policy:**
   ```bash
   kos zbot infer --model ./trained_policy.onnx --action-scale 0.2
   ```

### Policy Deployment Workflow

1. **Start the service:**
   ```bash
   kos service
   ```

2. **Deploy a policy:**
   ```bash
   kos policy start ./my_policy.onnx --episode-length 60 --action-scale 0.1
   ```

3. **Check policy status:**
   ```bash
   kos policy status
   ```

4. **Stop the policy:**
   ```bash
   kos policy stop
   ```

---

## Help

For more details on any command or subcommand, use the `--help` flag:

```bash
kos --help
kos actuator move --help
kos policy --help
kos zbot --help
kos zbot infer --help
```

---

## Notes

- **Always start a service** (`kos service` or `kos <robot_name>`) before running any actuator, policy, or test commands.
- **Robot-specific service is recommended** for safety and optimal performance.
- **Robot names must match available robot metadata.** Use `kscale robot list` to view available robots.
- **The new actuator move command** uses explicit options (`--id`, `--pos`, `--vel`) which makes negative positions easy to specify.
- **Safety limits are automatically enforced** when robot metadata is loaded.
- **Servo gains are automatically configured** from robot metadata but can be overridden with `--kp` and `--kd` options.
- **All actuator IDs** should be comma-separated (e.g., `11,12,13`).
- **For development,** use the editable install: `pip install -e .`

---

## License

[MIT License](LICENSE)
