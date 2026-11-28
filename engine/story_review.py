"""The story look reviews its own plan, fixes what it can and says what it could not.

1. Coverage: the text model lists who and what a viewer must see to follow the narration (each one must really be named in it). What the plan never shows is
   missing; a creature the plan drew as an ordinary person counts as missing too.
2. Pictures: every object on a card or beside a speaker is judged against its own sentence and the story's time and world. Judging is in two steps, so that
   nothing can simply agree with what it is told: the image model says what the picture shows without knowing the sentence (`story_objects.describe_all`), then
   the text model decides whether that fits.
3. Fix: a wrong picture is replaced by a drawing of what the sentence needs (drawn for the story's setting, with the reason of the rejection, and judged again),
   or removed. A missing person is described and put on screen at the sentence that names them; a missing creature is drawn whole and judged; a missing thing is
   drawn and shown beside the speaker.
4. Report: what was replaced, removed and added, and what is still missing, goes into the run (`story_review.json`) and into decisions.md.

The review can only fix what the engine can draw and show. It cannot add movement, and the models that judge can be wrong in both directions.
"""
import json
import os
import re

from engine import case_story, story_art, story_objects

KINDS = ("person", "creature", "thing")
MAX_NEEDED = 12
FIX_TRIES = 2
MAX_NEW_PEOPLE = 3


def _json(reply):
    from engine.script_gen import robust_json_parse
    try:
        return robust_json_parse(reply)
    except Exception:
        return None


def _ask_rows(ask, prompt, key):
    """The list under `key` in the model's JSON answer (a bare list counts), or None when there is no usable answer after a few tries."""
    return story_objects.patiently(lambda: story_objects.rows_of(_json(ask(prompt)), key), "text model (review)")


def _sentences(script):
    from engine import case_story
    return [case_story.sentences(s.get("narration")) for s in script["sections"]]


def _named(name, text):
    words = [w for w in re.findall(r"[^\W\d_]+", name.lower()) if len(w) >= 3 and w not in ("the", "and", "king", "queen")]
    return bool(words) and any(re.search(rf"\b{re.escape(w[:max(3, len(w) - 1)])}", text.lower()) for w in words)


# ---------------------------------------------------------------- 1. what has to be on screen

# beings a narration may call creatures that are simply people to draw, and the look tradition gives them when the model describes none
PERSON_ROLES = {"witch": {"figure": "woman", "age": "old", "headgear": "hood", "outfit": "robe", "outfit_colour": "black", "mood": "stern"},
                "hag": {"figure": "woman", "age": "old", "headgear": "hood", "outfit": "robe", "outfit_colour": "black", "mood": "stern"},
                "sorceress": {"figure": "woman", "headgear": "hood", "outfit": "robe", "outfit_colour": "purple"},
                "enchantress": {"figure": "woman", "outfit": "robe", "outfit_colour": "purple"},
                "wizard": {"age": "old", "facial_hair": "long_beard", "headgear": "hood", "outfit": "robe", "outfit_colour": "blue"},
                "sorcerer": {"facial_hair": "beard", "headgear": "hood", "outfit": "robe", "outfit_colour": "purple"}}


def _person_role(item):
    """The role ("witch") when this "creature" is really a person: that word in its name, no animal's shape and no monster features."""
    role = next((w for w in re.findall(r"[a-z]+", item["name"].lower()) if w in PERSON_ROLES), None)
    species = str(item.get("species") or "").strip().lower()
    return role if role and species in ("", "human", "other") and not item.get("features") else None


def needed_question(script):
    lines = [f"{si}.{k} {s}" for si, sents in enumerate(_sentences(script), 1) for k, s in enumerate(sents, 1)]
    return ("This is the narration of a short story video, each sentence numbered section.sentence:\n" + "\n".join(lines) + "\n\n"
            f"List, most important first and at most {MAX_NEEDED}, who and what a viewer MUST see to follow it: people (kind \"person\": human-shaped, including gods), "
            "creatures (kind \"creature\": a monster, beast or being that does not look like a person), and objects, vehicles or places the story turns on (kind \"thing\"). "
            "Use the narration's own name. For a creature also give \"species\" (the nearest of: " + ", ".join(story_art.SPECIES[1:]) + "; \"human\" for a monster with a person's shape; "
            "\"other\" when none of these is close, like a dragon) and \"features\" (any of: horns, fangs, glowing_eyes, spread_wings, snake_hair). For a creature also give \"tone\": \"threatening\" (an enemy or monster), \"gentle\" or \"neutral\". List each person or creature ONCE: when the narration (or the story it tells) calls one by two names or a title, put the other "
            "names under \"also\" (a queen who is also called by her title is one person). \"at\" is the first sentence that names it, as section.sentence. \"looks\" says in at most 10 words how it looks in this story's "
            "tradition, for a creature or a thing (like \"huge black horned smoke demon\"). Never list a feeling or an idea.\n\n"
            "Reply with raw JSON only: {\"needed\": [{\"name\": \"...\", \"also\": [], \"kind\": \"person\", \"at\": \"1.1\", \"looks\": \"\", \"tone\": \"\"}]}")


def needed(script, ask):
    """[{name, kind, section, sentence, looks}] the narration really names, or None when the model gave no usable list."""
    rows = _ask_rows(ask, needed_question(script), "needed")
    if rows is None:
        return None
    sents = _sentences(script)
    out = []
    for r in rows:
        name = " ".join(str(r.get("name") or "").split())[:40]
        kind = str(r.get("kind") or "").lower()
        m = re.match(r"\s*(\d+)\.(\d+)", str(r.get("at") or ""))
        if not name or kind not in KINDS or not m:
            continue
        si, k = int(m.group(1)) - 1, int(m.group(2))
        if not (0 <= si < len(sents) and 1 <= k <= len(sents[si])):
            continue
        if not _named(name, sents[si][k - 1]):                       # the model's sentence number may be off: find the first sentence that does name it
            hit = next(((i, j) for i, row in enumerate(sents) for j, s in enumerate(row, 1) if _named(name, s)), None)
            if not hit:
                continue                                             # not in the narration at all: never invented
            si, k = hit
        also = [" ".join(str(a).split())[:30] for a in (r.get("also") if isinstance(r.get("also"), list) else []) if str(a).strip()][:4]
        if all(not any(_same(x, y) for x in [name, *also] for y in [o["name"], *o["also"]]) for o in out):
            tone = str(r.get("tone") or "").lower()
            out.append({"name": name, "also": also, "kind": kind, "section": si, "sentence": k, "looks": " ".join(str(r.get("looks") or "").split())[:80],
                        "tone": tone if tone in story_objects.TONES else ("threatening" if kind == "creature" else ""),
                        "species": str(r.get("species") or "").strip().lower(), "features": r.get("features") if isinstance(r.get("features"), list) else []})
    return out[:MAX_NEEDED]


def _same(a, b):
    a, b = (re.sub(r"^(the|a|an)\s+", "", x.lower()).strip() for x in (a, b))
    return a == b or a in b.split() or b in a.split() or a.rstrip("s") == b.rstrip("s")


def shown_as(plan, item):
    """How the plan shows a needed item: the character's name, the emblem, a card's title, or None."""
    beats = [b for s in plan["sections"] for b in s["beats"]]
    if item["kind"] in ("person", "creature"):
        names = [item["name"], *item.get("also", [])]
        hit = next((b["character"] for b in beats if b.get("character") and any(_same(b["character"], n) for n in names)), None)
        if hit and item["kind"] == "creature" and not story_art.is_beast(plan["characters"].get(hit, {})):
            return None                                              # drawn as an ordinary person: not shown as what it is
        return hit
    for b in beats:
        for emblem in [b.get("emblem"), *[a["emblem"] for a in b.get("asides", [])]]:
            thing = (emblem or "").replace("custom:", "")
            if thing and (_same(thing, item["name"]) or any(_same(thing, w) for w in item["name"].lower().split() if len(w) > 3)):
                return emblem
    return None


# ---------------------------------------------------------------- 2. do the pictures fit

RULES = ("In a short video, each picture below is shown while its sentence is spoken. For EACH, decide whether to keep it.\n"
         "Every picture is a flat modern cartoon drawing: its drawing style and colours NEVER make it modern or wrong. Only the KIND of object can be too late for the "
         "story (a steamship or motor ship, a stethoscope, a gun in an ancient tale); a maze, a crown, a sword, a sailing ship are fine at any time (a maze shows a "
         "labyrinth).\nKeep it only when the picture IS a thing this sentence talks about, or the one sign everybody reads as it. Reject it when the sentence is about "
         "something else, even something often found nearby: mountains are not an island, a chest is not sand, a wolf is not a sheep.\n"
         "For a rejected picture, \"should\" names in one to three plain words the one physical thing from the sentence that should be drawn instead (never a person), "
         "or \"\" when the sentence names no such thing.\n\n")


def judge_question(setting, items):
    lines = "\n".join(f"{i}. Story: {setting}. The narrator says: \"{it['sentence']}\" The picture on screen shows: {it['seen']}" for i, it in enumerate(items, 1))
    return RULES + lines + "\n\nReply with raw JSON only: {\"verdicts\": [{\"id\": 1, \"keep\": true, \"why\": \"few words\", \"should\": \"\"}]}"


def judge(items, setting, ask):
    """[{keep, why, should}] for [{sentence, seen}] in order, None when it cannot be judged."""
    rows = _ask_rows(ask, judge_question(setting, items), "verdicts") if items else []
    if rows is None:
        return None
    by_id = {}
    for r in rows:
        try:
            by_id[int(r["id"])] = {"keep": r.get("keep") is True, "why": str(r.get("why") or "")[:120],
                                   "should": re.sub(r"[^a-z' -]", "", str(r.get("should") or "").lower()).strip()[:30]}
        except (KeyError, TypeError, ValueError):
            continue
    return [by_id.get(i) for i in range(1, len(items) + 1)] if by_id else None


def _pictures(plan, script, drawn):
    """Every object the plan shows, with the sentence it is shown with."""
    sents = _sentences(script)
    out = []
    for si, (row, said) in enumerate(zip(plan["sections"], sents)):
        for b in row["beats"]:
            places = [("card", b, b.get("emblem"), b["sentence"])] if b.get("emblem") else []
            places += [("aside", b, a["emblem"], a["sentence"]) for a in b.get("asides", [])]
            for where, beat, emblem, k in places:
                if emblem.startswith("custom:"):
                    path = drawn.get(emblem[len("custom:"):])
                    if not path:
                        continue
                    with open(path, encoding="utf-8") as f:
                        document = f.read()
                else:
                    document = story_art.emblem_svg(emblem)
                if document and 0 < k <= len(said):
                    out.append({"where": where, "section": si, "beat": beat, "emblem": emblem, "k": k, "sentence": said[k - 1], "svg": document})
    return out


def _remove(plan, item):
    """Takes a picture off the screen: an object beside a speaker goes; a card with it gives the screen back to the face before it."""
    beat = item["beat"]
    if item["where"] == "aside":
        beat["asides"] = [a for a in beat["asides"] if not (a["emblem"] == item["emblem"] and a["sentence"] == item["k"])]
        if not beat["asides"]:
            beat.pop("asides")
        return
    beats = plan["sections"][item["section"]]["beats"]
    i = beats.index(beat)
    face = next((b for b in reversed(beats[:i]) if b.get("character")), None) or next((b for b in beats[i + 1:] if b.get("character")), None)
    if face:
        beats[i] = dict(face, sentence=beat["sentence"], asides=[])
        beats[i].pop("asides")
    else:
        beat["emblem"] = ""                                          # nobody to give the screen to: the card keeps its title alone


def _swap(item, emblem):
    from engine import case_story
    if item["where"] == "card":
        item["beat"]["emblem"] = emblem
        item["beat"]["name"] = case_story._clip(emblem.replace("custom:", "").title(), case_story.MAX_NAME)
    else:
        for a in item["beat"]["asides"]:
            if a["emblem"] == item["emblem"] and a["sentence"] == item["k"]:
                a["emblem"] = emblem
    item["emblem"] = emblem


def portrait_question(setting, name, looks, tone, seen):
    wanted = {"threatening": "It is an enemy or monster, so it must feel threatening: a friendly, cute or smiling one is rejected.",
              "gentle": "It must not feel threatening.", "neutral": ""}.get(tone, "")
    return ("A drawing is shown as the PORTRAIT of a being in a short story video. Judge only whether it works as that being, in this story's time and world. A portrait "
            "does not have to show what the being does. " + wanted + "\nEvery drawing is a flat modern cartoon: its drawing style never makes it wrong.\n"
            f"1. Story: {setting}. The being: {name}" + (f", {looks}" if looks else "") + f". Someone who was not told what it is sees: {seen}\n\n"
            "Reply with raw JSON only: {\"verdicts\": [{\"id\": 1, \"keep\": true, \"why\": \"few words\"}]}")


def _draw_figure(name, looks, tone, setting, ask, folder, vision, render):
    """A drawing of a being that is recognised from what it looks like AND works as its portrait with the right feel: (path, "") or (None, why not). It is judged
    as a portrait: asked to show its sentence, a monster was once refused for not showing the fight."""
    subject = looks or name.lower()
    note = ""
    for _ in range(FIX_TRIES):
        got = story_objects.make([subject], ask, folder, vision=vision, render=render, setting=setting, feedback=note, fresh=bool(note), tone=tone or "neutral")[subject]
        if not got["path"]:
            return None, got["status"]
        with open(got["path"], encoding="utf-8") as f:
            document = f.read()
        seen = story_objects.describe_all([document], folder, vision, render, feeling=True)
        rows = _ask_rows(ask, portrait_question(setting, name, looks, tone, seen[0]), "verdicts") if seen else None
        if not rows:
            return None, "could not be judged"
        if rows[0].get("keep") is True:
            return got["path"], ""
        note = str(rows[0].get("why") or "")[:120]
    return None, f"rejected: {note}"


def _draw_for(thing, sentence, setting, ask, folder, vision, render, why=""):
    """A drawing of `thing` that is recognised AND fits the sentence and the setting: (path, "") or (None, why not)."""
    note = why
    for _ in range(FIX_TRIES):
        got = story_objects.make([thing], ask, folder, vision=vision, render=render, setting=setting, feedback=note, fresh=bool(note))[thing]
        if not got["path"]:
            return None, got["status"]
        with open(got["path"], encoding="utf-8") as f:
            document = f.read()
        seen = story_objects.describe_all([document], folder, vision, render)
        verdict = judge([{"sentence": sentence, "seen": seen[0]}], setting, ask) if seen else None
        if not verdict or not verdict[0]:
            return None, "could not be judged"
        if verdict[0]["keep"]:
            return got["path"], ""
        note = verdict[0]["why"]
    return None, f"rejected: {note}"


def review_pictures(plan, script, ask, folder, drawn, vision, render, report):
    items = _pictures(plan, script, drawn)
    if not items:
        return
    seen = story_objects.describe_all([it["svg"] for it in items], folder, vision, render)
    verdicts = judge([dict(it, seen=s) for it, s in zip(items, seen)], plan.get("setting") or script.get("title", ""), ask) if seen else None
    if verdicts is None:
        report["notes"].append(f"{len(items)} picture(s) could not be checked (no image model, or no usable answer)")
        return
    setting = plan.get("setting") or script.get("title", "")
    for it, shows, v in zip(items, seen, verdicts):
        label = it["emblem"].replace("custom:", "")
        report["checked"] += 1
        if v is None or v["keep"]:
            continue
        new, trouble = None, "the sentence names nothing else to draw"
        if v["should"]:
            new, trouble = _draw_for(v["should"], it["sentence"], setting, ask, folder, vision, render, why=v["why"])
        if new:
            _swap(it, "custom:" + v["should"])
            drawn[v["should"]] = new
            report["replaced"].append({"was": label, "now": v["should"], "sentence": it["sentence"], "why": v["why"]})
        else:
            _remove(plan, it)
            report["removed"].append({"was": label, "sentence": it["sentence"], "why": v["why"], "looked like": shows, "no replacement because": trouble})


# ---------------------------------------------------------------- 3. what is missing

def _put_on_screen(plan, item, name):
    """Gives the sentence that names a person or creature their face; the face before comes back on the next sentence. False when that sentence shows something else."""
    from engine import case_story
    row = plan["sections"][item["section"]]
    k = item["sentence"]
    at = {b["sentence"]: b for b in row["beats"]}
    here = at.get(k)
    if here and (here.get("emblem") or here.get("big")):
        return False
    shown = here.get("character") if here else None
    if shown and shown != name and sum(b.get("character") == shown for s in plan["sections"] for b in s["beats"]) < 2:
        return False                                        # it is the only time that one is seen
    before = at[max(n for n in at if n <= k)]
    new = {"sentence": k, "character": name, "name": case_story._clip(name, case_story.MAX_NAME), "role": "", "mood": "", "emblem": "", "big": "", "label": ""}
    if here and here.get("asides"):
        new["asides"] = here["asides"]
    row["beats"] = [b for b in row["beats"] if b["sentence"] != k] + [new]
    total = item.get("count", k)
    if k < total and k + 1 not in at:
        back = dict(before)
        back.pop("asides", None)
        row["beats"].append(dict(back, sentence=k + 1))
    row["beats"].sort(key=lambda b: b["sentence"])
    return True


def _describe_people(names, script, ask):
    prompt = ("Describe each of these people from the story \"" + str(script.get("title", "")) + "\" as a bust: " + ", ".join(names) + ". For each, choose only from these values: "
              f"figure: {', '.join(story_art.FIGURES)}; hair: {', '.join(story_art.HAIR)}; hair_colour: {', '.join(story_art.HAIR_COLOURS)}; skin: {', '.join(story_art.SKIN)}; "
              f"headgear: {', '.join(story_art.HEADGEAR)}; facial_hair: {', '.join(story_art.FACIAL_HAIR)}; outfit: {', '.join(story_art.OUTFITS)}; outfit_colour: "
              f"{', '.join(story_art.COLOURS)}; weapon: {', '.join(story_art.WEAPONS)}; mood: {', '.join(story_art.MOODS)}; age: {', '.join(story_art.AGES)}; species (human, or the animal it is): {', '.join(story_art.SPECIES)}.\n"
              "Reply with raw JSON only: {\"people\": [{\"name\": \"...\", \"figure\": \"...\"}]}")
    rows = _ask_rows(ask, prompt, "people") or []
    return {str(r.get("name")): story_art.clean_spec(r) for r in rows if r.get("name")}


def _from_parts(plan, item):
    """A creature the drawing kit can build (an animal it has, or a person's shape with monster features) gets that, which is dependable; its name in the
    cast, or None when only a new drawing can show it. A cast member who already looks like it is kept as it is."""
    names = [item["name"], *item.get("also", [])]
    who = next((n for n in plan["characters"] if any(_same(n, other) for other in names)), None)
    if who and story_art.is_beast(plan["characters"][who]):
        return who
    species = str(item.get("species") or "").strip().lower()
    features = [str(f).strip().lower() for f in item.get("features") or [] if isinstance(f, str)]
    marks = [f for f in features if f in story_art.story_beasts.FEATURES]
    snakes = "snake_hair" in features
    if species not in story_art.SPECIES[1:] and not (species == "human" and (marks or snakes)):
        return None
    base = dict(plan["characters"].get(who) or {"mood": "angry" if item.get("tone") == "threatening" else "neutral"})
    if species != "human":
        base.update(species=species, outfit=base.get("outfit") if who else "none")
    base["ornaments"] = [*(base.get("ornaments") or []), *marks]
    if snakes:
        base["hair"] = "snakes"
    who = who or item["name"]
    plan["characters"][who] = story_art.clean_spec(base)
    return who


def _drop_human_picture(plan, item):
    """A creature that could not be drawn must not stay on screen as a person (a hare as a man with a moustache misleads more than a name does):
    its bust leaves the cast and each of its beats becomes a card with its name. True when there was such a bust."""
    names = [item["name"], *item.get("also", [])]
    human = [n for n, spec in plan["characters"].items() if not story_art.is_beast(spec) and any(_same(n, other) for other in names)]
    for who in human:
        del plan["characters"][who]
        for section in plan["sections"]:
            for beat in section["beats"]:
                if beat.get("character") == who:
                    beat.update(character=None, name=who, mood="", role="", emblem="", big=beat.get("big", ""), label=beat.get("label", ""))
    return bool(human)


def review_coverage(plan, script, ask, folder, drawn, vision, render, report):
    wanted = needed(script, ask)
    if wanted is None:
        report["notes"].append("who and what must be seen could not be listed, so nothing missing was looked for")
        return
    report["needed"] = [w["name"] for w in wanted]
    setting = plan.get("setting") or script.get("title", "")
    sents = _sentences(script)
    wanted = [dict(w, kind="person") if w["kind"] == "creature" and _person_role(w) else w for w in wanted]
    missing = [dict(w, count=len(sents[w["section"]])) for w in wanted if not shown_as(plan, w)]
    for m in missing:       # already in the cast under a near name ("Witch" for "the witch") but not on screen: show that one, do not add a twin
        twin = next((n for n in plan["characters"] if m["kind"] == "person" and any(_same(n, other) for other in [m["name"], *m.get("also", [])])), None)
        if twin:
            m["name"] = twin
    people = [m for m in missing if m["kind"] == "person"][:MAX_NEW_PEOPLE]
    unknown = [m["name"] for m in people if m["name"] not in plan["characters"]]
    specs = _describe_people(unknown, script, ask) if unknown else {}
    for item in missing:
        name, sentence = item["name"], sents[item["section"]][item["sentence"] - 1]
        why = ""
        if item["kind"] == "person":
            spec = plan["characters"].get(name) or next((s for n, s in specs.items() if _same(n, name)), None)
            role = next((w for w in re.findall(r"[a-z]+", name.lower()) if w in PERSON_ROLES), None)
            if not spec and role:
                spec = story_art.clean_spec(PERSON_ROLES[role])
            if spec and name not in plan["characters"]:       # the same rules as the first plan: believe the name and the narration, no twins
                told = " ".join(str(s.get("narration") or "") for s in script["sections"])
                spec = case_story.apply_facts(spec, case_story.facts_from(name, told))
                spec = case_story.tell_apart({**plan["characters"], name: spec}, fixed=set(plan["characters"]))[name]
            if item not in people:
                why = f"only {MAX_NEW_PEOPLE} missing people are added"
            elif not spec:
                why = "the model did not describe this person"
            else:
                plan["characters"][name] = spec
                if not _put_on_screen(plan, item, name):
                    why = "the sentence that names them already shows something that cannot give way"
        else:
            looks = re.sub(r"^(a|an|the)\s+", "", re.sub(r"[^a-z' -]", " ", item["looks"].lower()).strip())
            looks = " ".join(looks.split()[:7])
            built = _from_parts(plan, item) if item["kind"] == "creature" else None
            if built:
                who, why = built, ""
                if not any(b.get("character") == who for s in plan["sections"] for b in s["beats"]) and not _put_on_screen(plan, item, who):
                    why = "the sentence that names it already shows something that cannot give way"
                path = None
            elif item["kind"] == "creature":
                path, why = _draw_figure(name, looks, item.get("tone") or "threatening", setting, ask, folder, vision, render)
            else:
                extra = f". The {name} looks like: {looks}" if looks else ""
                path, why = _draw_for(name.lower(), sentence, setting + extra, ask, folder, vision, render)
            if built:
                pass
            elif path and item["kind"] == "creature":
                existing = next((n for n in plan["characters"] if _same(n, name)), None)
                who = existing or name
                plan["characters"][who] = {"creature": path}
                if not any(b.get("character") == who for s in plan["sections"] for b in s["beats"]) and not _put_on_screen(plan, item, who):
                    why = "the sentence that names it already shows something that cannot give way"
            elif path:
                row = plan["sections"][item["section"]]
                beat = [b for b in row["beats"] if b["sentence"] <= item["sentence"]][-1]
                if beat.get("emblem") or beat.get("big") or any(a["sentence"] == item["sentence"] for a in beat.get("asides", [])):
                    why = "the screen already shows a thing at that sentence"
                else:
                    drawn[name.lower()] = path
                    beat.setdefault("asides", []).append({"sentence": item["sentence"], "emblem": "custom:" + name.lower()})
        if why and item["kind"] == "creature" and _drop_human_picture(plan, item):
            why += "; its picture as a human was taken out, so only its name is shown"
        if why:
            report["left"].append({"name": name, "kind": item["kind"], "why": why})
        else:
            report["added"].append({"name": name, "kind": item["kind"], "sentence": sentence})
    note_lost(plan, wanted, report)


def note_lost(plan, wanted, report):
    """The last look: a needed person or creature that no beat shows is reported, whatever took it off the screen (it may have been there before the review)."""
    told = {x["name"] for x in report["left"]}
    for item in wanted:
        if item["kind"] in ("person", "creature") and item["name"] not in told and not shown_as(plan, item):
            report["left"].append({"name": item["name"], "kind": item["kind"], "why": "no picture of them is on screen"})


def run(plan, script, ask, folder, drawn, vision=None, render=None):
    """Reviews and fixes `plan` in place (and adds to `drawn`, {name: svg path}). Returns the report: {checked, needed, replaced, removed, added, left, notes}."""
    if vision is None:
        from engine.visual_context import choose_backend
        vision = choose_backend()
    report = {"checked": 0, "needed": [], "replaced": [], "removed": [], "added": [], "left": [], "notes": []}
    if not ask:
        report["notes"].append("no text model, so nothing was reviewed")
        return report
    review_pictures(plan, script, ask, folder, drawn, vision, render, report)
    review_coverage(plan, script, ask, folder, drawn, vision, render, report)
    return report


def summary(report):
    """The report as lines for decisions.md."""
    lines = [f"- pictures checked against their sentences: {report.get('checked', 0)}"]
    lines += [f"- replaced: {r['was']} -> {r['now']} ({r['why']})" for r in report.get("replaced", [])]
    lines += [f"- removed: {r['was']} ({r['why']}; {r['no replacement because']})" for r in report.get("removed", [])]
    lines += [f"- added, it was missing: {r['name']} ({r['kind']})" for r in report.get("added", [])]
    lines += [f"- STILL MISSING: {r['name']} ({r['kind']}): {r['why']}" for r in report.get("left", [])]
    lines += [f"- note: {n}" for n in report.get("notes", [])]
    if not report.get("left"):
        lines.append("- nothing it listed as necessary is still missing (it cannot judge movement, pacing or whether events are told correctly)")
    return lines


def save(report, session_dir):
    with open(os.path.join(session_dir, "story_review.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
