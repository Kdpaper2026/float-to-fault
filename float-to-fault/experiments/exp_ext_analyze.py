import json, sys, numpy as np, collections
rng = np.random.default_rng(20261102)
rows = [r for r in json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'ext_sweep.json')) if not r.get('skip')]
GR = [(r, p, n) for r in (.5, .7, .9) for p in (.6, .8, 1.0) for n in (0.0, .25, .5)]
cell = lambda g: 'a' if g == 'a' else f'g{g[0]}_{g[1]}_{g[2]}'
rec = [r for r in rows if r['ro'] > 0]
print(f'{len(rows)} instances with delay; {len(rec)} with recoverable delay (ro > 0)\n')
def cap(pol, rg, rs=rec): 
    v = [r['cells'][rg][pol][0] / r['ro'] for r in rs if r['cells'].get(rg)]
    return np.mean(v), len(v)
def bootm(xs, B=3000):
    xs = np.array(xs); m = xs.mean(); b = [xs[rng.integers(0, len(xs), len(xs))].mean() for _ in range(B)]; return m, np.percentile(b, 2.5), np.percentile(b, 97.5)
print('== A. Days recovered: capture of oracle recovery, by extraction setting (tau .5, L .10, cost sigma .5, budget .5)')
print('%-22s %6s %6s %6s %6s %6s' % ('cell (rec,prec,noise)', 'P1', 'P2', 'P2e', 'P3', 'P4'))
tab = {}
for g in ['a'] + GR:
    k = cell(g); tab[k] = {p: cap(p, k)[0] for p in ('P1', 'P2', 'P2e', 'P3', 'P4')}
    print('%-22s %6.3f %6.3f %6.3f %6.3f %6.3f' % (str(g), *[tab[k][p] for p in ('P1', 'P2', 'P2e', 'P3', 'P4')]))
print('\nMarginal means over the other two factors (P2e capture / P4 capture / P2 capture / P1)')
for ai, nm, vals in ((0, 'recall', (.5, .7, .9)), (1, 'precision', (.6, .8, 1.0)), (2, 'size noise', (0.0, .25, .5))):
    for v in vals:
        ks = [cell(g) for g in GR if g[ai] == v]
        print('  %-10s %.2f  P2e %.3f  P4 %.3f  P2 %.3f  P1 %.3f' % (nm, v, *[np.mean([tab[k][p] for k in ks]) for p in ('P2e', 'P4', 'P2', 'P1')]))
ks = [cell(g) for g in GR]
print('\ncells (of 27) where the exact analyst-model optimiser P4 is below epoch Shapley P2e: %d ; where P2 > P1 by more than 0.05: %d ; cells with P2e capture >= 0.80: %d ; >= 0.60: %d' % (
    sum(tab[k]['P4'] < tab[k]['P2e'] for k in ks), sum(tab[k]['P2'] - tab[k]['P1'] > .05 for k in ks), sum(tab[k]['P2e'] >= .8 for k in ks), sum(tab[k]['P2e'] >= .6 for k in ks)))
best_p1 = [k for k in ks if tab[k]['P1'] >= tab[k]['P2e']]
print('cells where survey-frequency ranking P1 matches or beats epoch Shapley:', [k for k in best_p1] or 'none')
print('\n== B. Money objective: net value = rho * days recovered (true model) - spent cost; oracle = best net value in the true model within budget (>= 0)')
SEL = [('a', 'complete evidence'), ('g0.7_1.0_0.0', 'random omission (recall .7)'), ('g0.9_0.8_0.25', 'good extraction (.9/.8/.25)'), ('g0.5_0.8_0.5', 'poor extraction (.5/.8/.5)')]
pols = ['P2e', 'P3', 'P1s', 'P2es', 'P3n', 'P4n']
for rho in (1.5, 3.0, 6.0):
    print(f'\n-- rho = {rho}: mean oracle net value per instance {np.mean([r["orc"][str(rho)] for r in rows]):.2f} (cost units); instances where oracle net value is 0 (no fix pays): {np.mean([r["orc"][str(rho)] <= 1e-9 for r in rows]):.2f}')
    print('%-30s %s' % ('', '  '.join('%-28s' % p for p in pols)))
    for k, lab in SEL:
        out = []
        for p in pols:
            key = {'P3n': f'P3n{rho}', 'P4n': f'P4n{rho}', 'P1s': f'P1s{rho}', 'P2es': f'P2es{rho}'}.get(p, p)
            nets = [rho * r['cells'][k][key][0] - r['cells'][k][key][1] for r in rows if r['cells'].get(k)]
            orc = [r['orc'][str(rho)] for r in rows if r['cells'].get(k)]
            cr = sum(nets) / sum(orc)
            out.append('mean %.2f cap %.2f neg %.2f' % (np.mean(nets), cr, np.mean([x < -1e-9 for x in nets])))
        print('%-30s %s' % (lab, '  '.join('%-28s' % o for o in out)))
print('\n(mean = mean net value per instance in cost units; cap = sum of net values / sum of oracle net values; neg = share of instances where the policy ends with negative net value; P2e (days policy) spends the whole budget; P1s and P2es follow the survey-frequency / epoch-Shapley order but skip a fix that does not pay in the analyst model; P3n greedy and P4n exact also use that test; P3 is the days-greedy)')
