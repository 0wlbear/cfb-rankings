#!/bin/bash

# College Football Rankings App - AWS Lightsail Deployment Script

echo "🏈 CFB Rankings - Lightsail Deployment"
echo "======================================"

# Configuration
APP_NAME="cfb-rankings"
SERVICE_NAME="cfb-rankings-service"
REGION="us-east-1"  # Change if needed

# Build Docker image
echo "📦 Building Docker image..."
docker build -t $APP_NAME .

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$APP_NAME"

echo "🏷️  Tagging image for ECR..."
docker tag $APP_NAME:latest $ECR_URI:latest

# Create ECR repository if it doesn't exist
echo "📂 Creating ECR repository..."
aws ecr create-repository --repository-name $APP_NAME --region $REGION 2>/dev/null || echo "Repository already exists"

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Push image
echo "⬆️  Pushing image to ECR..."
docker push $ECR_URI:latest

# Create Lightsail container service (if it doesn't exist)
echo "🚀 Creating Lightsail container service..."
aws lightsail create-container-service \
    --service-name $SERVICE_NAME \
    --power nano \
    --scale 1 \
    --region $REGION 2>/dev/null || echo "Service already exists"

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
sleep 30

# Create deployment configuration
cat > deployment.json << DEPLOY_EOF
{
  "containers": {
    "cfb-app": {
      "image": "$ECR_URI:latest",
      "ports": {
        "5000": "HTTP"
      },
      "environment": {
        "FLASK_ENV": "production",
        "SECRET_KEY": "$(openssl rand -base64 32)"
      }
    }
  },
  "publicEndpoint": {
    "containerName": "cfb-app",
    "containerPort": 5000,
    "healthCheck": {
      "healthyThreshold": 2,
      "unhealthyThreshold": 2,
      "timeoutSeconds": 5,
      "intervalSeconds": 30,
      "path": "/health",
      "successCodes": "200"
    }
  }
}
DEPLOY_EOF

# Deploy to Lightsail
echo "🚢 Deploying to Lightsail..."
aws lightsail create-container-service-deployment \
    --service-name $SERVICE_NAME \
    --cli-input-json file://deployment.json \
    --region $REGION

# Clean up
rm deployment.json

echo "✅ Deployment initiated!"
echo ""
echo "📊 Check deployment status:"
echo "aws lightsail get-container-services --service-name $SERVICE_NAME --region $REGION"
echo ""
echo "🌐 Your app URL will be displayed after deployment completes:"
echo "aws lightsail get-container-services --service-name $SERVICE_NAME --region $REGION --query 'containerServices[0].url' --output text"
echo ""
echo "📝 To view logs:"
echo "aws lightsail get-container-log --service-name $SERVICE_NAME --container-name cfb-app --region $REGION"
