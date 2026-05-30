import json
import sys
import time
import torch
from torch import nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from aihwkit.nn import AnalogLinear
from aihwkit.simulator.configs import SingleRPUConfig
from aihwkit.simulator.parameters import WeightNoiseType
import gc

MODEL_ID = 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'

class AnalogLinearWrapper(nn.Module):
    def __init__(self, analog_linear, out_features):
        super().__init__()
        self.analog_linear = analog_linear
        self.out_features = out_features
    def forward(self, hidden_states, *args, **kwargs):
        orig_shape = hidden_states.shape
        orig_dtype = hidden_states.dtype
        hidden_states = hidden_states.float()
        if len(orig_shape) == 3:
            flat = hidden_states.reshape(-1, orig_shape[-1])
            out = self.analog_linear(flat)
            out = out.view(orig_shape[0], orig_shape[1], self.out_features)
        else:
            out = self.analog_linear(hidden_states)
        return out.to(orig_dtype)

def make_rpu(noise):
    cfg = SingleRPUConfig()
    cfg.forward.w_noise = noise
    cfg.forward.w_noise_type = WeightNoiseType.PCM_READ
    cfg.backward.w_noise = noise
    cfg.backward.w_noise_type = WeightNoiseType.PCM_READ
    cfg.device.w_min = -1.0
    cfg.device.w_max = 1.0
    return cfg

def measure_matrix_error(original_module, noise_eta, test_input):
    """Create analog tile, measure MSE and relative error vs digital."""
    weight = original_module.weight.data.cpu().float()
    rpu = make_rpu(noise_eta)
    analog = AnalogLinear(
        in_features=weight.shape[1],
        out_features=weight.shape[0],
        bias=False,
        rpu_config=rpu
    )
    analog.set_weights(weight)
    analog.eval()
    
    # For o_proj compatibility
    wrapped = AnalogLinearWrapper(analog, weight.shape[0])
    wrapped.eval()
    
    with torch.no_grad():
        digital_out = original_module(test_input.half())
        analog_out = wrapped(test_input.half())
        
        # Handle shape mismatch (digital may return 3D, analog may need reshape)
        if digital_out.shape != analog_out.shape:
            analog_out = analog_out.view(digital_out.shape)
        
        mse = ((analog_out.float() - digital_out.float()) ** 2).mean().item()
        rel_err = (torch.abs(analog_out.float() - digital_out.float()) / 
                   (digital_out.float().abs() + 1e-8)).mean().item()
    
    # Cleanup
    del analog, wrapped
    gc.collect()
    
    return {
        'mse': mse,
        'relative_error': rel_err,
        'shape': list(weight.shape),
        'num_weights': int(weight.numel()),
        'num_pcm_devices': int(weight.numel() * 2),  # differential pair
    }

def measure_layer(layer, layer_idx, test_input):
    """Measure all 7 matrices in a transformer layer."""
    results = {'layer': layer_idx, 'matrices': {}}
    
    matrices = {
        'q_proj': layer.self_attn.q_proj,
        'k_proj': layer.self_attn.k_proj,
        'v_proj': layer.self_attn.v_proj,
        'o_proj': layer.self_attn.o_proj,
        'gate_proj': layer.mlp.gate_proj,
        'up_proj': layer.mlp.up_proj,
        'down_proj': layer.mlp.down_proj,
    }
    
    for name, mod in matrices.items():
        # Test input shape must match each matrix's expected input
        in_features = mod.weight.shape[1]
        # Create test input of appropriate size
        test = torch.randn(1, 10, in_features)
        
        for noise_label, noise_val in [('eta_0', 0.0), ('eta_038', 0.038)]:
            try:
                metrics = measure_matrix_error(mod, noise_val, test)
                key = f'{name}_{noise_label}'
                results['matrices'][key] = metrics
            except Exception as e:
                results['matrices'][f'{name}_{noise_label}'] = {'error': str(e)}
    
    return results

def main():
    start_layer = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_layer = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    print(f'=== Measuring layers {start_layer}-{end_layer} ===')
    
    # Load model
    print('Loading model...')
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.float16, device_map='cpu', low_cpu_mem_usage=True
    )
    model.eval()
    print('Model loaded.')
    
    # Save incrementally after each layer
    all_results = []
    output_path = f'results/layer_profiles_{start_layer}_{end_layer}.json'
    
    for layer_idx in range(start_layer, min(end_layer + 1, len(model.model.layers))):
        layer = model.model.layers[layer_idx]
        print(f'  Measuring layer {layer_idx}...', end='', flush=True)
        
        # Standard test input for all matrices in this layer
        # (they all take hidden_dim=2048 as input)
        test_input = torch.randn(1, 10, 2048)
        
        layer_results = measure_layer(layer, layer_idx, test_input)
        all_results.append(layer_results)
        
        # Save after each layer so we don't lose progress on timeout
        with open(output_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        print(f' done ({len(layer_results["matrices"])} measurements)')
    
    print(f'Results saved to {output_path}')
    
    # Summary
    print('\n=== Summary ===')
    for lr in all_results:
        l = lr['layer']
        # Get o_proj errors
        o_0 = lr['matrices'].get('o_proj_eta_0', {}).get('relative_error', None)
        o_038 = lr['matrices'].get('o_proj_eta_038', {}).get('relative_error', None)
        print(f'  Layer {l}: o_proj η=0%={o_0*100:.1f}%, η=3.8%={o_038*100:.1f}%')
    
    gc.collect()

if __name__ == '__main__':
    main()
