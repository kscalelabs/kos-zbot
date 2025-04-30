import os
import logging
import asyncio
from typing import Optional
import dotenv
from voice.voice import Voice
from config import get_available_speakers, get_available_microphones

# Configure minimal logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def get_required_env_var(name: str) -> str:
    """Get a required environment variable or raise an error if not found."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value

def main() -> None:
    """Initialize and run the voice system."""
    # Load environment variables
    dotenv.load_dotenv()
    
    try:
        # Get required configuration
        openai_api_key = get_required_env_var("OPENAI_API_KEY")
        
        # Show available audio devices
        logger.info("Available input devices:")
        for device in get_available_microphones():
            logger.info(f"  ID: {device['id']}, Name: {device['name']}")
            
        logger.info("\nAvailable output devices:")
        for device in get_available_speakers():
            logger.info(f"  ID: {device['id']}, Name: {device['name']}")
        
        # Initialize voice system
        logger.info("\nInitializing voice system...")
        voice = Voice(
            openai_api_key=openai_api_key,
            config=None,
        )
        
        @voice.event("ready")
        async def handle_ready() -> None:
            """Handle the ready event when the voice system is initialized."""
            logger.info("Voice system ready")
        
        # Run the voice system
        asyncio.run(voice.run())
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
