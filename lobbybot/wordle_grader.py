from typing import List, Dict, Set, Tuple
from pathlib import Path
from collections import Counter, defaultdict
from settings import RESOURCES_PATH

import discord
import logging

GREEN, YELLOW, GRAY = "G", "Y", "B"
emoji_map = {
    GREEN: '🟩',
    YELLOW: '🟨',
    GRAY: '⬛'
}

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
    
    def add_hints_from_feedback(self, feedback: str, guess: str):
        used_counts = defaultdict(int)

        for i, (fb, c) in enumerate(zip(feedback, guess)):
            if fb == "G":
                self.green[i] = c
                used_counts[c] += 1
            elif fb == "Y":
                self.yellow[c].append(i)
                used_counts[c] += 1
            elif fb == "B":
                self.gray.add(c)

        # if there are more of a character than we 'used' in green/yellow hints, that means there is a maximum clause.
        guess_counts = Counter(guess)
        for c in guess_counts:
            if guess_counts[c] > used_counts[c]:
                self.max_instances[c] = used_counts[c]

    def __repr__(self):
        return f"Hints(green={self.green}, yellow={dict(self.yellow)}, gray={self.gray}, max_instances={self.max_instances})"

# returns 5 char string that would be given by Wordle if guess = guess when target = target
# G = green, Y = yellow, B = black/gray
# note: this assumes that wordles goes left to right on yellow giving (I.e. if there's one A in the word, and we guess 2, the first will be given yellow).
def simulate_feedback(guess: str, target: str) -> str:
    pattern = [GRAY] * len(guess)
    # used to determine if we should mark yellow or gray
    remaining = Counter(target)

    # mark greens
    for i, (g_char, t_char) in enumerate(zip(guess, target)):
        if g_char == t_char:
            pattern[i] = GREEN
            remaining[g_char] -= 1

    # mark yellows
    for i, g_char in enumerate(guess):
        if pattern[i] == GRAY and remaining[g_char] > 0:
            pattern[i] = YELLOW
            remaining[g_char] -= 1

    return ''.join(pattern)

def feedback_to_emojis(feedback: str) -> str:
    return ''.join(emoji_map[c] for c in feedback)

class WordleSolver:
    def __init__(self,
                 hard_mode: bool, 
                 answer: str, 
                 guesses: List[str], 
                 possible_guesses_filepath: Path,
                 possible_answers_filepath: Path):
        self.hard_mode = hard_mode
        self.answer = answer
        self.guesses = guesses
        self.hints = Hints()
        with open(possible_guesses_filepath) as f:
            self.possible_guesses = [line.strip() for line in f]
        with open(possible_answers_filepath) as f:
            self.possible_answers = [line.strip() for line in f]
        self.valid_guesses = self.possible_guesses.copy()
        self.valid_answers = self.possible_answers.copy()
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

    def find_optimal_guess(self) -> List[Tuple[float, str]]:
        # find the set of allowed guesses if in hard_mode
        candidate_guesses = self.valid_guesses if self.hard_mode else self.possible_guesses
        best_score = float('inf')
        best_words = []

        # if scores are within 0.001 of each other, count them as the same
        for g in candidate_guesses:
            score = self.evaluate_guess(g)
            if score < best_score - 1e-3:
                best_score = score
                best_words = [g]
            elif abs(score - best_score) < 1e-3:
                best_words.append(g)

        return [(best_score, w) for w in sorted(best_words)]

    
    # calculate the expected number of words remaining after making a guess
    # against all possible target words
    # lower scores are better (fewer words remaining on average)
    # ** ASSUMES valid_answers/guesses is consistent (i.e. it only contains actually valid words)
    def evaluate_guess(self, guess: str) -> float:
        target_candidates = self.valid_answers
        n = len(target_candidates)
        if n == 0:
            return 0.0
        
        # SPEEDIER LOGIC! instead of simulating feedback for each guess and finding each 
        bucket_counts = defaultdict(int)
        for target in target_candidates:
            p = simulate_feedback(guess, target)
            bucket_counts[p] += 1

        # expected number of remaining words = average bucket size across all possible hidden targets.
        total = 0
        for k in bucket_counts.values():
            total += k * k
        return total / n
    
    # make a guess and update the internal state
    def make_guess(self, guess: str):
        self.hints.add_hints_from_feedback(simulate_feedback(guess, self.answer), guess)
        self.valid_guesses = [word for word in self.valid_guesses if self.is_valid(word, self.hints)]
        self.valid_answers = [word for word in self.valid_answers if self.is_valid(word, self.hints)]
    
    def evaluate_guesses(self) -> List[Tuple[float, str]]:
        scores = []
        # use same opener
        self.make_guess(self.guesses[0])

        for guess in self.guesses[1:]:
            # how good was the guess you actually made?
            actual_score = self.evaluate_guess(guess)

            # what would have been optimal *at that point in time?*
            optimal = self.find_optimal_guess()
            if optimal:
                optimal_score = optimal[0][0]  # all same score
                optimal_words = [w for _, w in optimal]
            else:
                optimal_score = 0.0
                optimal_words = []

            pct = (optimal_score / actual_score * 100) if actual_score else -1.0
            scores.append((pct, optimal_words))

            # advance game state with the actual guess
            self.make_guess(guess)

        return scores

import discord

async def grade_wordle(interaction: discord.Interaction, guesses: str, answer: str, try_all_words: bool):
    guesses_arr = [guess.strip().lower() for guess in guesses.split(',')]
    answer = answer.strip().lower()
    if answer and guesses_arr[-1] != answer:
        guesses_arr.append(answer)

    for guess in guesses_arr:
        if not guess.isalpha():
            await interaction.response.send_message(
                "Input must be a comma-separated list of the actual guesses you made. "
                'For example, "bread, scout, hoist" would be valid input. '
                "Please include both the opener and the answer.",
                ephemeral=True
            )
            return
        
    if len(guesses_arr) <= 1:
        await interaction.response.send_message(
                "Congratulations on getting the Wordle in 1! " \
                "Unfortunately, there's nothing to analyze here...",
                ephemeral=True
            )
        
    guess_filepath = "wordle_valid_guesses.txt" if try_all_words else "wordle_valid_answers.txt"
    real_answer = guesses_arr[-1]
    
    solver = WordleSolver(
        True,
        real_answer,
        guesses_arr[:-1],
        Path(f"{RESOURCES_PATH}/{guess_filepath}"),
        Path(f"{RESOURCES_PATH}/wordle_valid_answers.txt")
    )

    await interaction.response.defer()

    scores = solver.evaluate_guesses()

    embed = discord.Embed(title="Wordle Guess Evaluation", color=discord.Color.green())
    embed.add_field(
        name=f"Starter",
        value=f"{feedback_to_emojis(simulate_feedback(guesses_arr[0], real_answer))} ||{guesses_arr[0]}||",
        inline=False
    )

    for i, (percentage, optimal_words) in enumerate(scores, start=1):
        guess_word = guesses_arr[i]
        guess_spoiler = f"||{guess_word}||"
        optimal_list = ', '.join(optimal_words)
        optimal_spoiler = f"||{optimal_list}||"
        embed.add_field(
            name=f"Guess {i}",
            value=f"{feedback_to_emojis(simulate_feedback(guess_word, real_answer))} {guess_spoiler}\n" 
                  f"{percentage:.2f}% as good as the optimal guess(es) {optimal_spoiler}",
            inline=False
        )

    embed.add_field(
        name="Answer",
        value=f"||{guesses_arr[-1]}||",
        inline=False
    )

    await interaction.followup.send(embed=embed)
