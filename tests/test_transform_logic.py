#!/usr/bin/env python3
"""
Teste sintético da codificação de idade e das principais regex CID.
Não usa os dados reais.
"""
import re

def age_years(x):
    s = str(int(x)).zfill(3)
    if s == "999":
        return None
    if s[0] in {"0","1","2","3"}:
        return 0
    if s[0] == "4":
        return int(s[1:])
    if s[0] == "5":
        return 100 + int(s[1:])
    return None

def normalize(s):
    return (s or "").upper().replace(".", "")

def has(blob, pattern):
    blob = normalize(blob)
    return bool(re.search(r"(^|[^A-Z0-9])" + pattern + r"([^A-Z0-9]|$)", blob))

assert age_years("460") == 60
assert age_years("499") == 99
assert age_years("500") == 100
assert age_years("512") == 112
assert age_years("023") == 0
assert age_years("205") == 0
assert age_years("311") == 0
assert age_years("999") is None

assert has("*G309 *I639 *E119", r"(G30|F00)[0-9A-Z]?")
assert has("*G309 *I639 *E119", r"I6[0-9][0-9A-Z]?")
assert has("*G309 *I639 *E119", r"E1[0-4][0-9A-Z]?")
assert not has("*G309 *I639", r"N18[0-9A-Z]?")

print("OK — testes sintéticos passaram.")