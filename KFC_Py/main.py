
import logging
from GameFactory import create_game
from GraphicsFactory import ImgFactory

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    game = create_game("pieces", ImgFactory())
    game.run()

