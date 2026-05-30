"""ISA-5.1 instrument-tag ontology and grammar.

Source: ANSI/ISA-5.1-2024 "Instrumentation Symbols and Identification" — the
standard governing P&ID instrument tag identifiers and symbol classes. The
letter tables below are the machine-checkable core of that standard: a tag is
``[measured-variable letter][modifier?][succeeding/function letters]-[loop no.][suffix?]``.

This is the P&ID analogue of the panel domain's `features.yaml` — the
standards-grounded vocabulary every downstream rule and label references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- ISA-5.1 Table: first-letter = measured / initiating variable ----------
MEASURED_VARIABLE_LETTERS: dict[str, str] = {
    "A": "Analysis",
    "B": "Burner/Combustion",
    "C": "User's choice (conductivity)",
    "D": "User's choice (density)",
    "E": "Voltage",
    "F": "Flow rate",
    "G": "User's choice (gauging)",
    "H": "Hand (manual)",
    "I": "Current (electrical)",
    "J": "Power",
    "K": "Time/Schedule",
    "L": "Level",
    "M": "User's choice (moisture)",
    "N": "User's choice",
    "O": "User's choice",
    "P": "Pressure/Vacuum",
    "Q": "Quantity",
    "R": "Radiation",
    "S": "Speed/Frequency",
    "T": "Temperature",
    "U": "Multivariable",
    "V": "Vibration/Mechanical analysis",
    "W": "Weight/Force",
    "X": "Unclassified",
    "Y": "Event/State/Presence",
    "Z": "Position/Dimension",
}

# --- ISA-5.1 Table: succeeding letters = readout/passive + output/function --
FUNCTION_LETTERS: dict[str, str] = {
    "A": "Alarm",
    "B": "User's choice",
    "C": "Control",
    "E": "Sensor/Primary element",
    "G": "Glass/Gauge/Viewing",
    "I": "Indicate",
    "K": "Control station",
    "L": "Light",
    "N": "User's choice",
    "O": "Orifice/Restriction",
    "P": "Test point/Connection",
    "R": "Record",
    "S": "Switch",
    "T": "Transmit",
    "U": "Multifunction",
    "V": "Valve/Damper/Louver",
    "W": "Well/Probe",
    "Y": "Relay/Compute/Convert",
    "Z": "Driver/Actuator/Final element",
}

# Modifier letters that may trail (e.g. alarm High/Low/Middle).
MODIFIER_LETTERS: dict[str, str] = {"H": "High", "L": "Low", "M": "Middle"}

# Final-control-element function letters (used by loop-completeness checks).
FINAL_ELEMENT_LETTERS = {"V", "Z"}
CONTROLLER_LETTER = "C"
TRANSMITTER_LETTER = "T"
SENSOR_LETTER = "E"

_TAG_RE = re.compile(r"^([A-Z]{1,5})-?\s?(\d{1,5})([A-Z]?)$")


@dataclass
class ParsedTag:
    """Result of parsing an ISA-5.1 instrument tag (e.g. ``FIC-101``)."""

    raw: str
    valid: bool
    measured_variable: str | None = None  # first letter
    function_letters: list[str] | None = None  # succeeding letters
    loop_number: str | None = None
    suffix: str | None = None
    errors: list[str] | None = None

    @property
    def symbol_class(self) -> str:
        """Derive a canonical symbol class id, e.g. FLOW_INDICATING_CONTROLLER."""
        if not self.valid or self.measured_variable is None:
            return "UNKNOWN_INSTRUMENT"
        var = MEASURED_VARIABLE_LETTERS.get(self.measured_variable, "").split("/")[0]
        var = re.sub(r"[^A-Za-z]+", "", var).upper() or self.measured_variable
        funcs = []
        for letter in self.function_letters or []:
            name = FUNCTION_LETTERS.get(letter) or MODIFIER_LETTERS.get(letter, letter)
            funcs.append(re.sub(r"[^A-Za-z]+", "", name.split("/")[0]).upper())
        return "_".join([var, *funcs]) or "INSTRUMENT"


def parse_tag(tag: str) -> ParsedTag:
    """Parse and validate an ISA-5.1 instrument tag.

    Deterministic: first letter must be a measured-variable letter; succeeding
    letters must be function or modifier letters; a loop number is required.
    """
    raw = (tag or "").strip().upper()
    errors: list[str] = []
    m = _TAG_RE.match(raw)
    if not m:
        return ParsedTag(
            raw=raw,
            valid=False,
            errors=["tag does not match ISA-5.1 pattern LETTERS-NUMBER"],
        )

    letters, loop_number, suffix = m.group(1), m.group(2), m.group(3) or None
    first, succeeding = letters[0], list(letters[1:])

    if first not in MEASURED_VARIABLE_LETTERS:
        errors.append(f"first letter '{first}' is not an ISA-5.1 measured-variable letter")
    for letter in succeeding:
        if letter not in FUNCTION_LETTERS and letter not in MODIFIER_LETTERS:
            errors.append(f"letter '{letter}' is not an ISA-5.1 function/modifier letter")

    return ParsedTag(
        raw=raw,
        valid=not errors,
        measured_variable=first,
        function_letters=succeeding,
        loop_number=loop_number,
        suffix=suffix,
        errors=errors or None,
    )
