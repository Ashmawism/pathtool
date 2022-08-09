import clr
from typing import Any, Union, Tuple

clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import *

import numpy as np
#import ifcopenshell as ifc

class Layer:
    """
    Layer class:
    Stores layer surfaces, print path and speed profile.
    Class attributes store general data applicable for all layers.
    """
    unwrap = None # unwrap function passed from built-in python
    H = 0 # usr setting layer height
    D = 0 # usr setting nozzle diameter
    R = 0 # usr setting blend radius
    nop = 0 # Number of extra perimeters
    pattern = "" # usr setting infill pattern
    patternPar = 0.5 # parameter for pattern
    ref = Point.ByCoordinates(0, 0.5, 0) # reference point, used to determine start curve.
    count = 0 # amount of layers
    inst = [] # registered layers (layers can access other layers)
    offsets = {} # stores offsets of perimeter surfaces
    
    def __init__(self):
        self.path = [] # tool path for print
        self.polyPath = None
        self.speed = None # speed profile
        self.surface = None # contains layer surface (Plane for planar layers, NURBS surface for non-planar)
        self.perimeter = None # stores outer perimeter as list of Curve
        self.PolyPerimeter = None # stores outer perimeter as PolyCurve
        self.sides = [] # list for sides
        self.corners = [] # list for corner types
        self.origin = None # origin of layer surface
        self.redir = False # reverse direction of intersection.
        self.test = None # just for testing
        
        self.count = Layer.count # layer ID
        Layer.inst.append(self) # registering self
        Layer.count += 1 # counting Layers
        self.height = Layer.count * Layer.H # Sets layer height for individual layers
        # for non-planar layers height will refer to the max Z of its bounding box.
    
    def get_noc(self) -> int: 
        return len(self.path)

    @classmethod
    def changeRef(cls, newRef: Point):
        """changes reference Point, to change start curve."""
        cls.ref = newRef 

    @classmethod
    def addOffset(cls, surf, dist):
        cls.offsets[f"{dist}"] = surf
    
    def defineLsurface(self, bb: BoundingBox, surf: Union[Surface, PolySurface, NurbsSurface]=None, nV: Vector=None):
        """
        defines layer surface from input.
        if surf != None -> non-planar 
        else -> planar
        nV: sets normal vector if different than vertical axis.
        bb: Bounding Box of the BIM component.
        """
        if nV == None:
            nV = Vector.ZAxis() # vertical axis
        
        if surf:
            pass # placeholder for non-planar layer definition.
        else:
            minP = bb.MinPoint
            maxP = bb.MaxPoint
            x = (minP.X + maxP.X)/2 # center x-coordinate
            y = (minP.Y + maxP.Y)/2 # center y-coordinate
            self.origin = Point.ByCoordinates(x, y, self.height) # defines origin in xy-center of the component
            self.surface = Plane.ByOriginNormal(self.origin, nV) # sets Plane at Origin with normal nV
    
    def setPerimeter(self, surf: Surface, sides: Curve):
        """
        Intersects boundary surfaces of component with layer surface to get perimeter curves for reference.
        Also determines which of the perimeter curves are sides.
        surf: boundary surface of component
        sides: side surfaces of the component
        """
        per = Layer.unwrap(self.surface.Intersect(surf))
        self.perimeter = per
        self.PolyPerimeter = per[0] # initialize Join
        
        for p in per[1:]:
            self.PolyPerimeter = self.PolyPerimeter.Join(p) # Join to PolyCurve
        
        # determine sides
        for p in per:
            for s in sides:
                t = Layer.unwrap(p.Intersect(s))
                
                if t and isinstance(t[0], type(p)): # intersection with side surface should reveil same type of curve.
                    self.sides.append(p)
        
        # determine side closest to reference point Layer.ref
        minD = 10000 # some large value
        for n,s in enumerate(self.sides):
            if s.DistanceTo(Layer.ref) < minD: # overwrite minD if smaller.
                minD = n
        
        self.sides = self.rotate(self.sides, minD) # rotate to closest side
        
    def addPerimeter(self, surf: Surface):
        """
        Adds a perimeter derived from surf to path
        surf: offset surface of BIMdata.surface
        """
        # TODO: if surf == None -> do offset of self.perimeter
        # TODO: check if perCurves are "closed" -> necessary for tilted components
        perCurves = Layer.unwrap(self.surface.Intersect(surf))
        perCurves = self.reverseCurves(perCurves)
        sides = self.identifySides(perCurves)
        aS = sides[not(self.redir)] # access side
        oS = sides[self.redir] # other side
        perCurves, aC = self.insertAccess(aS, perCurves)
        self.connect2path(perCurves, [oS, aC])
    
    def addPattern(self, getOffset):
        """
        Continues path planning with inner perimeters.
        """
        plan = getattr(self, f"plan{Layer.pattern}")
        plan(getOffset)
    
    def planZickZack(self, getOffset):
        outer, inner, p2p, aC = self.prepareHelpCurves(getOffset)

        pattern = []
        for n, (o, i) in enumerate(zip(outer, inner)):
            cTs = self.corners[n]
            cTe = self.corners[n+1]

            testS = (cTs == -1) or (cTs == 1)
            testE = (cTe == -1) or (cTe == 1)

            if testS:
                first = o
                second = i
            else:
                first = i
                second = o
            
            div = np.floor(o.Length/Layer.patternPar)
            divisions = Layer.unwrap(first.PointsAtEqualChordLength(div*2-int(testS == testE)))
            divisions.insert(0,Layer.unwrap(first.StartPoint))
            divisions.append(Layer.unwrap(first.EndPoint))
            otherDivisions = [Layer.unwrap(second.ClosestPointTo(p)) for p in divisions]

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
            
            if Layer.R:
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
        
        p2p.append(Layer.unwrap(Line.ByStartPointEndPoint(p2p[-1].EndPoint,pattern[0].StartPoint)))
        p2p.extend(pattern)

        self.connect2path(p2p, [p2p[0], aC], False)

        #print("Test zickzack")

    def planLamella(self, getOffset):
        print("Test lamella")

    def planHoneycomb(self, getOffset):
        print("Test honeycomb")
    
    def interlayerAccess(self):
        aC = self.path[0]
        newAC = [Layer.unwrap(c.Explode()[0]) for c in aC.TrimInteriorByParameter(0.25,0.75)]
    
        newAC.extend(self.path)
        newAC = self.rotate(newAC, 1)
        
        self.test = newAC


    def filletZack(self, helpLine: Line, first: Union[Vector, Line], second: Union[Vector, Line]) -> Tuple[Arc, float]:
        if isinstance(self.surface, Plane):
            pNormal = self.surface.Normal
        else:
            pass # TODO: for arbitrary surface
        
        center = helpLine.PointAtParameter(Layer.R/helpLine.Length)

        if isinstance(first,Vector):
            vector1 = first
            diff1 = 0
        else:
            vector1 = first.TangentAtParameter(0)
            diff1 = np.arcsin(2*Layer.R/first.Length)*180/np.pi
        
        if isinstance(second,Vector):
            vector2 = second
            diff2 = 0
        else:
            vector2 = second.TangentAtParameter(0)
            diff2 = np.arcsin(2*Layer.R/second.Length)*180/np.pi
        
        zackAngle = Vector.AngleAboutAxis(vector1, vector2, pNormal)
        
        angle1 = Vector.AngleAboutAxis(Vector.XAxis(), vector1, pNormal)
        angle2 = Vector.AngleAboutAxis(Vector.XAxis(), vector2, pNormal)
        
        if zackAngle > 180:
            corner = Arc.ByCenterPointRadiusAngle(center, Layer.R, angle2 + 90 - diff2, angle1 + 90 + diff1, pNormal)
            corner = corner.Reverse()
            zackAngle -= 180
        else:
            corner = Arc.ByCenterPointRadiusAngle(center, Layer.R ,angle1 - 90 - diff1, angle2 - 90 + diff2, pNormal)
        
        return corner, zackAngle

    def prepareHelpCurves(self, getOffset) -> Tuple[list, list, list, Curve]:
        start = Layer.nop + 1
        end = Layer.nop + 3
        perSurfs = [getOffset((n + 0.5)*Layer.D, Layer.R) for n in range(start, end)]

        perCurves = [Layer.unwrap(self.surface.Intersect(pS)) for pS in perSurfs]
        perCurves = [self.reverseCurves(pC) for pC in perCurves]
        
        sidesOI = [self.identifySides(pC) for pC in perCurves]
        aS = [sides[not(self.redir)] for sides in sidesOI] # access sides
        oS = [sides[self.redir] for sides in sidesOI] # other sides
        
        perCurves = [self.rotate(pC,pC.index(a)) for pC, a in zip(perCurves, aS)]
        
        path2pattern = perCurves[0][:perCurves[0].index(oS[0])+1+int(Layer.R > 0)]
        segmentsOI = [[c for c in pC[pC.index(o)+1:] if not(isinstance(c,Arc) and c.Radius - Layer.R < 0.001)] for pC, o in zip(perCurves, oS)]
        segmentsOI = [self.trimSegments(s) for s in segmentsOI]

        newouter, newinner = self.equalizeSegments(segmentsOI)

        if self.redir:
            self.corners.reverse()
        
        # combine tangent parts:
        outer = [newouter[0]]
        inner = [newinner[0]]
        for c, o, i in zip(self.corners[1:], newouter[1:],newinner[1:]):
            if c == 0: # if next curve is tangent
                outer[-1] = Layer.unwrap(outer[-1].Join(o).Reverse())
                inner[-1] = Layer.unwrap(inner[-1].Join(i).Reverse())
                
            elif c != -1:
                outer.append(o)
                inner.append(i)
        
        self.corners = [ct for ct in self.corners if ct != 0] # remove tangent type

        return outer, inner, path2pattern, oS[0]

    def connect2path(self, inner, vipC: list, removelast: bool=True):
        if self.path:
            inner = self.rotate(inner, inner.index(vipC[0]))
            startPar = Layer.D / inner[0].Length
            inner[0] = Layer.unwrap(inner[0].TrimByStartParameter(startPar).Explode()[0])

            l = Line.ByStartPointEndPoint(self.path[-1].EndPoint,inner[0].StartPoint)

            if Layer.R:
                # remove last fillet from intersection:
                if removelast:
                    _ = inner.pop(-1)
                
                # shorten and move line for first and second fillet:
                parl = Layer.R/l.Length
                l = l.TrimByParameter(parl,1-parl).Explode()[0]
                l = l.Translate(self.path[-1].TangentAtParameter(1),Layer.R)

                # line for end fillet:
                l2 = l.Translate(self.path[-1].TangentAtParameter(1),Layer.D).Reverse()

                # fillets:
                a1 = Arc.ByFillet(self.path[-1],l,Layer.R)
                a2 = Arc.ByFillet(l,inner[0],Layer.R)
                a3 = Arc.ByFillet(l2,self.path[0],Layer.R)

                # connecting end of inner path to last fillet:
                l3 = Line.ByStartPointEndPoint(inner[-1].EndPoint,a3.StartPoint)

                # outer2inner:
                self.path.append(a1)
                self.path.append(l)
                self.path.append(a2)

                # inner:
                self.path.extend(inner)

                # inner2outer:
                self.path.append(l3)
                self.path.append(a3)

            else:
                l3 = Line.ByStartPointEndPoint(inner[-1].EndPoint,self.path[0].StartPoint)
                
                # outer2inner:
                self.path.append(l)
        
                # inner:
                self.path.extend(inner)
                
                # inner2outer:
                self.path.append(l3)
        else:
            self.path = inner
        
        self.path = self.rotate(self.path, self.path.index(vipC[1]))
    
    def identifySides(self, curves: Curve) -> list:
        """
        Identifies curves of new offset corresponding to the sides
        """
        sides = []
        for s in self.sides: # for all perimeter sides
            mP = s.PointAtParameter(0.5) # center point of perimeter side
            dist = [10000, None] # some large value
            for c in curves:
                d = mP.DistanceTo(c)
                if d < dist[0]: # find closest curve to center point of perimeter side.
                    dist = [d, c]
            
            sides.append(dist[1])
        
        return sides
    
    def reverseCurves(self, curves: list, invert: bool=True) -> list:
        """
        Reverses all curves in a list and then reverses the list if self.redir is True.
        Inverses self.redir afterwards.
        """
        if self.redir:
            revCurves = [Layer.unwrap(c.Reverse()) for c in curves]
            revCurves.reverse()
        else:
            revCurves = curves

        self.redir = invert ^ self.redir # inverts redir if invert is True
        return revCurves

    def determineCurveSE(self):
        """
        Determines the Start End (SE) connection type of curves.
        """
        
        # Check corner type:
        idx = [self.perimeter.index(s) for s in self.sides]
        parts = [pC for pC in self.perimeter[min(idx)+1:max(idx)] if not(isinstance(pC,Arc) and pC.Radius - Layer.R < 0.001)]
        parts = iter(parts)
        
        curveT = [-1]
        
        prevC = next(parts, -1)
        nextC = next(parts, -1)
        
        while nextC != -1:
            angle = prevC.TangentAtParameter(1).AngleAboutAxis(nextC.TangentAtParameter(0), Vector.ZAxis())
            
            if (angle < 0.001) or (abs(angle - 360) < 0.01):
                t = 0
            elif angle > 180:
                t = 1
            else:
                t = 2
            
            curveT.append(t)
            prevC = nextC
            nextC = next(parts, -1)
        
        curveT.append(-1)
        
        self.corners = curveT

    """def createIFCentity(self, fim: ifc.file, createAxis2Placement, GUID, lPlacement):
        o = self.origin
        ownerHistory = fim.by_id(5)
        context = fim.by_id(11)
        pOrigin = fim.createIfcCartesianPoint((0.0, 0.0, o.Z))
            
        surfacePlacement = fim.createIfcAxis2Placement3D(pOrigin, None, None)
        surface = fim.createIfcPlane(surfacePlacement)
        segments = []
        for p in self.PolyPerimeter.Explode():
            segments.append(self.createIfcCurveSegment(fim, p, createAxis2Placement))
        Ccurve = fim.createIfcCompositeCurve(segments, False)
        lSurface = fim.createIfcCurveBoundedPlane(surface, Ccurve, [])
        # TODO: create composite curve on surface
        path = self.polyPath.Explode()
        pathsegments = []
        for n, c in enumerate(path):
            #if n != len(path)-1:
            pathsegments.append(self.createIfcCurveSegment(fim, c, createAxis2Placement))
            #else:
            #    segments.append(self.createIfcCurveSegment(fim, p, createAxis2Placement, 'DISCONTINUOUS'))

        pcurve = fim.createIfcCompositeCurve(pathsegments, False)

        axisRepresentation = fim.createIfcShapeRepresentation(context, "Axis", "Curve3D", [pcurve])
        bodyRepresentation = fim.createIfcShapeRepresentation(context, "Surface", "Surface3D", [lSurface])
        productShape = fim.createIfcProductDefinitionShape(None, None, [axisRepresentation, bodyRepresentation])

        return fim.createIfcBuildingElementProxy(GUID, ownerHistory, f"Layer_{self.count}", "a print layer", None, lPlacement, productShape, None, 'ELEMENT')
    """
    def createPolyPath(self):
        self.polyPath = PolyCurve.ByJoinedCurves(self.path, 0.0005)

    """    @staticmethod
    def createIfcCurveSegment(fim, curve, createAxis2Placement, transition='CONTINUOUS'):
        sP = curve.StartPoint
        eP = curve.EndPoint
        sP = fim.createIfcCartesianPoint((sP.X, sP.Y, sP.Z))
        eP = fim.createIfcCartesianPoint((eP.X, eP.Y, eP.Z))

        if isinstance(curve, Line):
            segment = fim.createIfcPolyLine([sP, eP])
        elif isinstance(curve, Arc):
            cP = curve.CenterPoint
            n = curve.Normal
            r = curve.Radius
            placement = createAxis2Placement(fim, (cP.X, cP.Y, cP.Z), (n.X, n.Y, n.Z))
            circle = fim.createIfcCircle(placement, r)
            segment = fim.createIfcTrimmedCurve(circle, [sP], [eP], True, 'CARTESIAN')
        elif isinstance(curve, NurbsCurve):
            print("spline curve")
            segment = None
        else:
            print("something went wrong")
            segment = None

        CCsegment = fim.createIfcCompositeCurveSegment(transition, True, segment)
        
        return CCsegment
    """
    
    @staticmethod
    def lineAlternateEO(a: Point, b: Point, i: int) -> Line:
        if i%2:
            return Line.ByStartPointEndPoint(b,a)
        else:
            return Line.ByStartPointEndPoint(a,b)

    @staticmethod
    def equalizeSegments(segmentsOI: list) -> Tuple[list, list]:
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

            o = Layer.unwrap(o.TrimByParameter(o.ParameterAtPoint(oSn),o.ParameterAtPoint(oEn)).Explode()[0])
            i = Layer.unwrap(i.TrimByParameter(i.ParameterAtPoint(iSn),i.ParameterAtPoint(iEn)).Explode()[0])

            newO.append(o)
            newI.append(i)
    
        return newO, newI

    @staticmethod
    def trimSegments(curves: list) -> list:
        trimed = []
        for idx, s in enumerate(curves):
            pStart, pEnd = Layer.getTrimPars(idx, curves)
            trimedS = Layer.unwrap(s.TrimByParameter(pStart, pEnd).Explode()[0])
            trimed.append(trimedS)
        
        return trimed
    
    @staticmethod
    def getTrimPars(idx: int, segments: list) -> Tuple[float, float]:
        angle2before = 0
        angle2next = 0
        typenext = 1
        typebefore = 1

        if idx != 0:
            angle2before, typebefore = Layer.getCornerAngle(segments[idx-1], segments[idx])

        if idx != len(segments)-1:
            angle2next, typenext = Layer.getCornerAngle(segments[idx], segments[idx+1])

        delta2before = Layer.cornerOffset(angle2before, typebefore)
        delta2next = Layer.cornerOffset(angle2next, typenext)

        pStart = delta2before/segments[idx].Length
        pEnd = 1 - delta2next/segments[idx].Length

        return pStart, pEnd

    @staticmethod
    def cornerOffset(angle, corner):
        if angle != 0:
            return (2*Layer.R*(1-np.cos(angle/2)) + corner*Layer.D)/(2*np.sin(angle/2)) - Layer.R
        else:
            return 0

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
    def insertAccess(curve: Curve, allCurves: list) -> list:
        """
        Splits Curve curve to create access to inner structures, inserts it into path and rotates path to second access curve.
        curve: Curve that is supposed to contain access.
        restOfCurves: Rest of the path.
        """
        aLen = curve.Length
        startP = 1 - (2*Layer.D)/aLen
        endP = 1 - (Layer.D-2*Layer.R)/aLen
        accessC = [Layer.unwrap(c.Explode()[0]) for c in curve.TrimInteriorByParameter(startP, endP)]

        idx = allCurves.index(curve)
        allCurves = Layer.replace(allCurves, Layer.flatten(accessC),idx)
        
        return allCurves, accessC[1]
        
    @staticmethod
    def rotate(l: list, idx: int) -> list:
        """
        Rotates list l to index idx.
        """
        idx = idx % len(l) # makes sure idx is not out of bounds
        if l:
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