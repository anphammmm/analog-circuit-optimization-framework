import datetime as dt
import math
import os
import shutil
import subprocess

import numpy as np
import pandas as pd


# ============================================================
# USER CONFIGURATION
# ============================================================
BATCH_SIZE = 1
POPULATION_SIZE = 20
NUM_ITERATIONS = 10
NUM_RUNS = 1

OCEAN_SCRIPT = "oceanScript.ocn"
PARAM_FILE = "PSO_circuit_params.txt"
RESULT_FILE = "Result_Analyse.txt"
EXCEL_FILE = "Optimize_PSO_result.xlsx"


# ============================================================
# PARAMETER CONFIGURATION
# Chia bien thanh 2 nhom:
# 1. OPTIMIZED_PARAMETERS: bien duoc toi uu
# 2. FIXED_PARAMETERS: bien giu co dinh
# 3. LINKED_PARAMETERS: bien phu thuoc vao bien khac
# ============================================================
OPTIMIZED_PARAMETERS = [
    {"name": "L", "scale": 1e-6, "unit": "um"},
    {"name": "W", "scale": 1e-6, "unit": "um"},
    {"name": "R4", "scale": 1.0, "unit": "ohm"},
    {"name": "R0", "scale": 1.0, "unit": "ohm"},
    # {"name": "R5", "scale": 1.0, "unit": "ohm"},
    {"name": "R1", "scale": 1.0, "unit": "ohm"},
    # {"name": "R2", "scale": 1.0, "unit": "ohm"},
    # {"name": "R3", "scale": 1.0, "unit": "ohm"},
]

FIXED_PARAMETERS = [
    {"name": "VDD", "value": 2.0, "scale": 1.0, "unit": "V"},
    {"name": "Ibias", "value": 100.0, "scale": 1e-9, "unit": "nA"},
    {"name": "Cout", "value": 0.0, "scale": 1e-12, "unit": "pF"},
    {"name": "Cc", "value": 0.0, "scale": 1e-12, "unit": "pF"},
]

LINKED_PARAMETERS = [
    {"name": "R2", "source": "R1"},
    {"name": "R3", "source": "R1"},
    {"name": "R5", "source": "R4"},
]


# Thu tu nay phai giong thu tu fscanf(...) trong oceanScript.ocn
INPUT_PARAMETER_ORDER = [
    "L",
    "W",
    "Cc",
    "R4",
    "Cout",
    "Ibias",
    "R0",
    "VDD",
    "R5",
    "R1",
    "R2",
    "R3",
]

OUTPUT_NAMES = [
    "cond",
    "TC",
    "PSRR_1k",
    "Gain_Margin",
    "Phase_Margin",
]


OPTIMIZED_MAP = {item["name"]: item for item in OPTIMIZED_PARAMETERS}
FIXED_MAP = {item["name"]: item for item in FIXED_PARAMETERS}
LINKED_MAP = {item["name"]: item for item in LINKED_PARAMETERS}
OUTPUT_COUNT = len(OUTPUT_NAMES)
OPTIMIZED_PARAMETER_COUNT = len(OPTIMIZED_PARAMETERS)


def validate_parameter_configuration():
    input_set = set(INPUT_PARAMETER_ORDER)

    optimized_set = set(OPTIMIZED_MAP.keys())
    fixed_set = set(FIXED_MAP.keys())
    linked_set = set(LINKED_MAP.keys())

    configured_set = optimized_set | fixed_set | linked_set

    overlap_opt_fixed = optimized_set & fixed_set
    overlap_opt_linked = optimized_set & linked_set
    overlap_fixed_linked = fixed_set & linked_set

    if overlap_opt_fixed:
        overlap = ", ".join(sorted(overlap_opt_fixed))
        raise ValueError(f"Parameters appear in both OPTIMIZED and FIXED: {overlap}")

    if overlap_opt_linked:
        overlap = ", ".join(sorted(overlap_opt_linked))
        raise ValueError(f"Parameters appear in both OPTIMIZED and LINKED: {overlap}")

    if overlap_fixed_linked:
        overlap = ", ".join(sorted(overlap_fixed_linked))
        raise ValueError(f"Parameters appear in both FIXED and LINKED: {overlap}")

    if configured_set != input_set:
        missing = sorted(input_set - configured_set)
        extra = sorted(configured_set - input_set)
        raise ValueError(
            "INPUT_PARAMETER_ORDER does not match configured parameters. "
            f"Missing={missing}, Extra={extra}"
        )

    for item in LINKED_PARAMETERS:
        name = item["name"]
        source = item["source"]

        if source not in configured_set:
            raise ValueError(
                f"LINKED parameter '{name}' refers to unknown source '{source}'"
            )

        if source in linked_set:
            raise ValueError(
                f"LINKED parameter '{name}' cannot use another LINKED parameter "
                f"'{source}' as source. Please link only to OPTIMIZED or FIXED parameters."
            )

    for item in OPTIMIZED_PARAMETERS:
        if "scale" not in item:
            raise ValueError(f"OPTIMIZED parameter '{item['name']}' is missing 'scale'")

    for item in FIXED_PARAMETERS:
        if "value" not in item:
            raise ValueError(f"FIXED parameter '{item['name']}' is missing 'value'")
        if "scale" not in item:
            raise ValueError(f"FIXED parameter '{item['name']}' is missing 'scale'")


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
    with open(PARAM_FILE, "w") as fout:
        for solution in batch_solutions:
            full_param = get_full_parameter_dict(solution)
            for param_name in INPUT_PARAMETER_ORDER:
                fout.write(f"\n{full_param[param_name]}")


def run_ocean_script():
    subprocess.run(
        ["ocean", "-nograph", "-restore", OCEAN_SCRIPT],
        check=True,
    )


def read_result_file(expected_batch_size):
    with open(RESULT_FILE) as fin:
        raw_values = [line.strip() for line in fin if line.strip()]

    result_values = np.array(raw_values, dtype=float)
    expected_size = OUTPUT_COUNT * expected_batch_size

    if result_values.size != expected_size:
        raise ValueError(
            f"Unexpected number of values in {RESULT_FILE}: "
            f"got {result_values.size}, expected {expected_size}"
        )

    return result_values.reshape(OUTPUT_COUNT, expected_batch_size)


def calculate_fom(cond, tc, psrr_1k, gain_margin, phase_margin):
    fom = np.zeros_like(tc, dtype=float)
    tc_safe = np.maximum(np.abs(tc), 1e-12)
    valid = (cond >= 1.0) & (gain_margin > 0.0) & (phase_margin >= 45.0)

    fom[valid] = (
        np.abs(psrr_1k[valid])
        * np.maximum(gain_margin[valid], 0.0)
        * np.maximum(phase_margin[valid], 0.0)
        / tc_safe[valid]
    )
    return fom


def calFitness(num_samples, sol):
    param_result_total = np.zeros((OUTPUT_COUNT, num_samples), dtype=float)
    loop_count = math.ceil(num_samples / BATCH_SIZE)

    for batch_idx in range(loop_count):
        start = batch_idx * BATCH_SIZE
        stop = min(start + BATCH_SIZE, num_samples)
        current_batch_size = stop - start

        write_parameter_file(sol[start:stop])
        run_ocean_script()
        batch_result = read_result_file(current_batch_size)
        param_result_total[:, start:stop] = batch_result

    cond = param_result_total[0, :].reshape(-1)
    tc = param_result_total[1, :].reshape(-1)
    psrr_1k = param_result_total[2, :].reshape(-1)
    gain_margin = param_result_total[3, :].reshape(-1)
    phase_margin = param_result_total[4, :].reshape(-1)

    fom = calculate_fom(cond, tc, psrr_1k, gain_margin, phase_margin)
    return fom, cond, tc, psrr_1k, gain_margin, phase_margin


def create_folder_path(index_value):
    now = dt.date.today()
    month = now.strftime("%b")
    day = now.strftime("%d")
    year = now.strftime("%Y")
    formatted_date = f"{index_value}_{day}-{month}-{year}"
    return os.path.join(os.getcwd(), formatted_date)


def build_history_columns():
    columns = ["Lan chay", "Begin", "End", "Time (s)", "FoM"]

    for cfg in OPTIMIZED_PARAMETERS:
        columns.append(f"{cfg['name']} ({cfg['unit']})")

    for cfg in FIXED_PARAMETERS:
        columns.append(f"{cfg['name']} ({cfg['unit']}, fixed)")

    columns.extend(
        [
            "cond",
            "TC (ppm/C)",
            "PSRR_1k (dB)",
            "Gain_Margin (dB)",
            "Phase_Margin (degree)",
        ]
    )
    return columns


class TLBO_Algorithm:
    def __init__(self, D, P, iterations, bounds, function, df, rng=None):
        self.D = D
        self.P = P
        self.iter = iterations
        self.Func = function
        self.df = df
        self.rng = np.random.RandomState() if rng is None else rng

        self.Lb = bounds[:, 0]
        self.Ub = bounds[:, 1]

        self.population = np.zeros((self.P, self.D), dtype=float)
        self.fitness = np.zeros(self.P, dtype=float)
        self.cond = np.zeros(self.P, dtype=float)
        self.TC = np.zeros(self.P, dtype=float)
        self.PSRR_1k = np.zeros(self.P, dtype=float)
        self.Gain_Margin = np.zeros(self.P, dtype=float)
        self.Phase_Margin = np.zeros(self.P, dtype=float)

        self.best = np.zeros(self.D, dtype=float)
        self.best_fom = -np.inf
        self.param_best = np.zeros(5, dtype=float)

    def initialize_population(self):
        self.population = self.Lb + self.rng.random_sample((self.P, self.D)) * (self.Ub - self.Lb)
        (
            self.fitness,
            self.cond,
            self.TC,
            self.PSRR_1k,
            self.Gain_Margin,
            self.Phase_Margin,
        ) = self.Func(self.P, self.population)
        self.update_global_best()

    def evaluate_one_candidate(self, candidate):
        fom, cond, tc, psrr_1k, gain_margin, phase_margin = self.Func(1, candidate.reshape(1, -1))
        return (
            fom[0],
            cond[0],
            tc[0],
            psrr_1k[0],
            gain_margin[0],
            phase_margin[0],
        )

    def update_global_best(self):
        best_idx = int(np.argmax(self.fitness))
        if self.fitness[best_idx] > self.best_fom:
            self.best_fom = self.fitness[best_idx]
            self.best[:] = self.population[best_idx]
            self.param_best[0] = self.cond[best_idx]
            self.param_best[1] = self.TC[best_idx]
            self.param_best[2] = self.PSRR_1k[best_idx]
            self.param_best[3] = self.Gain_Margin[best_idx]
            self.param_best[4] = self.Phase_Margin[best_idx]

    def append_history_row(self, run_index, begin_time):
        row = {
            "Lan chay": run_index,
            "Begin": begin_time,
            "End": dt.datetime.now().strftime("%H:%M:%S"),
            "Time (s)": (
                dt.datetime.strptime(dt.datetime.now().strftime("%H:%M:%S"), "%H:%M:%S")
                - dt.datetime.strptime(begin_time, "%H:%M:%S")
            ).total_seconds(),
            "FoM": self.best_fom,
        }

        for idx, cfg in enumerate(OPTIMIZED_PARAMETERS):
            row["%s (%s)" % (cfg["name"], cfg["unit"])] = self.best[idx]

        for cfg in FIXED_PARAMETERS:
            row["%s (%s, fixed)" % (cfg["name"], cfg["unit"])] = cfg["value"]

        row["cond"] = self.param_best[0]
        row["TC (ppm/C)"] = self.param_best[1]
        row["PSRR_1k (dB)"] = self.param_best[2]
        row["Gain_Margin (dB)"] = self.param_best[3]
        row["Phase_Margin (degree)"] = self.param_best[4]

        self.df.loc[len(self.df)] = row

    def teacher_phase(self):
        mean_pop = np.mean(self.population, axis=0)
        teacher = self.population[int(np.argmax(self.fitness))].copy()
        tf = self.rng.randint(1, 3)

        for i in range(self.P):
            r = self.rng.random_sample(self.D)
            new = self.population[i] + r * (teacher - tf * mean_pop)
            new = np.clip(new, self.Lb, self.Ub)

            (
                f_new,
                cond_new,
                tc_new,
                psrr_new,
                gm_new,
                pm_new,
            ) = self.evaluate_one_candidate(new)

            if f_new > self.fitness[i]:
                self.population[i] = new
                self.fitness[i] = f_new
                self.cond[i] = cond_new
                self.TC[i] = tc_new
                self.PSRR_1k[i] = psrr_new
                self.Gain_Margin[i] = gm_new
                self.Phase_Margin[i] = pm_new

    def learner_phase(self):
        for i in range(self.P):
            j = i
            while j == i:
                j = self.rng.randint(0, self.P)

            r = self.rng.random_sample(self.D)
            if self.fitness[i] > self.fitness[j]:
                new = self.population[i] + r * (self.population[i] - self.population[j])
            else:
                new = self.population[i] + r * (self.population[j] - self.population[i])

            new = np.clip(new, self.Lb, self.Ub)

            (
                f_new,
                cond_new,
                tc_new,
                psrr_new,
                gm_new,
                pm_new,
            ) = self.evaluate_one_candidate(new)

            if f_new > self.fitness[i]:
                self.population[i] = new
                self.fitness[i] = f_new
                self.cond[i] = cond_new
                self.TC[i] = tc_new
                self.PSRR_1k[i] = psrr_new
                self.Gain_Margin[i] = gm_new
                self.Phase_Margin[i] = pm_new

    def select_individual(self):
        begin_time = dt.datetime.now().strftime("%H:%M:%S")
        self.initialize_population()
        self.append_history_row(0, begin_time)

        for t in range(self.iter):
            begin_time = dt.datetime.now().strftime("%H:%M:%S")

            self.teacher_phase()
            self.learner_phase()
            self.update_global_best()

            self.append_history_row(t + 1, begin_time)
            print(self.df)

        return self.df



if __name__ == "__main__":
    validate_parameter_configuration()

    bounds = np.array(
        [
            [1.0, 100.0],       # L (um)
            [1.0, 100.0],      # W (um)
            [1.0e4, 1.0e6],    # R4 (ohm)
            [1.0e3, 1.0e6],    # R0 (ohm)
            # [1.0e4, 1.0e6],  # R5 (ohm)
            [1.0e4, 1.0e6],    # R1 (ohm)
            # [1.0e4, 1.0e6],  # R2 (ohm)
            # [1.0e4, 1.0e6],  # R3 (ohm)
        ],
        dtype=float,
    )

    if bounds.shape[0] != OPTIMIZED_PARAMETER_COUNT:
        raise ValueError(
            f"bounds has {bounds.shape[0]} rows but OPTIMIZED_PARAMETERS has "
            f"{OPTIMIZED_PARAMETER_COUNT} variables."
        )

    for s in range(NUM_RUNS):
        path = create_folder_path(s)
        os.mkdir(path)

        shutil.copy2(f"./{OCEAN_SCRIPT}", path)
        shutil.copy2(os.path.abspath(__file__), path)

        os.chdir(path)

        df = pd.DataFrame(columns=build_history_columns())
        algorithm = TLBO_Algorithm(
            OPTIMIZED_PARAMETER_COUNT,
            POPULATION_SIZE,
            NUM_ITERATIONS,
            bounds,
            calFitness,
            df,
        )
        df = algorithm.select_individual()

        print("Done one circuit!")
        df.to_excel(f"./{EXCEL_FILE}", sheet_name="TLBO", index=False)

        os.chdir("..")
