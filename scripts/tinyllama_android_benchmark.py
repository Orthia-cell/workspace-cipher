#!/usr/bin/env python3
"""
TinyLlama on Android — Weight Extraction + Inference Benchmark
For Laere Enterprises Analog Compute R&D

Run this on your Android tablet (Termux, Pydroid 3, or similar Python environment)
with TinyLlama installed. It will:
1. Find and load your TinyLlama model
2. Benchmark inference speed (tokens/sec)
3. Export weight matrices from one transformer block
4. Save everything to a zip you can send back

No GPU needed. Runs in ~30 seconds.
"""

import os
import sys
import time
import json
import zipfile
import glob

# Try to import what's available
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("[!] PyTorch not found. Will try llama.cpp / GGUF path.")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("[!] NumPy not found. Weight export will be limited.")

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# ============================================
# CONFIGURATION — Adjust these if needed
# ============================================
MODEL_PATH = os.environ.get("TINYLLAMA_PATH", "")
# Common locations to auto-detect
SEARCH_PATHS = [
    "./tinyllama",
    "./TinyLlama",
    "./models/tinyllama",
    "~/storage/models/tinyllama",
    "/sdcard/llama/models/tinyllama",
    ".",
]

OUTPUT_DIR = "./laere_analog_export"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================
# 1. Find the Model
# ============================================
def find_model():
    """Search for TinyLlama model files"""
    if MODEL_PATH and os.path.exists(MODEL_PATH):
        return MODEL_PATH
    
    for path in SEARCH_PATHS:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            # Check for GGUF or PyTorch files
            gguf = glob.glob(os.path.join(expanded, "*.gguf"))
            pt = glob.glob(os.path.join(expanded, "*.bin")) + glob.glob(os.path.join(expanded, "*.pt"))
            safetensors = glob.glob(os.path.join(expanded, "*.safetensors"))
            
            if gguf or pt or safetensors:
                print(f"[+] Found model files in: {expanded}")
                return expanded
    
    print("[-] Could not auto-detect model. Set TINYLLAMA_PATH env var.")
    print("    Example: export TINYLLAMA_PATH=/sdcard/llama/models/tinyllama")
    return None

# ============================================
# 2. Benchmark Inference
# ============================================
def benchmark_inference(model_path):
    """Run a quick inference benchmark"""
    results = {
        "model_path": model_path,
        "has_torch": HAS_TORCH,
        "has_transformers": HAS_TRANSFORMERS,
        "device": "cpu",
        "tokens_per_sec": None,
        "latency_ms": None,
    }
    
    # Try PyTorch / transformers path
    if HAS_TRANSFORMERS and HAS_TORCH:
        try:
            print("\n[*] Loading model with transformers (this may take a moment)...")
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float32,
                device_map="cpu",
                low_cpu_mem_usage=True,
            )
            
            prompt = "The future of artificial intelligence is"
            inputs = tokenizer(prompt, return_tensors="pt")
            
            # Warmup
            with torch.no_grad():
                _ = model.generate(inputs.input_ids, max_new_tokens=5, do_sample=False)
            
            # Benchmark: generate 50 tokens
            print("[*] Running benchmark (50 tokens)...")
            start = time.time()
            with torch.no_grad():
                output = model.generate(
                    inputs.input_ids,
                    max_new_tokens=50,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            elapsed = time.time() - start
            
            tokens_generated = output.shape[1] - inputs.input_ids.shape[1]
            tokens_per_sec = tokens_generated / elapsed
            latency_ms = (elapsed / tokens_generated) * 1000
            
            results["tokens_per_sec"] = round(tokens_per_sec, 2)
            results["latency_ms"] = round(latency_ms, 2)
            results["model_type"] = "transformers/pytorch"
            
            print(f"[+] Benchmark complete:")
            print(f"    Tokens generated: {tokens_generated}")
            print(f"    Time: {elapsed:.2f}s")
            print(f"    Speed: {tokens_per_sec:.2f} tok/sec")
            print(f"    Latency: {latency_ms:.1f} ms/tok")
            
            # Export one transformer block
            export_transformer_block(model, model_path)
            
        except Exception as e:
            print(f"[!] Transformers benchmark failed: {e}")
            results["error"] = str(e)
    
    # Try llama.cpp / GGUF path
    elif glob.glob(os.path.join(model_path, "*.gguf")):
        print("\n[*] GGUF model detected. Checking for llama.cpp...")
        # Check if main or llama-cli exists
        llama_bin = None
        for candidate in ["main", "llama-cli", "llama.cpp", "./main"]:
            if os.path.exists(candidate) or os.system(f"which {candidate} >/dev/null 2>&1") == 0:
                llama_bin = candidate
                break
        
        if llama_bin:
            gguf_file = glob.glob(os.path.join(model_path, "*.gguf"))[0]
            print(f"[*] Running llama.cpp benchmark on {os.path.basename(gguf_file)}")
            
            # Run a quick generation benchmark
            cmd = f'{llama_bin} -m "{gguf_file}" -p "The future of AI is" -n 50 --temp 0 -t 4 2>&1 | tee {OUTPUT_DIR}/llama_benchmark.log'
            print(f"    Command: {cmd}")
            os.system(cmd)
            
            # Parse the log for speed if possible
            results["model_type"] = "llama.cpp/gguf"
            results["gguf_file"] = os.path.basename(gguf_file)
        else:
            print("[!] llama.cpp binary not found. Skipping GGUF benchmark.")
            print("    If you have it installed, ensure 'main' or 'llama-cli' is in PATH.")
            results["model_type"] = "gguf (no llama.cpp)"
    
    else:
        print("[!] No compatible model format found for benchmarking.")
        results["model_type"] = "unknown"
    
    # Save results
    with open(f"{OUTPUT_DIR}/benchmark.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results

# ============================================
# 3. Export Transformer Block Weights
# ============================================
def export_transformer_block(model, model_path):
    """Export weights from layer 0 for analog tile analysis"""
    if not HAS_NUMPY:
        print("[!] NumPy not available. Skipping weight export.")
        return
    
    print("\n[*] Exporting transformer block 0 weights...")
    
    export_info = {
        "model_path": model_path,
        "exported_layers": [],
        "weight_shapes": {},
    }
    
    # Try to find transformer layers
    state_dict = model.state_dict()
    
    # Common naming patterns for transformer blocks
    layer_patterns = [
        "model.layers.0",           # Llama-style
        "transformer.h.0",          # GPT-Neo style
        "transformer.layer.0",      # BERT style
        "layers.0",                # Generic
    ]
    
    found_layer = None
    for pattern in layer_patterns:
        matching = [k for k in state_dict.keys() if pattern in k]
        if matching:
            found_layer = pattern
            print(f"[+] Found layer pattern: {pattern}")
            break
    
    if not found_layer:
        print("[!] Could not identify transformer layer pattern.")
        print("    Available keys (first 20):")
        for k in list(state_dict.keys())[:20]:
            print(f"      {k}")
        return
    
    # Export key weight matrices from layer 0
    key_weights = {
        "q_proj": "self_attn.q_proj.weight",
        "k_proj": "self_attn.k_proj.weight", 
        "v_proj": "self_attn.v_proj.weight",
        "o_proj": "self_attn.o_proj.weight",
        "gate_proj": "mlp.gate_proj.weight",
        "up_proj": "mlp.up_proj.weight",
        "down_proj": "mlp.down_proj.weight",
    }
    
    for name, suffix in key_weights.items():
        key = f"{found_layer}.{suffix}"
        if key in state_dict:
            weight = state_dict[key].cpu().numpy()
            filename = f"{OUTPUT_DIR}/layer0_{name}.npy"
            np.save(filename, weight)
            export_info["exported_layers"].append(name)
            export_info["weight_shapes"][name] = list(weight.shape)
            print(f"    [+] {name}: {weight.shape} → {filename}")
    
    # Also export full model metadata
    export_info["all_keys_sample"] = list(state_dict.keys())[:10]
    export_info["total_parameters"] = sum(p.numel() for p in model.parameters())
    
    with open(f"{OUTPUT_DIR}/export_info.json", "w") as f:
        json.dump(export_info, f, indent=2)
    
    print(f"\n[+] Exported {len(export_info['exported_layers'])} weight matrices")
    print(f"    Total model parameters: {export_info['total_parameters']:,}")

# ============================================
# 4. Package Everything
# ============================================
def package_results():
    """Zip up all results for easy transfer"""
    zip_path = f"{OUTPUT_DIR}/laere_analog_export.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                if file.endswith('.zip'):
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, OUTPUT_DIR)
                zf.write(filepath, arcname)
    
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"\n[+] Packaged results: {zip_path}")
    print(f"    Size: {size_mb:.1f} MB")
    print(f"\n[*] Send this file back to Orthia for analog tile mapping analysis.")
    
    return zip_path

# ============================================
# Main
# ============================================
def main():
    print("=" * 60)
    print("Laere Analog R&D — TinyLlama Android Benchmark")
    print("=" * 60)
    print(f"Python: {sys.version.split()[0]}")
    print(f"PyTorch: {torch.__version__ if HAS_TORCH else 'NOT FOUND'}")
    print(f"Transformers: {'OK' if HAS_TRANSFORMERS else 'NOT FOUND'}")
    print(f"NumPy: {'OK' if HAS_NUMPY else 'NOT FOUND'}")
    print(f"Output: {OUTPUT_DIR}/")
    
    # Find model
    model_path = find_model()
    if not model_path:
        print("\n[-] Exiting — no model found.")
        print("    Set TINYLLAMA_PATH to your model directory.")
        sys.exit(1)
    
    # Benchmark
    print(f"\n[*] Using model: {model_path}")
    results = benchmark_inference(model_path)
    
    # Package
    if any(glob.glob(f"{OUTPUT_DIR}/*")):
        zip_path = package_results()
    else:
        print("\n[!] Nothing to export.")
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Transfer laere_analog_export.zip back to Orthia")
    print("2. Orthia will map transformer weights to PCM analog tiles")
    print("3. Measure accuracy degradation from device noise")
    print("4. Compare analog inference speed vs. your digital baseline")

if __name__ == "__main__":
    main()
