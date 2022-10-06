#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2008-2022
#  National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

from itertools import product

from pyomo.common.collections import ComponentSet
from pyomo.common.config import add_docstring_list

from pyomo.contrib.gdpopt.algorithm_base_class import _GDPoptAlgorithm
from pyomo.contrib.gdpopt.config_options import (
    _add_mip_solver_configs, _add_nlp_solve_configs, _add_nlp_solver_configs
)
from pyomo.contrib.gdpopt.create_oa_subproblems import (
    add_discrete_variable_list, add_disjunction_list, get_subproblem
)
from pyomo.contrib.gdpopt.util import (
    fix_discrete_solution_in_subproblem, time_code
)
from pyomo.contrib.gdpopt.solve_subproblem import solve_subproblem

from pyomo.core import value
from pyomo.opt import TerminationCondition as tc
from pyomo.opt.base import SolverFactory

@SolverFactory.register(
    'gdpopt.enumerate',
    doc="Generalized Disjunctive Programming (GDP) solver that enumerates "
    "all discrete solutions")
class GDP_Enumeration_Solver(_GDPoptAlgorithm):
    """
    Solves Generalized Disjunctive Programming (GDP) by enumerating all
    discrete solutions and solving the resulting NLP subproblems, then
    returning the best solution found.

    Accepts models that can include nonlinear, continuous variables and
    constraints, as well as logical conditions. For non-convex problems,
    the algorithm will not be exact unless the NLP subproblems are solved
    globally.
    """

    def _log_citation(self, config):
        pass

    CONFIG = _GDPoptAlgorithm.CONFIG()
    _add_nlp_solver_configs(CONFIG, default_solver='ipopt')
    _add_nlp_solve_configs(CONFIG)
    # If we don't enumerate over integer values, we might have MILP subproblems
    _add_mip_solver_configs(CONFIG)

    algorithm = 'enumerate'

    def _discrete_solution_iterator(self, disjunctions,
                                    non_indicator_boolean_vars,
                                    discrete_var_list):
        discrete_var_values = [range(v.lb, v.ub + 1) for v in discrete_var_list]
        # we will calculate all the possible indicator_var realizations, and
        # then multiply those out by all the boolean var realizations and all
        # the integer var realizations.
        for true_indicators in product(*[disjunction.disjuncts for disjunction
                                         in disjunctions]):
            for boolean_realization in product(
                    [True, False], repeat=len(non_indicator_boolean_vars)):
                for integer_realization in product(*discrete_var_values):
                    yield (ComponentSet(true_indicators), boolean_realization,
                           integer_realization)

    def _solve_gdp(self, original_model, config):
        logger = config.logger

        util_block = self.original_util_block
        # From preprocessing to make sure this *is* a GDP, we already have 
        # lists of:
        #     * Disjuncts
        #     * BooleanVars
        #     * Algebraic vars
        # But we need to gather the Disjunctions and integer vars as well:
        add_disjunction_list(util_block)
        add_discrete_variable_list(util_block)

        subproblem, subproblem_util_block = get_subproblem(original_model,
                                                           util_block)

        discrete_solns = list(self._discrete_solution_iterator(
            subproblem_util_block.disjunction_list, 
            subproblem_util_block.non_indicator_boolean_variable_list,
            subproblem_util_block.discrete_variable_list))
        num_discrete_solns = len(discrete_solns)
        for soln in discrete_solns:
            # We will interrupt based on time limit of iteration limit:
            if (self.reached_time_limit(config) or 
                self.reached_iteration_limit(config)):
                break
            self.iteration += 1

            with time_code(self.timing, 'nlp'):
                with fix_discrete_solution_in_subproblem(*soln,
                                                         subproblem_util_block,
                                                         config, self):
                    nlp_termination = solve_subproblem(subproblem_util_block,
                                                       self, config)
                    if nlp_termination in {tc.optimal, tc.feasible}:
                        primal_improved = self._update_bounds_after_solve(
                            'subproblem',
                            primal=value(subproblem_util_block.obj.expr),
                            logger=config.logger)
                        if primal_improved:
                            self.update_incumbent(subproblem_util_block)

                    elif nlp_termination == tc.unbounded:
                        # the whole problem is unbounded, we can stop
                        self._update_primal_bound_to_unbounded()
                        break

            if self.iteration == num_discrete_solns:
                # We can terminate optimally or declare infeasibility: We have
                # enumerated all solutions, so our incumbent is optimal (or
                # locally optimal, depending on how we solved the subproblems)
                # if it exists, and if not then there is no solution.
                if self.incumbent_boolean_soln is None:
                    self._load_infeasible_termination_status(config)
                else: # the incumbent is optimal
                    self._update_bounds(dual=self.primal_bound(),
                                        force_update=True)
                    self._log_current_state(config.logger, '')
                    config.logger.info(
                        'GDPopt exiting--all discrete solutions have been '
                        'enumerated.')
                    self.pyomo_results.solver.termination_condition = tc.optimal
                    break


GDP_Enumeration_Solver.solve.__doc__ = add_docstring_list(
    GDP_Enumeration_Solver.solve.__doc__, GDP_Enumeration_Solver.CONFIG,
    indent_by=8)
