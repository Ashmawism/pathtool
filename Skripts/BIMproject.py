import clr
clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import PolySurface
from Autodesk.DesignScript.Geometry import Surface
clr.AddReference('DSCoreNodes')
import DSCore
from DSCore import List

class BIMdata:
    unwrap = None
    
    def __init__(self, inputGeo, unwrap):
        if isinstance(inputGeo,list):
            self.original = inputGeo
        else:
            self.original = [inputGeo]
        
        self.solid = None
        self.bb = None
        self.top = None
        self.bottom = None
        self.sides = []
        self.innersides = []
        self.outersides = []
        self.cference = []
        self.width = []
        self.height = 0
        self.count = 0
        self.offsets = {}
        
        BIMdata.unwrap = unwrap
    
    def extractSolid(self):
        solids = [item for e in self.original for item in e.Geometry()]
        self.count = len(solids)
        solids = iter(solids)
        self.solid = next(solids, -1)
        other = next(solids, -1)
        
        while other != -1:
            self.solid = self.solid.Union(other)
            other = next(solids, -1)
        
        self.bb = self.solid.BoundingBox
        self.height = self.bb.MaxPoint.Z
    
    def extractWidth(self):
        for o in self.original:
            pars = o.Parameters
            otyp = next(p.Value.Parameters for p in pars if p.Name == r'Typ')
            width = next(iter([p.Value for p in otyp if p.Name == r'Breite']), 0)
            self.width.append(width)
        
        if len(set(self.width)) == 1:
            self.width = [self.width[0]]
    
    def extractFaces(self):
        polyS = PolySurface.BySolid(self.solid)
        faces = polyS.Explode()
        
        for face in faces:
            f = BIMdata.unwrap(face)
            bb = f.BoundingBox
            topZ = bb.MaxPoint.Z
            bottomZ = bb.MinPoint.Z
            obottomZ = self.bb.MinPoint.Z
            
            if abs(bottomZ - obottomZ) < 0.0001 and abs(self.height - topZ) > 0.0001:
                self.bottom = f
            elif abs(bottomZ - obottomZ) > 0.0001 and abs(self.height - topZ) < 0.0001:
                self.top = f
            else:
                self.cference.append(f)
                per = f.PerimeterCurves()
                
                for c in per:
                    side = self.isWidth(c.Length)
                    
                    if side:
                        self.sides.append(f)
                        break
        
        perS = PolySurface.ByJoinedSurfaces(self.cference)
        self.offsets["0"] = perS
    
    def isWidth(self, value):
        for w in self.width:
            if abs(value - w) < 0.0001:
                return True
        
        return False
    
    def defineInsideOutside(self, selectedSides):
        per = []
        for c in self.cference:
            if c not in self.sides:
                per.append(c)
            
        for p in per:
            t = False
            for s in selectedSides:
                testI = BIMdata.unwrap(p.Intersect(s))
                
                if testI and isinstance(testI[0], Surface):
                    t = True
                    break
            
            if t:
                self.innersides.append(p)
            else:
                self.outersides.append(p)
    
    def getOffset(self, value, R=0):
        v = f"{value}"
        if v not in self.offsets:
            pS = self.offsets["0"]
            offS = pS.Offset(-value).Explode()
            
            oS = offS[0]
            for s in List.RestOfItems(offS):
                oS = oS.Join(s)
            
            vEdges = [e for e in oS.Edges if List.Count(e.AdjacentFaces) == 2]

            if R:
                perSurfs = oS.Fillet(vEdges, R)
            else:
                perSurfs = oS

            self.offsets[v] = perSurfs
        
        return self.offsets[v]
        
    def extractGUID(self):
        pars = BIMdata.unwrap(self.original[0]).LookupParameter("IfcGUID")
        return pars.AsString()