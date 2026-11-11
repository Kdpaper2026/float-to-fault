"""Reproduce Tables 14 and 15 of Huynh, Lucko and Eid (2023), warehouse case (data from Ibbs et al. 2011).
Players: all activities except EX, which is excusable and held at its actual duration in every coalition (our E_f).
Published values transcribed from the paper's Tables 14 and 15 (Shapley value column)."""
from itertools import combinations
from math import factorial
from fractions import Fraction
act = ['EX','FT','OF','ST','RF','WD','ME','EL','FC']
plan = dict(EX=10,FT=20,OF=25,ST=5,RF=5,WD=20,ME=30,EL=30,FC=5)
pred = dict(EX=[],FT=['EX'],OF=[],ST=['FT','OF'],RF=['ST'],WD=['RF'],ME=['ST'],EL=['ST'],FC=['WD','ME','EL'])
def makespan(dur):
    fin = {}
    for a in act:
        fin[a] = max([fin[p] for p in pred[a]], default=0) + dur[a]
    return fin['FC']
def shap(actual):
    players = [a for a in act if a != 'EX']
    v = lambda S: makespan({a: (actual[a] if (a in S or a == 'EX') else plan[a]) for a in act})
    n = len(players); out = {}
    for p in players:
        others = [q for q in players if q != p]; tot = Fraction(0)
        for k in range(n):
            for S in combinations(others, k):
                tot += Fraction(factorial(k) * factorial(n - k - 1), factorial(n)) * (v(set(S) | {p}) - v(set(S)))
        out[p] = tot
    return out, v(set()), v(set(players))
T14 = dict(EX=0, FT=2, OF=2, ST=0, RF=Fraction(1,6), WD=Fraction(1,6), ME=Fraction(23,6), EL=Fraction(5,6), FC=0)
T15 = dict(EX=0, FT=4, OF=0, ST=0, RF=0, WD=0, ME=4, EL=1, FC=-1)
cases = [('Table 14 (as-built: Ibbs et al. 2011)', dict(EX=11,FT=24,OF=35,ST=5,RF=7,WD=25,ME=35,EL=32,FC=5), T14),
         ('Table 15 (modified: OF 2 days early, RF and FC 1 day early)', dict(EX=11,FT=24,OF=23,ST=5,RF=4,WD=25,ME=35,EL=32,FC=4), T15)]
for name, actual, pub in cases:
    sh, v0, vN = shap(actual); print('\n' + name, '| planned finish with EX at actual (v0) =', v0, '| as-built finish =', vN, '| as-planned finish', makespan(plan), '| as-built finish by full actuals', makespan(actual))
    print('act  engine      published   match')
    allm = True
    for a in act:
        e = sh.get(a, Fraction(0)); p = Fraction(pub[a]); allm &= (e == p)
        print(f'{a:3s}  {str(e):10s}  {str(p):10s}  {"yes" if e == p else "NO"}')
    print('sum engine', sum(sh.values()), ' all match:', allm)
