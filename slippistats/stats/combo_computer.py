from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path

from ..enums.state import ActionState
from ..event import Frame, Position
from ..game import Game
from .common import (
    calc_damage_taken,
    did_lose_stock,
    get_death_direction,
    is_cmd_grabbed,
    is_damaged,
    is_dodging,
    is_downed,
    is_dying,
    is_grabbed,
    is_in_hitlag,
    is_in_hitstun,
    is_ledge_action,
    is_maybe_juggled,
    is_offstage,
    is_shield_broken,
    is_shielding,
    is_special_fall,
    is_teching,
    is_upb_lag,
    is_wavedashing,
)
from .computer import ComputerBase, Player

COMBO_LENIENCY = 45
PRE_COMBO_BUFFER_FRAMES = 60
POST_COMBO_BUFFER_FRAMES = 90

# class ComboEvent(Enum):
#     """Enumeration for combo states"""
#     # strictly speaking this is unnecessary and unused at the moment.
#     # AFAIK this is meant to be used in conjunction with real time
#     # parsing, which this parser *can* do. Maybe a future TODO to get it to work properly.
#     COMBO_START = "COMBO_START"
#     COMBO_EXTEND = "COMBO_EXTEND"
#     COMBO_END = "COMBO_END"


@dataclass
class MoveLanded:
    """Contains all data for a single move connecting"""

    frame_index: int = 0
    move_id: int = 0
    hit_count: int = 0
    damage: float = 0
    opponent_position: Position | None = None
    # TODO still in hitstun bool or frames since hitstun ended


@dataclass
class ComboData:
    """Contains a single complete combo, including movelist
    Helper functions for filtering combos include:
    minimum_damage(num)
    minimum_length(num)
    total_damage()"""

    moves: list[MoveLanded] = field(default_factory=list)
    did_kill: bool = False
    death_direction: str | None = None
    player_stocks: int = 4
    opponent_stocks: int = 4
    did_end_game: bool = False
    start_percent: float = 0.0
    current_percent: float = 0.0
    end_percent: float = 0.0
    start_frame: int = 0
    end_frame: int = 0

    # I could probably add a "combo_filters()" abstraction with keyword arguments,
    # but that feels like it shoehorns too much by limiting possible filter options, akin to clippi
    # Until i have a more robust list of filters, i won't make that further abstraction
    def total_damage(self) -> float:
        """Calculates total damage of the combo"""
        return self.end_percent - self.start_percent

    def minimum_length(self, num: int | float) -> bool:
        """Recieves number, returns True if combo's move count is greater than number"""
        return len(self.moves) >= num

    def minimum_damage(self, num: int | float) -> bool:
        """Recieves number, returns True if combo's total damage was over number"""
        return self.total_damage() >= num


@dataclass
class ComboState:
    """Contains info used during combo calculation to build the final combo"""

    combo: ComboData | None = field(default_factory=ComboData)
    move: MoveLanded | None = field(default_factory=MoveLanded)
    reset_counter: int = 0
    last_hit_animation: int | None = None


class ComboComputer(ComputerBase):
    """Base class for parsing combo events, call .prime_replay(path) to set up the instance,
    and .combo_compute(connect_code) to populate the computer's .combos list."""

    combo_state: ComboState
    queue: list[dict]
    replay_path: Path

    def __init__(self, replay: PathLike | Game | str | None = None):
        self.rules = None
        self.combos = []
        self.players = []
        self.combo_state = ComboState()
        self.metadata = None
        self.queue = []
        if replay is not None:
            self.prime_replay(replay)

    def reset_data(self):
        self.combos = []
        self.combo_state = ComboState()
        self.queue = []

    def to_json(self, combo: ComboData):
        self.queue.append({})
        self.queue[-1]["path"] = self.replay_path
        self.queue[-1]["gameStartAt"] = self.replay.metadata.date.strftime("%m/%d/%y %I:%M %p")
        self.queue[-1]["startFrame"] = combo.start_frame - PRE_COMBO_BUFFER_FRAMES
        self.queue[-1]["endFrame"] = combo.end_frame + POST_COMBO_BUFFER_FRAMES
        return self.queue

    def combo_compute(
        self,
        connect_code: str | None = None,
        player: Player | None = None,
        opponent: Player | None = None,
        hitstun_check=True,
        hitlag_check=True,
        tech_check=True,
        downed_check=True,
        offstage_check=True,
        dodge_check=True,
        shield_check=True,
        shield_break_check=True,
        ledge_check=True,
    ) -> list[ComboData]:
        """Generates list of combos from the replay information parsed using prime_replay(), returns nothing.
        Output is also accessible as a list through ComboComputer.combos"""

        if connect_code is None and player is None:
            raise ValueError("Combo compute functions require either a connect_code or player and opponent argument")

        if connect_code is not None:
            player = self.get_player(connect_code)
            opponent = self.get_opponent(connect_code)

        for i, player_frame in enumerate(player.frames):
            player_state: ActionState | int = player_frame.post.state
            prev_player_frame: Frame.Port.Data = player.frames[i - 1]

            opponent_frame: Frame.Port.Data = opponent.frames[i]
            opnt_action_state = opponent_frame.post.state
            prev_opponent_frame: Frame.Port.Data = opponent.frames[i - 1]

            opnt_is_damaged = is_damaged(opnt_action_state)
            # Bitflags are used because the hitstun frame count is used for a bunch of other things as well
            opnt_is_in_hitstun = is_in_hitstun(opponent_frame.post.flags) and hitstun_check
            opnt_is_grabbed = is_grabbed(opnt_action_state)
            opnt_is_cmd_grabbed = is_cmd_grabbed(opnt_action_state)
            opnt_damage_taken = calc_damage_taken(opponent_frame.post, prev_opponent_frame.post)

            # "Keep track of whether actionState changes after a hit. Used to compute move count
            # When purely using action state there was a bug where if you did two of the same
            # move really fast (such as ganon's jab), it would count as one move. Added
            # the actionStateCounter at this point which counts the number of frames since
            # an animation started. Should be more robust, for old files it should always be
            # null and null < null = false" - official parser
            action_changed_since_hit = not (player_state == self.combo_state.last_hit_animation)
            action_frame_counter = player_frame.post.state_age
            prev_action_counter = prev_player_frame.post.state_age
            action_state_reset = action_frame_counter < prev_action_counter
            if action_changed_since_hit or action_state_reset:
                self.combo_state.last_hit_animation = None

            # I throw in the extra hitstun check to make it extra robust in case we're forgetting some animation.
            # Don't include hitlag check unless you want shield hits to start combo events.
            # There might be false positives on self damage like fully charged roy neutral b
            if opnt_is_damaged or opnt_is_grabbed or opnt_is_cmd_grabbed or opnt_is_in_hitstun:
                # if the opponent has been hit and there's no "active" combo, start a new combo
                if self.combo_state.combo is None:
                    self.combo_state.combo = ComboData(
                        player_stocks=player_frame.post.stocks_remaining,
                        opponent_stocks=opponent_frame.post.stocks_remaining,
                        start_frame=i - 123,
                        start_percent=prev_opponent_frame.post.percent,
                        current_percent=opponent_frame.post.percent,
                        end_percent=opponent_frame.post.percent,
                    )

                    player.combos.append(self.combo_state.combo)

                # if the opponent has been hit and we're sure it's not the same move, record the move's data
                # BUG slippi-js has issues with this too, but magnifying glass damage will count as a move
                if opnt_damage_taken:
                    if self.combo_state.last_hit_animation is None:
                        self.combo_state.move = MoveLanded(
                            frame_index=i - 123,
                            move_id=player_frame.post.most_recent_hit,
                            opponent_position=opponent_frame.post.position,
                        )

                        self.combo_state.combo.moves.append(self.combo_state.move)

                    if self.combo_state.move:
                        self.combo_state.move.hit_count += 1
                        self.combo_state.move.damage += opnt_damage_taken

                    self.combo_state.last_hit_animation = prev_player_frame.post.state

            # If a combo hasn't started and no damage was taken this frame, just skip to the next frame
            if self.combo_state.combo is None:
                continue

            # Otherwise check all other relevant statistics and determine whether to continue or terminate the combo
            opnt_is_in_hitlag = is_in_hitlag(opponent_frame.post.flags) and hitlag_check
            opnt_is_teching = is_teching(opnt_action_state) and tech_check
            opnt_is_downed = is_downed(opnt_action_state) and downed_check
            opnt_is_dying = is_dying(opnt_action_state)
            opnt_is_offstage = is_offstage(opponent_frame.post.position, self.replay.start.stage) and offstage_check
            opnt_is_dodging = (
                is_dodging(opnt_action_state)
                and dodge_check
                and not is_wavedashing(opnt_action_state, i, opponent.frames)
            )
            opnt_is_shielding = is_shielding(opnt_action_state) and shield_check
            opnt_is_shield_broken = is_shield_broken(opnt_action_state) and shield_break_check
            opnt_did_lose_stock = did_lose_stock(opponent_frame.post, prev_opponent_frame.post)
            opnt_is_ledge_action = is_ledge_action(opnt_action_state) and ledge_check
            opnt_is_maybe_juggled = is_maybe_juggled(
                opponent_frame.post.position,
                getattr(opponent_frame.post, "is_airborne"),
                self.replay.start.stage,
            )  # TODO and juggled check
            opnt_is_special_fall = is_special_fall(opnt_action_state)
            opnt_is_upb_lag = is_upb_lag(opnt_action_state, prev_opponent_frame.post.state)
            # opnt_is_recovery_lag = is_recovery_lag(opponent_frame.character, opnt_action_state)

            if not opnt_did_lose_stock:
                self.combo_state.combo.current_percent = opponent_frame.post.percent

            player_did_lose_stock = did_lose_stock(player_frame.post, prev_player_frame.post)

            # reset the combo timeout timer to 0 if the opponent meets the following conditions
            # list expanded from official parser to allow for higher combo variety
            #  and captures more of what we would count as "combos"
            # noteably, this list will allow mid-combo shield pressure and edgeguards to be counted as part of a combo
            if (
                opnt_is_damaged
                or opnt_is_grabbed  # Action state range
                or opnt_is_cmd_grabbed  # Action state range
                or opnt_is_in_hitlag  # Action state range
                or opnt_is_in_hitstun  # Bitflags (will always fail with old replays)
                or opnt_is_shielding  # Bitflags (will always fail with old replays)
                or opnt_is_offstage  # Action state range
                or opnt_is_dodging  # X and Y coordinate check
                or opnt_is_dying  # Action state range
                or opnt_is_downed  # Action state range
                or opnt_is_teching  # Action state range
                or opnt_is_ledge_action  # Action state range
                or opnt_is_shield_broken  # Action state range
                or opnt_is_maybe_juggled  # Action state range
                or opnt_is_special_fall  # Y coordinate check
                or opnt_is_upb_lag  # Action state range
            ):  # Action state range
                self.combo_state.reset_counter = 0
            else:
                self.combo_state.reset_counter += 1

            should_terminate = False

            # All combo termination checks below
            if opnt_is_dying:
                self.combo_state.combo.death_direction = get_death_direction(opnt_action_state)

            if opnt_did_lose_stock:
                self.combo_state.combo.did_kill = True
                if opponent_frame.post.stocks_remaining == 0:
                    self.combo_state.combo.did_end_game = True

                should_terminate = True

            if self.combo_state.reset_counter > COMBO_LENIENCY or player_did_lose_stock:
                should_terminate = True

            # If the combo should end, finalize the values, reset the temp storage
            if should_terminate:
                self.combo_state.combo.end_frame = i - 123
                self.combo_state.combo.end_percent = prev_opponent_frame.post.percent
                self.combo_state.combo = None
                self.combo_state.move = None

        return player.combos
