"""DSLIB real-schedule replay with calendars and actual dates (exploratory, protocol amendment A4).
Two-class Shapley decomposition of observed project delay into
  D = activity duration deviations (what logic-only CPM can see)
  W = start waits beyond the logic-ready time (gaps CPM cannot see)
All times in working days of the project's own calendar (Agenda sheet)."""
import openpyxl, glob, re, json, sys, datetime as dt, collections, math
import numpy as np
BASE = '/tmp/claude-0/real/dslib/DSLIB 3.4/'

def dur(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    s = str(s).strip()
    w = re.search(r'(-?\d+(?:\.\d+)?)\s*w', s); d = re.search(r'(-?\d+(?:\.\d+)?)\s*d', s); h = re.search(r'(-?\d+(?:\.\d+)?)\s*h', s)
    if not d and not h and not w:
        try: return float(s)
        except: return None
    return (float(w.group(1)) * 5 if w else 0) + (float(d.group(1)) if d else 0) + (float(h.group(1)) / 8 if h else 0)

pred_pat = re.compile(r'^\s*(\d+)\s*(FS|SS|FF|SF)?\s*([+-]\s*(?:[\d.]+\s*[wdh]?\s*)+)?\s*$')
def parse_preds(s):
    out = []
    if s is None: return out
    for tok in str(s).split(';'):
        tok = tok.strip()
        if not tok: continue
        m = pred_pat.match(tok)
        if not m: return None
        lag = 0.0
        if m.group(3):
            g = m.group(3).replace(' ', ''); sign = -1.0 if g[0] == '-' else 1.0
            lag = sign * sum(dur(p) or 0.0 for p in re.findall(r'[\d.]+[wdh]?', g[1:]))
        out.append((int(m.group(1)), m.group(2) or 'FS', lag))
    return out

class Cal:
    def __init__(self, agenda_rows):
        self.hours = [False] * 24; self.days = [False] * 7; self.hol = set()
        names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i, r in enumerate(agenda_rows[1:]):
            if r[0] and re.match(r'^\d+:00 - ', str(r[0])):
                h = int(str(r[0]).split(':')[0])
                if h < 24: self.hours[h] = (str(r[1]).strip().lower() == 'yes')
            if r[3] in names: self.days[names.index(r[3])] = (str(r[4]).strip().lower() == 'yes')
            if len(r) > 6 and isinstance(r[6], (dt.datetime, dt.date)):
                self.hol.add((r[6].date() if isinstance(r[6], dt.datetime) else r[6]).toordinal())
        self.H = sum(self.hours) or 8
        self.cache = {}
    def isw(self, o):
        return self.days[(o - 1) % 7 if False else dt.date.fromordinal(o).weekday()] and o not in self.hol
    def cumdays(self, o):  # working days strictly before ordinal o, from fixed origin
        base = 730000
        if o in self.cache: return self.cache[o]
        # incremental from nearest cached
        lo = max([k for k in self.cache if k <= o], default=None)
        if lo is None: lo, v = base, 0
        else: v = self.cache[lo]
        for k in range(lo, o):
            if self.isw(k): v += 1
            self.cache[k + 1] = v
        self.cache[o] = v; return v
    def wd(self, t):
        o = t.toordinal(); v = self.cumdays(o)
        if self.isw(o):
            frac = t.hour + t.minute / 60.0
            done = sum(1.0 if h + 1 <= frac else max(0.0, frac - h) for h in range(24) if self.hours[h] and h < frac)
            v += done / self.H
        return float(v)

def load(code):
    f = glob.glob(BASE + 'Excel/' + code + '*.xlsx')[0]
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    cal = Cal(list(wb['Agenda'].iter_rows(values_only=True)))
    bs = list(wb['Baseline Schedule'].iter_rows(values_only=True))
    hi = next(i for i, x in enumerate(bs) if x and x[0] == 'ID'); H = bs[hi]; col = {h: j for j, h in enumerate(H) if h}
    tasks = [x for x in bs[hi + 1:] if x[0] is not None]
    wbs = {int(x[col['ID']]): str(x[col['WBS']]) for x in tasks}; wset = set(wbs.values())
    leaf = [i for i in wbs if not any(o.startswith(wbs[i] + '.') for o in wset)]
    B = {}
    for x in tasks:
        i = int(x[col['ID']])
        if i in leaf:
            B[i] = dict(s=x[col['Baseline Start']], e=x[col['Baseline End']], d=dur(x[col['Duration']]),
                        preds=parse_preds(x[col['Predecessors']]), wbs=wbs[i])
    root = [x for x in tasks if wbs[int(x[col['ID']])] == '1']
    rootb = (root[0][col['Baseline Start']], root[0][col['Baseline End']], dur(root[0][col['Duration']])) if root else None
    tps = [n for n in wb.sheetnames if re.match(r'^(Project Control - )?TP\d+$', n)]
    if not tps: return None
    last = list(wb[tps[-1]].iter_rows(values_only=True))
    hi = next(i for i, x in enumerate(last) if x and x[0] == 'ID'); LH = last[hi]; lc = {h: j for j, h in enumerate(LH) if h}
    A = {}; rootact = None
    for x in last[hi + 1:]:
        if x[0] is None: continue
        i = int(x[0]); ad = dur(x[lc['Actual Duration']]) if 'Actual Duration' in lc else None
        if i == 0 or (i not in leaf and wbs.get(i) == '1'): rootact = ad
        if i in leaf: A[i] = dict(s=x[lc['Actual Start']], d=ad, rem=dur(x[lc['Remaining Duration']]), tr=x[lc['Tracking']] if 'Tracking' in lc else None)
    return cal, B, A, rootb, rootact, len(tps)

def replay(code):
    L = load(code)
    if L is None: return dict(code=code, status='notp')
    cal, B, A, rootb, rootact, ntp = L
    ids = list(B)
    if any(B[i]['preds'] is None for i in ids): return dict(code=code, status='predparse')
    for i in ids: B[i]['preds'] = [(p, t, l) for (p, t, l) in B[i]['preds'] if p in B]
    for i in ids:
        a = A.get(i)
        if a is None or not isinstance(a['s'], dt.datetime) or a['d'] is None or (a['rem'] not in (None, 0, 0.0)):
            return dict(code=code, status='incomplete_actuals', n_leaf=len(ids))
    # topological order
    order = []; seen = set(); tmp = set()
    sys.setrecursionlimit(20000)
    def visit(i):
        if i in seen: return True
        if i in tmp: return False
        tmp.add(i)
        for (p, t, l) in B[i]['preds']:
            if not visit(p): return False
        tmp.discard(i); seen.add(i); order.append(i); return True
    for i in ids:
        if not visit(i): return dict(code=code, status='cycle')
    bs = {i: cal.wd(B[i]['s']) for i in ids}; be = {i: cal.wd(B[i]['e']) for i in ids}
    bd = {i: be[i] - bs[i] for i in ids}                     # baseline duration in calendar working time
    ad = {i: A[i]['d'] for i in ids}; as_ = {i: cal.wd(A[i]['s']) for i in ids}
    t0 = min(bs.values())
    def ready(i, st, fi, d_i):
        r = t0
        for (p, t, l) in B[i]['preds']:
            if t == 'FS': r = max(r, fi[p] + l)
            elif t == 'SS': r = max(r, st[p] + l)
            elif t == 'FF': r = max(r, fi[p] + l - d_i)
            elif t == 'SF': r = max(r, st[p] + l - d_i)
        return r
    # waits implied by the data
    fb = {i: bs[i] + bd[i] for i in ids}; fa = {i: as_[i] + ad[i] for i in ids}
    wb_ = {i: bs[i] - ready(i, bs, fb, bd[i]) for i in ids}
    wa_ = {i: as_[i] - ready(i, as_, fa, ad[i]) for i in ids}
    def run(dd, ww):
        st = {}; fi = {}
        for i in order:
            st[i] = ready(i, st, fi, dd[i]) + ww[i]; fi[i] = st[i] + dd[i]
        return max(fi.values()) - t0
    v0 = run(bd, wb_); vD = run(ad, wb_); vW = run(bd, wa_); vDW = run(ad, wa_)
    phiD = 0.5 * ((vD - v0) + (vDW - vW)); phiW = 0.5 * ((vW - v0) + (vDW - vD))
    # diagnostics
    n = len(ids)
    zero_b = sum(1 for i in ids if abs(wb_[i]) < 1e-6) / n          # baseline starts exactly at logic-ready time
    neg_b = sum(1 for i in ids if wb_[i] < -1e-6) / n
    zero_a = sum(1 for i in ids if abs(wa_[i]) < 1e-6) / n
    # activity-level contributions (additive proxy): total wait days > baseline wait, positive only
    ex_wait = sum(max(0.0, wa_[i] - wb_[i]) for i in ids); ex_dur = sum(max(0.0, ad[i] - bd[i]) for i in ids)
    root_b = (cal.wd(rootb[1]) - cal.wd(rootb[0])) if rootb and isinstance(rootb[0], dt.datetime) else None
    return dict(code=code, status='ok', n_leaf=n, H=cal.H, plan_replay=v0, act_replay=vDW, root_plan=root_b, root_plan_str=(rootb[2] if rootb else None),
                root_act=rootact, vD=vD, vW=vW, phiD=phiD, phiW=phiW, zero_b=zero_b, neg_b=neg_b, zero_a=zero_a,
                ex_wait=ex_wait, ex_dur=ex_dur, ntp=ntp)

if __name__ == '__main__':
    ar = openpyxl.load_workbook(BASE + 'DSLIB_Analysis_Sheet.xlsx', read_only=True, data_only=True)
    rows = list(ar['DSLIB'].iter_rows(values_only=True))
    data = [r for r in rows[3:] if r[0] and str(r[0]).startswith('C')]
    cons = [r for r in data if r[3] and str(r[3]).lower().startswith('construction')]
    only = sys.argv[1:] 
    out = []
    for r in cons:
        if only and r[0] not in only: continue
        try: x = replay(r[0])
        except Exception as e: x = dict(code=r[0], status='err:' + repr(e)[:80])
        x.update(name=r[1], sector=r[3], auth_static=r[8], auth_track=r[9], res=r[13], early_late=r[17], pd=r[11])
        out.append(x)
        print(r[0], x['status'], ({k: round(v, 1) if isinstance(v, float) else v for k, v in x.items() if k in ('n_leaf', 'plan_replay', 'root_plan', 'act_replay', 'root_act', 'phiD', 'phiW', 'zero_b')} if x['status'] == 'ok' else ''), flush=True)
    json.dump(out, open('dslib_replay_out.json', 'w'), default=str)
    print(collections.Counter(x['status'] for x in out))
