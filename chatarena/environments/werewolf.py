import random
import re
from typing import Dict, List, Union

from ..agent import SIGNAL_END_OF_CONVERSATION
from ..message import Message, MessagePool
from .base import Environment, TimeStep, register_env
from itertools import islice
DAY_DISSCUSION = 0
DAY_VOTE = 1
NIGHT_DISSCUSION = 2
NIGHT_VOTE = 3
REVEAL = 4
PLAYER_TO_WEREWOLF_COUNT = {5:1, 6:1, 7:2}
DEFAULT_PLAYER_COUNT = 7
WEREWOLF = 0
TOWNSFOLK = 1
GUARD = 2
SEER = 3
WITCH = 4
HUNTER = 5
DEAD = 0
ALIVE = 1
#2 Werewolfs and 5 Townsfolk
DEFAULT_DISTRIBUTION = [2, 5, 0, 0, 0, 0]
@register_env
class Werewolf(Environment):
    type_name = "werewolf"

    def __init__(
        self,
        player_names: List[str],
        **kwargs,
    ):
        super().__init__(player_names=player_names, **kwargs)
        self.message_pool = MessagePool()
        # Game states
        self._current_turn = 0
        self._next_player_idx = 0
        self._current_phase = DAY_DISSCUSION
        self.players_votes = None
        self.player_status = None
        self.werewolf_list = None
        self._initialized = False
        self.night_vote_dict = {}
    
        self.reset()


    def get_next_player(self) -> str:
        """Get the next player."""
        if self.is_terminal():
            return None
        while self.player_status[self._next_player_idx] != ALIVE:
            self._next_player_idx = (self._next_player_idx + 1) % len(self.player_names)
        return self.player_names[self._next_player_idx]
    

    def reset(self):
        self._current_turn = 0
        self._next_player_idx = 0
        self._current_phase = DAY_DISSCUSION
        self.player_status = self.set_players_alive()
        self.player_roles = self.set_player_roles(DEFAULT_DISTRIBUTION)
        self.night_vote_dict = self.reset_night_vote_dict()
        self.message_pool.reset()
        self._initialized = True
        init_timestep = TimeStep(
            observation=self.get_observation(),
            reward=self.get_zero_rewards(),
            terminal=False,
        )
        # I think I'm being silly, where does this go? 
        # I matched this to their example but...
        return init_timestep

    def print(self):
        """Prints the message pool, I might want to see if I could store this
        in a file for records. """
        self.message_pool.print()
        
    def get_observation(self, player_name=None) -> List[Message]:
        """Get observation for the player."""
        if player_name is None:
            return self.message_pool.get_all_messages()
        else:
            return self.message_pool.get_visible_messages(
                player_name, turn=self._current_turn
            )
        
    def step(self, player_name: str, action: str) -> TimeStep:
        """This is the action to result method so if they all vote and then a time step happens they learn the result and get rewards."""
        # Lets look deep at chameleon about how they handle their step and how that relates to the game. 
        if self._current_phase == DAY_DISSCUSION:
            self.day_discuss_turn(player_name=player_name, action=action)
        elif self._current_phase == DAY_VOTE:
            self.day_vote_turn(player_name=player_name, action=action)
        elif self._current_phase == NIGHT_DISSCUSION:
            self.night_discuss_turn(player_name=player_name, action=action)
        elif self._current_phase == NIGHT_VOTE:
            self.night_vote_turn(player_name=player_name, action=action)

    def day_discuss_turn(self, player_name: str):
        """Day discuss phase turn for all roles."""
        
    def day_vote_turn(self, player_name: str):
        """Day vote phase turn for all roles."""

    def night_discuss_turn(self, player_name: str):
        """Night discussion phase turn for special roles."""

    def night_vote_turn(self, player_name: str, action: str):
        """Night vote phase turn for special roles."""
        # Check if this is a special role, i.e. not basic townsfolk.
        if self.player_roles[player_name] == TOWNSFOLK:
            return
        else:
            # What is the actual night vote behavior, How do I get them to vote?
            message = Message(
                agent_name=player_name,
                content=action,
                turn=self._current_turn,
                visible_to=player_name,
            )
            self.message_pool.append_message(message) # Logs the who took the action and when, only visable to the current player in game.
            vote = self._text2vote(action)
            self.night_vote_dict[vote] = self.player_roles[player_name]

    def check_action(self, action: str, player_name: str) -> bool:
        """Checks if a action is valid."""
        return True

    def is_terminal(self) -> bool:
        """Checks if the game is over, for this that is a victory for werewolf or townsfolk"""
        town_count = 0
        werewolf_count = 0
        for player_name in self.player_status:
            if self.player_status[player_name] == ALIVE and self.player_roles[player_name] > WEREWOLF:
                town_count += 1
            elif self.player_status[player_name] == ALIVE and self.player_roles[player_name] == WEREWOLF:
                werewolf_count += 1
        if werewolf_count == 0 or town_count <= werewolf_count:
            return True
        return False


    def set_players_alive(self) -> Dict[str, float]:
        """
        Return a dictionary with all player names as keys and one as the status.
        """
        return {player_name: 1 for player_name in self.player_names}
    
    def set_player_roles(self, distribution) -> Dict[str, float]:
        it = iter(self.player_names)
        sliced = [list(islice(it, 0, i)) for i in distribution]
        return sliced
    
    
    #Taken from Cameleon, a fairly heavy implementation, but gives leaneancy to response.
    def _text2vote(self, text) -> str:
        """Convert text to vote, return a player's name."""
        # lower = text.lower().replace("[", "").replace("]", "").replace(".", "")
        text = text.lower()
        for name in self.player_names:
            candidates = [
                name.lower(),
                name.lower().replace(" ", ""),
                name.lower().replace(" ", "_"),
            ]
            if any([candidate in text for candidate in candidates]):
                return name
        return ""
    
    def reset_night_vote_dict(self):
        for player in self.player_names:
            self.night_vote_dict[player] = []
    def reset_day_vote_dict(self):
        for player in self.player_names:
            self.night_vote_dict[player] = 0
