import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import json

def read_ndjson(filepath):
    """Read NDJSON file and return list of parsed objects"""
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data

def filter_data_by_time(data, skip_seconds=0.1, start_time=None, end_time=None):
    """Filter data by time range"""
    if not data or (skip_seconds <= 0 and start_time is None and end_time is None):
        return data
    
    # Get the first timestamp
    t_start = data[0]['t_us']
    
    # First apply skip_seconds filter
    if skip_seconds > 0:
        skip_us = skip_seconds * 1e6  # Convert to microseconds
        filtered_data = [d for d in data if (d['t_us'] - t_start) >= skip_us]
        print(f"Skipped first {skip_seconds}s of data ({len(data) - len(filtered_data)} points)")
    else:
        filtered_data = data
    
    # Then apply time boundary filters
    if start_time is not None or end_time is not None:
        original_count = len(filtered_data)
        
        if start_time is not None:
            start_us = t_start + start_time * 1e6
            filtered_data = [d for d in filtered_data if d['t_us'] >= start_us]
        
        if end_time is not None:
            end_us = t_start + end_time * 1e6
            filtered_data = [d for d in filtered_data if d['t_us'] <= end_us]
        
        time_range_str = f"{start_time or 'start'} to {end_time or 'end'} seconds"
        print(f"Filtered to time range {time_range_str} ({len(filtered_data)} of {original_count} points)")
    
    return filtered_data

def plot_data(data, output_path=None, skip_seconds=0.1, actuator_index=None, start_time=None, end_time=None):
    """Plot all data fields from the NDJSON"""
    if not data:
        print("No data to plot")
        return
    
    # Filter data by time
    data = filter_data_by_time(data, skip_seconds, start_time, end_time)
    
    if not data:
        print("No data remaining after filtering")
        return
    
    # Extract timestamps and convert to seconds relative to first timestamp
    timestamps = [d['t_us'] for d in data]
    t_start = timestamps[0]
    times = [(t - t_start) / 1e6 for t in timestamps]  # Convert to seconds
    
    # Extract data arrays
    joint_angles = np.array([d['joint_angles'] for d in data if d['joint_angles'] is not None])
    joint_vels = np.array([d['joint_vels'] for d in data if d['joint_vels'] is not None])
    projected_g = np.array([d['projected_g'] for d in data if d['projected_g'] is not None])
    accel = np.array([d['accel'] for d in data if d['accel'] is not None])
    command = np.array([d['command'] for d in data if d['command'] is not None])
    output = np.array([d['output'] for d in data if d['output'] is not None])
    
    # Create subplots
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    
    # Update title based on filtering options
    title_parts = []
    if skip_seconds > 0:
        title_parts.append(f"skipped first {skip_seconds}s")
    if start_time is not None or end_time is not None:
        time_range = f"{start_time or 'start'}-{end_time or 'end'}s"
        title_parts.append(f"time range {time_range}")
    
    title_suffix = f" ({', '.join(title_parts)})" if title_parts else ""
    
    if actuator_index is not None:
        fig.suptitle(f'Robot Data for Actuator {actuator_index}{title_suffix}', fontsize=16)
    else:
        fig.suptitle(f'Robot Data Over Time{title_suffix}', fontsize=16)
    
    # ... rest of the plotting code remains the same ...
    # Plot joint angles
    if len(joint_angles) > 0:
        ax = axes[0, 0]
        if actuator_index is not None:
            # Plot only the specified actuator
            if actuator_index < joint_angles.shape[1]:
                ax.plot(times[:len(joint_angles)], joint_angles[:, actuator_index], 
                       alpha=0.7, linewidth=1.2, label=f'Actuator {actuator_index}')
                ax.legend()
            else:
                ax.text(0.5, 0.5, f'Actuator {actuator_index} not found\n(max index: {joint_angles.shape[1]-1})', 
                       transform=ax.transAxes, ha='center', va='center')
        else:
            # Plot all actuators
            for i in range(joint_angles.shape[1]):
                ax.plot(times[:len(joint_angles)], joint_angles[:, i], alpha=0.7, linewidth=0.8)
        ax.set_title('Joint Angles')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Angle (rad)')
        ax.grid(True, alpha=0.3)
    
    # Plot joint velocities
    if len(joint_vels) > 0:
        ax = axes[0, 1]
        if actuator_index is not None:
            # Plot only the specified actuator
            if actuator_index < joint_vels.shape[1]:
                ax.plot(times[:len(joint_vels)], joint_vels[:, actuator_index], 
                       alpha=0.7, linewidth=1.2, label=f'Actuator {actuator_index}')
                ax.legend()
            else:
                ax.text(0.5, 0.5, f'Actuator {actuator_index} not found\n(max index: {joint_vels.shape[1]-1})', 
                       transform=ax.transAxes, ha='center', va='center')
        else:
            # Plot all actuators
            for i in range(joint_vels.shape[1]):
                ax.plot(times[:len(joint_vels)], joint_vels[:, i], alpha=0.7, linewidth=0.8)
        ax.set_title('Joint Velocities')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Velocity (rad/s)')
        ax.grid(True, alpha=0.3)
    
    # Plot projected gravity
    if len(projected_g) > 0:
        ax = axes[1, 0]
        labels = ['X', 'Y', 'Z']
        for i in range(projected_g.shape[1]):
            ax.plot(times[:len(projected_g)], projected_g[:, i], label=labels[i], linewidth=1.5)
        ax.set_title('Projected Gravity')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Acceleration (m/s²)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    # Plot acceleration
    if len(accel) > 0:
        ax = axes[1, 1]
        labels = ['X', 'Y', 'Z']
        for i in range(accel.shape[1]):
            ax.plot(times[:len(accel)], accel[:, i], label=labels[i], linewidth=1.5)
        ax.set_title('Acceleration')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Acceleration (m/s²)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    # Plot command
    if len(command) > 0:
        ax = axes[2, 0]
        if actuator_index is not None and len(command.shape) > 1:
            # Plot only the specified actuator command if it exists
            if actuator_index < command.shape[1]:
                ax.plot(times[:len(command)], command[:, actuator_index], 
                       label=f'Cmd {actuator_index}', linewidth=1.2)
            else:
                ax.text(0.5, 0.5, f'Command {actuator_index} not found\n(max index: {command.shape[1]-1})', 
                       transform=ax.transAxes, ha='center', va='center')
        else:
            # Plot all commands or single command array
            if len(command.shape) > 1:
                for i in range(command.shape[1]):
                    ax.plot(times[:len(command)], command[:, i], label=f'Cmd {i}', linewidth=1.2)
            else:
                ax.plot(times[:len(command)], command, label='Command', linewidth=1.2)
        ax.set_title('Command')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Command Value')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    # Plot output
    if len(output) > 0:
        ax = axes[2, 1]
        if actuator_index is not None:
            # Plot only the specified actuator output
            if actuator_index < output.shape[1]:
                ax.plot(times[:len(output)], output[:, actuator_index], 
                       alpha=0.7, linewidth=1.2, label=f'Output {actuator_index}')
                ax.legend()
            else:
                ax.text(0.5, 0.5, f'Output {actuator_index} not found\n(max index: {output.shape[1]-1})', 
                       transform=ax.transAxes, ha='center', va='center')
        else:
            # Plot all outputs
            for i in range(output.shape[1]):
                ax.plot(times[:len(output)], output[:, i], alpha=0.7, linewidth=0.8)
        ax.set_title('Output')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Output Value')
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot if output path is provided
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()

def plot_joint_tracking(data, output_path=None, skip_seconds=0.1, start_time=None, end_time=None):
    """Plot policy output (actions) vs actual joint position for each joint individually"""
    if not data:
        print("No data to plot")
        return
    
    # Filter data by time
    data = filter_data_by_time(data, skip_seconds, start_time, end_time)
    
    if not data:
        print("No data remaining after filtering")
        return
    
    # Extract timestamps and convert to seconds relative to first timestamp
    timestamps = [d['t_us'] for d in data]
    t_start = timestamps[0]
    times = [(t - t_start) / 1e6 for t in timestamps]  # Convert to seconds
    
    # Extract data arrays
    joint_angles = np.array([d['joint_angles'] for d in data if d['joint_angles'] is not None])
    output = np.array([d['output'] for d in data if d['output'] is not None])
    
    if len(joint_angles) == 0:
        print("No joint angle data found")
        return
    
    if len(output) == 0:
        print("No policy output data found")
        return
    
    # Determine number of joints
    num_joints = joint_angles.shape[1]
    print(f"Found {num_joints} joints")
    
    # Handle output dimensions
    if len(output.shape) == 1:
        print("Warning: Policy output is 1D, cannot match to individual joints")
        return
    
    num_actions = output.shape[1]
    print(f"Found {num_actions} policy output dimensions")
    
    # Use minimum of joints and actions to avoid index errors
    num_plots = min(num_joints, num_actions)
    print(f"Creating {num_plots} action vs position tracking plots")
    
    # Calculate subplot grid dimensions
    cols = 4  # 4 plots per row
    rows = (num_plots + cols - 1) // cols  # Ceiling division
    
    # Create subplots
    fig, axes = plt.subplots(rows, cols, figsize=(20, 5 * rows))
    
    # Create title with time range info
    title_parts = []
    if skip_seconds > 0:
        title_parts.append(f"skipped first {skip_seconds}s")
    if start_time is not None or end_time is not None:
        time_range = f"{start_time or 'start'}-{end_time or 'end'}s"
        title_parts.append(f"time range {time_range}")
    
    title_suffix = f" ({', '.join(title_parts)})" if title_parts else ""
    fig.suptitle(f'Policy Actions vs Joint Positions{title_suffix}', fontsize=16)
    
    # Handle case where we only have one row
    if rows == 1:
        axes = axes.reshape(1, -1) if num_plots > 1 else np.array([[axes]])
    
    # Plot each joint
    for i in range(num_plots):
        row = i // cols
        col = i % cols
        ax = axes[row, col]
        
        # Plot actual joint position
        ax.plot(times[:len(joint_angles)], joint_angles[:, i], 
                label='Actual Position', linewidth=1.5, color='blue', alpha=0.8)
        
        # Plot policy action/output
        ax.plot(times[:len(output)], output[:, i], 
                label='Policy Action', linewidth=1.2, color='red', alpha=0.7, linestyle='--')
        
        ax.set_title(f'Joint {i}')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Position (rad)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    # Hide unused subplots
    for i in range(num_plots, rows * cols):
        row = i // cols
        col = i % cols
        axes[row, col].set_visible(False)
    
    plt.tight_layout()
    
    # Save plot if output path is provided
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()

def main():
    parser = argparse.ArgumentParser(description='Plot robot data from NDJSON file')
    parser.add_argument('filepath', help='Path to the NDJSON file to plot')
    parser.add_argument('--save', action='store_true', help='Save plot to disk')
    parser.add_argument('--skip', type=float, default=0.1, 
                       help='Skip first N seconds of data (default: 0.1)')
    parser.add_argument('--actuator', type=int, default=None,
                       help='Plot only a specific actuator index (0-based)')
    parser.add_argument('--tracking', action='store_true',
                       help='Plot command vs position tracking for all joints')
    parser.add_argument('--start-time', type=float, default=None,
                       help='Start time for plotting (seconds from data start)')
    parser.add_argument('--end-time', type=float, default=None,
                       help='End time for plotting (seconds from data start)')
    
    args = parser.parse_args()
    
    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return 1
    
    print(f"Reading data from {filepath}...")
    data = read_ndjson(filepath)
    print(f"Loaded {len(data)} data points")
    
    # Generate output path if saving is requested
    output_path = None
    if args.save:
        name_parts = [filepath.stem]
        if args.tracking:
            name_parts.append("tracking")
        if args.actuator is not None:
            name_parts.append(f"actuator_{args.actuator}")
        if args.start_time is not None or args.end_time is not None:
            time_range = f"{args.start_time or 'start'}to{args.end_time or 'end'}s"
            name_parts.append(time_range)
        name_parts.append("plot.png")
        output_path = filepath.parent / "_".join(name_parts)
    
    # Choose which plotting function to use
    if args.tracking:
        plot_joint_tracking(data, output_path, skip_seconds=args.skip, 
                          start_time=args.start_time, end_time=args.end_time)
    else:
        plot_data(data, output_path, skip_seconds=args.skip, actuator_index=args.actuator,
                 start_time=args.start_time, end_time=args.end_time)
    
    return 0

if __name__ == "__main__":
    exit(main())