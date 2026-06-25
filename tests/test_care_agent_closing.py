"""Regression tests for CareAgent._is_closing.

The agent says "thank you" politely mid-conversation; that must NOT be treated
as a call-ending sign-off, or the call ends after the first reply.
"""
from agent.care_agent import CareAgent


def test_polite_thank_you_is_not_closing():
    assert CareAgent._is_closing("Great, thank you Eleanor. How are you feeling?") is False
    assert CareAgent._is_closing("Thank you for sharing that with me.") is False
    assert CareAgent._is_closing("Have you been taking your medication?") is False


def test_real_signoffs_are_closing():
    assert CareAgent._is_closing("Take care, and call us anytime.") is True
    assert CareAgent._is_closing("Goodbye and stay well.") is True
    assert CareAgent._is_closing("Have a good day, Eleanor.") is True
    assert CareAgent._is_closing("Wishing you a speedy recovery — stay safe.") is True
