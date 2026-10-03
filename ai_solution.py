```python
def get ListenContinuations():
    from ..config import config
    from ..db import db

    def ListenContinuations():
        db().collection("listen").stream()

    return ListenContinuations
```