# Cadence Analog Optimization Template

This repository provides a reusable Python framework for optimization-driven analog circuit design with Cadence/Ocean in the loop. It is intended for projects where the simulator workflow remains largely unchanged while the optimization algorithm, circuit parameters, constraints, and figure of merit vary from one study to another.

The goal of the repository is to separate the reusable engineering pipeline from the problem-specific parts of the optimization task. Instead of rewriting the whole script each time a new circuit or a new algorithm is tested, the same backbone can be reused while only a small number of clearly identified sections are modified.

Typical use cases include:

- bandgap reference optimization
- LDO optimization
- OTA sizing and tuning
- inverter sizing
- any Cadence-based analog design flow where Python writes parameters, Ocean runs simulations, and Python reads back numerical results

The main reusable entry point in this repository is:

- [generic_optimization_template.py](/D:/Research_Quantum-AI%20for%20AICD/candence/DemoFolder/generic_optimization_template.py)

## Motivation

In many analog optimization scripts, most of the code does not actually belong to the optimization algorithm itself. A large fraction of the script is usually spent on:

- preparing simulator input files
- converting optimization variables into physical values
- handling fixed and linked design parameters
- launching Ocean
- reading simulator outputs
- checking feasibility constraints
- computing a figure of merit
- storing iteration history for later analysis

These parts tend to remain the same even when the optimization method changes from one metaheuristic to another. The template in this repository keeps those shared parts together and isolates the algorithm-specific logic so that different methods can be compared under the same simulation and evaluation pipeline.

This is especially useful in research-oriented repositories where the main question is not whether the simulator flow works, but which optimization strategy performs better under the same experimental conditions.

## Repository Purpose

This repository is designed to support a controlled optimization workflow in which:

- the circuit is fixed
- the simulator flow is fixed
- the simulator outputs are fixed
- the feasibility constraints are fixed
- the figure of merit is fixed
- only the optimization strategy changes

Under that setup, comparisons between DSA, TLBO, PSO, hybrid methods, or any other search strategy become much easier to interpret and reproduce.

## High-Level Workflow

For each candidate solution, the template follows the same sequence:

1. read the optimization vector
2. build a complete parameter dictionary
3. combine optimized, fixed, and linked parameters
4. write the simulator input file in the exact order expected by Ocean
5. call Ocean in batch mode
6. read the result file produced by the simulator
7. map the raw values to named outputs
8. check whether the candidate satisfies all constraints
9. compute a figure of merit for feasible solutions
10. pass the evaluated population back to the optimization algorithm
11. store the best result and relevant metrics in Excel format

This workflow is independent of the optimization algorithm itself. The algorithm only needs a way to propose new candidate solutions, while the surrounding Cadence/Ocean interaction layer stays unchanged.

## Repository Structure

A recommended repository layout is shown below:

```text
repo/
|- README.md
|- generic_optimization_template.py
|- DSA_py_bandgap.py
|- TLBO_py_bandgap.py
|- Hybrid_TLBO_DSA.py
|- Analyse.ocn
|- Analyse_new.ocn
|- example_results/
`- docs/
```

Suggested purpose of each file:

- `README.md`
  Public-facing documentation for repository users and readers.
- `generic_optimization_template.py`
  Reusable template that defines the common optimization workflow.
- `DSA_py_bandgap.py`
  DSA implementation built on top of the shared evaluation pipeline.
- `TLBO_py_bandgap.py`
  TLBO implementation built on top of the shared evaluation pipeline.
- `Hybrid_TLBO_DSA.py`
  Proposed hybrid algorithm using the same simulation and evaluation infrastructure.
- `Analyse.ocn` or `Analyse_new.ocn`
  Ocean scripts responsible for running Cadence simulations and writing result files.
- `example_results/`
  Optional folder containing representative outputs, screenshots, or result tables.

## Core Design Idea

The key design idea in this repository is modularity. The template is split into parts that answer different questions:

- What are the circuit parameters?
- Which of them are optimized?
- Which of them stay fixed?
- Which of them are linked to others?
- In what order should they be written to the simulator?
- Which metrics are returned by the simulator?
- Which combinations of metrics are acceptable?
- How is the objective score computed?
- How does the optimization algorithm update the population?

By separating these concerns, the same codebase can support multiple circuits and multiple algorithms with minimal structural changes.

## Template Sections

The main file is intentionally organized into clearly separated sections:

- `PROJECT / TOOL CONFIGURATION`
- `PARAMETER CONFIGURATION`
- `OUTPUT CONFIGURATION`
- `validate_parameter_configuration()`
- `get_full_parameter_dict()`
- `write_parameter_file()`
- `run_simulator()`
- `read_result_file()`
- `evaluate_constraints()`
- `calculate_fom()`
- `evaluate_population()`
- `TemplateOptimizationAlgorithm`
- `main()`

Each section serves a different role, and most customizations can be done without changing the entire script.

## Running Requirements

The template assumes the following environment:

- Python with `numpy` and `pandas`
- Cadence/Ocean available from the command line
- an Ocean script that reads the parameter file written by Python
- an Ocean script that writes a flat numeric result file readable by Python

If the Cadence environment is not available, the Python script can still be inspected and adapted, but full execution will require the simulator interface to be present.

## Parameter Configuration

The template supports three categories of parameters:

- optimized parameters
- fixed parameters
- linked parameters

This structure reflects a common analog design workflow where some values are free design variables, some values are constants, and some values are derived from or tied to others.

### Optimized Parameters

Optimized parameters are the variables that the algorithm is allowed to change.

Example:

```python
OPTIMIZED_PARAMETERS = [
    {"name": "VARIABLE_1", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_2", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_3", "lower": 1.0, "upper": 100.0, "scale": 1e-12, "unit": "pF"},
]
```

Each item includes:

- `name`
  Human-readable parameter name used internally by the script.
- `lower`
  Lower search bound in optimization space.
- `upper`
  Upper search bound in optimization space.
- `scale`
  Conversion factor applied before writing to the simulator file.
- `unit`
  Label used for logging and exported history.

Example interpretation:

```python
{"name": "L", "lower": 0.18, "upper": 2.0, "scale": 1e-6, "unit": "um"}
```

This means the optimizer searches in micrometers, but the simulator receives values in meters.

### Fixed Parameters

Fixed parameters are written to the simulator input file but are never changed by the optimization algorithm.

Example:

```python
FIXED_PARAMETERS = [
    {"name": "VDD", "value": 1.8, "scale": 1.0, "unit": "V"},
]
```

Typical examples include:

- supply voltage
- ambient temperature
- load current
- reference current
- process selector values

### Linked Parameters

Linked parameters copy values from other parameters.

Example:

```python
LINKED_PARAMETERS = [
    {"name": "MIRROR_W", "source": "VARIABLE_1"},
]
```

This is useful when:

- two transistors must share the same width
- two devices must use the same channel length
- one branch must copy another branch current or resistor value

## Parameter Order In The Simulator Input File

The exact order in which values are written to the simulator input file is controlled by:

```python
INPUT_PARAMETER_ORDER = [
    "VARIABLE_1",
    "VARIABLE_2",
    "VARIABLE_3",
    "FIXED_1",
    "LINKED_1",
]
```

This list is critical. It must match the exact order expected by the Ocean script. Even if the Python code is syntactically correct, the simulation results will be meaningless if the input order does not match the simulator-side parsing order.

The helper function `validate_parameter_configuration()` checks that:

- parameter names do not overlap across groups
- every configured parameter appears in the input order
- the input order does not reference unknown parameters
- linked parameters point to valid sources
- optimized bounds are valid

## How Candidate Solutions Are Expanded

The optimization algorithm works on a compact vector such as:

```python
[x1, x2, x3]
```

but the simulator usually expects a full set of named and scaled parameters.

That translation is performed by:

```python
def get_full_parameter_dict(solution_vector):
```

This function:

- maps optimized variables from vector form to named parameters
- scales them into simulator-ready values
- inserts all fixed parameters
- resolves all linked parameters

The result is a complete dictionary of input values ready to be written to the simulator input file.

## Input File Format

The input file is written by:

```python
def write_parameter_file(batch_solutions):
```

For batch evaluation, the template writes one solution after another, following the order in `INPUT_PARAMETER_ORDER`.

For example, if:

- `BATCH_SIZE = 2`
- `INPUT_PARAMETER_ORDER = ["L", "W", "VDD"]`

then the generated input file will conceptually look like:

```text
L_sample_1
W_sample_1
VDD_sample_1
L_sample_2
W_sample_2
VDD_sample_2
```

This means the file is sample-major. The Ocean script should therefore read the values in the same sequence.

## Simulator Output Configuration

The expected outputs are defined by:

```python
OUTPUT_NAMES = [
    "OUTPUT_1",
    "OUTPUT_2",
    "OUTPUT_3",
    "OUTPUT_4",
]
```

These names determine how the raw simulator result file will be interpreted.

Typical examples of outputs are:

- `cond`
- `tc`
- `psrr_1k`
- `gain_margin`
- `phase_margin`
- `power`
- `gain`
- `f3db`
- `ugbw`
- `line_regulation`
- `load_regulation`

The number of outputs is automatically stored as:

```python
OUTPUT_COUNT = len(OUTPUT_NAMES)
```

## Output File Format

The result reader assumes that the simulator writes a flat numeric file containing:

```text
OUTPUT_COUNT x expected_batch_size
```

values in output-major order.

Example:

- `OUTPUT_NAMES = ["cond", "tc", "psrr_1k"]`
- `expected_batch_size = 2`

Expected file content:

```text
cond_sample_1
cond_sample_2
tc_sample_1
tc_sample_2
psrr_1k_sample_1
psrr_1k_sample_2
```

The function:

```python
def read_result_file(expected_batch_size):
```

performs three tasks:

- reads all non-empty lines
- converts them to floating-point numbers
- verifies that the number of values matches the expected shape

If the size does not match, the script raises an exception immediately. This is important because incorrect result sizes often indicate simulator failure, file corruption, or a mismatch between Ocean output order and Python parsing logic.

## Batch Evaluation

The template supports evaluating several solutions in one simulator call through `BATCH_SIZE`.

This is handled in:

```python
def evaluate_population(num_samples, sol):
```

The population is split into batches. For each batch, the template:

- writes the input parameter file
- runs the simulator
- reads the result file
- places the results back into the global output arrays

This is useful when the simulator flow can process multiple candidate solutions in a single execution.

If the Ocean script only supports one candidate per run, `BATCH_SIZE` should be set to `1`.

## Constraints

Feasibility checking is implemented in:

```python
def evaluate_constraints(output_dict):
```

This function should return:

- `valid_mask`
- `constraint_info`

where:

- `valid_mask` is a Boolean array indicating whether each candidate satisfies the required design constraints
- `constraint_info` is an optional dictionary for logging or debugging extra information

Example:

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

This is the natural place to encode design constraints such as:

- startup condition
- stability margin
- minimum gain
- maximum power
- maximum temperature coefficient
- minimum PSRR
- output voltage window

In the default template, infeasible solutions receive `FoM = 0.0`, which creates a simple penalty-based handling strategy.

## Figure Of Merit

The objective function is implemented in:

```python
def calculate_fom(output_dict, valid_mask):
```

This function can be adapted to match the design goal of the target circuit. Typical FoM definitions may include:

- maximizing gain
- minimizing power
- maximizing PSRR while minimizing temperature coefficient
- maximizing gain-bandwidth per current
- maximizing stability margins under feasibility constraints

Example pattern:

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

Recommended design rule:

- use `evaluate_constraints()` for feasibility
- use `calculate_fom()` for ranking feasible candidates
- keep infeasible candidates at zero or assign a consistent penalty

This separation makes the optimization logic easier to read, debug, and compare across projects.

## Optimization Algorithm Layer

The reusable evaluation infrastructure is separated from the algorithm itself. The algorithm-specific part is placed in:

```python
class TemplateOptimizationAlgorithm:
```

The most important customization point is:

```python
def propose_new_population(self, iteration_index):
```

This function should generate the next candidate population according to the chosen optimization strategy.

The default implementation is intentionally simple and only serves as a placeholder. It demonstrates the interface expected by the rest of the framework but is not meant to be the final algorithm for a real study.

## How To Plug In Another Algorithm

To adapt the template to a specific optimization method, the most common approach is:

1. duplicate `generic_optimization_template.py`
2. rename it according to the target method and circuit
3. keep the simulator interface unchanged
4. replace the placeholder algorithm logic with the actual update rule

Examples:

- for TLBO, implement teacher and learner phases in `propose_new_population()`
- for DSA, implement the search, perturbation, and acceptance mechanism
- for PSO, add velocity and position updates
- for a hybrid method, combine the update rules while preserving the same evaluation pipeline

In many cases, the following methods are the main customization points:

- `propose_new_population()`
- `greedy_accept()`
- `initialize_population()`
- `update_global_best()`

Everything else can remain almost identical.

## Example Research Mapping

A clean comparative research repository could include the following files:

- `DSA_py_bandgap.py`
- `TLBO_py_bandgap.py`
- `Hybrid_TLBO_DSA.py`

All three files can share:

- the same circuit
- the same Ocean script
- the same input parameter definitions
- the same simulator outputs
- the same constraints
- the same FoM

and differ only in the optimization strategy.

This makes the repository easier for readers to understand because it clearly shows that:

- the environment is controlled
- the evaluation process is shared
- the algorithm is the main experimental variable

That is exactly the type of structure that helps communicate the contribution of a proposed hybrid method.

## Logging And Exported Results

The template stores optimization history in an Excel file. The exported history can include:

- run index
- iteration index
- start time
- end time
- elapsed time
- best FoM
- feasibility flag
- optimized parameter values
- fixed parameter values
- linked parameter values
- simulator outputs

This is useful for:

- convergence analysis
- comparing runs across different random seeds
- comparing algorithms under the same setup
- exporting tables for reports, figures, and publications

## Recommended Adaptation Workflow

When adapting the template to a new circuit, the typical workflow is:

1. duplicate `generic_optimization_template.py`
2. rename the file to match the algorithm and circuit
3. set `PROJECT_NAME`, `ALGORITHM_NAME`, and `CIRCUIT_NAME`
4. configure `SIMULATOR_COMMAND`, `PARAM_FILE`, `RESULT_FILE`, and `EXCEL_FILE`
5. define `OPTIMIZED_PARAMETERS`
6. define `FIXED_PARAMETERS`
7. define `LINKED_PARAMETERS`
8. define `INPUT_PARAMETER_ORDER`
9. define `OUTPUT_NAMES`
10. update `evaluate_constraints()`
11. update `calculate_fom()`
12. replace the placeholder optimization logic
13. test first with `BATCH_SIZE = 1`
14. increase population size and iteration count after the flow is verified

This order reduces debugging effort because simulator interface issues are usually easier to isolate before large-scale optimization runs begin.

## What Usually Needs To Change

For a new circuit or a new study, the sections most likely to change are:

- file names and simulator command
- list of design variables
- bounds and scaling
- input parameter order
- output metrics
- constraints
- FoM
- optimization algorithm

The sections least likely to change are:

- input file writing structure
- result file size checking
- batch evaluation flow
- history logging
- general run-folder organization

## Good Practice For Public Release

Before publishing a repository based on this template, it is good practice to:

- remove machine-specific absolute paths
- make sure Ocean file names are consistent across scripts
- explain what each output metric means
- explain the constraint set in engineering terms
- explain the FoM formula in words, not only code
- document the order expected in the input and output text files
- include a small reproducible example if possible
- keep naming consistent across script files, result files, and exported spreadsheets

## Limitations

This template is intentionally focused on a practical Cadence/Ocean optimization workflow. It does not attempt to provide:

- a universal optimization library
- a full multi-objective Pareto framework
- a simulator-agnostic abstraction layer

Instead, it focuses on a workflow that is common in analog circuit research and engineering: Python controls parameter generation and bookkeeping, while Ocean handles the actual circuit simulation and numerical extraction.

## Summary

This repository is not tied to one specific circuit or one specific optimization method. It is a reusable Cadence/Ocean optimization framework where the simulator pipeline stays fixed and the problem-specific logic is easy to replace.

That makes it well suited for:

- adapting quickly to new analog circuits
- comparing optimization algorithms fairly
- publishing structured studies involving DSA, TLBO, PSO, and hybrid optimization methods
- sharing a clear and reusable baseline with other researchers and engineers
