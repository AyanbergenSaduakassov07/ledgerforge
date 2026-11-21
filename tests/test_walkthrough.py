"""The pitch walkthrough runs end to end and its invariance check holds."""

from ledgerforge.walkthrough import walkthrough


def test_walkthrough_succeeds_and_reward_survives_renaming() -> None:
    assert walkthrough(2006) == 0
