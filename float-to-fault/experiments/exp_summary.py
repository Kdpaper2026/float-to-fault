import json, sys, os, numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
RES=sys.argv[1] if len(sys.argv)>1 else os.path.join(HERE,'results')
from exp_analyze import boot, f
cfgs=['primary','size_lo','size_hi','mix_owner','mix_contr','partial']
print('Held-out sensitivity: mean capture of the oracle recovery (instances with recoverable delay), tau .5, L_auth .1, sigma .5, beta .5')
print('%-10s %-3s %5s %7s %7s %7s %7s %7s %7s | CPMzero  lead-chg(d)  err(d)'%('config','reg','n','P1','P2','P2e','P3','P4','P2e-P2'))
for c in cfgs:
    rows=json.load(open(os.path.join(RES,f'held_{c}.json')))['rows']; ok=[r for r in rows if 'shapley' in r]
    D=sum(r['D'] for r in ok); zero=sum(sum(s for s,cc in zip(r['shapley'],r['cpm']) if cc==0) for r in ok)/D
    s=[r['stab']['d'] for r in ok if 'lead_changed' in r.get('stab',{}).get('d',{})]
    for rg in ('a','b','c','d'):
        key='0.5|0.1|0.5|0.5|'+rg; vs=[r['e2'][key] for r in ok if key in r.get('e2',{}) and r['e2'][key][0]>0]
        cap=lambda i: np.mean([v[i]/v[0] for v in vs])
        extra=('  %.3f     %.3f       %.3f'%(zero,np.mean([x['lead_changed'] for x in s]),np.mean([x['err_empauth'] for x in s]))) if rg=='a' else ''
        print('%-10s %-3s %5d %7.3f %7.3f %7.3f %7.3f %7.3f %7.3f |%s'%(c,rg,len(vs),cap(1),cap(2),cap(10),cap(3),cap(4),cap(10)-cap(2),extra))
