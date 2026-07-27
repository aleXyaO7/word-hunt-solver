Ping `https://word-hunt-solver--AlexY7.replit.app/play` with a screenshot of a Word Hunt game and receive a list of all available words that corresponds with alphaDictionary.

```
curl -X POST https://word-hunt-solver--alexy7.replit.app/play \
  -F "file=image.png"
```
where image.png is a tightly cropped screenshot of only the 4x4 grid.

Alternatively, ping `https://word-hunt-solver--AlexY7.replit.app/solve` with a 16-letter string representation of the 4x4 board.

```
curl -X POST https://word-hunt-solver--alexy7.replit.app/solve \
  -H "Content-Type: application/json" \
  -d '{"letters": "ABCDEFGHIJKLMNOP"}'
```
which represents the board:
```
ABCD
EFGH
IJKL
MNOP
```

To use the Shortcut: https://www.icloud.com/shortcuts/caa01eca1c0f435aac18af5101bbe2d8

Or, set it up manually by adding these steps:

1. Take Screenshot
2. Crop Image => Crop screenshot tightly (only the 4x4 grid)
3. Get Contents of URL => URL=`https://word-hunt-solver--AlexY7.replit.app/play`, Method=POST, Request Body=Form => 'file': (screenshot)
4. Get Dictionary Value => Get Value for 'letters' in (Contents of URL)
5. Send Message => Send (Dictionary Value) to (some phone number)
6. Get Dictionary Value => Get Value for 'max_score' in (Contents of URL)
7. Send Message => Send (Dictionary Value) to (some phone number)
8. Get Dictionary Value => Get Value for 'words' in (Contents of URL)
9. Combine Text => Combine (Dictionary Value) with New Lines
10. Send Message => Send (Combined Text) to (some phone number)

Additional things can be added, such as a Text field that stores the phone number or sending the cropped screenshot to the number as well.
