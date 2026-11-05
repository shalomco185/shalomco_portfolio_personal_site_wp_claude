"""אילוצי מסלול: תשתית להרחבה. בגרסה הבסיסית אף אילוץ לא מופעל.

כל אילוץ הוא מחלקה עם apply(ctx) שמקבלת SolverContext (ראו optimizer.py)
ומוסיפה את עצמה למודל של OR-Tools. כדי להפעיל אילוץ מוסיפים אותו לרשימה
שמחזירה build_constraints() (או בהתאם להגדרות השליח).

דוגמאות למימוש עתידי (בתיעוד של OR-Tools: "VRP with Time Windows",
"Capacity Constraints"):

  * TimeWindows: routing.AddDimension(transit_index, slack, horizon, False, "Time"),
    ואז לכל עצירה עם time_window: time_dim.CumulVar(index).SetRange(start, end).
  * VehicleCapacity: callback של נפח לכל צומת + AddDimensionWithVehicleCapacity.
  * Priority: מקדם עונש על איחור למשלוחי אקספרס (SetCumulVarSoftUpperBound).
  * Breaks: time_dim.SetBreakIntervalsOfVehicle(...).
"""
from __future__ import annotations

from typing import Protocol

from .optimizer import Problem, SolverContext


class Constraint(Protocol):
    name: str

    def apply(self, ctx: SolverContext) -> None: ...


def build_constraints(problem: Problem) -> list[Constraint]:
    """הרשימה ריקה בגרסה הבסיסית. כאן יתווספו אילוצים בהמשך."""
    return []
