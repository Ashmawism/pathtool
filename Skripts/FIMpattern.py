# pyright: reportMissingImports=false
import clr
from typing import Any, Union, Tuple
from collections import Counter

clr.AddReference('ProtoGeometry')

from Autodesk.DesignScript.Geometry import PolySurface
from Autodesk.DesignScript.Geometry import Plane
from Autodesk.DesignScript.Geometry import Vector
from Autodesk.DesignScript.Geometry import Point
from Autodesk.DesignScript.Geometry import PolyCurve
from Autodesk.DesignScript.Geometry import Curve
from Autodesk.DesignScript.Geometry import NurbsCurve
from Autodesk.DesignScript.Geometry import BoundingBox
from Autodesk.DesignScript.Geometry import Surface
from Autodesk.DesignScript.Geometry import NurbsSurface
from Autodesk.DesignScript.Geometry import Line
from Autodesk.DesignScript.Geometry import Arc
import numpy as np

class Pattern:
    """
    Pattern class:
    gives access to specific path planning methods
    """
    def __init__(self) -> None:        
        self.unwrap = None # unwrap function passed from built-in python
        self.H = 0 # usr setting layer height
        self.D = 0 # usr setting nozzle diameter
        self.R = 0 # usr setting blend radius
        self.nop = 0 # Number of perimeters
        self.noo = 0 # Number of Offsets required
        self.patternPar = 0.5 # parameter for pattern
        self.ref = Point.ByCoordinates(0, 0.5, 0) # reference point, used to determine start curve.
        self.offsets = None # stores offsets of perimeter surfaces
        self.getoffset = None # stores delegate of BIMproject method
        self.layer = None # temporarily stores Layer
    
    def setParameters(self, lH: float, nD: float, bR: float, NoP: int, pP: float):
        self.H = lH
        self.D = nD
        self.R = bR
        self.nop = NoP
        self.noo = NoP
        self.patternPar = pP

    def doPathPlanning(self, layer):
        self.layer = layer

    def addPerimeter(self, surf: Surface):
        """
        Adds a perimeter derived from surf to path
        surf: offset surface of BIMdata.surface
        """
        # FIXME: if surf == None -> do offset of self.perimeter
        # FIXME: check if perCurves are "closed" -> necessary for tilted components
        perCurves = self.unwrap(self.layer.surface.Intersect(surf))
        perCurves = self.reverseCurves(perCurves)
        sides = self.identifySides(perCurves)
        aS = sides[not(self.layer.redir)] # access side
        oS = sides[self.layer.redir] # other side
        perCurves, aC = self.insertAccess(aS, perCurves)
        self.connect2path(perCurves, [oS, aC])

    def cornerOffset(self, angle, corner):
        if angle != 0:
            return (2*self.R*(1-np.cos(angle/2)) + corner*self.D)/(2*np.sin(angle/2)) - self.R
        else:
            return 0
    
    def identifySides(self, curves: Curve) -> list:
        """
        Identifies curves of new offset corresponding to the sides
        """
        sides = []
        for s in self.layer.sides: # for all perimeter sides
            mP = s.PointAtParameter(0.5) # center point of perimeter side
            dist = [10000, None] # some large value
            for c in curves:
                d = mP.DistanceTo(c)
                if d < dist[0]: # find closest curve to center point of perimeter side.
                    dist = [d, c]
            
            sides.append(dist[1])
        
        return sides
    
    def prepareHelpCurves(self) -> Tuple[list, list, list, Curve]:
        start = self.nop
        end = self.noo
        perSurfs = [self.getOffset((n + 0.5)*self.D, self.R) for n in range(start, end)]
        perCurves = [self.unwrap(self.layer.surface.Intersect(pS)) for pS in perSurfs]
        perCurves = [self.reverseCurves(pC) for pC in perCurves]
        sidesOI = [self.identifySides(pC) for pC in perCurves]
        aS = [sides[not(self.layer.redir)] for sides in sidesOI] # access sides
        oS = [sides[self.layer.redir] for sides in sidesOI] # other sides
        
        perCurves = [self.rotate(pC,pC.index(a)) for pC, a in zip(perCurves, aS)]
        
        path2pattern = perCurves[0][:perCurves[0].index(oS[0])+1+int(self.R > 0)]
        segmentsOI = [[c for c in pC[pC.index(o)+1:] if (not(isinstance(c,Arc) and c.Radius - self.R < 0.001) and not(isinstance(c,NurbsCurve) and c.Length < 1.2*self.R*np.pi))] for pC, o in zip(perCurves, oS)]
        segmentsOI = [self.trimSegments(s) for s in segmentsOI]

        newouter, newinner = self.equalizeSegments(segmentsOI)

        if self.layer.redir:
            self.layer.corners.reverse()
        
        # combine tangent parts:
        outer = [newouter[0]]
        inner = [newinner[0]]
        for c, o, i in zip(self.layer.corners[1:], newouter[1:],newinner[1:]):
            if c == 0: # if next curve is tangent
                outer[-1] = self.unwrap(outer[-1].Join(o).Reverse())
                inner[-1] = self.unwrap(inner[-1].Join(i).Reverse())
                
            elif c != -1:
                outer.append(o)
                inner.append(i)
        
        self.layer.corners = [ct for ct in self.layer.corners if ct != 0] # remove tangent type

        return outer, inner, path2pattern, oS[0]

    def connect2path(self, inner, vipC: list, removelast: bool=True):
        if self.layer.path:
            inner = self.rotate(inner, inner.index(vipC[0]))
            startPar = self.D / inner[0].Length
            inner[0] = self.unwrap(inner[0].TrimByStartParameter(startPar).Explode()[0])

            l = Line.ByStartPointEndPoint(self.layer.path[-1].EndPoint,inner[0].StartPoint)

            if self.R:
                # remove last fillet from intersection:
                if removelast:
                    _ = inner.pop(-1)
                
                # shorten and move line for first and second fillet:
                parl = self.R/l.Length
                l = l.TrimByParameter(parl,1-parl).Explode()[0]
                l = l.Translate(self.layer.path[-1].TangentAtParameter(1),self.R)

                # line for end fillet:
                l2 = l.Translate(self.layer.path[-1].TangentAtParameter(1),self.D).Reverse()

                # fillets:
                a1 = Arc.ByFillet(self.layer.path[-1],l,self.R)
                a2 = Arc.ByFillet(l,inner[0],self.R)
                a3 = Arc.ByFillet(l2,self.layer.path[0],self.R)

                # connecting end of inner path to last fillet:
                l3 = Line.ByStartPointEndPoint(inner[-1].EndPoint,a3.StartPoint)

                # outer2inner:
                self.layer.path.append(a1)
                self.layer.path.append(l)
                self.layer.path.append(a2)

                # inner:
                self.layer.path.extend(inner)

                # inner2outer:
                self.layer.path.append(l3)
                self.layer.path.append(a3)

            else:
                l3 = Line.ByStartPointEndPoint(inner[-1].EndPoint,self.layer.path[0].StartPoint)
                
                # outer2inner:
                self.layer.path.append(l)
        
                # inner:
                self.layer.path.extend(inner)
                
                # inner2outer:
                self.layer.path.append(l3)
        else:
            self.layer.path = inner
        
        self.layer.path = self.rotate(self.layer.path, self.layer.path.index(vipC[1]))

    def insertAccess(self, curve: Curve, allCurves: list) -> list:
        """
        Splits Curve curve to create access to inner structures, inserts it into path and rotates path to second access curve.
        curve: Curve that is supposed to contain access.
        restOfCurves: Rest of the path.
        """
        aLen = curve.Length
        startP = 1 - (2*self.D)/aLen
        endP = 1 - (self.D-2*self.R)/aLen
        accessC = [self.unwrap(c.Explode()[0]) for c in curve.TrimInteriorByParameter(startP, endP)]

        idx = allCurves.index(curve)
        allCurves = self.replace(allCurves, self.flatten(accessC),idx)
        
        return allCurves, accessC[1]
    
    def reverseCurves(self, curves: list, invert: bool=True) -> list:
        """
        Reverses all curves in a list and then reverses the list if self.redir is True.
        Inverses self.redir afterwards.
        """
        if self.layer.redir:
            revCurves = [self.unwrap(c.Reverse()) for c in curves]
            revCurves.reverse()
        else:
            revCurves = curves

        self.layer.redir = invert ^ self.layer.redir # inverts redir if invert is True
        return revCurves

    @staticmethod
    def lineAlternateEO(a: Point, b: Point, i: int) -> Line:
        if i%2:
            return Line.ByStartPointEndPoint(b,a)
        else:
            return Line.ByStartPointEndPoint(a,b)

    def equalizeSegments(self, segmentsOI: list) -> Tuple[list, list]:
        outer = segmentsOI[0]
        inner = segmentsOI[1]

        newO = []
        newI = []

        for o, i in zip(outer, inner):
            oS = o.StartPoint
            oE = o.EndPoint
            iS = i.StartPoint
            iE = i.EndPoint
            
            oSn = o.ClosestPointTo(iS)
            oEn = o.ClosestPointTo(iE)
            iSn = i.ClosestPointTo(oS)
            iEn = i.ClosestPointTo(oE)

            o = self.unwrap(o.TrimByParameter(o.ParameterAtPoint(oSn),o.ParameterAtPoint(oEn)).Explode()[0])
            i = self.unwrap(i.TrimByParameter(i.ParameterAtPoint(iSn),i.ParameterAtPoint(iEn)).Explode()[0])

            newO.append(o)
            newI.append(i)
    
        return newO, newI

    def trimSegments(self, curves: list) -> list:
        trimed = []
        for idx, s in enumerate(curves):
            pStart, pEnd = self.getTrimPars(idx, curves)
            trimedS = self.unwrap(s.TrimByParameter(pStart, pEnd).Explode()[0])
            trimed.append(trimedS)
        
        return trimed
    
    def getTrimPars(self, idx: int, segments: list) -> Tuple[float, float]:
        angle2before = 0
        angle2next = 0
        typenext = 1
        typebefore = 1

        if idx != 0:
            angle2before, typebefore = self.getCornerAngle(segments[idx-1], segments[idx])

        if idx != len(segments)-1:
            angle2next, typenext = self.getCornerAngle(segments[idx], segments[idx+1])

        delta2before = self.cornerOffset(angle2before, typebefore)
        delta2next = self.cornerOffset(angle2next, typenext)

        pStart = delta2before/segments[idx].Length
        pEnd = 1 - delta2next/segments[idx].Length

        return pStart, pEnd

    @staticmethod
    def getCornerAngle(first: Curve, second: Curve) -> Tuple[float, int]:
        v1 = first.TangentAtParameter(1)
        v2 = second.TangentAtParameter(0)
    
        angle = v1.AngleWithVector(v2)/180*np.pi
    
        if angle < 0.0001:
            angle = 0
            corner = 0 # tangent
        else:
            corner = 1 # corner
        return angle, corner
        
    @staticmethod
    def rotate(l: list, idx: int) -> list:
        """
        Rotates list l to index idx.
        """
        if l:
            idx = idx % len(l) # makes sure idx is not out of bounds
            return l[idx:] + l[:idx]
        else:
            return l
    
    @staticmethod
    def flatten(l: list) -> list:
        """
        flattens list to be onedimensional
        """
        while isinstance(l[0], list):
            l = [element for sublist in l for element in sublist]
        return l
    
    @staticmethod
    def replace(l: list, newitem: Any, idx: int) -> list:
        if not isinstance(newitem,list):
            newitem = [newitem]
        return l[:idx] + newitem + l[idx+1:]
    
class ZickZack(Pattern):
    def __init__(self) -> None:
        super().__init__()

    def setParameters(self, lH, nD, bR, NoP, pP):
        super().setParameters(lH, nD, bR, NoP, pP)
        self.nop += 1 # at least one perimeter required for ZickZack
        self.noo = self.nop + 2 # pattern needs 2 offsets extra to be built
    
    def doPathPlanning(self, layer):
        super().doPathPlanning(layer)
        perSurfs = [self.getOffset((n + 0.5)*self.D, self.R) for n in range(0,self.nop)]
        for p in perSurfs:
            self.addPerimeter(p)
        
        self.planZickZack()
    
    def addPerimeter(self, surf: Surface):
        return super().addPerimeter(surf)
    
    def filletZack(self, helpLine: Line, first: Union[Vector, Line], second: Union[Vector, Line]) -> Tuple[Arc, float]:
        if isinstance(self.layer.surface, Plane):
            pNormal = self.layer.surface.Normal
        else:
            pass # [ ]: for arbitrary surface
        
        center = helpLine.PointAtParameter(self.R/helpLine.Length)

        if isinstance(first,Vector):
            vector1 = first
            diff1 = 0
        else:
            vector1 = first.TangentAtParameter(0)
            diff1 = np.arcsin(2*self.R/first.Length)*180/np.pi
        
        if isinstance(second,Vector):
            vector2 = second
            diff2 = 0
        else:
            vector2 = second.TangentAtParameter(0)
            diff2 = np.arcsin(2*self.R/second.Length)*180/np.pi
        
        zackAngle = Vector.AngleAboutAxis(vector1, vector2, pNormal)
        
        angle1 = Vector.AngleAboutAxis(Vector.XAxis(), vector1, pNormal)
        angle2 = Vector.AngleAboutAxis(Vector.XAxis(), vector2, pNormal)
        
        if zackAngle > 180:
            corner = Arc.ByCenterPointRadiusAngle(center, self.R, angle2 + 90 - diff2, angle1 + 90 + diff1, pNormal)
            corner = corner.Reverse()
            zackAngle -= 180
        else:
            corner = Arc.ByCenterPointRadiusAngle(center, self.R ,angle1 - 90 - diff1, angle2 - 90 + diff2, pNormal)
        
        return corner, zackAngle

    def planZickZack(self):
        outer, inner, p2p, aC = self.prepareHelpCurves()

        pattern = []
        for n, (o, i) in enumerate(zip(outer, inner)):
            cTs = self.layer.corners[n]
            cTe = self.layer.corners[n+1]

            testS = (cTs == -1) or (cTs == 1)
            testE = (cTe == -1) or (cTe == 1)

            if testS:
                first = o
                second = i
            else:
                first = i
                second = o
            
            div = np.floor(o.Length/self.patternPar)
            divisions = self.unwrap(first.PointsAtEqualChordLength(div*2-int(testS == testE)))
            divisions.insert(0,self.unwrap(first.StartPoint))
            divisions.append(self.unwrap(first.EndPoint))
            otherDivisions = [self.unwrap(second.ClosestPointTo(p)) for p in divisions]

            zacks = iter(divisions[::2])
            zicks = iter(otherDivisions[1::2])
            
            zickzack = []
            a = next(zacks, -1)
            b = next(zicks, -1)
            sw = True
            while b != -1:
                l = Line.ByStartPointEndPoint(a,b)
                
                a = b
                
                if sw:
                    b = next(zacks, -1)
                else:
                    b = next(zicks, -1)
                
                sw = not(sw)
                
                zickzack.append(l)
            
            if self.R:
                helpLines = [self.lineAlternateEO(a,b,j) for j, (a,b) in enumerate(zip(divisions,otherDivisions))]
                noz = len(helpLines) # number of zacks
                
                if cTs == -1:
                    firstVec = first.TangentAtParameter(0)
                else:
                    firstVec = Vector.ByTwoPoints(outer[n-1].EndPoint,o.StartPoint)
                
                corner, zackAngle = self.filletZack(helpLines[0], firstVec, zickzack[0])
                
                newZickzack = [corner]
                zackAngles = [zackAngle]
                
                for j in range(1,noz-1):
                    corner, zackAngle = self.filletZack(helpLines[j], zickzack[j-1], zickzack[j])
                    
                    line = Line.ByStartPointEndPoint(newZickzack[-1].EndPoint,corner.StartPoint)
                    
                    newZickzack.append(line)
                    newZickzack.append(corner)
                    zackAngles.append(zackAngle)
                
                if cTe == -1:
                    lastVec = first.TangentAtParameter(1)
                else:
                    lastVec = Vector.ByTwoPoints(o.EndPoint,outer[n+1].StartPoint)
                    
                corner, zackAngle = self.filletZack(helpLines[-1], zickzack[-1], lastVec)
                
                line = Line.ByStartPointEndPoint(newZickzack[-1].EndPoint, corner.StartPoint)
                
                newZickzack.append(line)
                newZickzack.append(corner)
                zackAngles.append(zackAngle)
                
                zickzack = newZickzack
                
            if cTs != -1:
                pattern.append(Line.ByStartPointEndPoint(pattern[-1].EndPoint,zickzack[0].StartPoint))

            pattern.extend(zickzack)
        
        p2p.append(self.unwrap(Line.ByStartPointEndPoint(p2p[-1].EndPoint,pattern[0].StartPoint)))
        p2p.extend(pattern)

        self.connect2path(p2p, [p2p[0], aC], False)

class Lamella(Pattern): # [ ]: implement Lamella
    def __init__(self) -> None:
        super().__init__()

class Honeycomb(Pattern): # [ ]: implement Honeycomb
    def __init__(self) -> None:
        super().__init__()