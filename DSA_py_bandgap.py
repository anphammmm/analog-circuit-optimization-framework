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
EXCEL_FILE = "Optimize_DSA_result.xlsx"

# 1: B-DSA, 2: S-DSA, 3: E1-DSA, 4: E2-DSA
# Co the dung 1 gia tri, hoac tuple/list de hybrid
DSA_METHOD = (1, 2, 3, 4)


# ============================================================
# PARAMETER CONFIGURATION
# Chia bien thanh 3 nhom:
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
        raise ValueError("Parameters appear in both OPTIMIZED and FIXED: %s" % overlap)

    if overlap_opt_linked:
        overlap = ", ".join(sorted(overlap_opt_linked))
        raise ValueError("Parameters appear in both OPTIMIZED and LINKED: %s" % overlap)

    if overlap_fixed_linked:
        overlap = ", ".join(sorted(overlap_fixed_linked))
        raise ValueError("Parameters appear in both FIXED and LINKED: %s" % overlap)

    if configured_set != input_set:
        missing = sorted(input_set - configured_set)
        extra = sorted(configured_set - input_set)
        raise ValueError(
            "INPUT_PARAMETER_ORDER does not match configured parameters. "
            "Missing=%s, Extra=%s" % (missing, extra)
        )

    for item in LINKED_PARAMETERS:
        name = item["name"]
        source = item["source"]

        if source not in configured_set:
            raise ValueError(
                "LINKED parameter '%s' refers to unknown source '%s'" % (name, source)
            )

        if source in linked_set:
            raise ValueError(
                "LINKED parameter '%s' cannot use another LINKED parameter '%s' as source. "
                "Please link only to OPTIMIZED or FIXED parameters." % (name, source)
            )

    for item in OPTIMIZED_PARAMETERS:
        if "scale" not in item:
            raise ValueError("OPTIMIZED parameter '%s' is missing 'scale'" % item["name"])

    for item in FIXED_PARAMETERS:
        if "value" not in item:
            raise ValueError("FIXED parameter '%s' is missing 'value'" % item["name"])
        if "scale" not in item:
            raise ValueError("FIXED parameter '%s' is missing 'scale'" % item["name"])


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
                fout.write("\n%s" % full_param[param_name])


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
            "Unexpected number of values in %s: got %d, expected %d"
            % (RESULT_FILE, result_values.size, expected_size)
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
    loop_count = int(math.ceil(float(num_samples) / float(BATCH_SIZE)))

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
    formatted_date = "%s_%s-%s-%s" % (index_value, day, month, year)
    return os.path.join(os.getcwd(), formatted_date)


def build_history_columns():
    columns = ["Lan chay", "Begin", "End", "Time (s)", "FoM"]

    for cfg in OPTIMIZED_PARAMETERS:
        columns.append("%s (%s)" % (cfg["name"], cfg["unit"]))

    for cfg in FIXED_PARAMETERS:
        columns.append("%s (%s, fixed)" % (cfg["name"], cfg["unit"]))

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


class DSA_Algorithm:
    def __init__(self, D, P, iterations, bounds, function, df, method=(1, 2, 3, 4), rng=None):
        self.D = D
        self.P = P
        self.iter = iterations
        self.Func = function
        self.df = df
        self.rng = np.random.RandomState() if rng is None else rng

        self.Lb = bounds[:, 0]
        self.Ub = bounds[:, 1]

        if isinstance(method, (int, np.integer)):
            self.method_list = [int(method)]
        else:
            self.method_list = list(method)

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
        self.population = self.genpop(self.P, self.D, self.Lb, self.Ub)
        (
            self.fitness,
            self.cond,
            self.TC,
            self.PSRR_1k,
            self.Gain_Margin,
            self.Phase_Margin,
        ) = self.Func(self.P, self.population)
        self.update_global_best()

    def genpop(self, popsize, dim, low_vec, up_vec):
        r = self.rng.random_sample((popsize, dim))
        return low_vec + r * (up_vec - low_vec)

    def update_bounds(self, population, low_vec, up_vec):
        popsize, dim = population.shape
        new_pop = population.copy()

        for i in range(popsize):
            for j in range(dim):
                if new_pop[i, j] < low_vec[j]:
                    if self.rng.random_sample() < self.rng.random_sample():
                        new_pop[i, j] = self.rng.random_sample() * (up_vec[j] - low_vec[j]) + low_vec[j]
                    else:
                        new_pop[i, j] = low_vec[j]

                if new_pop[i, j] > up_vec[j]:
                    if self.rng.random_sample() < self.rng.random_sample():
                        new_pop[i, j] = self.rng.random_sample() * (up_vec[j] - low_vec[j]) + low_vec[j]
                    else:
                        new_pop[i, j] = up_vec[j]

        return new_pop

    def generate_direction(self, one_method):
        popsize = self.population.shape[0]

        if one_method == 1:
            perm = self.rng.permutation(popsize)
            direction = self.population[perm, :]
        elif one_method == 2:
            ranked = np.argsort(-self.fitness)
            ind = np.empty(popsize, dtype=int)
            for i in range(popsize):
                r = self.rng.random_sample()
                k = int(np.ceil(r * popsize))
                k = max(k, 1)
                ind[i] = ranked[self.rng.randint(0, k)]
            direction = self.population[ind, :]
        elif one_method == 3:
            ranked = np.argsort(-self.fitness)
            r = self.rng.random_sample()
            k = int(np.ceil(r * popsize))
            k = max(k, 1)
            ibest = ranked[k - 1]
            direction = np.tile(self.population[ibest, :], (popsize, 1))
        elif one_method == 4:
            ibest = int(np.argmax(self.fitness))
            direction = np.tile(self.population[ibest, :], (popsize, 1))
        else:
            raise ValueError("Unknown DSA method: %s" % one_method)

        return direction

    def generate_map_of_active_individuals(self, popsize, dim, p1, p2):
        map_ = np.zeros((popsize, dim), dtype=float)

        if self.rng.random_sample() < self.rng.random_sample():
            if self.rng.random_sample() < p1:
                for i in range(popsize):
                    thresh = self.rng.random_sample()
                    map_[i, :] = (self.rng.random_sample(dim) < thresh).astype(float)
            else:
                for i in range(popsize):
                    j = self.rng.randint(0, dim)
                    map_[i, j] = 1.0
        else:
            for i in range(popsize):
                k = int(np.ceil(p2 * dim))
                k = max(k, 1)
                idx = self.rng.randint(0, dim, size=k)
                map_[i, idx] = 1.0

        return map_

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

    def evolve_one_epoch(self):
        p1 = 0.3 * self.rng.random_sample()
        p2 = 0.3 * self.rng.random_sample()

        one_method = self.method_list[self.rng.randint(0, len(self.method_list))]
        direction = self.generate_direction(one_method)
        map_ = self.generate_map_of_active_individuals(self.P, self.D, p1, p2)

        R = 1.0 / self.rng.gamma(shape=1.0, scale=0.5)

        stopover = self.population + (R * map_) * (direction - self.population)
        stopover = self.update_bounds(stopover, self.Lb, self.Ub)

        (
            fit_stopover,
            cond_new,
            tc_new,
            psrr_new,
            gm_new,
            pm_new,
        ) = self.Func(self.P, stopover)

        improved = fit_stopover > self.fitness

        self.fitness[improved] = fit_stopover[improved]
        self.population[improved, :] = stopover[improved, :]
        self.cond[improved] = cond_new[improved]
        self.TC[improved] = tc_new[improved]
        self.PSRR_1k[improved] = psrr_new[improved]
        self.Gain_Margin[improved] = gm_new[improved]
        self.Phase_Margin[improved] = pm_new[improved]

        self.update_global_best()

    def select_individual(self):
        begin_time = dt.datetime.now().strftime("%H:%M:%S")
        self.initialize_population()
        self.append_history_row(0, begin_time)

        for t in range(self.iter):
            begin_time = dt.datetime.now().strftime("%H:%M:%S")
            self.evolve_one_epoch()
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
            [1.0e3, 1.0e5],    # R0 (ohm)
            # [1.0e4, 1.0e6],  # R5 (ohm)
            [1.0e4, 1.0e6],    # R1 (ohm)
            # [1.0e4, 1.0e6],  # R2 (ohm)
            # [1.0e4, 1.0e6],  # R3 (ohm)
        ],
        dtype=float,
    )

    if bounds.shape[0] != OPTIMIZED_PARAMETER_COUNT:
        raise ValueError(
            "bounds has %d rows but OPTIMIZED_PARAMETERS has %d variables."
            % (bounds.shape[0], OPTIMIZED_PARAMETER_COUNT)
        )

    for s in range(NUM_RUNS):
        path = create_folder_path(s)
        os.mkdir(path)

        shutil.copy2("./%s" % OCEAN_SCRIPT, path)
        shutil.copy2(os.path.abspath(__file__), path)

        os.chdir(path)

        df = pd.DataFrame(columns=build_history_columns())
        algorithm = DSA_Algorithm(
            OPTIMIZED_PARAMETER_COUNT,
            POPULATION_SIZE,
            NUM_ITERATIONS,
            bounds,
            calFitness,
            df,
            method=DSA_METHOD,
        )
        df = algorithm.select_individual()

        print("Done one circuit!")
        df.to_excel("./%s" % EXCEL_FILE, sheet_name="DSA", index=False)

        os.chdir("..")
