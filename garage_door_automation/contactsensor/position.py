from enum import Enum, auto


class Position(Enum):
  FULLY_CLOSED = auto()
  SLIGHTLY_OPENED = auto()
  FULLY_OPENED = auto()
  BACK_YARD_DOOR = auto()
