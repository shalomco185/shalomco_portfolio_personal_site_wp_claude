"""חישוב הסדר האופטימלי של העצירות (Google OR-Tools).

הבעיה בגרסה הבסיסית: שליח אחד יוצא מנקודת התחלה ועובר בכל העצירות בזמן
הנסיעה הכולל הקצר ביותר. המסלול "פתוח" (אין חובת חזרה), אלא אם מעבירים end.

נקודות הרחבה:
  * Problem.end: נקודת סיום (בית / מחסן). נתמך כבר כאן; לא מוצג בממשק.
  * OptimizerStop: שדות לחלון זמן, עדיפות ונפח.
  * constraints.py: מחלקות אילוץ שמתחברות למודל לפני הפתרון (חלונות זמן,
    קיבולת רכב, הפסקות). ברירת המחדל: אין אילוצים.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from ..config import settings
from .routing import Coord, Matrix

BIG = 10**9


@dataclass
class OptimizerStop:
    stop_id: int
    coord: Coord
    service_s: float = 120.0
    # הרחבה עתידית:
    priority: int = 0
    time_window: tuple[int, int] | None = None  # שניות מתחילת המסלול
    volume: float | None = None


@dataclass
class Problem:
    start: Coord
    stops: list[OptimizerStop]
    end: Coord | None = None
    vehicle_capacity: float | None = None  # הרחבה עתידית
    constraints: list = field(default_factory=list)  # מופעים של constraints.Constraint


@dataclass
class Solution:
    order: list[int]  # אינדקסים לתוך problem.stops לפי סדר הביקור
    engine: str


@dataclass
class SolverContext:
    """מה שמחלקת אילוץ מקבלת כדי להוסיף את עצמה למודל."""

    problem: Problem
    matrix: Matrix
    manager: pywrapcp.RoutingIndexManager
    routing: pywrapcp.RoutingModel
    transit_index: int
    node_of_stop: dict[int, int]  # אינדקס עצירה -> צומת במודל


def build_coords(problem: Problem) -> list[Coord]:
    """סדר הצמתים: 0 = התחלה, 1..n = עצירות, n+1 = סיום (אם הוגדר)."""
    coords = [problem.start] + [s.coord for s in problem.stops]
    if problem.end is not None:
        coords.append(problem.end)
    return coords


def solve(problem: Problem, matrix: Matrix) -> Solution:
    n = len(problem.stops)
    if n == 0:
        return Solution(order=[], engine=matrix.engine)
    if n == 1:
        return Solution(order=[0], engine=matrix.engine)

    has_end = problem.end is not None
    size = n + 2  # התחלה + עצירות + סיום (אמיתי או דמה)
    end_node = n + 1
    dur = matrix.durations

    def cost(i: int, j: int) -> int:
        if j == end_node:
            return int(dur[i][end_node]) if has_end else 0  # מסלול פתוח: סיום בחינם
        if i == end_node:
            return BIG
        service = problem.stops[j - 1].service_s if 1 <= j <= n else 0
        return int(dur[i][j] + service)

    manager = pywrapcp.RoutingIndexManager(size, 1, [0], [end_node])
    routing = pywrapcp.RoutingModel(manager)

    def transit(from_index: int, to_index: int) -> int:
        return cost(manager.IndexToNode(from_index), manager.IndexToNode(to_index))

    transit_index = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    ctx = SolverContext(
        problem=problem,
        matrix=matrix,
        manager=manager,
        routing=routing,
        transit_index=transit_index,
        node_of_stop={k: k + 1 for k in range(n)},
    )
    for constraint in problem.constraints:
        constraint.apply(ctx)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.seconds = 1 if n <= 8 else max(1, settings.optimizer_time_limit_s)

    sol = routing.SolveWithParameters(params)
    if sol is None:
        raise RuntimeError("לא נמצא פתרון למסלול")

    order: list[int] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if 1 <= node <= n:
            order.append(node - 1)
        index = sol.Value(routing.NextVar(index))
    return Solution(order=order, engine=matrix.engine)


def nearest_neighbor(problem: Problem, matrix: Matrix) -> list[int]:
    """מסלול פשוט להשוואה ולבדיקות: תמיד לעצירה הקרובה ביותר."""
    n = len(problem.stops)
    left = set(range(n))
    cur, order = 0, []
    while left:
        nxt = min(left, key=lambda k: matrix.durations[cur][k + 1])
        order.append(nxt)
        left.remove(nxt)
        cur = nxt + 1
    return order


def route_cost(order: list[int], matrix: Matrix) -> float:
    nodes = [0] + [k + 1 for k in order]
    return sum(matrix.durations[a][b] for a, b in zip(nodes, nodes[1:]))
