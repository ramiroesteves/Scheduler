
from ortools.sat.python import cp_model
import pandas as pd

EXEMPT_REPEAT_STEPS = ["ipm", "cml", "tote_cleaning", "print_and_apply"]

def generate_schedule(operators, steps, available_operator_ids, offline_steps, is_4blade):
    model = cp_model.CpModel()

    # Categorize steps by area
    line2_steps = [s for s in steps if "line2" in s['name'] and s['name'] not in offline_steps]
    line3_steps = [s for s in steps if "line3" in s['name'] and s['name'] not in offline_steps]
    general_steps = [s for s in steps if "line2" not in s['name'] and "line3" not in s['name'] and s['name'] not in offline_steps]
    all_active_steps = line2_steps + line3_steps + general_steps

    available_ops = [op for op in operators if op['id'] in available_operator_ids]
    x = {}
    for o in available_ops:
        for s in all_active_steps:
            x[(o['id'], s['name'])] = model.NewBoolVar(f"x_{o['id']}_{s['name']}")

    for s in all_active_steps:
        base_step = base_step_name(s['name'])
        required = s['required']
        model.Add(
            sum(x[(o['id'], s['name'])] for o in available_ops if is_signed(o, base_step)) == required
        )

    for o in available_ops:
        assigned_steps = []
        assigned_base_names = {}
        for s in all_active_steps:
            base_step = base_step_name(s['name'])
            var = x[(o['id'], s['name'])]
            if is_signed(o, base_step):
                assigned_steps.append(var)
                if base_step not in EXEMPT_REPEAT_STEPS:
                    if base_step not in assigned_base_names:
                        assigned_base_names[base_step] = []
                    assigned_base_names[base_step].append(var)
            else:
                model.Add(var == 0)

        model.Add(sum(assigned_steps) <= 3)

        for base, vars_list in assigned_base_names.items():
            model.Add(sum(vars_list) <= 1)

    if is_4blade:
        for s in all_active_steps:
            if "form_fold" in s['name'] and "4blade" in s['name']:
                for o in available_ops:
                    if not any("form_fold_4blade" in s_off for s_off in o['signed_off']):
                        model.Add(x[(o['id'], s['name'])] == 0)

    model.Maximize(0)
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return None

    def format_result(step_group):
        rows = []
        for s in step_group:
            assigned = [f"{o['name']} (ID {o['id']})" for o in available_ops if solver.Value(x[(o['id'], s['name'])]) == 1]
            rows.append({"Step": s['name'], "Assigned Operators": ", ".join(assigned)})
        return pd.DataFrame(rows)

    return {
        "Line 2": format_result(line2_steps),
        "Line 3": format_result(line3_steps),
        "General": format_result(general_steps)
    }

def base_step_name(full_step_name):
    base = full_step_name
    for prefix in ["line2_", "line3_"]:
        base = base.replace(prefix, "")
    for suffix in ["_1st_half", "_2nd_half", "_4blade", "_3lam"]:
        base = base.replace(suffix, "")
    return base

def is_signed(operator, step_base):
    return any(step_base in s for s in operator["signed_off"])
