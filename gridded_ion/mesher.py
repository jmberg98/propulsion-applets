"""Tessellate a build123d/OCC shape to (positions, normals, indices) with smooth per-face normals."""
import numpy as np
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.BRepGProp import BRepGProp_Face

def mesh_shape(shape, lin=0.35, ang=0.35):
    shp = shape.wrapped if hasattr(shape, "wrapped") else shape
    BRepMesh_IncrementalMesh(shp, lin, False, ang, True)
    P=[]; N=[]; I=[]
    exp = TopExp_Explorer(shp, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        exp.Next()
        if tri is None: continue
        trsf = loc.Transformation()
        rev = (face.Orientation() == TopAbs_REVERSED)
        gf = BRepGProp_Face(face)
        base = len(P)
        nb = tri.NbNodes()
        # try UV nodes for normals; fall back to face-normal if absent
        has_uv = tri.HasUVNodes()
        from OCP.gp import gp_Pnt, gp_Vec, gp_Dir
        for i in range(1, nb+1):
            p = tri.Node(i).Transformed(trsf)
            P.append((p.X(), p.Y(), p.Z()))
            if has_uv:
                uv = tri.UVNode(i)
                pnt = gp_Pnt(); vec = gp_Vec()
                gf.Normal(uv.X(), uv.Y(), pnt, vec)
                d = gp_Dir(vec) if vec.Magnitude()>1e-12 else gp_Dir(0,0,1)
                dd = gp_Dir(d.X(), d.Y(), d.Z()); dd.Transform(trsf)
                nx,ny,nz = dd.X(), dd.Y(), dd.Z()
            else:
                nx,ny,nz = 0.0,0.0,1.0
            if rev: nx,ny,nz = -nx,-ny,-nz
            N.append((nx,ny,nz))
        for i in range(1, tri.NbTriangles()+1):
            a,b,c = tri.Triangle(i).Get()
            if rev: a,c = c,a
            I.append((base+a-1, base+b-1, base+c-1))
    P=np.array(P, dtype='<f4'); N=np.array(N, dtype='<f4'); I=np.array(I, dtype='<u4').reshape(-1)
    return P, N, I

if __name__ == "__main__":
    from build123d import Cylinder, Pos
    s = Pos(0,0,0)*Cylinder(radius=10, height=40)
    P,N,I = mesh_shape(s)
    print("verts", len(P), "tris", len(I)//3)
    # side-wall node: pick a vert with |z|<15, normal should be radial (nz~0, (nx,ny) ~ (x,y)/r)
    for k in range(len(P)):
        x,y,z=P[k]
        if abs(z)<15 and abs(x)>1:
            nrm=N[k]; r=np.hypot(x,y)
            print("side vert",[round(v,2) for v in P[k]],"normal",[round(v,2) for v in nrm],"radial-dot",round((nrm[0]*x+nrm[1]*y)/r,3),"nz",round(float(nrm[2]),3))
            break
    # cap node: z~20
    for k in range(len(P)):
        x,y,z=P[k]
        if abs(z-20)<0.1:
            print("cap vert",[round(v,2) for v in P[k]],"normal",[round(float(v),2) for v in N[k]])
            break

def _selftest():
    import numpy as np
    from build123d import Cylinder, Pos
    s = Pos(0,0,0)*Cylinder(radius=10, height=40)
    P,N,I = mesh_shape(s)
    sidew=capw=0; bad=0
    for k in range(len(P)):
        x,y,z=P[k]; nx,ny,nz=N[k]; r=np.hypot(x,y)
        if abs(z)<19.5 and r>1:  # pure side wall
            radial=(nx*x+ny*y)/r
            if radial>0.9 and abs(nz)<0.15: sidew+=1
            else: bad+=1
        if abs(abs(z)-20)<0.01 and r<9.5:  # cap interior
            if abs(nz)>0.9: capw+=1
            else: bad+=1
    print("side-correct",sidew,"cap-correct",capw,"bad",bad)
