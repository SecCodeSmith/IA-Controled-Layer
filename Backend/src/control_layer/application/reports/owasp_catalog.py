from __future__ import annotations

OWASP_CATALOG: list[tuple[str, str]] = [
    ("LLM01", "Prompt Injection"),
    ("LLM02", "Sensitive Information Disclosure"),
    ("LLM03", "Supply Chain"),
    ("LLM04", "Data and Model Poisoning"),
    ("LLM05", "Improper Output Handling"),
    ("LLM06", "Excessive Agency"),
    ("LLM07", "System Prompt Leakage"),
    ("LLM08", "Vector and Embedding Weaknesses"),
    ("LLM09", "Misinformation"),
    ("LLM10", "Unbounded Consumption"),
    ("ASI01", "Agent Goal Hijack"),
    ("ASI02", "Tool Misuse"),
    ("ASI03", "Identity & Privilege Abuse"),
    ("ASI04", "Agentic Supply Chain"),
    ("ASI05", "Unexpected Code Execution"),
    ("ASI06", "Memory & Context Poisoning"),
    ("ASI07", "Insecure Inter-Agent Communication"),
    ("ASI08", "Cascading Failures"),
    ("ASI09", "Human-Agent Trust Exploitation"),
    ("ASI10", "Rogue Agents"),
]
