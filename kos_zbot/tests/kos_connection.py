import asyncio
import grpc

async def kos_ready_async(kos_ip: str, port: int = 50051, timeout: float = 2.0) -> bool:
    address = f"{kos_ip}:{port}"
    channel = grpc.aio.insecure_channel(address)
    try:
        await asyncio.wait_for(channel.channel_ready(), timeout)
        return True
    except Exception:
        return False

def kos_ready(kos_ip: str, port: int = 50051, timeout: float = 2.0) -> bool:
    """
    Synchronous check if the KOS gRPC service is available.
    """
    return asyncio.run(kos_ready_async(kos_ip, port, timeout))