# minimal_motor_server.py
import asyncio
import grpc
from concurrent import futures
from kos_protos import actuator_pb2, actuator_pb2_grpc, common_pb2
from kos_zbot.feetech_actuator import SCSMotorController

# Test Flags
sync_test = False # Apply same position to all actuators for protocol performance testing

class MotorController:
    """Interface for real motor control using SCS servos."""
    
    def __init__(self):
        self.actuator_ids = set() 
        self.controller = SCSMotorController(device='/dev/ttyAMA5', baudrate=500000, rate=50)
        self.controller.start()
        self._lock = asyncio.Lock()

    def _counts_to_degrees(self, counts: float) -> float:
        return (counts * 360 / 4095) - 180
        
    def _degrees_to_counts(self, degrees: float) -> int:
        return (degrees + 180) * (4095 / 360)

    async def command_actuator(self, commands):
        """Send commands to multiple actuators atomically. Positions in degrees."""
        if not commands:
            return
            
        # Create a dictionary mapping each actuator to its commanded position
        servo_commands = {
            cmd['actuator_id']: self._degrees_to_counts(cmd['position'])
            for cmd in commands
            if cmd['actuator_id'] in self.actuator_ids  # Only include configured actuators
        }
        self.controller.set_positions(servo_commands)
        

    def __del__(self):
        if self.controller:
            self.controller.stop()

    async def get_actuator_state(self, actuator_id: int):
        """Get current actuator state."""
        if actuator_id not in self.actuator_ids:
            return actuator_pb2.ActuatorStateResponse(
                actuator_id=actuator_id,
                position=0.0,
                velocity=0.0,
                online=False
            )
            
        position_raw = self.controller.get_position(actuator_id)
        if position_raw is None:
            return actuator_pb2.ActuatorStateResponse(
                actuator_id=actuator_id,
                position=0.0,
                velocity=0.0,
                online=False
            )
            
        position_deg = self._counts_to_degrees(position_raw)
        return actuator_pb2.ActuatorStateResponse(
            actuator_id=actuator_id,
            position=position_deg,
            velocity=0.0,
            online=True
        )

    async def configure_actuator(self, actuator_id: int, config: dict):
        """Configure a single actuator"""
        async with self._lock:
            if 'acceleration' in config:
                if config['acceleration'] != 0:
                    config['acceleration'] = self._degrees_to_counts(config['acceleration'])
            
            # Configure the actuator and add it to our set if successful
            success = self.controller.configure_actuator(actuator_id, config)
            if success:
                self.actuator_ids.add(actuator_id)
            else:
                self.actuator_ids.discard(actuator_id)  # Remove if present
                print(f"Failed to configure actuator {actuator_id}")
                
            return success



class ActuatorService(actuator_pb2_grpc.ActuatorServiceServicer):
    def __init__(self, motor_controller):
        super().__init__()
        self.motor_controller = motor_controller

    async def ConfigureActuator(self, request, context):
        """Handle actuator configuration."""
        try:
            config = {}
            if request.HasField("torque_enabled"):
                config["torque_enabled"] = request.torque_enabled
            if request.HasField("zero_position"):
                config["zero_position"] = request.zero_position
            if request.HasField("kp"):
                config["kp"] = request.kp
            if request.HasField("kd"):
                config["kd"] = request.kd
            if request.HasField("max_torque"):
                config["max_torque"] = request.max_torque
            if request.HasField("acceleration"):
                config["acceleration"] = request.acceleration

            print(f"Configuring actuator {request.actuator_id} with settings: {config}")
            success = await self.motor_controller.configure_actuator(request.actuator_id, config)
            
            return common_pb2.ActionResponse(success=success)
            
        except Exception as e:
            error_msg = f"Error configuring actuator {request.actuator_id}: {str(e)}"
            print(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return common_pb2.ActionResponse(success=False)


    async def CommandActuators(self, request, context):
        """Handle multiple actuator commands atomically."""
        try:
            commands = [
                {
                    'actuator_id': cmd.actuator_id,
                    'position': cmd.position
                }
                for cmd in request.commands
            ]

            # Apply same position to all actuators for protocol performance testing
            if sync_test:
                servo_position = commands[0]['position'] if commands else 0
                test_commands = [
                    {
                        'actuator_id': actuator_id,
                        'position': servo_position
                    }
                    for actuator_id in self.motor_controller.actuator_ids
                ]
                await self.motor_controller.command_actuator(test_commands)
            else:
                await self.motor_controller.command_actuator(commands)

            return actuator_pb2.CommandActuatorsResponse()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return actuator_pb2.CommandActuatorsResponse()

        # In the ActuatorService class
    async def ReadAllParams(self, request, context):
        """Read all parameters from all servos"""
        try:
            # Call the motor controller's read function
            self.motor_controller.controller.read_all_servos_params()
            return common_pb2.ActionResponse(success=True)
        except Exception as e:
            error_msg = f"Error reading parameters: {str(e)}"
            print(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return common_pb2.ActionResponse(success=False)

    async def GetActuatorsState(self, request, context):
        """Handle actuator state requests."""
        try:
            ids = request.actuator_ids or [1]  # Default to actuator 1 if none specified
            states = []
            for actuator_id in ids:
                state = await self.motor_controller.get_actuator_state(actuator_id)
                states.append(state)
            return actuator_pb2.GetActuatorsStateResponse(states=states)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return actuator_pb2.GetActuatorsStateResponse()

async def serve(host: str = "0.0.0.0", port: int = 50051):
    """Start the gRPC server."""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    motor_controller = MotorController()
    try:
        actuator_service = ActuatorService(motor_controller)
        actuator_pb2_grpc.add_ActuatorServiceServicer_to_server(actuator_service, server)
        
        server.add_insecure_port(f"{host}:{port}")
        await server.start()
        print(f"Server started on {host}:{port}")
        await server.wait_for_termination()
    finally:
        motor_controller.controller.stop()  # Ensure cleanup happens

if __name__ == "__main__":
    asyncio.run(serve())