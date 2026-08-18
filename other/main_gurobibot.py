"""
THIS SCRIPT WAS PROPOSED BY Gurobi intelligence Hub LLM modeler after 10 Q&A interactions 
https://intelligence.gurobi.com/hub/modeler 
The formulation is different and intresting to analyze

R&D Project Assignment Optimizer
=================================
Selects which R&D projects to fund within a fixed budget and assigns employees
to funded projects, maximising total weighted satisfaction.

Satisfaction score per assignment = seniority x rank_weight, where:
  rank_weight[1]  -- first-choice match  (default 2.0)
  rank_weight[2]  -- second-choice match (default 1.0)
  rank_weight[0]  -- fill-in assignment  (default 0.1)
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd


# ---------------------------------------------------------------------------
# Default model parameters
# ---------------------------------------------------------------------------
DEFAULT_PARAMS = {
    "budget": 50_000.0,
    "rank_weights": {1: 2.0, 2: 1.0, 0: 0.1},
}


# ---------------------------------------------------------------------------
# Optimizer class
# ---------------------------------------------------------------------------
class RDProjectAssignmentOptimizer:
    """
    MILP optimizer for R&D project selection and employee assignment.

    Decision variables
    ------------------
    y[j]        -- binary, 1 if project j is funded
    x1[e]       -- binary, 1 if employee e is assigned to their first-choice project
    x2[e]       -- binary, 1 if employee e is assigned to their second-choice project
    xf[e, j]    -- binary, 1 if employee e is assigned to project j as a fill-in

    Objective
    ---------
    Maximise sum of (seniority_e x rank_weight x assignment_variable) for all assignments.

    Constraints
    -----------
    C1  Total cost of funded projects <= budget
    C2  First-choice assignment only allowed if the project is funded
    C3  Second-choice assignment only allowed if the project is funded
    C4  Fill-in assignment only allowed if the project is funded
    C5  Each employee assigned to at most one project
    C6  Minimum headcount per funded project
    C7  Maximum headcount per funded project
    """

    def __init__(self, env: gp.Env):
        """Initialise the optimizer with a Gurobi environment."""
        self.env = env
        self.model: gp.Model = None

        # Data
        self.employees: pd.DataFrame = None
        self.projects: pd.DataFrame = None
        self.params: dict = dict(DEFAULT_PARAMS)

        # Decision variables (populated in _create_variables)
        self._y = {}    # project selection
        self._x1 = {}   # first-choice assignments
        self._x2 = {}   # second-choice assignments
        self._xf = {}   # fill-in assignments (employee, project)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.model is not None:
            self.model.dispose()
        return False

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def set_data(
        self,
        employees: pd.DataFrame,
        projects: pd.DataFrame,
        params: dict = None,
    ):
        """
        Load problem data into the optimizer.

        Parameters
        ----------
        employees : DataFrame with columns
            [employee_id, name, seniority, first_choice, second_choice]
        projects : DataFrame with columns
            [project_id, name, cost, min_headcount, max_headcount]
        params : optional dict overriding DEFAULT_PARAMS
            Keys: budget (float), rank_weights (dict {1, 2, 0} -> float)
        """
        self.employees = employees.copy()
        self.projects = projects.copy()

        if params:
            # Deep-merge rank_weights so callers can override only specific keys
            merged = dict(DEFAULT_PARAMS)
            if "rank_weights" in params:
                merged["rank_weights"] = {**DEFAULT_PARAMS["rank_weights"], **params["rank_weights"]}
            merged.update({k: v for k, v in params.items() if k != "rank_weights"})
            self.params = merged

    # ------------------------------------------------------------------
    # Model building
    # ------------------------------------------------------------------

    def build_model(self):
        """Create and configure the Gurobi model."""
        self.model = gp.Model("RD_Project_Assignment", env=self.env)
        self.model.ModelSense = GRB.MAXIMIZE

        self._create_variables()
        self._set_objective()
        self._add_constraints()

    def _create_variables(self):
        """Declare all binary decision variables."""
        projects_list = self.projects["project_id"].tolist()
        employees_list = self.employees["employee_id"].tolist()

        # y[j] -- project j is funded
        self._y = {
            j: self.model.addVar(vtype=GRB.BINARY, name=f"y[{j}]")
            for j in projects_list
        }

        # x1[e] -- employee e gets their first-choice project
        self._x1 = {
            e: self.model.addVar(vtype=GRB.BINARY, name=f"x1[{e}]")
            for e in employees_list
        }

        # x2[e] -- employee e gets their second-choice project
        self._x2 = {
            e: self.model.addVar(vtype=GRB.BINARY, name=f"x2[{e}]")
            for e in employees_list
        }

        # xf[e, j] -- employee e is a fill-in on project j
        # Only create variables for valid (employee, project) fill-in pairs,
        # i.e., project j is NOT the employee's first or second choice.
        self._xf = {}
        for _, emp_row in self.employees.iterrows():
            e = emp_row["employee_id"]
            pref_set = {emp_row["first_choice"], emp_row["second_choice"]}
            for j in projects_list:
                if j not in pref_set:
                    self._xf[(e, j)] = self.model.addVar(
                        vtype=GRB.BINARY, name=f"xf[{e},{j}]"
                    )

    def _set_objective(self):
        """Maximise total weighted satisfaction score."""
        w = self.params["rank_weights"]
        w1 = w.get(1, 1)   # first-choice weight
        w2 = w.get(2, 0.5)   # second-choice weight
        w0 = w.get(0, 0.1)   # fill-in weight

        obj_terms = []

        for _, emp_row in self.employees.iterrows():
            e = emp_row["employee_id"]
            s = emp_row["seniority"]

            # First-choice contribution
            obj_terms.append(s * w1 * self._x1[e])

            # Second-choice contribution
            obj_terms.append(s * w2 * self._x2[e])

            # Fill-in contributions
            for j in self.projects["project_id"]:
                if (e, j) in self._xf:
                    obj_terms.append(s * w0 * self._xf[(e, j)])

        self.model.setObjective(gp.quicksum(obj_terms))

    def _add_constraints(self):
        """Add all business constraints to the model."""
        budget = self.params["budget"]
        projects_list = self.projects["project_id"].tolist()

        # -- Build lookup dictionaries for fast access --
        project_cost = self.projects.set_index("project_id")["cost"].to_dict()
        project_min = self.projects.set_index("project_id")["min_headcount"].to_dict()
        project_max = self.projects.set_index("project_id")["max_headcount"].to_dict()
        emp_first = self.employees.set_index("employee_id")["first_choice"].to_dict()
        emp_second = self.employees.set_index("employee_id")["second_choice"].to_dict()

        employees_list = self.employees["employee_id"].tolist()

        # C1 -- Budget: sum of costs of funded projects <= budget
        self.model.addConstr(
            gp.quicksum(project_cost[j] * self._y[j] for j in projects_list) <= budget,
            name="C1_budget"
        )

        # C2 -- First-choice only if the corresponding project is funded
        for e in employees_list:
            j1 = emp_first[e]
            self.model.addConstr(
                self._x1[e] <= self._y[j1],
                name=f"C2_first_funded[{e}]"
            )

        # C3 -- Second-choice only if the corresponding project is funded
        for e in employees_list:
            j2 = emp_second[e]
            self.model.addConstr(
                self._x2[e] <= self._y[j2],
                name=f"C3_second_funded[{e}]"
            )

        # C4 -- Fill-in only if the project is funded
        for (e, j), var in self._xf.items():
            self.model.addConstr(
                var <= self._y[j],
                name=f"C4_fillin_funded[{e},{j}]"
            )

        # C5 -- Each employee assigned to at most one project
        for e in employees_list:
            fill_in_sum = gp.quicksum(
                self._xf[(e, j)] for j in projects_list if (e, j) in self._xf
            )
            self.model.addConstr(
                self._x1[e] + self._x2[e] + fill_in_sum <= 1,
                name=f"C5_unique[{e}]"
            )

        # C6 & C7 -- Min / max headcount per funded project
        for j in projects_list:
            # All employees assigned to project j
            assigned_to_j = []

            # First-choice employees whose first choice is j
            for e in employees_list:
                if emp_first[e] == j:
                    assigned_to_j.append(self._x1[e])

            # Second-choice employees whose second choice is j
            for e in employees_list:
                if emp_second[e] == j:
                    assigned_to_j.append(self._x2[e])

            # Fill-in employees for project j
            for e in employees_list:
                if (e, j) in self._xf:
                    assigned_to_j.append(self._xf[(e, j)])

            headcount = gp.quicksum(assigned_to_j)

            # C6 -- headcount >= min_headcount * y[j]
            self.model.addConstr(
                headcount >= project_min[j] * self._y[j],
                name=f"C6_min_headcount[{j}]"
            )

            # C7 -- headcount <= max_headcount * y[j]
            self.model.addConstr(
                headcount <= project_max[j] * self._y[j],
                name=f"C7_max_headcount[{j}]"
            )

    # ------------------------------------------------------------------
    # Solving
    # ------------------------------------------------------------------

    def solve(self) -> int:
        """
        Run the Gurobi optimizer.

        Returns
        -------
        int : Gurobi status code
        """
        self.model.optimize()
        return self.model.Status

    # ------------------------------------------------------------------
    # Solution retrieval
    # ------------------------------------------------------------------

    def get_solution(self) -> dict:
        """
        Extract and return the solution as a structured dictionary.

        Returns
        -------
        dict with keys:
            status, is_optimal, objective_value, selected_projects,
            assignments, total_cost, unassigned_employees
        """
        status = self.model.Status
        is_optimal = status == GRB.OPTIMAL

        if not is_optimal:
            return {
                "status": status,
                "is_optimal": False,
                "objective_value": None,
                "selected_projects": [],
                "assignments": [],
                "total_cost": 0.0,
                "unassigned_employees": self.employees["employee_id"].tolist(),
            }

        project_cost = self.projects.set_index("project_id")["cost"].to_dict()
        emp_first = self.employees.set_index("employee_id")["first_choice"].to_dict()
        emp_second = self.employees.set_index("employee_id")["second_choice"].to_dict()
        seniority = self.employees.set_index("employee_id")["seniority"].to_dict()
        w = self.params["rank_weights"]

        # Funded projects
        selected_projects = [
            j for j, var in self._y.items() if var.X > 0.5
        ]
        total_cost = sum(project_cost[j] for j in selected_projects)

        # Build assignment list
        assignments = []
        assigned_employees = set()

        for e in self.employees["employee_id"]:
            if self._x1[e].X > 0.5:
                j = emp_first[e]
                assignments.append({
                    "employee_id": e,
                    "project_id": j,
                    "match_type": "first_choice",
                    "score": seniority[e] * w.get(1, 2.0),
                })
                assigned_employees.add(e)

            elif self._x2[e].X > 0.5:
                j = emp_second[e]
                assignments.append({
                    "employee_id": e,
                    "project_id": j,
                    "match_type": "second_choice",
                    "score": seniority[e] * w.get(2, 1.0),
                })
                assigned_employees.add(e)

            else:
                for j in self.projects["project_id"]:
                    if (e, j) in self._xf and self._xf[(e, j)].X > 0.5:
                        assignments.append({
                            "employee_id": e,
                            "project_id": j,
                            "match_type": "fill_in",
                            "score": seniority[e] * w.get(0, 0.1),
                        })
                        assigned_employees.add(e)
                        break  # at most one project per employee

        unassigned = [
            e for e in self.employees["employee_id"] if e not in assigned_employees
        ]

        return {
            "status": status,
            "is_optimal": True,
            "objective_value": self.model.ObjVal,
            "selected_projects": selected_projects,
            "assignments": assignments,
            "total_cost": total_cost,
            "unassigned_employees": unassigned,
        }

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display_results(self, solution: dict = None):
        """
        Print a formatted summary report of the solution.

        Parameters
        ----------
        solution : dict returned by get_solution(); if None, calls get_solution() internally.
        """
        if solution is None:
            solution = self.get_solution()

        print("=" * 60)
        print("  R&D PROJECT ASSIGNMENT — OPTIMIZATION REPORT")
        print("=" * 60)

        if not solution["is_optimal"]:
            print(f"  Status : {solution['status']} (no optimal solution found)")
            print("=" * 60)
            return

        print(f"  Total Satisfaction Score : {solution['objective_value']:.2f}")
        print(f"  Total Budget Used        : ${solution['total_cost']:,.2f}")
        print(f"  Projects Funded          : {len(solution['selected_projects'])}")
        print(f"  Employees Assigned       : {len(solution['assignments'])}")
        print(f"  Employees Unassigned     : {len(solution['unassigned_employees'])}")
        print("-" * 60)

        # Group assignments by project
        project_name = self.projects.set_index("project_id")["name"].to_dict()
        project_cost = self.projects.set_index("project_id")["cost"].to_dict()

        from collections import defaultdict
        roster: dict = defaultdict(list)
        for a in solution["assignments"]:
            roster[a["project_id"]].append(a)

        print("  FUNDED PROJECTS")
        print("-" * 60)
        for j in solution["selected_projects"]:
            pname = project_name.get(j, j)
            pcost = project_cost.get(j, 0)
            members = roster.get(j, [])
            print(f"  [{j}] {pname}  |  Cost: ${pcost:,.0f}  |  Headcount: {len(members)}")
            for a in members:
                tag = {"first_choice": "1st", "second_choice": "2nd", "fill_in": "fill"}.get(
                    a["match_type"], "?"
                )
                emp_name = self.employees.set_index("employee_id")["name"].get(a["employee_id"], a["employee_id"])
                sen = self.employees.set_index("employee_id")["seniority"].get(a["employee_id"], "?")
                print(f"      {a['employee_id']:8s} {emp_name:20s} seniority={sen}  [{tag}]  score={a['score']:.2f}")

        if solution["unassigned_employees"]:
            print("-" * 60)
            print("  UNASSIGNED EMPLOYEES")
            emp_name_map = self.employees.set_index("employee_id")["name"].to_dict()
            for e in solution["unassigned_employees"]:
                print(f"      {e}  {emp_name_map.get(e, '')}")

        print("=" * 60)


# ---------------------------------------------------------------------------
# Sample data and entry point
# ---------------------------------------------------------------------------

def build_sample_data():
    """Return a small representative dataset for demonstration."""
    import os 
    from dotenv import load_dotenv
    from os.path import join, dirname
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)

    employees = pd.read_csv(os.environ.get("INPUT_VOTES_CSV_PATH"))
    projects  = pd.read_csv(os.environ.get("INPUT_PROJECTS_CSV_PATH"))

    employees.rename(
        columns={
            "person_id": "employee_id", 
            "name": "name", 
            "person_seniority": "seniority", 
            "voted_project_first_choice": "first_choice", 
            "voted_project_second_choice": "second_choice"}, 
    inplace=True)
    employees["seniority"] = employees["seniority"].astype(int)
    employees["first_choice"] = employees["first_choice"].astype(str)
    employees["second_choice"] = employees["second_choice"].astype(str)
    employees["employee_id"] = employees["employee_id"].astype(str)


    projects.rename(
        columns={
            "project_id": "project_id",
            "project_name": "name",
            "project_cost": "cost",
            "min_people": "min_headcount",
            "max_people": "max_headcount"
        },
        inplace=True
    )
    projects["cost"] = projects["cost"].astype(float)
    projects["min_headcount"] = projects["min_headcount"].astype(int)
    projects["max_headcount"] = projects["max_headcount"].astype(int)
    projects["project_id"] = projects["project_id"].astype(str)




    # employees = pd.DataFrame([
    #     {"employee_id": "E01", "name": "Alice",   "seniority": 5, "first_choice": "P1", "second_choice": "P2"},
    #     {"employee_id": "E02", "name": "Bob",     "seniority": 4, "first_choice": "P1", "second_choice": "P3"},
    #     {"employee_id": "E03", "name": "Carol",   "seniority": 4, "first_choice": "P2", "second_choice": "P1"},
    #     {"employee_id": "E04", "name": "Dave",    "seniority": 3, "first_choice": "P3", "second_choice": "P1"},
    #     {"employee_id": "E05", "name": "Eve",     "seniority": 3, "first_choice": "P2", "second_choice": "P3"},
    #     {"employee_id": "E06", "name": "Frank",   "seniority": 2, "first_choice": "P3", "second_choice": "P2"},
    #     {"employee_id": "E07", "name": "Grace",   "seniority": 2, "first_choice": "P1", "second_choice": "P3"},
    #     {"employee_id": "E08", "name": "Henry",   "seniority": 1, "first_choice": "P2", "second_choice": "P3"},
    #     {"employee_id": "E09", "name": "Irene",   "seniority": 1, "first_choice": "P3", "second_choice": "P1"},
    # ])

    # projects = pd.DataFrame([
    #     {"project_id": "P1", "name": "Alpha Project",  "cost": 10_000, "min_headcount": 2, "max_headcount": 4},
    #     {"project_id": "P2", "name": "Beta Project",   "cost":  8_000, "min_headcount": 2, "max_headcount": 3},
    #     {"project_id": "P3", "name": "Gamma Project",  "cost":  6_000, "min_headcount": 2, "max_headcount": 3},
    # ])

    params = {
        "budget": 50_000.0,
        "rank_weights": {1: 1.0, 2: 0.5, 0: 0.1},
    }

    return employees, projects, params


if __name__ == "__main__":
    employees, projects, params = build_sample_data()

    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 1)
        env.setParam("TimeLimit", 30)
        env.start()

        with RDProjectAssignmentOptimizer(env) as optimizer:
            optimizer.set_data(employees, projects, params)
            optimizer.build_model()
            optimizer.solve()
            solution = optimizer.get_solution()
            optimizer.display_results(solution)
