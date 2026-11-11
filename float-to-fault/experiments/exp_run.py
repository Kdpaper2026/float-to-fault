"""Run the experiments of PROTOCOL.md v1.
  python3 -I exp_run.py test                      # engine self-tests on a few development instances
  python3 -I exp_run.py run <dev|held> <N_per_size> <outfile> [cfgname] [workers]
"""
import os, sys, math, json, random, itertools, hashlib, time, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
from exp_engine import *

CFGS = {
 'primary':  dict(mix='primary', scale=1.0, taus=[.25, .5, .75], Ls=[0.0, .10, .25], sigmas=[0.0, .5, 1.0], betas=[.25, .5, .75], regimes=['a', 'b', 'c', 'd']),
 'partial':  dict(mix='primary', scale=1.0, partial=True, taus=[.5], Ls=[.10], sigmas=[.5], betas=[.5], regimes=['a', 'b', 'c', 'd']),
 'size_lo':  dict(mix='primary', scale=0.5, taus=[.5], Ls=[.10], sigmas=[.5], betas=[.5], regimes=['a', 'b', 'c', 'd']),
 'size_hi':  dict(mix='primary', scale=2.0, taus=[.5], Ls=[.10], sigmas=[.5], betas=[.5], regimes=['a', 'b', 'c', 'd']),
 'mix_owner': dict(mix='owner', scale=1.0, taus=[.5], Ls=[.10], sigmas=[.5], betas=[.5], regimes=['a', 'b', 'c', 'd']),
 'mix_contr': dict(mix='contractor', scale=1.0, taus=[.5], Ls=[.10], sigmas=[.5], betas=[.5], regimes=['a', 'b', 'c', 'd']),
}
REG = {'b': dict(rec=.70, prec=1.0, noise=0.0), 'c': dict(rec=.91, prec=.91, noise=.2), 'd': dict(rec=.50, prec=.80, noise=.5)}
PARTY = {'employer': 'employer', 'authority': 'authority', 'contractor': 'contractor', 'neutral': 'neutral'}

def seed_of(*a): return int(hashlib.sha256('|'.join(map(str, a)).encode()).hexdigest()[:12], 16)

def perturb(inst, e, mult):
    e = dict(e); S0 = inst.S0; t = e['type']
    if t in ('design_hold', 'site_access', 'supply_delay', 'approval_wait'):
        delta = e['release'] - int(S0[e['job']])
        if delta > 0: e['release'] = int(S0[e['job']] + max(1, round(delta * mult)))
        e['size'] = max(1, round(e['size'] * mult))
    elif t in ('productivity', 'rework'): e['amount'] = max(1, round(e['amount'] * mult)); e['size'] = e['amount']
    elif t == 'labour': w = max(1, round((e['b'] - e['a']) * mult)); e['b'] = e['a'] + w; e['size'] = w
    else: e['jobs'] = [(j, max(1, math.ceil(a * mult))) for j, a in e['jobs']]; e['size'] = max(1, sum(a for _, a in e['jobs']))
    return e

def observe(inst, evs, regime, rng, mix, partial=False):
    if regime == 'a': return [dict(e, tid=e['id']) for e in evs]
    p = REG[regime]; kept = [e for e in evs if rng.random() < p['rec']]; obs = []
    for e in kept:
        mult = math.exp(rng.gauss(0, p['noise'])) if p['noise'] > 0 else 1.0
        o = perturb(inst, e, mult) if p['noise'] > 0 else dict(e); o['tid'] = e['id']; obs.append(o)
    x = len(kept) * (1 - p['prec']) / p['prec']; nph = int(x) + (rng.random() < x - int(x))
    for _ in range(nph): ph = gen_event(inst, rng, -1, mix); ph['tid'] = None; ph['phi'] = 0.65 if partial else 1.0; obs.append(ph)
    obs = obs[:10]
    for i, o in enumerate(obs): o['id'] = i
    return obs

def fill(rank, cost, B):
    ch = []; rem = B
    for k in rank:
        if cost[k] <= rem + 1e-9: ch.append(k); rem -= cost[k]
    return ch

def run_instance(arg):
    name, cfgname, meta = arg; cfg = CFGS[cfgname]; inst = Inst(name); rng = random.Random(seed_of(name, cfgname, 'ev'))
    K = 8; evs = [gen_event(inst, rng, i, cfg['mix'], cfg['scale']) for i in range(K)]; z = [rng.gauss(0, 1) for _ in range(K)]
    prng = random.Random(seed_of(name, 'phi'))
    for e in evs: e['phi'] = prng.uniform(.3, 1.0) if cfg.get('partial') else 1.0
    MT = Model(inst, evs); full = (1 << K) - 1; M0 = inst.M0; Mfull = MT.M(full); D = Mfull - M0; res = dict(name=name, nact=inst.n - 2, RS=meta.get('RS'), M0=M0, D=D, K=K)
    if D <= 0: res['skip'] = 'no_delay'; return res
    res['mono'] = all(MT.M(m | 1 << i) >= MT.M(m) for i in range(K) for m in range(1 << K) if not m >> i & 1)
    # ---------------- E1 attribution on the true events
    sh = shapley(MT.M, list(range(K))); assert abs(sum(sh.values()) - D) < 1e-6
    bf = [Mfull - MT.M(full & ~(1 << i)) for i in range(K)]; al = [MT.M(1 << i) - M0 for i in range(K)]
    def windows(order):
        m = 0; prev = M0; w = [0.0] * K
        for i in order: m |= 1 << i; w[i] = MT.M(m) - prev; prev = MT.M(m)
        return w
    win = windows(sorted(range(K), key=lambda i: (evs[i]['when'], i)))
    cpm = []
    for e in evs:
        t = e['type']
        if t in ('design_hold', 'site_access', 'supply_delay', 'approval_wait', 'productivity', 'rework'): cpm.append(float(e['size']) if e['job'] in inst.crit else 0.0)
        elif t == 'weather': cpm.append(float(sum(a for j, a in e['jobs'] if j in inst.crit)))
        else: cpm.append(0.0)
    sets = {}
    for kk in (1, 2, 3):
        opt = max(Mfull - MT.M(full & ~sum(1 << i for i in c)) for c in itertools.combinations(range(K), kk)); row = dict(opt=opt)
        for nm, sc in (('shapley', [sh[i] for i in range(K)]), ('butfor', bf), ('alone', al), ('windows', win), ('cpm', cpm)):
            top = sorted(range(K), key=lambda i: (-sc[i], i))[:kk]; row[nm] = Mfull - MT.M(full & ~sum(1 << i for i in top))
        sets[kk] = row
    wi = [i for i, e in enumerate(evs) if e['type'] == 'weather']; wmask = sum(1 << i for i in wi); Mref = MT.M(wmask)
    players = [i for i in range(K) if i not in wi]; shf = shapley(lambda m: MT.M(m | wmask), players)
    ledger = dict(planned=M0, fixed_ref=Mref, full=Mfull, attributed=Mfull - Mref, shap_sum=sum(shf.values()), n_weather=len(wi))
    owners = [e['owner'] for e in evs]; share_true = {p: sum(sh[i] for i in range(K) if owners[i] == p) / D for p in PARTY}
    res.update(shapley=[sh[i] for i in range(K)], butfor=bf, alone=al, windows=win, cpm=cpm, type=[e['type'] for e in evs], owner=owners, sets=sets, ledger=ledger, share_true=share_true,
               crit_job=[(e['job'] in inst.crit) if e['job'] is not None else None for e in evs])
    # ---------------- observed (regime) models: attribution stability and unpinned Shapley
    regimes = cfg['regimes']; OBS = {}
    for rg in regimes:
        orng = random.Random(seed_of(name, cfgname, 'obs', rg)); obs = observe(inst, evs, rg, orng, cfg['mix'], cfg.get('partial', False))
        Mo = MT if rg == 'a' else Model(inst, obs); Ko = len(obs)
        if Ko == 0: OBS[rg] = dict(obs=obs, Mo=Mo, sh={}, Dobs=0); continue
        fo = (1 << Ko) - 1; Dobs = Mo.M(fo) - M0; sho = shapley(Mo.M, list(range(Ko))) if rg != 'a' else sh
        OBS[rg] = dict(obs=obs, Mo=Mo, sh=sho, Dobs=Dobs)
    stab = {}
    for rg in regimes:
        o = OBS[rg]; obs = o['obs']
        if o['Dobs'] <= 0 or not obs: stab[rg] = dict(Dobs=o['Dobs'], n_obs=len(obs), n_phantom=sum(1 for x in obs if x['tid'] is None)); continue
        sp = {p: sum(o['sh'][i] for i in range(len(obs)) if obs[i]['owner'] == p) / o['Dobs'] for p in PARTY}
        lead_t = max(share_true, key=lambda p: (share_true[p], p)); lead_o = max(sp, key=lambda p: (sp[p], p))
        stab[rg] = dict(Dobs=o['Dobs'], n_obs=len(obs), n_phantom=sum(1 for x in obs if x['tid'] is None), share_obs=sp, err_empauth=abs((sp['employer'] + sp['authority']) - (share_true['employer'] + share_true['authority'])), lead_changed=lead_t != lead_o,
                        share_explained=o['Dobs'] / D)
    res['stab'] = stab
    # ---------------- E2 prospective mitigation at a decision epoch
    out = {}
    fixable_true = [i for i in range(K) if evs[i]['type'] != 'weather']
    for tau in cfg['taus']:
        t = tau * Mfull; mk, Sall, Fall = MT.realised(full); assert mk == Mfull
        pin = ((Sall < t), Sall.copy(), (Fall - Sall).copy())
        SHE = {}
        for rg in regimes:
            ob = OBS[rg]['obs']
            if not ob: SHE[rg] = {}; continue
            Mp = Model(inst, ob, pin, None); SHE[rg] = shapley(Mp.M, list(range(len(ob))))
        for Lq in cfg['Ls']:
            lead_of = lambda e: (Lq * M0 if e['type'] == 'approval_wait' else 0.0)
            MTp = Model(inst, evs, pin, dict(Sall=Sall, t=t, lead=[lead_of(e) for e in evs], phi=[e['phi'] for e in evs]))
            assert MTp.M(full, 0) == Mfull, 'pinned replay mismatch'
            Rtrue = {}
            for r in range(len(fixable_true) + 1):
                for sub in itertools.combinations(fixable_true, r):
                    m = sum(1 << i for i in sub); Rtrue[m] = Mfull - MTp.M(full, m)
            # observed pinned models
            RM = {}
            for rg in regimes:
                obs = OBS[rg]['obs']
                if rg == 'a': RM[rg] = None; continue
                Ko = len(obs)
                Mop = Model(inst, obs, pin, dict(Sall=Sall, t=t, lead=[lead_of(e) for e in obs], phi=[e.get('phi', 1.0) for e in obs])); fo_all = (1 << Ko) - 1
                fixo = [i for i in range(Ko) if obs[i]['type'] != 'weather']; base = Mop.M(fo_all, 0); tab = {}
                for r in range(len(fixo) + 1):
                    for sub in itertools.combinations(fixo, r):
                        m = sum(1 << i for i in sub); tab[m] = base - Mop.M(fo_all, m)
                RM[rg] = tab
            for sg in cfg['sigmas']:
                cost_t = [max(1.0, evs[i]['size']) * math.exp(sg * z[i]) for i in range(K)]; med = float(np.median([cost_t[i] for i in fixable_true]))
                for bt in cfg['betas']:
                    B = bt * sum(cost_t[i] for i in fixable_true)
                    # oracle
                    ro = max((Rtrue[m] for m in Rtrue if sum(cost_t[i] for i in range(K) if m >> i & 1) <= B + 1e-9), default=0)
                    for rg in regimes:
                        obs = OBS[rg]['obs']; Ko = len(obs); fixo = [i for i in range(Ko) if obs[i]['type'] != 'weather']
                        cost_o = [cost_t[o['tid']] if o['tid'] is not None else med for o in obs]
                        tab = Rtrue if rg == 'a' else RM[rg]
                        def Rt(sel):  # score a chosen set of observed indices in the TRUE model
                            return Rtrue[sum(1 << obs[i]['tid'] for i in sel if obs[i]['tid'] is not None)]
                        # P1 frequency
                        r1 = sorted(fixo, key=lambda i: (-SURVEY_W[obs[i]['type']], i)); c1 = fill(r1, cost_o, B)
                        # P2 shapley
                        sho = OBS[rg]['sh']; r2 = sorted(fixo, key=lambda i: (-sho.get(i, 0.0), i)); c2 = fill(r2, cost_o, B)
                        # P2b / P2e / P2eb: cost-aware and epoch-aware Shapley variants (amendment A2)
                        c2b = fill(sorted(fixo, key=lambda i: (-sho.get(i, 0.0) / cost_o[i], i)), cost_o, B)
                        she = SHE[rg]; c2e = fill(sorted(fixo, key=lambda i: (-she.get(i, 0.0), i)), cost_o, B)
                        c2eb = fill(sorted(fixo, key=lambda i: (-she.get(i, 0.0) / cost_o[i], i)), cost_o, B)
                        # P3 greedy marginal per cost, in the analyst's model
                        c3 = []; rem = B
                        while True:
                            cur = tab[sum(1 << i for i in c3)] if c3 else 0.0; best = None
                            for i in fixo:
                                if i in c3 or cost_o[i] > rem + 1e-9: continue
                                g = tab[sum(1 << x for x in c3 + [i])] - cur
                                if g > 1e-9 and (best is None or g / cost_o[i] > best[0] + 1e-12): best = (g / cost_o[i], i)
                            if best is None: break
                            c3.append(best[1]); rem -= cost_o[best[1]]
                        # P4 exact in the analyst's model
                        best4 = (-1, 0, 0)
                        for m in tab:
                            cs = sum(cost_o[i] for i in range(Ko) if m >> i & 1)
                            if cs <= B + 1e-9:
                                key = (tab[m], -cs, -m)
                                if key > best4: best4 = key
                        m4 = -best4[2] if best4[0] >= 0 else 0; c4 = [i for i in range(Ko) if m4 >> i & 1]
                        s2, s4 = frozenset(c2), frozenset(c4)
                        out[f'{tau}|{Lq}|{sg}|{bt}|{rg}'] = [ro, Rt(c1), Rt(c2), Rt(c3), Rt(c4), int(s2 == s4), int((c2[:1] == c4[:1])), len(c2), len(c4), Rt(c2b), Rt(c2e), Rt(c2eb)]
    res['e2'] = out; res['fixable'] = len(fixable_true)
    return res

def sample(split, nper, seed=20261028):
    P = [p for p in pool() if split_of(p['name']) == split]; rng = random.Random(seed); out = []
    by = collections.defaultdict(list)
    for p in sorted(P, key=lambda p: p['name']): by[p['nact']].append(p)
    for na in (30, 60, 90, 120):
        c = by[na]; rng.shuffle(c); out += c[:nper]
    return out

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'test':
        S = sample('dev', 3); t0 = time.time()
        for p in S[:6]:
            inst = Inst(p['name'])
            # baseline reproduction & monotone no-event
            assert inst.run(inst.zero_rel, inst.zero_ext, [], None) == inst.M0
            r = run_instance((p['name'], 'size_lo', p)); print(p['name'], p['nact'], 'M0', r['M0'], 'D', r['D'], 'mono', r.get('mono'), 'ledger', r.get('ledger'), 'keys', len(r.get('e2', {})), round(time.time() - t0, 1), 's')
    elif cmd == 'run':
        import multiprocessing as mp
        split, nper, outf = sys.argv[2], int(sys.argv[3]), sys.argv[4]; cfgname = sys.argv[5] if len(sys.argv) > 5 else 'primary'; W = int(sys.argv[6]) if len(sys.argv) > 6 else 2
        S = sample(split, nper); t0 = time.time(); jobs = [(p['name'], cfgname, p) for p in S]
        with mp.Pool(W) as pool_: res = pool_.map(run_instance, jobs, chunksize=2)
        json.dump(dict(split=split, cfg=cfgname, rows=res), open(outf, 'w')); print(len(res), 'instances', round(time.time() - t0), 's ->', outf)
