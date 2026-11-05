import random

from app.services.optimizer import OptimizerStop, Problem, build_coords, nearest_neighbor, route_cost, solve
from app.services.routing import _fallback_matrix


def _problem(n, seed=1, end=None):
    rnd = random.Random(seed)
    stops = [
        OptimizerStop(stop_id=i, coord=(32.05 + rnd.random() * 0.08, 34.75 + rnd.random() * 0.08), service_s=0)
        for i in range(n)
    ]
    return Problem(start=(32.08, 34.78), stops=stops, end=end)


def test_visits_every_stop_once():
    p = _problem(25)
    m = _fallback_matrix(build_coords(p))
    sol = solve(p, m)
    assert sorted(sol.order) == list(range(25))


def test_not_worse_than_nearest_neighbor():
    for seed in range(5):
        p = _problem(20, seed)
        m = _fallback_matrix(build_coords(p))
        assert route_cost(solve(p, m).order, m) <= route_cost(nearest_neighbor(p, m), m) + 1e-6


def test_line_of_stops_is_visited_in_order():
    # עצירות על קו ישר: המסלול האופטימלי עובר בהן לפי הסדר
    stops = [OptimizerStop(i, (32.0 + 0.01 * (i + 1), 34.8), 0) for i in range(6)]
    rnd = random.Random(3)
    shuffled = stops[:]
    rnd.shuffle(shuffled)
    p = Problem(start=(32.0, 34.8), stops=shuffled)
    m = _fallback_matrix(build_coords(p))
    order = [shuffled[k].stop_id for k in solve(p, m).order]
    assert order == list(range(6))


def test_with_end_point():
    p = _problem(10, end=(32.08, 34.78))
    m = _fallback_matrix(build_coords(p))
    assert sorted(solve(p, m).order) == list(range(10))


def test_single_and_empty():
    for n in (0, 1):
        p = _problem(n)
        assert solve(p, _fallback_matrix(build_coords(p))).order == list(range(n))
