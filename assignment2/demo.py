# Plays one match between two agents and prints the board every few turns.
from robofootball.agents import GreedyAgent, MinimaxAgent
from robofootball.game import render
from robofootball.match import play_match

if __name__ == "__main__":
    result = play_match(MinimaxAgent(4, "field"), GreedyAgent("structure"), seed=3, record=True)
    for state in result["history"][::8]:
        print(render(state), "\n")
    print("final score A-B:", result["score"], "shots:", result["shots"])
