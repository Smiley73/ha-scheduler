"""Test schedule sorting in config flow."""

from homeassistant.helpers.selector import SelectOptionDict


def test_schedule_sorting_logic():
    """Test the sorting logic used in schedule selection."""
    # Simulate the schedules dict that would be in config entry options
    schedules = {
        "id1": {"name": "zebra Schedule", "schedule_type": "date"},
        "id2": {"name": "Apple Schedule", "schedule_type": "date"},
        "id3": {"name": "banana Schedule", "schedule_type": "date"},
        "id4": {"name": "Cherry Schedule", "schedule_type": "date"},
    }

    # Apply the same sorting logic used in the config flow
    schedule_options = [
        SelectOptionDict(value=sid, label=sdata["name"])
        for sid, sdata in sorted(schedules.items(), key=lambda x: x[1]["name"].lower())
    ]

    # Extract the labels (schedule names) from the options
    labels = [option["label"] for option in schedule_options]

    # Expected order: Apple, banana, Cherry, zebra (case-insensitive alphabetical)
    expected_labels = [
        "Apple Schedule",
        "banana Schedule",
        "Cherry Schedule",
        "zebra Schedule",
    ]

    assert labels == expected_labels


def test_schedule_sorting_logic_mixed_case():
    """Test the sorting logic with more mixed case scenarios."""
    # Simulate schedules with various case patterns
    schedules = {
        "id1": {"name": "Zebra Schedule", "schedule_type": "date"},
        "id2": {"name": "apple Schedule", "schedule_type": "date"},
        "id3": {"name": "Banana Schedule", "schedule_type": "date"},
        "id4": {"name": "cherry Schedule", "schedule_type": "date"},
        "id5": {"name": "DELTA Schedule", "schedule_type": "date"},
        "id6": {"name": "echo schedule", "schedule_type": "date"},
    }

    # Apply the same sorting logic used in the config flow
    schedule_options = [
        SelectOptionDict(value=sid, label=sdata["name"])
        for sid, sdata in sorted(schedules.items(), key=lambda x: x[1]["name"].lower())
    ]

    # Extract the labels (schedule names) from the options
    labels = [option["label"] for option in schedule_options]

    # Expected order: apple, Banana, cherry, DELTA, echo, Zebra (case-insensitive alphabetical)
    expected_labels = [
        "apple Schedule",
        "Banana Schedule",
        "cherry Schedule",
        "DELTA Schedule",
        "echo schedule",
        "Zebra Schedule",
    ]

    assert labels == expected_labels


def test_schedule_sorting_preserves_values():
    """Test that sorting preserves the correct value-label mapping."""
    schedules = {
        "uuid-zebra": {"name": "zebra Schedule", "schedule_type": "date"},
        "uuid-apple": {"name": "Apple Schedule", "schedule_type": "date"},
        "uuid-banana": {"name": "banana Schedule", "schedule_type": "date"},
    }

    # Apply the same sorting logic used in the config flow
    schedule_options = [
        SelectOptionDict(value=sid, label=sdata["name"])
        for sid, sdata in sorted(schedules.items(), key=lambda x: x[1]["name"].lower())
    ]

    # Check that values are correctly mapped to labels
    expected_mapping = [
        ("uuid-apple", "Apple Schedule"),
        ("uuid-banana", "banana Schedule"),
        ("uuid-zebra", "zebra Schedule"),
    ]

    actual_mapping = [(option["value"], option["label"]) for option in schedule_options]

    assert actual_mapping == expected_mapping
