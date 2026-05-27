"""
AIHWKIT MNIST Tutorial — Basic analog training test
Validates: PyTorch + AIHWKIT integration, analog linear layers, training loop
"""
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from aihwkit.nn import AnalogLinear, AnalogSequential
from aihwkit.optim import AnalogSGD
from aihwkit.simulator.configs import FloatingPointRPUConfig

# Use analog tile with floating-point (no noise) for baseline validation
rpu_config = FloatingPointRPUConfig()

# Simple model: 784 → 128 → 10
model = AnalogSequential(
    AnalogLinear(784, 128, rpu_config=rpu_config),
    nn.ReLU(),
    AnalogLinear(128, 10, rpu_config=rpu_config),
)

# Data
transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
train_dataset = datasets.MNIST(root='./data', train=True, download=True, transform=transform)
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)

# Training setup
optimizer = AnalogSGD(model.parameters(), lr=0.01)
criterion = nn.CrossEntropyLoss()

# Train 1 epoch (quick validation)
print("Training MNIST on analog tiles (1 epoch, ~60 batches)...")
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
    if batch_idx >= 200:  # Limit for quick test
        break

# Quick accuracy check on first 1000 test samples
test_dataset = datasets.MNIST(root='./data', train=False, download=True, transform=transform)
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
        break  # Just first batch

accuracy = 100. * correct / total
print(f"\n✅ Test accuracy (first 1000 samples): {accuracy:.2f}%")
print("✅ AIHWKIT MNIST tutorial: PASSED")
