import time
import threading
import os
import gc
import asyncio
import signal
from typing import Optional, Dict
import logging
import numpy as np
from collections import deque
from kos_zbot.actuator import SCSMotorController, NoActuatorsFoundError
from kos_zbot.imu import BNO055Manager, IMUNotAvailableError
from kos_zbot.provider import ModelProvider
from kos_zbot.utils.logging import get_logger, KOSLoggerSetup, get_log_level
#from kos_zbot.utils.latency import get_tracker
import board
import busio
from datetime import datetime 
import json
import time

class TimingStats:
    """Track timing statistics for a component."""
    
    def __init__(self, name: str, max_samples: int = 1000):
        self.name = name
        self.samples = deque(maxlen=max_samples)
        self.total_time = 0.0
        self.count = 0
        
    def add_sample(self, duration_ns: int):
        """Add a timing sample in nanoseconds."""
        duration_us = duration_ns / 1000.0  # Convert to microseconds
        self.samples.append(duration_us)
        self.total_time += duration_us
        self.count += 1
        
    def get_stats(self) -> Dict:
        """Get timing statistics."""
        if not self.samples:
            return {"name": self.name, "count": 0}
            
        samples_array = np.array(list(self.samples))
        return {
            "name": self.name,
            "count": self.count,
            "mean_us": np.mean(samples_array),
            "std_us": np.std(samples_array),
            "min_us": np.min(samples_array),
            "max_us": np.max(samples_array),
            "p50_us": np.percentile(samples_array, 50),
            "p95_us": np.percentile(samples_array, 95),
            "p99_us": np.percentile(samples_array, 99),
            "total_time_ms": self.total_time / 1000.0
        }
        
    def reset(self):
        """Reset all timing data."""
        self.samples.clear()
        self.total_time = 0.0
        self.count = 0
class PolicyLoop:
    """
    A truly inference loop that handles IMU reading, policy inference,
    and actuator control directly in a single thread with high-precision timing.
    """

    def __init__(
        self,
        actuator_controller: SCSMotorController,
        imu_manager: BNO055Manager = None,
        rate: int = 50,  # Default to 50Hz control rate
    ):
        self.log = get_logger(__name__)
        self.actuator_controller = actuator_controller

        # Control rate and timing
        self.rate = rate
        self.period = 1.0 / rate
        self.PERIOD_NS = int(self.period * 1e9)  # e.g. 20,000,000 ns for 50Hz
        self.SPIN_US = 100  # busy-wait window (µs)
        self.SPIN_NS = self.SPIN_US * 1_000

        # State variables
        self.running = False
        self.thread = None

        # Timing measurement
        self.timing_enabled = True
        self.read_states_timing = TimingStats("read_states")
        self.run_policy_timing = TimingStats("run_policy")
        self.write_commands_timing = TimingStats("write_commands")
        self.control_loop_timing = TimingStats("control_loop")
        self.loop_jitter_timing = TimingStats("loop_jitter")
        
        # Track loop timing
        self.last_loop_time = 0
        self.target_period_us = self.PERIOD_NS / 1000.0  # Convert to microseconds

        # Performance tracking
        #self.latency_tracker = get_tracker("inference_loop")
        #self.latency_tracker.set_period(self.PERIOD_NS)

        # IMU variables
        self.imu_manager = imu_manager
        self.imu_values = {
            "accel": (0.0, 0.0, 0.0),
            "gyro": (0.0, 0.0, 0.0),
            "mag": (0.0, 0.0, 0.0),
            "quat": (0.0, 0.0, 0.0, 0.0),
            "calib": (0, 0, 0, 0),  # sys, gyro, accel, mag
        }

        # Policy variables
        self.policy_active = False
        self.policy_model = None
        self.policy_carry = None
        self.policy_provider = None
        self.action_scale = 0.1
        self.policy_log = []

    def init_policy(self, model_file, model_provider):
        """Initialize policy inference directly in this class."""
        try:
            from kinfer.rust_bindings import PyModelRunner

            self.policy_provider = model_provider
            self.policy_model = PyModelRunner(model_file, model_provider)
            self.policy_carry = self.policy_model.init()
            self.policy_active = True
            self.log.info(f"Loading model: {model_file}")
            return True
        except Exception as e:
            self.log.error(f"Policy initialization failed: {e}")
            self.policy_active = False
            return False

    def stop_policy(self):
        """Stop the policy execution."""
        self.policy_active = False
        self.policy_model = None
        self.policy_carry = None
        self.log.info("Policy stopped")

    def start(self):
        """Start the policy loop."""
        if self.running:
            self.log.warning("Policy loop already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._policy_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the policy loop."""
        if not self.running:
            return

        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        # Print final timing statistics
        self.print_timing_stats()
        
        # Save timing data
        #self._save_timing_data()

        self.imu_manager.stop()

        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"logs/policy_log_{timestamp}.json"
        
        #self.policy_provider.save_logs(filename)
        
        self.log.info(f"Policy logs saved to {filename}")


    def get_timing_stats(self) -> Dict:
        """Get comprehensive timing statistics."""
        return {
            "control_rate_hz": self.rate,
            "target_period_us": self.target_period_us,
            "read_states": self.read_states_timing.get_stats(),
            "run_policy": self.run_policy_timing.get_stats(),
            "write_commands": self.write_commands_timing.get_stats(),
            "control_loop": self.control_loop_timing.get_stats(),
            "loop_jitter": self.loop_jitter_timing.get_stats(),
        }
        
    def print_timing_stats(self):
        """Print timing statistics to log."""
        stats = self.get_timing_stats()
        
        self.log.info("=== TIMING STATISTICS ===")
        self.log.info(f"Target rate: {self.rate}Hz ({self.target_period_us:.1f}µs period)")
        
        for component in ["read_states", "run_policy", "write_commands", "control_loop", "loop_jitter"]:
            s = stats[component]
            if s["count"] > 0:
                self.log.info(
                    f"{s['name']:>15}: "
                    f"mean={s['mean_us']:6.1f}µs "
                    f"std={s['std_us']:5.1f}µs "
                    f"min={s['min_us']:5.1f}µs "
                    f"max={s['max_us']:6.1f}µs "
                    f"p95={s['p95_us']:6.1f}µs "
                    f"p99={s['p99_us']:6.1f}µs "
                    f"({s['count']} samples)"
                )
        
        # Calculate timing budget usage
        total_mean = (stats["read_states"]["mean_us"] + 
                     stats["run_policy"]["mean_us"] + 
                     stats["write_commands"]["mean_us"])
        budget_usage = (total_mean / self.target_period_us) * 100
        
        self.log.info(f"Timing budget usage: {budget_usage:.1f}% ({total_mean:.1f}µs / {self.target_period_us:.1f}µs)")
        
        if stats["loop_jitter"]["count"] > 0:
            jitter_p99 = stats["loop_jitter"]["p99_us"]
            jitter_tolerance = self.target_period_us * 0.1  # 10% tolerance
            if jitter_p99 > jitter_tolerance:
                self.log.warning(f"High jitter detected: p99={jitter_p99:.1f}µs (tolerance: {jitter_tolerance:.1f}µs)")

    def reset_timing_stats(self):
        """Reset all timing statistics."""
        self.read_states_timing.reset()
        self.run_policy_timing.reset() 
        self.write_commands_timing.reset()
        self.control_loop_timing.reset()
        self.loop_jitter_timing.reset()


    def _run_policy(self):
        """Run a single step of policy inference directly."""
        if not self.policy_active or not self.policy_model:
            return

        try:
            self.policy_provider.arrays.clear()
            output, self.policy_carry = self.policy_model.step(self.policy_carry)
            self.policy_model.take_action(output)
        except Exception as e:
            self.log.error(f"Policy inference error: {e}")

    def _policy_loop(self):
        """
        Main synchronous control loop with precise timing that:
        1. Reads IMU values directly
        2. Runs policy inference directly
        3. Reads/writes actuator states directly
        """
        # Try to set real-time priority and CPU affinity
        try:
            # Pin to core 1 (assuming it's available)
            os.sched_setaffinity(0, {1})
            allowed = os.sched_getaffinity(0)
            self.log.info(f"Inference loop running on CPUs: {sorted(allowed)}")

            # Set real-time scheduler if possible
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(80))
        except (AttributeError, PermissionError, ImportError) as e:
            self.log.warning(f"Could not set real-time priority: {e}")

        # Increase GC thresholds to reduce potential jitter
        gc.set_threshold(700, 10, 5)
        
        self.log.info("Warming up")
        warmup_start = time.monotonic_ns()
        warmup_end = warmup_start + int(1e9)
        all_valid = False
        
        while (time.monotonic_ns() < warmup_end or not all_valid) and self.running:
            self.actuator_controller._read_states()
            
            # Check actuator positions
            all_valid = True
            for actuator_id in self.actuator_controller.actuator_ids:
                pos = self.actuator_controller.get_position(actuator_id)
                if pos is None or pos == -180.0:
                    all_valid = False
                    break
                    
            self._run_policy()
            time.sleep(1/self.rate)
        
        self.policy_carry = self.policy_model.init()
        
        # Reset timing stats after warmup
        self.reset_timing_stats()
        self.last_loop_time = time.monotonic_ns()

        self.log.info(f"Starting policy ({self.rate}Hz)")
        next_time = time.monotonic_ns()
        loop_count = 0
        while self.running:
            #self.latency_tracker.record_iteration()

            loop_start = time.monotonic_ns()
             
            # Measure read_states timing
            read_start = time.monotonic_ns()
            self.actuator_controller._read_states()
            read_end = time.monotonic_ns()
            if self.timing_enabled:
                self.read_states_timing.add_sample(read_end - read_start)
            
            # Measure run_policy timing
            policy_start = time.monotonic_ns()
            self._run_policy()
            policy_end = time.monotonic_ns()
            if self.timing_enabled:
                self.run_policy_timing.add_sample(policy_end - policy_start)
            
            # Measure write_commands timing
            write_start = time.monotonic_ns()
            self.actuator_controller._write_commands()
            write_end = time.monotonic_ns()
            if self.timing_enabled:
                self.write_commands_timing.add_sample(write_end - write_start)
                

            # Measure overall control loop timing
            loop_end = time.monotonic_ns()
            if self.timing_enabled:
                self.control_loop_timing.add_sample(loop_end - loop_start)
                
                # Measure loop jitter (deviation from target period)
                if self.last_loop_time > 0:
                    actual_period_ns = loop_start - self.last_loop_time
                    period_error_ns = abs(actual_period_ns - self.PERIOD_NS)
                    self.loop_jitter_timing.add_sample(period_error_ns)
                
                self.last_loop_time = loop_start
                
            # Print stats periodically
            loop_count += 1
            if loop_count % (self.rate * 10) == 0:  # Every 10 seconds
                self.print_timing_stats()
            
            # -- Schedule next tick-
            next_time += self.PERIOD_NS
            now_ns = time.monotonic_ns()
            sleep_ns = next_time - now_ns - self.SPIN_NS

            if sleep_ns > 0:
                time.sleep(sleep_ns / 1e9)

            # Fine spin for the last bit of time
            while time.monotonic_ns() < next_time:
                pass

            # Check for timing issues
            over_ns = time.monotonic_ns() - next_time
            if over_ns > 0:
                next_time = time.monotonic_ns()  # Reset to avoid cascade

                over_us = over_ns / 1_000
                if over_us > 5_000:
                    self.log.error(f"Hard overrun {over_us/1000:.2f} ms")
                elif over_us > 2_000:
                    self.log.warning(f"Overrun {over_us/1000:.2f} ms")
                elif over_us > 500:
                    self.log.warning(f"Minor jitter {over_us/1000:.2f} ms")
                elif over_us > 100:
                    self.log.warning(f"Very minor jitter {over_us/1000:.2f} ms")
                elif over_us > 50:
                    self.log.warning(f"Super Minor jitter {over_us/1000:.4f} ms")
    
async def run_policy_loop(
    model_file=None,
    action_scale=0.1,
    episode_length=30.0,
    device="/dev/ttyAMA5",
    baudrate=1000000,
    rate=50,
):
    """
    Run a inference loop that handles IMU, actuators, and optionally a policy model
    in a single thread with high-precision timing.

    Args:
        model_file: Path to the policy model file (optional)
        action_scale: Scale factor for actions (0.0 to 1.0)
        episode_length: Run episode length in seconds
        device: Serial device for actuator controller
        baudrate: Serial baudrate for actuator controller
        rate: Control loop rate in Hz
    """

    if not KOSLoggerSetup._initialized:
        KOSLoggerSetup.setup(
            log_dir="logs", console_level=get_log_level(), file_level=logging.DEBUG
        )

    log = get_logger(__name__)

    # Initialize actuator controller
    try:
        actuator_controller = SCSMotorController(
            device=device, baudrate=baudrate, rate=rate
        )
    except NoActuatorsFoundError as e:
        log.error("No actuators found!")
        return 1

    # Initialize IMU
    imu_manager = BNO055Manager(update_rate=100)
    imu_manager.start()

    time.sleep(3.0) 

    policy_loop = PolicyLoop(
        actuator_controller=actuator_controller, imu_manager=imu_manager, rate=rate
    )

    stop_event = asyncio.Event()
    def handle_signal(sig, frame):
        log.info(f"Received signal {sig}, stopping")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if model_file:
        try:
            model_provider = ModelProvider(actuator_controller, imu_manager)
            model_provider.set_action_scale(action_scale)
              
            if not policy_loop.init_policy(model_file, model_provider):
                log.error("Failed to initialize policy")
                return 1
        except Exception as e:
            log.error(f"Error initializing policy: {e}")


    policy_loop.start()

    #policy_loop.latency_tracker.reset()
    log.info(f"Policy episode length: {episode_length} seconds")

    try:
        # Wait for the specified episode length or until interrupted
        await asyncio.wait_for(stop_event.wait(), timeout=episode_length)
    except asyncio.TimeoutError:
        log.info(f"Episode completed ({episode_length}s)")
    finally:
        policy_loop.stop()
        position_commands = {}
        for actuator_id in actuator_controller.actuator_ids:
            position_commands[actuator_id] = {"position": 0.0, "velocity": 0.0}

        if position_commands:
            log.info("Moving all joints to zero position")
            actuator_controller.set_targets(position_commands)
            actuator_controller._write_commands()
            time.sleep(1.0)

        imu_manager.stop()
        actuator_controller.stop()
        #policy_loop.latency_tracker.save_latest_snapshot()
        log.info("Deployment complete")

    return 0


def main():
    """
    Command-line entry point for the policy loop.
    This function can be called directly from the CLI.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run dedicated policy loop")
    parser.add_argument("--model", type=str, help="Path to the policy model file")
    parser.add_argument(
        "--action-scale",
        type=float,
        default=0.1,
        help="Scale factor for model outputs (0.0 to 1.0)",
    )
    parser.add_argument(
        "--episode-length", type=float, default=30.0, help="Run episode length in seconds"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="/dev/ttyAMA5",
        help="Serial device for actuator controller",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=1000000,
        help="Serial baudrate for actuator controller",
    )
    parser.add_argument("--rate", type=int, default=50, help="Control loop rate in Hz")

    args = parser.parse_args()

    asyncio.run(
        run_policy_loop(
            model_file=args.model,
            action_scale=args.action_scale,
            episode_length=args.episode_length,
            device=args.device,
            baudrate=args.baudrate,
            rate=args.rate,
        )
    )


if __name__ == "__main__":
    main()
