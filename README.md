# Project Allocation Optimization

This repository solves an optimization problem using MILP techniques (Mixed Integer Linear Programming). It is designed to solve an allocation problem with Gurobi optimizer. The core of the solution is implemented in the `create_model` function, which utilizes the Gurobi optimization solver to allocate individuals to projects based on their preferences.

## Problem formulation and modelization 

We are provided with a classic example of a binary integer programming model in operations research. It aims to maximize overall satisfaction while adhering to project capacity constraints.

### Decision Variables:
- **x[p, c]**: A binary decision variable where `x[p, c] = 1` if person `p` is assigned to project `c`, and `0` otherwise. These variables are used to determine the allocation of each person to a project.

### Objective Function:
- The objective function is to maximize the total satisfaction derived from the project allocations. It is formulated as:

  $$\text{maximize} \quad \sum_{p} \left( x[p, \text{firstChoice(p)}] + 0.5 \times x[p, \text{secondChoice(p)}] \right)$$

  `firstChoice(p)` being the first choice project of the person `p` and `secondChoice(p)` being his/her second choice.
  This function gives full weight to a person's first choice and half weight to their second choice, reflecting the relative importance of these preferences.

### Constraints:
1. **Assignment Constraint**:
   - Each person can be assigned to at most one project:

     $$\sum_{c} x[p, c] \leq 1, \quad \forall p$$

   This ensures that no person is allocated to more than one project.

2. **Project Capacity Constraints**:
   - Each project must have a number of people between its specified minimum and maximum limits:

     $$\sum_{p} x[p, c] \geq \text{minimumPeople}(c), \quad \forall c$$

     $$\sum_{p} x[p, c] \leq \text{maximumPeople}(c), \quad \forall c$$

   These constraints ensure that each project is neither under- nor over-subscribed.




# Script Overview

Here's a summary of what each part of the code does:

1. **Data Preparation (`get_input_data` function):**
   - Creates a DataFrame `df_votes` containing information about 20 people, including their IDs, names, and their first and second project choices.
   - Creates a DataFrame `df_projects` with details about 5 projects, specifying the minimum and maximum number of people that can be assigned to each project.
   - Prints both DataFrames and returns them for further processing.

2. **Model Creation and Optimization (`create_model` function):**
   - Initializes a Gurobi optimization model to allocate people to projects.
   - Defines binary decision variables `x` to represent whether a person is assigned to a project.
   - Sets an objective function to maximize the satisfaction of people's project choices, giving full weight to first choices and half weight to second choices.
   - Adds constraints to ensure each person is assigned to at most one project and that each project has a number of people within its specified limits.
   - Optimizes the model and checks the status of the solution, handling cases of optimality, infeasibility, and unboundedness.
   - If an optimal solution is found, it extracts the solution and prints the number of people allocated to each project.

3. **Solution Post-Processing (`post_process_solution` function):**
   - Updates the `df_votes` DataFrame with the allocation results, indicating whether each person got their first or second choice.
   - Merges the allocation results with `df_projects` to show which members are assigned to each project and counts the number of members per project.
   - Prints a summary of the results, including the percentage of people satisfied with their allocation and those who got their first or second choice.

4. **Execution (`__main__` block):**
   - Calls the functions in sequence to get input data, create and solve the model, and post-process the solution if one is found.

Overall, the script uses optimization to allocate people to projects based on their preferences while respecting project capacity constraints.

## Usage

To use this script, ensure you have the necessary dependencies installed, including Gurobi and Pandas. Run the script to see the allocation results and satisfaction metrics.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


