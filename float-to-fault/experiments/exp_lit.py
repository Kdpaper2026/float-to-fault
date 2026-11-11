"""Amendment A7 (exploratory): court litigation / stay order as an independent delay cause.
Frozen files are not edited; the event compiler and the perturbation function are patched at run time.
  python3 -I exp_lit.py test                               # development split, 2 instances
  python3 -I exp_lit.py run <dev|held> <N_per_size> <outfile> <cfg> [workers]
"""
import os, sys, math, json, random, itertools, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import exp_engine as E
import exp_run as X
from exp_engine import Inst, Model, shapley, gen_event

PARTIES = ['employer', 'authority', 'contractor', 'neutral', 'court']
LQ, SG, BT, TAU = .10, .5, .5, .5
LC = {'primary': dict(scale=1.0, lead=.25, cm=1.0), 'scale_lo': dict(scale=.5, lead=.25, cm=1.0), 'scale_hi': dict(scale=2.0, lead=.25, cm=1.0),
      'lead_lo': dict(scale=1.0, lead=.10, cm=1.0), 'lead_hi': dict(scale=1.0, lead=.50, cm=1.0), 'cost3': dict(scale=1.0, lead=.25, cm=3.0)}
E.SURVEY_W['litigation'] = 0.5

def compile2(inst, evs):
    n = inst.n; K = len(evs); REL = np.zeros((K, n), dtype=np.int64); EXT = np.zeros((K, n), dtype=np.int64); CUT = [None] * K
    for k, e in enumerate(evs):
        t = e['type']
        if t == 'litigation':
            for j in e['rel_jobs']: REL[k, j] = e['release']
        elif t in ('design_hold', 'site_access', 'supply_delay', 'approval_wait'): REL[k, e['job']] = e['release']
        elif t in ('productivity', 'rework'): EXT[k, e['job']] = e['amount']
        elif t == 'labour': CUT[k] = (e['res'], e['a'], e['b'])
        else:
            for j, a in e['jobs']: EXT[k, j] += a
    return REL, EXT, CUT
E.compile_events = compile2
_perturb0 = X.perturb
def perturb2(inst, e, mult):
    if e['type'] == 'litigation':
        e = dict(e); w2 = max(1, round(e['size'] * mult)); e['release'] = e['a'] + w2; e['b'] = e['a'] + w2; e['size'] = w2; return e
    return _perturb0(inst, e, mult)
X.perturb = perturb2

def make_lit(inst, name, lc):
    r = random.Random(X.seed_of(name, 'lit')); M0 = inst.M0; S0 = inst.S0
    a = int(round(r.uniform(.1, .6) * M0)); w = max(1, int(round(lc['scale'] * r.uniform(.05, .20) * M0))); zl = r.gauss(0, 1)
    rel_jobs = [j for j in inst.real if S0[j] >= a]
    return dict(id=8, type='litigation', owner='court', job=None, release=a + w, amount=0, jobs=None, res=None, a=a, b=a + w, size=w, rel_jobs=rel_jobs, when=a, phi=1.0), zl

def lead_pct(sh, owners, D):
    s = {p: sum(sh[i] for i in range(len(owners)) if owners[i] == p) / D for p in PARTIES}
    return s, max(PARTIES, key=lambda p: (s[p], p))

def world(inst, name, evs, z, regimes, lc, tag):
    K = len(evs); MT = Model(inst, evs); full = (1 << K) - 1; M0 = inst.M0; Mfull = MT.M(full); D = Mfull - M0
    if D <= 0: return None
    sh = shapley(MT.M, list(range(K))); owners = [e['owner'] for e in evs]; share_t, lead_t = lead_pct(sh, owners, D)
    t = TAU * Mfull; mk, Sall, Fall = MT.realised(full); assert mk == Mfull
    pin = ((Sall < t), Sall.copy(), (Fall - Sall).copy())
    lead_of = lambda e: (LQ * M0 if e['type'] == 'approval_wait' else (lc['lead'] * M0 if e['type'] == 'litigation' else 0.0))
    MTp = Model(inst, evs, pin, dict(Sall=Sall, t=t, lead=[lead_of(e) for e in evs], phi=[1.0] * K)); assert MTp.M(full, 0) == Mfull
    fixable = [i for i in range(K) if evs[i]['type'] != 'weather']; Rtrue = {}
    for r in range(len(fixable) + 1):
        for sub in itertools.combinations(fixable, r):
            m = sum(1 << i for i in sub); Rtrue[m] = Mfull - MTp.M(full, m)
    cost_t = [max(1.0, evs[i]['size']) * math.exp(SG * z[i]) * (lc['cm'] if evs[i]['type'] == 'litigation' else 1.0) for i in range(K)]
    med = float(np.median([cost_t[i] for i in fixable])); B = BT * sum(cost_t[i] for i in fixable)
    feas = [m for m in Rtrue if sum(cost_t[i] for i in range(K) if m >> i & 1) <= B + 1e-9]
    bestk = max(((Rtrue[m], -sum(cost_t[i] for i in range(K) if m >> i & 1), -m) for m in feas)); ro = bestk[0]; mo = -bestk[2]
    li = [i for i in range(K) if evs[i]['type'] == 'litigation']
    out = dict(D=D, K=K, shares_true=share_t, lead_true=lead_t, ro=ro, lit_in_oracle=int(bool(li) and bool(mo >> li[0] & 1)), lit_days=(sh[li[0]] if li else 0.0), regs={})
    for rg in regimes:
        if rg == 'a': obs = [dict(e, tid=e['id']) for e in evs]
        elif rg == 'lo': obs = [dict(e, tid=e['id']) for e in evs if e['type'] != 'litigation']
        else: obs = X.observe(inst, evs, rg, random.Random(X.seed_of(name, 'lit', tag, rg)), 'primary', False)
        if rg == 'lo':
            for i, o in enumerate(obs): o['id'] = i
        Ko = len(obs)
        if Ko == 0: out['regs'][rg] = None; continue
        fo_all = (1 << Ko) - 1; Mo = MT if rg == 'a' else Model(inst, obs); Dobs = Mo.M(fo_all) - M0
        if Dobs <= 0: out['regs'][rg] = dict(Dobs=Dobs); continue
        sho = sh if rg == 'a' else shapley(Mo.M, list(range(Ko)))
        share_o, lead_o = lead_pct(sho, [o['owner'] for o in obs], Dobs)
        Mp = Model(inst, obs, pin, None); she = shapley(Mp.M, list(range(Ko)))
        fixo = [i for i in range(Ko) if obs[i]['type'] != 'weather']
        if rg == 'a': tab = Rtrue
        else:
            Mop = Model(inst, obs, pin, dict(Sall=Sall, t=t, lead=[lead_of(e) for e in obs], phi=[1.0] * Ko)); base = Mop.M(fo_all, 0); tab = {}
            for r in range(len(fixo) + 1):
                for sub in itertools.combinations(fixo, r):
                    m = sum(1 << i for i in sub); tab[m] = base - Mop.M(fo_all, m)
        cost_o = [cost_t[o['tid']] if o['tid'] is not None else med for o in obs]
        def Rt(sel): return Rtrue[sum(1 << obs[i]['tid'] for i in sel if obs[i]['tid'] is not None)]
        def haslit(sel): return int(any(obs[i]['type'] == 'litigation' for i in sel))
        c1 = X.fill(sorted(fixo, key=lambda i: (-E.SURVEY_W[obs[i]['type']], i)), cost_o, B)
        c2 = X.fill(sorted(fixo, key=lambda i: (-sho.get(i, 0.0), i)), cost_o, B)
        c2e = X.fill(sorted(fixo, key=lambda i: (-she.get(i, 0.0), i)), cost_o, B)
        c3 = []; rem = B
        while True:
            cur = tab[sum(1 << i for i in c3)] if c3 else 0.0; best = None
            for i in fixo:
                if i in c3 or cost_o[i] > rem + 1e-9: continue
                g = tab[sum(1 << x for x in c3 + [i])] - cur
                if g > 1e-9 and (best is None or g / cost_o[i] > best[0] + 1e-12): best = (g / cost_o[i], i)
            if best is None: break
            c3.append(best[1]); rem -= cost_o[best[1]]
        b4 = None
        for m in tab:
            cs = sum(cost_o[i] for i in range(Ko) if m >> i & 1)
            if cs <= B + 1e-9:
                key = (tab[m], -cs, -m)
                if b4 is None or key > b4: b4 = key
        m4 = -b4[2]; c4 = [i for i in range(Ko) if m4 >> i & 1]
        pol = {'P1': c1, 'P2': c2, 'P2e': c2e, 'P3': c3, 'P4': c4}
        out['regs'][rg] = dict(Dobs=Dobs, share_obs=share_o, lead_obs=lead_o, R={k: Rt(v) for k, v in pol.items()}, lit={k: haslit(v) for k, v in pol.items()}, nobs=Ko, nph=sum(1 for o in obs if o['tid'] is None))
    return out

def run_lit(arg):
    name, cfgn = arg; lc = LC[cfgn]; inst = Inst(name); rng = random.Random(X.seed_of(name, 'primary', 'ev'))
    evs8 = [gen_event(inst, rng, i, 'primary', 1.0) for i in range(8)]; z8 = [rng.gauss(0, 1) for _ in range(8)]
    for e in evs8: e['phi'] = 1.0
    lit, zl = make_lit(inst, name, lc); evs9 = evs8 + [lit]; z9 = z8 + [zl]
    A = world(inst, name, evs8, z8, ['a', 'c', 'd'], lc, 'w8'); B = world(inst, name, evs9, z9, ['a', 'lo', 'c', 'd'], lc, 'w9')
    return dict(name=name, nact=inst.n - 2, M0=inst.M0, lit_size=lit['size'], lit_start=lit['a'], A=A, B=B)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'test':
        S = X.sample('dev', 1)[:3]; t0 = time.time()
        for p in S:
            r = run_lit((p['name'], 'primary')); print(p['name'], 'lit', r['lit_size'], '@', r['lit_start'], 'M0', r['M0'], 'DA', r['A'] and r['A']['D'], 'DB', r['B'] and r['B']['D'],
                  'leadB', r['B'] and r['B']['lead_true'], 'lit_days', r['B'] and round(r['B']['lit_days'], 1), 'ro', r['B'] and r['B']['ro'], round(time.time() - t0, 1), 's')
            if r['B']: print('   regs', {k: (v and v.get('R')) for k, v in r['B']['regs'].items()})
    elif cmd == 'run':
        import multiprocessing as mp
        split, nper, outf, cfgn = sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]; W = int(sys.argv[6]) if len(sys.argv) > 6 else 2
        S = X.sample(split, nper, seed=20261102); t0 = time.time()
        with mp.Pool(W) as pl: res = pl.map(run_lit, [(p['name'], cfgn) for p in S], chunksize=2)
        json.dump(dict(split=split, cfg=cfgn, rows=res), open(outf, 'w')); print(len(res), 'instances', round(time.time() - t0), 's ->', outf)
