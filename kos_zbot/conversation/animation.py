import multiprocessing as mp
from multiprocessing import Queue, Process
import pickle
from kos_zbot.scripts.hello_wave import run_sine_test
from kos_zbot.scripts.salute import salute as salute_func
from kos_zbot.scripts.squat import play_keyframes as squat_func
from kos_zbot.scripts.ymca import play_keyframes as ymca_func

class AnimationController:
    def __init__(self):
        self.motion_queue = Queue()
        self.motion_process = Process(target=self._motion_worker, daemon=True)
        self.motion_process.start()
    
    def _motion_worker(self):
        """Runs in separate process"""
        import asyncio
        
        async def worker():
            while True:
                try:
                    # Get motion command from queue
                    command = self.motion_queue.get()
                    if command is None:  # Shutdown signal
                        break
                    
                    motion_type, args, kwargs = command
                    
                    if motion_type == "wave":
                        await run_sine_test(*args, **kwargs)
                    elif motion_type == "salute":
                        await salute_func(*args, **kwargs)
                    elif motion_type == "squat":
                        print("Squat motion initialated")
                        await squat_func()
                    elif motion_type == "ymca":
                        print("YMCA Dance initiated")
                        await ymca_func()
                        
                except Exception as e:
                    print(f"Motion error: {e}")
        
        asyncio.run(worker())
    
    def wave(self, actuator_ids, **config):
        self.motion_queue.put(("wave", (actuator_ids,), config))
    
    def salute(self, actuator_ids, **config):
        self.motion_queue.put(("salute", (actuator_ids,), config))

    # Squat -- currently hard coded, no adjustments
    def squat(self, actuator_ids, **config):
        self.motion_queue.put(("squat", (actuator_ids,), config))
    # Basic YMCA -- currently hard coded, no adjustments
    def ymca(self, actuator_ids, **config):
        self.motion_queue.put(("ymca", (actuator_ids,), config))
    
    def shutdown(self):
        self.motion_queue.put(None)
        self.motion_process.join()
