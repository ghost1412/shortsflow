"""Woods are woods: palm trees only where the planner asks for palms."""
import xml.dom.minidom

from engine import case_story, story_art as sa


def drawing(ground, w=1080, h=1920):
    text = sa.backdrop_svg("day", ground, w, h)
    xml.dom.minidom.parseString(text)
    return text


def test_trees_are_not_the_palm_drawing_and_palms_are_their_own_ground():
    assert "palms" in sa.GROUNDS and drawing("trees") != drawing("palms")
    for w, h in ((1080, 1920), (1920, 1080)):
        woods = drawing("trees", w, h)
        assert woods.count("<circle") > drawing("none", w, h).count("<circle") + 10      # leafy crowns
        assert 'stroke-width="9" fill="none"' not in woods                                 # the curved palm trunk
        assert 'stroke-width="9" fill="none"' in drawing("palms", w, h)


def test_the_planner_is_told_where_palms_belong():
    prompt = case_story.request({"sections": [{"id": "a", "title": "t", "narration": "Marie walks in Paris."}]}, {})
    assert "palms ONLY for deserts" in prompt and "trees, palms" in prompt
