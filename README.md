# Cadence Analog Optimization Template

This repository provides a reusable Python framework for analog circuit optimization with Cadence/Ocean in the loop. It is intended for studies where the simulation workflow stays fixed while the optimization algorithm, circuit parameters, constraints, and figure of merit vary across experiments.

The framework separates reusable infrastructure from problem-specific logic:

- circuit input definition
- simulator input generation
- Ocean execution
- result parsing
- feasibility checking
- FoM evaluation
- optimization history logging

This makes it easier to compare multiple optimization methods under the same simulation and evaluation conditions.

## Overview

The repository is suitable for optimization-driven analog design tasks such as:

- bandgap reference optimization
- LDO optimization
- OTA optimization
- inverter sizing
- any Cadence-based circuit where Python writes input parameters and reads simulator outputs

The main reusable file is:

- [generic_optimization_template.py](/D:/Research_Quantum-AI%20for%20AICD/candence/DemoFolder/generic_optimization_template.py)

## Workflow

For each candidate solution, the template follows the same pipeline:

1. build a complete parameter dictionary from optimized, fixed, and linked parameters
2. write the simulator input file in a predefined order
3. call Ocean in batch mode
4. read the result file produced by the simulator
5. map raw outputs into named metrics
6. check feasibility constraints
7. compute a figure of merit for feasible solutions
8. update the optimization population
9. store optimization history in Excel format

This flow is algorithm-independent. Only the population update rule needs to be replaced when switching between DSA, TLBO, Hybrid TLBO-DSA, PSO, or any other metaheuristic.

## Why This Structure Matters

The template is intended for controlled optimization studies where:

- the circuit is fixed
- the simulation flow is fixed
- the outputs are fixed
- the constraints are fixed
- the FoM is fixed
- only the optimization strategy changes

That setup makes algorithm comparison clearer and more reproducible.

## Suggested Repository Layout

```text
repo/
|- README.md
|- generic_optimization_template.py
|- DSA_py_bandgap.py
|- TLBO_py_bandgap.py
|- Hybrid_TLBO_DSA.py
|- Analyse.ocn
|- Analyse_new.ocn
`- example_results/
```

## Template Structure

The template is organized into the following sections:

- `PROJECT / TOOL CONFIGURATION`
- `PARAMETER CONFIGURATION`
- `OUTPUT CONFIGURATION`
- `evaluate_constraints()`
- `calculate_fom()`
- `TemplateOptimizationAlgorithm`

These are the intended customization points when adapting the framework to another circuit or another algorithm.

## Parameter Model

The template supports three types of parameters.

### Optimized Parameters

These parameters are updated by the optimization algorithm.

```python
OPTIMIZED_PARAMETERS = [
    {"name": "VARIABLE_1", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
    {"name": "VARIABLE_2", "lower": 0.18, "upper": 10.0, "scale": 1e-6, "unit": "um"},
]
```

Each parameter includes:

- `name`: parameter name
- `lower`: lower bound in search space
- `upper`: upper bound in search space
- `scale`: conversion factor before writing to the simulator
- `unit`: unit label for logging

### Fixed Parameters

These parameters are passed to the simulator but are not updated by the algorithm.

```python
FIXED_PARAMETERS = [
    {"name": "FIXED_1", "value": 1.8, "scale": 1.0, "unit": "V"},
]
```

### Linked Parameters

These parameters copy the value of another parameter.

```python
LINKED_PARAMETERS = [
    {"name": "LINKED_1", "source": "VARIABLE_1"},
]
```

This is useful for mirrored devices or matched design variables.

## Simulator Input Interface

The order of values written to the simulator input file is defined by:

```python
INPUT_PARAMETER_ORDER = [
    "VARIABLE_1",
    "VARIABLE_2",
    "FIXED_1",
    "LINKED_1",
]
```

This order must match the exact order expected by the Ocean script.

For a batch of candidate solutions, the template writes values sample by sample. If the simulator expects a different layout, the write function should be adapted.

## Simulator Output Interface

The simulator outputs are declared by:

```python
OUTPUT_NAMES = [
    "OUTPUT_1",
    "OUTPUT_2",
    "OUTPUT_3",
]
```

The parser expects a flat numeric result file containing:

```text
OUTPUT_COUNT x BATCH_SIZE
```

values in output-major order.

Example for:

- `OUTPUT_NAMES = ["cond", "tc", "psrr_1k"]`
- `BATCH_SIZE = 2`

Expected result file layout:

```text
cond_sample_1
cond_sample_2
tc_sample_1
tc_sample_2
psrr_1k_sample_1
psrr_1k_sample_2
```

If the Ocean script writes another layout, the parser must be updated accordingly.

## Constraints

Feasibility is handled in:

```python
def evaluate_constraints(output_dict):
```

This function returns:

- `valid_mask`: Boolean feasibility array
- `constraint_info`: optional extra values for logging

Example:

```python
valid_mask = (
    (output_dict["cond"] >= 1.0)
    & (output_dict["gain_margin"] > 0.0)
    & (output_dict["phase_margin"] >= 45.0)
)
```

Only feasible solutions should receive a meaningful FoM. In the default template, infeasible solutions receive `FoM = 0.0`.

## Figure Of Merit

The objective is defined in:

```python
def calculate_fom(output_dict, valid_mask):
```

This function can represent any design target, including:

- gain maximization
- power minimization
- PSRR and phase-margin tradeoff
- temperature-coefficient reduction
- weighted multi-objective scoring

A common pattern is:

1. evaluate feasibility in `evaluate_constraints()`
2. assign nonzero FoM only to feasible solutions
3. keep infeasible solutions at zero or apply a penalty

## Algorithm Layer

The optimization logic is intentionally isolated inside:

```python
class TemplateOptimizationAlgorithm:
```

and especially:

```python
def propose_new_population(self, iteration_index):
```

This allows different metaheuristics to reuse the same Cadence interaction layer.

## Example Algorithm Variants

Within the same framework, different files can represent different optimization strategies:

- `DSA_py_bandgap.py`
  Uses the same simulator, outputs, constraints, and FoM, but applies a DSA-based search rule.
- `TLBO_py_bandgap.py`
  Uses the same simulator, outputs, constraints, and FoM, but applies TLBO teacher and learner phases.
- `Hybrid_TLBO_DSA.py`
  Uses the same simulator, outputs, constraints, and FoM, but combines TLBO and DSA ideas into a hybrid update strategy.

This organization is useful in comparative studies because the algorithm becomes the primary experimental variable.

## Adapting The Template To A New Circuit

When moving to another circuit, the following sections usually need to be updated:

1. `SIMULATOR_COMMAND`
2. `PARAM_FILE`
3. `RESULT_FILE`
4. `FILES_TO_COPY_TO_RUN_FOLDER`
5. `OPTIMIZED_PARAMETERS`
6. `FIXED_PARAMETERS`
7. `LINKED_PARAMETERS`
8. `INPUT_PARAMETER_ORDER`
9. `OUTPUT_NAMES`
10. `evaluate_constraints()`
11. `calculate_fom()`

In most cases, the batch simulation flow and result logging can remain unchanged.

## Logged Results

The template stores optimization history in Excel format, including:

- run index
- iteration index
- start and end time
- elapsed time
- best FoM
- feasibility flag
- optimized parameter values
- fixed parameter values
- linked parameter values
- simulator outputs

This history is helpful for convergence inspection and cross-algorithm comparison.

## Notes For Public Release

Before publishing a project built on this template, it is recommended to:

- remove machine-specific absolute paths
- keep Ocean script names consistent
- document the expected input and output file order
- explain the meaning of each output metric
- describe the constraint set clearly
- describe the FoM in engineering terms
- include at least one small reproducible example

## Summary

This repository is not tied to one specific analog block or one specific optimization method. It is a reusable Cadence/Ocean optimization framework where the simulator pipeline stays fixed and the problem-specific logic is easy to replace.

That makes it suitable for:

- adapting quickly to new circuits
- comparing optimization algorithms fairly
- publishing structured DSA, TLBO, and hybrid optimization studies
