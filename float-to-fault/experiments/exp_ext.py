"""Amendment A4: extraction-error sweep and money objective (exploratory)."""
import os, sys, math, json, random, itertools, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import exp_run as X
from exp_engine import *
GRID = [(r, p, n) for r in (.5, .7, .9) for p in (.6, .8, 1.0) for n in (0.0, .25, .5)]
RHOS = (1.5, 3.0, 6.0)
for (r, p, n) in GRID: X.REG[f'g{r}_{p}_{n}'] = dict(rec=r, prec=p, noise=n)
TAU, LQ, SG, BT = .5, .10, .5, .5

def run_ext(arg):
    name, meta = arg; cfg = X.CFGS['primary']; inst = Inst(name); rng = random.Random(X.seed_of(name, 'primary', 'ev'))
    K = 8; evs = [gen_event(inst, rng, i, cfg['mix'], cfg['scale']) for i in range(K)]; z = [rng.gauss(0, 1) for _ in range(K)]
    for e in evs: e['phi'] = 1.0
    MT = Model(inst, evs); full = (1 << K) - 1; M0 = inst.M0; Mfull = MT.M(full); D = Mfull - M0
    if D <= 0: return dict(name=name, skip=1)
    t = TAU * Mfull; mk, Sall, Fall = MT.realised(full)
    pin = ((Sall < t), Sall.copy(), (Fall - Sall).copy())
    fixable = [i for i in range(K) if evs[i]['type'] != 'weather']
    lead_of = lambda e: (LQ * M0 if e['type'] == 'approval_wait' else 0.0)
    MTp = Model(inst, evs, pin, dict(Sall=Sall, t=t, lead=[lead_of(e) for e in evs], phi=[1.0] * K))
    Rtrue = {}
    for r in range(len(fixable) + 1):
        for sub in itertools.combinations(fixable, r):
            m = sum(1 << i for i in sub); Rtrue[m] = Mfull - MTp.M(full, m)
    cost_t = [max(1.0, evs[i]['size']) * math.exp(SG * z[i]) for i in range(K)]; med = float(np.median([cost_t[i] for i in fixable]))
    B = BT * sum(cost_t[i] for i in fixable)
    feas = [m for m in Rtrue if sum(cost_t[i] for i in range(K) if m >> i & 1) <= B + 1e-9]
    ro = max(Rtrue[m] for m in feas)
    orc = {rho: max(0.0, max(rho * Rtrue[m] - sum(cost_t[i] for i in range(K) if m >> i & 1) for m in feas)) for rho in RHOS}
    out = dict(name=name, D=D, ro=ro, orc=orc, cells={})
    for rg in ['a'] + [f'g{r}_{p}_{n}' for (r, p, n) in GRID]:
        orng = random.Random(X.seed_of(name, 'obsgrid', rg.split('_')[0] if False else rg)); obs = X.observe(inst, evs, rg, orng, cfg['mix'], False)
        Ko = len(obs)
        if rg == 'a': Mo = MT; obs = [dict(e, tid=e['id']) for e in evs]; Ko = K
        else: Mo = Model(inst, obs)
        fixo = [i for i in range(Ko) if obs[i]['type'] != 'weather']
        cost_o = [cost_t[o['tid']] if o['tid'] is not None else med for o in obs]
        if Ko == 0: out['cells'][rg] = None; continue
        sho = shapley(Mo.M, list(range(Ko))) if rg != 'a' else shapley(MT.M, list(range(K)))
        Mp = Model(inst, obs, pin, None); she = shapley(Mp.M, list(range(Ko)))
        if rg == 'a': tab = Rtrue
        else:
            Mop = Model(inst, obs, pin, dict(Sall=Sall, t=t, lead=[lead_of(e) for e in obs], phi=[1.0] * Ko)); fo_all = (1 << Ko) - 1; base = Mop.M(fo_all, 0); tab = {}
            for r in range(len(fixo) + 1):
                for sub in itertools.combinations(fixo, r):
                    m = sum(1 << i for i in sub); tab[m] = base - Mop.M(fo_all, m)
        def Rt(sel): return Rtrue[sum(1 << obs[i]['tid'] for i in sel if obs[i]['tid'] is not None)]
        def sp(sel): return sum(cost_o[i] for i in sel)
        c1 = X.fill(sorted(fixo, key=lambda i: (-SURVEY_W[obs[i]['type']], i)), cost_o, B)
        c2 = X.fill(sorted(fixo, key=lambda i: (-sho.get(i, 0.0), i)), cost_o, B)
        c2e = X.fill(sorted(fixo, key=lambda i: (-she.get(i, 0.0), i)), cost_o, B)
        def greedy(stop_rho=None):
            c3 = []; rem = B
            while True:
                cur = tab[sum(1 << i for i in c3)] if c3 else 0.0; best = None
                for i in fixo:
                    if i in c3 or cost_o[i] > rem + 1e-9: continue
                    g = tab[sum(1 << x for x in c3 + [i])] - cur
                    if stop_rho is not None and stop_rho * g - cost_o[i] <= 1e-9: continue
                    if g > 1e-9 and (best is None or g / cost_o[i] > best[0] + 1e-12): best = (g / cost_o[i], i)
                if best is None: break
                c3.append(best[1]); rem -= cost_o[best[1]]
            return c3
        def exact(rho=None):
            bestk = None
            for m in tab:
                cs = sum(cost_o[i] for i in range(Ko) if m >> i & 1)
                if cs <= B + 1e-9:
                    key = ((rho * tab[m] - cs) if rho else tab[m], -cs, -m)
                    if bestk is None or key > bestk: bestk = key
            m4 = -bestk[2]; return [i for i in range(Ko) if m4 >> i & 1]
        def ranked_stop(order, rho):
            ch = []; rem = B
            for i in order:
                if cost_o[i] > rem + 1e-9: continue
                cur = tab[sum(1 << x for x in ch)] if ch else 0.0; g = tab[sum(1 << x for x in ch + [i])] - cur
                if rho * g - cost_o[i] > 1e-9: ch.append(i); rem -= cost_o[i]
            return ch
        r1o = sorted(fixo, key=lambda i: (-SURVEY_W[obs[i]['type']], i)); r2eo = sorted(fixo, key=lambda i: (-she.get(i, 0.0), i))
        pol = {'P1': c1, 'P2': c2, 'P2e': c2e, 'P3': greedy(), 'P4': exact()}
        cell = {k: [Rt(v), sp(v)] for k, v in pol.items()}
        for rho in RHOS:
            cell[f'P1s{rho}'] = [Rt(ranked_stop(r1o, rho)), sp(ranked_stop(r1o, rho))]; cell[f'P2es{rho}'] = [Rt(ranked_stop(r2eo, rho)), sp(ranked_stop(r2eo, rho))]
            cell[f'P3n{rho}'] = [Rt(greedy(rho)), sp(greedy(rho))]; e4 = exact(rho); cell[f'P4n{rho}'] = [Rt(e4), sp(e4)]
        cell['nobs'] = Ko; cell['nph'] = sum(1 for o in obs if o['tid'] is None)
        out['cells'][rg] = cell
    return out

if __name__ == '__main__':
    import multiprocessing as mp
    nper, outf, W = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    S = X.sample('held', nper, seed=20261101); t0 = time.time()
    if nper <= 2:
        for p in S[:2]: r = run_ext((p['name'], p)); print(p['name'], r.get('D'), round(time.time() - t0, 1), 's')
    else:
        with mp.Pool(W) as pl: res = pl.map(run_ext, [(p['name'], p) for p in S], chunksize=2)
        json.dump(res, open(outf, 'w')); print(len(res), 'instances', round(time.time() - t0), 's ->', outf)
