"""One way for a mode to take its options: a schema, not one command-line flag per option.

A mode declares an `OptionSet` (a name and a list of `Option`s). Its command line is then ONE repeatable flag, `--<name> KEY=VALUE` (plus
`--<name>_file FILE.json` for saved settings), and the same schema serves the browser tab, other callers and the tests: parsing, validation,
`--<name> help` text and the defaults all come from it. A new option is one line.

    CASE = OptionSet("case", [Option("theme", "choice", "dark", "the look", ("dark", "neon")), Option("draft", "switch", False, "a quick draft")])
    CASE.parse(["theme=neon", "draft"])        # {"theme": "neon", "draft": True}
    CASE.from_args(args)                       # reads args.case and args.case_file

Kinds: "text", "choice" (must be one of `choices`), "switch" (KEY, KEY=on, KEY=off), "path" (quotes stripped). An `Option` may carry `check`, a
function that takes the raw text and returns the value or raises `OptionError` with a plain message.
"""
import json
from dataclasses import dataclass
from typing import Callable, Optional

_TRUE, _FALSE = ("", "1", "true", "yes", "on"), ("0", "false", "no", "off")


class OptionError(ValueError):
    """A bad key or value: the message says what is allowed."""


@dataclass(frozen=True)
class Option:
    key: str
    kind: str                     # "text", "choice", "switch", "path"
    default: object
    help: str
    choices: tuple = ()
    check: Optional[Callable] = None


class OptionSet:
    def __init__(self, name, options):
        self.name = name
        self.options = tuple(options)
        self.by_key = {o.key: o for o in self.options}
        if len(self.by_key) != len(self.options):
            raise ValueError(f"{name}: an option key is used twice")

    def defaults(self):
        return {o.key: o.default for o in self.options}

    def describe(self):
        """The options as plain help text, one line each."""
        lines = [f"{self.name.upper()} options (use --{self.name} KEY=VALUE, repeatable; a bare switch means on):"]
        for o in self.options:
            shown = o.default if o.kind != "switch" else ("on" if o.default else "off")
            extra = f" [{' | '.join(o.choices)}]" if o.choices else ""
            lines.append(f"  {o.key:<11} {o.help}{extra} (default: {shown or '-'})")
        return "\n".join(lines)

    def _value(self, option, raw):
        raw = str(raw).strip()
        if option.check:
            return option.check(raw)
        if option.kind == "switch":
            low = raw.lower()
            if low in _TRUE:
                return True
            if low in _FALSE:
                return False
            raise OptionError(f"'{option.key}' is a switch: use {option.key}, {option.key}=on or {option.key}=off (got '{raw}').")
        if option.kind == "choice" and raw not in option.choices:
            raise OptionError(f"'{option.key}' must be one of: {', '.join(option.choices)} (got '{raw}').")
        return raw.strip('"') if option.kind == "path" else raw

    def parse(self, pairs=None, file=None):
        """The options as a dict with every key set: defaults, then the JSON `file`, then the "key=value" `pairs` (later ones win).
        Raises OptionError for an unknown key or a bad value; the key `help` raises it with `describe()` as the message."""
        values = self.defaults()
        items = []
        if file:
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError) as e:
                raise OptionError(f"The settings file could not be read: {e}")
            if not isinstance(data, dict):
                raise OptionError("The settings file must hold one JSON object of option names and values.")
            items += [(k, "on" if v is True else "off" if v is False else v) for k, v in data.items()]
        items += [tuple((str(p).split("=", 1) + [""])[:2]) for p in (pairs or [])]
        for key, raw in items:
            key = str(key).strip().lower()
            if key == "help":
                raise OptionError(self.describe())
            option = self.by_key.get(key)
            if option is None:
                raise OptionError(f"Unknown {self.name.upper()} option '{key}'. Known: {', '.join(self.by_key)}.")
            values[key] = self._value(option, raw)
        return values

    def from_args(self, args):
        """The options of a parsed command line: `--<name>` pairs and `--<name>_file`."""
        return self.parse(getattr(args, self.name, None), getattr(args, f"{self.name}_file", None))

    def to_pairs(self, values):
        """The `--<name> KEY=VALUE` strings that give `values` back (only what differs from the defaults), for building a command line."""
        out = []
        for o in self.options:
            v = values.get(o.key, o.default)
            if v == o.default or v in (None, ""):
                continue
            out.append(o.key if (o.kind == "switch" and v is True) else f"{o.key}={'off' if v is False else v}")
        return out
