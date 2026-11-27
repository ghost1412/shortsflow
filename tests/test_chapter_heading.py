"""A chapter title written as a heading is not thrown out for its capitals."""
from engine import chapters as ch

SAID = "eye retinal issues and there are four different maladies that happen to your eyeball when you are up here for 6 months"


def test_a_short_heading_in_the_models_own_words_is_kept():
    assert ch.grounded_title("Eye Health Issues", SAID)


def test_a_heading_about_something_never_said_is_not():
    assert not ch.grounded_title("Rocket Fuel Prices", SAID)


def test_invented_numbers_and_invented_names_in_a_sentence_are_still_refused():
    assert not ch.grounded_title("Eye Issues After 9 Months", SAID)
    assert not ch.grounded_title("What happens to eyes in Houston", SAID)
