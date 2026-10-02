import numpy as np, math
T={}
for n,lat0 in [('S30E022',-30),('S31E022',-31)]:
    T[lat0]=np.fromfile(n+'.hgt','>i2').reshape(3601,3601).astype(float)
def z(lat,lon):
    lat0=math.floor(lat); a=T[lat0]
    r=(lat0+1-lat)*3600; c=(lon-22)*3600
    r0,c0=int(r),int(c); dr,dc=r-r0,c-c0
    v=a[r0:r0+2,c0:c0+2]
    return v[0,0]*(1-dr)*(1-dc)+v[0,1]*(1-dr)*dc+v[1,0]*dr*(1-dc)+v[1,1]*dr*dc
def dist(a,b):
    R=6371000;la1,lo1,la2,lo2=map(math.radians,(*a,*b))
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
S=(-30.0220257,22.3551282)
TW={'T1 (new, -29.9597,22.4196)':(-29.959722222,22.419555556),'T2 Alkantpan CEN_64770':(-29.95869444,22.30183333)}
print('Site ground', round(z(*S)))
k=4/3;Re=6371000*k
for name,t in TW.items():
    D=dist(t,S);N=600
    pts=[(t[0]+(S[0]-t[0])*i/N,t[1]+(S[1]-t[1])*i/N) for i in range(N+1)]
    g=np.array([z(*p) for p in pts]); d=np.linspace(0,D,N+1)
    bulge=d*(D-d)/(2*Re)
    print(f'\n{name}: {D/1000:.2f} km, tower ground {g[0]:.0f} m, site ground {g[-1]:.0f} m, max terrain {g.max():.0f} m at {d[g.argmax()]/1000:.1f} km')
    for f in (5.8,18):
        lam=3e8/(f*1e9)
        for ht in (20,30,40):
            for hs in (6,10,15):
                a=g[0]+ht; b=g[-1]+hs
                los=a+(b-a)*d/D
                F1=np.sqrt(lam*d*(D-d)/D)
                clr=(los-(g+bulge))[1:-1]; F=F1[1:-1]
                ratio=(clr/F).min(); i=(clr/F).argmin()
                print(f'  {f:>4} GHz tower {ht}m / site {hs}m: min clearance {clr.min():6.1f} m, worst F1 ratio {ratio*100:5.0f}% at {d[1:-1][i]/1000:.1f} km', '-> LOS+60%F1 OK' if ratio>=0.6 else ('-> LOS ok, Fresnel partial' if clr.min()>0 else '-> BLOCKED'))
    np.savetxt(name.split()[0]+'_profile.csv',np.c_[d,g,bulge],delimiter=',',header='dist_m,ground_m,earth_bulge_m_k1.33',fmt='%.1f')
