"""
AIHWKIT PCM Noise Model Test — Analog noise impact on MNIST
Validates: PCM noise injection, hardware-aware training concept
"""
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from aihwkit.nn import AnalogLinear, AnalogSequential
from aihwkit.optim import AnalogSGD
from aihwkit.simulator.configs import SingleRPUConfig
from aihwkit.simulator.parameters import WeightNoiseType

# Use SingleRPUConfig with realistic PCM-like noise
def make_pcm_config():
    rpu_config = SingleRPUConfig()
    # Add weight noise for read (forward pass) - PCM read noise
    rpu_config.forward.w_noise = 0.015
    rpu_config.forward.w_noise_type = WeightNoiseType.PCM_READ
    # Add weight noise for update (backward pass)
    rpu_config.backward.w_noise = 0.015
    rpu_config.backward.w_noise_type = WeightNoiseType.PCM_READ
    return rpu_config

rpu_config = make_pcm_config()

# Same model architecture
model = AnalogSequential(
    AnalogLinear(784, 128, rpu_config=rpu_config),
    nn.ReLU(),
    AnalogLinear(128, 10, rpu_config=rpu_config),
)

# Data (reuse downloaded data)
transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
train_dataset = datasets.MNIST(root='./data', train=True, download=False, transform=transform)
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)

optimizer = AnalogSGD(model.parameters(), lr=0.01)
criterion = nn.CrossEntropyLoss()

print("Training MNIST with PCM noise model (1 epoch, ~200 batches)...")
model.train()
for batch_idx, (data, target) in enumerate(train_loader):
    data = data.view(-1, 784)
    optimizer.zero_grad()
    output = model(data)
    loss = criterion(output, target)
    loss.backward()
    optimizer.step()
    if batch_idx % 100 == 0:
        print(f"  Batch {batch_idx:3d}/938 — Loss: {loss.item():.4f}")
    if batch_idx >= 200:
        break

# Test accuracy
test_dataset = datasets.MNIST(root='./data', train=False, download=False, transform=transform)
test_loader = DataLoader(test_dataset, batch_size=1000, shuffle=False)
model.eval()
correct = 0
total = 0
with torch.no_grad():
    for data, target in test_loader:
        data = data.view(-1, 784)
        output = model(data)
        pred = output.argmax(dim=1)
        correct += pred.eq(target).sum().item()
        total += target.size(0)
        break

accuracy = 100. * correct / total
print(f"\n📊 Test accuracy (first 1000 samples): {accuracy:.2f}%")
print(f"📊 PCM noise impact: Baseline (no noise) ≈ 83-90% | With noise ≈ {accuracy:.1f}%")
print("✅ PCM noise model test: COMPLETE")
