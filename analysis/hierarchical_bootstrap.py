import json
import numpy as np
from pathlib import Path
from itertools import product
from collections import defaultdict

# Conversion factors to milliseconds (ms/op)
SCORE_UNIT_TO_MS = {
    "ns/op": 1e-6,
    "us/op": 1e-3,
    "ms/op": 1.0,
    "s/op":  1e3,
}

# ---------------- CONFIG ----------------

N_BOOT = 10000
CONF_LEVEL = 0.95
RANDOM_SEED = 42

OUTPUT_STATS_FILE = "hierarchical_bootstrap_results.txt"
OUTPUT_SUMMARY_FILE = "hierarchical_bootstrap_summary.txt"
OUTPUT_DETECTIONS_FILE = "confirmed_detections.txt"

np.random.seed(RANDOM_SEED)

# ---------------- UTILS ----------------

def is_empty_json_file(path: Path) -> bool:
    """Return True if JSON content is empty, [], or invalid"""
    try:
        with open(path) as f:
            content = f.read().strip()
            
        # Check if file is empty
        if not content:
            return True
            
        # Try to parse JSON
        data = json.loads(content)
        
        # Check if it's an empty array
        return isinstance(data, list) and len(data) == 0
        
    except json.JSONDecodeError:
        # Invalid JSON - treat as empty
        return True
    except Exception:
        # Any other error - treat as empty
        return True


def load_jmh_scores(path):
    """Load JMH rawData and normalize all measurements to ms/op"""
    try:
        with open(path) as f:
            content = f.read().strip()
        
        if not content:
            raise ValueError(f"File is empty: {path}")
        
        data = json.loads(content)
        
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"Invalid JMH data structure in {path}")
        
        metric = data[0]["primaryMetric"]
        scores = metric["rawData"]
        unit = metric["scoreUnit"]

        if unit not in SCORE_UNIT_TO_MS:
            raise ValueError(f"Unknown scoreUnit '{unit}' in {path}")

        factor = SCORE_UNIT_TO_MS[unit]

        # Convert everything to ms/op
        return [np.array(fork) * factor for fork in scores]
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")
    except KeyError as e:
        raise ValueError(f"Missing expected field {e} in {path}")
    except Exception as e:
        raise ValueError(f"Error loading {path}: {e}")


# ---------------- STATISTICS ----------------

def hierarchical_bootstrap_ratio(group_a, group_b):
    """
    Perform hierarchical bootstrap to compute ratio of means.
    Returns array of ratios: mean(group_b) / mean(group_a)
    """
    ratios = []

    for _ in range(N_BOOT):
        # Resample forks with replacement
        forks_a = np.random.choice(len(group_a), len(group_a), replace=True)
        forks_b = np.random.choice(len(group_b), len(group_b), replace=True)

        sample_a = []
        sample_b = []

        # For each resampled fork, resample iterations
        for i in forks_a:
            iters = group_a[i]
            sample_a.extend(np.random.choice(iters, len(iters), replace=True))

        for i in forks_b:
            iters = group_b[i]
            sample_b.extend(np.random.choice(iters, len(iters), replace=True))

        mean_a = np.mean(sample_a)
        mean_b = np.mean(sample_b)
        
        # Compute ratio (avoid division by zero)
        if mean_b > 0:
            ratios.append(mean_a / mean_b)
        else:
            ratios.append(np.nan)

    return np.array([r for r in ratios if not np.isnan(r)])


def vargha_delaney_a12(x, y):
    """Compute Vargha-Delaney A12 effect size"""
    wins = sum(1 for xi, yi in product(x, y) if xi > yi)
    ties = sum(1 for xi, yi in product(x, y) if xi == yi)
    return (wins + 0.5 * ties) / (len(x) * len(y))


# ---------------- DISCOVERY ----------------

def discover_benchmark_pairs(base_dir: Path):
    """
    Discover all benchmark pairs (before_fix vs after_fix) for both
    ju2jmh and LLM-generated benchmarks across all pairs and modules.
    
    Returns a nested dictionary:
    {
        'pair_1': {
            'core': {
                'ju2jmh': {
                    'BenchmarkClass': {
                        'benchmark_name.json': {
                            'before': Path,
                            'after': Path
                        }
                    }
                },
                'llm': { ... }
            },
            'hadoop': { ... }
        },
        'pair_2': { ... }
    }
    """
    pairs = defaultdict(lambda: defaultdict(lambda: {'ju2jmh': defaultdict(dict), 'llm': defaultdict(dict)}))
    
    # Results root directory.
    # Historical name: ignite_results/
    # Current repo layout: data/
    results_dir = base_dir / "ignite_results"
    if not results_dir.exists():
        results_dir = base_dir / "data"

    if not results_dir.exists():
        raise ValueError(
            f"Expected results directory 'data' (or legacy 'ignite_results') in {base_dir}"
        )
    
    # Process each pair directory
    for pair_dir in sorted(results_dir.iterdir()):
        if not pair_dir.is_dir() or not pair_dir.name.startswith('pair_'):
            continue
        
        pair_name = pair_dir.name
        
        # Find before and after directories
        before_dirs = list(pair_dir.glob("before_*"))
        after_dirs = list(pair_dir.glob("after_*"))
        
        if len(before_dirs) != 1 or len(after_dirs) != 1:
            print(f"Warning: {pair_name} doesn't have exactly one before and one after directory")
            continue
        
        before_dir = before_dirs[0]
        after_dir = after_dirs[0]
        
        # Process each module (core, hadoop, etc.)
        for module in ['core', 'hadoop']:
            before_module = before_dir / module
            after_module = after_dir / module
            
            if not before_module.exists() and not after_module.exists():
                continue
            
            # Process ju2jmh benchmarks
            before_ju2jmh = before_module / 'ju2jmh' if before_module.exists() else None
            after_ju2jmh = after_module / 'ju2jmh' if after_module.exists() else None
            
            if before_ju2jmh and before_ju2jmh.exists() and after_ju2jmh and after_ju2jmh.exists():
                # Find all benchmark classes
                for before_class_dir in before_ju2jmh.iterdir():
                    if not before_class_dir.is_dir():
                        continue
                    
                    class_name = before_class_dir.name
                    after_class_dir = after_ju2jmh / class_name
                    
                    if not after_class_dir.exists():
                        continue
                    
                    # Match benchmark files
                    for before_file in before_class_dir.glob("*.json"):
                        after_file = after_class_dir / before_file.name
                        
                        if after_file.exists():
                            pairs[pair_name][module]['ju2jmh'][class_name][before_file.name] = {
                                'before': before_file,
                                'after': after_file
                            }
            
            # Process LLM benchmarks
            before_llm = before_module / 'llm' if before_module.exists() else None
            after_llm = after_module / 'llm' if after_module.exists() else None
            
            if before_llm and before_llm.exists() and after_llm and after_llm.exists():
                # Find all benchmark classes
                for before_class_dir in before_llm.iterdir():
                    if not before_class_dir.is_dir():
                        continue
                    
                    class_name = before_class_dir.name
                    after_class_dir = after_llm / class_name
                    
                    if not after_class_dir.exists():
                        continue
                    
                    # Match benchmark files
                    for before_file in before_class_dir.glob("*.json"):
                        after_file = after_class_dir / before_file.name
                        
                        if after_file.exists():
                            pairs[pair_name][module]['llm'][class_name][before_file.name] = {
                                'before': before_file,
                                'after': after_file
                            }
    
    return dict(pairs)


# ---------------- MAIN ----------------

def main():
    base_dir = Path(".")
    
    print("=" * 80)
    print("HIERARCHICAL BOOTSTRAP ANALYSIS")
    print("Comparing Before-Fix vs After-Fix Benchmarks")
    print("=" * 80)
    print()
    
    # Discover all benchmark pairs
    print("Discovering benchmark pairs...")
    pairs = discover_benchmark_pairs(base_dir)
    
    pair_names = sorted(pairs.keys())
    total_pairs = len(pair_names)
    
    if total_pairs == 0:
        print("ERROR: No pairs found!")
        print("Expected directory structure:")
        print("  data/  (or legacy: ignite_results/)")
        print("    pair_1/")
        print("      before_<hash>/")
        print("        core/ju2jmh/")
        print("        core/llm/")
        print("      after_<hash>/")
        print("        core/ju2jmh/")
        print("        core/llm/")
        return
    
    print(f"Found {total_pairs} pairs")
    print()
    
    stats_lines = []
    summary_lines = []
    detection_lines = []

    overall_detected_ju2jmh = 0
    overall_regressions_ju2jmh = 0
    overall_improvements_ju2jmh = 0
    overall_total_ju2jmh = 0
    
    overall_detected_llm = 0
    overall_regressions_llm = 0
    overall_improvements_llm = 0
    overall_total_llm = 0

    for idx, pair_name in enumerate(pair_names, start=1):
        print(f"[{idx}/{total_pairs}] Processing {pair_name}")

        stats_lines.append(f"Pair: {pair_name}")
        stats_lines.append("=" * 80)
        summary_lines.append(f"Pair: {pair_name}")
        detection_lines.append(f"Pair: {pair_name}")

        pair_data = pairs[pair_name]
        
        pair_detected_ju2jmh = 0
        pair_regressions_ju2jmh = 0
        pair_improvements_ju2jmh = 0
        pair_total_ju2jmh = 0
        
        pair_detected_llm = 0
        pair_regressions_llm = 0
        pair_improvements_llm = 0
        pair_total_llm = 0
        
        # Process each module
        for module_name in sorted(pair_data.keys()):
            module_data = pair_data[module_name]
            
            stats_lines.append(f"\nModule: {module_name}")
            stats_lines.append("-" * 80)
            summary_lines.append(f"  Module: {module_name}")
            
            # Process JU2JMH benchmarks
            ju2jmh_data = module_data['ju2jmh']
            if ju2jmh_data:
                stats_lines.append("\n--- JU2JMH BENCHMARKS ---\n")
                summary_lines.append("    JU2JMH Benchmarks:")
                
                for class_name in sorted(ju2jmh_data.keys()):
                    benchmarks = ju2jmh_data[class_name]
                    
                    stats_lines.append(f"  Class: {class_name}")
                    
                    for bench_name, bench_paths in sorted(benchmarks.items()):
                        before_path = bench_paths['before']
                        after_path = bench_paths['after']
                        
                        # Skip empty JSONs
                        before_empty = is_empty_json_file(before_path)
                        after_empty = is_empty_json_file(after_path)
                        
                        if before_empty or after_empty:
                            reason = []
                            if before_empty:
                                reason.append("before-fix file empty/invalid")
                            if after_empty:
                                reason.append("after-fix file empty/invalid")
                            stats_lines.append(f"    {bench_name}: SKIPPED ({', '.join(reason)})")
                            continue
                        
                        before_fix = load_jmh_scores(before_path)
                        after_fix = load_jmh_scores(after_path)
                        
                        # Compute ratio of means via hierarchical bootstrap
                        # Ratio = before / after (we expect before > after if regression was fixed)
                        ratios = hierarchical_bootstrap_ratio(before_fix, after_fix)
                        
                        # Point estimate: ratio of sample means
                        flat_before = np.concatenate(before_fix)
                        flat_after = np.concatenate(after_fix)
                        point_estimate = np.mean(flat_before) / np.mean(flat_after)
                        
                        # Confidence interval for ratio
                        alpha = 1 - CONF_LEVEL
                        lo, hi = np.percentile(ratios, [alpha / 2 * 100, (1 - alpha / 2) * 100])
                        
                        # Statistical significance: CI excludes 1
                        is_significant = (lo > 1.0 or hi < 1.0)
                        
                        # Classification
                        # If before > after (ratio > 1), the fix made it faster (regression detected)
                        # If before < after (ratio < 1), the fix made it slower (unexpected!)
                        is_detection = (lo > 1.0)  # Before was slower (regression detected)
                        is_unexpected = (hi < 1.0)  # Before was faster (unexpected!)
                        
                        # Convert to percentage change
                        pct_change = (point_estimate - 1.0) * 100
                        pct_lo = (lo - 1.0) * 100
                        pct_hi = (hi - 1.0) * 100
                        margin = max(abs(pct_change - pct_lo), abs(pct_hi - pct_change))
                        
                        # Additional statistics
                        p_gt_1 = np.mean(ratios > 1.0)
                        a12 = vargha_delaney_a12(flat_before, flat_after)
                        
                        # Update counters
                        pair_total_ju2jmh += 1
                        overall_total_ju2jmh += 1
                        
                        if is_significant:
                            pair_detected_ju2jmh += 1
                            overall_detected_ju2jmh += 1
                            
                            if is_detection:
                                pair_regressions_ju2jmh += 1
                                overall_regressions_ju2jmh += 1
                            elif is_unexpected:
                                pair_improvements_ju2jmh += 1
                                overall_improvements_ju2jmh += 1
                        
                        # Format output
                        stats_lines.append(f"\n    Benchmark: {bench_name}")
                        stats_lines.append(f"      Point estimate (ratio): {point_estimate:.6f}")
                        
                        if pct_change >= 0:
                            stats_lines.append(
                                f"      Performance change: {abs(pct_change):.2f}% ± {margin:.2f}% "
                                f"(before-fix was SLOWER)"
                            )
                        else:
                            stats_lines.append(
                                f"      Performance change: {abs(pct_change):.2f}% ± {margin:.2f}% "
                                f"(before-fix was FASTER)"
                            )
                        
                        stats_lines.append(
                            f"      {int(CONF_LEVEL*100)}% CI for ratio: [{lo:.6f}, {hi:.6f}]"
                        )
                        stats_lines.append(
                            f"      {int(CONF_LEVEL*100)}% CI (percentage): [{pct_lo:.2f}%, {pct_hi:.2f}%]"
                        )
                        stats_lines.append(f"      P(before > after): {p_gt_1:.4f}")
                        stats_lines.append(
                            f"      Vargha-Delaney A12 (Before > After): {a12:.4f}"
                        )
                        
                        # Significance classification
                        if is_detection:
                            stats_lines.append("      >>> REGRESSION DETECTED (before was significantly slower)")
                            detection_lines.append(
                                f"    [JU2JMH] {module_name}/{class_name}/{bench_name}: "
                                f"DETECTED ({abs(pct_change):.2f}% ± {margin:.2f}% slower before fix)"
                            )
                        elif is_unexpected:
                            stats_lines.append("      >>> UNEXPECTED RESULT (before was significantly faster)")
                        else:
                            stats_lines.append("      >>> NOT DETECTED (CI includes 1)")
                        
                        # Summary line
                        sig_marker = "✓" if is_significant else "✗"
                        summary_lines.append(
                            f"      {sig_marker} {class_name}/{bench_name}: {pct_change:+.2f}% ± {margin:.2f}% "
                            f"[CI: {pct_lo:.2f}%, {pct_hi:.2f}%]"
                        )
            
            # Process LLM benchmarks
            llm_data = module_data['llm']
            if llm_data:
                stats_lines.append("\n--- LLM-GENERATED BENCHMARKS ---\n")
                summary_lines.append("    LLM-Generated Benchmarks:")
                
                for class_name in sorted(llm_data.keys()):
                    benchmarks = llm_data[class_name]
                    
                    stats_lines.append(f"  Class: {class_name}")
                    
                    for bench_name, bench_paths in sorted(benchmarks.items()):
                        before_path = bench_paths['before']
                        after_path = bench_paths['after']
                        
                        # Skip empty JSONs
                        before_empty = is_empty_json_file(before_path)
                        after_empty = is_empty_json_file(after_path)
                        
                        if before_empty or after_empty:
                            reason = []
                            if before_empty:
                                reason.append("before-fix file empty/invalid")
                            if after_empty:
                                reason.append("after-fix file empty/invalid")
                            stats_lines.append(f"    {bench_name}: SKIPPED ({', '.join(reason)})")
                            continue
                        
                        before_fix = load_jmh_scores(before_path)
                        after_fix = load_jmh_scores(after_path)
                        
                        # Compute ratio of means via hierarchical bootstrap
                        ratios = hierarchical_bootstrap_ratio(before_fix, after_fix)
                        
                        # Point estimate: ratio of sample means
                        flat_before = np.concatenate(before_fix)
                        flat_after = np.concatenate(after_fix)
                        point_estimate = np.mean(flat_before) / np.mean(flat_after)
                        
                        # Confidence interval for ratio
                        alpha = 1 - CONF_LEVEL
                        lo, hi = np.percentile(ratios, [alpha / 2 * 100, (1 - alpha / 2) * 100])
                        
                        # Statistical significance: CI excludes 1
                        is_significant = (lo > 1.0 or hi < 1.0)
                        
                        # Classification
                        is_detection = (lo > 1.0)  # Before was slower
                        is_unexpected = (hi < 1.0)  # Before was faster
                        
                        # Convert to percentage change
                        pct_change = (point_estimate - 1.0) * 100
                        pct_lo = (lo - 1.0) * 100
                        pct_hi = (hi - 1.0) * 100
                        margin = max(abs(pct_change - pct_lo), abs(pct_hi - pct_change))
                        
                        # Additional statistics
                        p_gt_1 = np.mean(ratios > 1.0)
                        a12 = vargha_delaney_a12(flat_before, flat_after)
                        
                        # Update counters
                        pair_total_llm += 1
                        overall_total_llm += 1
                        
                        if is_significant:
                            pair_detected_llm += 1
                            overall_detected_llm += 1
                            
                            if is_detection:
                                pair_regressions_llm += 1
                                overall_regressions_llm += 1
                            elif is_unexpected:
                                pair_improvements_llm += 1
                                overall_improvements_llm += 1
                        
                        # Format output
                        stats_lines.append(f"\n    Benchmark: {bench_name}")
                        stats_lines.append(f"      Point estimate (ratio): {point_estimate:.6f}")
                        
                        if pct_change >= 0:
                            stats_lines.append(
                                f"      Performance change: {abs(pct_change):.2f}% ± {margin:.2f}% "
                                f"(before-fix was SLOWER)"
                            )
                        else:
                            stats_lines.append(
                                f"      Performance change: {abs(pct_change):.2f}% ± {margin:.2f}% "
                                f"(before-fix was FASTER)"
                            )
                        
                        stats_lines.append(
                            f"      {int(CONF_LEVEL*100)}% CI for ratio: [{lo:.6f}, {hi:.6f}]"
                        )
                        stats_lines.append(
                            f"      {int(CONF_LEVEL*100)}% CI (percentage): [{pct_lo:.2f}%, {pct_hi:.2f}%]"
                        )
                        stats_lines.append(f"      P(before > after): {p_gt_1:.4f}")
                        stats_lines.append(
                            f"      Vargha-Delaney A12 (Before > After): {a12:.4f}"
                        )
                        
                        # Significance classification
                        if is_detection:
                            stats_lines.append("      >>> REGRESSION DETECTED (before was significantly slower)")
                            detection_lines.append(
                                f"    [LLM] {module_name}/{class_name}/{bench_name}: "
                                f"DETECTED ({abs(pct_change):.2f}% ± {margin:.2f}% slower before fix)"
                            )
                        elif is_unexpected:
                            stats_lines.append("      >>> UNEXPECTED RESULT (before was significantly faster)")
                        else:
                            stats_lines.append("      >>> NOT DETECTED (CI includes 1)")
                        
                        # Summary line
                        sig_marker = "✓" if is_significant else "✗"
                        summary_lines.append(
                            f"      {sig_marker} {class_name}/{bench_name}: {pct_change:+.2f}% ± {margin:.2f}% "
                            f"[CI: {pct_lo:.2f}%, {pct_hi:.2f}%]"
                        )
        
        # Pair summary
        stats_lines.append(f"\n{'='*80}")
        stats_lines.append(f"Pair {pair_name} Summary:")
        stats_lines.append(f"  JU2JMH Benchmarks:")
        stats_lines.append(f"    Total: {pair_total_ju2jmh}")
        if pair_total_ju2jmh > 0:
            stats_lines.append(f"    Significant differences: {pair_detected_ju2jmh} ({100*pair_detected_ju2jmh/pair_total_ju2jmh:.1f}%)")
        else:
            stats_lines.append(f"    Significant differences: 0")
        stats_lines.append(f"      - Regressions detected: {pair_regressions_ju2jmh}")
        stats_lines.append(f"      - Unexpected results: {pair_improvements_ju2jmh}")
        stats_lines.append(f"  LLM-Generated Benchmarks:")
        stats_lines.append(f"    Total: {pair_total_llm}")
        if pair_total_llm > 0:
            stats_lines.append(f"    Significant differences: {pair_detected_llm} ({100*pair_detected_llm/pair_total_llm:.1f}%)")
        else:
            stats_lines.append(f"    Significant differences: 0")
        stats_lines.append(f"      - Regressions detected: {pair_regressions_llm}")
        stats_lines.append(f"      - Unexpected results: {pair_improvements_llm}")
        stats_lines.append("")

        summary_lines.append(
            f"  JU2JMH: {pair_detected_ju2jmh}/{pair_total_ju2jmh} significant " +
            (f"({100*pair_detected_ju2jmh/pair_total_ju2jmh:.1f}%) | " if pair_total_ju2jmh > 0 else "| ") +
            f"Detected: {pair_regressions_ju2jmh} | Unexpected: {pair_improvements_ju2jmh}"
        )
        summary_lines.append(
            f"  LLM: {pair_detected_llm}/{pair_total_llm} significant " +
            (f"({100*pair_detected_llm/pair_total_llm:.1f}%) | " if pair_total_llm > 0 else "| ") +
            f"Detected: {pair_regressions_llm} | Unexpected: {pair_improvements_llm}"
        )
        summary_lines.append("")

        if pair_regressions_ju2jmh == 0 and pair_regressions_llm == 0:
            detection_lines.append("  No regressions detected")
        detection_lines.append("")

    # Overall summary
    summary_lines.append("=" * 80)
    summary_lines.append("OVERALL SUMMARY")
    summary_lines.append("=" * 80)
    summary_lines.append(f"Total pairs analyzed: {total_pairs}")
    summary_lines.append("")
    summary_lines.append("JU2JMH BENCHMARKS:")
    summary_lines.append(f"  Total benchmarks: {overall_total_ju2jmh}")
    if overall_total_ju2jmh > 0:
        summary_lines.append(
            f"  Significant differences: {overall_detected_ju2jmh} ({100*overall_detected_ju2jmh/overall_total_ju2jmh:.1f}%)"
        )
    else:
        summary_lines.append(f"  Significant differences: 0")
    summary_lines.append(f"    - Regressions detected: {overall_regressions_ju2jmh}")
    summary_lines.append(f"    - Unexpected results: {overall_improvements_ju2jmh}")
    summary_lines.append("")
    summary_lines.append("LLM-GENERATED BENCHMARKS:")
    summary_lines.append(f"  Total benchmarks: {overall_total_llm}")
    if overall_total_llm > 0:
        summary_lines.append(
            f"  Significant differences: {overall_detected_llm} ({100*overall_detected_llm/overall_total_llm:.1f}%)"
        )
    else:
        summary_lines.append(f"  Significant differences: 0")
    summary_lines.append(f"    - Regressions detected: {overall_regressions_llm}")
    summary_lines.append(f"    - Unexpected results: {overall_improvements_llm}")
    summary_lines.append("")
    summary_lines.append("COMPARISON:")
    if overall_total_ju2jmh > 0 and overall_total_llm > 0:
        ju2jmh_detection_rate = 100 * overall_regressions_ju2jmh / overall_total_ju2jmh
        llm_detection_rate = 100 * overall_regressions_llm / overall_total_llm
        summary_lines.append(f"  JU2JMH detection rate: {ju2jmh_detection_rate:.1f}%")
        summary_lines.append(f"  LLM detection rate: {llm_detection_rate:.1f}%")

    # Write output files
    with open(OUTPUT_STATS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(stats_lines))

    with open(OUTPUT_SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    with open(OUTPUT_DETECTIONS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(detection_lines))

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Detailed statistics: {OUTPUT_STATS_FILE}")
    print(f"Quick summary: {OUTPUT_SUMMARY_FILE}")
    print(f"Confirmed detections: {OUTPUT_DETECTIONS_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    main()