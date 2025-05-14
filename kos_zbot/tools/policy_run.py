import asyncio
from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async

async def policy_start(policy_file: str, episode_length: float = 30.0, action_scale: float = 0.1):
    """Start policy deployment."""
    kos_ip = "127.0.0.1"
    if not await kos_ready_async(kos_ip):
        print(f"KOS service not available at {kos_ip}:50051")
        return False

    try:
        kos = KOS(kos_ip)
        # For now, we'll just pass the policy file since the API doesn't support parameters
        # TODO: Update when custom API is available
        await kos.process_manager.start_kclip(policy_file)
        print(f"Successfully started policy: {policy_file}")
        print(f"** Not Implemented: Episode length: {episode_length}s")
        print(f"** Not Implemented: Action scale: {action_scale}")
        return True
    except grpc.RpcError as e:
        print(f"Failed to start policy: {e.details()}")
        return False
    except Exception as e:
        print(f"Error starting policy: {e}")
        return False

async def policy_stop():
    """Stop policy deployment."""
    kos_ip = "127.0.0.1"
    if not await kos_ready_async(kos_ip):
        print(f"KOS service not available at {kos_ip}:50051")
        return False

    try:
        kos = KOS(kos_ip)
        await kos.process_manager.stop_kclip()
        print("Successfully stopped policy")
        return True
    except grpc.RpcError as e:
        print(f"Failed to stop policy: {e.details()}")
        return False
    except Exception as e:
        print(f"Error stopping policy: {e}")
        return False