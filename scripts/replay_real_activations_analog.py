import json
import os
import sys
import torch
import numpy as np
from torch import nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from aihwkit.nn import AnalogLinear
from aihwkit.simulator.configs import SingleRPUConfig
from aihwkit.simulator.parameters import WeightNoiseType
import gc

MODEL_ID = 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'
ACTIVATIONS_DIR = 'results/real_activations'
OUTPUT_DIR = 'results/real_activation_analog_errors'
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

def make_rpu(noise_eta):
    cfg = SingleRPUConfig()
    cfg.forward.w_noise = noise_eta
    cfg.forward.w_noise_type = WeightNoiseType.PCM_READ
    cfg.backward.w_noise = noise_eta
    cfg.backward.w_noise_type = WeightNoiseType.PCM_READ
    cfg.device.w_min = -1.0
    cfg.device.w_max = 1.0
    return cfg

def measure_matrix_with_real_activation(original_module, noise_eta, real_activation):
    """Measure analog error using real activation from WikiText-2."""
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
    
    wrapped = AnalogLinearWrapper(analog, weight.shape[0])
    wrapped.eval()
    
    # Convert real activation to torch tensor (float16, then half)
    act_tensor = torch.from_numpy(real_activation).half()
    
    with torch.no_grad():
        digital_out = original_module(act_tensor)
        analog_out = wrapped(act_tensor)
        
        if digital_out.shape != analog_out.shape:
            analog_out = analog_out.view(digital_out.shape)
        
        mse = ((analog_out.float() - digital_out.float()) ** 2).mean().item()
        rel_err = (torch.abs(analog_out.float() - digital_out.float()) / 
                   (digital_out.float().abs() + 1e-8)).mean().item()
        
        # Also compute per-token statistics
        seq_len = digital_out.shape[1]
        token_rel_errors = []
        for t in range(seq_len):
            d_t = digital_out[:, t, :].float()
            a_t = analog_out[:, t, :].float()
            token_rel = (torch.abs(a_t - d_t) / (d_t.abs() + 1e-8)).mean().item()
            token_rel_errors.append(token_rel)
    
    del analog, wrapped
    gc.collect()
    
    return {
        'mse': mse,
        'relative_error': rel_err,
        'token_rel_errors': token_rel_errors,
        'mean_token_rel_error': float(np.mean(token_rel_errors)),
        'max_token_rel_error': float(np.max(token_rel_errors)),
        'std_token_rel_error': float(np.std(token_rel_errors)),
    }

def main():
    target_layer = int(sys.argv[1]) if len(sys.argv) > 1 else 18
    print(f'=== Real Activation Analog Replay: Layer {target_layer} ===')
    
    # Load real activation
    act_path = f'{ACTIVATIONS_DIR}/layer_{target_layer}_input_activations.npy'
    real_activation = np.load(act_path)
    print(f'Loaded activation: shape={real_activation.shape}')
    
    # Load model
    print('Loading model...')
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.float16, device_map='cpu', low_cpu_mem_usage=True
    )
    model.eval()
    print('Model loaded.')
    
    layer = model.model.layers[target_layer]
    
    matrices = {
        'q_proj': layer.self_attn.q_proj,
        'k_proj': layer.self_attn.k_proj,
        'v_proj': layer.self_attn.v_proj,
        'o_proj': layer.self_attn.o_proj,
        'gate_proj': layer.mlp.gate_proj,
        'up_proj': layer.mlp.up_proj,
        'down_proj': layer.mlp.down_proj,
    }
    
    results = {'layer': target_layer, 'matrices': {}}
    
    for name, mod in matrices.items():
        print(f'  Measuring {name}...', end='', flush=True)
        
        for noise_label, noise_val in [('eta_0', 0.0), ('eta_038', 0.038)]:
            try:
                metrics = measure_matrix_with_real_activation(mod, noise_val, real_activation)
                key = f'{name}_{noise_label}'
                results['matrices'][key] = metrics
            except Exception as e:
                results['matrices'][f'{name}_{noise_label}'] = {'error': str(e)}
        
        print(' done')
    
    # Save results
    output_path = f'{OUTPUT_DIR}/layer_{target_layer}_real_activation_errors.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f'\n=== Summary for Layer {target_layer} (Real Activations) ===')
    for name in ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']:
        k0 = f'{name}_eta_0'
        k038 = f'{name}_eta_038'
        r0 = results['matrices'].get(k0, {}).get('relative_error', None)
        r038 = results['matrices'].get(k038, {}).get('relative_error', None)
        if r0 is not None:
            delta = (r038 - r0) * 100 if r038 else 0
            print(f'  {name:10s}: η=0%={r0*100:6.1f}% | η=3.8%={r038*100:6.1f}% | PCM_delta={delta:+6.1f}%')
    
    gc.collect()
    print(f'Results saved to {output_path}')

if __name__ == '__main__':
    main()
