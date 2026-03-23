# EvaluatingAutomatedMethods4MicrobenchmarkGeneration
Evaluating Automated Methods for Microbenchmark Generation is a study that analyzes how different automated methodologies (ju2jmh-augmented LLM and standalone LLM) impact the sensitivity and accuracy of regression detection campaigns in the context of Performance Engineering.

# Methods Overview
This study explores and evaluates automated methods for generating performance microbenchmarks, focusing on two distinct approaches: ju2jmh, an automation tool that converts unit tests into microbenchmarks, and Large Language Models (LLMs), such as GPT-4, which directly generates microbenchmarks from source code.

### ju2jmh+LLM approach

![ju2jmh+LLM Progress](img/ju2jmh+llm_progress.png)

The following structure details the execution of this methodology as applied to the Apache Ignite project, focusing on the isolation and detection of performance regressions.

### Standalone LLM approach

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

## Evaluated Commit Pairs

The experimental evaluation targets specific, real-world performance regressions within the [Apache Ignite](https://github.com/apache/ignite) project. These targets were identified based on the mining study conducted by Campos et al., providing a verified ground truth for our benchmarking methodologies.

For each target, we analyzed a Parent Commit (the version containing the performance bottleneck) and a Fix Commit (the version where the optimization was implemented).

| Pair |  Parent Commit (Buggy) | Fix Commit (Optimized) |
|------|-----------------------|------------------------|
| Pair 1 | 9d82f2ca06fa6069c1976cc75814874256b24f8c | b038730ee56a662f73e02bbec83eb1712180fa82 |
| Pair 2 | 227599fbbd007427d817284d8be64386e18c4e7e | feba95348391938aa7bb32499c647103b6a0a16f |
| Pair 3 | 5224c9de4bea8d905bd53cd1699e5da2267f70c4 | 160dab09587a4c6ebdcfd71368360cfcb153575b |

### Method Changes

The specific Java methods and logic changes analyzed within these commits are documented in [data/method_changes.json](data/method_changes.json). This file serves as the technical reference for which code paths were targeted during the microbenchmark generation phase (using both the Standalone LLM and ju2jmh pipelines).

Step 1: Repository Checkout and Preparation
The evaluation compares the performance of Apache Ignite across two states: the Parent (pre-fix) state containing the regression and the Fix (post-fix) state where the optimization was applied.

1. Clone the Target System
First, clone the official Apache Ignite repository and navigate into the project root:

Bash
git clone https://github.com/apache/ignite.git
cd ignite

2. Navigate to Experimental Versions
To reproduce the results for a specific pair, you must checkout the relevant commit hash. For example, to prepare the environment for Pair 3 (IgniteUtils):

To test the version with the performance issue:

Bash
git checkout //commit (parent/fix)

3. Build the Environment
After each checkout, you must rebuild the core module to ensure the specific logic of that commit is compiled. Ensure you are using Java 8 and Maven 3.9.10.

Bash
# Build the core module and resolve dependencies
mvn clean install -pl modules/core -am -DskipTests -Dmaven.javadoc.skip=true
[!IMPORTANT]
Because microbenchmarks are highly sensitive to the binary state of the system, you must run mvn clean install every time you switch between a Parent and a Fix commit to ensure no artifacts from the previous version remain in the target/ folders.

## ju2jmh-augmented LLM

## Analyzed Data

All the previous phases are applied to a real-world, industrial-grade system: Apache Ignite. This system contains historically documented performance regressions, and the goal is to apply the two automated microbenchmark generation methodologies (ju2jmh-augmented LLM and Standalone LLM) to determine if the generated performance tests can successfully isolate and detect the performance degradation and its subsequent fix. The target methods within the system are analyzed across two distinct states by performing a checkout on three precise pairs of commits:

- ***Pre-fix (parent) commit:*** At this commit, the performance regression is still present in the system.
- ***Post-fix (child) commit:*** At this commit, the performance issue has just been resolved