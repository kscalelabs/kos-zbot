import asyncio
import matplotlib.pyplot as plt
from pykos import KOS
from collections import defaultdict
import time



class ServoPositionPlotter:
    def __init__(self, ip="192.168.113.131", poll_rate_hz=100):
        self.kos = KOS(ip)
        self.poll_interval = 1.0 / poll_rate_hz
        
        self.servo_ids = [
            11, 12, 13, 14,  # Left Arm
            21, 22, 23, 24,  # Right Arm
            31, 32, 33, 34, 35, 36,  # Left Leg
            41, 42, 43, 44, 45, 46,  # Right Legwa
        ]
        
        # Initialize empty sets/dicts for dynamic servo tracking
        self.active_servo_ids = set()
        self.lines = {}
        self.positions = defaultdict(list)
        self.timestamps = []
        
        plt.ion() 
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Position (degrees)')
        self.ax.set_title('Servo Positions Over Time')
        self.ax.grid(True)
        
        self.fig.subplots_adjust(left=0.25, 
                                right=0.95,
                                top=0.95,
                                bottom=0.1) 
        self.start_time = None

    async def poll_positions(self, duration_seconds=30):
        self.start_time = time.time()
        
        try:
            while time.time() - self.start_time < duration_seconds:
                try:
                    # Query all possible servos but only plot the ones that respond
                    response = await self.kos.actuator.get_actuators_state(self.servo_ids)
                    current_time = time.time() - self.start_time
                    
                    self.timestamps.append(current_time)
                    
                    for state in response.states:
                        servo_id = state.actuator_id
                        if abs(state.position) < 1e-6:
                            continue

                        # Add new servo if we haven't seen it before
                        if servo_id not in self.active_servo_ids:
                            self._add_new_servo(servo_id)
                        self.positions[servo_id].append(state.position)

                    # Update plot
                    self._update_plot()
                    
                    # Wait for next polling interval
                    await asyncio.sleep(self.poll_interval)
                    
                except Exception as e:
                    print(f"Error polling positions: {e}")
                    break
        except KeyboardInterrupt:
            print("\nStopping data collection...")
        finally:
            plt.ioff()

    def _add_new_servo(self, servo_id):
        """Add a new servo line to the plot"""
        if servo_id not in self.lines:
            line, = self.ax.plot([], [], label=f'Servo {servo_id}')
            self.lines[servo_id] = line
            self.active_servo_ids.add(servo_id)
            # Update legend with only active servos
            handles = [self.lines[sid] for sid in sorted(self.active_servo_ids)]
            labels = [f'Servo {sid}' for sid in sorted(self.active_servo_ids)]
            self.ax.legend(handles, labels, 
                          bbox_to_anchor=(-0.2, 0.5),
                          loc='center right',
                          borderaxespad=0)
    
    def _update_plot(self):
        # Update each line with new data
        for servo_id, line in self.lines.items():
            line.set_xdata(self.timestamps)
            line.set_ydata(self.positions[servo_id])
        
        # Adjust plot limits
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()  

async def main():
    plotter = ServoPositionPlotter(poll_rate_hz=50)
    try:
        await plotter.poll_positions(duration_seconds=60)
    except KeyboardInterrupt:
        pass
    
    plt.ioff()
    plt.show()

if __name__ == "__main__":
    asyncio.run(main())