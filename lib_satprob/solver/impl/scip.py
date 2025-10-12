from math import copysign
from threading import Timer
from time import time as now
from typing import Dict, Union, \
    Any, Tuple, Optional, NamedTuple

from pysat import solvers as slv
from pysat.examples.rc2 import RC2

from ..solver import Report, Solver, \
    _Solver, KeyLimit, UNLIMITED

from ...encoding import PySatFormula, MaxSatFormula, \
    to_sat_formula, is_sat_formula, is_max_sat_formula, is_scip_formula, ScipFormula
from ...encoding import is_sc
from ...variables import Assumptions, Supplements, Clause

#
# ==============================================================================
class ScipSetts(NamedTuple):
    pass


#
# ==============================================================================
class FormulaError(TypeError):
    def __init__(self, formula: PySatFormula):
        super().__init__(f'Unknown formula {type(formula)}')


#
# ==============================================================================
class ScipTimer:
    def __init__(self, solver: slv.Solver, limit: KeyLimit):
        self._timer = None
        self._solver = solver
        self._timestamp = None
        self.key, self.limit = limit

    def value(self) -> float:
        return now() - self._timestamp

    def interrupt(self):
        if self._solver:
            self._solver.interrupt()
            self._solver.clear_interrupt()

    def __enter__(self):
        if self.limit is not None:
            if self.key == 'time':
                self._timer = Timer(self.limit, self.interrupt, ())
                self._timer.start()
            else:
                raise KeyError(f'Scip don\'t support {self.key} limit')

        self._timestamp = now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._timer is not None:
            if self._timer.is_alive():
                self._timer.cancel()
            self._timer = None
        self._solver = None


#
# ==============================================================================
def _solve(solver: ScipSolver, assumptions: Assumptions, limit: KeyLimit,
           extract_model: bool, use_timer: bool) -> Report:
    if not use_timer and limit == UNLIMITED:
        status = solver.solve(assumptions)
        stats = solver.accum_stats()
    else:
        with ScipTimer(solver, limit) as timer:
            status = solver.solve_limited(assumptions, True)
            stats = {**solver.accum_stats(), 'time': timer.value()}

    cost = None
    model = solver.get_model() if extract_model and status else None
    return Report(status, stats, model, cost)


#
# ==============================================================================
def _propagate(solver: ScipSolver, assumptions: Assumptions) -> Report:
    stamp, (status, literals) = now(), solver.propagate(assumptions)
    stats = {**solver.accum_stats(), 'time': now() - stamp}

    # pysat: The status is ``True`` if NO conflict arisen
    # during propagation. Otherwise, the status is ``False``.

    # evoguess: The status is ``True`` if NO conflict arisen
    # during propagation and all literals in formula assigned.
    # The status is ``False`` if conflict arisen.
    # Otherwise, the status is ``None``.

    all_assigned = len(literals) >= solver.nof_vars()
    return Report(status and (all_assigned or None), stats, literals)

#
# ==============================================================================
class _ScipSolver(_Solver):
    _solver = None
    _last_stats = {}

    def __init__(
            self,
            formula: PySatFormula,
            settings: ScipSetts,
            use_timer: bool = True
    ):
        self.settings = settings
        super().__init__(formula, use_timer)

    def __enter__(self) -> '_ScipSolver':
        return self

    def __exit__(self, *args):
        if self._solver:
            self._solver.delete()
            self._solver = None

    def _init_solver(
            self, supplements: Supplements,
            formula: Optional[ScipFormula] = None
    ) -> Tuple[Optional[ScipSolver], Assumptions]:
        name = self.settings.sat_name
        formula = formula or self.formula
        assumptions, constraints = supplements

        if is_scip_formula(formula):
            if len(constraints) > 0:
                solver = slv.Solver(name, formula)
                solver.append_formula(constraints)
                return solver, assumptions
            elif self._solver is None:
                solver = slv.Solver(name, formula)
                self._solver = solver.solver
                solver.solver = None
            return None, assumptions
        else:
            raise FormulaError(formula)

    def _fix_stats(self, report: Report) -> Report:
        fixed_stats = {
            key: value if key == 'time' else
            value - self._last_stats.get(key, 0)
            for key, value in report.stats.items()
        }
        status, self._last_stats, model, weight = report
        return Report(status, fixed_stats, model, weight)

    def solve(
            self, supplements: Supplements,
            limit: KeyLimit = UNLIMITED,
            extract_model: bool = True,
    ) -> Report:
        assumptions, constraints = supplements
        args = (limit, extract_model, self.use_timer)

        solver, assumptions = self._init_solver(
            (assumptions, constraints), self.formula
        )
        if not solver: return self._fix_stats(
            _solve(self._solver, assumptions, *args)
        )
        with solver:
            return _solve(solver, assumptions, *args)

    def propagate(
            self, supplements: Supplements,
            ignore_constraints: bool = False
    ) -> Report:
        assumptions, constraints = supplements
        if ignore_constraints: constraints = []

        formula = self.formula
        solver, assumptions = self._init_solver(
            (assumptions, constraints), formula
        )
        if not solver: return self._fix_stats(
            _propagate(self._solver, assumptions)
        )
        with solver:
            return _propagate(solver, assumptions)

    def add_clause(
            self, clause: Clause,
            append_to_formula: bool = True
    ) -> None:
        raise NotImplementedError("add_clause not supported for scip")


#
# ==============================================================================
class ScipSolver(Solver):
    slug = 'solver:scip'

    def __init__(self):
        self.settings = ScipSetts()

    def get_instance(
            self, formula: PySatFormula, use_timer: bool = True
    ) -> _ScipSolver:
        return _ScipSolver(formula, self.settings, use_timer)

    def __config__(self) -> Dict[str, Any]:
        return {
            'slug': self.slug
        }


__all__ = [
    'ScipSolver',
    '_ScipSolver',
    # types
    'PySatTimer',
    'PySatSetts',
    # errors
    'FormulaError'
]
