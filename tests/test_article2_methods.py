#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name, ROOT/filename)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

rates=load("rates","06_article2_rates.py")
dec=load("dec","08_article2_decomposition.py")

assert len(rates.EXPECTED_AGES)==19
assert abs(sum(rates.WHO.values())-1.0)<1e-12
assert abs(rates.WHO_RAW["90+"]-(0.15+0.04+0.005))<1e-12

# Decomposição sintética: deve reconstruir a mudança exatamente.
N0=1000.; N1=1200.
S0=np.array([0.8,0.2]); S1=np.array([0.7,0.3])
R0=np.array([0.01,0.05]); R1=np.array([0.008,0.04])
c=dec.shapley_decompose(N0,S0,R0,N1,S1,R1)
y0=dec.outcome(N0,S0,R0); y1=dec.outcome(N1,S1,R1)
assert abs(sum(c.values())-(y1-y0))<1e-10

# Se só o tamanho muda, apenas growth deve contribuir.
c2=dec.shapley_decompose(N0,S0,R0,N1,S0,R0)
assert abs(c2["ageing"])<1e-12 and abs(c2["rate_change"])<1e-12
assert abs(c2["growth"]-(dec.outcome(N1,S0,R0)-dec.outcome(N0,S0,R0)))<1e-10
print("OK — métodos do Artigo 2 passaram nos testes sintéticos.")