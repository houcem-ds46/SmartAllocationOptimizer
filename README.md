# 1. The business problem :  The Friday Afternoon Headach

You are an Operations Manager. It’s Friday afternoon, and the quarterly project kick-off is on Monday. You have dozens of employees to assign to a list of new R&D projects.

Everyone has submitted their top choices. The senior experts expect their preferences to be honored. Meanwhile, Finance has handed you a strict budget to spend for future R&D projects, and every project has minimum and maximum headcount limits. If you try to solve this in a spreadsheet, you will spend your entire weekend dragging rows, breaking capacity constraints, and ultimately leaving half the team frustrated.

Instead, you export the team's votes to a CSV and run a single Python script.

In a fraction of a second, you get a perfect allocation plan, a budget impact report, and a dashboard ready for Monday's meeting. This repository provides that exact decision-support system. To prove its value, it compares two distinct algorithmic engines:

- The Greedy Algorithm (The Human Way): A fast, common-sense heuristic that mimics a human planner doing their best to serve senior experts first and then fill the remaining gaps.

- The MILP Optimizer (The AI augmented way with Gurobi Solver): A heavy-duty mathematical solver that analyzes millions of combinations globally to guarantee the absolute best ROI, maximizing team satisfaction without breaking a single business rule.


# 2. The Greedy Algorithm (Baseline)
Motivation:
Before deploying complex solvers, it is best practice to establish a baseline. The greedy algorithm simulates the manual logic a human planner might use. It is fast, easy to interpret, and prioritizes "VIPs" (individuals with the highest seniority) first.

Pseudo-Code Approach:
The algorithm operates in two phases:

- VIP First: Iterate through seniority levels from highest to lowest. For each person at the current seniority, attempt to assign them to their 1st choice. If full or over budget, try the 2nd choice.

- Filling the Gaps: Once the budget is exhausted or all VIPs are served, look at the projects that are already "opened" (allocated to at least one person). Fill the remaining seats up to the maximum capacity with unassigned people, prioritizing those who voted for the project.

```Plaintext
Initialize available_budget = MAX_BUDGET
Sort people by seniority (Descending)

// Phase 1
FOR EACH person IN people:
    IF 1st_choice_project has capacity AND cost <= available_budget:
        Assign person to 1st_choice
        Deduct cost from available_budget
    ELSE IF 2nd_choice_project has capacity AND cost <= available_budget:
        Assign person to 2nd_choice
        Deduct cost from available_budget

// Phase 2
FOR EACH opened_project:
    WHILE opened_project has empty seats AND unassigned people exist:
        Find unassigned person with highest combined score (vote + seniority)
        Assign to opened_project
```
# 3. The Mathematical Optimization model (Gurobi)

## Motivation 

Heuristics often get stuck in local optima (e.g., filling a sub-optimal project early on and lacking the budget to open a better one later). To find the mathematically proven best allocation, we model this as a Mixed-Integer Linear Programming (MILP) problem using Gurobi. It ensures a global view of all constraints simultaneously. We aim to find the optimal way to assign people to projects while : 

* Maximizing weighted satisfaction based on project preferences and seniority
* Respecting project capacity limits
* Staying within a defined project budget when possible (soft constraint allowing 5% overbudget excess). Allowing a controlled budget overrun with a penalty

## Sets and Parameters

* `P`: Set of all people
* `C`: Set of all projects
* `S[p, c]`: Weighted satisfaction score of assigning person `p` to project `c`

  * For a first-choice project: `S[p, c] = Seniority[p] × 1`
  * For a second-choice project: `S[p, c] = Seniority[p] × 0.5`
* `Cost[c]`: Financial cost of activating project `c`
* `Min[c]`: Minimum number of people required for project `c`
* `Max[c]`: Maximum number of people allowed for project `c`
* `B`: Total project budget
* `λ`: Penalty weight applied to budget overruns

## Decision Variables

* `x[p, c] ∈ {0, 1}`: Binary assignment variable

  * `x[p, c] = 1` if person `p` is assigned to project `c`
  * `x[p, c] = 0` otherwise
* `y[c] ∈ {0, 1}`: Binary project activation variable

  * `y[c] = 1` if project `c` is activated
  * `y[c] = 0` otherwise
* `o ≥ 0`: Continuous variable representing the amount by which the total project cost exceeds the budget

## Objective Function

The model maximizes total weighted satisfaction while penalizing any budget overrun:


$$ \max \quad \sum_{p \in P} \sum_{c \in C} S[p, c] \cdot x[p, c] - \lambda \cdot o $$

The first term rewards assignments that provide higher satisfaction. The second term penalizes solutions that exceed the available budget.

## Constraints

### 1. Assignment Constraint

Each person can be assigned to at most one project:

$$
\sum_{c \in C} x[p, c] \leq 1,
\quad \forall p \in P
$$


### 2. Project Activation definition 

A project can only have assigned people if it is activated.

Using a Big-M constraint, where:

$$
BigM = \text{Size}[P] + 1
$$

the constraint is:

$$
\sum_{p \in P} x[p, c]
\leq
BigM \cdot y[c],
\quad \forall c \in C
$$

`y[c] = 1` only and only if project c is activated.

### 3. Minimum and Maximum Project Capacity

Each activated project must have between its minimum and maximum number of assigned people:

$$
\text{Min}[c] \cdot y[c]
\leq
\sum_{p \in P} x[p, c]
\leq
\text{Max}[c] \cdot y[c],
\quad \forall c \in C
$$

This constraint garantees that if project c is being used  `y[c] = 1`, then we make sure that min and max capacity are respected


### 4. Budget Constraint definition 

The total cost of activated projects must not exceed the budget plus the allowed overrun:

$$
\sum_{c \in C}
\text{Cost}[c] \cdot y[c]
\leq
B + o
$$

The variable `o` represents the amount by which the project budget is exceeded. (this soft contraint is optional, the user can decide if he/she wants to respect the max budget by changing a global variable) 

If the total project cost is within the budget, `o` can be `0`.

If the total project cost exceeds the budget, `o` must increase accordingly.

### 5. Maximum Authorized Budget Overrun

The budget overrun is limited to 5% of the total budget:

$$
o \leq 0.05 \cdot B
$$

This prevents the optimization model from exceeding the budget by more than 5%.

The `5%` value can be changed depending on the business requirement.

## Complete MILP Formulation

### Sets and Parameters

$$
P = \text{set of people}
$$

$$
C = \text{set of projects}
$$

$$
S[p, c] = \text{weighted satisfaction score}
$$

$$
\text{Cost}[c] = \text{cost of activating project } c
$$

$$
\text{Min}[c] = \text{minimum project capacity}
$$

$$
\text{Max}[c] = \text{maximum project capacity}
$$

$$
B = \text{total project budget}
$$

$$
\lambda = \text{budget overrun penalty weight}
$$

### Decision Variables

$$
x[p, c] \in {0,1},
\quad \forall p \in P,\ c \in C
$$

$$
y[c] \in {0,1},
\quad \forall c \in C
$$

$$
o \geq 0
$$

### Objective

$$ \max \quad \sum_{p \in P} \sum_{c \in C} S[p, c] \cdot x[p, c] - \lambda \cdot o $$

### Constraints

**At most one project per person:**

$$
\sum_{c \in C} x[p, c] \leq 1,
\quad \forall p \in P
$$

**Project activation:**

$$
\sum_{p \in P} x[p, c]
\leq
\text{BigM} \cdot y[c],
\quad \forall c \in C
$$

**Project capacity:**

$$
\text{Min}[c] \cdot y[c]
\leq
\sum_{p \in P} x[p, c]
\leq
\text{Max}[c] \cdot y[c],
\quad \forall c \in C
$$

**Budget with soft overrun:**

$$
\sum_{c \in C}
\text{Cost}[c] \cdot y[c]
\leq
B + o
$$

**Maximum authorized overrun:**

$$
o \leq 0.05 \cdot B
$$

## Interpretation

The model tries to assign people to projects to maximize weighted satisfaction while respecting project capacities and controlling the total project budget. It makes a trade-off between **people's preferences**, **project capacity**, and **budget**.

A project is activated only when people are assigned to it. Once activated, it must satisfy its minimum and maximum capacity.

Assignments are rewarded according to the satisfaction score `S[p, c]`. This custom score is based on seniority and project preference, assigning a senior person to their preferred project receives a higher objective contribution.

When soft budget constraint is activated, the model can exceed the budget by up to 5%, but doing so reduces the objective value through the penalty term: Therefore, the optimizer will only use the allowed budget overrun when the additional satisfaction gained from activating projects justifies its penalty.

# 4.Comparing Approaches: Greedy vs. Optim

To objectively evaluate the performance of our allocation engine, we benchmarked the baseline heuristic (Greedy algorithm) against the exact mathematical solver (MILP Optimization). Here is the detailed breakdown of the key performance indicators:

| Metric | Greedy (Baseline) | Optim (MILP) | Gain / Impact |
|---|---:|---:|---:|
| Execution Time | 80 ms | 141 ms | +76% time (Trade-off) |
| Number of allocated projects | 5 | 5 | Cost differs |
| Total Project Cost | $47,500 | $52,500 | +10.5% cost (Trade-off) |
| Number of people allocated to their 1st Choice | 10 | 21 | +110% |
| Number of people allocated to their 2nd Choice | 10 | 3 | -70% (Trade-off) |
| Weighted Satisfaction Score | 78 | 117.5 | +51% |


While the Greedy approach offers a slightly faster execution time and a lower immediate budget footprint, the Optimization algorithm provides a massively superior ROI in terms of overall employee satisfaction. By taking a global view of all constraints rather than making sequential, localized decisions, the MILP solver drastically increases the number of people getting their top preferences. 
Ultimately, for a marginal budget increase of $5,000, the Optimization model more than doubles the number of employees assigned to their absolute first choice. 
This proves the immense business value of shifting from naive heuristics to Operations Research: you invest slightly more in budget and computational milliseconds, but you maximize human capital satisfaction and retention.

Here is a general assessment of the two approaches : 

| Approach | Pros | Cons |
|---|---|---|
| Greedy Heuristic (Baseline) | Quick to implement<br>Extremely fast execution time ($O(N)$ complexity)<br><br>No specialized solver licensing required.<br><br>Business: Intuitive and easy to explain to non-technical stakeholders. | Brittle architecture (adding new business rules often leads to nested, unmaintainable "spaghetti" code)<br><br>Trapped in local optima, sacrificing global ROI<br>Fails to guarantee complex constraints |
| MILP Optimization (Gurobi) | Mathematically guarantees the global optimum<br><br>Highly flexible (new constraints are simply added as mathematical equations)<br><br>Maximizes ROI and overall satisfaction<br><br>Enables advanced scenario analysis (e.g., Pareto frontiers for budget elasticity). | Computationally intensive for massive datasets (NP-Hard)<br><br>Requires specialized Operations Research (OR) expertise to formulate.<br><br>Enterprise-grade solvers (like Gurobi) involve high commercial licensing costs but free alternatives exist with less performance |



# 5.Code architecture 

Global ArchitectureThe pipeline is entirely orchestrated by the launch_process() function, ensuring a clean flow from data ingestion to evaluation and visualization.get_input_data: Ingests data from either local CSV files or directly from Google Sheets via API (managing individuals' votes/seniority and projects' capacities/costs).perform_sanity_checks: A robust validation layer ensuring data integrity (e.g., verifying unique IDs, checking that maximum capacity $\ge$ minimum capacity, and ensuring no missing cross-references).Algorithmic Engines:greedy_allocation: Runs the baseline heuristic.create_model: Formulates and runs the MILP optimization model.post_process_solution: Merges the algorithmic outputs with the initial data to generate human-readable allocations and calculates business KPIs (satisfaction scores, budget utilization, allocation rates).display_allocation_results_graph & display_kpi_compraison: Generates interactive Plotly visualizations (slope graphs and comparative bar charts) to help stakeholders understand the trade-offs.

- get_input_data: Ingests data from either local CSV files or directly from Google Sheets via API (managing individuals' votes/seniority and projects' capacities/costs).

- perform_sanity_checks: A robust validation layer ensuring data integrity (e.g., verifying unique IDs, checking that maximum capacity $\ge$ minimum capacity, and ensuring no missing cross-references).

- Algorithmic Engines:
- - greedy_allocation: Runs the baseline heuristic
- - create_model: Formulates and runs the MILP optimization model.

- post_process_solution: Merges the algorithmic outputs with the initial data to generate human-readable allocations and calculates business KPIs (satisfaction scores, budget utilization, allocation rates).

- display_allocation_results_graph & display_kpi_compraison: Generates interactive Plotly visualizations (slope graphs and comparative bar charts) to help stakeholders understand the trade-offs.

Below is a global schema describing the architecture : 

```
[votes.csv]    [projects.csv]
       |               |
       v               v
+--------------------------+      +-------------------------+      +---------------------+
| Read inputs              | ---> | Sanity checks           | ---> | Allocation engine   |
| (get_input_data)         |      | (perform_sanity_checks) |      |  - greedy()         |
+--------------------------+      +-------------------------+      |  - solve_milp()     |
                                                                   +---------+-----------+
                                                                             |
                                                                             v
                                                                   +-------------------------+ 
                                                                   | Post-process / KPI      |
                                                                   | (post_process_solution) |
                                                                   +---------+---------------+
                                                                             |
                                                                             v
                                                                   +-------------------------+ 
                                                                   | Display & Export        |
                                                                   | (display_allocation...  |
                                                                   | & df.to_csv)            |
                                                                   +---------+---------------+
                                                                             |
                                                                             v
                                                                 [output_votes.csv]
                                                                 [output_projects.csv]
                                                                 [df_kpi_cont.csv]

```
## Installation

Before running the project, ensure that you have all the necessary dependencies installed. You can do this by installing the packages listed in the `requirements.txt` file. To install these dependencies, run the following command in your terminal:

```sh
pip install -r requirements.txt
```

## Usage

To use this script, ensure you have the necessary dependencies installed, including Gurobi and Pandas. Run the script to see the allocation results and satisfaction metrics.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


