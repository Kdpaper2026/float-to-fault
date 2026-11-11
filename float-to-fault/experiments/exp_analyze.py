"""Analysis of experiment outputs (PROTOCOL.md v1).  python3 -I exp_analyze.py <result.json> [more result.json ...]"""
import sys, json, math, collections, itertools
import numpy as np
rng = np.random.default_rng(20261028)
def boot(x, B=2000):
    x = np.asarray(x, float)
    if len(x) == 0: return (float('nan'),) * 3
    idx = rng.integers(0, len(x), (B, len(x))); m = x[idx].mean(1); return x.mean(), np.percentile(m, 2.5), np.percentile(m, 97.5)
def f(t, d=3): return '%.*f [%.*f, %.*f]' % (d, t[0], d, t[1], d, t[2])
P = print
POL = ['P1 frequency', 'P2 Shapley', 'P3 direct greedy', 'P4 exact (model)']

def e1(rows):
    ok = [r for r in rows if 'shapley' in r]; P(f'\n== E1 attribution ({len(ok)} instances with delay; {len(rows) - len(ok)} without delay) ==')
    P('monotone in all masks:', sum(1 for r in ok if r['mono']), 'of', len(ok))
    D = sum(r['D'] for r in ok); zero = sum(sum(s for s, c in zip(r['shapley'], r['cpm']) if c == 0) for r in ok) / D; claim = sum(sum(r['cpm']) for r in ok) / D
    ghost = sum(sum(c for s, c in zip(r['shapley'], r['cpm']) if s < 1e-9) for r in ok) / max(1e-9, sum(sum(r['cpm']) for r in ok))
    P('CPM zero-share (pooled; Shapley days in events CPM scores 0 / total delay): %.3f' % zero); P('CPM claim ratio (pooled; days CPM claims / total delay): %.3f' % claim); P('share of CPM-claimed days on events with zero effect: %.3f' % ghost)
    nocrit = np.mean([sum(r['cpm']) == 0 for r in ok]); P('instances where CPM scores no event at all: %.3f' % nocrit)
    P('D/M0 mean %.3f  median %.3f' % (np.mean([r['D'] / r['M0'] for r in ok]), np.median([r['D'] / r['M0'] for r in ok])))
    P('fix-first efficiency (retrospective, full information; delay removed by top-k / best k-set), mean [95% CI]')
    for k in ('1', '2', '3'):
        for m in ('shapley', 'butfor', 'alone', 'windows', 'cpm'):
            v = [r['sets'][k][m] / r['sets'][k]['opt'] for r in ok if r['sets'][k]['opt'] > 0]; P(f'  k={k} {m:8s} {f(boot(v))}')
    P('summed but-for / D: %.3f   summed alone / D: %.3f' % (np.mean([sum(r['butfor']) / r['D'] for r in ok]), np.mean([sum(r['alone']) / r['D'] for r in ok])))
    led = [r['ledger'] for r in ok]; P('ledger: instances with a weather event %.3f; mean fixed-event reference share of total lateness (full-planned): %.3f' % (np.mean([l['n_weather'] > 0 for l in led]), sum(l['fixed_ref'] - l['planned'] for l in led) / sum(l['full'] - l['planned'] for l in led)))
    P('ledger identity |sum Shapley - (full - fixed_ref)| max: %.2e' % max(abs(l['shap_sum'] - l['attributed']) for l in led))
    st = collections.Counter(); tot = collections.Counter()
    for r in ok:
        for p, v in r['share_true'].items(): tot[p] += v
    P('mean true Shapley share by party:', {p: round(v / len(ok), 3) for p, v in tot.items()})

def e3(rows):
    ok = [r for r in rows if 'stab' in r]; P(f'\n== E3 attribution stability under evidence regimes ({len(ok)} instances) ==')
    for rg in ('b', 'c', 'd'):
        s = [r['stab'][rg] for r in ok if rg in r['stab'] and 'err_empauth' in r['stab'][rg]]
        if not s: continue
        P(f'regime {rg}: n={len(s)}  events observed {np.mean([x["n_obs"] for x in s]):.1f}  phantoms {np.mean([x["n_phantom"] for x in s]):.2f}  delay explained (D_obs/D) {np.mean([x["share_explained"] for x in s]):.3f}')
        P('   error in owner+authority share (abs):', f(boot([x['err_empauth'] for x in s])), '  leading party changes:', f(boot([float(x['lead_changed']) for x in s])))

def e2(rows, key_filter=None):
    ok = [r for r in rows if 'e2' in r]; P(f'\n== E2 prospective mitigation ({len(ok)} instances) ==')
    def cap(key, idx_pol, need_pos=True):
        out = []
        for r in ok:
            v = r['e2'].get(key)
            if v is None or v[0] <= 0: continue
            out.append(v[idx_pol] / v[0])
        return out
    prim = '0.5|0.1|0.5|0.5|'
    for rg in ('a', 'b', 'c', 'd'):
        key = prim + rg; vs = [r['e2'][key] for r in ok if key in r['e2'] and r['e2'][key][0] > 0]
        if not vs: continue
        P(f'\n-- primary configuration, evidence regime {rg} (tau 0.5, L_auth 0.10, sigma 0.5, beta 0.5); instances with recoverable delay: {len(vs)} of {len(ok)}')
        for i, nm in enumerate(POL, start=1): P(f'  capture {nm:18s} {f(boot([v[i] / v[0] for v in vs]))}   regret days {f(boot([v[0] - v[i] for v in vs]), 2)}')
        for i, nm in ((9, 'P2b Shapley/cost'), (10, 'P2e epoch Shapley'), (11, 'P2eb epoch Shapley/cost')):
            if all(len(v) > i for v in vs): P(f'  capture {nm:24s} {f(boot([v[i] / v[0] for v in vs]))}   regret days {f(boot([v[0] - v[i] for v in vs]), 2)}   >=99% of oracle: {np.mean([v[i] / v[0] >= 0.99 for v in vs]):.3f}')
        if all(len(v) > 10 for v in vs): P('  paired: P2e-P2 capture %s | P3-P2e %s | P4-P2e %s' % (f(boot([(v[10] - v[2]) / v[0] for v in vs])), f(boot([(v[3] - v[10]) / v[0] for v in vs])), f(boot([(v[4] - v[10]) / v[0] for v in vs]))))
        P('  paired: P3-P2 capture %s | P4-P2 %s | P2-P1 %s' % (f(boot([(v[3] - v[2]) / v[0] for v in vs])), f(boot([(v[4] - v[2]) / v[0] for v in vs])), f(boot([(v[2] - v[1]) / v[0] for v in vs]))))
        P('  P2 chooses the same fix set as P4: %s ; same first fix: %s ; P2 captures >= 99%% of oracle: %.3f' % (f(boot([float(v[5]) for v in vs])), f(boot([float(v[6]) for v in vs])), np.mean([v[2] / v[0] >= 0.99 for v in vs])))
    P('\n-- one-factor sensitivity (regime a, other factors at primary), capture of P2 Shapley / P3 greedy / P1 frequency and gap P4-P2')
    grid = collections.defaultdict(list)
    for r in ok:
        for k, v in r['e2'].items():
            tau, L, sg, bt, rg = k.split('|')
            if rg == 'a' and v[0] > 0: grid[(tau, L, sg, bt)].append(v)
    dims = {'tau': 0, 'L_auth': 1, 'sigma': 2, 'beta': 3}; base = ('0.5', '0.1', '0.5', '0.5')
    for dn, di in dims.items():
        for k in sorted({g[di] for g in grid}, key=float):
            g = list(base); g[di] = k; vs = grid[tuple(g)]
            if not vs: continue
            P(f'  {dn}={k:5s} n={len(vs):4d}  P1 {np.mean([v[1] / v[0] for v in vs]):.3f}  P2 {np.mean([v[2] / v[0] for v in vs]):.3f}  P3 {np.mean([v[3] / v[0] for v in vs]):.3f}  P4 {np.mean([v[4] / v[0] for v in vs]):.3f}  P2e {np.mean([v[10] / v[0] for v in vs]) if all(len(x) > 10 for x in vs) else float("nan"):.3f}  P2 same-set-as-P4 {np.mean([v[5] for v in vs]):.3f}')
    P('\n-- by instance characteristics (primary, regime a)')
    key = prim + 'a'
    def grp(sel, nm):
        vs = [r['e2'][key] for r in ok if key in r['e2'] and r['e2'][key][0] > 0 and sel(r)]
        if vs: P(f'  {nm:28s} n={len(vs):4d}  P1 {np.mean([v[1] / v[0] for v in vs]):.3f}  P2 {np.mean([v[2] / v[0] for v in vs]):.3f}  P3 {np.mean([v[3] / v[0] for v in vs]):.3f}  gap(P4-P2) {np.mean([(v[4] - v[2]) / v[0] for v in vs]):.3f}  agree {np.mean([v[5] for v in vs]):.3f}')
    for na in (30, 60, 90, 120): grp(lambda r, na=na: r['nact'] == na, f'activities = {na}')
    rs = [r['RS'] for r in ok if r.get('RS') is not None]
    if rs:
        q = np.quantile(rs, [1 / 3, 2 / 3])
        grp(lambda r: r.get('RS') is not None and r['RS'] <= q[0], 'resource strength: low third'); grp(lambda r: r.get('RS') is not None and q[0] < r['RS'] <= q[1], 'resource strength: middle third'); grp(lambda r: r.get('RS') is not None and r['RS'] > q[1], 'resource strength: high third')
    auth = lambda r: sum(s for s, t in zip(r['shapley'], r['type']) if t == 'approval_wait') / r['D']
    grp(lambda r: auth(r) == 0, 'no authority event'); grp(lambda r: 0 < auth(r) <= 0.25, 'authority share <= 25%'); grp(lambda r: auth(r) > 0.25, 'authority share > 25%')
    ot = lambda r: sum(1 for t in r['type'] if t == 'weather')
    grp(lambda r: r['D'] / r['M0'] < 0.1, 'delay < 10% of baseline'); grp(lambda r: r['D'] / r['M0'] >= 0.1, 'delay >= 10% of baseline')

def hyp(rows, split):
    ok = [r for r in rows if 'shapley' in r]; P(f'\n== Pre-specified hypothesis readings ({split}) ==')
    D = sum(r['D'] for r in ok); zero = sum(sum(s for s, c in zip(r['shapley'], r['cpm']) if c == 0) for r in ok) / D
    P(f'H1 CPM zero-share >= 0.30 pooled: {zero:.3f} -> {"consistent with H1" if zero >= 0.30 else "NOT supported"}')
    s = [r['stab']['d'] for r in ok if 'd' in r.get('stab', {}) and 'lead_changed' in r['stab']['d']]
    if s: lc = np.mean([x['lead_changed'] for x in s]); P(f'H2 leading party changes under regime d in >= 10% of instances: {lc:.3f} -> {"consistent with H2" if lc >= 0.10 else "NOT supported"}')
    key = '0.5|0.1|0.5|0.5|a'; vs = [r['e2'][key] for r in ok if key in r.get('e2', {}) and r['e2'][key][0] > 0]
    if vs: ag = np.mean([v[5] for v in vs]); P(f'H3 P2 picks the same set as P4 in a majority of instances (primary): {ag:.3f} -> {"consistent with H3 (agreement)" if ag > .5 else "NOT supported (agreement is not a majority)"}')
    if vs: c99 = np.mean([v[2] / v[0] >= 0.99 for v in vs]); P(f'H3b P2 reaches >= 99% of oracle recovery in a majority of instances with recoverable delay: {c99:.3f} -> {"consistent with H3b" if c99 > .5 else "NOT supported"}')
    g0 = [r['e2']['0.5|0.0|0.5|0.5|a'] for r in ok if '0.5|0.0|0.5|0.5|a' in r.get('e2', {}) and r['e2']['0.5|0.0|0.5|0.5|a'][0] > 0]; g2 = [r['e2']['0.5|0.25|0.5|0.5|a'] for r in ok if '0.5|0.25|0.5|0.5|a' in r.get('e2', {}) and r['e2']['0.5|0.25|0.5|0.5|a'][0] > 0]
    if g0 and g2:
        c0 = np.mean([v[2] / v[0] for v in g0]); c2 = np.mean([v[2] / v[0] for v in g2]); P(f'H4 capture of P2 falls by >= 0.05 from L_auth 0 to 0.25: {c0:.3f} -> {c2:.3f} (drop {c0 - c2:.3f}) -> {"consistent with H4" if c0 - c2 >= .05 else "NOT supported"}')

if __name__ == '__main__':
    for fn in sys.argv[1:]:
        d = json.load(open(fn)); rows = d['rows']; P(f'\n########## {fn}  split={d["split"]} cfg={d["cfg"]}  instances={len(rows)}')
        e1(rows); e3(rows); e2(rows); hyp(rows, d['split'])
