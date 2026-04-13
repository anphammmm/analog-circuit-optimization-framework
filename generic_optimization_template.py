import datetime as dt
import math
import os
import shutil
import subprocess

import numpy as np
import pandas as pd


# ============================================================
# PROJECT / TOOL CONFIGURATION
# ============================================================
PROJECT_NAME = "VARIABLE_PROJECT_NAME"
ALGORITHM_NAME = "VARIABLE_ALGORITHM_NAME"
CIRCUIT_NAME = "VARIABLE_CIRCUIT_NAME"

BATCH_SIZE = 1
POPULATION_SIZE = 20
NUM_ITERATIONS = 30
NUM_RUNS = 1

SIMULATOR_COMMAND = ["ocean", "-nograph", "-restore", "VARIABLE_ANALYSE.ocn"]
PARAM_FILE = "VARIABLE_circuit_params.txt"
RESULT_FILE = "VARIABLE_result.txt"
EXCEL_FILE = "VARIABLE_optimization_history.xlsx"

# Files copied into each run folder before simulation starts.
FILES_TO_COPY_TO_RUN_FOLDER = [
    "VARIABLE_ANALYSE.ocn",
]


# ============================================================
# PARAMETER CONFIGURATION
# ============================================================
# Keep only the parameters you want the optimization algorithm to update.
OPTIMIZED_PARAMETERS = [
    {"name": "VARIABLE_1", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_2", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_3", "lower": 1.0, "upper": 100.0, "scale": 1e-12, "unit": "pF"},
]

# Fixed parameters are written to the simulator input file but never updated
# by the algorithm.
FIXED_PARAMETERS = [
    {"name": "FIXED_1", "value": 1.8, "scale": 1.0, "unit": "V"},
]

# Linked parameters copy the value of another parameter. This is useful when
# two devices must share the same width/length/current.
LINKED_PARAMETERS = [
    {"name": "LINKED_1", "source": "VARIABLE_1"},
]

# The order below must match the order expected by the simulator script.
INPUT_PARAMETER_ORDER = [
    "VARIABLE_1",
    "VARIABLE_2",
    "VARIABLE_3",
    "FIXED_1",
    "LINKED_1",
]


# ============================================================
# OUTPUT CONFIGURATION
# ============================================================
# These names must match the order written by the simulator result file.
OUTPUT_NAMES = [
    "OUTPUT_1",
    "OUTPUT_2",
    "OUTPUT_3",
    "OUTPUT_4",
]


OPTIMIZED_MAP = {item["name"]: item for item in OPTIMIZED_PARAMETERS}
FIXED_MAP = {item["name"]: item for item in FIXED_PARAMETERS}
LINKED_MAP = {item["name"]: item for item in LINKED_PARAMETERS}
OUTPUT_COUNT = len(OUTPUT_NAMES)
OPTIMIZED_PARAMETER_COUNT = len(OPTIMIZED_PARAMETERS)


def validate_parameter_configuration():
    optimized_set = set(OPTIMIZED_MAP.keys())
    fixed_set = set(FIXED_MAP.keys())
    linked_set = set(LINKED_MAP.keys())
    ordered_set = set(INPUT_PARAMETER_ORDER)
    configured_set = optimized_set | fixed_set | linked_set

    duplicate_names = (optimized_set & fixed_set) | (optimized_set & linked_set) | (fixed_set & linked_set)
    if duplicate_names:
        duplicate_str = ", ".join(sorted(duplicate_names))
        raise ValueError(f"Parameter appears in more than one configuration group: {duplicate_str}")

    missing_from_order = configured_set - ordered_set
    missing_from_config = ordered_set - configured_set
    if missing_from_order or missing_from_config:
        raise ValueError(
            "INPUT_PARAMETER_ORDER does not match parameter configuration. "
            f"Missing from order={sorted(missing_from_order)}, "
            f"Missing from config={sorted(missing_from_config)}"
        )

    known_sources = optimized_set | fixed_set | linked_set
    for cfg in LINKED_PARAMETERS:
        if cfg["source"] not in known_sources:
            raise ValueError(
                f"Linked parameter '{cfg['name']}' references unknown source '{cfg['source']}'"
            )

    for cfg in OPTIMIZED_PARAMETERS:
        if cfg["lower"] > cfg["upper"]:
            raise ValueError(f"Invalid bounds for '{cfg['name']}': lower > upper")


def get_bounds_array():
    return np.array([[cfg["lower"], cfg["upper"]] for cfg in OPTIMIZED_PARAMETERS], dtype=float)


def get_full_parameter_dict(solution_vector):
    param_dict = {}

    for idx, cfg in enumerate(OPTIMIZED_PARAMETERS):
        param_dict[cfg["name"]] = solution_vector[idx] * cfg["scale"]

    for cfg in FIXED_PARAMETERS:
        param_dict[cfg["name"]] = cfg["value"] * cfg["scale"]

    for cfg in LINKED_PARAMETERS:
        param_dict[cfg["name"]] = param_dict[cfg["source"]]

    return param_dict


def write_parameter_file(batch_solutions):
    lines = []
    for solution in batch_solutions:
        full_param = get_full_parameter_dict(solution)
        for param_name in INPUT_PARAMETER_ORDER:
            lines.append(str(full_param[param_name]))

    with open(PARAM_FILE, "w") as fout:
        if lines:
            fout.write("\n".join(lines) + "\n")


def run_simulator():
    subprocess.run(SIMULATOR_COMMAND, check=True)


def read_result_file(expected_batch_size):
    with open(RESULT_FILE) as fin:
        raw_values = [line.strip() for line in fin if line.strip()]

    result_values = np.array(raw_values, dtype=float)
    expected_size = OUTPUT_COUNT * expected_batch_size

    if result_values.size != expected_size:
        raise ValueError(
            "Unexpected number of values in %s: got %d, expected %d"
            % (RESULT_FILE, result_values.size, expected_size)
        )

    return result_values.reshape(OUTPUT_COUNT, expected_batch_size)


def batch_result_to_dict(batch_result):
    return {
        output_name: batch_result[idx, :].reshape(-1)
        for idx, output_name in enumerate(OUTPUT_NAMES)
    }


def evaluate_constraints(output_dict):
    """
    CHANGE THIS FUNCTION FOR YOUR CIRCUIT.

    Return:
        valid_mask: numpy bool array, True = feasible solution
        constraint_info: dict for logging/debugging

    Example:
        valid_mask = (
            (output_dict["cond"] >= 1.0)
            & (output_dict["gain_margin"] > 0.0)
            & (output_dict["phase_margin"] >= 45.0)
        )
    """
    valid_mask = (
        (output_dict["OUTPUT_1"] >= 0.0)
        & (output_dict["OUTPUT_2"] >= 0.0)
        & (output_dict["OUTPUT_3"] >= 0.0)
    )

    constraint_info = {
        "valid": valid_mask.astype(int),
    }
    return valid_mask, constraint_info


def calculate_fom(output_dict, valid_mask):
    """
    CHANGE THIS FUNCTION FOR YOUR CIRCUIT.

    Only the feasible solutions should receive a positive FoM. Infeasible
    solutions stay at 0.0 by default.
    """
    fom = np.zeros_like(output_dict[OUTPUT_NAMES[0]], dtype=float)

    metric_1 = np.abs(output_dict["OUTPUT_1"])
    metric_2 = np.maximum(output_dict["OUTPUT_2"], 0.0)
    metric_3 = np.maximum(np.abs(output_dict["OUTPUT_3"]), 1e-12)

    fom[valid_mask] = metric_1[valid_mask] * metric_2[valid_mask] / metric_3[valid_mask]
    return fom


def evaluate_population(num_samples, sol):
    all_outputs = {
        output_name: np.zeros(num_samples, dtype=float)
        for output_name in OUTPUT_NAMES
    }

    loop_count = math.ceil(num_samples / BATCH_SIZE)

    for batch_idx in range(loop_count):
        start = batch_idx * BATCH_SIZE
        stop = min(start + BATCH_SIZE, num_samples)
        current_batch_size = stop - start

        write_parameter_file(sol[start:stop])
        run_simulator()
        batch_result = read_result_file(current_batch_size)
        batch_output_dict = batch_result_to_dict(batch_result)

        for output_name in OUTPUT_NAMES:
            all_outputs[output_name][start:stop] = batch_output_dict[output_name]

    valid_mask, constraint_info = evaluate_constraints(all_outputs)
    fom = calculate_fom(all_outputs, valid_mask)

    result = {
        "fom": fom,
        "valid": valid_mask.astype(int),
    }
    result.update(all_outputs)
    result.update(constraint_info)
    return result


def create_folder_path(run_index):
    now = dt.date.today()
    month = now.strftime("%b")
    day = now.strftime("%d")
    year = now.strftime("%Y")
    formatted_date = f"{run_index}_{day}-{month}-{year}"
    return os.path.join(os.getcwd(), formatted_date)


def prepare_run_folder(run_index):
    path = create_folder_path(run_index)
    os.makedirs(path, exist_ok=True)

    for filename in FILES_TO_COPY_TO_RUN_FOLDER:
        if os.path.exists(filename):
            shutil.copy2(filename, path)

    return path


def build_history_columns():
    columns = [
        "Run",
        "Iteration",
        "Begin",
        "End",
        "Time (s)",
        "FoM",
        "Valid",
    ]

    for cfg in OPTIMIZED_PARAMETERS:
        columns.append(f"{cfg['name']} ({cfg['unit']})")

    for cfg in FIXED_PARAMETERS:
        columns.append(f"{cfg['name']} ({cfg['unit']}, fixed)")

    for cfg in LINKED_PARAMETERS:
        columns.append(f"{cfg['name']} (linked)")

    columns.extend(OUTPUT_NAMES)
    return columns


def append_history_row(df, run_index, iteration_index, begin_dt, best_solution, best_metrics):
    end_dt = dt.datetime.now()
    duration_seconds = (end_dt - begin_dt).total_seconds()

    full_param = get_full_parameter_dict(best_solution)

    row = {
        "Run": run_index,
        "Iteration": iteration_index,
        "Begin": begin_dt.strftime("%H:%M:%S"),
        "End": end_dt.strftime("%H:%M:%S"),
        "Time (s)": duration_seconds,
        "FoM": float(best_metrics["fom"]),
        "Valid": int(best_metrics["valid"]),
    }

    for cfg in OPTIMIZED_PARAMETERS:
        row[f"{cfg['name']} ({cfg['unit']})"] = best_solution[OPTIMIZED_PARAMETERS.index(cfg)]

    for cfg in FIXED_PARAMETERS:
        row[f"{cfg['name']} ({cfg['unit']}, fixed)"] = full_param[cfg["name"]]

    for cfg in LINKED_PARAMETERS:
        row[f"{cfg['name']} (linked)"] = full_param[cfg["name"]]

    for output_name in OUTPUT_NAMES:
        row[output_name] = float(best_metrics[output_name])

    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


class TemplateOptimizationAlgorithm:
    """
    This class is intentionally simple. Replace `propose_new_population`
    with DSA, TLBO, PSO, GA, DE, or your own hybrid update rule.
    """

    def __init__(self, population_size, iterations, bounds, evaluator, df, rng=None):
        self.population_size = population_size
        self.iterations = iterations
        self.bounds = bounds
        self.evaluator = evaluator
        self.df = df
        self.rng = np.random.default_rng() if rng is None else rng

        self.dimension = bounds.shape[0]
        self.lower_bounds = bounds[:, 0]
        self.upper_bounds = bounds[:, 1]

        self.population = np.zeros((self.population_size, self.dimension), dtype=float)
        self.metrics = {}
        self.best_solution = np.zeros(self.dimension, dtype=float)
        self.best_metrics = None

    def initialize_population(self):
        self.population = self.lower_bounds + self.rng.random((self.population_size, self.dimension)) * (
            self.upper_bounds - self.lower_bounds
        )
        self.metrics = self.evaluator(self.population_size, self.population)
        self.update_global_best()

    def propose_new_population(self, iteration_index):
        """
        CHANGE THIS FUNCTION FOR YOUR ALGORITHM.

        Examples:
        - TLBO: teacher phase + learner phase
        - DSA: donor/search/acceptance rule
        - Hybrid: combine TLBO teacher step with DSA perturbation step
        """
        anneal = 1.0 - (iteration_index / max(self.iterations, 1))
        step = 0.15 * max(anneal, 0.05) * (self.upper_bounds - self.lower_bounds)
        noise = self.rng.normal(loc=0.0, scale=1.0, size=self.population.shape)
        candidate_population = self.population + noise * step
        return np.clip(candidate_population, self.lower_bounds, self.upper_bounds)

    def greedy_accept(self, candidate_population, candidate_metrics):
        improved = candidate_metrics["fom"] > self.metrics["fom"]
        if np.any(improved):
            self.population[improved] = candidate_population[improved]
            for key in self.metrics:
                self.metrics[key][improved] = candidate_metrics[key][improved]

    def update_global_best(self):
        best_index = int(np.argmax(self.metrics["fom"]))
        best_fom = self.metrics["fom"][best_index]

        if self.best_metrics is None or best_fom > self.best_metrics["fom"]:
            self.best_solution = self.population[best_index].copy()
            self.best_metrics = {
                key: self.metrics[key][best_index].item() if np.ndim(self.metrics[key][best_index]) == 0 else self.metrics[key][best_index]
                for key in self.metrics
            }

    def run(self, run_index):
        begin_dt = dt.datetime.now()
        self.initialize_population()
        self.df = append_history_row(self.df, run_index, 0, begin_dt, self.best_solution, self.best_metrics)

        for iteration_index in range(1, self.iterations + 1):
            begin_dt = dt.datetime.now()
            candidate_population = self.propose_new_population(iteration_index)
            candidate_metrics = self.evaluator(self.population_size, candidate_population)
            self.greedy_accept(candidate_population, candidate_metrics)
            self.update_global_best()
            self.df = append_history_row(
                self.df,
                run_index,
                iteration_index,
                begin_dt,
                self.best_solution,
                self.best_metrics,
            )

        return self.df


def main():
    validate_parameter_configuration()
    bounds = get_bounds_array()
    columns_name = build_history_columns()

    for run_index in range(NUM_RUNS):
        run_folder = prepare_run_folder(run_index)
        base_dir = os.getcwd()
        os.chdir(run_folder)

        try:
            df = pd.DataFrame(columns=columns_name)
            algorithm = TemplateOptimizationAlgorithm(
                population_size=POPULATION_SIZE,
                iterations=NUM_ITERATIONS,
                bounds=bounds,
                evaluator=evaluate_population,
                df=df,
            )
            df = algorithm.run(run_index)
            df.to_excel(EXCEL_FILE, sheet_name=ALGORITHM_NAME or "Template", index=False)
            print(f"Completed run {run_index} for {PROJECT_NAME} / {CIRCUIT_NAME}")
        finally:
            os.chdir(base_dir)


if __name__ == "__main__":
    main()
