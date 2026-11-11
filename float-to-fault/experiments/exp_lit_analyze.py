"""Analysis for amendment A7 (litigation event).  python3 -I exp_lit_analyze.py > lit_analysis.txt"""
import os, sys, json, random
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results')
PARTIES = ['employer', 'authority', 'contractor', 'neutral', 'court']
rng = np.random.default_rng(7)

def load(n):
    p = os.path.join(RES, f'lit_{n}.json')
    return json.load(open(p))['rows'] if os.path.exists(p) else None

def boot_ratio(num, den, B=2000):
    num, den = np.asarray(num, float), np.asarray(den, float); n = len(num)
    if n == 0 or den.sum() == 0: return float('nan'), float('nan'), float('nan')
    r = num.sum() / den.sum(); bs = []
    for _ in range(B):
        i = rng.integers(0, n, n); d = den[i].sum(); bs.append(num[i].sum() / d if d > 0 else np.nan)
    return r, np.nanpercentile(bs, 2.5), np.nanpercentile(bs, 97.5)

def boot_mean(x, B=2000):
    x = np.asarray(x, float); n = len(x)
    if n == 0: return float('nan'), float('nan'), float('nan')
    bs = [x[rng.integers(0, n, n)].mean() for _ in range(B)]; return x.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)

def fmt(t): return f'{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]'

def main():
    rows = load('primary'); assert rows, 'primary missing'
    ok = [r for r in rows if r['A'] and r['B']]; print(f'instances {len(rows)}; with delay in both worlds {len(ok)}; delay only with litigation {sum(1 for r in rows if (not r["A"]) and r["B"])}')
    DA = np.array([r['A']['D'] for r in ok], float); DB = np.array([r['B']['D'] for r in ok], float); LD = np.array([r['B']['lit_days'] for r in ok], float)
    print('\n== Attribution (truth, primary config) ==')
    print('mean delay days 8-event world %.1f, 9-event world %.1f (litigation adds %.1f days on average, pooled)' % (DA.mean(), DB.mean(), (DB - DA).mean()))
    print('instances where litigation adds delay (D9 > D8): %d of %d (%.1f%%)' % ((DB > DA).sum(), len(ok), 100 * (DB > DA).mean()))
    print('litigation Shapley share of attributed delay, pooled (ratio of sums): ' + fmt(boot_ratio(LD, DB)))
    print('litigation Shapley share, per instance mean: ' + fmt(boot_mean(LD / DB)))
    for w, key, D in (('8-event', 'A', DA), ('9-event', 'B', DB)):
        s = {p: sum(r[key]['shares_true'][p] * r[key]['D'] for r in ok) / D.sum() for p in PARTIES}; print(f'pooled share by party, {w} world: ' + ', '.join(f'{p} {s[p]:.3f}' for p in PARTIES))
    la = [r['A']['lead_true'] for r in ok]; lb = [r['B']['lead_true'] for r in ok]
    print('leading party counts 8-event:', {p: la.count(p) for p in PARTIES}, '| 9-event:', {p: lb.count(p) for p in PARTIES})
    print('leading party differs between worlds: %.1f%%' % (100 * np.mean([a != b for a, b in zip(la, lb)])))
    print('\n== HL1: litigation missing from the record (regime lo) and other regimes, 9-event world ==')
    for rg in ('lo', 'c', 'd'):
        ch = [r['B']['regs'][rg]['lead_obs'] != r['B']['lead_true'] for r in ok if r['B']['regs'].get(rg) and 'lead_obs' in r['B']['regs'][rg]]
        chl = [r['B']['regs'][rg]['lead_obs'] != r['B']['lead_true'] for r in ok if r['B']['regs'].get(rg) and 'lead_obs' in r['B']['regs'][rg] and r['B']['lit_days'] / r['B']['D'] >= .05]
        print(f'regime {rg}: leading party changed in {100*np.mean(ch):.1f}% of {len(ch)} instances; where litigation carries >= 5% of delay: {100*np.mean(chl) if chl else float("nan"):.1f}% of {len(chl)}')
    ch8 = [r['A']['regs'][rg]['lead_obs'] != r['A']['lead_true'] for rg in ('c', 'd') for r in ok if r['A']['regs'].get(rg) and 'lead_obs' in r['A']['regs'][rg]]
    print('(reference, 8-event world, regimes c and d pooled: %.1f%%)' % (100 * np.mean(ch8)))
    print('\n== Mitigation: capture of oracle recovery (mean of per-instance ratios over instances with recoverable delay, as in the protocol) ==')
    for key, nm in (('A', '8-event'), ('B', '9-event')):
        for rg in ('a', 'lo', 'c', 'd'):
            rs = [r[key] for r in ok if r[key]['ro'] > 0 and r[key]['regs'].get(rg) and 'R' in r[key]['regs'][rg]]
            if not rs: continue
            den = [x['ro'] for x in rs]; line = f'{nm} regime {rg} (n={len(rs)}): '
            for pol in ('P1', 'P2', 'P2e', 'P3', 'P4'): line += f'{pol} {fmt(boot_mean([x["regs"][rg]["R"][pol] / x["ro"] for x in rs]))}  '
            print(line)
    rsB = [r['B'] for r in ok if r['B']['ro'] > 0 and r['B']['regs'].get('a')]
    print('\nHL2 (9-event world, complete record, n=%d): P2e capture %s ; P2e minus P4 gap (days/oracle days) %s' % (len(rsB), fmt(boot_mean([x['regs']['a']['R']['P2e'] / x['ro'] for x in rsB])),
          fmt(boot_mean([(x['regs']['a']['R']['P2e'] - x['regs']['a']['R']['P4']) / x['ro'] for x in rsB]))))
    print('recoverable delay exists in %d of %d (9-event) vs %d of %d (8-event) instances' % (len(rsB), len(ok), sum(1 for r in ok if r['A']['ro'] > 0), len(ok)))
    print('litigation event in the oracle best set: %.1f%% of 9-event instances with recoverable delay; chosen by P2e (complete record): %.1f%%; by P4: %.1f%%' % (
        100 * np.mean([x['lit_in_oracle'] for x in rsB]), 100 * np.mean([x['regs']['a']['lit']['P2e'] for x in rsB]), 100 * np.mean([x['regs']['a']['lit']['P4'] for x in rsB])))
    # litigation still running at the epoch?
    act = [r['lit_start'] + r['lit_size'] > 0.5 * (r['M0'] + r['B']['D']) for r in ok]; print('litigation window still open at the decision epoch in %.1f%% of instances' % (100 * np.mean(act)))
    print('\n== Sensitivity configurations (n instances; litigation share of attributed delay; share of recoverable instances with litigation in oracle set; P2e capture, complete record) ==')
    for n in ('primary', 'scale_lo', 'scale_hi', 'lead_lo', 'lead_hi', 'cost3'):
        rr = load(n)
        if not rr: print(n, 'not available'); continue
        o = [r for r in rr if r['A'] and r['B']]; LDn = np.array([r['B']['lit_days'] for r in o]); DBn = np.array([r['B']['D'] for r in o]); rs = [r['B'] for r in o if r['B']['ro'] > 0 and r['B']['regs'].get('a')]
        print(f'{n:9s} n={len(o):3d} lit share {fmt(boot_ratio(LDn, DBn))} | lit in oracle set {100*np.mean([x["lit_in_oracle"] for x in rs]):.1f}% (n={len(rs)}) | P2e capture {fmt(boot_mean([x["regs"]["a"]["R"]["P2e"] / x["ro"] for x in rs]))}')
    # HL3 on all common instances (protocol wording: share of instances; instances without recoverable delay count as 'not in set')
    lo, hi = load('lead_lo'), load('lead_hi')
    if lo and hi:
        H = {r['name']: r for r in hi}; fl, fh = [], []
        for r in lo:
            if r['name'] in H and r['B'] and H[r['name']]['B']: fl.append(r['B']['lit_in_oracle']); fh.append(H[r['name']]['B']['lit_in_oracle'])
        print(f'\nHL3 (all {len(fl)} common instances): litigation in oracle best set with L_lit 0.10: {sum(fl)} ({100*np.mean(fl):.1f}%), with L_lit 0.50: {sum(fh)} ({100*np.mean(fh):.1f}%)')
    # who was the true leader when the leading party changed under omission
    chg = [r['B']['lead_true'] for r in ok if r['B']['regs'].get('lo') and r['B']['regs']['lo'].get('lead_obs') != r['B']['lead_true']]
    print('\nleading party changed under omission (lo): %d instances; true leader was court in %d of them' % (len(chg), sum(1 for x in chg if x == 'court')))
    nc = [r for r in ok if r['B']['lead_true'] != 'court' and r['B']['regs'].get('lo') and 'lead_obs' in r['B']['regs']['lo']]
    print('instances where the true leader is not the court: %d; leader changed under omission in %d' % (len(nc), sum(1 for r in nc if r['B']['regs']['lo']['lead_obs'] != r['B']['lead_true'])))

if __name__ == '__main__': main()
