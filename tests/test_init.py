"""Test the Scheduler integration init."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.scheduler.const import DOMAIN


async def test_setup_entry_with_schedules(hass: HomeAssistant, hub_entry):
    """Test setting up the integration with schedules."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state == ConfigEntryState.LOADED
    assert hub_entry.runtime_data is not None
    
    # Check that hub device was created
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, hub_entry.entry_id)
    assert len(devices) == 2  # Hub + 1 schedule device


async def test_setup_entry_without_schedules(hass: HomeAssistant, empty_hub_entry):
    """Test setting up the integration without schedules."""
    empty_hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(empty_hub_entry.entry_id)
    await hass.async_block_till_done()

    assert empty_hub_entry.state == ConfigEntryState.LOADED
    assert empty_hub_entry.runtime_data is not None
    
    # Check that no devices were created (no schedules)
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, empty_hub_entry.entry_id)
    assert len(devices) == 0


async def test_unload_entry(hass: HomeAssistant, hub_entry):
    """Test unloading the integration."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state == ConfigEntryState.NOT_LOADED


async def test_reload_entry(hass: HomeAssistant, hub_entry):
    """Test reloading a config entry."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state == ConfigEntryState.LOADED
    
    # Reload the entry
    assert await hass.config_entries.async_reload(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state == ConfigEntryState.LOADED
    assert hub_entry.runtime_data is not None


async def test_device_removal(hass: HomeAssistant, hub_entry):
    """Test removing a schedule device."""
    from custom_components.scheduler import async_remove_config_entry_device
    
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, hub_entry.entry_id)
    
    # Find the schedule device (not the hub)
    schedule_device = None
    for device in devices:
        if (DOMAIN, "test_schedule_1") in device.identifiers:
            schedule_device = device
            break
    
    assert schedule_device is not None
    
    # Remove the schedule device
    result = await async_remove_config_entry_device(hass, hub_entry, schedule_device)
    assert result is True
    
    # Verify schedule was removed from config entry
    assert "test_schedule_1" not in hub_entry.data["schedules"]


async def test_hub_device_removal_prevented(hass: HomeAssistant, hub_entry):
    """Test that hub device cannot be removed."""
    from custom_components.scheduler import async_remove_config_entry_device
    
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, hub_entry.entry_id)
    
    # Find the hub device
    hub_device = None
    for device in devices:
        if (DOMAIN, "scheduler_hub") in device.identifiers:
            hub_device = device
            break
    
    assert hub_device is not None
    
    # Try to remove the hub device (should fail)
    result = await async_remove_config_entry_device(hass, hub_entry, hub_device)
    assert result is False



async def test_calendar_created_with_schedules(hass: HomeAssistant, hub_entry):
    """Test that calendar entity is created when schedules exist."""
    from homeassistant.helpers import entity_registry as er
    
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Check that calendar entity was created
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, hub_entry.entry_id)
    
    # Should have: 1 schedule binary sensor + 1 hub binary sensor + 1 calendar
    calendar_entities = [e for e in entities if e.domain == "calendar"]
    assert len(calendar_entities) == 1
    assert calendar_entities[0].unique_id == f"{hub_entry.entry_id}_calendar"


async def test_calendar_not_created_without_schedules(hass: HomeAssistant, empty_hub_entry):
    """Test that calendar entity is not created when no schedules exist."""
    from homeassistant.helpers import entity_registry as er
    
    empty_hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(empty_hub_entry.entry_id)
    await hass.async_block_till_done()

    # Check that no calendar entity was created
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, empty_hub_entry.entry_id)
    
    calendar_entities = [e for e in entities if e.domain == "calendar"]
    assert len(calendar_entities) == 0



async def test_async_remove_config_entry_device_not_found(hass: HomeAssistant, hub_entry):
    """Test removing a device that doesn't exist in schedules."""
    from custom_components.scheduler import async_remove_config_entry_device
    from homeassistant.helpers import device_registry as dr

    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    # Create a fake device entry that doesn't match any schedule
    fake_device = dr.DeviceEntry(
        id="fake_device_id",
        identifiers={(DOMAIN, "non_existent_schedule")},
        config_entries={hub_entry.entry_id},
    )

    # Try to remove it (should return False)
    result = await async_remove_config_entry_device(hass, hub_entry, fake_device)
    assert result is False
