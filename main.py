import io
import os
from typing import List

import easyocr
import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from PIL import Image, ImageOps
from pydantic import BaseModel

app = FastAPI()


@app.get("/")
async def health_check():
    return {"status": "ok"}

# EasyOCR reader, loaded lazily on first use so uvicorn can start and pass
# the health check before the model finishes downloading.
_ocr_reader = None


def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


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


def load_dictionary(path="words_alpha.txt", min_length=3):
    with open(path) as f:
        words = {line.strip().upper() for line in f if len(line.strip()) >= min_length}
    return words


DICTIONARY = load_dictionary()
TRIE_ROOT = build_trie(DICTIONARY)

# ---------- Solver ----------
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def find_words(grid: List[List[str]], min_length: int = 3):
    rows, cols = len(grid), len(grid[0])
    found = {}

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
            dfs(r, c, TRIE_ROOT, [], {(r, c)})

    return found


# ---------- /solve models + endpoint ----------
DEFAULT_SIZE = 4
DEFAULT_MIN_LENGTH = 3


class SolveRequest(BaseModel):
    letters: str  # e.g. "CATSORENDOGSABCD"


class SolveResponse(BaseModel):
    words: List[str]
    count: int
    status: str = "ok"


def solve_letters(letters: str) -> SolveResponse:
    """
    Shared logic: takes a flat letter string, validates it, builds the grid,
    runs the DFS/trie solver, and returns a SolveResponse. Used by both the
    /solve endpoint and /play (so there's exactly one place this logic lives).
    """
    letters = letters.upper().strip()
    expected = DEFAULT_SIZE * DEFAULT_SIZE

    if len(letters) != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Expected {expected} letters for a {DEFAULT_SIZE}x{DEFAULT_SIZE} grid, got {len(letters)}",
        )

    grid = [
        list(letters[i * DEFAULT_SIZE : (i + 1) * DEFAULT_SIZE])
        for i in range(DEFAULT_SIZE)
    ]

    found = find_words(grid, DEFAULT_MIN_LENGTH)
    words_sorted = [str(s) for s in sorted(found.keys(), key=len, reverse=True)]
    return SolveResponse(words=words_sorted, count=len(words_sorted))


@app.post("/solve", response_model=SolveResponse)
async def solve(request: SolveRequest) -> SolveResponse:
    return solve_letters(request.letters)


# ---------- Single-cell letter recognition via EasyOCR ----------
ALLOWED_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def read_letter_from_image(img: Image.Image) -> tuple[str, float]:
    """
    Runs EasyOCR on a single cropped letter tile and returns the best
    single-character guess plus its confidence (0-1, higher is better).

    A white padding border is added before OCR -- text detectors often need
    some blank margin around a shape to recognize it as text at all, and
    thin/narrow letters (like a bare vertical line for "I") are the most
    likely to sit right at the crop edges.

    Detection thresholds are loosened from EasyOCR's defaults (text_threshold,
    low_text, contrast_ths) since a single thin, low-contrast stroke is
    exactly the kind of shape the default settings are prone to miss.

    If EasyOCR still detects nothing at all, this defaults to "I" -- a bare
    vertical line is the most common case where OCR finds no text region to
    latch onto, since there's so little shape to detect.
    """
    padded = ImageOps.expand(img, border=20, fill="white")
    np_img = np.array(padded.convert("RGB"))

    results = get_ocr_reader().readtext(
        np_img,
        allowlist=ALLOWED_LETTERS,
        detail=1,
        paragraph=False,
        text_threshold=0.5,
        low_text=0.3,
        contrast_ths=0.05,
    )

    if not results:
        return "I", 0.0

    # Pick the highest-confidence detection, then take its first character
    # in case EasyOCR returns more than one character for a single tile.
    best = max(results, key=lambda r: r[2])
    text, confidence = best[1], best[2]
    text = text.strip().upper()
    if not text:
        return "I", 0.0

    return text[0], float(confidence)


class IdentifyResponse(BaseModel):
    letter: str
    confidence: float
    status: str = "ok"


@app.post("/identify-letter", response_model=IdentifyResponse)
async def identify_letter(file: UploadFile = File(...)) -> IdentifyResponse:
    contents = await file.read()
    try:
        img = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(
            status_code=400, detail="Could not read uploaded file as an image."
        )

    letter, confidence = read_letter_from_image(img)
    return IdentifyResponse(letter=letter, confidence=confidence)


class GridIdentifyResponse(BaseModel):
    letters: str
    size: int
    per_cell_confidence: List[float]
    status: str = "ok"


# ---- Hardcoded grid bounding box (calibrate these once for your phone/game) ----
# These are pixel coordinates within the FULL screenshot image.
GRID_X = 182
GRID_Y = 1245
GRID_WIDTH = 927
GRID_HEIGHT = 927
# GRID_SIZE reuses DEFAULT_SIZE (defined above near /solve) so there's one
# single place that controls board size for the whole app.
GRID_SIZE = DEFAULT_SIZE


@app.post("/identify-grid", response_model=GridIdentifyResponse)
async def identify_grid(request: Request):
    """
    Accepts the FULL screenshot as a multipart/form-data upload (this is what
    Shortcuts actually sends even when "File" is picked as the body type).
    Grabs whichever field in the form contains the uploaded file, regardless
    of its field name. Uses the hardcoded GRID_X / GRID_Y / GRID_WIDTH /
    GRID_HEIGHT / GRID_SIZE constants above for the bounding box -- edit
    those directly if your board's position or size ever changes.
    Crops out each cell server-side and reads each letter with EasyOCR.
    """
    x, y, width, height, size = GRID_X, GRID_Y, GRID_WIDTH, GRID_HEIGHT, GRID_SIZE

    # Shortcuts sends the image as multipart/form-data even when "File" is
    # selected as the body type, so we parse the form and grab whichever
    # field contains the uploaded file, regardless of its field name.
    form = await request.form()
    upload = None
    for value in form.values():
        if isinstance(value, StarletteUploadFile):
            upload = value
            break

    if upload is None:
        raise HTTPException(
            status_code=400,
            detail="No file found in the request. Make sure the Shortcut sends the screenshot as a file/form upload.",
        )

    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    # ---- DEBUG: save exactly what was received, for inspection ----
    with open("debug_received.png", "wb") as f:
        f.write(contents)
    # -----------------------------------------------------------

    try:
        full_img = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(
            status_code=400, detail="Could not read uploaded file as an image."
        )

    img_w, img_h = full_img.size
    if x < 0 or y < 0 or x + width > img_w or y + height > img_h:
        raise HTTPException(
            status_code=400,
            detail=f"Grid box ({x},{y},{width},{height}) falls outside image bounds ({img_w}x{img_h}).",
        )

    cell_w = width / size
    cell_h = height / size

    letters = []
    confidences = []

    for row in range(size):
        for col in range(size):
            left = x + col * cell_w
            top = y + row * cell_h
            right = left + cell_w
            bottom = top + cell_h

            cell_img = full_img.crop((left, top, right, bottom))
            # Upscale small tiles for more reliable OCR
            cell_img = cell_img.resize((256, 256))

            letter, confidence = read_letter_from_image(cell_img)

            letters.append(letter)
            confidences.append(confidence)

    grid_letters = "".join(letters)
    print(f"[identify_grid] letters: {grid_letters}")

    return GridIdentifyResponse(
        letters=grid_letters,
        size=size,
        per_cell_confidence=confidences,
    )


# ---------- Combined endpoint: screenshot in, words out ----------
class PlayResponse(BaseModel):
    letters: str
    words: List[str]
    count: int
    max_score: int
    per_cell_confidence: List[float]
    status: str = "ok"


@app.post("/play", response_model=PlayResponse)
async def play(request: Request):
    """
    One-call endpoint: POST the raw screenshot bytes, get back the solved word list.
    This is literally just identify_grid() followed by solve_letters() --
    the same two steps /identify-grid and /solve do separately, chained
    together here for convenience.
    """
    grid_result = await identify_grid(request=request)
    solved = solve_letters(grid_result.letters)
    letters = "\n".join([grid_result.letters[i * 4 : i * 4 + 4] for i in range(4)])
    print(f"[play] letters:\n{letters}")

    max_score = sum([(len(word) - 3) * 400 + 100 for word in solved.words])

    return PlayResponse(
        letters=letters,
        words=solved.words[:15],
        count=solved.count,
        max_score=max_score,
        per_cell_confidence=grid_result.per_cell_confidence,
    )
