import openpyxl, collections, math
wb = openpyxl.load_workbook('SECOND_CODER_SHEET_COMPLETED.xlsx', data_only=True)
A = [r for r in wb['Coding A general causes'].iter_rows(min_row=2, values_only=True)]
Bq = [r for r in wb['Coding B contract reasons'].iter_rows(min_row=2, values_only=True)]
# authors' coding of Table A1 (paper Appendix A); multi-valued entries are sets
auth = {1:({'employer'},{'labour','supply_delay'}),2:({'employer'},{'design_hold','rework'}),3:({'employer'},{'design_hold'}),4:({'contractor'},{'labour','supply_delay'}),
 5:({'contractor'},{'not_event'}),6:({'employer'},{'rework','design_hold'}),7:({'contractor'},{'productivity'}),8:({'contractor'},{'rework'}),9:({'contractor'},{'productivity'}),
 10:({'contractor'},{'labour'}),11:({'contractor'},{'supply_delay'}),12:({'neutral'},{'weather'}),13:({'employer'},{'rework','design_hold'}),14:({'employer','authority'},{'approval_wait'}),
 15:({'employer'},{'not_event'}),16:({'employer'},{'labour','supply_delay'}),17:({'contractor'},{'productivity'}),18:({'authority'},{'approval_wait'}),19:({'employer'},{'not_event'}),20:({'employer'},{'design_hold','rework'})}
def kappa(a, b):
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n; ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    return po, (po - pe) / (1 - pe) if pe < 1 else float('nan')
def single(s, v): return v if v in s else sorted(s)[0]
rows = []
for r in A:
    i, _, oc, et, nt = r; ao, ae = auth[i]; rows.append((i, r[1], oc, et, ao, ae))
print('== A. 20 general causes: second coder vs authors (set-valued authors codes count as agreeing if the coder value is in the set)')
for fld, k in (('owner_class', 2), ('event_type', 3)):
    ag = [r[k] in r[4 if k == 2 else 5] for r in rows]
    a1 = [single(r[4 if k == 2 else 5], r[k]) for r in rows]; b1 = [r[k] for r in rows]
    po, kp = kappa(a1, b1)
    unc = [r[k] == 'unclear' for r in rows]
    comm = [g for g, u in zip(ag, unc) if not u]
    print(f'{fld}: agree {sum(ag)}/20 = {sum(ag)/20:.2f}; kappa {kp:.2f}; coder said unclear {sum(unc)}/20; among the {len(comm)} rows where the coder committed: agree {sum(comm)}/{len(comm)} = {sum(comm)/len(comm):.2f}')
print('\nrow-level disagreements (coder vs authors):')
for r in rows:
    d = []
    if r[2] not in r[4]: d.append(f'owner coder={r[2]} authors={sorted(r[4])}')
    if r[3] not in r[5]: d.append(f'event coder={r[3]} authors={sorted(r[5])}')
    if d: print(r[0], r[1][:55], '|', '; '.join(d))
print('\ncoder owner counts:', dict(collections.Counter(r[2] for r in rows)), '\ncoder event counts:', dict(collections.Counter(r[3] for r in rows)))
# lenient: 'baseline' owner for authors' not_event rows treated as match
len_ok = sum((r[2] in r[4]) or (r[2] == 'baseline' and 'not_event' in r[5]) for r in rows)
print('owner agreement if the authors baseline/not_event rows count as baseline:', len_ok, '/20')
# B: compare coder owner with party the source attributes (not an authors coding)
src = ['employer'] * 7 + ['contractor'] * 3 + ['authority/neutral'] * 5   # order of Table A2; 'Delay in other works'/geology are external stakeholder
src = ['employer', 'employer', 'employer', 'employer', 'employer', 'employer', 'employer', 'contractor', 'contractor', 'contractor', 'external', 'external', 'external', 'external', 'external']
# sheet B order: 1 procurement(E) 2 contract mgmt(E) 3 feasibility(E) 4 land(E) 5 scope(E) 6 related works(E) 7 baselining(E) 8 contract admin(C) 9 resources(C) 10 liquidity(C) 11 approval(ext) 12 FM(ext) 13 FM covid(ext) 14 other works(ext) 15 geology(ext)
print('\n== B. 15 contract reasons: coder owner class vs the party the World Bank source attributes the reason to')
ok = 0; comm = 0
for r, s in zip(Bq, src):
    oc = r[2]; match = (oc == s) or (s == 'external' and oc in ('authority', 'neutral')) or (s == 'employer' and oc in ('baseline',))
    comm += oc != 'unclear'; ok += match and oc != 'unclear'
    print(r[0], r[1][:50], '| source:', s, '| coder:', oc, '|', 'consistent' if match else ('unclear' if oc == 'unclear' else 'differs'))
print('coder committed on', comm, 'of 15; of those, consistent with the source party:', ok)
