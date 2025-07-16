from typing import List, Dict, Set, Tuple
from pathlib import Path
from collections import Counter, defaultdict
from settings import RESOURCES_PATH

import discord
import logging
import heapq

logger = logging.getLogger(__name__)
# Contains all the known hints
# green: int -> char (spot -> char)
# yellow: char -> ints (where it cannot be)
# gray: Set[char]
# maxInstances: char -> int, describes the maximum amount of a character there can be in
#               in a word. this can be found out when you double guess a letter (e.x. ALARM)
#               and one of them shows up as yellow. 
#               **If the char doesn't have any restrictions, it will not be in the dict.**
#   notable invariants: maxInstances is only ever updated when there's a gray + yellow/green in the same guess
#                       gray always includes any char used for a maxInstances rule
class Hints:
    def __init__(self,
                 green: Dict[int, str] = None, 
                 yellow: Dict[str, List[int]] = None, 
                 gray: Set[str] = None,
                 max_instances: Dict[str, int] = None):
        self.green = green if green is not None else {}
        self.yellow = defaultdict(list, yellow if yellow is not None else {})
        self.gray = gray if gray is not None else set()
        self.max_instances = max_instances if max_instances is not None else {}
    
    def copy(self) -> "Hints":
        return Hints(
            green=self.green.copy(),
            yellow=defaultdict(list, {k: v[:] for k, v in self.yellow.items()}),
            gray=self.gray.copy(),
            max_instances=self.max_instances.copy()
        )
    
    def __repr__(self):
        return f"Hints(green={self.green}, yellow={dict(self.yellow)}, gray={self.gray}, max_instances={self.max_instances})"
    
class WordleSolver:
    def __init__(self,
                 hardMode: bool, 
                 answer: str, 
                 guesses: List[str], 
                 possible_guesses_filepath: Path):
        self.hardMode = hardMode
        self.answer = answer
        self.guesses = guesses
        self.hints = Hints()
        with open(possible_guesses_filepath) as f:
            self.possible_guesses = [line.strip() for line in f]
        self.valid_words = self.possible_guesses.copy()
        # Pre-compute character counts for all words to avoid repeated Counter() calls
        self.word_char_counts = {}
        for word in self.possible_guesses:
            self.word_char_counts[word] = Counter(word)

    def is_valid(self, word: str, hints: Hints) -> bool:
        char_count = self.word_char_counts[word]
        for c in hints.gray:
            # check if c shows up in the word too many times based on info we have
            if c in hints.max_instances:
                if char_count[c] > hints.max_instances[c]:
                    return False
            else:
                # Fully banned letter
                if c in word:
                    return False
        
        # Check green positions (fixed positions)
        for pos, c in hints.green.items():
            if word[pos] != c:
                return False
        
        # Check yellow constraints
        for c, bad_positions in hints.yellow.items():
            if c not in word:
                return False
            if any(word[pos] == c for pos in bad_positions):
                return False
        
        return True

    def update_valid_words(self, new_hints: Hints):
        self.valid_words = [word for word in self.valid_words if self.is_valid(word, new_hints)]

    def simulate_feedback(self, guess: str, target_word: str) -> Hints:
        if len(guess) != len(target_word):
            logger.error("guess is not the same length as target")
            return Hints()
        
        new_hints = self.hints.copy()
        seen = set()
        ans_counter = Counter(target_word)
        used_counts = defaultdict(int)

        for i, c in enumerate(guess):
            if target_word[i] == c:
                new_hints.green[i] = c
                seen.add(i)
                ans_counter[c] -= 1
                used_counts[c] += 1
        
        for i, c in enumerate(guess):
            # if we already have a green feedback there, skip it
            if i in seen:
                continue
            
            # so now, if we encounter a match, and there are remaining 'counters' for that
            # character, then we mark as yellow. Otherwise, gray.
            if c in target_word and ans_counter[c] > 0:
                if i not in new_hints.yellow[c]:
                    new_hints.yellow[c].append(i)
                ans_counter[c] -= 1
                used_counts[c] += 1
            else:
                new_hints.gray.add(c)

        # if used_counts and guess_counts differ, then a max occurence rule must be added
        guess_counts = Counter(guess)
        for c in used_counts:
            if guess_counts[c] > used_counts[c]:
                if c in new_hints.max_instances:
                    new_hints.max_instances[c] = min(new_hints.max_instances[c], used_counts[c])
                else: 
                    new_hints.max_instances[c] = used_counts[c]
        
        return new_hints

    def find_optimal_guess(self) -> List[str]:
        # find the set of allowed guesses if in hardMode
        candidates = []
        if self.hardMode:
            # Use pre-filtered valid words instead of checking all possible_guesses
            candidates = self.valid_words.copy()
        else:
            candidates = self.possible_guesses

        results = []
        for guess in candidates:
            heapq.heappush(results, (self.evaluate_guess(guess), guess))
        
        return results
    
    # calculate the expected number of words remaining after making a guess
    # against all possible target words
    # lower scores are better (fewer words remaining on average)
    def evaluate_guess(self, guess: str) -> float:
        """
        Evaluate a guess by calculating the expected number of words remaining
        after making this guess against all possible target words.
        Lower scores are better (fewer words remaining).
        """
        total_remaining = 0
        
        # Test this guess against every possible target word
        for target_word in self.valid_words:
            simulated_hints = self.simulate_feedback(guess, target_word)
            
            # Count how many words would still be valid after getting this feedback
            remaining_after_feedback = 0
            for candidate in self.valid_words:
                if self.is_valid(candidate, simulated_hints):
                    remaining_after_feedback += 1
            
            total_remaining += remaining_after_feedback
        
        # Return average number of words remaining
        return total_remaining / len(self.valid_words) if self.valid_words else 0
    
    # make a guess and update the internal state
    def make_guess(self, guess: str):
        self.hints = self.simulate_feedback(guess, self.answer)
        self.update_valid_words(self.hints)
    
    def evaluate_guesses(self) -> List[Tuple[float, str]]:
        scores = []
        
        # assume the same starter as the one made
        self.make_guess(self.guesses[0])

        for guess in self.guesses[1:]:
            remaining_words_actual = self.evaluate_guess(guess)
            
            results = self.find_optimal_guess()
            best_words = []
            if results:
                remaining_words_theoretical, _ = results[0]
                while results and results[0][0] == remaining_words_theoretical:
                    _, word = heapq.heappop(results)
                    best_words.append(word)
            
            scores.append((remaining_words_theoretical/remaining_words_actual * 100, best_words))
          
            # update state using the actual guess made
            self.make_guess(guess)

        return scores

import discord, asyncio

async def grade_wordle(interaction: discord.Interaction, guesses: str):
    guesses_arr = [guess.strip().lower() for guess in guesses.split(',')]
    for guess in guesses_arr:
        if not guess.isalpha():
            await interaction.response.send_message(
                "Input must be a comma-separated list of the actual guesses you made. "
                'For example, "bread, scout, hoist" would be valid input. '
                "Please include both the opener and the answer.",
                ephemeral=True
            )
            return

    solver = WordleSolver(
        True,
        guesses_arr[-1],
        guesses_arr[:-1],
        Path(f"{RESOURCES_PATH}/wordle_valid_answers.txt")
    )

    await interaction.response.defer()

    scores = await asyncio.to_thread(solver.evaluate_guesses)

    embed = discord.Embed(title="Wordle Guess Evaluation", color=discord.Color.green())
    embed.add_field(
        name="Starter",
        value=f"||{guesses_arr[0]}||",
        inline=False
    )

    for i, (percentage, optimal_words) in enumerate(scores, start=1):
        guess_word = guesses_arr[i]
        guess_spoiler = f"||{guess_word}||"
        optimal_list = ', '.join(optimal_words)
        optimal_spoiler = f"||{optimal_list}||"
        embed.add_field(
            name=f"Guess {i}: {guess_spoiler}",
            value=f"{percentage:.2f}% as good as the optimal guess(es) {optimal_spoiler}",
            inline=False
        )

    embed.add_field(
        name="Answer",
        value=f"||{guesses_arr[-1]}||",
        inline=False
    )

    await interaction.followup.send(embed=embed)
