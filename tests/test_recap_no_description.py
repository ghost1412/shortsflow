"""A recap never shows the prompt's note that a moment was not described ("Day 1: No Descriptions")."""
import json

import pytest

from engine import trip_recap as tr

DAYS = [{"moments": [{}, {}]}]


@pytest.mark.parametrize("text", ["Day 1: No Descriptions", "No description", "Moments without captions", "Not described", "Descriptions are missing"])
def test_words_about_missing_descriptions_are_not_used(text):
    assert tr.said(text) == ""


@pytest.mark.parametrize("text", ["No Place Like Home", "A day without cars", "The lighthouse no one visits", "Event Recap"])
def test_ordinary_titles_stay(text):
    assert tr.said(text) == text


def test_the_whole_itinerary_falls_back_field_by_field():
    reply = json.dumps({"title": "Day 1: No Descriptions", "hook": "You have to see this place.",
                        "days": [{"title": "No Descriptions", "summary": "The moments have no description.", "captions": ["no description", "The tower"]}]})
    got = tr.write_itinerary("", "", DAYS, ask=lambda p: reply, kind="event")
    assert "Descriptions" not in got["title"] and got["hook"] == "You have to see this place."
    assert "Descriptions" not in got["days"][0]["title"] and got["days"][0]["summary"] == "" and got["days"][0]["captions"] == ["", "The tower"]
