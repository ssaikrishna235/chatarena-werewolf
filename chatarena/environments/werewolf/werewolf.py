import random
import re
from typing import Dict, List, Union
import sys
import json
from ...agent import SIGNAL_END_OF_CONVERSATION
from ...message import Message, MessagePool
from ..base import Environment, TimeStep, register_env
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
DEFAULT_PROMPTS = "prompt_jsons/default.json"
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
        self.prompt_dict = None
        self._initialized = False
        self.night_vote_dict = {}
        self.day_vote_dict = {}
    
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
        if len(sys.argv) > 0:
            prompt_dict = self._get_prompt_dict(sys.argv[1])
        else:
            prompt_dict = self._get_prompt_dict(DEFAULT_PROMPTS)
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
        """Individual players are explicitly reminded who is dead."""
        if player_name is None:
            return self.message_pool.get_all_messages()
        else:
            return self.message_pool.get_visible_messages(
                player_name, turn=self._current_turn
            ).extend(self.get_dead_list())
        
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
        terminal = self.is_terminal()
        timestep = TimeStep(
            observation=self.get_observation(), reward=self.get_rewards(terminal), terminal=terminal
        )

        if self.is_terminal():
            timestep.terminal = True

    def day_discuss_turn(self, player_name: str, action: str):
        """Day discuss phase turn for all roles."""
        self.message_pool.append_message(
            Message(agent_name=player_name, content=action, turn=self._current_turn)
            )
        
    def day_vote_turn(self, player_name: str, action: str):
        """Day vote phase turn for all roles."""
        message = Message(
            agent_name=player_name,
            content=action,
            turn=self._current_turn,
            visible_to=player_name,
        )
        self.message_pool.append_message(message) # Logs the who took the action and when, only visable to the current player in game.
        vote = self._text2vote(action)
        self.day_vote_dict[vote] += 1

    def night_discuss_turn(self, player_name: str, action: str):
        """Night discussion phase turn for special roles."""
        if (self.player_roles[player_name] == WEREWOLF):
            self.message_pool.append_message(
                Message(agent_name=player_name, content=action, turn=self._current_turn, visible_to=self.werewolf_list)
                )

    def night_vote_turn(self, player_name: str, action: str):
        """Night vote phase turn for special roles."""
        # Check if this is a special role, i.e. not basic townsfolk.
        if self.player_roles[player_name] == TOWNSFOLK: # Townsfolk don't have night actions.
            return
        else:
            message = Message(
                agent_name=player_name,
                content=action,
                turn=self._current_turn,
                visible_to=player_name,
            )
            self.message_pool.append_message(message) # Logs the who took the action and when, only visable to the current player in game.
            vote = self._text2vote(action)
            self.night_vote_dict[vote] = self.player_roles[player_name]

    # def reveal_turn(self, player_name: str):
    #     """Reveal phase turn, this is just informing the agents what happened in the night"""

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
        player_roles = [list(islice(it, 0, i)) for i in distribution]
        self.werewolf_list = []
        for player in player_roles:
            if player_roles[player] == WEREWOLF:
                self.werewolf_list.append(player)
        return player_roles
    
    #Taken from Cameleon, a fairly heavy implementation, but gives leniency to response.
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
    
    #Currently gives no rewards
    def get_rewards(self, is_terminal):
        reward_dict = {}
        for player in self.player_names:
            reward_dict[player] = 0

    def get_dead_list(self):
        dead_list = []
        for player in self.player_status.keys():
            if self.player_status[player] == DEAD:
                dead_list.append(player + " is dead, do not conside them.")
    
    def _moderator_speak(self, text: str, visible_to: Union[str, List[str]] = "all"):
        """Moderator say something."""
        message = Message(
            agent_name="Moderator",
            content=text,
            turn=self._current_turn,
            visible_to=visible_to,
        )
        self.message_pool.append_message(message)

    def _get_prompt_dict(self, file_name):
        """Read the json for the prompts."""
        try:
            with open(file_name, 'r', encoding='utf-8') as file_object:
                return json.load(file_object)
        except IOError:
            with open(DEFAULT_PROMPTS, 'r', encoding='utf-8') as file_object:
                return json.load(file_object)
