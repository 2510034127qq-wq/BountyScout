```python
def verify_zero_value_proof(zero, a, m, s):
    # Verify the zero-value proof (ZKP) for the given parameters
    left = (a * s) % m
    right = zero
    return left == right
```