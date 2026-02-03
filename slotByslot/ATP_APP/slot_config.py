# slot_config.py
from dataclasses import dataclass

# Shared defaults (your note: same for all slots)
DEFAULT_ADC_CH = 0
DEFAULT_CS_GPIO = 5

@dataclass(frozen=True)
class SlotConfig:
    # --- REQUIRED (no defaults) ---
    slot: int
    can_tx_id: int
    relay_gpio: int
    power_gpio: int
    iul_gpio: int
    id_port: str                 # "A" or "B"
    id_pins: tuple               # (p0,p1,p2) positions on that port
    id_baseline_bits: int        # 3-bit [ID3 ID2 ID1] e.g. 0b110

    # Gate2 expected ID report (0..3 etc from firmware behavior)
    expected_idpins_gate2: set

    # Gate5 expected results after clearing each pin
    expected_after_clear: dict

    # --- OPTIONAL (defaults) ---
    can_rsp_id: int = 0x063
    adc_ch: int = DEFAULT_ADC_CH
    cs_gpio: int = DEFAULT_CS_GPIO


# Your table (update if anything changes)
SLOTS = {
    1: SlotConfig(
        slot=1,
        can_tx_id=0x001,
        relay_gpio=22,
        power_gpio=21,
        iul_gpio=18,
        id_port="A",
        id_pins=(0, 1, 2),
        id_baseline_bits=0b110,
        expected_idpins_gate2={0x00},
        expected_after_clear={0: 0x03, 1: 0x05, 2: 0x06},
    ),
    2: SlotConfig(
        slot=2,
        can_tx_id=0x002,
        relay_gpio=27,
        power_gpio=20,
        iul_gpio=23,
        id_port="A",
        id_pins=(3, 4, 5),
        id_baseline_bits=0b101,
        expected_idpins_gate2={0x01},
        expected_after_clear={3: 0x03, 4: 0x05, 5: 0x06},
    ),
    3: SlotConfig(
        slot=3,
        can_tx_id=0x003,
        relay_gpio=6,
        power_gpio=16,
        iul_gpio=24,
        id_port="B",
        id_pins=(0, 1, 2),
        id_baseline_bits=0b100,
        expected_idpins_gate2={0x02},
        expected_after_clear={0: 0x02, 1: 0x04, 2: 0x06},
    ),
    4: SlotConfig(
        slot=4,
        can_tx_id=0x004,
        relay_gpio=13,
        power_gpio=12,
        iul_gpio=25,
        id_port="B",
        id_pins=(3, 4, 5),
        id_baseline_bits=0b011,
        expected_idpins_gate2={0x03},
        expected_after_clear={3: 0x01, 4: 0x05, 5: 0x06},
    ),
}

def get_slot_config(slot: int) -> SlotConfig:
    if slot not in SLOTS:
        raise ValueError(f"Invalid slot: {slot}")
    return SLOTS[slot]
