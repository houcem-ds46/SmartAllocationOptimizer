import os
import pandas as pd 
import gurobipy as gp
from gurobipy import GRB
import numpy as np
pd.set_option('future.no_silent_downcasting', True)
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


def get_input_data():
    if os.environ.get("LOCAL_EXECUTION") == "False":
        
        from google.colab import auth
        import gspread
        from google.auth import default
        # Autenticating to google
        auth.authenticate_user()
        creds, _ = default()
        gc = gspread.authorize(creds)
        # Defining my worksheet
        worksheet_votes = gc.open_by_key(os.environ.get("MY_GOOGLE_SHEET_ID")).worksheet('votes')
        # Get_all_values gives a list of rows
        rows = worksheet_votes.get_all_values()
        # Convert to a DataFrame
        df_votes = pd.DataFrame(rows[1:], columns=rows[0])

        # Defining my worksheet
        worksheet_projects = gc.open_by_key(os.environ.get("MY_GOOGLE_SHEET_ID")).worksheet('projects')
        # Get_all_values gives a list of rows
        rows = worksheet_projects.get_all_values()
        # Convert to a DataFrame
        df_projects = pd.DataFrame(rows[1:], columns=rows[0])

        # Convert project choice columns to integer type
        df_votes['voted_project_first_choice'] = df_votes['voted_project_first_choice'].astype(int)
        df_votes['voted_project_second_choice'] = df_votes['voted_project_second_choice'].astype(int)
        df_votes['person_id'] = df_votes['person_id'].astype(int)

        df_projects["min_people"] = df_projects["min_people"].astype(int)
        df_projects["max_people"] = df_projects["max_people"].astype(int)
        df_projects["project_id"] = df_projects["project_id"].astype(int)
    else:
        df_votes = pd.read_csv(os.environ.get("INPUT_VOTES_CSV_PATH"))
        df_projects = pd.read_csv(os.environ.get("INPUT_PROJECTS_CSV_PATH"))
        if "include" in df_votes.columns:
            df_votes = df_votes[df_votes["include"]==1].copy()
        if "include" in df_projects.columns:
            df_projects = df_projects[df_projects["include"]==1].copy()

        # (
        #             pd.DataFrame(
        #                 {
        #                 'person_id' : range(21),
        #                 'name' : ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Henry', 'Ivy', 'Jack',
        #                         'Kate', 'Liam', 'Mia', 'Noah', 'Olivia', 'Peter', 'Quinn', 'Rachel', 'Sam', 'Tina', 'Lolo'],
        #                 'voted_project_first_choice': [0, 1, 2, 3, 4, 0, 1, 2, 3, 4,
        #                     0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0], 
        #                 'voted_project_second_choice': [1, 2, 3, 4, 0, 1, 2, 3, 4, 0,
        #                     1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1]}
        #             )
        #         )

        
        # # New dataframe for projects
        # df_projects = pd.DataFrame({
        #     'project_id': range(5),
        #     'min_people': [2, 2, 2, 2, 4],
        #     'max_people': [4, 4, 4, 4, 4]
        # })
        
   
    print(df_votes)
    print(df_projects)
    return df_votes, df_projects

def greedy_allocation(df_votes, df_projects):
    """
    Simulates a naive logic where the allocator goes through the list of people, 
    prioritizes them by seniority, 
    and allocates them to their first choice if possible, 
    otherwise to their second choice, 
    until the budget is exhausted or all people are served.
    """
    timer_start = pd.Timestamp.now()
    # Initialize an empty allocation dictionary
    nb_of_people = len(df_votes)
    greedy_allocation_list = [np.nan] * nb_of_people
    used_budget = 0
    served_seniority_score = df_votes['person_seniority'].max()
    served_person_id = []
    used_projects = []

    # Create a copy of the projects DataFrame to track remaining capacity
    projects = df_projects.set_index('project_id').copy()

    # greedy allocation loop
    while used_budget < int(os.getenv("PROJECT_BUDGET")) and served_seniority_score >= 0 and len(served_person_id) < nb_of_people:
        for _, row in df_votes.iterrows():
            person_id = row['person_id']
            first_choice = row['voted_project_first_choice']
            second_choice = row['voted_project_second_choice']
            person_seniority = row['person_seniority']
            if person_id not in served_person_id and person_seniority == served_seniority_score:
                print("...serving person_id with seniority ", person_id, person_seniority)
                # Get the costs beforehand
                first_cost = projects.loc[first_choice, 'project_cost']
                second_cost = projects.loc[second_choice, 'project_cost']
                # Try to allocate the person to their first choice if there's capacity
                if greedy_allocation_list.count(first_choice) < projects.loc[first_choice, 'max_people'] and (used_budget + first_cost) <= int(os.getenv("PROJECT_BUDGET")) :
                    greedy_allocation_list[person_id] = first_choice
                    served_person_id.append(person_id)
                    used_budget += first_cost
                    if first_choice not in used_projects:
                        used_projects.append(first_choice)
                    print("person_id ", person_id, " allocated to first_choice ", first_choice, " used_budget: ", used_budget)
                # If not, try to allocate them to their second choice
                elif greedy_allocation_list.count(second_choice) < projects.loc[second_choice, 'max_people'] and (used_budget + second_cost) <= int(os.getenv("PROJECT_BUDGET")):
                    greedy_allocation_list[person_id] = second_choice
                    served_person_id.append(person_id)
                    used_budget += second_cost
                    if second_choice not in used_projects:
                        used_projects.append(second_choice)
                    print("person_id ", person_id, " allocated to second_choice ", second_choice, " used_budget: ", used_budget)

                
        # Decrease the served seniority score for the next iteration
        served_seniority_score -= 1


    print("used_budget: ", used_budget)
    assert used_budget <= int(os.getenv("PROJECT_BUDGET")), "Budget exceeded in greedy allocation"
    print("used_projects: ", used_projects)
    print("len(served_person_id)    : ", len(served_person_id))
    # After the budget is exhausted and people with the highest seniority have been served, we can try to allocate remaining people to projects that are not yet at their maximum capacity, even if they didn't vote for them.
    for project_id in set(used_projects):
        allocated_count = greedy_allocation_list.count(project_id)
        print("project_id ", project_id, " allocated_count ", allocated_count)
        #min_people = projects.loc[project_id, 'min_people']
        max_people = projects.loc[project_id, 'max_people']
        while allocated_count <= max_people and  len(served_person_id) < nb_of_people:
            # Select a random person from the unallocated people having the most seniority to allocate to this project :
            unallocated_people = [p for p in range(nb_of_people) if greedy_allocation_list[p] is np.nan and p not in served_person_id]
            df_votes_unallocated = df_votes[df_votes['person_id'].isin(unallocated_people)]

            # Define a custom priority score based the person votes for the project and his/her seniority. 
            # This will help us to prioritize the allocation of people to projects that they voted for, while also considering their seniority.
            df_votes_unallocated["priority_score"] = 0
            df_votes_unallocated.loc[df_votes_unallocated['voted_project_first_choice'] == project_id, 'priority_score'] += 10_000
            df_votes_unallocated.loc[df_votes_unallocated['voted_project_second_choice'] == project_id, 'priority_score'] += 5_000
            df_votes_unallocated["priority_score"] += df_votes_unallocated["person_seniority"]
            df_votes_unallocated = df_votes_unallocated.sort_values(by="priority_score", ascending=False)

            for _, row in df_votes_unallocated.iterrows():
                person_id = row['person_id']
                #Allocate the person 
                greedy_allocation_list[person_id] = project_id

                allocated_count += 1
                print("person_id ", person_id, " allocated to project_id ", project_id, " because maximum capacity is not reached")
                served_person_id.append(person_id)
                break  # Break after allocating one person to this project
        timer_end = pd.Timestamp.now()
        greedy_duration = (timer_end - timer_start).total_seconds()
    return greedy_allocation_list, greedy_duration



def create_model(df_votes, df_projects):
    timer_start = pd.Timestamp.now()

    nb_of_people = len(df_votes)
    num_projects = len(df_projects)
    print(nb_of_people)
    print(num_projects)
    model = gp.Model('project_allocation')

    num_projects = len(df_projects)  # Store the number of projects

    # Create decision variables
    x = model.addVars(nb_of_people, num_projects, vtype=GRB.BINARY, name="x")


    
    # Define a binary variable to flag if a project is at least allocated to one person
    var_project_c_is_used = {}
    for c in range(num_projects):
        var_project_c_is_used[c] = model.addVar(vtype=GRB.BINARY, name=f'var_P_is_allocated_{c}')

    # Definition of variable var_project_c_is_used : it indicates if project c was used
    big_M = nb_of_people * 10   # A large number to ensure the constraint is effective
    for c in range(num_projects):
        model.addConstr(
            gp.quicksum( x[p, c] for p in range(nb_of_people))
            <= var_project_c_is_used[c] * big_M
            , name=f"definition_of_project_is_being_used_{c}"
        )

    # Add constraints to ensure each person is assigned to exactly one project
    for _, row in df_votes.iterrows():
        person_id = row['person_id']
        model.addConstr(
            gp.quicksum(x[person_id, c] for c in range(num_projects)) <= 1,
            name=f"ensure_at_most_one_project_is_allocated_to_person_id_{person_id}"
        )
    
  
    # Add constraints to ensure each project has at least min_people and at most max_people
    for _, row in df_projects.iterrows():
        c = row['project_id']
        min_people = row['min_people']
        max_people = row['max_people']
        print("project_id: ", c)
        print("min_people: ", min_people)
        print("max_people: ", max_people)
        print("-----------------------------------")

        model.addConstr(
            gp.quicksum(x[p, c] for p in range(nb_of_people)) >= min_people*var_project_c_is_used[c],
            name=f"min_people_project_{c}"
        )
        model.addConstr(
            gp.quicksum(x[p, c] for p in range(nb_of_people)) <= max_people*var_project_c_is_used[c],
            name=f"max_people_project_{c}"
        )

        # Set objective function    
    person_seniority = df_votes.set_index('person_id')['person_seniority'].to_dict()
    objective_weighted_satisfaction_score = gp.quicksum(
            person_seniority[p] * (x[p, c1] + 0.5 * x[p, c2]) 
            for p in range(nb_of_people)
            for c1, c2 in zip(df_votes.loc[df_votes["person_id"]==p ,"voted_project_first_choice"], df_votes.loc[df_votes["person_id"]==p, "voted_project_second_choice"])
    ) 


    cost_project = df_projects.set_index('project_id')['project_cost'].to_dict()
    objective_cost_of_used_projects = gp.quicksum(
            cost_project[c] * var_project_c_is_used[c] for c in range(num_projects)
    )  


    if os.getenv("BUDGET_IS_HARD_CONSTRAINT") == "True":
        # Add a constraint to ensure the total cost of used projects does not exceed the budget
        model.addConstr(
                objective_cost_of_used_projects
                <= int(os.getenv("PROJECT_BUDGET")) 
                , name=f"respecting_budget_constraint"
        )
        # Objective function maximizes the weighted satisfaction score
        obj = objective_weighted_satisfaction_score 
        model.setObjective(obj, GRB.MAXIMIZE)
    else:
        # Define budget Overun variable 
        overrun = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name="budget_overrun")

        # add a constraint to define the overrun variable
        model.addConstr(
            objective_cost_of_used_projects <= int(os.getenv("PROJECT_BUDGET")) + overrun,
            name="respecting_budget_constraint_with_flexibility"
        )

        # Dont overrun more than 5% of budget
        model.addConstr(
                overrun
                <= float(os.getenv("BUDGET_OVERRUN_PCT")) * int(os.getenv("PROJECT_BUDGET"))
                , name=f"respecting_budget_constraint"
        )

        # Defining lambda value to penalize the overrun in the objective function. This value can be adjusted based on how much you want to penalize exceeding the budget.
        lambda_val = 0.001 

        # 4. Tu modifies ta fonction objectif pour pénaliser le dépassement
        obj = objective_weighted_satisfaction_score - (lambda_val * overrun)
        model.setObjective(obj, GRB.MAXIMIZE)
    




    
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
        print(f'Weighted satisfaction score: {objective_weighted_satisfaction_score.getValue()}')
        print(f'Cost of used_projects: {objective_cost_of_used_projects.getValue()}')

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
    timer_end = pd.Timestamp.now()
    optim_duration = (timer_end - timer_start).total_seconds()
    return solution, optim_duration


def post_process_solution(df_votes, df_projects, solution, solution_type, solution_duration=None):
    nb_of_people = len(df_votes)
    
    # Update df_votes with the solution
    df_votes_enriched = (
        df_votes.copy()
        .assign(allocated_to_project_id=solution)
        .assign(is_allocated_project_in_choices=lambda x: x.apply(lambda row: row['allocated_to_project_id'] in [row['voted_project_first_choice'], row['voted_project_second_choice']], axis=1))
        .assign(got_his_her_first_choice=lambda x: x.apply(lambda row: row['allocated_to_project_id'] in [row['voted_project_first_choice']], axis=1))
        .assign(got_his_her_second_choice=lambda x: x.apply(lambda row: row['allocated_to_project_id'] in [row['voted_project_second_choice']], axis=1))
    )
    print("\n")
    print(df_votes_enriched)

    df_project_allocation = (
        df_projects.copy()
        .merge(
            df_votes_enriched.groupby('allocated_to_project_id')['name'].apply(list).reset_index(name='members'), 
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

    # Define custum KPI metrics
    kpi_dict = dict()
    kpi_dict["nb_of_people"] = nb_of_people
    kpi_dict["nb_of_people_satisfied"] = int(df_votes_enriched["is_allocated_project_in_choices"].sum())
    kpi_dict["nb_of_people_got_his_her_first_choice"] = int(df_votes_enriched["got_his_her_first_choice"].sum())
    kpi_dict["nb_of_people_got_his_her_second_choice"] = int(df_votes_enriched["got_his_her_second_choice"].sum())
    kpi_dict["nb_of_people_not_allocated"] = int(df_votes_enriched["allocated_to_project_id"].isna().sum())
    kpi_dict["percentage_of_people_satisfied"] = int(df_votes_enriched["is_allocated_project_in_choices"].sum()*100/nb_of_people)
    kpi_dict["percentage_of_people_got_his_her_first_choice"] = int(df_votes_enriched["got_his_her_first_choice"].sum()*100/nb_of_people)
    kpi_dict["percentage_of_people_got_his_her_second_choice"] = int(df_votes_enriched["got_his_her_second_choice"].sum()*100/nb_of_people)
    kpi_dict["percentage_of_people_not_allocated"] = int(df_votes_enriched["allocated_to_project_id"].isna().sum()*100/nb_of_people)
    kpi_dict["number_of_projects"] = len(df_projects)
    kpi_dict["number_of_projects_allocated_to_minimum_capacity"] = int((df_project_allocation["count_members"] == df_project_allocation["min_people"]).sum())
    kpi_dict["number_of_projects_allocated_to_maximum_capacity"] = int((df_project_allocation["count_members"] == df_project_allocation["max_people"]).sum())
    kpi_dict["number_of_projects_without_any_allocated_member"] = int((df_project_allocation["count_members"] == 0).sum())
    kpi_dict["weighted_satisfaction_score"] = df_votes_enriched.apply(lambda row: row['person_seniority'] * (1 if row['got_his_her_first_choice'] else 0.5 if row['got_his_her_second_choice'] else 0), axis=1).sum()
    kpi_dict["cost_of_used_projects"] = df_projects.loc[df_project_allocation["count_members"]>0, "project_cost"].sum()
    kpi_dict["solution_duration"] = solution_duration if solution_duration is not None else 0

    df_kpi = pd.DataFrame(
        kpi_dict.items(),
        columns=["KPI_NAME", "KPI_VALUE"]
    )
    df_kpi["SOLUTION_TYPE"] = solution_type
    print(f'\t-{int(df_votes_enriched["is_allocated_project_in_choices"].sum()*100/nb_of_people)} % of people are satisfied ')
    print(f'\t\t-{int(df_votes_enriched["got_his_her_first_choice"].sum()*100/nb_of_people)} % of people got his/her first choice')
    print(f'\t\t-{int(df_votes_enriched["got_his_her_second_choice"].sum()*100/nb_of_people)} % of people got his/her second choice')
    print(f'\t-Percentage of people who arent allocated to a project is {int(df_votes_enriched["allocated_to_project_id"].isna().sum()*100/nb_of_people)} %')

    print(df_kpi)

    return df_votes_enriched, df_project_allocation, df_kpi



def display_allocation_results_graph(df_votes, df_projects, df_kpi, solution_type):
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go

    # Filtrer les KPIs pour le type de solution demandé
    df_kpi_filtered = df_kpi[df_kpi["SOLUTION_TYPE"] == solution_type]
    
    # Créer un texte formaté avec les KPIs (en HTML pour Plotly)
    kpi_text = f"<b>KPIs ({solution_type})</b><br><br>"
    for idx, row in df_kpi_filtered.iterrows():
        # Formater la valeur (par exemple enlever les décimales si c'est un entier)
        val = int(row['KPI_VALUE']) if row['KPI_VALUE'] % 1 == 0 else row['KPI_VALUE']
        kpi_text += f"{row['KPI_NAME']}: {val}<br>"

    # 1. Charger les données
    df = df_votes.copy()

    # 2. Préparation des données et des libellés
    # Gérer les projets non assignés (NaN)
    df['allocated_project'] = df['allocated_to_project_id'].fillna(-1).astype(int).astype(str)
    df['allocated_project'] = df['allocated_project'].replace('-1', 'Non assigné')

    # Créer le libellé pour chaque personne : "Nom (Séniorité)"
    df['person_label'] = df["person_id"].astype(str) + "-" + df['name'] + ' (sen: ' + df['person_seniority'].astype(str) + ')'

    # Jointure avec df_projects - IMPORTANT : utiliser how='left' pour garder les "Non assigné"
    df = pd.merge(
        df,
        df_projects[['project_id', 'project_name', 'project_cost']],
        left_on='allocated_to_project_id',
        right_on='project_id',
        how='left'
    )

    # Créer le libellé du projet et remplacer les valeurs vides par "Non assigné"
    df['project_label'] = df["project_id"].astype(str) + "-" + df['project_name'] + ' (cost: ' + df['project_cost'].astype(str) + ')'
    df['project_label'] = df['project_label'].fillna('Non assigné')

    # Extraire les listes uniques pour les axes Y (basé sur le nouveau project_label)
    people = df['person_label'].tolist() 
    projects = sorted(df['project_label'].unique().tolist())

    # S'assurer que "Non assigné" s'affiche en bas si présent
    if 'Non assigné' in projects:
        projects.remove('Non assigné')
        projects.append('Non assigné')

    # 3. Calculer les positions (Y) pour espacer uniformément de haut en bas
    y_people = np.linspace(1, 0, len(people))
    y_projects = np.linspace(1, 0, len(projects))

    # Mapping pour retrouver la coordonnée Y de chaque personne et de chaque projet
    person_y_map = dict(zip(people, y_people))
    project_y_map = dict(zip(projects, y_projects))

    # 4. Initialiser la figure Plotly
    fig = go.Figure()

    # Ajouter les lignes de connexion
    for idx, row in df.iterrows():
        p_label = row['person_label']
        proj_label = row['project_label'] # Utilisation du nouveau libellé
        
        # Appliquer ta règle de couleurs
        if row['got_his_her_first_choice']:
            color = '#2ca02c' # Vert
        elif row['got_his_her_second_choice']:
            color = '#ff7f0e' # Orange
        else:
            color = '#7f7f7f' # Gris
            
        y0 = person_y_map[p_label]
        y1 = project_y_map[proj_label] # Mapping avec le nom complet du projet
        
        # Tracer la ligne
        fig.add_trace(go.Scatter(
            x=[0, 1],
            y=[y0, y1],
            mode='lines+markers',
            line=dict(color=color, width=2.5),
            marker=dict(color=color, size=6),
            hoverinfo='skip',
            showlegend=False
        ))

    # 5. Ajouter les libellés à gauche (Personnes)
    fig.add_trace(go.Scatter(
        x=[0] * len(people),
        y=y_people,
        mode='text',
        text=people,
        textposition='middle left',
        textfont=dict(size=12),
        showlegend=False,
        hoverinfo='none'
    ))

    # 6. Ajouter les libellés à droite (Projets)
    fig.add_trace(go.Scatter(
        x=[1] * len(projects),
        y=y_projects,
        mode='text',
        text=projects, # Le texte est déjà correctement formaté dans la liste "projects"
        textposition='middle right',
        textfont=dict(size=12, color='black'),
        showlegend=False,
        hoverinfo='none'
    ))

    # 7. Mise en forme finale pour l'esthétique du slope graph
    # On ajoute une marge à droite (r=250) pour avoir la place d'afficher les KPIs
    fig.update_layout(
        title=dict(text=f'<b>Allocation des collab aux projets avec la solution {solution_type}</b>', font=dict(size=20), x=0.5),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 1.8]), # On étend un peu le range X
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white',
        margin=dict(l=20, r=250, t=80, b=20), 
        height=max(600, len(people) * 30)
    )

    # 8. Ajouter les KPIs en annotation sur le côté droit
    fig.add_annotation(
        x=1.6, # Position X (au-delà des projets)
        y=0.9, # Position Y (vers le haut du graphe)
        text=kpi_text,
        showarrow=False,
        align='left',
        font=dict(size=12, color="black"),
        bgcolor="white",
        bordercolor="black",
        borderwidth=1,
        borderpad=10
    )

    fig.show()



def display_kpi_compraison(df_kpi):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # --- 1. Extraire les données pour le Graphique 1 (Satisfaction) ---
    kpi_name_1 = 'weighted_satisfaction_score'
    df_g1 = df_kpi[df_kpi['KPI_NAME'] == kpi_name_1]
    val_greedy_1 = df_g1[df_g1['SOLUTION_TYPE'] == 'Greedy']['KPI_VALUE'].values[0]
    val_optim_1 = df_g1[df_g1['SOLUTION_TYPE'] == 'Optim']['KPI_VALUE'].values[0]
    gap_pct_1 = ((val_optim_1 - val_greedy_1) / val_greedy_1) * 100

    # --- 2. Extraire les données pour le Graphique 2 (Coût) ---
    kpi_name_2 = 'cost_of_used_projects'
    df_g2 = df_kpi[df_kpi['KPI_NAME'] == kpi_name_2]
    val_greedy_2 = df_g2[df_g2['SOLUTION_TYPE'] == 'Greedy']['KPI_VALUE'].values[0]
    val_optim_2 = df_g2[df_g2['SOLUTION_TYPE'] == 'Optim']['KPI_VALUE'].values[0]
    gap_pct_2 = ((val_optim_2 - val_greedy_2) / val_greedy_2) * 100

    # --- 3. Extraire les données pour le Graphique 3 (Durée en ms) ---
    kpi_name_3 = 'solution_duration' 
    df_g3 = df_kpi[df_kpi['KPI_NAME'] == kpi_name_3]
    val_greedy_3 = df_g3[df_g3['SOLUTION_TYPE'] == 'Greedy']['KPI_VALUE'].values[0] * 1000
    val_optim_3 = df_g3[df_g3['SOLUTION_TYPE'] == 'Optim']['KPI_VALUE'].values[0] * 1000
    gap_pct_3 = ((val_optim_3 - val_greedy_3) / val_greedy_3) * 100

    # --- 4. Extraire les données pour le Graphique 4 (Choix) ---
    kpi_name_4a = 'nb_of_people_got_his_her_first_choice'
    kpi_name_4b = 'nb_of_people_got_his_her_second_choice'
    
    df_g4a = df_kpi[df_kpi['KPI_NAME'] == kpi_name_4a]
    val_greedy_4a = df_g4a[df_g4a['SOLUTION_TYPE'] == 'Greedy']['KPI_VALUE'].values[0]
    val_optim_4a = df_g4a[df_g4a['SOLUTION_TYPE'] == 'Optim']['KPI_VALUE'].values[0]
    
    df_g4b = df_kpi[df_kpi['KPI_NAME'] == kpi_name_4b]
    val_greedy_4b = df_g4b[df_g4b['SOLUTION_TYPE'] == 'Greedy']['KPI_VALUE'].values[0]
    val_optim_4b = df_g4b[df_g4b['SOLUTION_TYPE'] == 'Optim']['KPI_VALUE'].values[0]

    # --- Initialiser la figure (2 lignes, 3 colonnes) ---
    # Le paramètre 'specs' permet de fusionner des cellules.
    # Ici, la ligne 2 a un graphique qui prend les 3 colonnes ("colspan": 3).
    fig = make_subplots(
        rows=2, cols=3,
        specs=[
            [{"type": "bar"}, {"type": "bar"}, {"type": "bar"}],
            [{"type": "bar", "colspan": 3}, None, None]
        ],
        subplot_titles=(
            f"Score de satisfaction<br>(Gap: {gap_pct_1:+.1f}%)", 
            f"Coût des projets ($)<br>(Gap: {gap_pct_2:+.1f}%)", 
            f"Durée de résolution (ms)<br>(Gap: {gap_pct_3:+.1f}%)", 
            "Répartition des choix"
        ),
        vertical_spacing=0.15 # Ajoute un peu d'espace entre la ligne 1 et la ligne 2
    )

    # --- Ajouter les traces ---
    
    # Graphique 1 (Ligne 1, Col 1)
    fig.add_trace(
        go.Bar(
            name='Score (Greedy/Optim)',
            x=['Greedy', 'Optim'],
            y=[val_greedy_1, val_optim_1],
            marker_color=['grey', 'lightblue'], 
            text=[round(val_greedy_1, 2), round(val_optim_1, 2)], 
            textposition='auto',
            showlegend=False
        ),
        row=1, col=1
    )

    # Graphique 2 (Ligne 1, Col 2)
    fig.add_trace(
        go.Bar(
            name='Coût (Greedy/Optim)',
            x=['Greedy', 'Optim'],
            y=[val_greedy_2, val_optim_2],
            marker_color=['grey', 'lightblue'], 
            text=[f"${round(val_greedy_2):,}", f"${round(val_optim_2):,}"], 
            textposition='auto',
            showlegend=False
        ),
        row=1, col=2
    )

    # Graphique 3 (Ligne 1, Col 3)
    fig.add_trace(
        go.Bar(
            name='Durée (Greedy/Optim)',
            x=['Greedy', 'Optim'],
            y=[val_greedy_3, val_optim_3],
            marker_color=['grey', 'lightblue'], 
            text=[f"{round(val_greedy_3, 1)} ms", f"{round(val_optim_3, 1)} ms"], 
            textposition='auto',
            showlegend=False
        ),
        row=1, col=3
    )

    # Graphique 4 (Ligne 2, Col 1 - s'étend sur 3 colonnes) - Double barre (1er Choix)
    fig.add_trace(
        go.Bar(
            name='Nb de collab ayant obtenu leur 1er choix',
            x=['Greedy', 'Optim'],
            y=[val_greedy_4a, val_optim_4a],
            marker_color='#2ca02c', 
            text=[int(val_greedy_4a), int(val_optim_4a)],
            textposition='auto',
            showlegend=True
        ),
        row=2, col=1
    )
    
    # Graphique 4 (Ligne 2, Col 1) - Double barre (2ème Choix)
    fig.add_trace(
        go.Bar(
            name='Nb de collab ayant obtenu leur 2ème choix',
            x=['Greedy', 'Optim'],
            y=[val_greedy_4b, val_optim_4b],
            marker_color='#ff7f0e', 
            text=[int(val_greedy_4b), int(val_optim_4b)],
            textposition='auto',
            showlegend=True
        ),
        row=2, col=1
    )

    # --- Mise en forme globale ---
    fig.update_layout(
        title_text="<b>Comparatif des Solutions : Greedy vs Optim</b>",
        title_x=0.5,
        plot_bgcolor='white',
        height=1000, 
        barmode='group',
        # Placement de la légende à droite
        legend=dict(
            orientation="v", # Vertical
            yanchor="middle", 
            y=0.25, # Position sur l'axe Y (plus proche du graphique du bas)
            xanchor="left", 
            x=1.02 # Juste à l'extérieur du graphique, sur la droite
        )
    )

    # Afficher la figure
    fig.show()

    
if __name__ == "__main__":
    df_votes, df_projects = get_input_data()


    ######### GREEDY SOLUTION
    df_greedy_allocation, greedy_duration = greedy_allocation(df_votes, df_projects)
    print(f"Time taken for Greedy allocation: {greedy_duration} seconds")
    df_votes_greedy, df_projects_greedy, df_kpi_greedy = post_process_solution(df_votes, df_projects, df_greedy_allocation, solution_type="Greedy", solution_duration=greedy_duration)
    display_allocation_results_graph(df_votes_greedy, df_projects_greedy, df_kpi_greedy, solution_type="Greedy")

    #Save greedy output to CSV files
    df_votes_greedy.to_csv(os.getenv("OUTPUT_GREEDY_VOTES_CSV_PATH"), index=False)
    df_projects_greedy.to_csv(os.getenv("OUTPUT_GREEDY_PROJECTS_CSV_PATH"), index=False)


    ######### OPTIM SOLUTION
    solution, optim_duration = create_model(df_votes, df_projects)
    print(f"Time taken for Optim allocation: {optim_duration} seconds")
    if solution is not None:
        df_votes_optim, df_projects_optim, df_kpi_optim= post_process_solution(df_votes, df_projects, solution, solution_type="Optim", solution_duration=optim_duration)
        df_votes_optim.to_csv(os.getenv("OUTPUT_OPTIM_VOTES_CSV_PATH"), index=False)
        df_projects_optim.to_csv(os.getenv("OUTPUT_OPTIM_PROJECTS_CSV_PATH"), index=False)
        display_allocation_results_graph(df_votes_optim, df_projects_optim, df_kpi_optim, solution_type="Optim")

    
    df_kpi_cont = pd.concat([df_kpi_greedy, df_kpi_optim], axis=0).sort_values(by="KPI_NAME", ascending=True).reset_index(drop=True)
    display_kpi_compraison(df_kpi_cont)
    
    df_kpi_cont.to_csv(os.getenv("OUTPUT_KPI_CSV_PATH"), index=False)
    print(df_kpi_cont)
