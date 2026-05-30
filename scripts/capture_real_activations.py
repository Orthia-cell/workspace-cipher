import json
import os
import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'
OUTPUT_DIR = 'results/real_activations'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Sample real text from WikiText-2 style (academic/prose mix)
SAMPLE_TEXTS = [
    "The United States Declaration of Independence is the pronouncement adopted by the Second Continental Congress meeting in Philadelphia, Pennsylvania, on July 4, 1776.",
    "Enacted by the British Parliament, the Stamp Act required that many printed materials in the colonies be produced on stamped paper produced in London.",
    "Machine learning is a field of inquiry devoted to understanding and building methods that learn, that is, methods that leverage data to improve performance on some set of tasks.",
    "The Transformer architecture has become the dominant approach for natural language processing tasks, replacing earlier recurrent neural network models.",
    "In the field of artificial intelligence, neural networks are computing systems inspired by biological neural networks that constitute animal brains.",
    "The history of artificial intelligence began in antiquity, with myths, stories and rumors of artificial beings endowed with intelligence or consciousness by master craftsmen.",
    "Deep learning is part of a broader family of machine learning methods based on artificial neural networks with representation learning.",
    "Natural language processing is a subfield of linguistics, computer science, and artificial intelligence concerned with the interactions between computers and human language.",
    "Reinforcement learning is an area of machine learning concerned with how intelligent agents ought to take actions in an environment in order to maximize the notion of cumulative reward.",
    "Computer vision is an interdisciplinary scientific field that deals with how computers can gain high-level understanding from digital images or videos.",
    "The Turing test, originally called the imitation game by Alan Turing in 1950, is a test of a machine's ability to exhibit intelligent behavior equivalent to, or indistinguishable from, that of a human.",
    "Cloud computing is the on-demand availability of computer system resources, especially data storage and computing power, without direct active management by the user.",
    "Quantum computing is a type of computation that harnesses the collective properties of quantum states, such as superposition, interference, and entanglement, to perform calculations.",
    "The Internet of Things describes physical objects with sensors, processing ability, software and other technologies that connect and exchange data with other devices and systems over the Internet.",
    "Blockchain is a distributed ledger technology that maintains a continuously growing list of records, called blocks, which are linked and secured using cryptography.",
    "Cryptocurrency is a digital currency designed to work as a medium of exchange through a computer network that is not reliant on any central authority, such as a government or bank.",
    "The Apollo program was the third United States human spaceflight program carried out by NASA, which succeeded in landing the first humans on the Moon in 1969.",
    "The Industrial Revolution was the transition to new manufacturing processes in Great Britain, continental Europe, and the United States, that occurred during the period from around 1760 to about 1820.",
    "Climate change includes both global warming driven by human-induced emissions of greenhouse gases and the resulting large-scale shifts in weather patterns.",
    "Genetic engineering, also called genetic modification or genetic manipulation, is a set of technologies used to change the genetic makeup of cells.",
]

print('=== Capturing Real Activations for Layers 18-21 ===')
print(f'Using {len(SAMPLE_TEXTS)} sample texts (inline, no datasets library needed)')
print('Loading model...')

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map='cpu',
    low_cpu_mem_usage=True
)
model.eval()

layer_inputs = {l: [] for l in [18, 19, 20, 21]}
capture_count = 0
max_samples = len(SAMPLE_TEXTS)

for idx, text in enumerate(SAMPLE_TEXTS[:max_samples]):
    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=128)
    input_ids = inputs['input_ids']
    
    if input_ids.shape[1] < 10:
        continue
    
    with torch.no_grad():
        outputs = model(input_ids, output_hidden_states=True)
        hidden_states = outputs.hidden_states
        
        for target_layer in [18, 19, 20, 21]:
            hs = hidden_states[target_layer]
            layer_inputs[target_layer].append(hs.cpu().float().numpy())
    
    capture_count += 1
    if capture_count % 5 == 0:
        print(f'  Captured {capture_count} samples...')

print(f'\nTotal samples captured: {capture_count}')

for layer_idx in [18, 19, 20, 21]:
    activations = layer_inputs[layer_idx]
    # Pad to same sequence length for concatenation
    max_seq = max(a.shape[1] for a in activations)
    padded = []
    for a in activations:
        if a.shape[1] < max_seq:
            pad_width = [(0, 0), (0, max_seq - a.shape[1]), (0, 0)]
            a = np.pad(a, pad_width, mode='constant', constant_values=0)
        padded.append(a)
    all_acts = np.concatenate(padded, axis=0)
    
    fname = f'{OUTPUT_DIR}/layer_{layer_idx}_input_activations.npy'
    np.save(fname, all_acts)
    print(f'Layer {layer_idx} input: shape={all_acts.shape}, saved to {fname}')
    
    stats = {
        'layer': layer_idx,
        'shape': list(all_acts.shape),
        'mean': float(np.mean(all_acts)),
        'std': float(np.std(all_acts)),
        'min': float(np.min(all_acts)),
        'max': float(np.max(all_acts)),
        'median_abs': float(np.median(np.abs(all_acts))),
        'sparsity_frac': float(np.mean(np.abs(all_acts) < 0.01)),
    }
    with open(f'{OUTPUT_DIR}/layer_{layer_idx}_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)
    print(f'  Stats: mean={stats["mean"]:.4f}, std={stats["std"]:.4f}, median_abs={stats["median_abs"]:.4f}, sparsity={stats["sparsity_frac"]:.2%}')

meta = {
    'model': MODEL_ID,
    'num_samples': capture_count,
    'max_seq_length': 128,
    'target_layers': [18, 19, 20, 21],
    'note': 'Real activations entering layers 18-21 (output of previous layers)'
}
with open(f'{OUTPUT_DIR}/capture_metadata.json', 'w') as f:
    json.dump(meta, f, indent=2)

print(f'\nAll activations saved to {OUTPUT_DIR}/')
