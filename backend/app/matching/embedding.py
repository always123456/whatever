"""文本相似度。

MVP 默认 KeywordEmbedder：确定性、零依赖，保证闭环和测试在无模型/无网络环境下跑通。
后续把 config.embedding_backend 设为 semantic、安装 sentence-transformers 后，
可换成 bge 向量余弦相似度，引擎其余部分不变（AI 层可插拔）。
"""
import re
from collections import Counter

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_WORD = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    words = _WORD.findall(text)
    bigrams: list[str] = []
    for seg in _CJK.findall(text):
        if len(seg) == 1:
            bigrams.append(seg)
        else:
            bigrams += [seg[i : i + 2] for i in range(len(seg) - 1)]
    return words + bigrams


def text_similarity(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    ca, cb = Counter(ta), Counter(tb)
    common = set(ca) & set(cb)
    dot = sum(ca[w] * cb[w] for w in common)
    na = sum(v * v for v in ca.values()) ** 0.5
    nb = sum(v * v for v in cb.values()) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
