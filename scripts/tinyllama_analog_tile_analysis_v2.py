"""
TinyLlama Layer 0 — Analog Tile Mapping + PCM Noise Impact Analysis
Streamlined version for memory-constrained environments.
Maps transformer attention and MLP weights to AIHWKIT analog tiles.
"""
import numpy as np
import torch
from aihwkit.nn import AnalogLinear
from aihwkit.simulator.configs import SingleRPUConfig
from aihwkit.simulator.parameters import WeightNoiseType
import json
import os
import gc

OUTPUT_DIR = './laere_analog_export'
RESULTS_FILE = f'{OUTPUT_DIR}/analog_analysis.json'

# ============================================
# 1. PCM Configuration (η = 3.8% per IBM)
# ============================================
def create_pcm_config(noise_level=0.038):
    rpu_config = SingleRPUConfig()
    rpu_config.forward.w_noise = noise_level
    rpu_config.forward.w_noise_type = WeightNoiseType.PCM_READ
    rpu_config.backward.w_noise = noise_level
    rpu_config.backward.w_noise_type = WeightNoiseType.PCM_READ
    rpu_config.device.w_min = -1.0
    rpu_config.device.w_max = 1.0
    return rpu_config

# ============================================
# 2. Analyze Single Weight Matrix
# ============================================
def analyze_weight(name, weight_np, rpu_config, num_runs=3, batch_size=10):
    """Map one weight matrix to analog tile and measure noise impact."""
    weight_tensor = torch.from_numpy(weight_np).float()
    in_features = weight_tensor.shape[1]
    out_features = weight_tensor.shape[0]
    
    print(f"\n[*] {name}: {weight_np.shape} ({weight_np.nbytes/1024/1024:.1f} MB)")
    
    # Hardware estimate
    num_weights = weight_np.size
    num_devices = num_weights * 2  # Differential pair
    device_area_nm2 = 50 * 50
    total_area_um2 = (num_devices * device_area_nm2) / 1e6
    
    print(f"    PCM devices (differential): {num_devices:,}")
    print(f"    Crossbar: {out_features} × {in_features}")
    print(f"    Estimated area: {total_area_um2:.1f} μm²")
    
    # Create analog tile
    analog_layer = AnalogLinear(
        in_features=in_features,
        out_features=out_features,
        bias=False,
        rpu_config=rpu_config
    )
    analog_layer.set_weights(weight_tensor)
    analog_layer.eval()
    
    print(f"    Weight range: [{weight_tensor.min():.3f}, {weight_tensor.max():.3f}]")
    
    # Digital reference
    torch.manual_seed(42)
    test_input = torch.randn(batch_size, in_features)
    digital_output = torch.matmul(test_input, weight_tensor.T)
    
    # Analog inference (PCM noise, multiple runs)
    analog_outputs = []
    for run in range(num_runs):
        with torch.no_grad():
            out = analog_layer(test_input)
        analog_outputs.append(out)
    
    analog_stack = torch.stack(analog_outputs)
    analog_mean = analog_stack.mean(dim=0)
    analog_std = analog_stack.std(dim=0)
    
    # Error metrics
    mse_digital_analog = ((digital_output - analog_mean) ** 2).mean().item()
    mse_analog_variance = (analog_std ** 2).mean().item()
    signal_power = (digital_output ** 2).mean().item()
    snr_db = 10 * np.log10(signal_power / (mse_digital_analog + 1e-10))
    relative_error = torch.abs(digital_output - analog_mean).mean().item() / torch.abs(digital_output).mean().item()
    
    print(f"    MSE (digital vs analog mean): {mse_digital_analog:.6f}")
    print(f"    Run-to-run variance: {mse_analog_variance:.6f}")
    print(f"    SNR: {snr_db:.2f} dB")
    print(f"    Relative error: {relative_error:.4f} ({relative_error*100:.2f}%)")
    
    # Cleanup
    del analog_layer, analog_outputs, analog_stack, analog_mean, analog_std
    gc.collect()
    
    return {
        'shape': list(weight_np.shape),
        'hardware': {
            'num_weights': int(num_weights),
            'num_pcm_devices': int(num_devices),
            'crossbar_rows': int(out_features),
            'crossbar_cols': int(in_features),
            'estimated_area_um2': total_area_um2,
            'estimated_area_mm2': total_area_um2 / 1e6,
        },
        'benchmark': {
            'mse_digital_analog': mse_digital_analog,
            'mse_analog_variance': mse_analog_variance,
            'snr_db': snr_db,
            'relative_error': relative_error,
            'relative_error_pct': relative_error * 100,
        }
    }

# ============================================
# 3. Noise Sensitivity Sweep
# ============================================
def noise_sweep(name, weight_np):
    """Test accuracy at different PCM noise levels."""
    print(f"\n{'='*60}")
    print(f"Noise Sensitivity Sweep: {name}")
    print(f"{'='*60}")
    
    noise_levels = [0.0, 0.01, 0.02, 0.038, 0.05, 0.10]
    sweep_results = {}
    
    for noise in noise_levels:
        rpu_config = create_pcm_config(noise_level=noise)
        data = analyze_weight(f"{name} (η={noise*100:.1f}%)", weight_np, rpu_config, num_runs=3, batch_size=10)
        sweep_results[f"eta_{noise}"] = data['benchmark']
        gc.collect()
    
    print(f"\n| Noise η | Rel. Error | SNR (dB) |")
    print("|---------|------------|----------|")
    for key, data in sweep_results.items():
        eta = float(key.replace('eta_', ''))
        print(f"| {eta*100:6.1f}% | {data['relative_error_pct']:9.2f}% | {data['snr_db']:8.2f} |")
    
    return sweep_results

# ============================================
# 4. Main Analysis
# ============================================
def main():
    print("=" * 60)
    print("TinyLlama Layer 0 — Analog Tile Mapping Analysis")
    print("=" * 60)
    
    files = {
        'q_proj': 'layer0_self_attn_q_proj_weight.npy',
        'k_proj': 'layer0_self_attn_k_proj_weight.npy',
        'v_proj': 'layer0_self_attn_v_proj_weight.npy',
        'o_proj': 'layer0_self_attn_o_proj_weight.npy',
        'gate_proj': 'layer0_mlp_gate_proj_weight.npy',
        'up_proj': 'layer0_mlp_up_proj_weight.npy',
        'down_proj': 'layer0_mlp_down_proj_weight.npy',
    }
    
    # PCM config at η = 3.8%
    rpu_config = create_pcm_config(noise_level=0.038)
    
    results = {
        'model': 'TinyLlama-1.1B-Chat-v1.0',
        'layer': 'transformer block 0',
        'noise_level': 0.038,
        'blocks': {},
        'total_devices': 0,
        'total_area_mm2': 0,
    }
    
    for name, filename in files.items():
        path = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(path):
            print(f"[!] Missing: {filename}")
            continue
        
        weight_np = np.load(path)
        data = analyze_weight(name, weight_np, rpu_config, num_runs=3, batch_size=10)
        
        results['blocks'][name] = data
        results['total_devices'] += data['hardware']['num_pcm_devices']
        results['total_area_mm2'] += data['hardware']['estimated_area_mm2']
        gc.collect()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total weight matrices: {len(results['blocks'])}")
    print(f"Total PCM devices: {results['total_devices']:,}")
    print(f"Estimated total area: {results['total_area_mm2']:.4f} mm²")
    print(f"\nPer-block relative error (analog vs digital, η=3.8%):")
    
    for name, data in results['blocks'].items():
        err = data['benchmark']['relative_error_pct']
        devices = data['hardware']['num_pcm_devices']
        print(f"  {name:15s}: {err:6.2f}% error | {devices:,} devices")
    
    # Save results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Saved: {RESULTS_FILE}")
    
    # Noise sweep on o_proj (largest, most representative)
    print("\n[*] Running noise sensitivity sweep on o_proj...")
    o_proj_np = np.load(os.path.join(OUTPUT_DIR, files['o_proj']))
    sweep = noise_sweep('o_proj', o_proj_np)
    
    sweep_file = f'{OUTPUT_DIR}/noise_sweep.json'
    with open(sweep_file, 'w') as f:
        json.dump(sweep, f, indent=2)
    print(f"[+] Saved: {sweep_file}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nArtifacts in {OUTPUT_DIR}:")
    print(f"  benchmark.json — Digital baseline (4.21 tok/s)")
    print(f"  analog_analysis.json — Per-block analog mapping + PCM noise")
    print(f"  noise_sweep.json — Sensitivity across η = 0–10%")

if __name__ == '__main__':
    main()
