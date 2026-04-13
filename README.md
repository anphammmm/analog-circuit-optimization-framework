# Generic Optimization Template for Cadence / Ocean

This repository now includes a reusable template:

- [generic_optimization_template.py](/D:/Research_Quantum-AI%20for%20AICD/candence/DemoFolder/generic_optimization_template.py)

The goal of this template is simple:

- keep the common workflow unchanged
- change only the parts that depend on the circuit, outputs, FoM, constraints, and optimization algorithm

## 1. Common workflow kept unchanged

The template keeps the same backbone that usually appears in Cadence-based optimization scripts:

1. define input parameters
2. convert an optimization vector into a full parameter dictionary
3. write the simulator input file
4. run Ocean / Cadence
5. read the simulator result file
6. apply constraints
7. calculate FoM
8. let the optimization algorithm update the population
9. save optimization history to Excel

That means when you switch from one circuit to another, or from TLBO to DSA to Hybrid, you do not need to rewrite the whole pipeline.

## 2. Which file to edit

Main file:

- [generic_optimization_template.py](/D:/Research_Quantum-AI%20for%20AICD/candence/DemoFolder/generic_optimization_template.py)

The important sections are already separated clearly:

- `PROJECT / TOOL CONFIGURATION`
- `PARAMETER CONFIGURATION`
- `OUTPUT CONFIGURATION`
- `evaluate_constraints()`
- `calculate_fom()`
- `TemplateOptimizationAlgorithm.propose_new_population()`

## 3. How to customize the template

### 3.1. Set simulator files and run command

Edit these variables near the top of the file:

```python
PROJECT_NAME = "VARIABLE_PROJECT_NAME"
ALGORITHM_NAME = "VARIABLE_ALGORITHM_NAME"
CIRCUIT_NAME = "VARIABLE_CIRCUIT_NAME"

SIMULATOR_COMMAND = ["ocean", "-nograph", "-restore", "VARIABLE_ANALYSE.ocn"]
PARAM_FILE = "VARIABLE_circuit_params.txt"
RESULT_FILE = "VARIABLE_result.txt"
EXCEL_FILE = "VARIABLE_optimization_history.xlsx"
FILES_TO_COPY_TO_RUN_FOLDER = ["VARIABLE_ANALYSE.ocn"]
```

What to change:

- `PROJECT_NAME`: your project or paper name
- `ALGORITHM_NAME`: `DSA`, `TLBO`, `Hybrid_TLBO_DSA`, `PSO`, etc.
- `CIRCUIT_NAME`: your circuit name such as `Bandgap`, `LDO`, `OTA`, `Comparator`
- `SIMULATOR_COMMAND`: the exact command used to call Ocean
- `PARAM_FILE`: the text file written by Python and read by Ocean
- `RESULT_FILE`: the text file written by Ocean and read by Python
- `EXCEL_FILE`: final optimization history file
- `FILES_TO_COPY_TO_RUN_FOLDER`: files that must exist inside each run folder

### 3.2. Set optimization inputs

Edit:

```python
OPTIMIZED_PARAMETERS = [
    {"name": "VARIABLE_1", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_2", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_3", "lower": 1.0, "upper": 100.0, "scale": 1e-12, "unit": "pF"},
]
```

Use this for variables updated by the optimization algorithm.

Meaning of each field:

- `name`: parameter name
- `lower`: lower bound in optimization space
- `upper`: upper bound in optimization space
- `scale`: multiplier used before writing to simulator
- `unit`: only for logging / Excel header

Example:

```python
{"name": "L", "lower": 0.18, "upper": 2.0, "scale": 1e-6, "unit": "um"}
```

If the algorithm works in micrometers but Cadence expects meters, use `scale = 1e-6`.

### 3.3. Set fixed parameters

Edit:

```python
FIXED_PARAMETERS = [
    {"name": "FIXED_1", "value": 1.8, "scale": 1.0, "unit": "V"},
]
```

Use this for parameters that never change during optimization.

Examples:

- `VDD`
- `Temperature`
- `Load_Current`
- `Reference_Current`

### 3.4. Set linked parameters

Edit:

```python
LINKED_PARAMETERS = [
    {"name": "LINKED_1", "source": "VARIABLE_1"},
]
```

Use this when one parameter must copy another parameter.

Typical examples:

- PMOS width equals NMOS width
- two devices share the same length
- mirrored current branch reuses one value

### 3.5. Set the exact input order expected by Ocean

Edit:

```python
INPUT_PARAMETER_ORDER = [
    "VARIABLE_1",
    "VARIABLE_2",
    "VARIABLE_3",
    "FIXED_1",
    "LINKED_1",
]
```

This order is very important.

The function `write_parameter_file()` writes values exactly in this order. If your Ocean script reads parameters in a different order, simulation results will be wrong even if the code runs successfully.

### 3.6. Set outputs

Edit:

```python
OUTPUT_NAMES = [
    "OUTPUT_1",
    "OUTPUT_2",
    "OUTPUT_3",
    "OUTPUT_4",
]
```

These names must match the order used in `RESULT_FILE`.

If your simulator writes:

```text
cond
tc
psrr_1k
phase_margin
```

then use:

```python
OUTPUT_NAMES = ["cond", "tc", "psrr_1k", "phase_margin"]
```

## 4. How the input and output files are interpreted

### 4.1. Input file format

`write_parameter_file(batch_solutions)` writes all input values line by line.

For batch size = 2 and:

- `INPUT_PARAMETER_ORDER = ["L", "W", "VDD"]`

the parameter file will look like:

```text
L_sample_1
W_sample_1
VDD_sample_1
L_sample_2
W_sample_2
VDD_sample_2
```

So the file is written sample by sample.

### 4.2. Result file format

`read_result_file(expected_batch_size)` expects a flat file with:

```text
OUTPUT_COUNT x expected_batch_size
```

numeric values.

For batch size = 2 and:

- `OUTPUT_NAMES = ["cond", "tc", "psrr_1k"]`

the expected result order is:

```text
cond_sample_1
cond_sample_2
tc_sample_1
tc_sample_2
psrr_1k_sample_1
psrr_1k_sample_2
```

So the file is grouped by output, not by sample.

If your Ocean script writes data in another order, you must adjust either:

- the Ocean output writing order
- or the Python reshape / parsing logic

## 5. How to define constraints

Edit the function:

```python
def evaluate_constraints(output_dict):
```

This function must return:

- `valid_mask`: boolean array
- `constraint_info`: additional values for logging

Example for analog constraints:

```python
def evaluate_constraints(output_dict):
    valid_mask = (
        (output_dict["cond"] >= 1.0)
        & (output_dict["gain_margin"] > 0.0)
        & (output_dict["phase_margin"] >= 45.0)
    )

    constraint_info = {
        "valid": valid_mask.astype(int),
    }
    return valid_mask, constraint_info
```

Meaning:

- if a solution satisfies all constraints, it is feasible
- if not, it is infeasible

In the template, infeasible solutions receive `FoM = 0.0` by default.

## 6. How to define FoM

Edit the function:

```python
def calculate_fom(output_dict, valid_mask):
```

Example:

```python
def calculate_fom(output_dict, valid_mask):
    fom = np.zeros_like(output_dict["tc"], dtype=float)
    tc_safe = np.maximum(np.abs(output_dict["tc"]), 1e-12)

    fom[valid_mask] = (
        np.abs(output_dict["psrr_1k"][valid_mask])
        * np.maximum(output_dict["gain_margin"][valid_mask], 0.0)
        * np.maximum(output_dict["phase_margin"][valid_mask], 0.0)
        / tc_safe[valid_mask]
    )
    return fom
```

You can replace this with any objective:

- maximize gain
- minimize power
- maximize GBW / power
- maximize PSRR and minimize TC
- weighted sum of multiple metrics
- penalty-based objective

Recommended rule:

- handle constraints in `evaluate_constraints()`
- calculate the objective only for feasible solutions in `calculate_fom()`

## 7. How to change the optimization algorithm

The common Cadence-related part should stay the same.

Usually you only need to change:

```python
class TemplateOptimizationAlgorithm:
```

and especially:

```python
def propose_new_population(self, iteration_index):
```

That is the place to insert your algorithm logic.

### 7.1. If you use TLBO

Replace `propose_new_population()` with:

- teacher phase
- learner phase
- any selection rule you already use in your TLBO code

### 7.2. If you use DSA

Replace `propose_new_population()` with:

- donor / search step
- trial solution generation
- acceptance rule

### 7.3. If you use your own Hybrid algorithm

Keep the same simulation pipeline and combine your custom steps inside:

- `propose_new_population()`
- optionally `greedy_accept()`

That way, your new algorithm still uses the same:

- parameter writer
- Ocean runner
- result reader
- constraint handler
- FoM evaluator
- Excel logging format

## 8. Suggested workflow when adapting to a new circuit

1. Duplicate `generic_optimization_template.py`
2. Rename it, for example:
   `TLBO_py_bandgap.py`
3. Replace the project/file names at the top
4. Define `OPTIMIZED_PARAMETERS`, `FIXED_PARAMETERS`, and `LINKED_PARAMETERS`
5. Set `INPUT_PARAMETER_ORDER`
6. Set `OUTPUT_NAMES`
7. Edit `evaluate_constraints()`
8. Edit `calculate_fom()`
9. Replace `TemplateOptimizationAlgorithm` with your real algorithm
10. Test with `BATCH_SIZE = 1` first
11. After the file works, increase population size and iteration count

## 9. Example mapping for your GitHub repository

You mentioned three algorithm files:

- `DSA`
- `TLBO`
- `Hybrid` (your proposed algorithm)

You can present them in the repository like this:

- `DSA_py_bandgap.py`
  Uses the same Cadence input/output/FoM pipeline, but the search rule is pure DSA.
- `TLBO_py_bandgap.py`
  Uses the same Cadence input/output/FoM pipeline, but the update rule follows TLBO teacher and learner phases.
- `Hybrid_TLBO_DSA.py`
  Uses the same Cadence input/output/FoM pipeline, but combines TLBO and DSA ideas in one search strategy.

That makes the comparison very clear for GitHub readers:

- same circuit
- same simulator flow
- same constraints
- same FoM
- only the optimization algorithm changes

This is the strongest way to show the value of your proposed Hybrid method, because readers can see that the algorithm is the only major difference.

## 10. Good practice before uploading to GitHub

Before publishing, check these items:

- remove local absolute paths if any
- make sure file names are consistent
- write clearly what each output means
- explain the FoM formula in words
- explain the constraints in words
- mention the expected simulator result file order
- keep one small example in comments for future reuse

## 11. Recommended repository structure

Example:

```text
repo/
├─ README.md
├─ generic_optimization_template.py
├─ DSA_py_bandgap.py
├─ TLBO_py_bandgap.py
├─ Hybrid_TLBO_DSA.py
├─ Analyse.ocn
├─ Analyse_new.ocn
└─ example_results/
```

If you want, the next good step is:

- I can also generate three cleaned public versions named exactly for `DSA`, `TLBO`, and `Hybrid`, all based on this template, so you can upload them directly to GitHub.
