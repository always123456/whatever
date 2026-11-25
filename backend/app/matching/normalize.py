"""技能/行业别名归一（确定性，无 key 也生效）：供转卡层与抽取层统一。

- 规范值优先常见英文写法（Python / JavaScript / ...），中文别名归到规范词。
- 未命中的值 strip 后原样返回，避免误改 C++ / Node.js / Go 等特殊大小写。
- 只合并「同义别名/拼写变体」，不合并语义上不同的词（MySQL 与 PostgreSQL 保持独立）。
"""

_SKILL_ALIASES = {
    # 语言
    "python": "Python", "py": "Python", "python3": "Python", "python开发": "Python",
    "javascript": "JavaScript", "js": "JavaScript", "ecmascript": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "java": "Java",
    "golang": "Go", "go语言": "Go",
    "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#",
    # 前端
    "vue": "Vue", "vuejs": "Vue", "vue.js": "Vue", "vue3": "Vue",
    "react": "React", "reactjs": "React", "react.js": "React",
    # 后端/中间件
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "pg": "PostgreSQL",
    "mysql": "MySQL",
    "fastapi": "FastAPI",
    # 运维/工具
    "linux": "Linux",
    "docker": "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "git": "Git",
    # AI
    "pytorch": "PyTorch", "torch": "PyTorch",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "机器学习": "机器学习", "machine learning": "机器学习", "machinelearning": "机器学习", "ml": "机器学习",
    "深度学习": "深度学习", "deep learning": "深度学习", "deeplearning": "深度学习", "dl": "深度学习",
    # 领域
    "后端开发": "后端开发", "后端": "后端开发", "服务端": "后端开发", "backend": "后端开发",
    "前端开发": "前端开发", "前端": "前端开发", "frontend": "前端开发",
    "数据分析": "数据分析",
}

_INDUSTRY_ALIASES = {
    "互联网": "互联网", "it": "互联网", "互联网行业": "互联网", "web": "互联网",
    "人工智能": "人工智能", "ai": "人工智能",
    "数据": "数据", "大数据": "数据",
    "云计算": "云计算", "云": "云计算", "cloud": "云计算",
    "金融": "金融", "fintech": "金融",
    "教育": "教育",
    "医疗": "医疗", "医疗健康": "医疗",
    "电商": "电商", "电子商务": "电商",
}


def _normalize_token(value, alias_map) -> str:
    if not value:
        return ""
    t = str(value).strip()
    if not t:
        return ""
    return alias_map.get(t.lower(), t)


def normalize_skill(value) -> str:
    """单个技能名归一；空/None 返回空串。"""
    return _normalize_token(value, _SKILL_ALIASES)


def normalize_skills(values) -> list:
    """技能列表归一 + 去重（保序）。"""
    seen = set()
    out = []
    for v in values or []:
        n = normalize_skill(v)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def normalize_industry(value) -> str:
    """单个行业名归一；空/None 返回空串。"""
    return _normalize_token(value, _INDUSTRY_ALIASES)
