# Reference tables for decoding J1939 fault codes into readable text.
# FMI is the small, standardized (SAE J1939-73) set -- covered close to fully.
# SPN is a huge space assigned across the whole spec; this covers the common ones
# likely to show up on a diesel engine, with a graceful fallback for anything else.

FMI_DESCRIPTIONS = {
    0: "above normal range — most severe",
    1: "below normal range — most severe",
    2: "erratic, intermittent, or incorrect",
    3: "voltage above normal or shorted high",
    4: "voltage below normal or shorted low",
    5: "current below normal or open circuit",
    6: "current above normal or grounded circuit",
    7: "mechanical system not responding properly",
    8: "abnormal frequency, pulse width, or period",
    9: "abnormal update rate",
    10: "abnormal rate of change",
    11: "root cause not known",
    12: "bad intelligent device or component",
    13: "out of calibration",
    14: "special instructions",
    15: "above normal range — least severe",
    16: "above normal range — moderately severe",
    17: "below normal range — least severe",
    18: "below normal range — moderately severe",
    19: "received network data in error",
    20: "data drifted high",
    21: "data drifted low",
    31: "condition exists",
}

SPN_DESCRIPTIONS = {
    91: "Accelerator Pedal Position",
    94: "Fuel Delivery Pressure",
    97: "Water in Fuel Indicator",
    100: "Engine Oil Pressure",
    102: "Boost Pressure",
    105: "Intake Manifold Temperature",
    106: "Air Inlet Pressure",
    108: "Barometric Pressure",
    110: "Engine Coolant Temperature",
    111: "Coolant Level",
    157: "Injector Metering Rail Pressure",
    168: "Electrical Potential (Battery Voltage)",
    172: "Air Inlet Temperature",
    174: "Engine Fuel Temperature",
    175: "Engine Oil Temperature",
    177: "Transmission Oil Temperature",
    190: "Engine Speed (RPM)",
    247: "Engine Total Hours of Operation",
    523: "Transmission Current Gear",
}


def describe_spn(spn):
    return SPN_DESCRIPTIONS.get(spn, f"SPN {spn} (not in local reference table)")


def describe_fmi(fmi):
    return FMI_DESCRIPTIONS.get(fmi, f"failure mode {fmi} (uncommon/reserved)")


def describe_fault(spn, fmi):
    return f"{describe_spn(spn)} — {describe_fmi(fmi)}"
