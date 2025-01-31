from enum import IntFlag
from functools import lru_cache
from .character import InGameCharacter
from ..util import IntEnum, try_enum

# Use reference: https://docs.google.com/spreadsheets/d/1JX2w-r2fuvWuNgGb6D3Cs4wHQKLFegZe2jhbBuIhCG8/edit#gid=13

# To check if an action state is zero-indexed:https://github.com/altf4/libmelee/blob/master/melee/actiondata.csv
# I might add some form of check in here, but for now i just handle it manually.


class Direction(IntEnum):
    """Direction values used by the game engine.

    LEFT = -1

    DOWN = 0
        Down = 0 is useful for stats, but technically 0 is used as the direction during the Warp Star item animation
    RIGHT = 1
    """

    LEFT = -1
    DOWN = 0
    """Technically used for Warp Star item animation, but useful as "DOWN" for stats purposes."""
    RIGHT = 1


class LCancel(IntEnum):
    """L-Cancel Status, active for 1 frame upon landing during an aerial attack

    NOT_APPLICABLE = 0
        Value at all other times
    SUCCESS = 1

    FAILURE = 2
    """

    NOT_APPLICABLE = 0
    """Any frame other than when l cancels are checked upon landing"""
    SUCCESS = 1
    """Active for 1 frame upon landing during an aerial attack"""
    FAILURE = 2
    """Active for 1 frame upon landing during an aerial attack"""


class Hurtbox(IntEnum):
    """
    * VULNERABLE = 0
    * INVULNERABLE = 1
    * INTANGIBLE = 2
    """

    VULNERABLE = 0
    INVULNERABLE = 1
    """Attacks collide with hurtbox, incurring hitlag but dealing no damage"""
    INTANGIBLE = 2
    """Attacks pass through hurtbox, incurring no hitlag and dealing no damage"""


class Field1(IntFlag):
    """State Bitfield 1

    Known Bits:
        * Bit 2 - ABSORBER_BUBBLE
        * Bit 4 - REFLECT_NO_OWNERSHIP_CHANGE
        * Bit 5 - REFLECT_BUBBLE
    """

    BIT_1 = 1
    ABSORBER_BUBBLE = 2
    """Active when any absorber hitbox is active (ness down b)"""
    BIT_3 = 4
    REFLECT_NO_OWNERSHIP_CHANGE = 8
    """Active when REFLECT_BUBBLE is active, but the reflected projectile does not change ownership (e.g. Mewtwo side b)
    """
    REFLECT_BUBBLE = 16
    """Active when any projectile reflect bubble is active"""
    BIT_6 = 32
    BIT_7 = 64
    BIT_8 = 128


class Field2(IntFlag):
    """State Bitfield 2

    Known Bits:
        * Bit 3 - SUBACTION_INVULN
        * Bit 4 - FASTFALL
        * Bit 5 - DEFENDER_HITLAG
        * Bit 6 - HITLAG

    """

    BIT_1 = 1
    BIT_2 = 2
    SUBACTION_INVULN = 4
    """Active when the character recieves intangibility or invulnerability due to an subaction that is removed upon"""
    FASTFALL = 8
    """Active when the player is fastfalling"""
    DEFENDER_HITLAG = 16
    """Active when HITLAG is active, if the character is being hit. Can be thought of as CAN_SDI"""
    HITLAG = 32
    """Active when character is in hitlag"""
    BIT_7 = 64
    BIT_8 = 128


class Field3(IntFlag):
    """State Bitfield 3

    Known Bits:
        * Bit 3 - HOLDING_CHARACTER
        * BIT 8 - SHIELDING
    """

    BIT_1 = 1
    BIT_2 = 2
    HOLDING_CHARACTER = 4
    """Active when holding a character after a successful grab"""
    BIT_4 = 8
    BIT_5 = 16
    BIT_6 = 32
    BIT_7 = 64
    SHIELDING = 128
    """Active when character is shielding"""


class Field4(IntFlag):
    """State Bitfield 4

    Known Bits:
        * Bit 2 - HITSTUN
        * BIT 3 - HITBOX_TOUCHING_SHIELD
        * BIT 6 - POWERSHIELD_BUBBLE

    """

    BIT_1 = 1
    HITSTUN = 2
    """Active when character is in hitstun"""
    HITBOX_TOUCHING_SHIELD = 4
    """Dubious meaning, likely related to subframe events"""
    BIT_4 = 8
    BIT_5 = 16
    POWERSHIELD_BUBBLE = 32
    """Active when character's Powershield bubble is active (physical or projectile)"""
    BIT_7 = 64
    BIT_8 = 128


class Field5(IntFlag):
    """State Bitfield 5

    Known Bits:
        * Bit 2 - IS_CLOAKING_DEVICE
        * Bit 4 - IS_FOLLOWER
        * Bit 5 - IS_INACTIVE
        * Bit 7 - IS_DEAD
        * Bit 8 - IS_OFFSCREEN

    """

    BIT_1 = 1
    IS_CLOAKING_DEVICE = 2
    """Active if player is invisible due to item/special mode toggle"""
    BIT_3 = 4
    IS_FOLLOWER = 8
    """Active if character is follower-type (e.g. Nana)"""
    IS_INACTIVE = 16
    """
    Character is not the current active character (Shiek when Zelda is active, teammates with 0 stocks).

    Should never be active in a replay, as this bit is what determines whether a frame is recorded for the character
    or not. Corresponds to action state Sleep (different from fura_sleep and damage_sleep)
    """
    BIT_6 = 32
    IS_DEAD = 64
    """Active when character is dead"""
    IS_OFFSCREEN = 128
    """Active when character is in the magnifying glass"""


# ---------------------------------------------------------------------------- #
#                                 Action States                                #
# ---------------------------------------------------------------------------- #


class ActionRange(IntEnum):
    """Action State Ranges - used to simplify checks for clusters of action states"""

    DAMAGE_START = 75
    DAMAGE_END = 91
    CAPTURE_START = 223
    CAPTURE_END = 232
    GUARD_START = 178
    GUARD_END = 182
    GUARD_BREAK_START = 205
    GUARD_BREAK_END = 211
    GROUNDED_CONTROL_START = 14
    GROUNDED_CONTROL_END = 24
    LEDGE_ACTION_START = 252
    LEDGE_ACTION_END = 263
    SQUAT_START = 39
    SQUAT_END = 41
    DOWN_START = 183
    DOWN_END = 198
    TECH_START = 199
    TECH_END = 204
    DODGE_START = 233
    DODGE_END = 236
    DYING_START = 0
    DYING_END = 10
    CONTROLLED_JUMP_START = 24
    CONTROLLED_JUMP_END = 34
    GROUND_ATTACK_START = 44
    GROUND_ATTACK_END = 64
    AERIAL_ATTACK_START = 65
    AERIAL_ATTACK_END = 74
    FALL_SPECIAL_START = 35
    FALL_SPECIAL_END = 37
    AERIAL_LAND_LAG_START = 70
    AERIAL_LAND_LAG_END = 74
    ACTIONABLE_AIR_START = 25
    ACTIONABLE_AIR_END = 34
    THROWN_START = 239
    THROWN_END = 243

    # Command Grabs
    COMMAND_GRAB_RANGE1_START = 266
    COMMAND_GRAB_RANGE1_END = 304

    COMMAND_GRAB_RANGE2_START = 327
    COMMAND_GRAB_RANGE2_END = 338


class ActionState(IntEnum):
    """Individual Action State IDs. See ActionRange for state ranges."""

    DEAD_DOWN = 0
    """Bottom blast zone death"""
    DEAD_LEFT = 1
    """Left blast zone death"""
    DEAD_RIGHT = 2
    """Right blast zone death"""
    DEAD_UP = 3
    """Up blast zone death used in 1P "Team Kirby", etc."""
    DEAD_UP_STAR = 4
    """Standard star KO"""
    DEAD_UP_STAR_ICE = 5
    """Star KO while encased in ice"""
    DEAD_UP_FALL = 6
    """64-esque front fall, likely unused per OG Modders"""
    DEAD_UP_FALL_HIT_CAMERA = 7
    DEAD_UP_FALL_HIT_CAMERA_FLAT = 8
    DEAD_UP_FALL_ICE = 9
    DEAD_UP_FALL_HIT_CAMERA_ICE = 10

    SLEEP = 11
    """"Nothing" state - used as sheik/zelda state when the other is active"""

    REBIRTH = 12
    """Entering on halo"""
    REBIRTH_WAIT = 13
    """Waiting on halo"""

    WAIT = 14
    """Default standing state"""

    # ------------------------------ Generic Movement ----------------------------- #

    WALK_SLOW = 15
    WALK_MIDDLE = 16
    WALK_FAST = 17
    TURN = 18
    TURN_RUN = 19
    """Slow sliding turnaround when in full run"""
    DASH = 20
    RUN = 21
    RUN_DIRECT = 22
    RUN_BRAKE = 23
    KNEE_BEND = 24
    """Jumpsquat"""
    JUMP_F = 25
    """First jump, forward"""
    JUMP_B = 26
    """First jump, backwards"""
    JUMP_AERIAL_F = 27
    """Aerial jump forward"""
    JUMP_AERIAL_B = 28
    """Aerial jump backward"""
    FALL = 29
    """Default fall"""
    FALL_F = 30
    """Fall forward DI"""
    FALL_B = 31
    """Fall backward DI"""
    FALL_AERIAL = 32
    """Fall after second jump"""
    FALL_AERIAL_F = 33
    """Fall after second jump, forward DI"""
    FALL_AERIAL_B = 34
    """Fall after second jump, backward DI"""
    FALL_SPECIAL = 35
    """Non-actionable fall used after Up B, air dodge, and some B moves"""
    FALL_SPECIAL_F = 36
    """Non-actionable fall, forward DI"""
    FALL_SPECIAL_B = 37
    """Non-actionable fall, backward DI"""
    DAMAGE_FALL = 38
    """Tumble"""
    SQUAT = 39
    """Stand -> Crouch"""
    SQUAT_WAIT = 40
    """Full crouch"""
    SQUAT_RV = 41
    """Crouch -> Stand"""
    LAND = 42
    """Universal no-action landing lag, fully interruptable"""
    LAND_FALL_SPECIAL = 43
    """Landing from FALL_SPECIAL[_F/B]"""

    # ------------------------------- Attacks ------------------------------ #

    ATTACK_11 = 44
    """Jab 1"""
    ATTACK_12 = 45
    """Jab 2"""
    ATTACK_13 = 46
    """Jab 3"""
    ATTACK_100_START = 47
    """Rapid jab start"""
    ATTACK_100_LOOP = 48
    """Rapid jab loop"""
    ATTACK_100_END = 49
    """Rapid jab end"""
    ATTACK_DASH = 50
    """Dash attack"""
    ATTACK_S_3_HI = 51
    """Up-angled Ftilt"""
    ATTACK_S_3_HI_S = 52
    """Slight up-angled F-tilt"""
    ATTACK_S_3_S = 53
    """No angle Ftilt"""
    ATTACK_S_3_LW_S = 54
    """Slight down-angled Ftilt"""
    ATTACK_S_3_LW = 55
    """Down-angled Ftilt"""
    ATTACK_HI_3 = 56
    """Utilt"""
    ATTACK_LW_3 = 57
    """Dtilt"""
    ATTACK_S_4_HI = 58
    """Up-angled Fsmash"""
    ATTACK_S_4_HI_S = 59
    """Slight up-angled Fsmash"""
    ATTACK_S_4_S = 60
    """No angle Fsmash"""
    ATTACK_S_4_LW_S = 61
    """Slight down-angled Fsmash"""
    ATTACK_S_4_LW = 62
    """Down-angled Fsmash"""
    ATTACK_HI_4 = 63
    """Usmash"""
    ATTACK_LW_4 = 64
    """Dsmash"""
    ATTACK_AIR_N = 65
    """Nair"""
    ATTACK_AIR_F = 66
    """Fair"""
    ATTACK_AIR_B = 67
    """Bair"""
    ATTACK_AIR_HI = 68
    """Uair"""
    ATTACK_AIR_LW = 69
    """Dair"""
    LANDING_AIR_N = 70
    """Nair landing animation"""
    LANDING_AIR_F = 71
    """Fair landing animation"""
    LANDING_AIR_B = 72
    """Bair landing animation"""
    LANDING_AIR_HI = 73
    """Uair landing animation"""
    LANDING_AIR_LW = 74
    """Dair landing animation"""

    # -------------------- Generic Damage -------------------- #

    DAMAGE_HI_1 = 75
    DAMAGE_HI_2 = 76
    DAMAGE_HI_3 = 77
    DAMAGE_N_1 = 78
    DAMAGE_N_2 = 79
    DAMAGE_N_3 = 80
    DAMAGE_LW_1 = 81
    DAMAGE_LW_2 = 82
    DAMAGE_LW_3 = 83
    DAMAGE_AIR_1 = 84
    DAMAGE_AIR_2 = 85
    DAMAGE_AIR_3 = 86
    DAMAGE_FLY_HI = 87
    DAMAGE_FLY_N = 88
    DAMAGE_FLY_LW = 89
    DAMAGE_FLY_TOP = 90
    DAMAGE_FLY_ROLL = 91

    # -------------------------- Generic Item ------------------------- #

    LIGHT_GET = 92
    """Picking up most items"""
    HEAVY_GET = 93
    """Picking up heavy items (Barrel)"""
    LIGHT_THROW_F = 94
    """Start of item throw"""
    LIGHT_THROW_B = 95
    LIGHT_THROW_HI = 96
    LIGHT_THROW_LW = 97
    LIGHT_THROW_DASH = 98
    LIGHT_THROW_DROP = 99
    LIGHT_THROW_AIR_F = 100
    LIGHT_THROW_AIR_B = 101
    LIGHT_THROW_AIR_HI = 102
    LIGHT_THROW_AIR_LW = 103
    HEAVY_THROW_F = 104
    HEAVY_THROW_B = 105
    HEAVY_THROW_HI = 106
    HEAVY_THROW_LW = 107
    LIGHT_THROW_F_4 = 108

    # Smash throw start

    LIGHT_THROW_B_4 = 109
    LIGHT_THROW_HI_4 = 110
    LIGHT_THROW_LW_4 = 111
    LIGHT_THROW_AIR_F_4 = 112
    LIGHT_THROW_AIR_B_4 = 113
    LIGHT_THROW_AIR_HI_4 = 114
    LIGHT_THROW_AIR_LW_4 = 115
    HEAVY_THROW_F_4 = 116
    HEAVY_THROW_B_4 = 117
    HEAVY_THROW_HI_4 = 118
    HEAVY_THROW_LW_4 = 119

    # End of item throw

    SWORD_SWING_1 = 120

    # --------------------- Item-Specific -------------------- #

    SWORD_SWING_3 = 121
    SWORD_SWING_4 = 122
    SWORD_SWING_DASH = 123
    BAT_SWING_1 = 124
    BAT_SWING_3 = 125
    BAT_SWING_4 = 126
    BAT_SWING_DASH = 127
    PARASOL_SWING_1 = 128
    PARASOL_SWING_3 = 129
    PARASOL_SWING_4 = 130
    PARASOL_SWING_DASH = 131
    HARISEN_SWING_1 = 132
    HARISEN_SWING_3 = 133
    HARISEN_SWING_4 = 134
    HARISEN_SWING_DASH = 135
    STAR_ROD_SWING_1 = 136
    STAR_ROD_SWING_3 = 137
    STAR_ROD_SWING_4 = 138
    STAR_ROD_SWING_DASH = 139
    LIP_STICK_SWING_1 = 140
    LIP_STICK_SWING_3 = 141
    LIP_STICK_SWING_4 = 142
    LIP_STICK_SWING_DASH = 143
    ITEM_PARASOL_OPEN = 144
    ITEM_PARASOL_FALL = 145
    ITEM_PARASOL_FALL_SPECIAL = 146
    ITEM_PARASOL_DAMAGE_FALL = 147
    L_GUN_SHOOT = 148
    L_GUN_SHOOT_AIR = 149
    L_GUN_SHOOT_EMPTY = 150
    L_GUN_SHOOT_AIR_EMPTY = 151
    FIRE_FLOWER_SHOOT = 152
    FIRE_FLOWER_SHOOT_AIR = 153
    ITEM_SCREW = 154
    ITEM_SCREW_AIR = 155
    DAMAGE_SCREW = 156
    DAMAGE_SCREW_AIR = 157
    ITEM_SCOPE_START = 158
    ITEM_SCOPE_RAPID = 159
    ITEM_SCOPE_FIRE = 160
    ITEM_SCOPE_END = 161
    ITEM_SCOPE_AIR_START = 162
    ITEM_SCOPE_AIR_RAPID = 163
    ITEM_SCOPE_AIR_FIRE = 164
    ITEM_SCOPE_AIR_END = 165
    ITEM_SCOPE_START_EMPTY = 166
    ITEM_SCOPE_RAPID_EMPTY = 167
    ITEM_SCOPE_FIRE_EMPTY = 168
    ITEM_SCOPE_END_EMPTY = 169
    ITEM_SCOPE_AIR_START_EMPTY = 170
    ITEM_SCOPE_AIR_RAPID_EMPTY = 171
    ITEM_SCOPE_AIR_FIRE_EMPTY = 172
    ITEM_SCOPE_AIR_END_EMPTY = 173

    LIFT_WAIT = 174
    LIFT_WALK_1 = 175
    LIFT_WALK_2 = 176
    LIFT_TURN = 177

    # ------------------------------- Shield ------------------------------ #

    GUARD_ON = 178
    """Raising shield"""
    GUARD = 179
    """Holding shield"""
    GUARD_OFF = 180
    """Releasing shield"""
    GUARD_SET_OFF = 181
    """Shield stun"""
    GUARD_REFLECT = 182
    """Powershield"""

    # -------------------------------- Tech States ------------------------------- #

    DOWN_BOUND_U = 183
    """Missed tech bounce, facing upwards"""
    DOWN_WAIT_U = 184
    """Downed, facing up"""
    DOWN_DAMAGE_U = 185
    """Jab reset while laying facing up"""
    DOWN_STAND_U = 186
    """Neutral getup, facing up"""
    DOWN_ATTACK_U = 187
    """Getup attack, facing up"""
    DOWN_FOWARD_U = 188
    """Missed tech roll forward"""
    DOWN_BACK_U = 189
    """Missed tech roll backward"""
    DOWN_SPOT_U = 190
    """Does not appear to be used"""
    DOWN_BOUND_D = 191
    """Missed tech bounce, facing down"""
    DOWN_WAIT_D = 192
    """Downed, facing down"""
    DOWN_DAMAGE_D = 193
    """Hit while laying on ground, facing down"""
    DOWN_STAND_D = 194
    """Neutral getup, facing down"""
    DOWN_ATTACK_D = 195
    """Getup attack, facing down"""
    DOWN_FOWARD_D = 196
    """Missed tech roll forward"""
    DOWN_BACK_D = 197
    """Missed tech roll backward"""
    DOWN_SPOT_D = 198
    """Does not appear to be used"""
    PASSIVE = 199
    """Neutral tech"""
    PASSIVE_STAND_F = 200
    """Forward tech"""
    PASSIVE_STAND_B = 201
    """Backward tech"""
    PASSIVE_WALL = 202
    """Wall tech"""
    PASSIVE_WALL_JUMP = 203
    """Walljump and Walljump tech"""
    PASSIVE_CEIL = 204
    """Ceiling tech"""

    # ---------------------------- Shield Break --------------------------- #

    SHIELD_BREAK_FLY = 205
    """Initial bounce when shield is broken"""
    SHIELD_BREAK_FALL = 206
    """Fall during shield break"""
    SHIELD_BREAK_DOWN_U = 207
    SHIELD_BREAK_DOWN_D = 208
    SHIELD_BREAK_STAND_U = 209
    SHIELD_BREAK_STAND_D = 210
    FURA_FURA = 211
    """Shield break totter"""

    # ----------------------------------- Grab ----------------------------------- #

    CATCH = 212
    """Grab"""
    CATCH_PULL = 213
    """Successful grab, pulling opponent in"""
    CATCH_DASH = 214
    """Dash grab"""
    CATCH_DASH_PULL = 215
    """Successful dash grab, pulling opponent in"""
    CATCH_WAIT = 216
    """Grab hold"""
    CATCH_ATTACK = 217
    """Pummel"""
    CATCH_CUT = 218
    """Grab release"""
    THROW_F = 219
    """Fthrow"""
    THROW_B = 220
    """Bthrow"""
    THROW_HI = 221
    """Uthrow"""
    THROW_LW = 222
    """Dthrow"""
    CAPTURE_PULLED_HI = 223
    CAPTURE_WAIT_HI = 224
    CAPTURE_DAMAGE_HI = 225
    CAPTURE_PULLED_LW = 226
    """Being grabbed and pulled"""
    CAPTURE_WAIT_LW = 227
    """Grabbed and held"""
    CAPTURE_DAMAGE_LW = 228
    """Pummeled"""
    CAPTURE_CUT = 229
    """Grab release"""
    CAPTURE_JUMP = 230
    """Jumping mash out"""
    CAPTURE_NECK = 231
    """Does not appear to be used"""
    CAPTURE_FOOT = 232
    """Does not appear to be used"""

    # -------------------------------- Dodge/Roll -------------------------------- #
    ESCAPE_F = 233
    """Shield roll forward"""
    ESCAPE_B = 234
    """Shield roll backward"""
    ESCAPE = 235
    """Spot dodge"""
    ESCAPE_AIR = 236
    """Airdodge"""

    REBOUND_STOP = 237
    REBOUND = 238

    # ---------------------------------- Thrown ---------------------------------- #
    THROWN_F = 239
    """Receiving Fthrow"""
    THROWN_B = 240
    """Receiving Bthrow"""
    THROWN_HI = 241
    """Receiving Uthrow"""
    THROWN_LW = 242
    """Receiving Dthrow"""
    THROWN_LW_WOMEN = 243

    # ----------------------------- Wall/Edge/Ceiling ---------------------------- #

    PASS = 244
    """Drop through platform"""
    OTTOTTO = 245
    """Ledge teeter"""
    OTTOTTO_WAIT = 246
    """Teeter loop?"""
    FLY_REFLECT_WALL = 247
    """Missed wall tech"""
    FLY_REFLECT_CEIL = 248
    """Missed ceiling tech"""
    STOP_WALL = 249
    """Wall bonk"""
    STOP_CEIL = 250
    """Ceiling bonk"""
    MISS_FOOT = 251
    """Backward shield slideoff"""

    # ----------------------------------- Ledge ---------------------------------- #

    CLIFF_CATCH = 252
    """Ledge grab"""
    CLIFF_WAIT = 253
    """Ledge hang"""
    CLIFF_CLIMB_SLOW = 254
    """Regular getup >100%"""
    CLIFF_CLIMB_QUICK = 255
    """Regular getup <100%"""
    CLIFF_ATTACK_SLOW = 256
    """Ledge attack >100%"""
    CLIFF_ATTACK_QUICK = 257
    """Ledge attack <100%"""
    CLIFF_ESCAPE_SLOW = 258
    """Ledge roll >100%"""
    CLIFF_ESCAPE_QUICK = 259
    """Ledge roll <100%"""
    CLIFF_JUMP_SLOW_1 = 260
    """Ledge jump >100%"""
    CLIFF_JUMP_SLOW_2 = 261
    """Ledge jump >100%"""
    CLIFF_JUMP_QUICK_1 = 262
    """Ledge jump <100%"""
    CLIFF_JUMP_QUICK_2 = 263
    """Ledge jump <100%"""

    # ----------------------------------- Taunt ---------------------------------- #

    APPEAL_R = 264
    """Taunt facing right"""
    APPEAL_L = 265
    """Taunt facing left"""

    # ------------------------------- Command Grabs and Misc ------------------------------ #

    SHOULDERED_WAIT = 266
    """DK cargo carry"""
    SHOULDERED_WALK_SLOW = 267
    SHOULDERED_WALK_MIDDLE = 268
    SHOULDERED_WALK_FAST = 269
    SHOULDERED_TURN = 270
    THROWN_F_F = 271
    """DK cargo throw"""
    THROWN_F_B = 272
    THROWN_F_HI = 273
    THROWN_F_LW = 274

    CAPTURE_CAPTAIN = 275
    """Falcon up B grab"""
    CAPTURE_YOSHI = 276  # TODO Yoshi neutral B grab victim?
    YOSHI_EGG = 277  # TODO Yoshi neutral B grab victim in egg?
    CAPTURE_KOOPA = 278
    """Koopa claw"""
    CAPTURE_DAMAGE_KOOPA = 279
    CAPTURE_WAIT_KOOPA = 280
    THROWN_KOOPA_F = 281
    THROWN_KOOPA_B = 282
    CAPTURE_KOOPA_AIR = 283
    CAPTURE_DAMAGE_KOOPA_AIR = 284
    CAPTURE_WAIT_KOOPA_AIR = 285
    THROWN_KOOPA_AIR_F = 286
    THROWN_KOOPA_AIR_B = 287
    CAPTURE_KIRBY = 288
    """Kirby succ victim"""
    CAPTURE_WAIT_KIRBY = 289
    THROWN_KIRBY_STAR = 290
    """Kirby spit victim"""
    THROWN_COPY_STAR = 291
    """Kirby swallow victim"""
    THROWN_KIRBY = 292
    BARREL_WAIT = 293  # I think this is used for the barrel on DK jungle 64?

    BURY = 294
    """Stuck in ground by DK side b or similar"""
    BURY_WAIT = 295
    BURY_JUMP = 296

    DAMAGE_SONG = 297
    """Put to sleep by Jiggs sing or similar"""
    DAMAGE_SONG_WAIT = 298
    DAMAGE_SONG_RV = 299

    DAMAGE_BIND = 300
    """Hit by Mewtwo disable"""
    CAPTURE_MEWTWO = 301
    """Does not appear to be used"""
    CAPTURE_MEWTWO_AIR = 302
    """Does not appear to be used"""
    THROWN_MEWTWO = 303
    """Hit by Mewtwo confusion"""
    THROWN_MEWTWO_AIR = 304
    """Hit by Mewtwo's confusion in the air"""

    # ---------------------------- More Item-Specific ---------------------------- #

    WARP_STAR_JUMP = 305
    WARP_STAR_FALL = 306
    HAMMER_WAIT = 307
    HAMMER_WALK = 308
    HAMMER_TURN = 309
    HAMMER_KNEE_BEND = 310
    HAMMER_FALL = 311
    HAMMER_JUMP = 312
    HAMMER_LANDING = 313
    # super/poison mushroom states:
    KINOKO_GIANT_START = 314
    KINOKO_GIANT_START_AIR = 315
    KINOKO_GIANT_END = 316
    KINOKO_GIANT_END_AIR = 317
    KINOKO_SMALL_START = 318
    KINOKO_SMALL_START_AIR = 319
    KINOKO_SMALL_END = 320
    KINOKO_SMALL_END_AIR = 321

    ENTRY = 322
    """Beginning of the match warp in"""
    ENTRY_START = 323
    """Beginning of the match warp in"""
    ENTRY_END = 324
    """Beginning of the match warp in"""

    DAMAGE_ICE = 325
    DAMAGE_ICE_JUMP = 326
    CAPTURE_MASTER_HAND = 327
    CAPTURE_DAMAGE_MASTER_HAND = 328
    CAPTURE_WAIT_MASTER_HAND = 329
    THROWN_MASTER_HAND = 330
    CAPTURE_KIRBY_YOSHI = 331
    KIRBY_YOSHI_EGG = 332
    CAPTURE_REDEAD = 333
    CAPTURE_LIKE_LIKE = 334

    DOWN_REFLECT = 335
    """
    A very rare action state where the character transitions from a DownBoundU or DownBoundD (missed tech) state
    into a wall bounce. This state is not techable and neither is the probable next floor hit.
    Most commonly encountered on Pokémon Stadium
    """

    CAPTURE_CRAZY_HAND = 336
    CAPTURE_DAMAGE_CRAZY_HAND = 337
    CAPTURE_WAIT_CRAZY_HAND = 338
    THROWN_CRAZY_HAND = 339
    BARREL_CANNON_WAIT = 340


# ---------------------------------------------------------------------------- #
#                           Character Specific State                           #
# ---------------------------------------------------------------------------- #


@lru_cache
def get_character_state(state: int, character: InGameCharacter | int | None = None) -> ActionState:
    """Accepts state and optionally a character, returns a character-specific action state if possible, otherwise
    returns a general action state.

    Raises:
        ValueError if state is less than 0
        KeyError if supplied character does not match any valid in-game character values"""
    if state < 0:
        raise ValueError()
    if state < 341:
        return ActionState(state)
    return try_enum(CHARACTER_STATE_DICT[character], state)


class Bowser(IntEnum):
    FIRE_BREATH_GROUND_STARTUP = 341
    FIRE_BREATH_GROUND_LOOP = 342
    FIRE_BREATH_GROUND_END = 343
    FIRE_BREATH_AIR_STARTUP = 344
    FIRE_BREATH_AIR_LOOP = 345
    FIRE_BREATH_AIR_END = 346
    KOOPA_KLAW_GROUND = 347
    KOOPA_KLAW_GROUND_GRAB = 348
    KOOPA_KLAW_GROUND_PUMMEL = 349
    KOOPA_KLAW_GROUND_WAIT = 350
    KOOPA_KLAW_GROUND_THROW_F = 351
    KOOPA_KLAW_GROUND_THROW_B = 352
    KOOPA_KLAW_AIR = 353
    KOOPA_KLAW_AIR_GRAB = 354
    KOOPA_KLAW_AIR_PUMMEL = 355
    KOOPA_KLAW_AIR_WAIT = 356
    KOOPA_KLAW_AIR_THROW_F = 357
    KOOPA_KLAW_AIR_THROW_B = 358
    WHIRLING_FORTRESS_GROUND = 359
    WHIRLING_FORTRESS_AIR = 360
    BOMB_GROUND_BEGIN = 361
    BOMB_AIR = 362
    BOMB_LAND = 363


class CaptainFalcon(IntEnum):
    FALCON_PUNCH_GROUND = 347
    FALCON_PUNCH_AIR = 348
    RAPTOR_BOOST_GROUND = 349
    RAPTOR_BOOST_GROUND_HIT = 350
    RAPTOR_BOOST_AIR = 351
    RAPTOR_BOOST_AIR_HIT = 352
    FALCON_DIVE_GROUND = 353
    FALCON_DIVE_AIR = 354
    FALCON_DIVE_CATCH = 355
    FALCON_DIVE_ENDING = 356
    FALCON_KICK_GROUND = 357
    FALCON_KICK_GROUND_ENDING_ON_GROUND = 358
    FALCON_KICK_AIR = 359
    FALCON_KICK_AIR_ENDING_ON_GROUND = 360
    FALCON_KICK_AIR_ENDING_IN_AIR = 361
    FALCON_KICK_GROUND_ENDING_IN_AIR = 362
    FALCON_KICK_HIT_WALL = 363


class DonkeyKong(IntEnum):
    KONG_KARRY_WAIT = 351
    KONG_KARRY_WALK_SLOW = 352
    KONG_KARRY_WALK_MIDDLE = 353
    KONG_KARRY_WALK_FAST = 354
    KONG_KARRY_TURN = 355
    KONG_KARRY_JUMP_SQUAT = 356
    KONG_KARRY_FALL = 357
    KONG_KARRY_JUMP = 358
    KONG_KARRY_LANDING = 359
    KONG_KARRY_GROUND_THROW_FORWARD = 361
    KONG_KARRY_GROUND_THROW_BACKWARD = 362
    KONG_KARRY_GROUND_THROW_UP = 363
    KONG_KARRY_GROUND_THROW_DOWN = 364
    KONG_KARRY_AIR_THROW_FORWARD = 365
    KONG_KARRY_AIR_THROW_BACKWARD = 366
    KONG_KARRY_AIR_THROW_UP = 367
    KONG_KARRY_AIR_THROW_DOWN = 368
    GIANT_PUNCH_GROUND_CHARGE_STARTUP = 369
    GIANT_PUNCH_GROUND_CHARGE_LOOP = 370
    GIANT_PUNCH_GROUND_CHARGE_STOP = 371
    GIANT_PUNCH_GROUND_EARLY_PUNCH = 372
    GIANT_PUNCH_GROUND_FULL_CHARGE_PUNCH = 373
    GIANT_PUNCH_AIR_CHARGE_STARTUP = 374
    GIANT_PUNCH_AIR_CHARGE_LOOP = 375
    GIANT_PUNCH_AIR_CHARGE_STOP = 376
    GIANT_PUNCH_AIR_EARLY_PUNCH = 377
    GIANT_PUNCH_AIR_FULL_CHARGE_PUNCH = 378
    HEADBUTT_GROUND = 379
    HEADBUTT_AIR = 380
    SPINNING_KONG_GROUND = 381
    SPINNING_KONG_AIR = 382
    HAND_SLAP_STARTUP = 383
    HAND_SLAP_LOOP = 384
    HAND_SLAP_END = 385


class DrMario(IntEnum):
    TAUNT_R = 341
    MEGAVITAMIN_GROUND = 343
    MEGAVITAMIN_AIR = 344
    SUPER_SHEET_GROUND = 345
    SUPER_SHEET_AIR = 346
    SUPER_JUMP_PUNCH_GROUND = 347
    SUPER_JUMP_PUNCH_AIR = 348
    TORNADO_GROUND = 349
    TORNADO_AIR = 350


class Falco(IntEnum):
    BLASTER_GROUND_STARTUP = 341
    BLASTER_GROUND_LOOP = 342
    BLASTER_GROUND_END = 343
    BLASTER_AIR_STARTUP = 344
    BLASTER_AIR_LOOP = 345
    BLASTER_AIR_END = 346
    PHANTASM_GROUND_STARTUP = 347
    PHANTASM_GROUND = 348
    PHANTASM_GROUND_END = 349
    PHANTASM_STARTUP_AIR = 350
    PHANTASM_AIR = 351
    PHANTASM_AIR_END = 352
    FIRE_BIRD_GROUND_STARTUP = 353
    FIRE_BIRD_AIR_STARTUP = 354
    FIRE_BIRD_GROUND = 355
    FIRE_BIRD_AIR = 356
    FIRE_BIRD_GROUND_END = 357
    FIRE_BIRD_AIR_END = 358
    FIRE_BIRD_BOUNCE_END = 359
    REFLECTOR_GROUND_STARTUP = 360
    REFLECTOR_GROUND_LOOP = 361
    REFLECTOR_GROUND_REFLECT = 362
    REFLECTOR_GROUND_END = 363
    REFLECTOR_GROUND_CHANGE_DIRECTION = 364
    REFLECTOR_AIR_STARTUP = 365
    REFLECTOR_AIR_LOOP = 366
    REFLECTOR_AIR_REFLECT = 367
    REFLECTOR_AIR_END = 368
    REFLECTOR_AIR_CHANGE_DIRECTION = 369
    SMASH_TAUNT_RIGHT_STARTUP = 370
    SMASH_TAUNT_LEFT_STARTUP = 371
    SMASH_TAUNT_RIGHT_RISE = 372
    SMASH_TAUNT_LEFT_RISE = 373
    SMASH_TAUNT_RIGHT_FINISH = 374
    SMASH_TAUNT_LEFT_FINISH = 375


class Fox(IntEnum):
    BLASTER_GROUND_STARTUP = 341
    BLASTER_GROUND_LOOP = 342
    BLASTER_GROUND_END = 343
    BLASTER_AIR_STARTUP = 344
    BLASTER_AIR_LOOP = 345
    BLASTER_AIR_END = 346
    ILLUSION_GROUND_STARTUP = 347
    ILLUSION_GROUND = 348
    ILLUSION_GROUND_END = 349
    ILLUSION_STARTUP_AIR = 350
    ILLUSION_AIR = 351
    ILLUSION_AIR_END = 352
    FIRE_FOX_GROUND_STARTUP = 353
    FIRE_FOX_AIR_STARTUP = 354
    FIRE_FOX_GROUND = 355
    FIRE_FOX_AIR = 356
    FIRE_FOX_GROUND_END = 357
    FIRE_FOX_AIR_END = 358
    FIRE_FOX_BOUNCE_END = 359
    REFLECTOR_GROUND_STARTUP = 360
    REFLECTOR_GROUND_LOOP = 361
    REFLECTOR_GROUND_REFLECT = 362
    REFLECTOR_GROUND_END = 363
    REFLECTOR_GROUND_CHANGE_DIRECTION = 364
    REFLECTOR_AIR_STARTUP = 365
    REFLECTOR_AIR_LOOP = 366
    REFLECTOR_AIR_REFLECT = 367
    REFLECTOR_AIR_END = 368
    REFLECTOR_AIR_CHANGE_DIRECTION = 369
    SMASH_TAUNT_RIGHT_STARTUP = 370
    SMASH_TAUNT_LEFT_STARTUP = 371
    SMASH_TAUNT_RIGHT_RISE = 372
    SMASH_TAUNT_LEFT_RISE = 373
    SMASH_TAUNT_RIGHT_FINISH = 374
    SMASH_TAUNT_LEFT_FINISH = 375


class GameAndWatch(IntEnum):
    JAB = 341
    RAPID_JABS_START = 342
    RAPID_JABS_LOOP = 343
    RAPID_JABS_END = 344
    DOWN_TILT = 345
    SIDE_SMASH = 346
    NAIR = 347
    BAIR = 348
    UAIR = 349
    NAIR_LANDING = 350
    BAIR_LANDING = 351
    UAIR_LANDING = 352
    CHEF_GROUND = 353
    CHEF_AIR = 354
    JUDGMENT_1_GROUND = 355
    JUDGMENT_2_GROUND = 356
    JUDGMENT_3_GROUND = 357
    JUDGMENT_4_GROUND = 358
    JUDGMENT_5_GROUND = 359
    JUDGMENT_6_GROUND = 360
    JUDGMENT_7_GROUND = 361
    JUDGMENT_8_GROUND = 362
    JUDGMENT_9_GROUND = 363
    JUDGMENT_1_AIR = 364
    JUDGMENT_2_AIR = 365
    JUDGMENT_3_AIR = 366
    JUDGMENT_4_AIR = 367
    JUDGMENT_5_AIR = 368
    JUDGMENT_6_AIR = 369
    JUDGMENT_7_AIR = 370
    JUDGMENT_8_AIR = 371
    JUDGMENT_9_AIR = 372
    FIRE_GROUND = 373
    FIRE_AIR = 374
    OIL_PANIC_GROUND = 375
    OIL_PANIC_GROUND_ABSORB = 376
    OIL_PANIC_GROUND_SPILL = 377
    OIL_PANIC_AIR = 378
    OIL_PANIC_AIR_ABSORB = 379
    OIL_PANIC_AIR_SPILL = 380


class Ganondorf(IntEnum):
    WARLOCK_PUNCH_GROUND = 347
    WARLOCK_PUNCH_AIR = 348
    GERUDO_DRAGON_GROUND = 349
    GERUDO_DRAGON_GROUND_HIT = 350
    GERUDO_DRAGON_AIR = 351
    GERUDO_DRAGON_AIR_HIT = 352
    DARK_DIVE_GROUND = 353
    DARK_DIVE_AIR = 354
    DARK_DIVE_CATCH = 355
    DARK_DIVE_ENDING = 356
    WIZARDS_FOOT_GROUND = 357
    WIZARDS_FOOT_GROUND_ENDING_ON_GROUND = 358
    WIZARDS_FOOT_AIR = 359
    WIZARDS_FOOT_AIR_ENDING_ON_GROUND = 360
    WIZARDS_FOOT_AIR_ENDING_IN_AIR = 361
    WIZARDS_FOOT_GROUND_ENDING_IN_AIR = 362
    WIZARDS_FOOT_HIT_WALL = 363


class Jigglypuff(IntEnum):
    JUMP_2 = 341
    JUMP_3 = 342
    JUMP_4 = 343
    JUMP_5 = 344
    JUMP_6 = 345
    ROLLOUT_GROUND_START_CHARGE_RIGHT = 346
    ROLLOUT_GROUND_START_CHARGE_LEFT = 347
    ROLLOUT_GROUND_CHARGE_LOOP = 348
    ROLLOUT_GROUND_FULLY_CHARGED = 349
    ROLLOUT_GROUND_CHARGE_RELEASE = 350
    ROLLOUT_GROUND_START_TURN = 351
    ROLLOUT_GROUND_END_RIGHT = 352
    ROLLOUT_GROUND_END_LEFT = 353
    ROLLOUT_AIR_START_CHARGE_RIGHT = 354
    ROLLOUT_AIR_START_CHARGE_LEFT = 355
    ROLLOUT_AIR_CHARGE_LOOP = 356
    ROLLOUT_AIR_FULLY_CHARGED = 357
    ROLLOUT_AIR_CHARGE_RELEASE = 358
    ROLLOUT_AIR_END_RIGHT = 360
    ROLLOUT_AIR_END_LEFT = 361
    ROLLOUT_HIT = 362
    POUND_GROUND = 363
    POUND_AIR = 364
    SING_GROUND_LEFT = 365
    SING_AIR_LEFT = 366
    SING_GROUND_RIGHT = 367
    SING_AIR_RIGHT = 368
    REST_GROUND_LEFT = 369
    REST_AIR_LEFT = 370
    REST_GROUND_RIGHT = 371
    REST_AIR_RIGHT = 372


class Kirby(IntEnum):
    JUMP_2 = 341
    JUMP_3 = 342
    JUMP_4 = 343
    JUMP_5 = 344
    JUMP_6 = 345
    JUMP_2_WITH_HAT = 346
    JUMP_3_WITH_HAT = 347
    JUMP_4_WITH_HAT = 348
    JUMP_5_WITH_HAT = 349
    JUMP_6_WITH_HAT = 350
    DASH_ATTACK_GROUND = 351
    DASH_ATTACK_AIR = 352
    SWALLOW_GROUND_STARTUP = 353
    SWALLOW_GROUND_LOOP = 354
    SWALLOW_GROUND_END = 355
    SWALLOW_GROUND_CAPTURE = 356
    SWALLOW_GROUND_CAPTURED = 358
    SWALLOW_GROUND_CAPTURE_WAIT = 359
    SWALLOW_CAPTURE_WALK_SLOW = 360
    SWALLOW_CAPTURE_WALK_MIDDLE = 361
    SWALLOW_CAPTURE_WALK_FAST = 362
    SWALLOW_GROUND_CAPTURE_TURN = 363
    SWALLOW_CAPTURE_JUMP_SQUAT = 364
    SWALLOW_CAPTURE_JUMP = 365
    SWALLOW_CAPTURE_LANDING = 366
    SWALLOW_GROUND_DIGEST = 367
    SWALLOW_GROUND_SPIT = 369
    SWALLOW_AIR_STARTUP = 371
    SWALLOW_AIR_LOOP = 372
    SWALLOW_AIR_END = 373
    SWALLOW_AIR_CAPTURE = 374
    SWALLOW_AIR_CAPTURED = 376
    SWALLOW_AIR_CAPTURE_WAIT = 377
    SWALLOW_AIR_DIGEST = 378
    SWALLOW_AIR_SPIT = 380
    SWALLOW_AIR_CAPTURE_TURN = 382
    HAMMER_GROUND = 383
    HAMMER_AIR = 384
    FINAL_CUTTER_GROUND_STARTUP = 385
    FINAL_CUTTER_GROUND_END = 388
    FINAL_CUTTER_AIR_STARTUP = 389
    FINAL_CUTTER_AIR_APEX = 390
    FINAL_CUTTER_SWORD_DESCENT = 391
    FINAL_CUTTER_AIR_END = 392
    STONE_GROUND_STARTUP = 393
    STONE_GROUND = 394
    STONE_GROUND_END = 395
    STONE_AIR_STARTUP = 396
    STONE_AIR = 397
    STONE_AIR_END = 398
    MARIO_FIREBALL_GROUND = 399
    MARIO_FIREBALL_AIR = 400
    LINK_BOW_GROUND_CHARGE = 401
    LINK_BOW_GROUND_FULLY_CHARGED = 402
    LINK_BOW_GROUND_FIRE = 403
    LINK_BOW_AIR_CHARGE = 404
    LINK_BOW_AIR_FULLY_CHARGED = 405
    LINK_BOW_AIR_FIRE = 406
    SAMUS_CHARGE_SHOT_GROUND_START = 407
    SAMUS_CHARGE_SHOT_GROUND_LOOP = 408
    SAMUS_CHARGE_SHOT_GROUND_END = 409
    SAMUS_CHARGE_SHOT_GROUND_FIRE = 410
    SAMUS_CHARGE_SHOT_AIR_START = 411
    SAMUS_CHARGE_SHOT_AIR_FIRE = 412
    YOSHI_EGG_LAY_GROUND = 413
    YOSHI_EGG_LAY_GROUND_CAPTURE_START = 414
    YOSHI_EGG_LAY_GROUND_CAPTURE = 416
    YOSHI_EGG_LAY_AIR = 418
    YOSHI_EGG_LAY_AIR_CAPTURE_START = 419
    YOSHI_EGG_LAY_AIR_CAPTURE = 421
    FOX_BLASTER_GROUND_STARTUP = 423
    FOX_BLASTER_GROUND_LOOP = 424
    FOX_BLASTER_GROUND_END = 425
    FOX_BLASTER_AIR_STARTUP = 426
    FOX_BLASTER_AIR_LOOP = 427
    FOX_BLASTER_AIR_END = 428
    PIKACHU_THUNDER_JOLT_GROUND = 429
    PIKACHU_THUNDER_JOLT_AIR = 430
    LUIGI_FIREBALL_GROUND = 431
    LUIGI_FIREBALL_AIR = 432
    FALCON_FALCON_PUNCH_GROUND = 433
    FALCON_FALCON_PUNCH_AIR = 434
    NESS_PK_FLASH_GROUND_STARTUP = 435
    NESS_PK_FLASH_GROUND_CHARGE = 436
    NESS_PK_FLASH_GROUND_EXPLODE = 437
    NESS_PK_FLASH_GROUND_END = 438
    NESS_PK_FLASH_AIR_STARTUP = 439
    NESS_PK_FLASH_AIR_CHARGE = 440
    NESS_PK_FLASH_AIR_EXPLODE = 441
    NESS_PK_FLASH_AIR_END = 442
    BOWSER_FIRE_BREATH_GROUND_START = 443
    BOWSER_FIRE_BREATH_GROUND_LOOP = 444
    BOWSER_FIRE_BREATH_GROUND_END = 445
    BOWSER_FIRE_BREATH_AIR_START = 446
    BOWSER_FIRE_BREATH_AIR_LOOP = 447
    BOWSER_FIRE_BREATH_AIR_END = 448
    PEACH_TOAD_GROUND = 449
    PEACH_TOAD_GROUND_ATTACK = 450
    PEACH_TOAD_AIR = 451
    PEACH_TOAD_AIR_ATTACK = 452
    ICE_CLIMBERS_ICE_SHOT_GROUND = 453
    ICE_CLIMBERS_ICE_SHOT_AIR = 454
    DK_GIANT_PUNCH_GROUND_CHARGE_STARTUP = 455
    DK_GIANT_PUNCH_GROUND_CHARGE_LOOP = 456
    DK_GIANT_PUNCH_GROUND_CHARGE_STOP = 457
    DK_GIANT_PUNCH_GROUND_EARLY_PUNCH = 458
    DK_GIANT_PUNCH_GROUND_FULL_CHARGE_PUNCH = 459
    DK_GIANT_PUNCH_AIR_CHARGE_STARTUP = 460
    DK_GIANT_PUNCH_AIR_CHARGE_LOOP = 461
    DK_GIANT_PUNCH_AIR_CHARGE_STOP = 462
    DK_GIANT_PUNCH_AIR_EARLY_PUNCH = 463
    DK_GIANT_PUNCH_AIR_FULL_CHARGE_PUNCH = 464
    ZELDA_NAYRUS_LOVE_GROUND = 465
    ZELDA_NAYRUS_LOVE_AIR = 466
    SHEIK_NEEDLE_STORM_GROUND_START_CHARGE = 467
    SHEIK_NEEDLE_STORM_GROUND_CHARGE_LOOP = 468
    SHEIK_NEEDLE_STORM_GROUND_END_CHARGE = 469
    SHEIK_NEEDLE_STORM_GROUND_FIRE = 470
    SHEIK_NEEDLE_STORM_AIR_START_CHARGE = 471
    SHEIK_NEEDLE_STORM_AIR_CHARGE_LOOP = 472
    SHEIK_NEEDLE_STORM_AIR_END_CHARGE = 473
    SHEIK_NEEDLE_STORM_AIR_FIRE = 474
    JIGGLYPUFF_ROLLOUT_GROUND_START_CHARGE_RIGHT = 475
    JIGGLYPUFF_ROLLOUT_GROUND_START_CHARGE_LEFT = 476
    JIGGLYPUFF_ROLLOUT_GROUND_CHARGE_LOOP = 477
    JIGGLYPUFF_ROLLOUT_GROUND_FULLY_CHARGED = 478
    JIGGLYPUFF_ROLLOUT_GROUND_CHARGE_RELEASE = 479
    JIGGLYPUFF_ROLLOUT_GROUND_START_TURN = 480
    JIGGLYPUFF_ROLLOUT_GROUND_END_RIGHT = 481
    JIGGLYPUFF_ROLLOUT_GROUND_END_LEFT = 482
    JIGGLYPUFF_ROLLOUT_AIR_START_CHARGE_RIGHT = 483
    JIGGLYPUFF_ROLLOUT_AIR_START_CHARGE_LEFT = 484
    JIGGLYPUFF_ROLLOUT_AIR_CHARGE_LOOP = 485
    JIGGLYPUFF_ROLLOUT_AIR_FULLY_CHARGED = 486
    JIGGLYPUFF_ROLLOUT_AIR_CHARGE_RELEASE = 487
    JIGGLYPUFF_ROLLOUT_AIR_END_RIGHT = 489
    JIGGLYPUFF_ROLLOUT_AIR_END_LEFT = 490
    JIGGLYPUFF_ROLLOUT_HIT = 491
    MARTH_SHIELD_BREAKER_GROUND_START_CHARGE = 492
    MARTH_SHIELD_BREAKER_GROUND_CHARGE_LOOP = 493
    MARTH_SHIELD_BREAKER_GROUND_EARLY_RELEASE = 494
    MARTH_SHIELD_BREAKER_GROUND_FULLY_CHARGED = 495
    MARTH_SHIELD_BREAKER_AIR_START_CHARGE = 496
    MARTH_SHIELD_BREAKER_AIR_CHARGE_LOOP = 497
    MARTH_SHIELD_BREAKER_AIR_EARLY_RELEASE = 498
    MARTH_SHIELD_BREAKER_AIR_FULLY_CHARGED = 499
    MEWTWO_SHADOW_BALL_GROUND_START_CHARGE = 500
    MEWTWO_SHADOW_BALL_GROUND_CHARGE_LOOP = 501
    MEWTWO_SHADOW_BALL_GROUND_FULLY_CHARGED = 502
    MEWTWO_SHADOW_BALL_GROUND_END_CHARGE = 503
    MEWTWO_SHADOW_BALL_GROUND_FIRE = 504
    MEWTWO_SHADOW_BALL_AIR_START_CHARGE = 505
    MEWTWO_SHADOW_BALL_AIR_CHARGE_LOOP = 506
    MEWTWO_SHADOW_BALL_AIR_FULLY_CHARGED = 507
    MEWTWO_SHADOW_BALL_AIR_END_CHARGE = 508
    MEWTWO_SHADOW_BALL_AIR_FIRE = 509
    GAMEAND_WATCH_OIL_PANIC_GROUND = 510
    GAMEAND_WATCH_OIL_PANIC_AIR = 511
    DOC_MEGAVITAMIN_GROUND = 512
    DOC_MEGAVITAMIN_AIR = 513
    YOUNG_LINK_FIRE_BOW_GROUND_CHARGE = 514
    YOUNG_LINK_FIRE_BOW_GROUND_FULLY_CHARGED = 515
    YOUNG_LINK_FIRE_BOW_GROUND_FIRE = 516
    YOUNG_LINK_FIRE_BOW_AIR_CHARGE = 517
    YOUNG_LINK_FIRE_BOW_AIR_FULLY_CHARGED = 518
    YOUNG_LINK_FIRE_BOW_AIR_FIRE = 519
    FALCO_BLASTER_GROUND_STARTUP = 520
    FALCO_BLASTER_GROUND_LOOP = 521
    FALCO_BLASTER_GROUND_END = 522
    FALCO_BLASTER_AIR_STARTUP = 523
    FALCO_BLASTER_AIR_LOOP = 524
    FALCO_BLASTER_AIR_END = 525
    PICHU_THUNDER_JOLT_GROUND = 526
    PICHU_THUNDER_JOLT_AIR = 527
    GANON_WARLOCK_PUNCH_GROUND = 528
    GANON_WARLOCK_PUNCH_AIR = 529
    ROY_FLARE_BLADE_GROUND_START_CHARGE = 530
    ROY_FLARE_BLADE_GROUND_CHARGE_LOOP = 531
    ROY_FLARE_BLADE_GROUND_EARLY_RELEASE = 532
    ROY_FLARE_BLADE_GROUND_FULLY_CHARGED = 533
    ROY_FLARE_BLADE_AIR_START_CHARGE = 534
    ROY_FLARE_BLADE_AIR_CHARGE_LOOP = 535
    ROY_FLARE_BLADE_AIR_EARLY_RELEASE = 536
    ROY_FLARE_BLADE_AIR_FULLY_CHARGED = 537


class Link(IntEnum):
    SIDE_SMASH_2 = 341
    BOW_GROUND_CHARGE = 344
    BOW_GROUND_FULLY_CHARGED = 345
    BOW_GROUND_FIRE = 346
    BOW_AIR_CHARGE = 347
    BOW_AIR_FULLY_CHARGED = 348
    BOW_AIR_FIRE = 349
    BOOMERANG_GROUND_THROW = 350
    BOOMERANG_GROUND_CATCH = 351
    BOOMERANG_GROUND_THROW_EMPTY = 352
    BOOMERANG_AIR_THROW = 353
    BOOMERANG_AIR_CATCH = 354
    BOOMERANG_AIR_THROW_EMPTY = 355
    SPIN_ATTACK_GROUND = 356
    SPIN_ATTACK_AIR = 357
    BOMB_GROUND = 358
    BOMB_AIR = 359
    ZAIR = 360
    ZAIR_CATCH = 361


class Luigi(IntEnum):
    FIREBALL_GROUND = 341
    FIREBALL_AIR = 342
    GREEN_MISSILE_GROUND_STARTUP = 343
    GREEN_MISSILE_GROUND_CHARGE = 344
    GREEN_MISSILE_GROUND_LANDING = 346
    GREEN_MISSILE_GROUND_TAKEOFF = 347
    GREEN_MISSILE_GROUND_TAKEOFF_MISFIRE = 348
    GREEN_MISSILE_AIR_STARTUP = 349
    GREEN_MISSILE_AIR_CHARGE = 350
    GREEN_MISSILE_AIR = 351
    GREEN_MISSILE_AIR_END = 352
    GREEN_MISSILE_AIR_TAKEOFF = 353
    GREEN_MISSILE_AIR_TAKEOFF_MISFIRE = 354
    SUPER_JUMP_PUNCH_GROUND = 355
    SUPER_JUMP_PUNCH_AIR = 356
    CYCLONE_GROUND = 357
    CYCLONE_AIR = 358


class Mario(IntEnum):
    FIREBALL_GROUND = 343
    FIREBALL_AIR = 344
    CAPE_GROUND = 345
    CAPE_AIR = 346
    SUPER_JUMP_PUNCH_GROUND = 347
    SUPER_JUMP_PUNCH_AIR = 348
    TORNADO_GROUND = 349
    TORNADO_AIR = 350


class Marth(IntEnum):
    SHIELD_BREAKER_GROUND_START_CHARGE = 341
    SHIELD_BREAKER_GROUND_CHARGE_LOOP = 342
    SHIELD_BREAKER_GROUND_EARLY_RELEASE = 343
    SHIELD_BREAKER_GROUND_FULLY_CHARGED = 344
    SHIELD_BREAKER_AIR_START_CHARGE = 345
    SHIELD_BREAKER_AIR_CHARGE_LOOP = 346
    SHIELD_BREAKER_AIR_EARLY_RELEASE = 347
    SHIELD_BREAKER_AIR_FULLY_CHARGED = 348
    DANCING_BLADE_1_GROUND = 349
    DANCING_BLADE_2_UP_GROUND = 350
    DANCING_BLADE_2_SIDE_GROUND = 351
    DANCING_BLADE_3_UP_GROUND = 352
    DANCING_BLADE_3_SIDE_GROUND = 353
    DANCING_BLADE_3_DOWN_GROUND = 354
    DANCING_BLADE_4_UP_GROUND = 355
    DANCING_BLADE_4_SIDE_GROUND = 356
    DANCING_BLADE_4_DOWN_GROUND = 357
    DANCING_BLADE_1_AIR = 358
    DANCING_BLADE_2_UP_AIR = 359
    DANCING_BLADE_2_SIDE_AIR = 360
    DANCING_BLADE_3_UP_AIR = 361
    DANCING_BLADE_3_SIDE_AIR = 362
    DANCING_BLADE_3_DOWN_AIR = 363
    DANCING_BLADE_4_UP_AIR = 364
    DANCING_BLADE_4_SIDE_AIR = 365
    DANCING_BLADE_4_DOWN_AIR = 366
    DOLPHIN_SLASH_GROUND = 367
    DOLPHIN_SLASH_AIR = 368
    COUNTER_GROUND = 369
    COUNTER_GROUND_HIT = 370
    COUNTER_AIR = 371
    COUNTER_AIR_HIT = 372


class Mewtwo(IntEnum):
    SHADOW_BALL_GROUND_START_CHARGE = 341
    SHADOW_BALL_GROUND_CHARGE_LOOP = 342
    SHADOW_BALL_GROUND_FULLY_CHARGED = 343
    SHADOW_BALL_GROUND_END_CHARGE = 344
    SHADOW_BALL_GROUND_FIRE = 345
    SHADOW_BALL_AIR_START_CHARGE = 346
    SHADOW_BALL_AIR_CHARGE_LOOP = 347
    SHADOW_BALL_AIR_FULLY_CHARGED = 348
    SHADOW_BALL_AIR_END_CHARGE = 349
    SHADOW_BALL_AIR_FIRE = 350
    CONFUSION_GROUND = 351
    CONFUSION_AIR = 352
    TELEPORT_GROUND_STARTUP = 353
    TELEPORT_GROUND_DISAPPEAR = 354
    TELEPORT_GROUND_REAPPEAR = 355
    TELEPORT_AIR_STARTUP = 356
    TELEPORT_AIR_DISAPPEAR = 357
    TELEPORT_AIR_REAPPEAR = 358
    DISABLE_GROUND = 359
    DISABLE_AIR = 360


class Nana(IntEnum):
    ICE_SHOT_GROUND = 341
    ICE_SHOT_AIR = 342
    BLIZZARD_GROUND = 357
    BLIZZARD_AIR = 358
    SQUALL_HAMMER_GROUND_TOGETHER = 359
    SQUALL_HAMMER_AIR_TOGETHER = 360
    BELAY_CATAPULT_STARTUP = 361
    BELAY_GROUND_CATAPULT_END = 362
    BELAY_CATAPULTING = 365


class Ness(IntEnum):
    SIDE_SMASH = 341
    UP_SMASH = 342
    UP_SMASH_CHARGE = 343
    UP_SMASH_CHARGED = 344
    DOWN_SMASH = 345
    DOWN_SMASH_CHARGE = 346
    DOWN_SMASH_CHARGED = 347
    PK_FLASH_GROUND_STARTUP = 348
    PK_FLASH_GROUND_CHARGE = 349
    PK_FLASH_GROUND_EXPLODE = 350
    PK_FLASH_GROUND_END = 351
    PK_FLASH_AIR_STARTUP = 352
    PK_FLASH_AIR_CHARGE = 353
    PK_FLASH_AIR_EXPLODE = 354
    PK_FLASH_AIR_END = 355
    PK_FIRE_GROUND = 356
    PK_FIRE_AIR = 357
    PK_THUNDER_GROUND_STARTUP = 358
    PK_THUNDER_GROUND = 359
    PK_THUNDER_GROUND_END = 360
    PK_THUNDER_GROUND_HIT = 361
    PK_THUNDER_AIR_STARTUP = 362
    PK_THUNDER_AIR = 363
    PK_THUNDER_AIR_END = 364
    PK_THUNDER_AIR_HIT = 365
    PK_THUNDER_AIR_HIT_WALL = 366
    PSI_MAGNET_GROUND_STARTUP = 367
    PSI_MAGNET_GROUND_LOOP = 368
    PSI_MAGNET_GROUND_ABSORB = 369
    PSI_MAGNET_GROUND_END = 370
    PSI_MAGNET_AIR_STARTUP = 372
    PSI_MAGNET_AIR_LOOP = 373
    PSI_MAGNET_AIR_ABSORB = 374
    PSI_MAGNET_AIR_END = 375


class Peach(IntEnum):
    FLOAT = 341
    FLOAT_END_FORWARD = 342
    FLOAT_END_BACKWARD = 343
    FLOAT_NAIR = 344
    FLOAT_FAIR = 345
    FLOAT_BAIR = 346
    FLOAT_UAIR = 347
    FLOAT_DAIR = 348
    SIDE_SMASH_GOLF_CLUB = 349
    SIDE_SMASH_FRYING_PAN = 350
    SIDE_SMASH_TENNIS_RACKET = 351
    VEGETABLE_GROUND = 352
    VEGETABLE_AIR = 353
    BOMBER_GROUND_STARTUP = 354
    BOMBER_GROUND_END = 355
    BOMBER_AIR_STARTUP = 357
    BOMBER_AIR_END = 358
    BOMBER_AIR_HIT = 359
    BOMBER_AIR = 360
    PARASOL_GROUND_START = 361
    PARASOL_AIR_START = 363
    TOAD_GROUND = 365
    TOAD_GROUND_ATTACK = 366
    TOAD_AIR = 367
    TOAD_AIR_ATTACK = 368
    PARASOL_OPENING = 369
    PARASOL_OPEN = 370


class Pichu(IntEnum):
    THUNDER_JOLT_GROUND = 341
    THUNDER_JOLT_AIR = 342
    SKULL_BASH_GROUND_STARTUP = 343
    SKULL_BASH_GROUND_CHARGE = 344
    SKULL_BASH_GROUND_LANDING = 346
    SKULL_BASH_GROUND_TAKEOFF = 347
    SKULL_BASH_AIR_STARTUP = 348
    SKULL_BASH_AIR_CHARGE = 349
    SKULL_BASH_AIR = 350
    SKULL_BASH_AIR_END = 351
    SKULL_BASH_AIR_TAKEOFF = 352
    AGILITY_GROUND_STARTUP = 353
    AGILITY_GROUND = 354
    AGILITY_GROUND_END = 355
    AGILITY_AIR_STARTUP = 356
    AGILITY_AIR = 357
    AGILITY_AIR_END = 358
    THUNDER_GROUND_STARTUP = 359
    THUNDER_GROUND = 360
    THUNDER_GROUND_HIT = 361
    THUNDER_GROUND_END = 362
    THUNDER_AIR_STARTUP = 363
    THUNDER_AIR = 364
    THUNDER_AIR_HIT = 365
    THUNDER_AIR_END = 366


class Pikachu(IntEnum):
    THUNDER_JOLT_GROUND = 341
    THUNDER_JOLT_AIR = 342
    SKULL_BASH_GROUND_STARTUP = 343
    SKULL_BASH_GROUND_CHARGE = 344
    SKULL_BASH_GROUND_LANDING = 346
    SKULL_BASH_GROUND_TAKEOFF = 347
    SKULL_BASH_AIR_STARTUP = 348
    SKULL_BASH_AIR_CHARGE = 349
    SKULL_BASH_AIR = 350
    SKULL_BASH_AIR_END = 351
    SKULL_BASH_AIR_TAKEOFF = 352
    QUICK_ATTACK_GROUND_STARTUP = 353
    QUICK_ATTACK_GROUND = 354
    QUICK_ATTACK_GROUND_END = 355
    QUICK_ATTACK_AIR_STARTUP = 356
    QUICK_ATTACK_AIR = 357
    QUICK_ATTACK_AIR_END = 358
    THUNDER_GROUND_STARTUP = 359
    THUNDER_GROUND = 360
    THUNDER_GROUND_HIT = 361
    THUNDER_GROUND_END = 362
    THUNDER_AIR_STARTUP = 363
    THUNDER_AIR = 364
    THUNDER_AIR_HIT = 365
    THUNDER_AIR_END = 366


class Popo(IntEnum):
    ICE_SHOT_GROUND = 341
    ICE_SHOT_AIR = 342
    SQUALL_HAMMER_GROUND_SOLO = 343
    SQUALL_HAMMER_GROUND_TOGETHER = 344
    SQUALL_HAMMER_AIR_SOLO = 345
    SQUALL_HAMMER_AIR_TOGETHER = 346
    BELAY_GROUND_STARTUP = 347
    BELAY_GROUND_CATAPULTING_NANA = 348
    BELAY_GROUND_FAILED_CATAPULTING = 350
    BELAY_GROUND_FAILED_CATAPULTING_END = 351
    BELAY_AIR_STARTUP = 352
    BELAY_AIR_CATAPULTING_NANA = 353
    BELAY_CATAPULTING = 354
    BELAY_AIR_FAILED_CATAPULTING = 355
    BELAY_AIR_FAILED_CATAPULTING_END = 356
    BLIZZARD_GROUND = 357
    BLIZZARD_AIR = 358


class Roy(IntEnum):
    FLARE_BLADE_GROUND_START_CHARGE = 341
    FLARE_BLADE_GROUND_CHARGE_LOOP = 342
    FLARE_BLADE_GROUND_EARLY_RELEASE = 343
    FLARE_BLADE_GROUND_FULLY_CHARGED = 344
    FLARE_BLADE_AIR_START_CHARGE = 345
    FLARE_BLADE_AIR_CHARGE_LOOP = 346
    FLARE_BLADE_AIR_EARLY_RELEASE = 347
    FLARE_BLADE_AIR_FULLY_CHARGED = 348
    DOUBLE_EDGE_DANCE_1_GROUND = 349
    DOUBLE_EDGE_DANCE_2_UP_GROUND = 350
    DOUBLE_EDGE_DANCE_2_SIDE_GROUND = 351
    DOUBLE_EDGE_DANCE_3_UP_GROUND = 352
    DOUBLE_EDGE_DANCE_3_SIDE_GROUND = 353
    DOUBLE_EDGE_DANCE_3_DOWN_GROUND = 354
    DOUBLE_EDGE_DANCE_4_UP_GROUND = 355
    DOUBLE_EDGE_DANCE_4_SIDE_GROUND = 356
    DOUBLE_EDGE_DANCE_4_DOWN_GROUND = 357
    DOUBLE_EDGE_DANCE_1_AIR = 358
    DOUBLE_EDGE_DANCE_2_UP_AIR = 359
    DOUBLE_EDGE_DANCE_2_SIDE_AIR = 360
    DOUBLE_EDGE_DANCE_3_UP_AIR = 361
    DOUBLE_EDGE_DANCE_3_SIDE_AIR = 362
    DOUBLE_EDGE_DANCE_3_DOWN_AIR = 363
    DOUBLE_EDGE_DANCE_4_UP_AIR = 364
    DOUBLE_EDGE_DANCE_4_SIDE_AIR = 365
    DOUBLE_EDGE_DANCE_4_DOWN_AIR = 366
    BLAZER_GROUND = 367
    BLAZER_AIR = 368
    COUNTER_GROUND = 369
    COUNTER_GROUND_HIT = 370
    COUNTER_AIR = 371
    COUNTER_AIR_HIT = 372


class Samus(IntEnum):
    BOMB_JUMP_GROUND = 341
    BOMB_JUMP_AIR = 342
    CHARGE_SHOT_GROUND_START = 343
    CHARGE_SHOT_GROUND_LOOP = 344
    CHARGE_SHOT_GROUND_END = 345
    CHARGE_SHOT_GROUND_FIRE = 346
    CHARGE_SHOT_AIR_START = 347
    CHARGE_SHOT_AIR_FIRE = 348
    MISSILE_GROUND = 349
    MISSILE_SMASH_GROUND = 350
    MISSILE_AIR = 351
    MISSILE_SMASH_AIR = 352
    SCREW_ATTACK_GROUND = 353
    SCREW_ATTACK_AIR = 354
    BOMB_END_GROUND = 355
    BOMB_AIR = 356
    ZAIR = 357
    ZAIR_CATCH = 358


class Sheik(IntEnum):
    NEEDLE_STORM_GROUND_START_CHARGE = 341
    NEEDLE_STORM_GROUND_CHARGE_LOOP = 342
    NEEDLE_STORM_GROUND_END_CHARGE = 343
    NEEDLE_STORM_GROUND_FIRE = 344
    NEEDLE_STORM_AIR_START_CHARGE = 345
    NEEDLE_STORM_AIR_CHARGE_LOOP = 346
    NEEDLE_STORM_AIR_END_CHARGE = 347
    NEEDLE_STORM_AIR_FIRE = 348
    CHAIN_GROUND_STARTUP = 349
    CHAIN_GROUND_LOOP = 350
    CHAIN_GROUND_END = 351
    CHAIN_AIR_STARTUP = 352
    CHAIN_AIR_LOOP = 353
    CHAIN_AIR_END = 354
    VANISH_GROUND_STARTUP = 355
    VANISH_GROUND_DISAPPEAR = 356
    VANISH_GROUND_REAPPEAR = 357
    VANISH_AIR_STARTUP = 358
    VANISH_AIR_DISAPPEAR = 359
    VANISH_AIR_REAPPEAR = 360
    TRANSFORM_GROUND = 361
    TRANSFORM_GROUND_ENDING = 362
    TRANSFORM_AIR = 363
    TRANSFORM_AIR_ENDING = 364


class Yoshi(IntEnum):
    SHIELD_HOLD = 342
    SHIELD_RELEASE = 343
    SHIELD_DAMAGE = 344
    SHIELD_STARTUP = 345
    EGG_LAY_GROUND = 346
    EGG_LAY_GROUND_CAPTURE_START = 347
    EGG_LAY_GROUND_CAPTURE = 349
    EGG_LAY_AIR = 351
    EGG_LAY_AIR_CAPTURE_START = 352
    EGG_LAY_AIR_CAPTURE = 354
    EGG_ROLL_GROUND_STARTUP = 356
    EGG_ROLL_GROUND = 357
    EGG_ROLL_GROUND_CHANGE_DIRECTION = 358
    EGG_ROLL_GROUND_END = 359
    EGG_ROLL_AIR_START = 360
    EGG_ROLL_AIR = 361
    EGG_ROLL_BOUNCE = 362
    EGG_ROLL_AIR_END = 363
    EGG_THROW_GROUND = 364
    EGG_THROW_AIR = 365
    BOMB_GROUND = 366
    BOMB_LAND = 367
    BOMB_AIR = 368


class YoungLink(IntEnum):
    SIDE_SMASH_2 = 341
    TAUNT_R = 342
    TAUNT_L = 343
    FIRE_BOW_GROUND_CHARGE = 344
    FIRE_BOW_GROUND_FULLY_CHARGED = 345
    FIRE_BOW_GROUND_FIRE = 346
    FIRE_BOW_AIR_CHARGE = 347
    FIRE_BOW_AIR_FULLY_CHARGED = 348
    FIRE_BOW_AIR_FIRE = 349
    BOOMERANG_GROUND_THROW = 350
    BOOMERANG_GROUND_CATCH = 351
    BOOMERANG_GROUND_THROW_EMPTY = 352
    BOOMERANG_AIR_THROW = 353
    BOOMERANG_AIR_CATCH = 354
    BOOMERANG_AIR_THROW_EMPTY = 355
    SPIN_ATTACK_GROUND = 356
    SPIN_ATTACK_AIR = 357
    BOMB_GROUND = 358
    BOMB_AIR = 359
    ZAIR = 360
    ZAIR_CATCH = 361


class Zelda(IntEnum):
    NAYRUS_LOVE_GROUND = 341
    NAYRUS_LOVE_AIR = 342
    DINS_FIRE_GROUND_STARTUP = 343
    DINS_FIRE_GROUND_TRAVEL = 344
    DINS_FIRE_GROUND_EXPLODE = 345
    DINS_FIRE_AIR_STARTUP = 346
    DINS_FIRE_AIR_TRAVEL = 347
    DINS_FIRE_AIR_EXPLODE = 348
    FARORES_WIND_GROUND = 349
    FARORES_WIND_GROUND_DISAPPEAR = 350
    FARORES_WIND_GROUND_REAPPEAR = 351
    FARORES_WIND_AIR = 352
    FARORES_WIND_AIR_DISAPPEAR = 353
    FARORES_WIND_AIR_REAPPEAR = 354
    TRANSFORM_GROUND = 355
    TRANSFORM_GROUND_ENDING = 356
    TRANSFORM_AIR = 357
    TRANSFORM_AIR_ENDING = 358


CHARACTER_STATE_DICT = {
    InGameCharacter.BOWSER: Bowser,
    InGameCharacter.CAPTAIN_FALCON: CaptainFalcon,
    InGameCharacter.DONKEY_KONG: DonkeyKong,
    InGameCharacter.DR_MARIO: DrMario,
    InGameCharacter.FALCO: Falco,
    InGameCharacter.FOX: Fox,
    InGameCharacter.GAME_AND_WATCH: GameAndWatch,
    InGameCharacter.GANONDORF: Ganondorf,
    InGameCharacter.JIGGLYPUFF: Jigglypuff,
    InGameCharacter.KIRBY: Kirby,
    InGameCharacter.LINK: Link,
    InGameCharacter.LUIGI: Luigi,
    InGameCharacter.MARIO: Mario,
    InGameCharacter.MARTH: Marth,
    InGameCharacter.MEWTWO: Mewtwo,
    InGameCharacter.NANA: Nana,
    InGameCharacter.NESS: Ness,
    InGameCharacter.PEACH: Peach,
    InGameCharacter.PICHU: Pichu,
    InGameCharacter.PIKACHU: Pikachu,
    InGameCharacter.POPO: Popo,
    InGameCharacter.ROY: Roy,
    InGameCharacter.SAMUS: Samus,
    InGameCharacter.SHEIK: Sheik,
    InGameCharacter.YOSHI: Yoshi,
    InGameCharacter.YOUNG_LINK: YoungLink,
    InGameCharacter.ZELDA: Zelda,
    None: ActionState,
}
