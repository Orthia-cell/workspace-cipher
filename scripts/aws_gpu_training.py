"""
AWS GPU Instance Automation for Laere Analog Compute R&D
Launches an EC2 g4dn.xlarge (Tesla T4, 16GB VRAM, ~$0.50/hour)
Installs PyTorch + AIHWKIT, runs full ResNet-32 CIFAR-10 training
Downloads results to S3, terminates instance

Requirements: AWS credentials (env vars or ~/.aws/credentials)
Budget: ~$5-10 per full training run (200 epochs baseline + 50 epochs noise)
"""
import boto3
import time
import os
import sys

# Configuration
INSTANCE_TYPE = 'g4dn.xlarge'
AMI_ID = 'ami-0c02fb55956c7d316'  # Amazon Linux 2023 with NVIDIA drivers (us-east-1)
KEY_NAME = os.getenv('AWS_KEY_NAME', 'laere-gpu-key')
SECURITY_GROUP = os.getenv('AWS_SECURITY_GROUP', 'default')
REGION = os.getenv('AWS_REGION', 'us-east-1')
S3_BUCKET = os.getenv('S3_BUCKET', 'laere-research-results')

# User data script for instance initialization
USER_DATA = """#!/bin/bash
set -e

# Update and install dependencies
yum update -y
yum install -y python3-pip git htop nvtop

# Install NVIDIA drivers and CUDA
amazon-linux-extras install -y nvidia

# Install PyTorch with CUDA
pip3 install torch torchvision aihwkit

# Clone workspace-cipher repo
cd /home/ec2-user
su - ec2-user -c 'git clone https://github.com/Orthia-cell/workspace-cipher.git'

# Download training script and run
su - ec2-user -c 'cd workspace-cipher && python3 scripts/resnet32_cifar10_analog.py 2>&1 | tee training.log'

# Upload results to S3
aws s3 cp resnet32_baseline_best.pth s3://{s3_bucket}/analog-compute/{timestamp}/
aws s3 cp resnet32_noise_best.pth s3://{s3_bucket}/analog-compute/{timestamp}/
aws s3 cp training.log s3://{s3_bucket}/analog-compute/{timestamp}/

# Signal completion
echo "Training complete. Results uploaded to S3." >> /home/ec2-user/training-complete.txt

# Terminate instance after 5 minute grace period
sleep 300
aws ec2 terminate-instances --instance-ids $(curl -s http://169.254.169.254/latest/meta-data/instance-id) --region {region}
"""

def launch_training_instance():
    """Launch EC2 instance, run training, auto-terminate"""
    ec2 = boto3.client('ec2', region_name=REGION)
    
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    user_data = USER_DATA.format(s3_bucket=S3_BUCKET, timestamp=timestamp, region=REGION)
    
    print(f"Launching {INSTANCE_TYPE} in {REGION}...")
    print(f"Estimated cost: ~$0.50/hour, total ~$5-10 for full training run")
    
    try:
        response = ec2.run_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            KeyName=KEY_NAME,
            SecurityGroups=[SECURITY_GROUP],
            UserData=user_data,
            InstanceInitiatedShutdownBehavior='terminate',
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': f'laere-resnet32-training-{timestamp}'},
                    {'Key': 'Project', 'Value': 'analog-compute'},
                    {'Key': 'Owner', 'Value': 'laere'},
                    {'Key': 'AutoTerminate', 'Value': 'true'}
                ]
            }],
            BlockDeviceMappings=[{
                'DeviceName': '/dev/xvda',
                'Ebs': {'VolumeSize': 50, 'VolumeType': 'gp3'}
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        print(f"Instance launched: {instance_id}")
        print(f"Training results will be uploaded to: s3://{S3_BUCKET}/analog-compute/{timestamp}/")
        
        # Wait for instance to be running
        print("Waiting for instance to reach 'running' state...")
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])
        
        # Get instance details
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'pending')
        
        print(f"Instance running at: {public_ip}")
        print(f"SSH: ssh -i ~/.ssh/{KEY_NAME}.pem ec2-user@{public_ip}")
        print(f"Monitor logs: ssh ... 'tail -f workspace-cipher/training.log'")
        
        return instance_id, timestamp
        
    except Exception as e:
        print(f"Error launching instance: {e}")
        sys.exit(1)

def check_training_status(instance_id):
    """Check if training is complete via S3"""
    s3 = boto3.client('s3', region_name=REGION)
    
    print("Checking S3 for results...")
    try:
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=f'analog-compute/'
        )
        
        if 'Contents' in response:
            print(f"Found {len(response['Contents'])} result objects in S3")
            for obj in response['Contents'][-5:]:
                print(f"  - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("No results found yet. Training may still be in progress.")
            
    except Exception as e:
        print(f"Error checking S3: {e}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Laere Analog Compute GPU Training')
    parser.add_argument('--launch', action='store_true', help='Launch training instance')
    parser.add_argument('--check', action='store_true', help='Check training status')
    parser.add_argument('--instance-id', help='Instance ID to check')
    
    args = parser.parse_args()
    
    if args.launch:
        instance_id, timestamp = launch_training_instance()
        print(f"\nTo check status later: python aws_gpu_training.py --check")
    elif args.check:
        check_training_status(args.instance_id)
    else:
        print("Usage:")
        print("  python aws_gpu_training.py --launch    # Launch training instance")
        print("  python aws_gpu_training.py --check       # Check S3 for results")
        print(f"\nPrerequisites:")
        print(f"  - AWS credentials configured (aws configure)")
        print(f"  - S3 bucket '{S3_BUCKET}' created")
        print(f"  - SSH key '{KEY_NAME}' in AWS EC2")
