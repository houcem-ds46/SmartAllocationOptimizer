import pandas as pd 
import gurobipy as gp
from gurobipy import GRB
import numpy as np

def get_input_data():
    df_votes = (
            pd.DataFrame(
                {
                'person_id' : range(20),
                'name' : ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Henry', 'Ivy', 'Jack',
                        'Kate', 'Liam', 'Mia', 'Noah', 'Olivia', 'Peter', 'Quinn', 'Rachel', 'Sam', 'Tina'],
                'voted_project_first_choice': [0, 1, 2, 3, 4, 0, 1, 2, 3, 4,
                    0, 1, 2, 3, 4, 0, 1, 2, 3, 4], 
                'voted_project_second_choice': [1, 2, 3, 4, 0, 1, 2, 3, 4, 0,
                    1, 2, 3, 4, 0, 1, 2, 3, 4, 0]}
            )
        )
    print(df_votes)

    # New dataframe for projects
    df_projects = pd.DataFrame({
        'project_id': range(5),
        'min_people': [2, 2, 2, 2, 4],
        'max_people': [4, 4, 4, 4, 4]
    })
    print(df_projects)

    return df_votes, df_projects


def create_model(df_votes, df_projects):
    nb_of_people = len(df_votes)
    num_projects = len(df_projects)
    print(nb_of_people)
    print(num_projects)
    model = gp.Model('project_allocation')

    num_projects = len(df_projects)  # Store the number of projects

    # Create decision variables
    x = model.addVars(nb_of_people, num_projects, vtype=GRB.BINARY, name="x")

    # Set objective function
    obj = gp.quicksum(
        x[p, c1] + 0.5 * x[p, c2]
        for p in range(nb_of_people)
        for c1, c2 in zip(df_votes["voted_project_first_choice"], df_votes["voted_project_second_choice"])
    )
    model.setObjective(obj, GRB.MAXIMIZE)

    # Add constraints to ensure each person is assigned to exactly one project
    for _, row in df_votes.iterrows():
        person_id = row['person_id']
        model.addConstr(
            gp.quicksum(x[person_id, c] for c in range(num_projects)) <= 1,
            name=f"ensure_at_most_one_project_is_allocated_to_person_id_{person_id}"
        )
    
  
    # Add constraints to ensure each project has at least min_people and at most max_people
    for _, row in df_projects.iterrows():
        project_id = row['project_id']
        min_people = row['min_people']
        max_people = row['max_people']
        print("project_id: ", project_id)
        print("min_people: ", min_people)
        print("max_people: ", max_people)
        print("-----------------------------------")
        model.addConstr(
            gp.quicksum(x[p, project_id] for p in range(nb_of_people)) >= min_people,
            name=f"min_people_project_{project_id}"
        )
        model.addConstr(
            gp.quicksum(x[p, project_id] for p in range(nb_of_people)) <= max_people,
            name=f"max_people_project_{project_id}"
        )
    
    # Model optimize
    model.optimize()

    # Check the optimization status
    if model.status == GRB.OPTIMAL:
        print("Optimal solution found")
    elif model.status == GRB.INFEASIBLE:
        print("Model is infeasible")
        model.computeIIS()
        print("The following constraints and bounds are causing the infeasibility:")
        for c in model.getConstrs():
            if c.IISConstr:
                print(f'\t-Constraint {c.ConstrName}: {c.Sense} {c.RHS}')
        for v in model.getVars():
            if v.IISLB:
                print(f'\t-Lower bound of variable {v.VarName}: {v.LB}')
            if v.IISUB:
                print(f'\t-Upper bound of variable {v.VarName}: {v.UB}')
        print("\nTo resolve infeasibility, consider relaxing these constraints or bounds.")
    elif model.status == GRB.UNBOUNDED:
        print("Model is unbounded")
    else:
        print(f"Optimization was stopped with status {model.status}")

    if model.status == GRB.OPTIMAL:
        # retrieve the objective value
        print(f'Optimal value of objective function: {model.objVal}')

        # retrieve the solution
        solution = [np.nan] * nb_of_people
        for p in range(nb_of_people):
            for c in range(num_projects):
                if x[p, c].X > 0.5:
                    solution[p] = c
        for project_id in range(num_projects):
            print(f"\t-Project {project_id} has {sum([x[p, project_id].X for p in range(nb_of_people)])} people allocated")
    else:
        solution = None
    
    return solution


def post_process_solution(df_votes, df_projects, solution):
    nb_of_people = len(df_votes)
    
    # Update df_votes with the solution
    df_votes = (
        df_votes.copy()
        .assign(allocated_to_project_id=solution)
        .assign(is_allocated_project_in_choices=lambda x: x.apply(lambda row: row['allocated_to_project_id'] in [row['voted_project_first_choice'], row['voted_project_second_choice']], axis=1))
        .assign(got_his_her_first_choice=lambda x: x.apply(lambda row: row['allocated_to_project_id'] in [row['voted_project_first_choice']], axis=1))
        .assign(got_his_her_second_choice=lambda x: x.apply(lambda row: row['allocated_to_project_id'] in [row['voted_project_second_choice']], axis=1))
    )
    print("\n")
    print(df_votes)

    df_project_allocation = (
        df_projects.copy()
        .merge(
            df_votes.groupby('allocated_to_project_id')['name'].apply(list).reset_index(name='members'), 
            left_on='project_id', 
            right_on='allocated_to_project_id', 
            how='left'
        )
        .assign(count_members=lambda x: x['members'].apply(lambda m: len(m) if isinstance(m, list) else 0))
        .drop(columns=['allocated_to_project_id'])
    )
    print("\n")
    print(df_project_allocation)

    print("Results summary:")
    print(f'\t-{int(df_votes["is_allocated_project_in_choices"].sum()*100/nb_of_people)} % of people are satisfied ')
    print(f'\t\t-{int(df_votes["got_his_her_first_choice"].sum()*100/nb_of_people)} % of people got his/her first choice')
    print(f'\t\t-{int(df_votes["got_his_her_second_choice"].sum()*100/nb_of_people)} % of people got his/her second choice')
    print(f'\t-Percentage of people who arent allocated to a project is {int(df_votes["allocated_to_project_id"].isna().sum()*100/nb_of_people)} %')

if __name__ == "__main__":
    df_votes, df_projects = get_input_data()
    solution = create_model(df_votes, df_projects)
    if solution is not None:
        post_process_solution(df_votes, df_projects, solution)

