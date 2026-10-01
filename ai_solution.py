```python
def first_word(s):
    import re
    match = re.match(r'\S+', s)
    return match.group() if match else ''
```