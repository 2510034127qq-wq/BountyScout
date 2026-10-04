```python
import random

def dodge_rolling(prompt):
    roll = random.randint(1, 10)
    if prompt == "Dodge":
        return f"Dodge Rolling: {roll}"
    else:
        return "Please input 'Dodge' to use this function."
```