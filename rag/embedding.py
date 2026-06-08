"""基于词频统计的小型本地向量化模型。"""

import math
from collections import Counter
from typing import Counter as CounterType, Dict

from tools.score_tool import tokenize


Vector = Dict[str, float]
"""内存向量库使用的稀疏向量类型。"""


def embed_text(text: str) -> Vector:
    """将文本转换为归一化的稀疏词袋向量。"""

    counts: CounterType[str] = Counter(token.lower() for token in tokenize(text))
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {token: value / norm for token, value in counts.items()}


def cosine_similarity(left: Vector, right: Vector) -> float:
    """计算两个稀疏向量之间的余弦相似度。"""

    if not left or not right:
        return 0.0
    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    return sum(value * larger.get(token, 0.0) for token, value in smaller.items())
