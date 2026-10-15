"""
Baseball scorekeeping: count, outs, runners, runs, innings, walk-offs, with undo.

Pitches arrive as "ball" / "strike" (called or swinging) / "foul" / "hbp" / "in_play". The camera can
decide ball vs strike but not what happened to a ball put in play, so "in_play" must be followed by
play(<outcome>) before the next pitch; steals, wild pitches and corrections go through adjust().
"""
import copy
from typing import List, Optional, Tuple

PITCHES = ("ball", "strike", "foul", "hbp", "in_play")
PLAYS = ("out", "single", "double", "triple", "home_run", "error", "sac_fly", "double_play")
_HIT_BASES = {"single": 1, "double": 2, "triple": 3, "home_run": 4}


class Game:
    def __init__(self, away: str = "Away", home: str = "Home", innings: int = 9):
        self.away, self.home, self.innings = away, home, innings
        self.inning, self.top = 1, True
        self.outs = self.balls = self.strikes = 0
        self.bases: List[bool] = [False, False, False]  # runners on 1st, 2nd, 3rd
        self.line = {"away": [], "home": []}  # runs per completed / current inning
        self.awaiting_play = False
        self.over, self.winner = False, None
        self.log: List[dict] = []
        self.history: List[dict] = []

    # ---- read ----
    @property
    def count(self) -> Tuple[int, int]:
        return self.balls, self.strikes

    def runs(self) -> Tuple[int, int]:
        return sum(self.line["away"]), sum(self.line["home"])

    def to_dict(self) -> dict:
        return {**self._state(), "away": self.away, "home": self.home, "innings": self.innings,
                "runs": list(self.runs())}

    def dump(self) -> dict:
        """Everything needed to resume after a restart, undo history included."""
        return {**self.to_dict(), "history": copy.deepcopy(self.history)}

    @classmethod
    def load(cls, d: dict) -> "Game":
        g = cls(d["away"], d["home"], d["innings"])
        for k in ("inning", "top", "outs", "balls", "strikes", "bases", "line", "awaiting_play", "over", "winner", "log"):
            setattr(g, k, copy.deepcopy(d[k]))
        g.history = copy.deepcopy(d.get("history", []))
        return g

    # ---- actions ----
    def pitch(self, kind: str, info: Optional[dict] = None) -> None:
        """info (e.g. the measured mph, who made the call) is stored with the log entry."""
        if kind not in PITCHES:
            raise ValueError(f"unknown pitch {kind!r}")
        self._guard(playing=True)
        self._push()
        if kind == "ball":
            self.balls += 1
            if self.balls == 4:
                self._walk()
        elif kind == "strike":
            self.strikes += 1
            if self.strikes == 3:
                self._out(1)
        elif kind == "foul":
            self.strikes = min(2, self.strikes + 1)
        elif kind == "hbp":
            self._walk()
        else:
            self.awaiting_play = True
        self._record(kind, info)

    def play(self, outcome: str) -> None:
        if outcome not in PLAYS:
            raise ValueError(f"unknown play {outcome!r}")
        if not self.awaiting_play:
            raise ValueError("no ball was put in play")
        self._guard()
        self._push()
        self.awaiting_play = False
        if outcome in _HIT_BASES:
            self._hit(_HIT_BASES[outcome])
        elif outcome == "error":
            self._reset_count()
            self._force_advance()
            self._check_walk_off()
        elif outcome == "sac_fly":
            if self.bases[2] and self.outs < 2:  # the run counts only if it beats the third out
                self.bases[2] = False
                self._score(1)
            self._out(1)
        elif outcome == "double_play":
            if not any(self.bases):
                raise ValueError("a double play needs a runner on base")
            lead = 0 if self.bases[0] else max(i for i, b in enumerate(self.bases) if b)
            self.bases[lead] = False
            self._out(2)
        else:
            self._out(1)
        self._record(outcome)

    def adjust(self, bases: Optional[List[bool]] = None, runs: int = 0, outs: int = 0) -> None:
        """Manual correction (steal, wild pitch, pickoff, scoring error): bases replaces the runners;
        runs and outs are added for the batting team."""
        self._guard()
        self._push()
        if bases is not None:
            if len(bases) != 3:
                raise ValueError("bases must be [first, second, third]")
            self.bases = [bool(b) for b in bases]
        if runs:
            self._score(runs)
        if outs:
            self._out(outs, new_batter=False)
        self._record("adjust")

    def undo(self) -> bool:
        if not self.history:
            return False
        s = self.history.pop()
        (self.inning, self.top, self.outs, self.balls, self.strikes, self.bases, self.line,
         self.awaiting_play, self.over, self.winner, self.log) = (
            s["inning"], s["top"], s["outs"], s["balls"], s["strikes"], s["bases"], s["line"],
            s["awaiting_play"], s["over"], s["winner"], s["log"])
        return True

    # ---- rules ----
    def _guard(self, playing: bool = False) -> None:
        if self.over:
            raise ValueError("the game is over")
        if playing and self.awaiting_play:
            raise ValueError("resolve the ball in play first")

    def _state(self) -> dict:
        return {"inning": self.inning, "top": self.top, "outs": self.outs, "balls": self.balls,
                "strikes": self.strikes, "bases": list(self.bases), "line": copy.deepcopy(self.line),
                "awaiting_play": self.awaiting_play, "over": self.over, "winner": self.winner,
                "log": copy.deepcopy(self.log)}

    def _push(self) -> None:
        self.history.append(self._state())

    def _record(self, kind: str, info: Optional[dict] = None) -> None:
        self.log.append({"inning": self.inning, "top": self.top, "kind": kind, "balls": self.balls,
                         "strikes": self.strikes, "outs": self.outs, "runs": list(self.runs()), **(info or {})})

    def _reset_count(self) -> None:
        self.balls = self.strikes = 0

    def _side(self) -> str:
        return "away" if self.top else "home"

    def _ensure_line(self) -> None:
        """Line score has a (possibly 0) entry for every half-inning that has started."""
        want = {"away": self.inning, "home": self.inning if not self.top else self.inning - 1}
        for side, n in want.items():
            self.line[side] += [0] * (n - len(self.line[side]))

    def _score(self, n: int) -> None:
        self._ensure_line()
        self.line[self._side()][self.inning - 1] += n
        self._check_walk_off()

    def _check_walk_off(self) -> None:
        if not self.top and self.inning >= self.innings and self.runs()[1] > self.runs()[0]:
            self.over, self.winner = True, "home"

    def _force_advance(self) -> None:
        """Batter takes first; only runners forced by it move."""
        b = self.bases
        if b[0]:
            if b[1]:
                if b[2]:
                    self._score(1)
                b[2] = True
            b[1] = True
        b[0] = True

    def _walk(self) -> None:
        self._reset_count()
        self._force_advance()
        self._check_walk_off()

    def _hit(self, n: int) -> None:
        self._reset_count()
        new, scored = [False, False, False], 0
        for i, runner in enumerate(self.bases):
            if runner:
                pos = i + 1 + n
                if pos > 3:
                    scored += 1
                else:
                    new[pos - 1] = True
        if n == 4:
            scored += 1
        else:
            new[n - 1] = True
        self.bases = new
        if scored:
            self._score(scored)

    def _out(self, n: int, new_batter: bool = True) -> None:
        self.outs += n
        if new_batter:
            self._reset_count()
        if self.outs >= 3:
            self._end_half()

    def _end_half(self) -> None:
        self._ensure_line()
        self.outs, self.bases = 0, [False, False, False]
        self._reset_count()
        away, home = self.runs()
        if self.top:
            if self.inning >= self.innings and home > away:  # the home team does not bat when ahead
                self.over, self.winner = True, "home"
            self.top = False
        else:
            if self.inning >= self.innings and away != home:
                self.over, self.winner = True, "away" if away > home else "home"
            self.inning, self.top = self.inning + 1, True
