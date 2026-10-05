"""Deterministic random numbers that give the same results on every platform.

Python only guarantees that `random.Random.random()` produces the same sequence
for the same seed across versions. `randrange`, `choice`, `shuffle` and
`sample` may change, so every helper here is built on `random()` alone.

Each component gets its own generator, seeded from SHA-256 of a name, so adding
a component or a draw in one place does not shift the others.
"""

import hashlib
import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class Rng:
    def __init__(self, material: str) -> None:
        self.material = material
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        self._random = random.Random(int.from_bytes(digest[:8], "big"))

    def derive(self, name: str) -> "Rng":
        return Rng(f"{self.material}/{name}")

    def random(self) -> float:
        return self._random.random()

    def chance(self, probability: float) -> bool:
        return self.random() < probability

    def randint(self, low: int, high: int) -> int:
        """Integer in [low, high], both included."""
        return low + int(self.random() * (high - low + 1))

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.random()

    def choice(self, items: Sequence[T]) -> T:
        return items[int(self.random() * len(items))]

    def weighted(self, weights: Sequence[float]) -> int:
        """Index drawn with the given weights (they sum to 1)."""
        point = self.random()
        for index, weight in enumerate(weights):
            if point < weight:
                return index
            point -= weight
        return len(weights) - 1

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        pool = list(items)
        return [pool.pop(int(self.random() * len(pool))) for _ in range(count)]

    def shuffled(self, items: Sequence[T]) -> list[T]:
        return self.sample(items, len(items))
