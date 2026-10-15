"""Baseball scorekeeping rules: count, walks, strikeouts, runners, outs, innings, walk-offs, undo."""
import pytest

from velopath.scorebook import Game


def throw(g, *kinds):
    for k in kinds:
        g.pitch(k)


def test_count_and_strikeout():
    g = Game()
    throw(g, "ball", "strike", "strike")
    assert (g.balls, g.strikes, g.outs) == (1, 2, 0)
    g.pitch("strike")  # strike three
    assert (g.balls, g.strikes, g.outs) == (0, 0, 1)


def test_foul_is_a_strike_until_two_strikes():
    g = Game()
    throw(g, "foul", "foul", "foul", "foul")
    assert (g.strikes, g.outs) == (2, 0)  # fouls with two strikes never strike the batter out
    g.pitch("strike")
    assert g.outs == 1


def test_walk_forces_runners_one_base():
    g = Game()
    throw(g, "ball", "ball", "ball", "ball")
    assert g.bases == [True, False, False] and g.count == (0, 0)
    throw(g, "ball", "ball", "ball", "ball")
    assert g.bases == [True, True, False]


def test_bases_loaded_walk_scores_a_run():
    g = Game()
    for _ in range(3):
        throw(g, "ball", "ball", "ball", "ball")
    assert g.bases == [True, True, True] and g.runs() == (0, 0)
    throw(g, "ball", "ball", "ball", "ball")
    assert g.runs() == (1, 0) and g.bases == [True, True, True]


def test_walk_does_not_move_a_runner_on_second_alone():
    g = Game()
    g.adjust(bases=[False, True, False])
    throw(g, "ball", "ball", "ball", "ball")
    assert g.bases == [True, True, False]  # runner on 2nd was not forced
    g = Game()
    g.adjust(bases=[False, False, True])
    throw(g, "ball", "ball", "ball", "ball")
    assert g.bases == [True, False, True] and g.runs() == (0, 0)


def test_hit_by_pitch_is_a_walk():
    g = Game()
    g.pitch("hbp")
    assert g.bases == [True, False, False] and g.count == (0, 0)


@pytest.mark.parametrize("outcome,bases_after,runs", [
    ("single", [True, False, False], 0),
    ("double", [False, True, False], 0),
    ("triple", [False, False, True], 0),
    ("home_run", [False, False, False], 1),
])
def test_hits_with_empty_bases(outcome, bases_after, runs):
    g = Game()
    g.pitch("in_play")
    g.play(outcome)
    assert g.bases == bases_after and g.runs() == (runs, 0)


def test_single_advances_every_runner_one_base_and_scores_from_third():
    g = Game()
    g.adjust(bases=[True, True, True])
    g.pitch("in_play")
    g.play("single")
    assert g.bases == [True, True, True] and g.runs() == (1, 0)


def test_double_scores_runners_from_second_and_third():
    g = Game()
    g.adjust(bases=[True, True, True])
    g.pitch("in_play")
    g.play("double")
    assert g.runs() == (2, 0) and g.bases == [False, True, True]


def test_grand_slam():
    g = Game()
    g.adjust(bases=[True, True, True])
    g.pitch("in_play")
    g.play("home_run")
    assert g.runs() == (4, 0) and g.bases == [False, False, False]


def test_out_keeps_runners_and_resets_count():
    g = Game()
    g.adjust(bases=[True, False, False])
    throw(g, "ball", "strike")
    g.pitch("in_play")
    g.play("out")
    assert g.outs == 1 and g.bases == [True, False, False] and g.count == (0, 0)


def test_sac_fly_scores_from_third_only_before_the_third_out():
    g = Game()
    g.adjust(bases=[False, False, True])
    g.pitch("in_play")
    g.play("sac_fly")
    assert g.outs == 1 and g.runs() == (1, 0)
    g = Game()
    g.adjust(bases=[False, False, True], outs=2)
    g.pitch("in_play")
    g.play("sac_fly")  # third out: the run does not count
    assert g.runs() == (0, 0) and (g.top, g.outs) == (False, 0)


def test_double_play_removes_the_runner_from_first():
    g = Game()
    g.adjust(bases=[True, False, True])
    g.pitch("in_play")
    g.play("double_play")
    assert g.outs == 2 and g.bases == [False, False, True]


def test_error_puts_the_batter_on_and_forces_runners():
    g = Game()
    g.adjust(bases=[True, False, False])
    g.pitch("in_play")
    g.play("error")
    assert g.bases == [True, True, False] and g.outs == 0


def test_three_outs_end_the_half_inning():
    g = Game()
    g.adjust(bases=[True, True, False])
    for _ in range(3):
        throw(g, "strike", "strike", "strike")
    assert (g.inning, g.top, g.outs) == (1, False, 0) and g.bases == [False] * 3 and g.count == (0, 0)
    for _ in range(3):
        throw(g, "strike", "strike", "strike")
    assert (g.inning, g.top) == (2, True)


def test_runs_go_into_the_line_score_by_inning():
    g = Game()
    g.pitch("in_play")
    g.play("home_run")  # top 1: away scores
    for _ in range(3):
        throw(g, "strike", "strike", "strike")
    g.pitch("in_play")
    g.play("home_run")  # bottom 1: home scores
    assert g.line["away"] == [1] and g.line["home"] == [1]


def test_in_play_must_be_resolved_before_the_next_pitch():
    g = Game()
    g.pitch("in_play")
    with pytest.raises(ValueError):
        g.pitch("ball")
    with pytest.raises(ValueError):
        Game().play("single")  # no ball was put in play


def _finish_half(g):
    for _ in range(3):
        throw(g, "strike", "strike", "strike")


def test_tied_after_top_of_last_inning_still_plays_the_bottom():
    g = Game(innings=1)
    _finish_half(g)  # top 1: 0-0
    assert not g.over and not g.top
    g.pitch("in_play")
    g.play("home_run")  # bottom 1: walk-off
    assert g.over and g.winner == "home"


def test_home_team_already_ahead_does_not_bat_in_the_last_half_inning():
    g = Game(innings=2)
    _finish_half(g)  # top 1
    g.pitch("in_play")
    g.play("home_run")  # bottom 1: home leads 1-0
    _finish_half(g)  # three outs end the bottom of the 1st
    _finish_half(g)  # top 2: away scores nothing
    assert g.over and g.winner == "home" and g.line["home"] == [1]  # bottom 2 never played


def test_walk_off_ends_the_game_immediately():
    g = Game(innings=9)
    g.inning, g.top = 9, False
    g.adjust(bases=[False, False, True])
    g.pitch("in_play")
    g.play("single")
    assert g.over and g.runs() == (0, 1) and g.winner == "home"


def test_tied_after_nine_goes_to_extra_innings():
    g = Game(innings=1)
    _finish_half(g)
    _finish_half(g)  # 0-0 after the bottom of the 1st
    assert not g.over and (g.inning, g.top) == (2, True)


def test_away_team_wins_when_home_cannot_catch_up():
    g = Game(innings=1)
    g.pitch("in_play")
    g.play("home_run")  # away leads 1-0
    _finish_half(g)
    _finish_half(g)  # bottom 1 ends, home still behind
    assert g.over and g.winner == "away"


def test_game_over_blocks_more_pitches():
    g = Game(innings=1)
    g.pitch("in_play")
    g.play("home_run")
    _finish_half(g)
    _finish_half(g)
    with pytest.raises(ValueError):
        g.pitch("ball")


def test_undo_restores_everything():
    g = Game()
    throw(g, "ball", "strike")
    before = g.to_dict()
    g.pitch("in_play")
    g.play("home_run")
    assert g.runs() == (1, 0)
    g.undo()  # the home run play
    g.undo()  # the in_play pitch
    assert g.to_dict() == before
    while g.undo():
        pass
    assert g.count == (0, 0) and g.history == [] and g.to_dict() == Game().to_dict()


def test_undo_on_a_fresh_game_is_a_noop():
    assert Game().undo() is False


def test_adjust_corrects_steals_wild_pitches_and_runs():
    g = Game()
    g.adjust(bases=[False, True, False], runs=1, outs=1)
    assert g.bases == [False, True, False] and g.runs() == (1, 0) and g.outs == 1
    g.adjust(outs=2)  # caught stealing -> third out ends the half
    assert (g.top, g.outs) == (False, 0)


def test_to_dict_is_json_ready_and_logs_each_event():
    import json
    g = Game(away="Lions", home="Tigers")
    g.pitch("ball")
    g.pitch("in_play")
    g.play("single")
    d = json.loads(json.dumps(g.to_dict()))
    assert d["away"] == "Lions" and d["home"] == "Tigers" and d["bases"] == [True, False, False]
    assert [e["kind"] for e in d["log"]] == ["ball", "in_play", "single"]


def test_dump_and_load_keep_state_and_undo_history():
    import json
    g = Game(away="Lions", home="Tigers", innings=7)
    g.pitch("ball")
    g.pitch("in_play")
    g.play("double")
    copy = Game.load(json.loads(json.dumps(g.dump())))
    assert copy.to_dict() == g.to_dict() and copy.innings == 7
    copy.undo()
    copy.undo()
    assert copy.count == (1, 0) and copy.bases == [False] * 3  # history came along
