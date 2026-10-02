```python
from datetime import datetime

def conversation_to_latex(chat_history: list) -> str:
    """Converts a conversation to a LaTeX report."""
    today = datetime.now().strftime("%Y-%m-%d")
    latex = f"\\begin{{document}}\n\\title{{Conversation Report}}\n\\date{{\\today}}\n\n\\maketitle\n\n"
    for message in chat_history:
        latex += f"\\begin{{quote}}{{}}"
        latex += f"\\textit{{User:}} {message['content']}\n\n"
        latex += f"\\begin{{quote}}{{}}"
        latex += f"\\textit{{Assistant:}} {message['assistant_content']}\n\n"
    latex += "\\end{document}"
    return latex
```

```python
if __name__ == "__main__":
    chat_history = [
        {"content": "Hello, how are you?", "assistant_content": "I'm doing well, thank you."},
        {"content": "What's your favorite color?", "assistant_content": "My favorite color is blue."}
    ]
    print(conversation_to_latex(chat_history))
```