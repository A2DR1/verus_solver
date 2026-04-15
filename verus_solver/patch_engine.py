from dataclasses import dataclass
from typing import List


@dataclass
class TextPatch:
    old: str
    new: str
    description: str = ""


def apply_text_patches(code: str, patches: List[TextPatch]) -> str:
    updated = code
    for patch in patches:
        updated = updated.replace(patch.old, patch.new)
    return updated

