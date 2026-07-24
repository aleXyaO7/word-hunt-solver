from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()


# ---------- Trie setup ----------
class TrieNode:
    __slots__ = ("children", "is_word")

    def __init__(self):
        self.children = {}
        self.is_word = False


def build_trie(words):
    root = TrieNode()
    for w in words:
        node = root
        for ch in w:
            node = node.children.setdefault(ch, TrieNode())
        node.is_word = True
    return root


def load_dictionary(path="words_alpha.txt", min_length=3, max_length=15):
    with open(path) as f:
        words = {
            line.strip().upper()
            for line in f
            if min_length <= len(line.strip()) <= max_length
        }
    return words


DICTIONARY = load_dictionary()
TRIE_ROOT = build_trie(DICTIONARY)

# ---------- Solver ----------
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def find_words(grid: List[List[str]], min_length: int = 3):
    rows, cols = len(grid), len(grid[0])
    found = {}  # word -> path (list of [row, col])

    def dfs(r, c, node, path, visited):
        letter = grid[r][c].upper()
        if letter not in node.children:
            return
        next_node = node.children[letter]

        if next_node.is_word and len(path) + 1 >= min_length:
            word = "".join(grid[pr][pc].upper() for pr, pc in path) + letter
            if word not in found:
                found[word] = path + [(r, c)]

        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited:
                visited.add((nr, nc))
                dfs(nr, nc, next_node, path + [(r, c)], visited)
                visited.remove((nr, nc))

    for r in range(rows):
        for c in range(cols):
            visited = {(r, c)}
            dfs(r, c, TRIE_ROOT, [], visited)

    return found


# ---------- API ----------
class SolveRequest(BaseModel):
    grid: List[List[str]]
    min_length: int = 3


class SolveResponse(BaseModel):
    words: List[str]
    count: int
    status: str = "ok"


@app.post("/solve", response_model=SolveResponse)
async def solve(request: SolveRequest) -> SolveResponse:
    found = find_words(request.grid, request.min_length)
    words_sorted = [str(s) for s in sorted(found.keys(), key=len, reverse=True)]
    return SolveResponse(words=words_sorted, count=len(words_sorted))
