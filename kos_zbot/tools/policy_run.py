import asyncio
from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async
import grpc

async def policy_start(policy_file: str, episode_length: float = 30.0, action_scale: float = 0.1, dry_run: bool = False):
    """Start policy deployment."""
    kos_ip = "127.0.0.1"
    if not await kos_ready_async(kos_ip):
        print(f"KOS service not available at {kos_ip}:50051")
        return False

    try:
        print(f"Debug: Creating KOS client")  # Debug print
        kos = KOS(kos_ip)
        print(f"Debug: Calling start_policy")  # Debug print
        print(f"Debug: Policy attribute exists: {hasattr(kos, 'policy')}")  # Debug print
        print(f"Debug: Policy type: {type(kos.policy)}")  # Debug print
        print(f"Debug: Calling start_policy")  # Debug print
        await kos.policy.start_policy(
            action=policy_file,
            action_scale=action_scale,
            episode_length=int(episode_length),
            dry_run=dry_run
        )
        print(f"Successfully started policy: {policy_file}")
        print(f"Episode length: {episode_length}s")
        print(f"Action scale: {action_scale}")
        print(f"Dry run: {dry_run}")
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
        await kos.policy.stop_policy()
        print("Successfully stopped policy")
        return True
    except grpc.RpcError as e:
        print(f"Failed to stop policy: {e.details()}")
        return False
    except Exception as e:
        print(f"Error stopping policy: {str(e)}")
        return False

async def get_policy_state():
    """Get current policy state."""
    kos_ip = "127.0.0.1"
    if not await kos_ready_async(kos_ip):
        print(f"KOS service not available at {kos_ip}:50051")
        return None

    try:
        kos = KOS(kos_ip)
        state = await kos.policy.get_state()
        return state
    except grpc.RpcError as e:
        print(f"Failed to get policy state: {e.details()}")
        return None
    except Exception as e:
        print(f"Error getting policy state: {e}")
        return None