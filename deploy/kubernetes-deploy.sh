#!/bin/bash
# HyperSearch AI Platform - Kubernetes Deployment Script

set -e

echo "🚀 HyperSearch AI Platform - Kubernetes Deployment"
echo "=================================================="

# Check prerequisites
echo "📋 Checking prerequisites..."
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl."
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Create namespaces
echo "🏗️  Creating namespaces..."
kubectl apply -f k8s/namespace.yaml

# Deploy configuration
echo "🔐 Deploying configuration..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Deploy backend
echo "🚀 Deploying backend..."
kubectl apply -f k8s/backend-deployment.yaml

# Wait for deployment
echo "⏳ Waiting for deployment..."
kubectl wait --for=condition=Available deployment/hypersearch-backend -n hypersearch --timeout=300s

echo "🎉 HyperSearch AI Platform deployed successfully!"
echo "🌐 Check status: kubectl get pods -n hypersearch"