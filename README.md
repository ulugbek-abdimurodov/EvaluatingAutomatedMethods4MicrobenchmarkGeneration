# EvaluatingAutomatedMethods4MicrobenchmarkGeneration
Evaluating Automated Methods for Microbenchmark Generation is a study that analyzes how different automated methodologies (ju2jmh-augmented LLM and standalone LLM) impact the sensitivity and accuracy of regression detection campaigns in the context of Performance Engineering

# Methods Overview
This study explores and evaluates automated methods for generating performance microbenchmarks, focusing on two distinct approaches: ju2jmh, an automation tool that converts unit tests into microbenchmarks, and Large Language Models (LLMs), such as GPT-4, which directly generates microbenchmarks from source code.

### ju2jmh+LLM approach

![ju2jmh+LLM Progress](img/ju2jmh+llm_progress.png)

The following structure details the execution of this methodology as applied to the Apache Ignite project, focusing on the isolation and detection of performance regressions.

### Standalane LLM approach

![Standalone LLM](img/standalone_llm.png)

The standalone LLM approach serves as a critical comparative baseline in this research, representing a "pure" generative methodology for performance test creation.

## Obtained Results

This study answers a Research Question:

> Between ju2jmh-augmented LLM and standalone LLM, which approach is more effective at detecting performance regressions?

You can find the full information in [the Master Thesis document](docs/Master_Thesis.pdf)

## Project Structure

- [analysis](analysis/) - comparison results.
- [data](data/) - benchmark results.
- [img](img/) - images of the structure of both approaches.
- [ju2jmh-augmented_llm](ju2jmh-augmented_llm/) - additional files for the ju2jmh-augmented LLM approach.

## Method workflow

### Configuration setup

To ensure reproducibility of the benchmarking experiments, the following environment configuration was used.

### Required Tools & Versions

| Tool        | Version     | Purpose |
|-------------|------------|--------|
| Java        | 8          | Build and run Apache Ignite |
| Java        | 17         | Run ju2jmh (JMH benchmark generation) |
| Maven       | 3.9.10     | Build Apache Ignite |
| Gradle      | 7.4.2      | Build ju2jmh project |
| Python      | 3.13.1     | Compare and analyze benchmark results |

---

A reference for ju2jmh project: https://github.com/alniniclas/junit-to-jmh


## ju2jmh-augmented LLM


## Analyzed Data

All the previous phases are applied to a real-world, industrial-grade system: Apache Ignite. This system contains historically documented performance regressions, and the goal is to apply the two automated microbenchmark generation methodologies (ju2jmh-augmented LLM and Standalone LLM) to determine if the generated performance tests can successfully isolate and detect the performance degradation and its subsequent fix. The target methods within the system are analyzed across two distinct states by performing a checkout on three precise pairs of commits:

- ***Pre-fix (parent) commit:*** At this commit, the performance regression is still present in the system.
- ***Post-fix (child) commit:*** At this commit, the performance issue has just been resolved