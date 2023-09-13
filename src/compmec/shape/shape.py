"""
This modules contains all the geometry need to make any kind of shape.
You can use directly the function ```regular_polygon``` and the transformations
like ```move```, ```rotate``` and ```scale``` to model your desired curve.

You can assemble JordanCurves to create shapes with holes,
or even unconnected shapes.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Optional, Tuple, Union

import numpy as np

from compmec.shape.jordancurve import IntegrateJordan, JordanCurve
from compmec.shape.polygon import Box, Point2D


class IntegrateShape:
    @staticmethod
    def polynomial(
        shape: BaseShape, expx: int, expy: int, nnodes: Optional[int] = None
    ) -> float:
        """Computes the integral

        I = int_D x^expx * y^expy * dA

        Which D is the region defined by shape

        We transform this integral into a boundary integral

        I = (1/(1+expx)) * int_C x^(expx + 1) * y^expy * dy

        """
        assert isinstance(shape, BaseShape)
        assert isinstance(expx, int)
        assert isinstance(expy, int)
        assert nnodes is None or isinstance(nnodes, int)
        total = 0
        for jordan in shape.jordans:
            total += IntegrateJordan.vertical(jordan, expx + 1, expy, nnodes)
        return total / (1 + expx)

    @staticmethod
    def area(shape: BaseShape, nnodes: Optional[int] = None) -> float:
        return IntegrateShape.polynomial(shape, 0, 0, nnodes)


class FollowPath:
    """
    Class responsible to compute the final jordan curve
    result from boolean operation between two simple shapes

    """

    @staticmethod
    def split_at_intersections(jordana: JordanCurve, jordanb: JordanCurve):
        """
        Find the intersections between two jordan curves and call split on the
        nodes which intersects
        """
        assert isinstance(jordana, JordanCurve)
        assert isinstance(jordanb, JordanCurve)
        all_positions = (set(), set())
        inters = jordana.intersection(jordanb, end_points=False)
        for ai, bj, ui, vj in inters:
            all_positions[0].add((ai, ui))
            all_positions[1].add((bj, vj))
        all_positions = [tuple(sorted(nodes)) for nodes in all_positions]
        for positions, jordan in zip(all_positions, (jordana, jordanb)):
            indexs = [position[0] for position in positions]
            nodes = [position[1] for position in positions]
            jordan.split(indexs, nodes)

    @staticmethod
    def winding_number(jordan: JordanCurve, point: Point2D) -> int:
        """
        Computes the winding number of a point,
        It can be -1, 0 or 1
        """
        point = Point2D(point)
        copy = jordan.copy().move(-point)
        wind = IntegrateJordan.winding_number(copy)
        del copy
        return wind

    @staticmethod
    def point_inside(point: Point2D, limiters: Tuple[JordanCurve]) -> bool:
        contains = FollowPath.interior_jordan_contains_point
        for limit in limiters:
            if not contains(limit, point):
                return False
        return True

    @staticmethod
    def midpoints_inclosed(
        jordan: JordanCurve, limiters: Tuple[JordanCurve]
    ) -> Tuple[bool]:
        """
        Given two list of jordan curves, named as As and Bs, this function returns a
        matrix of booleans which tells if the midpoint of each bezier is inside a region
        defined by Bs

        len(matrix) = len(As)
        len(matrix[i]) = len(As[i].segments)
        """
        assert isinstance(jordan, JordanCurve)
        assert isinstance(limiters, (tuple, list))
        for limit in limiters:
            assert isinstance(limit, JordanCurve)
        boolvector = []
        for bezier in jordan.segments:
            mid_node = Fraction(1, 2)
            mid_point = bezier(mid_node)
            inside = Contains.point_in_closed_jordan(mid_point, limiters)
            boolvector.append(inside)
        return tuple(boolvector)

    @staticmethod
    def pursue_path(
        index_jordan: int, index_segment: int, jordans: Tuple[JordanCurve]
    ) -> Tuple[Tuple[int]]:
        """
        Given a list of jordans, it returns a matrix of integers like
        [(a1, b1), (a2, b2), (a3, b3), ..., (an, bn)] such
            End point of jordans[a_{i}].segments[b_{i}]
            Start point of jordans[a_{i+1}].segments[b_{i+1}]
        are equal

        The first point (a1, b1) = (0, index)

        The end point of jordans[an].segments[bn] is equal to
        the start point of jordans[a1].segments[b1]

        We suppose there's no triple intersection
        """
        matrix = []
        all_segments = [jordan.segments for jordan in jordans]
        while True:
            index_segment %= len(all_segments[index_jordan])
            segment = all_segments[index_jordan][index_segment]
            if (index_jordan, index_segment) in matrix:
                break
            matrix.append((index_jordan, index_segment))
            last_point = segment.ctrlpoints[-1]
            for i, jordan in enumerate(jordans):
                if i == index_jordan:
                    continue
                if last_point in jordan:
                    break
            else:
                index_segment += 1
                continue
            index_jordan = i
            for j, segj in enumerate(all_segments[index_jordan]):
                if segj.ctrlpoints[0] == last_point:
                    index_segment = j
                    break
        return tuple(matrix)

    @staticmethod
    def switch_boolean(boolvector: Tuple[bool]) -> Tuple[int]:
        """
        Given an array of booleans, it returns the index such
        boolvectors switch from False to True
        It counts as a Deck, if it switch from last element to first

        Example:
        [F, F] -> []
        [T, T] -> []
        [F, T] -> [1]
        [F, T, F] -> [1]
        [F, T, F, F] -> [1]
        [T, F] -> [0]
        [T, T, F] -> [0]
        [T, F, T, F] -> [0, 2]
        """
        nvals = len(boolvector)
        results = []
        for i in range(nvals):
            if (not boolvector[i - 1]) and boolvector[i]:
                results.append(i)
        return tuple(results)

    @staticmethod
    def is_rotation(oneobj: Tuple[Any], other: Tuple[Any]) -> bool:
        """
        Tells if a list is equal to another
        """
        assert isinstance(oneobj, (tuple, list))
        assert isinstance(other, (tuple, list))
        oneobj = tuple(oneobj)
        other = tuple(other)
        if len(oneobj) != len(other):
            return False
        rotation = 0
        for elem in oneobj:
            if elem == other[0]:
                break
            rotation += 1
        else:
            return False
        nelems = len(other)
        for i, elem in enumerate(other):
            j = (i + rotation) % nelems
            if elem != oneobj[j]:
                return False
        return True

    @staticmethod
    def filter_rotations(matrix: Tuple[Tuple[Any]]):
        """
        Remove repeted elements in matrix such they are only rotations

        Example:
        filter_tuples([[A, B, C], [B, C, A]]) -> [[A, B, C]]
        filter_tuples([[A, B, C], [C, B, A]]) -> [[A, B, C], [C, B, A]]
        """
        filtered = []
        for line in matrix:
            for fline in filtered:
                if FollowPath.is_rotation(line, fline):
                    break
            else:
                filtered.append(line)
        return tuple(filtered)

    @staticmethod
    def split_jordans(jordansa: Tuple[JordanCurve], jordansb: Tuple[JordanCurve]):
        """
        Splits a
        """
        for jordans in (jordansa, jordansb):
            assert isinstance(jordans, (tuple, list))
            for jordan in jordans:
                assert isinstance(jordan, JordanCurve)
        for jordana in jordansa:
            for jordanb in jordansb:
                if jordana & jordanb:
                    FollowPath.split_at_intersections(jordana, jordanb)

    @staticmethod
    def union_indexs(
        jordansa: Tuple[JordanCurve], jordansb: Tuple[JordanCurve]
    ) -> Tuple[Tuple[Tuple[int]]]:
        """
        Function to find indexs for union_path
        """
        FollowPath.split_jordans(jordansa, jordansb)
        final_index_matrix = []
        all_jordans = jordansa + jordansb
        for k in range(2):
            jordans0 = jordansa if k == 0 else jordansb
            jordans1 = jordansb if k == 0 else jordansa
            for local_index_jordan, jordan in enumerate(jordans0):
                insiders = FollowPath.midpoints_inclosed(jordan, jordans1)
                outsiders = [not inside for inside in insiders]
                start_indexs = FollowPath.switch_boolean(outsiders)
                global_index_jordan = k * len(jordansa) + local_index_jordan
                for index_segment in start_indexs:
                    bezindexs = FollowPath.pursue_path(
                        global_index_jordan, index_segment, all_jordans
                    )
                    final_index_matrix.append(bezindexs)
        final_index_matrix = FollowPath.filter_rotations(final_index_matrix)
        return tuple(final_index_matrix)

    @staticmethod
    def intersection_indexs(
        jordansa: Tuple[JordanCurve], jordansb: Tuple[JordanCurve]
    ) -> Tuple[Tuple[Tuple[int]]]:
        """
        Function to find indexs for intersection_path
        """
        assert isinstance(jordansa, (tuple, list))
        assert isinstance(jordansb, (tuple, list))
        FollowPath.split_jordans(jordansa, jordansb)
        final_index_matrix = []
        all_jordans = jordansa + jordansb
        for k in range(2):
            jordans0 = jordansa if k == 0 else jordansb
            jordans1 = jordansb if k == 0 else jordansa
            for local_index_jordan, jordan in enumerate(jordans0):
                insiders = FollowPath.midpoints_inclosed(jordan, jordans1)
                start_indexs = FollowPath.switch_boolean(insiders)
                global_index_jordan = k * len(jordansa) + local_index_jordan
                for index_segment in start_indexs:
                    bezindexs = FollowPath.pursue_path(
                        global_index_jordan, index_segment, all_jordans
                    )
                    final_index_matrix.append(bezindexs)
        final_index_matrix = FollowPath.filter_rotations(final_index_matrix)
        return tuple(final_index_matrix)

    @staticmethod
    def indexs_to_jordan(
        jordans: Tuple[JordanCurve], matrix_indexs: Tuple[Tuple[int, int]]
    ) -> JordanCurve:
        """
        Given 'n' jordan curves, and a matrix of integers
        [(a0, b0), (a1, b1), ..., (am, bm)]
        Returns a myjordan (JordanCurve instance) such
        len(myjordan.segments) = matrix_indexs.shape[0]
        myjordan.segments[i] = jordans[ai].segments[bi]
        """
        beziers = []
        for index_jordan, index_segment in matrix_indexs:
            new_bezier = jordans[index_jordan].segments[index_segment]
            new_bezier = new_bezier.copy()
            beziers.append(new_bezier)
        new_jordan = JordanCurve.from_segments(beziers)
        return new_jordan

    @staticmethod
    def union_path(
        jordansa: Tuple[JordanCurve], jordansb: Tuple[JordanCurve]
    ) -> Tuple[JordanCurve]:
        """
        Returns a list of jordan curves which is the result
        of the union between 'jordansa' and 'jordansb'
        """
        assert isinstance(jordansa, (tuple, list))
        assert isinstance(jordansb, (tuple, list))
        for jordan in jordansa:
            assert isinstance(jordan, JordanCurve)
        for jordan in jordansb:
            assert isinstance(jordan, JordanCurve)
        all_matrices_indexs = FollowPath.union_indexs(jordansa, jordansb)
        all_jordans = jordansa + jordansb
        new_jordans = []
        for matrix_indexs in all_matrices_indexs:
            jordan = FollowPath.indexs_to_jordan(all_jordans, matrix_indexs)
            new_jordans.append(jordan)
        return tuple(new_jordans)

    @staticmethod
    def intersection_path(
        jordansa: Tuple[JordanCurve], jordansb: Tuple[JordanCurve]
    ) -> Tuple[JordanCurve]:
        """
        Returns a list of jordan curves which is the result
        of the intersection between 'jordansa' and 'jordansb'
        """
        assert isinstance(jordansa, (tuple, list))
        assert isinstance(jordansb, (tuple, list))
        for jordan in jordansa:
            assert isinstance(jordan, JordanCurve)
        for jordan in jordansb:
            assert isinstance(jordan, JordanCurve)
        all_matrices_indexs = FollowPath.intersection_indexs(jordansa, jordansb)
        all_jordans = jordansa + jordansb
        new_jordans = []
        for matrix_indexs in all_matrices_indexs:
            jordan = FollowPath.indexs_to_jordan(all_jordans, matrix_indexs)
            new_jordans.append(jordan)
        return tuple(new_jordans)


class Contains:
    @staticmethod
    def point_at_jordan(point: Point2D, jordans: Tuple[JordanCurve]) -> bool:
        assert isinstance(point, Point2D)
        assert isinstance(jordans, (list, tuple))
        for jordan in jordans:
            assert isinstance(jordan, JordanCurve)
        for jordan in jordans:
            if point in jordan:
                return True
        return False

    @staticmethod
    def point_in_open_jordan(point: Point2D, jordans: Tuple[JordanCurve]) -> bool:
        assert isinstance(point, Point2D)
        assert isinstance(jordans, (list, tuple))
        for jordan in jordans:
            assert isinstance(jordan, JordanCurve)
        for jordan in jordans:
            wind = FollowPath.winding_number(jordan, point)
            if float(jordan) > 0 and wind != 1:
                return False
            if float(jordan) < 0 and wind != 0:
                return False
        return True

    @staticmethod
    def point_in_closed_jordan(point: Point2D, jordan: JordanCurve) -> bool:
        if Contains.point_at_jordan(point, jordan):
            return True
        return Contains.point_in_open_jordan(point, jordan)


class BaseShape(object):
    """
    Class which allows operations like:
     - move
     - scale
     - rotation
     - invert
     - union
     - intersection
     - XOR
    """

    def __init__(self):
        pass

    def __neg__(self) -> BaseShape:
        return ~self

    def __add__(self, other: BaseShape):
        return self | other

    def __mul__(self, value: BaseShape):
        return self & value

    def __xor__(self, other: BaseShape):
        return (self - other) | (other - self)

    def __bool__(self) -> bool:
        """
        Returns True if the curve's is positive
        Else if curve's area is negative
        """
        return float(self) > 0

    def move(self, point: Point2D) -> BaseShape:
        point = Point2D(point)
        for jordan in self.jordans:
            jordan.move(point)
        return self

    def scale(self, xscale: float, yscale: float) -> BaseShape:
        for jordan in self.jordans:
            jordan.scale(xscale, yscale)
        return self

    def rotate(self, angle: float, degrees: bool = False) -> BaseShape:
        for jordan in self.jordans:
            jordan.rotate(angle, degrees)
        return self


class EmptyShape(BaseShape):
    """
    A class to represent a empty shape, the zero element
    """

    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(EmptyShape, cls).__new__(cls)
        return cls.__instance

    def __or__(self, other: BaseShape) -> BaseShape:
        return other.copy()

    def __and__(self, other: BaseShape) -> BaseShape:
        return self

    def __sub__(self, other: BaseShape) -> BaseShape:
        return self

    def __float__(self) -> float:
        return float(0)

    def __invert__(self) -> BaseShape:
        return WholeShape()

    def __contains__(self, other: BaseShape) -> bool:
        return self is other

    def __str__(self) -> str:
        return "EmptyShape"

    def __repr__(self) -> str:
        return self.__str__()

    def copy(self) -> BaseShape:
        return self


class WholeShape(BaseShape):
    """
    A class to represent a empty shape, the zero element
    """

    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(WholeShape, cls).__new__(cls)
        return cls.__instance

    def __or__(self, other: BaseShape) -> BaseShape:
        return self

    def __and__(self, other: BaseShape) -> BaseShape:
        return other.copy()

    def __float__(self) -> float:
        return float("inf")

    def __invert__(self) -> BaseShape:
        return EmptyShape()

    def __contains__(self, other: BaseShape) -> bool:
        return True

    def __str__(self) -> str:
        return "WholeShape"

    def __repr__(self) -> str:
        return self.__str__()

    def __sub__(self, other: BaseShape) -> BaseShape:
        if isinstance(other, EmptyShape):
            return self
        if isinstance(other, WholeShape):
            return EmptyShape()
        if isinstance(other, SimpleShape):
            return ConnectedShape(WholeShape(), [other])
        if isinstance(other, ConnectedShape):
            outside = WholeShape() - other.positive
            return DisjointShape([outside] + other.holes)
        raise NotImplementedError

    def copy(self) -> BaseShape:
        return self


class FiniteShape(BaseShape):
    def __init__(self, *args, **kwargs):
        self.__box = None

    def __invert__(self) -> BaseShape:
        return WholeShape() - self

    def copy(self) -> FiniteShape:
        jordans = tuple(jordan.copy() for jordan in self.jordans)
        return ShapeFromJordans(jordans)

    def box(self) -> Box:
        if self.__box is None:
            box = self.jordans[0].box()
            for jordan in self.jordans[1:]:
                box |= jordan.box()
            self.__box = box
        return self.__box

    def __or__(self, other: BaseShape) -> BaseShape:
        assert isinstance(other, BaseShape)
        if isinstance(other, WholeShape):
            return WholeShape()
        if isinstance(other, EmptyShape):
            return self.copy()
        jordansa = tuple(self.jordans)
        jordansb = tuple(other.jordans)
        new_jordans = FollowPath.union_path(jordansa, jordansb)
        return ShapeFromJordans(new_jordans)

    def __and__(self, other: BaseShape) -> BaseShape:
        assert isinstance(other, BaseShape)
        if isinstance(other, WholeShape):
            return self.copy()
        if isinstance(other, EmptyShape):
            return EmptyShape()
        jordansa = tuple(self.jordans)
        jordansb = tuple(other.jordans)
        new_jordans = FollowPath.intersection_path(jordansa, jordansb)
        return ShapeFromJordans(new_jordans)

    def __sub__(self, other: BaseShape) -> BaseShape:
        assert isinstance(other, BaseShape)
        if isinstance(other, WholeShape):
            return EmptyShape()
        if isinstance(other, EmptyShape):
            return self.copy()
        jordansa = tuple(self.jordans)
        jordansb = tuple(~jordan for jordan in other.jordans)
        new_jordans = FollowPath.intersection_path(jordansa, jordansb)
        return ShapeFromJordans(new_jordans)


class SimpleShape(FiniteShape):
    """
    Simple class shape which is defined by only one jordan curve
    Example:
        - Interior of a circle, which jordan is in fact a circle
        - Interior of a polygon, which jordan are the edges
        - Exterior of a circle, when the jordan is a negative circle
    """

    def __init__(self, jordancurve: JordanCurve):
        assert isinstance(jordancurve, JordanCurve)
        super().__init__()
        self.jordancurve = jordancurve

    def __str__(self) -> str:
        area = float(self)
        vertices = self.jordancurve.vertices
        vertices = tuple([tuple(vertex) for vertex in vertices])
        msg = f"Simple Shape of area {area:.2f} with vertices:\n"
        msg += str(np.array(vertices, dtype="float64"))
        return msg

    def __repr__(self) -> str:
        area, vertices = float(self), self.jordancurve.vertices
        msg = f"Simple shape of area {area:.2f} with {len(vertices)} vertices"
        return msg

    def __float__(self) -> float:
        return float(self.__area)

    def __eq__(self, other: BaseShape) -> bool:
        if not isinstance(other, BaseShape):
            raise ValueError
        if not isinstance(other, SimpleShape):
            return False
        return self.jordancurve == other.jordancurve

    def __or__(self, other: BaseShape) -> BaseShape:
        assert isinstance(other, BaseShape)
        if not isinstance(other, SimpleShape):
            return other | self
        if self in other:
            return other.copy()
        if other in self:
            return self.copy()
        new_jordans = FollowPath.union_path([self.jordancurve], [other.jordancurve])
        simple_shapes = [SimpleShape(jordan) for jordan in new_jordans]
        return DisjointShape(simple_shapes)

    def __and__(self, other: BaseShape) -> BaseShape:
        assert isinstance(other, BaseShape)
        if not isinstance(other, SimpleShape):
            return other & self
        if self in other:
            return self.copy()
        if other in self:
            return other.copy()
        intersect = self.jordancurve.intersection(other.jordancurve, end_points=True)
        if not intersect:
            return EmptyShape()

        new_jordans = FollowPath.intersection_path(
            [self.jordancurve], [other.jordancurve]
        )
        simple_shapes = [SimpleShape(jordan) for jordan in new_jordans]
        assert len(simple_shapes) == 1
        return simple_shapes[0]

    def __contains__(self, object: Union[Point2D, JordanCurve, BaseShape]) -> bool:
        if isinstance(object, BaseShape):
            return self.contains_shape(object)
        if isinstance(object, JordanCurve):
            return self.contains_jordan_curve(object)
        point = Point2D(object)
        return self.contains_point(point)

    @property
    def jordans(self) -> JordanCurve:
        return (self.__jordancurve,)

    @property
    def jordancurve(self) -> JordanCurve:
        return self.__jordancurve

    @jordancurve.setter
    def jordancurve(self, other: JordanCurve):
        assert isinstance(other, JordanCurve)
        if other.lenght < 0:
            raise ValueError("Simple Shape area must be always positive!")
        self.__jordancurve = other.copy()
        self.__area = IntegrateShape.area(self)

    def interior_point(self) -> Point2D:
        """Gives an interior point inside the SimpleShape"""
        vertices = self.jordancurve.vertices
        while True:
            poids = np.random.randint(1, 10, len(vertices))
            sumpoids = sum(poids)
            poids = tuple(Fraction(poid, sumpoids) for poid in poids)
            point = sum(map(np.prod, zip(poids, vertices)), Point2D(0, 0))
            if point not in self.jordancurve and point in self:
                return point

    def contains_point(self, point: Point2D) -> bool:
        """
        We compute the winding number to determine if
        the point is inside the region.
        Uses numerical integration
        See wikipedia for details.
        """
        point = Point2D(point)
        if point not in self.box():
            return False
        jordan = self.jordancurve
        if point in jordan:  # point in boundary
            return True
        wind = FollowPath.winding_number(jordan, point)
        return wind == 1 if float(jordan) > 0 else wind == 0

    def contains_jordan_curve(self, other: JordanCurve) -> bool:
        assert isinstance(other, JordanCurve)
        for point in other.points(1):
            if not self.contains_point(point):
                return False
        return True

    def contains_shape(self, other: BaseShape) -> bool:
        assert isinstance(other, BaseShape)
        if isinstance(other, EmptyShape):
            return True
        if isinstance(other, WholeShape):
            return False
        if isinstance(other, SimpleShape):
            return self.contains_jordan_curve(other.jordancurve)
        if isinstance(other, ConnectedShape):
            return self.contains_shape(other.positive)
        # Disjoint shape
        for subshape in other.subshapes:
            if not self.contains_shape(subshape):
                return False
        return True


class ConnectedShape(FiniteShape):
    """
    Class of connected shape
    This class stores, for example

        circle(radius = 2) - circle(radius = 1)

    Also stores the inversion of a simple shape

    """

    def __new__(
        cls, positive: Union[WholeShape, SimpleShape], holes: Tuple[SimpleShape]
    ):
        assert isinstance(positive, (WholeShape, SimpleShape))
        holes = list(holes)
        while EmptyShape() in holes:
            holes.remove(EmptyShape())
        if len(holes) == 0:
            return positive.copy()
        for hole in holes:
            assert isinstance(hole, SimpleShape)
            if hole not in positive:
                raise ValueError
        instance = super(ConnectedShape, cls).__new__(cls)
        instance.positive = positive
        instance.holes = holes
        return instance

    def __init__(
        self, positive: Union[WholeShape, SimpleShape], holes: Tuple[SimpleShape]
    ):
        super().__init__()

    def interior_point(self) -> Point2D:
        """Gives a random interior point inside the Connected Shape"""
        xmin = min(
            min(point[0] for point in jordan.vertices) for jordan in self.jordans
        )
        xmax = max(
            max(point[0] for point in jordan.vertices) for jordan in self.jordans
        )
        xmin -= (xmax - xmin) / 10
        xmax += (xmax - xmin) / 10
        ymin = min(
            min(point[1] for point in jordan.vertices) for jordan in self.jordans
        )
        ymax = max(
            max(point[1] for point in jordan.vertices) for jordan in self.jordans
        )
        ymin -= (ymax - ymin) / 10
        ymax += (ymax - ymin) / 10
        while True:
            xval = np.random.uniform(xmin, xmax)
            yval = np.random.uniform(ymin, ymax)
            point = (xval, yval)
            if point not in self.positive:
                continue
            for jordan in self.jordans:
                if point in jordan:
                    break
            else:
                if point in self:
                    return Point2D(point)

    def contains_point(self, point: Point2D) -> bool:
        point = Point2D(point)
        if point not in self.positive:
            return False
        for hole in self.holes:
            if point in hole and point not in hole.jordancurve:
                return False
        return True

    def contains_jordan_curve(self, jordan: JordanCurve) -> bool:
        assert isinstance(jordan, JordanCurve)
        for point in jordan.points(1):
            if not self.contains_point(point):
                return False
        return True

    def contains_shape(self, shape: BaseShape) -> bool:
        assert isinstance(shape, BaseShape)
        if isinstance(shape, EmptyShape):
            return True
        if isinstance(shape, WholeShape):
            return False
        if float(shape) * float(self) < 0:
            return False
        if shape.interior_point() not in self:
            return False
        for jordan in shape.jordans:
            if jordan not in self:
                return False
        return True

    def __contains__(self, object: Union[Point2D, JordanCurve, BaseShape]) -> bool:
        if isinstance(object, BaseShape):
            return self.contains_shape(object)
        if isinstance(object, JordanCurve):
            return self.contains_jordan_curve(object)
        point = Point2D(object)
        return self.contains_point(point)

    def __float__(self) -> float:
        soma = 0
        if not isinstance(self.positive, WholeShape):
            soma += float(self.positive)
        for hole in self.holes:
            soma -= float(hole)
        return float(soma)

    def __str__(self) -> str:
        msg = f"Connected shape with {len(self.holes)} holes,"
        msg += f" total area {float(self)}.\n"
        msg += "Positive: " + str(self.positive) + "\n"
        msg += "Negative: " + str(self.holes) + "\n"
        return msg

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: BaseShape) -> bool:
        assert isinstance(other, BaseShape)
        if isinstance(other, (EmptyShape, WholeShape, SimpleShape)):
            return False
        if abs(float(self) - float(other)) > 1e-6:
            return False
        assert isinstance(other, ConnectedShape)
        if self.positive != other.positive:
            return False
        holesa = list(self.holes)
        holesb = list(other.holes)
        if len(holesa) != len(holesb):
            return False
        areasa = [float(hole) for hole in holesa]
        holesa = [hole for _, hole in sorted(zip(areasa, holesa))]
        areasb = [float(hole) for hole in holesb]
        holesb = [hole for _, hole in sorted(zip(areasb, holesb))]
        for holea in holesa:
            if holea not in holesb:
                return False
        return True

    @property
    def jordans(self) -> Tuple[JordanCurve]:
        lista = []
        if not isinstance(self.positive, WholeShape):
            lista.append(self.positive.jordancurve)
        for hole in self.holes:
            lista.append(~(hole.jordancurve))
        return tuple(lista)


class DisjointShape(FiniteShape):
    def __new__(cls, subshapes: Tuple[ConnectedShape]):
        subshapes = list(subshapes)
        while EmptyShape() in subshapes:
            subshapes.remove(EmptyShape())
        if len(subshapes) == 0:
            return EmptyShape()
        for subshape in subshapes:
            assert isinstance(subshape, (SimpleShape, ConnectedShape))
        if len(subshapes) == 1:
            return subshapes[0].copy()
        instance = super(DisjointShape, cls).__new__(cls)
        instance.subshapes = subshapes
        return instance

    def __init__(self, subshapes: Tuple[ConnectedShape]):
        super().__init__()

    def __contains__(self, object: Union[BaseShape, JordanCurve, Point2D]) -> bool:
        if isinstance(object, BaseShape):
            return self.contains_shape(object)
        if isinstance(object, JordanCurve):
            return self.contains_jordan(object)
        point = Point2D(object)
        return self.contains_point(point)

    def interior_point(self) -> Point2D:
        """Gives a random interior point inside the Disjoint shape"""
        nsubshapes = len(self.subshapes)
        index = np.random.randint(nsubshapes)
        return self.subshapes[index].interior_point()

    def contains_point(self, point: Point2D) -> bool:
        point = Point2D(point)
        for subshape in self.subshapes:
            if point in subshape:
                return True
        return False

    def contains_jordan(self, jordan: JordanCurve) -> bool:
        assert isinstance(jordan, JordanCurve)
        for subshape in self.subshapes:
            if jordan in subshape:
                return True
        return False

    def contains_shape(self, shape: BaseShape) -> bool:
        assert isinstance(shape, BaseShape)
        if isinstance(shape, EmptyShape):
            return True
        if isinstance(shape, WholeShape):
            return False
        assert not isinstance(shape, DisjointShape)
        for subshape in self.subshapes:
            if shape in subshape:
                return True
        return False

    @property
    def jordans(self) -> Tuple[JordanCurve]:
        lista = []
        for subshape in self.subshapes:
            lista += list(subshape.jordans)
        return tuple(lista)


def ShapeFromJordans(jordans: Tuple[JordanCurve]) -> BaseShape:
    """Returns the correspondent shape

    This function don't do entry validation
    as verify if one shape is inside other

    Example
    ----------
    >>> ShapeFromJordans([])
    EmptyShape
    """
    if len(jordans) == 0:
        return EmptyShape()
    if len(jordans) == 1 and float(jordans[0]) > 0:
        return SimpleShape(jordans[0])
    lenghts = np.array(tuple(map(float, jordans)))
    if np.all(lenghts < 0):
        simples = [SimpleShape(~jordan) for jordan in jordans]
        return ConnectedShape(WholeShape(), simples)
    if np.all(lenghts > 0):
        simples = [SimpleShape(jordan) for jordan in jordans]
        return DisjointShape(simples)
    raise NotImplementedError
