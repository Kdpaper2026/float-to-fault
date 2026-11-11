import json, numpy as np, collections
rng = np.random.default_rng(20261028)
o = json.load(open('dslib_replay_out.json'))
ok = [x for x in o if x['status'] == 'ok' and x['root_plan'] is not None]
for x in ok:
    x['delay'] = x['act_replay'] - x['plan_replay']; x['cpmD'] = x['vD'] - x['plan_replay']
    x['fid'] = max(abs(x['plan_replay'] - x['root_plan']), abs(x['act_replay'] - (x['root_act'] or x['act_replay'])))
screen = [x for x in ok if x['neg_b'] <= 0.05]
def boot(xs, f, B=4000):
    v = [f(xs)]
    for _ in range(B):
        s = [xs[i] for i in rng.integers(0, len(xs), len(xs))]
        try: v.append(f(s))
        except ZeroDivisionError: pass
    a = np.array(v[1:]); return v[0], np.percentile(a, 2.5), np.percentile(a, 97.5)
def block(name, xs):
    late = [x for x in xs if x['delay'] > 0]
    print(f'\n== {name}: {len(xs)} projects replayed, {len(late)} late (observed delay > 0)')
    if not late: return
    D = lambda s: sum(x['delay'] for x in s)
    print('  total observed delay (late projects) %.0f working days; median project delay %.1f' % (D(late), np.median([x['delay'] for x in late])))
    for lab, f in [('CPM-with-actual-durations claim / observed delay', lambda s: sum(x['cpmD'] for x in s) / D(s)),
                   ('Shapley share of delay in start waits (W)', lambda s: sum(x['phiW'] for x in s) / D(s)),
                   ('Shapley share of delay in duration overruns (D)', lambda s: sum(x['phiD'] for x in s) / D(s)),
                   ]:
        m, lo, hi = boot(late, f); print('  %-62s %.3f [%.3f, %.3f]' % (lab, m, lo, hi))
    big = [x for x in late if x['delay'] >= 10]
    sh = [x['phiW'] / x['delay'] for x in big]
    print('  projects late by >=10 days: %d; per-project W-share median %.2f, share with W-share >= 0.30: %.2f; W-share <=0.05: %.2f' % (len(big), np.median(sh), np.mean([s >= .3 for s in sh]), np.mean([s <= .05 for s in sh])))
print('Replay fidelity: |replayed - file root| max over projects = %.3f working days (consistency by construction; calendars/relations parsed)' % max(x['fid'] for x in ok))
print('Baseline starts exactly at logic-ready time (median over projects): %.2f ; negative-wait share: median %.2f max %.2f' % (np.median([x['zero_b'] for x in ok]), np.median([x['neg_b'] for x in ok]), max(x['neg_b'] for x in ok)))
print('Projects: replayed %d of %d construction; screened (<=5%% activities starting before logic permits) %d' % (len(ok), len(o), len(screen)))
strict = [x for x in screen if x['fid'] <= 0.5]
print('Replayed real duration matches the file-reported real duration within 0.5 day: %d of %d (the other %d overshoot by 9-45 days)' % (sum(1 for x in ok if x['fid'] <= 0.5), len(ok), sum(1 for x in ok if x['fid'] > 0.5)))
print('Strict screen (logic-consistent baseline AND replay matches reported real duration): %d projects' % len(strict))
block('STRICT screen (primary)', strict)
block('STRICT, tracking authenticity G', [x for x in strict if x['auth_track'] == 'G'])
block('STRICT, tracking authenticity not G', [x for x in strict if x['auth_track'] != 'G'])
block('STRICT, G, excluding near-duplicate 2016 series (C2016-16..26)', [x for x in strict if x['auth_track'] == 'G' and not (x['code'].startswith('C2016-') and 16 <= int(x['code'][-2:]) <= 26)])
block('STRICT, only projects whose DSLIB tracking has >=5 periods', [x for x in strict if x['ntp'] >= 5])
block('all replayed', ok)
block('screened', screen)
block('screened, tracking authenticity G', [x for x in screen if x['auth_track'] == 'G'])
block('screened, tracking authenticity not G', [x for x in screen if x['auth_track'] != 'G'])
block('screened, G, excluding near-duplicate 2016 series (C2016-16..26)', [x for x in screen if x['auth_track'] == 'G' and not (x['code'].startswith('C2016-') and 16 <= int(x['code'][-2:]) <= 26)])
