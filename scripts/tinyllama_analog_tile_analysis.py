"""
TinyLlama Layer 0 — Analog Tile Mapping + PCM Noise Impact Analysis
Maps transformer attention and MLP weights to AIHWKIT analog tiles
Measures inference accuracy degradation from PCM device noise

Requires: laere_analog_export/layer0_*.npy (from tinyllama_benchmark.py)
"""
import numpy as np
import torch
from aihwkit.nn import AnalogLinear
from aihwkit.simulator.configs import SingleRPUConfig
from aihwkit.simulator.parameters import WeightNoiseType
import json
import os
import time

OUTPUT_DIR = './laere_analog_export'
RESULTS_FILE = f'{OUTPUT_DIR}/analog_analysis.json'

# ============================================
# 1. Load Exported Weights
# ============================================
def load_weights():
    weights = {}
    files = {
        'q_proj': 'layer0_self_attn_q_proj_weight.npy',
        'k_proj': 'layer0_self_attn_k_proj_weight.npy',
        'v_proj': 'layer0_self_attn_v_proj_weight.npy',
        'o_proj': 'layer0_self_attn_o_proj_weight.npy',
        'gate_proj': 'layer0_mlp_gate_proj_weight.npy',
        'up_proj': 'layer0_mlp_up_proj_weight.npy',
        'down_proj': 'layer0_mlp_down_proj_weight.npy',
    }
    
    for name, filename in files.items():
        path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(path):
            weights[name] = np.load(path)
            print(f"[+] {name}: {weights[name].shape} ({weights[name].nbytes/1024/1024:.1f} MB)")
        else:
            print(f"[!] Missing: {filename}")
    
    return weights

# ============================================
# 2. Create PCM Analog Configuration
# ============================================
def create_pcm_config(noise_level=0.038):
    """PCM noise configuration per IBM paper (eta = 3.8%)"""
    rpu_config = SingleRPUConfig()
    rpu_config.forward.w_noise = noise_level
    rpu_config.forward.w_noise_type = WeightNoiseType.PCM_READ
    rpu_config.backward.w_noise = noise_level
    rpu_config.backward.w_noise_type = WeightNoiseType.PCM_READ
    rpu_config.device.w_min = -1.0
    rpu_config.device.w_max = 1.0
    return rpu_config

# ============================================
# 3. Map Weight Matrix to Analog Tile
# ============================================
def map_to_analog(weight_matrix, rpu_config, name):
    """Map a numpy weight matrix to AIHWKIT AnalogLinear tile"""
    # Convert to torch tensor
    weight_tensor = torch.from_numpy(weight_matrix).float()
    
    in_features = weight_tensor.shape[1]
    out_features = weight_tensor.shape[0]
    
    # Create analog linear layer
    analog_layer = AnalogLinear(
        in_features=in_features,
        out_features=out_features,
        bias=False,
        rpu_config=rpu_config
    )
    
    # Set weights
    analog_layer.set_weights(weight_tensor)
    
    print(f"    Analog tile: {in_features} → {out_features}")
    print(f"    Weight range: [{weight_tensor.min():.3f}, {weight_tensor.max():.3f}]")
    print(f"    Weight std: {weight_tensor.std():.4f}")
    
    return analog_layer

# ============================================
# 4. Benchmark: Digital vs Analog Inference
# ============================================
def benchmark_layer(analog_layer, weight_tensor, name, num_runs=10):
    """Compare digital (exact) vs analog (noisy) inference"""
    in_features = weight_tensor.shape[1]
    
    # Generate random input (batch=100)
    torch.manual_seed(42)
    test_input = torch.randn(100, in_features)
    
    # Digital reference (exact matrix multiply)
    digital_output = torch.matmul(test_input, weight_tensor.T)
    
    # Analog inference (with PCM noise, multiple runs)
    analog_outputs = []
    analog_layer.eval()
    
    for run in range(num_runs):
        with torch.no_grad():
            out = analog_layer(test_input)
        analog_outputs.append(out)
    
    # Compute statistics
    analog_stack = torch.stack(analog_outputs)
    analog_mean = analog_stack.mean(dim=0)
    analog_std = analog_stack.std(dim=0)
    
    # Error metrics
    mse_digital_analog = ((digital_output - analog_mean) ** 2).mean().item()
    mse_analog_variance = (analog_std ** 2).mean().item()
    
    # Signal-to-noise ratio
    signal_power = (digital_output ** 2).mean().item()
    snr_db = 10 * np.log10(signal_power / (mse_digital_analog + 1e-10))
    
    # Relative error
    relative_error = torch.abs(digital_output - analog_mean).mean().item() / torch.abs(digital_output).mean().item()
    
    print(f"    Digital vs Analog mean MSE: {mse_digital_analog:.6f}")
    print(f"    Analog run-to-run variance: {mse_analog_variance:.6f}")
    print(f"    SNR: {snr_db:.2f} dB")
    print(f"    Relative error: {relative_error:.4f} ({relative_error*100:.2f}%)")
    
    return {
        'mse_digital_analog': mse_digital_analog,
        'mse_analog_variance': mse_analog_variance,
        'snr_db': snr_db,
        'relative_error': relative_error,
        'relative_error_pct': relative_error * 100,
    }

# ============================================
# 5. PCM Device Count + Area Estimation
# ============================================
def estimate_hardware(weight_matrix, name):
    """Estimate PCM devices needed for differential mapping"""
    # Each weight needs 2 PCM devices (differential pair: G+ and G-)
    num_weights = weight_matrix.size
    num_devices = num_weights * 2  # Differential pair
    
    # IBM PCM device: ~50nm × 50nm (2,500 nm²)
    device_area_nm2 = 50 * 50
    total_area_um2 = (num_devices * device_area_nm2) / 1e6
    
    # Crossbar array dimensions
    rows, cols = weight_matrix.shape
    
    print(f"    Weights: {num_weights:,}")
    print(f"    PCM devices (differential): {num_devices:,}")
    print(f"    Crossbar: {rows} × {cols}")
    print(f"    Estimated area: {total_area_um2:.1f} μm² ({total_area_um2/1e6:.4f} mm²)")
    
    return {
        'num_weights': int(num_weights),
        'num_pcm_devices': int(num_devices),
        'crossbar_rows': int(rows),
        'crossbar_cols': int(cols),
        'estimated_area_um2': total_area_um2,
        'estimated_area_mm2': total_area_um2 / 1e6,
    }

# ============================================
# 6. Full Layer Analysis
# ============================================
def analyze_full_layer():
    """Map complete attention + MLP block to analog tiles"""
    print("=" * 60)
    print("TinyLlama Layer 0 — Analog Tile Mapping Analysis")
    print("=" * 60)
    
    weights = load_weights()
    if not weights:
        print("[!] No weights found. Run tinyllama_benchmark.py first.")
        return
    
    rpu_config = create_pcm_config(noise_level=0.038)
    
    results = {
        'model': 'TinyLlama-1.1B-Chat-v1.0',
        'layer': 'transformer block 0',
        'noise_level': 0.038,
        'blocks': {},
        'total_devices': 0,
        'total_area_mm2': 0,
    }
    
    # Analyze each weight matrix
    for name, w in weights.items():
        print(f"\n[*] {name}: {w.shape}")
        
        weight_tensor = torch.from_numpy(w).float()
        
        # Hardware estimate
        hw = estimate_hardware(w, name)
        results['total_devices'] += hw['num_pcm_devices']
        results['total_area_mm2'] += hw['estimated_area_mm2']
        
        # Map to analog
        analog_layer = map_to_analog(w, rpu_config, name)
        
        # Benchmark
        bench = benchmark_layer(analog_layer, weight_tensor, name, num_runs=10)
        
        results['blocks'][name] = {
            'shape': list(w.shape),
            'hardware': hw,
            'benchmark': bench,
        }
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total weight matrices: {len(weights)}")
    print(f"Total PCM devices: {results['total_devices']:,}")
    print(f"Estimated total area: {results['total_area_mm2']:.4f} mm²")
    print(f"\nPer-block relative error (analog vs digital):")
    
    for name, data in results['blocks'].items():
        err = data['benchmark']['relative_error_pct']
        devices = data['hardware']['num_pcm_devices']
        print(f"  {name:15s}: {err:6.2f}% error | {devices:,} devices")
    
    # Save results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[+] Results saved to {RESULTS_FILE}")
    
    return results

# ============================================
# 7. Noise Sensitivity Sweep
# ============================================
def noise_sensitivity_sweep():
    """Test how accuracy degrades with different PCM noise levels"""
    print("\n" + "=" * 60)
    print("Noise Sensitivity Sweep")
    print("=" * 60)
    
    weights = load_weights()
    if not weights:
        return
    
    # Use o_proj (2048×2048, largest) as representative
    test_name = 'o_proj'
    if test_name not in weights:
        test_name = list(weights.keys())[0]
    
    w = weights[test_name]
    weight_tensor = torch.from_numpy(w).float()
    
    noise_levels = [0.0, 0.01, 0.02, 0.038, 0.05, 0.10]
    sweep_results = {}
    
    for noise in noise_levels:
        print(f"\n[*] Noise η = {noise*100:.1f}%")
        rpu_config = create_pcm_config(noise_level=noise)
        analog_layer = map_to_analog(w, rpu_config, test_name)
        bench = benchmark_layer(analog_layer, weight_tensor, test_name, num_runs=5)
        sweep_results[f"eta_{noise}"] = bench
    
    # Save sweep
    sweep_file = f'{OUTPUT_DIR}/noise_sweep.json'
    with open(sweep_file, 'w') as f:
        json.dump(sweep_results, f, indent=2)
    
    print(f"\n[+] Sweep saved to {sweep_file}")
    
    # Print table
    print("\n| Noise η | Rel. Error | SNR (dB) |")
    print("|-----------|------------|----------|")
    for key, data in sweep_results.items():
        eta = float(key.replace('eta_', ''))
        print(f"| {eta*100:6.1f}% | {data['relative_error_pct']:9.2f}% | {data['snr_db']:8.2f} |")

# ============================================
# Main
# ============================================
def main():
    # Full analysis
    results = analyze_full_layer()
    
    # Noise sweep
    noise_sensitivity_sweep()
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nFiles generated:")
    print(f"  {OUTPUT_DIR}/benchmark.json — Digital baseline")
    print(f"  {OUTPUT_DIR}/analog_analysis.json — Per-block analog mapping")
    print(f"  {OUTPUT_DIR}/noise_sweep.json — Noise sensitivity")
    print(f"\nNext: Feed exported weights into hardware-aware training")
    print(f"      to see if noise injection (eta=3.8%) keeps accuracy")
    print(f"      within acceptable bounds for full model inference.")

if __name__ == '__main__':
    main()
