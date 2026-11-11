"""Engine for the attribution-vs-mitigation experiments (PROTOCOL.md v1).
Fixed-commitment, baseline-sequence serial scheduler with no overtaking, numba-compiled.  Events, Shapley attribution, decision-epoch fixes, policies, evidence regimes."""
import os, sys, math, json, random, itertools, hashlib, tarfile, functools
import numpy as np, numba as nb

HERE = os.path.dirname(os.path.abspath(__file__))
TAR = '/tmp/claude-0/real/rcplib/ALL/ALL.tar'
XLS = '/tmp/claude-0/real/rcplib/RCPLIB (Parameters and BKS).xlsx'
NYC = json.load(open(os.path.join(HERE, 'nyc_leads.json')))
BIN_WEEKS = (0.5, 2.6, 8.6, 19.3, 38.9, 64.0)
PROJ_WEEKS = (26.0, 52.0, 104.0)
def nyc_masses(cls):
    k = {'routine': 'Alteration', 'major': 'New Building'}[cls]; a = NYC['approved'][k]; c = NYC['cum_counts'][k]
    pts = [0] + [c[x] for x in ('7', '30', '90', '180', '365')] + [a]
    return [(pts[i + 1] - pts[i]) / a for i in range(6)]

# ---------------------------------------------------------------- instances
def parse_rcp(txt):
    t = list(map(int, txt.split())); n, R = t[0], t[1]; cap = np.array(t[2:2 + R], dtype=np.int32); p = 2 + R
    dur = np.zeros(n, dtype=np.int64); dem = np.zeros((n, R), dtype=np.int32); succ = []
    for j in range(n):
        dur[j] = t[p]; dem[j] = t[p + 1:p + 1 + R]; ns = t[p + 1 + R]; succ.append([x - 1 for x in t[p + 2 + R:p + 2 + R + ns]]); p += 2 + R + ns
    pred = [[] for _ in range(n)]
    for j in range(n):
        for s in succ[j]: pred[s].append(j)
    ptr = np.zeros(n + 1, dtype=np.int64); idx = []
    for j in range(n): ptr[j + 1] = ptr[j] + len(pred[j]); idx += pred[j]
    assert all(s > j for j in range(n) for s in succ[j]), 'not topologically numbered'
    return dict(n=n, R=R, cap=cap, dur=dur, dem=dem, succ=succ, pred=pred, pptr=ptr, pidx=np.array(idx, dtype=np.int64))

_tf = {}
def load(name):
    if os.getpid() not in _tf: _tf[os.getpid()] = tarfile.open(TAR)
    return parse_rcp(_tf[os.getpid()].extractfile('original/' + name).read().decode())

def pool():
    import openpyxl
    ws = openpyxl.load_workbook(XLS, read_only=True)['All']; it = ws.iter_rows(values_only=True); h = list(next(it)); out = []
    for r in it:
        if r[0] is None or r[5] not in (30, 60, 90, 120): continue
        set_ = r[2]; nm = f'{r[2] if set_ == "sD" else r[3]}_{r[1]}.rcp'; out.append(dict(name=nm, nact=r[5], RS=r[26], set=set_))
    return out
def split_of(name): return 'dev' if hashlib.sha256(name.encode()).digest()[0] % 2 == 0 else 'held'

# ---------------------------------------------------------------- scheduler
@nb.njit(cache=True)
def sched(order, dur, ext, rel, dem, prof, pptr, pidx, pin, pst, pdu, out_st, out_fi):
    n = len(dur); R = dem.shape[1]; H = prof.shape[1]; use = np.zeros((R, H), dtype=np.int32); prev = 0; mk = 0
    for q in range(len(order)):
        j = order[q]
        if pin[j]:
            s = pst[j]; d = pdu[j]
        else:
            d = dur[j] + ext[j]; s = rel[j]
            if prev > s: s = prev
            for k in range(pptr[j], pptr[j + 1]):
                f = out_fi[pidx[k]]
                if f > s: s = f
            if d > 0:
                while True:
                    ok = True; bad = -1
                    for r in range(R):
                        dm = dem[j, r]
                        if dm == 0: continue
                        for u in range(s, s + d):
                            if use[r, u] + dm > prof[r, u]:
                                ok = False; bad = u; break
                        if not ok: break
                    if ok: break
                    s = bad + 1
        if d > 0:
            for r in range(R):
                dm = dem[j, r]
                if dm != 0:
                    for u in range(s, s + d): use[r, u] += dm
        out_st[j] = s; out_fi[j] = s + d
        if s > prev: prev = s
        if s + d > mk: mk = s + d
    return mk

class Inst:
    def __init__(self, name):
        self.name = name; d = load(name); self.__dict__.update(d); n = self.n
        # precedence-only critical path
        est = np.zeros(n, dtype=np.int64)
        for j in range(n):
            for s in self.succ[j]: est[s] = max(est[s], est[j] + self.dur[j])
        T = est[n - 1]; lft = np.full(n, T, dtype=np.int64)
        for j in range(n - 1, -1, -1):
            for s in self.succ[j]: lft[j] = min(lft[j], lft[s] - self.dur[s])
        self.est, self.lft, self.T_cpm = est, lft, T; self.slack = lft - est - self.dur
        self.order = np.array(sorted(range(n), key=lambda j: (lft[j], j)), dtype=np.int64)
        self.st = np.zeros(n, dtype=np.int64); self.fi = np.zeros(n, dtype=np.int64)
        self.zero_ext = np.zeros(n, dtype=np.int64); self.zero_rel = np.zeros(n, dtype=np.int64)
        self.nopin = np.zeros(n, dtype=np.bool_); self.zst = np.zeros(n, dtype=np.int64)
        H = int(self.dur.sum()) + 8
        self.M0 = self.run(self.zero_rel, self.zero_ext, [], None)
        self.S0 = self.st.copy()
        self.crit = {j for j in range(1, n - 1) if self.dur[j] > 0 and self.slack[j] == 0}
        self.real = [j for j in range(1, n - 1) if self.dur[j] > 0]
    def run(self, rel, ext, cuts, pin):
        H = int(self.dur.sum() + ext.sum() + rel.max() + (max([b for (_, _, b) in cuts]) if cuts else 0) + 16)
        if pin is not None: H = max(H, int(pin[1].max() + pin[2].max()) + 16 + int(self.dur.sum() + ext.sum()))
        prof = np.tile(self.cap[:, None], (1, H)).astype(np.int32)
        for (r, a, b) in cuts:
            if self.cap[r] > 0: prof[r, a:min(b, H)] = np.maximum(prof[r, a:min(b, H)] - 1, 0)
        if pin is None: pm, ps, pd = self.nopin, self.zst, self.zst
        else: pm, ps, pd = pin
        fi = np.zeros(self.n, dtype=np.int64); st = np.zeros(self.n, dtype=np.int64)
        mk = sched(self.order, self.dur, ext, rel, self.dem, prof, self.pptr, self.pidx, pm, ps, pd, st, fi)
        self.st, self.fi = st, fi
        return int(mk)

# ---------------------------------------------------------------- events
TYPES = {'primary': [('design_hold', 'employer', .18), ('site_access', 'employer', .09), ('approval_wait', 'authority', .18), ('supply_delay', 'contractor', .10), ('productivity', 'contractor', .13), ('rework', 'contractor', .09), ('labour', 'contractor', .13), ('weather', 'neutral', .10)],
         'owner': [('design_hold', 'employer', .25), ('site_access', 'employer', .15), ('approval_wait', 'authority', .25), ('supply_delay', 'contractor', .05), ('productivity', 'contractor', .07), ('rework', 'contractor', .04), ('labour', 'contractor', .06), ('weather', 'neutral', .13)],
         'contractor': [('design_hold', 'employer', .08), ('site_access', 'employer', .04), ('approval_wait', 'authority', .08), ('supply_delay', 'contractor', .16), ('productivity', 'contractor', .22), ('rework', 'contractor', .14), ('labour', 'contractor', .18), ('weather', 'neutral', .10)]}
OWNER_OF = {t: o for t, o, _ in TYPES['primary']}
# survey weights: sum of Pereira et al. 2024 ICG of mapped causes (Appendix A, Table A1); site_access has no top-20 cause -> small floor
SURVEY_W = {'design_hold': 9.25 + 5.44 + 3.08 + 1.68 + 0.92, 'approval_wait': 1.59 + 1.03, 'supply_delay': 1.91, 'productivity': 1.97 + 2.92, 'rework': 2.46,
            'labour': 1.97 + 3.35, 'site_access': 0.5, 'weather': 1.81}

def gen_event(inst, rng, i, mix='primary', scale=1.0, force_type=None):
    n, d, S0, M0 = inst.n, inst.dur, inst.S0, inst.M0; real = inst.real; early = [j for j in real if S0[j] <= 0.8 * M0] or real
    wk = rng.choice(PROJ_WEEKS); uw = wk / M0; masses = nyc_masses(rng.choice(['routine', 'major'])); L0 = max(1, round(0.05 * M0))
    if force_type: ty = force_type; ow = OWNER_OF[ty]
    else:
        r = rng.random(); acc = 0
        for ty, ow, p in TYPES[mix]:
            acc += p
            if r <= acc: break
    if ty == 'labour' and not [r for r in range(inst.R) if inst.cap[r] >= 2]: ty = 'productivity'; ow = 'contractor'
    e = dict(id=i, type=ty, owner=ow, job=None, release=0, amount=0, jobs=None, res=None, a=0, b=0)
    if ty in ('design_hold', 'site_access', 'supply_delay'):
        j = rng.choice(early); h = max(1, round(scale * (rng.uniform(.04, .15) if ty == 'design_hold' else rng.uniform(.02, .08)) * M0)); e.update(job=j, release=int(S0[j] + h), size=h)
    elif ty == 'approval_wait':
        j = rng.choice(early); weeks = rng.choices(BIN_WEEKS, weights=masses)[0]; h = min(round(0.35 * M0), max(1, math.ceil(scale * weeks / uw))); f = max(0, int(S0[j]) - L0)
        e.update(job=j, release=int(f + h), size=max(1, f + h - int(S0[j])))
    elif ty in ('productivity', 'rework'):
        j = rng.choice(early); a = max(1, math.ceil(scale * (rng.uniform(.3, 1.0) if ty == 'productivity' else rng.uniform(.5, 1.5)) * d[j])); e.update(job=j, amount=int(a), size=int(a))
    elif ty == 'labour':
        rs = [r for r in range(inst.R) if inst.cap[r] >= 2]; a0 = round(rng.uniform(0, .6) * M0); w = max(1, round(scale * rng.uniform(.1, .25) * M0)); e.update(res=rng.choice(rs), a=int(a0), b=int(a0 + w), size=int(w))
    else:
        a0 = round(rng.uniform(0, .6) * M0); w = max(1, round(rng.uniform(.05, .12) * M0)); fr = min(1.0, rng.uniform(.3, .6) * scale)
        jobs = [(j, math.ceil(fr * d[j])) for j in real if a0 <= S0[j] < a0 + w]; e.update(a=int(a0), b=int(a0 + w), jobs=jobs, size=max(1, sum(x for _, x in jobs)))
    e['when'] = int(S0[e['job']]) if e['job'] is not None else int(e['a'])
    return e

def compile_events(inst, evs):
    n = inst.n; K = len(evs); REL = np.zeros((K, n), dtype=np.int64); EXT = np.zeros((K, n), dtype=np.int64); CUT = [None] * K
    for k, e in enumerate(evs):
        t = e['type']
        if t in ('design_hold', 'site_access', 'supply_delay', 'approval_wait'): REL[k, e['job']] = e['release']
        elif t in ('productivity', 'rework'): EXT[k, e['job']] = e['amount']
        elif t == 'labour': CUT[k] = (e['res'], e['a'], e['b'])
        else:
            for j, a in e['jobs']: EXT[k, j] += a
    return REL, EXT, CUT

class Model:
    """Makespan oracle for a set of (true or observed) events, optional pinned commitments and fixes."""
    def __init__(self, inst, evs, pin=None, fixinfo=None):
        self.inst, self.evs, self.pin = inst, evs, pin; self.K = len(evs); self.REL, self.EXT, self.CUT = compile_events(inst, evs); self.cache = {}
        self.fix = fixinfo  # dict(Sall, t, lead[k]) -> fixed variants computed lazily
    def _arrays(self, inc, fixmask):
        K = self.K; rel = self.inst.zero_rel.copy(); ext = self.inst.zero_ext.copy(); cuts = []
        for k in range(K):
            if not (inc >> k & 1): continue
            REL, EXT, CUT = self.REL[k], self.EXT[k], self.CUT[k]
            if fixmask >> k & 1:
                Sall, t, lead = self.fix['Sall'], self.fix['t'], self.fix['lead'][k]; ok = Sall >= t + lead; phi = self.fix['phi'][k] if 'phi' in self.fix else 1.0
                if self.evs[k]['type'] == 'weather': pass
                elif CUT is not None:
                    a, b = CUT[1], CUT[2]; sr = max(a, int(t + lead))
                    if sr < b:
                        b2 = b - int(round(phi * (b - sr))); CUT = None if b2 <= a else (CUT[0], a, b2)
                elif REL.any():
                    if phi >= 1.0: REL = np.where(ok, 0, REL)
                    else: S0 = self.inst.S0; REL = np.where(ok & (REL > S0), S0 + np.round((1 - phi) * (REL - S0)).astype(np.int64), REL)
                else:
                    if phi >= 1.0: EXT = np.where(ok, 0, EXT)
                    else: EXT = np.where(ok, np.ceil((1 - phi) * EXT).astype(np.int64), EXT)
            rel = np.maximum(rel, REL); ext = ext + EXT
            if CUT is not None: cuts.append(CUT)
        return rel, ext, cuts
    def M(self, inc, fixmask=0):
        key = (inc, fixmask)
        if key not in self.cache:
            rel, ext, cuts = self._arrays(inc, fixmask); self.cache[key] = self.inst.run(rel, ext, cuts, self.pin)
        return self.cache[key]
    def realised(self, inc):
        rel, ext, cuts = self._arrays(inc, 0); m = self.inst.run(rel, ext, cuts, self.pin); return m, self.inst.st.copy(), self.inst.fi.copy()

def shapley(Mfun, members):
    m = len(members); sh = {i: 0.0 for i in members}; f = math.factorial
    for i in members:
        rest = [x for x in members if x != i]
        for r in range(m):
            w = f(r) * f(m - r - 1) / f(m)
            for sub in itertools.combinations(rest, r):
                mask = sum(1 << x for x in sub); sh[i] += w * (Mfun(mask | 1 << i) - Mfun(mask))
    return sh
