import json
from pathlib import Path
import sounddevice as sd

PROJECT_DIR = Path(__file__).parent
CONFIG_DIR = PROJECT_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "microphone_name": None,
    "speaker_name": None,
    "volume": 0.35,
    "environment": "default",
}


def get_available_devices():
    device_list = sd.query_devices()
    microphones = []
    speakers = []

    for i, device in enumerate(device_list):
        device_info = {
            "id": i,
            "name": device["name"],
            "channels": (
                device["max_input_channels"]
                if device["max_input_channels"] > 0
                else device["max_output_channels"]
            ),
        }

        if device["max_input_channels"] > 0:
            microphones.append(device_info)
        if device["max_output_channels"] > 0:
            speakers.append(device_info)

    return microphones, speakers


def find_device_id_by_name(device_name, device_type="input"):
    if not device_name:
        return None
    
    device_list = sd.query_devices()
    for i, device in enumerate(device_list):
        if device["name"] == device_name:
            if device_type == "input" and device["max_input_channels"] > 0:
                return i
            elif device_type == "output" and device["max_output_channels"] > 0:
                return i
    return None


def get_default_device_name(device_type="input"):
    try:
        if device_type == "input":
            default_device = sd.query_devices(kind='input')
        else:
            default_device = sd.query_devices(kind='output')
        return default_device["name"]
    except:
        return None


def prompt_device_selection(devices, device_type):
    if not devices:
        print(f"No {device_type}s found!")
        return None

    print(f"\nAvailable {device_type}s:")
    print("-" * 50)
    for device in devices:
        print(
            f"{device['id']:2d}: {device['name']} (channels: {device['channels']})"
        )

    while True:
        try:
            choice = input(f"\nSelect {device_type} ID: ").strip()
            device_id = int(choice)

            valid_ids = [device["id"] for device in devices]
            if device_id in valid_ids:
                selected_device = next(
                    d for d in devices if d["id"] == device_id
                )
                print(f"Selected {device_type}: {selected_device['name']}")
                return selected_device["name"]
            else:
                print(f"Invalid choice. Please select from available IDs.")

        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print(
                f"\nUsing first available {device_type}: {devices[0]['name']}"
            )
            return devices[0]['name']


def migrate_legacy_config(config):
    """Migrate old ID-based config to name-based config."""
    migrated = False
    
    # Migrate microphone_id to microphone_name
    if "microphone_id" in config and "microphone_name" not in config:
        mic_id = config["microphone_id"]
        device_list = sd.query_devices()
        if mic_id < len(device_list):
            device = device_list[mic_id]
            if device["max_input_channels"] > 0:
                config["microphone_name"] = device["name"]
                print(f"Migrated microphone ID {mic_id} to name: {device['name']}")
                migrated = True
        del config["microphone_id"]
    
    # Migrate speaker_id to speaker_name
    if "speaker_id" in config and "speaker_name" not in config:
        speaker_id = config["speaker_id"]
        device_list = sd.query_devices()
        if speaker_id < len(device_list):
            device = device_list[speaker_id]
            if device["max_output_channels"] > 0:
                config["speaker_name"] = device["name"]
                print(f"Migrated speaker ID {speaker_id} to name: {device['name']}")
                migrated = True
        del config["speaker_id"]
    
    return config, migrated


def create_config():
    CONFIG_DIR.mkdir(exist_ok=True)

    config = DEFAULT_CONFIG.copy()
    microphones, speakers = get_available_devices()

    mic_name = prompt_device_selection(microphones, "microphone")
    if mic_name is not None:
        config["microphone_name"] = mic_name
    else:
        default_mic = get_default_device_name("input")
        if default_mic:
            config["microphone_name"] = default_mic
            print(f"Warning: No microphones found. Using default: {default_mic}")
        else:
            print("Warning: No microphones found and no default available.")

    speaker_name = prompt_device_selection(speakers, "speaker")
    if speaker_name is not None:
        config["speaker_name"] = speaker_name
    else:
        default_speaker = get_default_device_name("output")
        if default_speaker:
            config["speaker_name"] = default_speaker
            print(f"Warning: No speakers found. Using default: {default_speaker}")
        else:
            print("Warning: No speakers found and no default available.")

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        print(f"\n✓ Configuration saved to: {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        print("Using default configuration in memory only.")

    print("=" * 40)
    return config


def load_config():
    CONFIG_DIR.mkdir(exist_ok=True)

    if not CONFIG_FILE.exists():
        print("Configuration not found. Setting up for first time...")
        return create_config()

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

        # Migrate legacy ID-based config to name-based config
        config, migrated = migrate_legacy_config(config)

        # Ensure all default keys are present
        for key in DEFAULT_CONFIG:
            if key not in config:
                config[key] = DEFAULT_CONFIG[key]

        # Save migrated config if changes were made
        if migrated:
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)
                print("✓ Configuration migrated and saved.")
            except Exception as e:
                print(f"Warning: Could not save migrated configuration: {e}")

        return config

    except Exception as e:
        print(f"Error loading configuration: {e}")
        print("Creating new configuration...")
        return create_config()


def get_microphone_id(config):
    mic_name = config.get("microphone_name")
    if not mic_name:
        return None
    
    mic_id = find_device_id_by_name(mic_name, "input")
    if mic_id is None:
        print(f"Warning: Microphone '{mic_name}' not found. Available devices:")
        microphones, _ = get_available_devices()
        for mic in microphones:
            print(f"  - {mic['name']}")
        
        default_mic = get_default_device_name("input")
        if default_mic:
            default_id = find_device_id_by_name(default_mic, "input")
            print(f"Using default microphone: {default_mic}")
            return default_id
    
    return mic_id


def get_speaker_id(config):
    speaker_name = config.get("speaker_name")
    if not speaker_name:
        return None
    
    speaker_id = find_device_id_by_name(speaker_name, "output")
    if speaker_id is None:
        print(f"Warning: Speaker '{speaker_name}' not found. Available devices:")
        _, speakers = get_available_devices()
        for speaker in speakers:
            print(f"  - {speaker['name']}")
        
        default_speaker = get_default_device_name("output")
        if default_speaker:
            default_id = find_device_id_by_name(default_speaker, "output")
            print(f"Using default speaker: {default_speaker}")
            return default_id
    
    return speaker_id
