"""Quick test to verify models work correctly."""

from pathlib import Path

from src.launchsampler.models import (
    AppConfig,
    Color,
    Launchpad,
    LaunchpadModel,
    Pad,
    PlaybackMode,
    Sample,
    Set,
)


def test_basic_models():
    """Test basic model creation and serialization."""
    print("Testing models...\n")

    # Test Color
    red = Color.red()
    print(f"Red color: {red.to_rgb_tuple()}")

    # Test Sample
    sample = Sample.from_file(Path("kick.wav"))
    print(f"Sample: {sample.name} at {sample.path}")

    # Test Pad
    pad = Pad(x=0, y=0, sample=sample, color=red, mode=PlaybackMode.ONE_SHOT)
    print(f"Pad at {pad.position}, assigned: {pad.is_assigned}")

    # Test Launchpad
    launchpad = Launchpad.create_empty(LaunchpadModel.LAUNCHPAD_X)
    print(f"Launchpad has {len(launchpad.pads)} pads")

    # Assign sample to a pad
    target_pad = launchpad.get_pad(0, 0)
    target_pad.sample = sample
    target_pad.color = Color.green()
    print(f"Assigned pads: {len(launchpad.assigned_pads)}")

    # Test Set
    my_set = Set.create_empty("test_set")
    my_set.launchpad = launchpad
    print(f"Set '{my_set.name}' created at {my_set.created_at}")

    # Test serialization
    json_data = my_set.model_dump_json(indent=2)
    print(f"\nSerialized set (first 200 chars):\n{json_data[:200]}...")

    # Test deserialization
    loaded_set = Set.model_validate_json(json_data)
    print(f"\nLoaded set: {loaded_set.name}")
    print(f"Loaded assigned pads: {len(loaded_set.launchpad.assigned_pads)}")

    # Test AppConfig
    config = AppConfig.load_or_default()
    print(f"\nConfig sample rate: {config.sample_rate}")
    print(f"Sets directory: {config.sets_dir}")

    print("\n[OK] All tests passed!")


if __name__ == "__main__":
    test_basic_models()
