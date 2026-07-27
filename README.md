Ping `https://word-hunt-solver--AlexY7.replit.app/play` with a screenshot of a Word Hunt game and receive a list of all available words that corresponds with alphaDictionary.

Example curl request:
```
curl -X POST https://word-hunt-solver--alexy7.replit.app/play \
  -F "file=screenshot.png"
```
where screenshot.png is your screenshot file.

Alternatively, set up a shortcut on an appropriate iPhone model:

1. Take Screenshot
2. Get Contents of URL => URL=`https://word-hunt-solver--AlexY7.replit.app/play`, Method=POST, Request Body=Form => 'file': (screenshot)
3. Get Dictionary Value => Get Value for 'letters' in (Contents of URL)
4. Send Message => Send (Dictionary Value) to (some phone number)
5. Get Dictionary Value => Get Value for 'max_score' in (Contents of URL)
6. Send Message => Send (Dictionary Value) to (some phone number)
7. Get Dictionary Value => Get Value for 'words' in (Contents of URL)
8. Combine Text => Combine (Dictionary Value) with New Lines
9. Send Message => Send (Combined Text) to (some phone number)
