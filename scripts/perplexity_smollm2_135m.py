#!/usr/bin/env python3
"""
Perplexity test with smaller model (SmolLM2-135M) to avoid OOM.
Tests analog viability with fewer resources.
"""

import json
import os
import torch
import numpy as np
from torch import nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from aihwkit.nn import AnalogLinear
from aihwkit.simulator.configs import SingleRPUConfig
from aihwkit.simulator.parameters import WeightNoiseType
import gc

MODEL_ID = 'HuggingFaceTB/SmolLM2-135M'
OUTPUT_DIR = 'results/perplexity_tests'
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_TEXTS = [
    "The United States Declaration of Independence is the pronouncement adopted by the Second Continental Congress meeting in Philadelphia, Pennsylvania, on July 4, 1776.",
    "Machine learning is a field of inquiry devoted to understanding and building methods that learn, that is, methods that leverage data to improve performance on some set of tasks.",
    "The Transformer architecture has become the dominant approach for natural language processing tasks, replacing earlier recurrent neural network models.",
    "Deep learning is part of a broader family of machine learning methods based on artificial neural networks with representation learning.",
    "Natural language processing is a subfield of linguistics, computer science, and artificial intelligence concerned with the interactions between computers and human language.",
    "Reinforcement learning is an area of machine learning concerned with how intelligent agents ought to take actions in an environment in order to maximize the notion of cumulative reward.",
    "Computer vision is an interdisciplinary scientific field that deals with how computers can gain high-level understanding from digital images or videos.",
    "The Turing test, originally called the imitation game by Alan Turing in 1950, is a test of a machine's ability to exhibit intelligent behavior equivalent to, or indistinguishable from, that of a human.",
    "Quantum computing is a type of computation that harnesses the collective properties of quantum states, such as superposition, interference, and entanglement, to perform calculations.",
    "The Internet of Things describes physical objects with sensors, processing ability, software and other technologies that connect and exchange data with other devices and systems over the Internet.",
]

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

def make_rpu(noise_eta=0.038):
    cfg = SingleRPUConfig()
    cfg.forward.w_noise = noise_eta
    cfg.forward.w_noise_type = WeightNoiseType.PCM_READ
    cfg.backward.w_noise = noise_eta
    cfg.backward.w_noise_type = WeightNoiseType.PCM_READ
    cfg.device.w_min = -1.0
    cfg.device.w_max = 1.0
    return cfg

def create_analog_matrix(original_module, noise_eta=0.038):
    weight = original_module.weight.data.cpu().float()
    rpu = make_rpu(noise_eta)
    analog = AnalogLinear(
        in_features=weight.shape[1],
        out_features=weight.shape[0],
        bias=original_module.bias is not None,
        rpu_config=rpu
    )
    if original_module.bias is not None:
        analog.set_weights(weight, original_module.bias.data.cpu().float())
    else:
        analog.set_weights(weight)
    analog.eval()
    wrapped = AnalogLinearWrapper(analog, weight.shape[0])
    wrapped.eval()
    return wrapped

def map_layers_to_analog(model, target_layers, noise_eta=0.038):
    for layer_idx in target_layers:
        layer = model.model.layers[layer_idx]
        print(f'  Mapping layer {layer_idx}...')
        layer.self_attn.q_proj = create_analog_matrix(layer.self_attn.q_proj, noise_eta)
        layer.self_attn.k_proj = create_analog_matrix(layer.self_attn.k_proj, noise_eta)
        layer.self_attn.v_proj = create_analog_matrix(layer.self_attn.v_proj, noise_eta)
        layer.self_attn.o_proj = create_analog_matrix(layer.self_attn.o_proj, noise_eta)
        layer.mlp.gate_proj = create_analog_matrix(layer.mlp.gate_proj, noise_eta)
        layer.mlp.up_proj = create_analog_matrix(layer.mlp.up_proj, noise_eta)
        layer.mlp.down_proj = create_analog_matrix(layer.mlp.down_proj, noise_eta)
    print(f'Mapped {len(target_layers)} layers to analog (η={noise_eta})')
    return model

def calculate_perplexity(model, tokenizer, texts, max_length=64):
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    
    with torch.no_grad():
        for i, text in enumerate(texts):
            print(f'  Processing text {i+1}/{len(texts)}...')
            inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=max_length)
            input_ids = inputs['input_ids']
            
            if input_ids.shape[1] < 5:
                continue
            
            labels = input_ids.clone()
            outputs = model(input_ids, labels=labels)
            loss = outputs.loss
            n_tokens = (labels != -100).sum().item()
            
            if loss is not None and n_tokens > 0:
                total_loss += loss.item() * n_tokens
                total_tokens += n_tokens
            
            del inputs, input_ids, labels, outputs
            gc.collect()
    
    if total_tokens == 0:
        return float('inf')
    
    avg_loss = total_loss / total_tokens
    perplexity = np.exp(avg_loss)
    return perplexity

def main():
    target_layers = [18, 19, 20, 21]  # Last 4 layers of SmolLM2-135M (30 layers total)
    noise_eta = 0.038
    
    print('=== SmolLM2-135M Analog Perplexity Test ===')
    print(f'Target layers: {target_layers}')
    print(f'PCM noise η: {noise_eta}')
    print(f'Text samples: {len(SAMPLE_TEXTS)}')
    print()
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    
    # Test 1: Digital baseline
    print('--- Test 1: Digital Baseline ---')
    print('Loading model...')
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map='cpu',
        low_cpu_mem_usage=True
    )
    model.eval()
    
    print('Calculating digital perplexity...')
    ppl_digital = calculate_perplexity(model, tokenizer, SAMPLE_TEXTS)
    print(f'Digital Perplexity: {ppl_digital:.2f}')
    
    del model
    gc.collect()
    
    # Test 2: Analog test
    print('\n--- Test 2: Analog Layers 18-21 ---')
    print('Loading model...')
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map='cpu',
        low_cpu_mem_usage=True
    )
    model.eval()
    
    model = map_layers_to_analog(model, target_layers, noise_eta)
    
    print('Calculating analog perplexity...')
    ppl_analog = calculate_perplexity(model, tokenizer, SAMPLE_TEXTS)
    print(f'Analog Perplexity: {ppl_analog:.2f}')
    
    # Results
    degradation = ppl_analog - ppl_digital
    pct_degradation = (degradation / ppl_digital) * 100 if ppl_digital > 0 else float('inf')
    ratio = ppl_analog / ppl_digital if ppl_digital > 0 else float('inf')
    
    print('\n=== RESULTS ===')
    print(f'Digital Perplexity:  {ppl_digital:.2f}')
    print(f'Analog Perplexity:   {ppl_analog:.2f}')
    print(f'Absolute Δ:          {degradation:+.2f}')
    print(f'Percent Δ:           {pct_degradation:+.1f}%')
    print(f'Ratio (analog/dig):  {ratio:.2f}×')
    
    if pct_degradation < 10:
        verdict = 'GREEN — Analog is viable!'
    elif pct_degradation < 50:
        verdict = 'YELLOW — Marginal, try selective mapping'
    else:
        verdict = 'RED — Current PCM noise too high'
    print(f'Verdict: {verdict}')
    
    results = {
        'model': MODEL_ID,
        'target_layers': target_layers,
        'noise_eta': noise_eta,
        'num_samples': len(SAMPLE_TEXTS),
        'digital_perplexity': float(ppl_digital),
        'analog_perplexity': float(ppl_analog),
        'absolute_degradation': float(degradation),
        'percent_degradation': float(pct_degradation),
        'ratio': float(ratio),
        'verdict': verdict,
    }
    
    output_path = f'{OUTPUT_DIR}/perplexity_smollm2_135m.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nResults saved to {output_path}')
    print('\nDone!')
    
    del model
    gc.collect()

if __name__ == '__main__':
    main()
