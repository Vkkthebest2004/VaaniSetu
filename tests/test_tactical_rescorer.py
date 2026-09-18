"""
Unit tests for TacticalRescorer domain language model biasing.
"""

import pytest
from vaanisetu.stt.tactical_rescorer import TacticalRescorer


def test_tactical_rescorer_initialization():
    tr = TacticalRescorer()
    assert tr is not None


def test_phonetic_confusion_correction():
    tr = TacticalRescorer()

    # Evacuation confusion
    raw = "Emergency of accuation immediate assistance required"
    corrected = tr.rescore(raw)
    assert "EVACUATION" in corrected.upper()

    # Medical confusion
    raw2 = "Send mate team to location"
    corrected2 = tr.rescore(raw2)
    assert "MEDICAL TEAM" in corrected2.upper()

    # Flood confusion
    raw3 = "Warning water lev l is rising fast"
    corrected3 = tr.rescore(raw3)
    assert "WATER LEVEL" in corrected3.upper()


def test_channel_inverse_text_normalization():
    tr = TacticalRescorer()
    raw = "Switch all units to Channel 7"
    corrected = tr.rescore(raw)
    assert "Channel 07" in corrected

    raw2 = "Reporting on CH 14"
    corrected2 = tr.rescore(raw2)
    assert "Channel 14" in corrected2


def test_sector_normalization():
    tr = TacticalRescorer()
    raw = "Casualties located at sector 4"
    corrected = tr.rescore(raw)
    assert "Sector 04" in corrected


def test_indic_normalization():
    tr = TacticalRescorer()
    raw = "सुरखित स्थान पर जाएं"
    corrected = tr.rescore(raw)
    assert "सुरक्षित" in corrected
