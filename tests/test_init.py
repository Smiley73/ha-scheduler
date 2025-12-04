"""Test the Scheduler integration init."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.scheduler.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant, config_entry):
    """Test setting up the integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data


async def test_unload_entry(hass: HomeAssistant, config_entry):
    """Test unloading the integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_multiple_entries(hass: HomeAssistant):
    """Test setting up multiple config entries."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Schedule 1",
        data={
            "name": "Schedule 1",
            "start_month": 1,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 15,
        },
        entry_id="test_entry_1",
        unique_id="test_unique_1",
    )
    
    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Schedule 2",
        data={
            "name": "Schedule 2",
            "start_month": 7,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 31,
        },
        entry_id="test_entry_2",
        unique_id="test_unique_2",
    )
    
    config_entry1.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry1.entry_id)
    await hass.async_block_till_done()
    
    config_entry2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry2.entry_id)
    await hass.async_block_till_done()

    assert config_entry1.state == ConfigEntryState.LOADED
    assert config_entry2.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry1.entry_id in hass.data[DOMAIN]
    assert config_entry2.entry_id in hass.data[DOMAIN]


async def test_unload_one_of_multiple_entries(hass: HomeAssistant):
    """Test unloading one entry when multiple are loaded."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Schedule 1",
        data={
            "name": "Schedule 1",
            "start_month": 1,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 15,
        },
        entry_id="test_entry_1",
        unique_id="test_unique_1",
    )
    
    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Schedule 2",
        data={
            "name": "Schedule 2",
            "start_month": 7,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 31,
        },
        entry_id="test_entry_2",
        unique_id="test_unique_2",
    )
    
    config_entry1.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry1.entry_id)
    await hass.async_block_till_done()
    
    config_entry2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry2.entry_id)
    await hass.async_block_till_done()

    # Unload first entry
    assert await hass.config_entries.async_unload(config_entry1.entry_id)
    await hass.async_block_till_done()

    assert config_entry1.state == ConfigEntryState.NOT_LOADED
    assert config_entry2.state == ConfigEntryState.LOADED
    assert config_entry1.entry_id not in hass.data[DOMAIN]
    assert config_entry2.entry_id in hass.data[DOMAIN]


async def test_reload_entry(hass: HomeAssistant, config_entry):
    """Test reloading a config entry."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    
    # Reload the entry
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]
