To solve the task, we need to create two functions: one to export conversations to JSON Lines (JSONL) format and another to export memories to an Atom feed format.

### Solution Code

```python
import json
from xml.etree import ElementTree as ET

def export_conversations_to_jsonl(conversations):
    """
    Converts a list of conversations into JSON Lines format.
    Each conversation is a dictionary with 'id' and 'messages'.
    Each message is a dictionary with 'id' and 'content'.
    """
    for conv in conversations:
        conv_id = conv['id']
        messages = [{'id': msg['id'], 'content': msg['content']} for msg in conv['messages']]
        yield json.dumps({'id': conv_id, 'messages': messages})

def export_memories_to_atom(memories):
    """
    Converts a list of memories into an Atom feed format.
    Each memory is a dictionary with 'id' and 'content'.
    """
    root = ET.Element('feed', {'xml:lang': 'en'})
    ET.SubElement(root, 'title').text = 'Memories Feed'
    ET.SubElement(root, 'subtitle').text = 'A collection of memories'
    ET.SubElement(root, 'generator').text = 'Python CLI'

    for memory in memories:
        entry = ET.SubElement(root, 'entry')
        id_elem = ET.SubElement(entry, 'id')
        id_elem.text = f'memory-{memory["id"]}'
        content = ET.SubElement(entry, 'content')
        content.text = memory['content']

    return ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8')
```