```python
from mashpy import ParallelTask

def process_items(items):
    pt = ParallelTask(workers=4)
    pt.pipe.items = items
    pt.run()
    return pt.results

items = ["item1", "item2", "item3", "item4"]
result = process_items(items)
print(result)
```