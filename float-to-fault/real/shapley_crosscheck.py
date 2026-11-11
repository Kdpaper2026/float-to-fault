"""Independent check of the engine's Shapley values: permutation enumeration (8! orders) vs the subset-weight formula used in exp_engine."""
import sys, itertools, random, math
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'experiments')); import exp_run as X
from exp_engine import *
S = X.sample('dev', 2, seed=7)[:8]; worst = 0.0; n = 0
for p in S:
    inst = Inst(p['name']); rng = random.Random(X.seed_of(p['name'], 'primary', 'ev')); K = 8
    evs = [gen_event(inst, rng, i, 'primary', 1.0) for i in range(K)]
    for e in evs: e['phi'] = 1.0
    MT = Model(inst, evs); sh = shapley(MT.M, list(range(K)))
    perm = [0.0] * K; cache = {}
    M = lambda m: cache.setdefault(m, MT.M(m))
    cnt = 0
    for order in itertools.permutations(range(K)):
        m = 0; prev = M(0)
        for i in order: m |= 1 << i; cur = M(m); perm[i] += cur - prev; prev = cur
        cnt += 1
    perm = [x / cnt for x in perm]; err = max(abs(perm[i] - sh[i]) for i in range(K)); worst = max(worst, err); n += 1
    print(p['name'], 'D=%.1f' % (M((1 << K) - 1) - M(0)), 'max |perm - formula| = %.2e' % err, 'sum=%.3f' % sum(sh.values()))
print('instances', n, 'worst abs difference %.2e' % worst)
