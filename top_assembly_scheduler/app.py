import streamlit as st
import json
import os
from scheduler import generate_schedule

OPERATORS_PATH = "data/operators.json"
STEPS_PATH = "data/steps.json"

st.set_page_config(page_title="Top Assembly Scheduler", layout="wide")

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path) as f:
            return json.load(f)
    return []

def save_json(data, file_path):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def simplify_step_name(full_step_name):
    step_name_simplify = {
        "tote_cleaning": "Tote Cleaning",
        "ipm": "IPM",
        "cml": "CML",
        "plasma": "Plasma",
        "coating_feed": "Coating Feed",
        "coating_unload": "Coating Unload",
        "leak_test": "Leak Test",
        "form_fold": "Form Fold",
        "coil": "Coil",
        "print_and_apply": "Print & Apply"
    }
    base = full_step_name
    for prefix in ["line2_", "line3_"]:
        base = base.replace(prefix, "")
    for suffix in ["_1st_half", "_2nd_half", "_4blade", "_3lam"]:
        base = base.replace(suffix, "")
    for key in step_name_simplify:
        if base.startswith(key):
            return step_name_simplify[key]
    return base.replace("_", " ").title()

def categorize_half(step_name):
    if "1st_half" in step_name:
        return "1st Half"
    elif "2nd_half" in step_name:
        return "2nd Half"
    else:
        return "Full Day"

# Load data
operators = load_json(OPERATORS_PATH)
steps = load_json(STEPS_PATH)
step_names = [s["name"] for s in steps]

# Tabs
tab1, tab2, tab3 = st.tabs(["📅 Scheduler", "🧑‍🔧 Team Management", "✏️ Edit Operator"])

with tab1:
    st.title("🔧 Daily Operator Scheduler – Top Assembly | Boston Scientific")

    st.sidebar.header("📋 Schedule Settings")
    all_operator_ids = [op["id"] for op in operators]
    unavailable_ops = st.sidebar.multiselect(
        "Select Unavailable Operators:",
        options=all_operator_ids,
        format_func=lambda x: next(op["name"] for op in operators if op["id"] == x)
    )
    available_ops = [op_id for op_id in all_operator_ids if op_id not in unavailable_ops]
    off_steps = st.sidebar.multiselect("Steps temporarily offline:", step_names)
    is_4blade = st.sidebar.checkbox("4-Blade Balloon Production Today", value=False)

        if st.button("📅 Generate Schedule"):
        result = generate_schedule(
            operators=operators,
            steps=steps,
            available_operator_ids=available_ops,
            offline_steps=off_steps,
            is_4blade=is_4blade,
            training_assignments=training_data
        )

        if result:
            st.success("✅ Schedule generated successfully!")
            for group in ["Line 2", "Line 3", "General"]:
                st.subheader(f"📍 {group}")
                df = result[group]
                df["Half"] = df["Step"].apply(categorize_half)
                df["Step"] = df["Step"].apply(simplify_step_name)

                if group == "General":
                    col1, col2, col3 = st.columns(3)
                else:
                    col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**☀️ 1st Half**")
                    st.dataframe(df[df["Half"] == "1st Half"][["Step", "Assigned Operators"]].reset_index(drop=True))

                with col2:
                    st.markdown("**🌙 2nd Half**")
                    st.dataframe(df[df["Half"] == "2nd Half"][["Step", "Assigned Operators"]].reset_index(drop=True))

                if group == "General":
                    with col3:
                        st.markdown("**🕒 Full Day**")
                        st.dataframe(df[df["Half"] == "Full Day"][["Step", "Assigned Operators"]].reset_index(drop=True))

            for group in ["Line 2", "Line 3", "General"]:
                csv = result[group].to_csv(index=False).encode("utf-8")
                st.download_button(f"⬇️ Download {group} Schedule (CSV)", csv, file_name=f"{group.lower().replace(' ', '_')}_schedule.csv", mime="text/csv")

        else:
            st.error("⚠️ Could not generate a valid schedule. Please review inputs.")

    st.markdown("---")
    st.caption("Built with ❤️ using Streamlit and Google OR-Tools | Ramiro Esteves")

with tab2:
    st.title("🧑‍🔧 Team Management – Operator Database")

    subtab1, subtab2 = st.tabs(["➕ Add Operator", "❌ Remove Operator"])

    with subtab1:
        st.subheader("Add New Operator")
        new_name = st.text_input("Operator Name:")
        new_id = st.number_input("Operator ID (must be unique)", min_value=1, step=1)
        signed_steps = st.multiselect("Steps this operator is signed off for:", options=step_names)

        if st.button("✅ Add Operator"):
            if not new_name.strip():
                st.error("Name is required.")
            elif any(op["id"] == new_id for op in operators):
                st.error("This ID is already in use.")
            else:
                operators.append({
                    "id": int(new_id),
                    "name": new_name.strip(),
                    "signed_off": signed_steps
                })
                save_json(operators, OPERATORS_PATH)
                st.success(f"Operator {new_name} added successfully.")
                st.experimental_rerun()

    with subtab2:
        st.subheader("Remove Operator")
        operator_options = {f"{op['name']} (ID {op['id']})": op["id"] for op in operators}
        selected_to_remove = st.selectbox("Select operator to remove:", list(operator_options.keys()))

        if st.button("🗑️ Remove Operator"):
            op_id = operator_options[selected_to_remove]
            operators = [op for op in operators if op["id"] != op_id]
            save_json(operators, OPERATORS_PATH)
            st.success("Operator removed successfully.")
            st.experimental_rerun()

with tab3:
    st.title("✏️ Edit Operator's Signed-Off Steps")

    operator_map = {f"{op['name']} (ID {op['id']})": op for op in operators}
    selected_operator_name = st.selectbox("Select operator to edit:", list(operator_map.keys()))

    if selected_operator_name:
        op = operator_map[selected_operator_name]
        valid_defaults = [s for s in op["signed_off"] if s in step_names]
        edited_steps = st.multiselect(
            f"Edit steps for {op['name']}:",
            options=step_names,
            default=valid_defaults
        )
        if st.button("💾 Save Changes"):
            for operator in operators:
                if operator["id"] == op["id"]:
                    operator["signed_off"] = edited_steps
                    break
            save_json(operators, OPERATORS_PATH)
            st.success("Steps updated successfully.")
            st.experimental_rerun()