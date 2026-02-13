#!/usr/bin/env python3
"""
OpenFOAM Allocator Performance Analysis
Reads CSV data with allocator benchmarks and creates visualizations
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import argparse
from matplotlib.colors import LogNorm

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)

from matplotlib.colors import LogNorm

def plot_allocator_overview_heatmap_new(df, output_dir, baseline):
    pivot_data = df.pivot_table(
        values='total_mean',
        index='command',
        columns='allocator',
        aggfunc='mean'
    )

    if baseline not in pivot_data.columns:
        raise ValueError(f"Baseline '{baseline}' not found")

    # time / baseline_time
    pivot_relative = pivot_data.div(pivot_data[baseline], axis=0)

    # True min/max (no clipping!)
    vmin = pivot_relative.min().min()
    vmax = pivot_relative.max().max()

    fig, ax = plt.subplots(
        figsize=(12, max(8, len(pivot_relative) * 0.3))
    )

    sns.heatmap(
        pivot_relative,
        cmap="RdYlGn_r",              # green = faster
        norm=LogNorm(vmin=vmin, vmax=vmax),
        cbar_kws={
            "label": "Execution Time / GNU baseline (1.0 = same)"
        },
        ax=ax
    )

    ax.set_title(
        "Allocator Performance Heatmap\n"
        "(Normalized to GNU baseline — greener = faster)",
        fontsize=14,
        fontweight="bold",
        pad=20
    )

    ax.set_xlabel("Allocator")
    ax.set_ylabel("Command")

    plt.tight_layout()
    plt.savefig(output_dir / "allocator_heatmap_new.png", dpi=150)
    plt.close()


def load_and_clean_data(csv_path):
    """Load CSV and filter out failures and timeouts"""
    df = pd.read_csv(csv_path)
    
    # Filter out failures (-1) and timeouts (-60)
    numeric_cols = ['total_mean', 'total_min', 'total_max', 
                    'user_mean', 'user_min', 'user_max',
                    'system_mean', 'system_min', 'system_max']
    
    # Create mask for valid data (no -1 or -60 values)
    commands = []
    for index, row in df.iterrows():
        if (-60 in row.values) or (-1 in row.values):
            continue
        commands.append(row['command'])
    filtered_df = df[df['command'].isin(commands)]
    
    print(f"Loaded {len(df)} rows, {len(filtered_df)} valid rows after filtering")
    print(f"Filtered out {len(df) - len(filtered_df)} failed/timeout rows")
    print(f"\nCommands: {filtered_df['command'].nunique()}")
    print(f"Allocators: {filtered_df['allocator'].nunique()}")
    
    return filtered_df

def plot_command_comparison(df, command, output_dir):
    """Create a detailed plot for a single command across allocators"""
    cmd_data = df[df['command'] == command].copy()
    
    if len(cmd_data) == 0:
        return
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f'Performance Comparison: {command}', fontsize=14, fontweight='bold')
    
    allocators = cmd_data['allocator'].values
    x_pos = np.arange(len(allocators))
    
    # Total time
    axes[0].bar(x_pos, cmd_data['total_mean'], alpha=0.7, color='steelblue')
    axes[0].errorbar(x_pos, cmd_data['total_mean'], 
                     yerr=[cmd_data['total_mean'] - cmd_data['total_min'],
                           cmd_data['total_max'] - cmd_data['total_mean']],
                     fmt='none', color='black', capsize=5, alpha=0.5)
    axes[0].set_xlabel('Allocator')
    axes[0].set_ylabel('Time (s)')
    axes[0].set_title('Total Time')
    axes[0].set_xticks(x_pos)
    axes[0].set_xticklabels(allocators, rotation=45, ha='right')
    axes[0].grid(axis='y', alpha=0.3)
    
    # User time
    axes[1].bar(x_pos, cmd_data['user_mean'], alpha=0.7, color='forestgreen')
    axes[1].errorbar(x_pos, cmd_data['user_mean'], 
                     yerr=[cmd_data['user_mean'] - cmd_data['user_min'],
                           cmd_data['user_max'] - cmd_data['user_mean']],
                     fmt='none', color='black', capsize=5, alpha=0.5)
    axes[1].set_xlabel('Allocator')
    axes[1].set_ylabel('Time (s)')
    axes[1].set_title('User Time')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(allocators, rotation=45, ha='right')
    axes[1].grid(axis='y', alpha=0.3)
    
    # System time
    axes[2].bar(x_pos, cmd_data['system_mean'], alpha=0.7, color='coral')
    axes[2].errorbar(x_pos, cmd_data['system_mean'], 
                     yerr=[cmd_data['system_mean'] - cmd_data['system_min'],
                           cmd_data['system_max'] - cmd_data['system_mean']],
                     fmt='none', color='black', capsize=5, alpha=0.5)
    axes[2].set_xlabel('Allocator')
    axes[2].set_ylabel('Time (s)')
    axes[2].set_title('System Time')
    axes[2].set_xticks(x_pos)
    axes[2].set_xticklabels(allocators, rotation=45, ha='right')
    axes[2].grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    # Save with sanitized filename
    safe_cmd_name = command.replace('/', '_').replace(' ', '_')
    output_path = output_dir / f'{safe_cmd_name}.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")

def plot_allocator_overview_heatmap(df, output_dir, baseline):
    """Create a heatmap showing allocator performance relative to a baseline.
    
    Values are execution_time / baseline_time:
      - 1.0  = same as baseline
      - <1.0 = faster than baseline
      - >1.0 = slower than baseline
    """

    # Pivot data: command x allocator
    pivot_data = df.pivot_table(
        values='total_mean',
        index='command',
        columns='allocator',
        aggfunc='mean'
    )

    if baseline not in pivot_data.columns:
        raise ValueError(f"Baseline allocator '{baseline}' not found in data")

    # Normalize by baseline (time / baseline_time)
    pivot_relative = pivot_data.div(pivot_data[baseline], axis=0)

    # Determine color scale limits (symmetric-ish around 1.0)
    vmin = pivot_relative.min().min()
    vmax = pivot_relative.max().max()

    # Optional: clamp extremes to keep heatmap readable
    vmin = max(vmin, 0.5)
    vmax = min(vmax, 1.5)

    fig, ax = plt.subplots(
        figsize=(12, max(8, len(pivot_relative) * 0.3))
    )

    sns.heatmap(
        pivot_relative,
        cmap='RdYlGn_r',     # green = faster (lower)
        center=1.0,          # baseline is neutral
        vmin=vmin,
        vmax=vmax,
        cbar_kws={
            'label': 'Execution Time / Baseline (1.0 = baseline)'
        },
        ax=ax
    )

    ax.set_title(
        f'Allocator Performance Heatmap\n(Normalized to {baseline} baseline)',
        fontsize=14,
        fontweight='bold',
        pad=20
    )
    ax.set_xlabel('Allocator', fontsize=12)
    ax.set_ylabel('Command', fontsize=12)

    plt.tight_layout()
    output_path = output_dir / 'allocator_heatmap.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    
    print(f"Saved: {output_path}")

def plot_allocator_summary(df, output_dir):
    """Create summary statistics for each allocator across all commands"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # Average performance across all commands
    allocator_means = df.groupby('allocator')['total_mean'].mean().sort_values()
    
    axes[0, 0].barh(range(len(allocator_means)), allocator_means.values, color='steelblue', alpha=0.7)
    axes[0, 0].set_yticks(range(len(allocator_means)))
    axes[0, 0].set_yticklabels(allocator_means.index)
    axes[0, 0].set_xlabel('Average Total Time (s)')
    axes[0, 0].set_title('Average Performance Across All Commands', fontweight='bold')
    axes[0, 0].grid(axis='x', alpha=0.3)
    
    # Win count (how many times each allocator was fastest)
    fastest_allocator = df.groupby('command').apply(
        lambda x: x.loc[x['total_mean'].idxmin(), 'allocator']
    )
    win_counts = fastest_allocator.value_counts()
    
    axes[0, 1].bar(range(len(win_counts)), win_counts.values, color='forestgreen', alpha=0.7)
    axes[0, 1].set_xticks(range(len(win_counts)))
    axes[0, 1].set_xticklabels(win_counts.index, rotation=45, ha='right')
    axes[0, 1].set_ylabel('Number of Commands')
    axes[0, 1].set_title('Win Count (Times Fastest)', fontweight='bold')
    axes[0, 1].grid(axis='y', alpha=0.3)
    
    # Box plot of performance distribution
    allocators = df['allocator'].unique()
    data_for_box = [df[df['allocator'] == alloc]['total_mean'].values for alloc in allocators]
    
    bp = axes[1, 0].boxplot(data_for_box, labels=allocators, patch_artist=True)
    for patch in bp['boxes']:
        patch.set_facecolor('lightblue')
        patch.set_alpha(0.7)
    axes[1, 0].set_xticklabels(allocators, rotation=45, ha='right')
    axes[1, 0].set_ylabel('Total Time (s)')
    axes[1, 0].set_title('Performance Distribution', fontweight='bold')
    axes[1, 0].grid(axis='y', alpha=0.3)
    
    # Coefficient of variation (consistency metric)
    cv_data = df.groupby('allocator').apply(
        lambda x: x['total_mean'].std() / x['total_mean'].mean()
    ).sort_values()
    
    axes[1, 1].barh(range(len(cv_data)), cv_data.values, color='coral', alpha=0.7)
    axes[1, 1].set_yticks(range(len(cv_data)))
    axes[1, 1].set_yticklabels(cv_data.index)
    axes[1, 1].set_xlabel('Coefficient of Variation (lower = more consistent)')
    axes[1, 1].set_title('Performance Consistency', fontweight='bold')
    axes[1, 1].grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    output_path = output_dir / 'allocator_summary.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")

def plot_top_commands_comparison(df, output_dir, n_commands=10):
    """Plot comparison for the N commands with highest average runtime"""
    # Find commands with highest average runtime
    top_commands = df.groupby('command')['total_mean'].mean().nlargest(n_commands).index
    
    df_top = df[df['command'].isin(top_commands)]
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Create grouped bar chart
    allocators = df_top['allocator'].unique()
    n_allocators = len(allocators)
    x = np.arange(len(top_commands))
    width = 0.8 / n_allocators
    
    colors = plt.cm.tab10(np.linspace(0, 1, n_allocators))
    
    for i, allocator in enumerate(allocators):
        data = []
        for cmd in top_commands:
            cmd_data = df_top[(df_top['command'] == cmd) & (df_top['allocator'] == allocator)]
            if len(cmd_data) > 0:
                data.append(cmd_data['total_mean'].values[0])
            else:
                data.append(0)
        
        ax.bar(x + i * width, data, width, label=allocator, color=colors[i], alpha=0.8)
    
    ax.set_xlabel('Command', fontsize=12)
    ax.set_ylabel('Total Time (s)', fontsize=12)
    ax.set_title(f'Top {n_commands} Longest Running Commands', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width * (n_allocators - 1) / 2)
    ax.set_xticklabels(top_commands, rotation=45, ha='right')
    ax.legend(title='Allocator', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    output_path = output_dir / 'top_commands_comparison.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Analyze OpenFOAM allocator performance data')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--output-dir', '-o', default='plots', help='Output directory for plots')
    parser.add_argument('--skip-individual', action='store_true', 
                        help='Skip individual command plots')
    parser.add_argument('--top-n', type=int, default=10,
                        help='Number of top commands to show in comparison plot')
    parser.add_argument('--baseline', '-b', type=str, default=None,
                        help='Baseline allocator for normalization (default: normalize to slowest per command)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load data
    print("Loading data...")
    df = load_and_clean_data(args.csv_file)
    
    if len(df) == 0:
        print("No valid data to plot!")
        return
    
    # Validate baseline allocator if specified
    if args.baseline:
        available_allocators = df['allocator'].unique()
        if args.baseline not in available_allocators:
            print(f"\nWarning: Baseline allocator '{args.baseline}' not found in data!")
            print(f"Available allocators: {', '.join(available_allocators)}")
            print("Continuing with default normalization (slowest per command)...")
            args.baseline = None
        else:
            print(f"\nUsing '{args.baseline}' as baseline allocator")
    
    # Create overview plots
    print("\nCreating overview plots...")
    plot_allocator_summary(df, output_dir)
    plot_allocator_overview_heatmap(df, output_dir, baseline=args.baseline)
    plot_allocator_overview_heatmap_new(df, output_dir, baseline=args.baseline)
    plot_top_commands_comparison(df, output_dir, n_commands=args.top_n)
    
    # Create individual command plots
    if not args.skip_individual:
        print("\nCreating individual command plots...")
        commands = df['command'].unique()
        for i, command in enumerate(commands, 1):
            print(f"  [{i}/{len(commands)}] {command}")
            plot_command_comparison(df, command, output_dir)
    
    print(f"\n✓ All plots saved to: {output_dir.absolute()}")
    print(f"\nKey files:")
    print(f"  - allocator_summary.png: Overall performance comparison")
    print(f"  - allocator_heatmap.png: Performance across all commands")
    print(f"  - top_commands_comparison.png: Detailed view of longest-running commands")

if __name__ == '__main__':
    main()
