"""Does a baseline-sequence serial scheduler with renewable-resource limits reproduce the baseline starts of real DSLIB plans?
Continuous working-day time; demands parsed from 'Name[d #avail]' or bare names (demand 1)."""
import re, json, sys, datetime as dt, openpyxl, glob
sys.path.insert(0, '.')
from dslib_replay import *
def parse_dem(s):
    out = {}
    if not s: return out
    for tok in str(s).split(';'):
        tok = tok.strip()
        if not tok: continue
        m = re.match(r'^(.*?)\[\s*([\d.]+)\s*(?:#\s*[\d.]+)?\s*\]$', tok)
        if m: out[m.group(1).strip()] = float(m.group(2))
        else: out[tok] = 1.0
    return out
def check(code):
    f = glob.glob(BASE + 'Excel/' + code + '*.xlsx')[0]
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    cal = Cal(list(wb['Agenda'].iter_rows(values_only=True)))
    res = {}
    for x in list(wb['Resources'].iter_rows(values_only=True))[2:]:
        if x[0] is None or not x[1]: continue
        if str(x[2]).lower().startswith('renew'):
            try: res[str(x[1]).strip()] = float(str(x[3]).strip())
            except: pass
    b = list(wb['Baseline Schedule'].iter_rows(values_only=True))
    h = next(i for i, x in enumerate(b) if x and x[0] == 'ID'); col = {k: j for j, k in enumerate(b[h]) if k}
    tasks = [x for x in b[h + 1:] if x[0] is not None]
    wbs = {int(x[col['ID']]): str(x[col['WBS']]) for x in tasks}; ws = set(wbs.values())
    leaf = [i for i in wbs if not any(o.startswith(wbs[i] + '.') for o in ws)]
    T = {}
    for x in tasks:
        i = int(x[col['ID']])
        if i in leaf:
            p = parse_preds(x[col['Predecessors']])
            if p is None: return dict(code=code, status='predparse')
            T[i] = dict(s=cal.wd(x[col['Baseline Start']]), e=cal.wd(x[col['Baseline End']]), dem=parse_dem(x[col['Resource Demand']]), preds=[q for q in p if q[0] in leaf])
    for i in T: T[i]['d'] = T[i]['e'] - T[i]['s']; T[i]['dem'] = {k: v for k, v in T[i]['dem'].items() if k in res}
    order = sorted(T, key=lambda i: (T[i]['s'], i))    # baseline sequence
    st = {}; fi = {}; usage = []                       # usage: (s,e,{res:amt})
    t0 = min(T[i]['s'] for i in T)
    def ok(s, e, dem):
        pts = sorted({s} | {u[0] for u in usage if s < u[0] < e})
        for p in pts:
            for r, a in dem.items():
                if a + sum(u[2].get(r, 0) for u in usage if u[0] <= p < u[1]) > res[r] + 1e-9: return False
        return True
    for i in order:
        r0 = t0
        for (p, t, l) in T[i]['preds']:
            if p not in st: continue
            if t == 'FS': r0 = max(r0, fi[p] + l)
            elif t == 'SS': r0 = max(r0, st[p] + l)
            elif t == 'FF': r0 = max(r0, fi[p] + l - T[i]['d'])
            elif t == 'SF': r0 = max(r0, st[p] + l - T[i]['d'])
        d = T[i]['d']; dem = T[i]['dem']
        if any(a > res[r] + 1e-9 for r, a in dem.items()): dem = {r: min(a, res[r]) for r, a in dem.items()}
        cands = sorted({r0} | {u[1] for u in usage if u[1] > r0})
        s = next(c for c in cands if ok(c, c + d, dem))
        st[i] = s; fi[i] = s + d; usage.append((s, s + d, dem))
    n = len(T)
    exact = sum(1 for i in T if abs(st[i] - T[i]['s']) < 0.05) / n
    late = sum(1 for i in T if st[i] > T[i]['s'] + 0.05) / n
    early = sum(1 for i in T if st[i] < T[i]['s'] - 0.05) / n
    mk_b = max(T[i]['e'] for i in T) - t0; mk_r = max(fi.values()) - t0
    # logic-only (no resources) for comparison
    return dict(code=code, status='ok', n=n, n_res=len(res), exact=exact, sched_later=late, sched_earlier=early, plan_finish=mk_b, replay_finish=mk_r,
                n_with_dem=sum(1 for i in T if T[i]['dem']))
if __name__ == '__main__':
    out = []
    for c in ['C2011-10', 'C2011-12', 'C2012-13', 'C2012-17', 'C2015-27', 'C2018-10', 'C2025-10']:
        try: r = check(c)
        except Exception as e: r = dict(code=c, status='err:' + repr(e)[:100])
        print(r, flush=True); out.append(r)
    json.dump(out, open('dslib_resource_check.json', 'w'))
