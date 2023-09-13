"""
This modules contains a powerful class called JordanCurve which
is in fact, stores a list of spline-curves.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Optional, Tuple, Union

import numpy as np

from compmec.shape.curve import IntegratePlanar, PlanarCurve
from compmec.shape.polygon import Box, Point2D


class IntersectionBeziers:
    tol_du = 1e-9  # tolerance convergence
    tol_norm = 1e-9  # tolerance convergence
    max_denom = math.ceil(1 / tol_du)

    @staticmethod
    def is_equal_controlpoints(cptsa: Tuple[Point2D], cptsb: Tuple[Point2D]) -> bool:
        if len(cptsa) != len(cptsb):
            return False
        for pta, ptb in zip(cptsa, cptsb):
            if pta != ptb:
                return False
        return True

    @staticmethod
    def eval_bezier(degree: int, node: float) -> Tuple[float]:
        """
        Returns [B_p(u)] = [B_{0p}(u) ... B_{pp}(u)]
        With
            B_{ip} = binom(p, i) * (1-u)^{p-i} * u^i
        """
        comp = 1 - node
        result = [0] * (degree + 1)
        for i in range(degree + 1):
            result[i] = math.comb(degree, i) * comp ** (degree - i) * node**i
        return tuple(result)

    @staticmethod
    def matrix_derivate(degree: int) -> Tuple[Tuple[int]]:
        """
        Let A(u) be a nonrational-bezier curve defined by
            A(u) = sum_{i=0}^{p} B_{ip}(u) * P_{i}
        We want to compute the derivative A'(u)

        This function returns a matrix [M] such
            A'(u) = sum_{i=0}^{p} B_{ip}(u) * Q_{i}
            Q_{i} = sum_{j=0}^{p} M_{i,j} * P_j

        Where
            B_{ip}(u) = binom(p, i) * (1-u)^{p-i} * u^i
        """
        matrix = np.zeros((degree + 1, degree + 1), dtype="int16")
        for i in range(degree):
            matrix[i, i + 1] = degree - i
            matrix[i + 1, i] = -(i + 1)
        for i in range(degree + 1):
            matrix[i, i] = 2 * i - degree
        return tuple([tuple(line) for line in matrix])

    @staticmethod
    def intersection_bezier(
        cptsa: Tuple[Point2D], cptsb: Tuple[Point2D]
    ) -> Tuple[Tuple[float]]:
        """
        Returns the intersection parameters of the intersection of two bezier curves.

        Given two bezier curves A(u) and B(v), this function returns the pairs (u*, t*)
        such A(u*) = B(v*). As there can be many intersections, returns
            [(u0*, t0*), ..., (un*, tn*)]

        If one curve is equal to another, returns a empty tuple
        if there's no intersection, returns a empty tuple
        """
        tol_du = IntersectionBeziers.tol_du
        if IntersectionBeziers.is_equal_controlpoints(cptsa, cptsb):
            return ((None, None),)
        dega = len(cptsa) - 1
        degb = len(cptsb) - 1
        dmata = np.array(IntersectionBeziers.matrix_derivate(dega))
        dmatb = np.array(IntersectionBeziers.matrix_derivate(degb))

        cptsa = np.array(cptsa)
        cptsb = np.array(cptsb)
        dcptsa = dmata @ cptsa
        ddcptsa = dmata @ dcptsa
        dcptsb = dmatb @ cptsb
        ddcptsb = dmatb @ dcptsb

        pts_ada = np.tensordot(cptsa, dcptsa, axes=0)
        pts_adb = np.tensordot(cptsa, dcptsb, axes=0)
        pts_bda = np.tensordot(cptsb, dcptsa, axes=0)
        pts_bdb = np.tensordot(cptsb, dcptsb, axes=0)
        pts_adda = np.tensordot(cptsa, ddcptsa, axes=0)
        pts_addb = np.tensordot(cptsa, ddcptsb, axes=0)
        pts_bdda = np.tensordot(cptsb, ddcptsa, axes=0)
        pts_bddb = np.tensordot(cptsb, ddcptsb, axes=0)
        pts_dada = np.tensordot(dcptsa, dcptsa, axes=0)
        pts_dadb = np.tensordot(dcptsa, dcptsb, axes=0)
        pts_dbdb = np.tensordot(dcptsb, dcptsb, axes=0)

        nptas, nptbs = dega + 3, degb + 3
        usample = [Fraction(i) / nptbs for i in range(nptas + 1)]
        vsample = [Fraction(i) / nptbs for i in range(nptbs + 1)]

        intersections = set()
        for i in range(nptas + 1):
            for j in range(nptbs + 1):
                ui = usample[i]
                vj = vsample[j]
                # Starts newton iteration
                for k in range(10):  # Number of newton iterations
                    aui = IntersectionBeziers.eval_bezier(dega, ui)
                    bvj = IntersectionBeziers.eval_bezier(degb, vj)
                    ada = aui @ pts_ada @ aui
                    adb = aui @ pts_adb @ bvj
                    bda = bvj @ pts_bda @ aui
                    bdb = bvj @ pts_bdb @ bvj
                    adda = aui @ pts_adda @ aui
                    addb = aui @ pts_addb @ bvj
                    bdda = bvj @ pts_bdda @ aui
                    bddb = bvj @ pts_bddb @ bvj
                    dada = aui @ pts_dada @ aui
                    dadb = aui @ pts_dadb @ bvj
                    dbdb = bvj @ pts_dbdb @ bvj

                    mat00 = dbdb + bddb - addb
                    mat11 = dada + adda - bdda
                    vec0 = ada - bda
                    vec1 = bdb - adb
                    denom = mat00 * mat11 - dadb**2
                    if denom == 0:
                        ui, vj = float("inf"), float("inf")
                        break
                    oldui = ui
                    oldvj = vj
                    ui -= (mat00 * vec0 + dadb * vec1) / denom
                    vj -= (dadb * vec0 + mat11 * vec1) / denom
                    if isinstance(ui, Fraction):
                        ui = ui.limit_denominator(IntersectionBeziers.max_denom)
                    if isinstance(vj, Fraction):
                        vj = vj.limit_denominator(IntersectionBeziers.max_denom)
                    ui = min(1, max(0, ui))
                    vj = min(1, max(0, vj))

                    if abs(oldui - ui) > tol_du:
                        continue
                    if abs(oldvj - vj) > tol_du:
                        continue
                    break
                if ui < 0 or 1 < ui or vj < 0 or 1 < vj:
                    continue
                intersections.add((ui, vj))
        filter_inters = set()
        for ui, vj in intersections:
            for uk, vl in filter_inters:
                if abs(ui - uk) < tol_du and abs(vj - vl) < tol_du:
                    break
            else:
                filter_inters.add((ui, vj))
        for ui, vj in tuple(filter_inters):
            aui = IntersectionBeziers.eval_bezier(dega, ui)
            bvj = IntersectionBeziers.eval_bezier(degb, vj)
            pta = aui @ cptsa
            ptb = bvj @ cptsb
            norm = abs(pta - ptb)
            if norm > IntersectionBeziers.tol_norm:
                filter_inters.remove((ui, vj))
        filter_inters = tuple(filter_inters)
        return filter_inters


class IntegrateJordan:
    @staticmethod
    def horizontal(
        jordan: JordanCurve, expx: int, expy: int, nnodes: Optional[int] = None
    ):
        """
        Computes the integral I

        I = int x^expx * y^expy * dx
        """
        assert isinstance(jordan, JordanCurve)
        assert isinstance(expx, int)
        assert isinstance(expy, int)
        assert nnodes is None or isinstance(nnodes, int)
        total = 0
        for bezier in jordan.segments:
            total += IntegratePlanar.horizontal(bezier, expx, expy, nnodes)
        return total

    @staticmethod
    def vertical(
        jordan: JordanCurve, expx: int, expy: int, nnodes: Optional[int] = None
    ):
        """
        Computes the integral I

        I = int x^expx * y^expy * dy
        """
        assert isinstance(jordan, JordanCurve)
        assert isinstance(expx, int)
        assert isinstance(expy, int)
        assert nnodes is None or isinstance(nnodes, int)
        total = 0
        for bezier in jordan.segments:
            total += IntegratePlanar.vertical(bezier, expx, expy, nnodes)
        return total

    @staticmethod
    def polynomial(
        jordan: JordanCurve, expx: int, expy: int, nnodes: Optional[int] = None
    ):
        """
        Computes the integral

        I = int x^expx * y^expy * ds
        """
        assert isinstance(jordan, JordanCurve)
        assert nnodes is None or isinstance(nnodes, int)
        total = 0
        for bezier in jordan.segments:
            total += IntegratePlanar.polynomial(bezier, expx, expy, nnodes)
        return total

    @staticmethod
    def lenght(jordan: JordanCurve, nnodes: Optional[int] = None) -> float:
        """
        Computes the lenght of jordan curve
        """
        assert isinstance(jordan, JordanCurve)
        assert nnodes is None or isinstance(nnodes, int)
        lenght = 0
        for bezier in jordan.segments:
            lenght += IntegratePlanar.lenght(bezier, nnodes)
        return lenght

    @staticmethod
    def area(jordan: JordanCurve, nnodes: Optional[int] = None) -> float:
        """
        Computes the interior area from jordan curve
        """
        assert isinstance(jordan, JordanCurve)
        assert nnodes is None or isinstance(nnodes, int)
        area = 0
        for bezier in jordan.segments:
            area += IntegratePlanar.area(bezier, nnodes)
        return area

    @staticmethod
    def winding_number(
        jordan: JordanCurve, nnodes: Optional[int] = None
    ) -> Union[int, float]:
        """Computes the winding number from jordan curve

        Returns [-1, 0, 0.5 or 1]
        """
        wind = 0
        for bezier in jordan.segments:
            if (0, 0) in bezier:  # point in boundary
                return 0.5
        for bezier in jordan.segments:
            wind += IntegratePlanar.winding_number(bezier, nnodes)
        wind = round(wind)
        return wind


class JordanCurve:
    """
    Jordan Curve is an arbitrary closed curve which doesn't intersect itself.
    It stores a list of 'segments', each segment is a bezier curve
    """

    def __init__(self):
        self.__segments = None
        self.__lenght = None

    @classmethod
    def from_segments(cls, beziers: Tuple[PlanarCurve]) -> JordanCurve:
        assert isinstance(beziers, (tuple, list))
        for bezier in beziers:
            assert isinstance(bezier, PlanarCurve)
        instance = cls()
        instance.segments = beziers
        return instance

    @classmethod
    def from_vertices(cls, vertices: Tuple[Point2D]) -> JordanCurve:
        if isinstance(vertices, str):
            raise TypeError
        vertices = list(vertices)
        for i, vertex in enumerate(vertices):
            vertices[i] = Point2D(vertex)
        nverts = len(vertices)
        vertices.append(vertices[0])
        beziers = [0] * nverts
        for i in range(nverts):
            ctrlpoints = vertices[i : i + 2]
            new_bezier = PlanarCurve(ctrlpoints)
            beziers[i] = new_bezier
        return cls.from_segments(beziers)

    def copy(self) -> JordanCurve:
        segments = tuple(segment.copy() for segment in self.segments)
        return self.__class__.from_segments(segments)

    def clean(self) -> JordanCurve:
        for segment in self.segments:
            segment.clean()
        segments = list(self.segments)
        while True:
            nsegments = len(segments)
            for i in range(nsegments):
                j = (i + 1) % nsegments
                seg0 = segments[i]
                seg1 = segments[j]
                try:
                    segment = PlanarCurve.unite([seg0, seg1])
                    segments[i] = segment
                    segments.pop(j)
                    break  # Can unite
                except ValueError:
                    pass  # Cannot unite
            else:
                break
        self.segments = segments
        return self

    def move(self, point: Point2D) -> JordanCurve:
        for vertex in self.vertices:
            vertex.move(point)
        return self

    def scale(self, xscale: float, yscale: float) -> JordanCurve:
        float(xscale)
        float(yscale)
        for vertex in self.vertices:
            vertex.scale(xscale, yscale)
        return self

    def rotate(self, angle: float, degrees: bool = False) -> JordanCurve:
        float(angle)
        if degrees:
            angle *= np.pi / 180
        for vertex in self.vertices:
            vertex.rotate(angle)
        return self

    def invert(self) -> JordanCurve:
        """
        Invert the orientation of a jordan curve
        """
        segments = self.segments
        nsegs = len(segments)
        new_segments = []
        for i in range(nsegs - 1, -1, -1):
            new_segments.append(segments[i].invert())
        self.segments = tuple(new_segments)
        return self

    def split(self, indexs: Tuple[int], nodes: Tuple[float]) -> None:
        """
        Divides a list of segments in the respective nodes
        If node == 0 or node == 1 (extremities), only ignores
        the given node
        """
        assert isinstance(indexs, (tuple, list))
        assert isinstance(nodes, (tuple, list))
        for index in indexs:
            assert isinstance(index, int)
            assert 0 <= index
            assert index < len(self.segments)
        for node in nodes:
            float(node)
            assert 0 <= node
            assert node <= 1
        assert len(indexs) == len(nodes)
        indexs = list(indexs)
        new_segments = list(self.segments)
        inserted = 0
        for index, node in zip(indexs, nodes):
            if abs(node) < 1e-6 or abs(node - 1) < 1e-6:
                continue
            segment = new_segments[index + inserted]
            bezleft, bezrigh = segment.split([node])
            new_segments[index + inserted] = bezleft
            new_segments.insert(index + inserted + 1, bezrigh)
            inserted += 1
        self.segments = tuple(new_segments)

    def points(self, subnpts: Optional[int] = 2) -> Tuple[Point2D]:
        """
        Returns a list of points on the boundary.
        Main reason: plot the jordan
        You can choose the precision by changing the ```subnpts``` parameter

        subnpts = 1 -> midpoint
        subnpts = 2 -> extremities
        subnpts = 3 -> extremities + midpoints
        """
        assert isinstance(subnpts, int)
        all_points = []
        for segment in self.segments:
            usample = np.linspace(0, 1, subnpts, endpoint=False)
            all_points += list(segment.eval(usample))
        all_points.append(all_points[0])
        return tuple(all_points)

    def box(self) -> Box:
        """Gives two points which encloses the jordan curve"""
        inf = float("inf")
        box = Box(Point2D(inf, inf), Point2D(-inf, -inf))
        for bezier in self.segments:
            box |= bezier.box()
        return box

    @property
    def lenght(self) -> float:
        if self.__lenght is None:
            lenght = IntegrateJordan.lenght(self)
            area = IntegrateJordan.area(self)
            self.__lenght = lenght if area > 0 else -lenght
        return self.__lenght

    @property
    def segments(self) -> Tuple[PlanarCurve]:
        return tuple(self.__segments)

    @property
    def vertices(self) -> Tuple[Point2D]:
        """
        Returns a tuple of non repeted points
        """
        if self.__vertices is None:
            vertices = []
            for segment in self.segments:
                for point in segment.ctrlpoints:
                    if point not in vertices:
                        vertices.append(point)
            self.__vertices = tuple(vertices)
        return self.__vertices

    @segments.setter
    def segments(self, other: Tuple[PlanarCurve]):
        assert isinstance(other, (tuple, list))
        for segment in other:
            if not isinstance(segment, PlanarCurve):
                raise TypeError
        ncurves = len(other)
        for i in range(ncurves - 1):
            end_point = other[i].ctrlpoints[-1]
            start_point = other[i + 1].ctrlpoints[0]
            assert start_point == end_point
        for segment in other:
            segment.clean()
        self.__lenght = None
        self.__vertices = None
        segments = []
        for bezier in other:
            ctrlpoints = [Point2D(point) for point in bezier.ctrlpoints]
            new_bezier = PlanarCurve(ctrlpoints)
            segments.append(new_bezier)
        self.__segments = tuple(segments)

    def __and__(self, other: JordanCurve) -> Tuple[Tuple[int, int, float, float]]:
        """
        Given two jordan curves, this functions returns the intersection
        between these two jordan curves
        Returns empty tuple if the curves don't intersect each other
        """
        return self.intersection(other, equal_beziers=False, end_points=False)

    def __str__(self) -> str:
        max_degree = max(curve.degree for curve in self.segments)
        msg = f"Jordan Curve of degree {max_degree} and vertices\n"
        msg += str(self.vertices)
        return msg

    def __repr__(self) -> str:
        max_degree = max(curve.degree for curve in self.segments)
        msg = "JordanCurve (deg %d, nsegs %d)"
        msg %= max_degree, len(self.segments)
        return msg

    def __eq__(self, other: JordanCurve) -> bool:
        assert isinstance(other, JordanCurve)
        for point in other.points(1):
            if point not in self:
                return False
        selcopy = self.copy().clean()
        othcopy = other.copy().clean()
        if len(selcopy.segments) != len(othcopy.segments):
            return False
        segment1 = othcopy.segments[0]
        for index, segment0 in enumerate(selcopy.segments):
            if segment0 == segment1:
                break
        else:
            return False
        nsegments = len(self.segments)
        for i, segment1 in enumerate(othcopy.segments):
            segment0 = selcopy.segments[(i + index) % nsegments]
            if segment0 != segment1:
                return False
        return True

    def __ne__(self, other: JordanCurve) -> bool:
        return not self.__eq__(other)

    def __invert__(self) -> JordanCurve:
        return self.copy().invert()

    def __contains__(self, point: Point2D) -> bool:
        """
        Tells if the point is on the boundary
        """
        if point not in self.box():
            return False
        for bezier in self.segments:
            if point in bezier:
                return True
        return False

    def __float__(self) -> float:
        return self.lenght

    def __abs__(self) -> JordanCurve:
        """
        Returns the same curve, but in positive direction
        """
        return self.copy() if float(self) > 0 else (~self)

    def intersection(
        self, other: JordanCurve, equal_beziers: bool = True, end_points: bool = True
    ) -> Tuple[Tuple[int, int, float, float]]:
        """
        Returns the intersection between two curves A and B
        result = ((a0, b0, u0, v0), (a1, b1, u1, v1), ...)
        Which
            A.segments[ai].eval(ui) == B.segments[bi].eval(vi)
        0 <= ai < len(A.segments)
        0 <= bi < len(B.segments)
        0 <= u0 <= 1
        0 <= v0 <= 1
        """
        assert isinstance(other, JordanCurve)
        bandb = IntersectionBeziers.intersection_bezier
        intersections = set()
        for ai, sbezier in enumerate(self.segments):
            for bj, obezier in enumerate(other.segments):
                inters = bandb(sbezier.ctrlpoints, obezier.ctrlpoints)
                for item in inters:
                    ui, vj = item
                    intersections.add((ai, bj, ui, vj))
        if not equal_beziers:
            for ai, bi, ui, vi in tuple(intersections):
                if ui is None:
                    intersections.remove((ai, bi, ui, vi))
        if not end_points:
            for ai, bi, ui, vi in tuple(intersections):
                if ui is None or (0 < ui and ui < 1) or (0 < vi and vi < 1):
                    continue
                intersections.remove((ai, bi, ui, vi))
        return tuple(sorted(intersections))
