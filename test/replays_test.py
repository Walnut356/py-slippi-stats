#!/usr/bin/python3

# fmt: off
import datetime, glob, os, subprocess, unittest
from pathlib import Path

from slippistats.game import Game
from slippistats.parse import parse
from slippistats.enums.character import CSSCharacter, InGameCharacter
from slippistats.enums.item import Item
from slippistats.enums.stage import Stage
from slippistats.log import log
from slippistats.metadata import Metadata
from slippistats.event import Buttons, Direction, End, Frame, Position, Start, Triggers, Velocity
from slippistats.parse import ParseEvent
from slippistats.stats.stats_computer import StatsComputer
import polars as pl

BPhys = Buttons.Physical
BLog = Buttons.Logical


def norm(f):
    return 1 if f > 0.01 else -1 if f < -0.01 else 0


def path(name):
    return os.path.join(os.path.dirname(__file__), 'replays', name + '.slp')


class TestGame(unittest.TestCase):

    def __init__(self, *args, **kwargs) -> None:
        self.pkgname: str = "slippistats"
        super().__init__(*args, **kwargs)
        my_env = os.environ.copy()
        self.pypath: str = my_env.get("PYTHONPATH", os.getcwd())
        self.mypy_opts: list[str] = ['--ignore-missing-imports']

    def _game(self, name):
        return Game(path(name))

    def _stick_seq(self, game):
        pass

    # not used yet because the recorder currently puts bogus values in triggers.physical
    def _trigger_seq(self, game):
        last_triggers = None
        trigger_seq = []
        for frame in game.frames:
            t = frame.ports[0].leader.pre.triggers
            t = Triggers(norm(t.logical), norm(t.physical.l), norm(t.physical.r))
            if (t.logical or t.physical.l or t.physical.r) and t != last_triggers:
                trigger_seq.append(t)
            last_triggers = t
        return trigger_seq

    def _button_seq(self, game):
        last_buttons = None
        button_seq = []
        for frame in game.frames:
            b = frame.ports[0].leader.pre.buttons
            if (b.logical or b.physical) and b != last_buttons:
                button_seq.append(b)
            last_buttons = b
        return button_seq

    # def test_run_mypy_module(self):
    #     """Run mypy on all module sources"""
    #     mypy_call: list[str] = ["mypy"] + self.mypy_opts + ["-p", self.pkgname]
    #     browse_result: int = subprocess.call(mypy_call, env=os.environ, cwd=self.pypath)
    #     self.assertEqual(browse_result, 0, 'mypy on slippi')

    # def test_run_mypy_tests(self):
    #     """Run mypy on all tests in module under the tests directory"""
    #     for test_file in glob.iglob(f'{os.getcwd()}/tests/*.py'):
    #         mypy_call: list[str] = ["mypy"] + self.mypy_opts + [test_file]
    #         test_result: int = subprocess.call(mypy_call, env=os.environ, cwd=self.pypath)
    #         self.assertEqual(test_result, 0, f'mypy on test {test_file}')

    def test_slippi_old_version(self):
        game = self._game('v0.1')
        self.assertEqual(game.start.slippi_version, Start.SlippiVersion(0, 1, 0, 0))
        self.assertEqual(game.metadata.duration, None)
        self.assertEqual(game.metadata.players, (None, None, None, None))
        self.assertEqual(game.start.players[0].character, CSSCharacter.FOX)
        self.assertEqual(game.start.players[1].character, CSSCharacter.GANONDORF)

    def test_game(self):
        game = self._game('game')

        self.assertEqual(
            game.metadata,
            Metadata._parse(
                {
                    'startAt': '2018-06-22T07:52:59Z',
                    'lastFrame': 5085,
                    'playedOn': 'dolphin',
                    'players': {
                        '0': {
                            'characters': {
                                InGameCharacter.MARTH: 5209
                                }
                            },
                        '1': {
                            'characters': {
                                InGameCharacter.FOX: 5209
                                }
                            }
                        }
                    }
                )
            )
        self.assertEqual(
            game.metadata,
            Metadata(
                date=datetime.datetime(2018, 6, 22, 7, 52, 59, 0, datetime.timezone.utc),
                duration=5209,
                platform=Metadata.Platform.DOLPHIN,
                players=(Metadata.Player({InGameCharacter.MARTH: 5209}), Metadata.Player({InGameCharacter.FOX: 5209}), None, None)
                )
            )

        self.assertEqual(
            game.start,
            Start(
                is_teams=False,
                random_seed=3803194226,
                slippi=Start.SlippiVersion(1, 0, 0, 0),
                stage=Stage.YOSHIS_STORY,
                players=(
                    Start.Player(
                        character=CSSCharacter.MARTH,
                        type=Start.Player.Type.HUMAN,
                        stocks=4,
                        costume=3,
                        team=None,
                        ucf=Start.Player.UCF(False, False)
                        ),
                    Start.Player(
                        character=CSSCharacter.FOX,
                        type=Start.Player.Type.CPU,
                        stocks=4,
                        costume=0,
                        team=None,
                        ucf=Start.Player.UCF(False, False)
                        ), None, None
                    )
                )
            )

        self.assertEqual(game.end, End(End.Method.CONCLUSIVE))

        self.assertEqual(game.metadata.duration, len(game.frames))

    def test_game_skip_frames(self):
        game = Game(path('game'), skip_frames=True)

        self.assertEqual(
            game.metadata,
            Metadata._parse(
                {
                    'startAt': '2018-06-22T07:52:59Z',
                    'lastFrame': 5085,
                    'playedOn': 'dolphin',
                    'players': {
                        '0': {
                            'characters': {
                                InGameCharacter.MARTH: 5209
                                }
                            },
                        '1': {
                            'characters': {
                                InGameCharacter.FOX: 5209
                                }
                            }
                        }
                    }
                )
            )
        self.assertEqual(
            game.metadata,
            Metadata(
                date=datetime.datetime(2018, 6, 22, 7, 52, 59, 0, datetime.timezone.utc),
                duration=5209,
                platform=Metadata.Platform.DOLPHIN,
                players=(Metadata.Player({InGameCharacter.MARTH: 5209}), Metadata.Player({InGameCharacter.FOX: 5209}), None, None)
                )
            )

        self.assertEqual(
            game.start,
            Start(
                is_teams=False,
                players=(
                    Start.Player(
                        character=CSSCharacter.MARTH,
                        type=Start.Player.Type.HUMAN,
                        stocks=4,
                        costume=3,
                        team=None,
                        ucf=Start.Player.UCF(False, False)
                        ),
                    Start.Player(
                        character=CSSCharacter.FOX,
                        type=Start.Player.Type.CPU,
                        stocks=4,
                        costume=0,
                        team=None,
                        ucf=Start.Player.UCF(False, False)
                        ), None, None
                    ),
                random_seed=3803194226,
                slippi=Start.SlippiVersion(1, 0, 0, 0),
                stage=Stage.YOSHIS_STORY,
                )
            )

        self.assertEqual(game.end, End(End.Method.CONCLUSIVE))

        self.assertFalse(game.frames)

    def test_ics(self):
        game = self._game('ics')
        self.assertEqual(game.metadata.players[0].characters, {
            InGameCharacter.NANA: 344,
            InGameCharacter.POPO: 344
            })
        self.assertEqual(game.start.players[0].character, CSSCharacter.ICE_CLIMBERS)
        self.assertIsNotNone(game.frames[0].ports[0].follower)

    def test_ucf(self):
        self.assertEqual(self._game('shield_drop').start.players[0].ucf, Start.Player.UCF(dash_back=False, shield_drop=True))
        self.assertEqual(self._game('dash_back').start.players[0].ucf, Start.Player.UCF(dash_back=True, shield_drop=False))

    def test_buttons_lrzs(self):
        game = self._game('buttons_lrzs')
        self.assertEqual(
            self._button_seq(game), [
                Buttons(BLog.TRIGGER_ANALOG, BPhys.NONE),
                Buttons(BLog.TRIGGER_ANALOG | BLog.L, BPhys.L),
                Buttons(BLog.TRIGGER_ANALOG, BPhys.NONE),
                Buttons(BLog.TRIGGER_ANALOG | BLog.R, BPhys.R),
                Buttons(BLog.TRIGGER_ANALOG | BLog.A | BLog.Z, BPhys.Z),
                Buttons(BLog.START, BPhys.START)
                ]
            )

    def test_buttons_abxy(self):
        game = self._game('buttons_abxy')
        self.assertEqual(
            self._button_seq(game),
            [Buttons(BLog.A, BPhys.A),
             Buttons(BLog.B, BPhys.B),
             Buttons(BLog.X, BPhys.X),
             Buttons(BLog.Y, BPhys.Y)]
            )

    def test_dpad_udlr(self):
        game = self._game('dpad_udlr')
        self.assertEqual(
            self._button_seq(game), [
                Buttons(BLog.DPAD_UP, BPhys.DPAD_UP),
                Buttons(BLog.DPAD_DOWN, BPhys.DPAD_DOWN),
                Buttons(BLog.DPAD_LEFT, BPhys.DPAD_LEFT),
                Buttons(BLog.DPAD_RIGHT, BPhys.DPAD_RIGHT)
                ]
            )

    def test_cstick_udlr(self):
        game = self._game('cstick_udlr')
        self.assertEqual(
            self._button_seq(game), [
                Buttons(BLog.CSTICK_UP, BPhys.NONE),
                Buttons(BLog.CSTICK_DOWN, BPhys.NONE),
                Buttons(BLog.CSTICK_LEFT, BPhys.NONE),
                Buttons(BLog.CSTICK_RIGHT, BPhys.NONE)
                ]
            )

    def test_joystick_udlr(self):
        game = self._game('joystick_udlr')
        self.assertEqual(
            self._button_seq(game), [
                Buttons(BLog.JOYSTICK_UP, BPhys.NONE),
                Buttons(BLog.JOYSTICK_DOWN, BPhys.NONE),
                Buttons(BLog.JOYSTICK_LEFT, BPhys.NONE),
                Buttons(BLog.JOYSTICK_RIGHT, BPhys.NONE)
                ]
            )

    def test_nintendont(self):
        game = self._game('nintendont')
        self.assertEqual(game.metadata.platform, Metadata.Platform.NINTENDONT)

    def test_netplay_name(self):
        game = self._game('netplay')
        players = game.metadata.players
        self.assertEqual([players[0].connect_code, players[0].display_name], ['ABCD#123', 'abcdefghijk'])
        self.assertEqual([players[1].connect_code, players[1].display_name], ['XX#000', 'nobody'])

    def test_console_name(self):
        game = self._game('console_name')
        self.assertEqual(game.metadata.console_name, 'Station 1')

    def test_metadata_json(self):
        game = self._game('game')
        self.assertEqual(
            game.metadata_raw, {
                'lastFrame': 5085,
                'playedOn': 'dolphin',
                'players': {
                    '0': {
                        'characters': {
                            '18': 5209
                            }
                        },
                    '1': {
                        'characters': {
                            '1': 5209
                            }
                        }
                    },
                'startAt': '2018-06-22T07:52:59Z'
                }
            )

    def test_v2(self):
        game = self._game('v2.0')
        self.assertEqual(game.start.slippi_version, Start.SlippiVersion(2, 0, 1))

    def test_v3_14_0(self):
        game = self._game('v3.14.0')
        self.assertEqual(game.start.slippi_version, Start.SlippiVersion(3, 14, 0))
        self.assertEqual(game.start.match_id, 'mode.unranked-2022-12-27T01:04:44.19-0')
        self.assertEqual(game.start.game_number, 4)

    def test_unknown_event(self):
        with self.assertLogs(log, 'INFO') as log_context:
            game = self._game('unknown_event')
        self.assertEqual(log_context.output, ['INFO:root:ignoring unknown event type: 0xff'])

    def test_items(self):
        game = self._game('items')
        items = {}
        for f in game.frames:
            for i in f.items:
                if not i.spawn_id in items:
                    items[i.spawn_id] = i
        self.assertEqual(
            items, {
                0:
                    Frame.Item(
                        damage_taken=0,
                        facing_direction=Direction.RIGHT,
                        position=Position(-62.7096061706543, -1.4932749271392822),
                        spawn_id=0,
                        state=0,
                        timer=140.0,
                        type=Item.PEACH_TURNIP,
                        velocity=Velocity(0.0, 0.0),
                        missile_type=None,
                        turnip_type=None,
                        is_shot_launched=None,
                        charge_power=None,
                        owner=None,
                        ),
                1:
                    Frame.Item(
                        damage_taken=0,
                        facing_direction=Direction.LEFT,
                        position=Position(20.395559310913086, -1.4932749271392822),
                        spawn_id=1,
                        state=0,
                        timer=140.0,
                        type=Item.PEACH_TURNIP,
                        velocity=Velocity(0.0, 0.0),
                        missile_type=None,
                        turnip_type=None,
                        is_shot_launched=None,
                        charge_power=None,
                        owner=None,
                        ),
                2:
                    Frame.Item(
                        damage_taken=0,
                        facing_direction=Direction.RIGHT,
                        position=Position(-3.982539176940918, -1.4932749271392822),
                        spawn_id=2,
                        state=0,
                        timer=140.0,
                        type=Item.PEACH_TURNIP,
                        velocity=Velocity(0.0, 0.0),
                        missile_type=None,
                        turnip_type=None,
                        is_shot_launched=None,
                        charge_power=None,
                        owner=None,
                        )
                }
            )

    def test_throw_detection(self):
        throws = StatsComputer(self._game(R"fox_throws")).stats_compute()[1].stats.take_hits.to_polars()
        throws = throws.select(pl.col("character"), pl.col("opnt_character"), pl.col("frame_index"), pl.col("last_hit_by"))
        assert(throws.frame_equal(pl.read_parquet(R"test/data/fox_throws.parquet")))
        throws = StatsComputer(self._game(R"falcon_throws")).stats_compute()[1].stats.take_hits.to_polars()
        throws = throws.select(pl.col("character"), pl.col("opnt_character"), pl.col("frame_index"), pl.col("last_hit_by"))
        assert(throws.frame_equal(pl.read_parquet(R"test/data/falcon_throws.parquet")))


    # def test_wavedash_data(self):
    #     wavedashes = StatsComputer(self._game("wavedash"))
    #     wavedashes = wavedashes.wavedash_compute(player=wavedashes.players[0]).to_polars()
    #     assert (wavedashes.frame_equal(pl.read_parquet(Path(r'test\data\wavedash.parquet'))))

    # def test_dash_data(self):
    #     dashes = StatsComputer(self._game("dash"))
    #     dashes = dashes.dash_compute(player=dashes.players[0]).to_polars()
    #     assert (dashes.frame_equal(pl.read_parquet(Path(r'test\data\dash.parquet'))))


# class TestParse(unittest.TestCase):

#     def test_parse(self):
#         metadata = None

#         def set_metadata(x):
#             nonlocal metadata
#             metadata = x

#         parse(path('game'), {Metadata: set_metadata})
#         self.assertEqual(metadata.duration, 5209)

if __name__ == '__main__':
    unittest.main()
