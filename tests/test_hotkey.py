"""Tests for `app/hotkey.py`'s `parse_hotkey()`.

Pure string-parsing logic, no Win32/Qt involved -- these run on any
platform. The previous session verified this same logic ad hoc against a
stubbed `PySide6.QtCore` inside a throwaway script; this file makes that
coverage permanent so it survives past any one session/sandbox.
"""

from __future__ import annotations

import pytest

from app.hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    parse_hotkey,
)


def test_ctrl_shift_space():
    modifiers, vk = parse_hotkey("ctrl+shift+space")
    assert modifiers == (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)
    assert vk == 0x20


def test_alt_letter():
    modifiers, vk = parse_hotkey("alt+q")
    assert modifiers == (MOD_ALT | MOD_NOREPEAT)
    assert vk == ord("Q")


def test_win_digit():
    modifiers, vk = parse_hotkey("win+1")
    assert modifiers == (MOD_WIN | MOD_NOREPEAT)
    assert vk == ord("1")


def test_function_key():
    modifiers, vk = parse_hotkey("ctrl+alt+f5")
    assert modifiers == (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT)
    assert vk == 0x74  # F5


def test_modifier_aliases():
    # control/meta/super should behave the same as ctrl/win.
    m1, vk1 = parse_hotkey("control+meta+enter")
    m2, vk2 = parse_hotkey("ctrl+super+return")
    assert m1 == m2 == (MOD_CONTROL | MOD_WIN | MOD_NOREPEAT)
    assert vk1 == vk2 == 0x0D


def test_case_insensitive():
    modifiers, vk = parse_hotkey("CTRL+SHIFT+SPACE")
    assert modifiers == (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)
    assert vk == 0x20


def test_whitespace_tolerance():
    modifiers, vk = parse_hotkey(" ctrl + shift + space ")
    assert modifiers == (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)
    assert vk == 0x20


def test_empty_string_raises():
    with pytest.raises(ValueError):
        parse_hotkey("")


def test_only_modifiers_raises():
    with pytest.raises(ValueError):
        parse_hotkey("ctrl+shift")


def test_two_main_keys_raises():
    with pytest.raises(ValueError):
        parse_hotkey("ctrl+a+b")


def test_unrecognized_key_raises():
    with pytest.raises(ValueError):
        parse_hotkey("ctrl+banana")


def test_unrecognized_modifier_treated_as_main_key_conflict():
    # "foo" isn't a known modifier, so it's treated as the main key --
    # combined with "space" that's two main keys, which should still
    # raise (not silently pick one).
    with pytest.raises(ValueError):
        parse_hotkey("foo+space")
